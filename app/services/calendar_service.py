"""
Service Calendrier iCloud (CalDAV) — avec système de Mock intégré.

Deux backends interchangeables via la variable d'environnement CALENDAR_USE_MOCK :
  - ``MockCalendar``   : génère des RDVs fictifs réalistes (développement / test)
  - ``ICloudCalendar`` : se connecte au vrai calendrier Apple via CalDAV (production)

Usage rapide ::

    from datetime import date
    from app.services.calendar_service import get_free_slots, build_calendar_context

    slots = get_free_slots(date.today())
    context_str = build_calendar_context(date.today())
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ─── Constantes ──────────────────────────────────────────────────────────────

# Plage de travail de la coiffeuse (bornes incluses pour les créneaux libres)
WORK_START = time(9, 0)
WORK_END = time(18, 0)

# Durée minimale d'un créneau libre pour qu'il soit proposé (en minutes)
MIN_SLOT_MINUTES = 30

# Jours de fermeture (0=lundi … 6=dimanche)
CLOSED_DAYS: set[int] = {6}  # fermé le dimanche

# Données fictives pour le MockCalendar — spécialité coiffure afro/locks
_MOCK_APPOINTMENTS: list[tuple[str, int, int, int]] = [
    # (résumé, heure_début, heure_fin, poids)  ← poids pour random.choices
    ("Retwist", 9, 11, 4),
    ("Starter Locks", 9, 12, 2),
    ("Coupe Afro", 9, 10, 3),
    ("Tresses Vanilles", 10, 13, 3),
    ("Box Braids", 10, 14, 2),
    ("Shampoing + Soin", 11, 12, 3),
    ("Retwist + Soin", 11, 13, 3),
    ("Faux Locs", 13, 16, 2),
    ("Coupe Enfant", 14, 15, 3),
    ("Démêlage + Soin", 14, 16, 2),
    ("Entretien Locks", 15, 16, 3),
    ("Twist Out", 15, 17, 2),
    ("Coupe + Façon", 16, 17, 3),
    ("Soin Hydratation", 16, 18, 2),
]


# ─── Modèle de données ───────────────────────────────────────────────────────


@dataclass(frozen=True, order=True)
class CalendarEvent:
    """Représente un rendez-vous sur le calendrier."""

    start: datetime
    end: datetime
    summary: str

    @property
    def duration_minutes(self) -> int:
        """Durée de l'événement en minutes."""
        return int((self.end - self.start).total_seconds() / 60)

    def __str__(self) -> str:
        return (
            f"{self.summary} "
            f"({self.start.strftime('%Hh%M')} → {self.end.strftime('%Hh%M')})"
        )


@dataclass(frozen=True, order=True)
class FreeSlot:
    """Représente un créneau libre."""

    start: datetime
    end: datetime

    @property
    def duration_minutes(self) -> int:
        """Durée du créneau en minutes."""
        return int((self.end - self.start).total_seconds() / 60)

    def label(self) -> str:
        """Retourne une chaîne lisible, ex: '12h00 → 14h30 (2h30)'."""
        h = self.duration_minutes // 60
        m = self.duration_minutes % 60
        dur = f"{h}h{m:02d}" if m else f"{h}h"
        return (
            f"{self.start.strftime('%Hh%M')} → {self.end.strftime('%Hh%M')} ({dur})"
        )


# ─── Backend Mock ─────────────────────────────────────────────────────────────


class MockCalendar:
    """
    Calendrier fictif — simule le planning d'une coiffeuse pour la semaine courante.

    Génère des RDVs réalistes de façon déterministe selon la date (seed = date ISO).
    Pas d'appel réseau : idéal pour le développement et les tests.
    """

    def get_events(self, target_date: date) -> list[CalendarEvent]:
        """Retourne une liste d'événements fictifs pour *target_date*."""
        if target_date.weekday() in CLOSED_DAYS:
            logger.debug("MockCalendar: %s est un jour fermé", target_date)
            return []

        # Seed déterministe : même date → mêmes RDVs (reproductible en tests)
        rng = random.Random(target_date.isoformat())

        summaries = [apt[0] for apt in _MOCK_APPOINTMENTS]
        weights = [apt[3] for apt in _MOCK_APPOINTMENTS]
        # Lookup rapide : nom → (heure_début, heure_fin)
        appointment_hours: dict[str, tuple[int, int]] = {apt[0]: (apt[1], apt[2]) for apt in _MOCK_APPOINTMENTS}

        # Tire entre 3 et 6 RDVs distincts pour la journée
        target_count = rng.randint(3, 6)
        # Tire plus de candidats que nécessaire pour pouvoir dédoublonner
        candidate_names: list[str] = rng.choices(summaries, weights=weights, k=target_count * 3)

        events: list[CalendarEvent] = []
        occupied_start_hours: set[int] = set()  # évite deux RDVs à la même heure de début

        for name in candidate_names:
            if len(events) >= target_count:
                break
            h_start, h_end = appointment_hours[name]
            if h_start in occupied_start_hours:
                continue
            occupied_start_hours.add(h_start)

            events.append(
                CalendarEvent(
                    start=datetime.combine(target_date, time(h_start, 0)),
                    end=datetime.combine(target_date, time(h_end, 0)),
                    summary=name,
                )
            )

        return sorted(events)


# ─── Backend iCloud CalDAV ────────────────────────────────────────────────────


class ICloudCalendar:
    """
    Calendrier Apple iCloud via le protocole CalDAV.

    Nécessite que les variables d'environnement soient renseignées :
    - ``CALDAV_EMAIL``        : adresse email iCloud
    - ``CALDAV_APP_PASSWORD`` : mot de passe d'application Apple (16 caractères)
    - ``CALDAV_URL``          : ``https://caldav.icloud.com`` (par défaut)

    .. warning::
        N'utilise JAMAIS ton mot de passe iCloud principal ici !
        Génère un "mot de passe d'application" sur appleid.apple.com.
    """

    # Tag injecté dans le résumé des événements de test — permet de les retrouver et
    # de les supprimer proprement sans toucher aux vrais RDVs.
    TEST_TAG = "[TEST-KYANA]"

    def __init__(self) -> None:
        try:
            import caldav  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "La bibliothèque 'caldav' est manquante. "
                "Installe-la : pip install caldav"
            ) from exc

        self._settings = get_settings()
        self._calendar_cache = None  # cache de la connexion

    # ── Connexion ─────────────────────────────────────────────

    def _connect(self):
        """
        Ouvre (ou restitue depuis le cache) la connexion au calendrier iCloud.

        Stratégie de sélection du calendrier (dans l'ordre) :
        1. Calendrier dont le nom correspond à ``CALDAV_CALENDAR_NAME`` (si défini)
        2. Calendrier nommé "Kyana"
        3. Calendrier "Personnel" ou URL contenant /home/
        4. Calendrier "Travail" ou URL contenant /work/
        5. Premier calendrier dont le nom ne contient pas "rappels" / "reminders"
           (les Rappels sont des VTODO, iCloud refuse l'écriture de VEVENT dessus)
        """
        if self._calendar_cache is not None:
            return self._calendar_cache

        import caldav  # noqa: F811 — importé ici pour éviter l'import circulaire au module level

        if not self._settings.caldav_email or not self._settings.caldav_app_password:
            raise ValueError(
                "CALDAV_EMAIL et CALDAV_APP_PASSWORD doivent être définis dans .env"
            )

        client = caldav.DAVClient(
            url=self._settings.caldav_url,
            username=self._settings.caldav_email,
            password=self._settings.caldav_app_password,
        )
        principal = client.principal()
        calendars = principal.calendars()

        if not calendars:
            raise ConnectionError("Aucun calendrier trouvé sur le compte iCloud")

        # Filtre : exclut les calendriers Rappels (VTODO uniquement, écriture VEVENT interdite)
        _READONLY_KEYWORDS = {"rappels", "reminders", "anniversaires", "birthdays"}

        def _is_readonly(cal) -> bool:
            """Retourne True si le calendrier est de type Rappels/Anniversaires (lecture seule pour VEVENT)."""
            name_lower = (cal.name or "").lower()
            return any(kw in name_lower for kw in _READONLY_KEYWORDS)

        def _name(cal) -> str:
            """Retourne le nom du calendrier en minuscules."""
            return (cal.name or "").lower()

        def _url(cal) -> str:
            """Retourne l'URL CalDAV du calendrier en minuscules."""
            return str(cal.url).lower()

        # 1. Nom explicitement configuré via .env
        target_name = self._settings.caldav_calendar_name.strip().lower()
        if target_name:
            cal = next((c for c in calendars if _name(c) == target_name), None)
            if cal:
                self._calendar_cache = cal
                return cal
            logger.warning(
                "Calendrier '%s' non trouvé, sélection automatique", target_name
            )

        # 2. Nommé "kyana"
        cal = next((c for c in calendars if "kyana" in _name(c)), None)

        # 3. Personnel / home
        if not cal:
            cal = next(
                (c for c in calendars if "personnel" in _name(c) or "/home/" in _url(c)),
                None,
            )

        # 4. Travail / work
        if not cal:
            cal = next(
                (c for c in calendars if "travail" in _name(c) or "/work/" in _url(c)),
                None,
            )

        # 5. Premier calendrier non-Rappels
        if not cal:
            cal = next((c for c in calendars if not _is_readonly(c)), None)

        # Dernier recours : premier de la liste (peut échouer en écriture)
        if not cal:
            cal = calendars[0]
            logger.warning(
                "Aucun calendrier éditable identifié — utilisation de '%s' (peut être en lecture seule)",
                cal.name,
            )

        self._calendar_cache = cal
        return cal

    # ── Lecture ───────────────────────────────────────────────

    def get_events(self, target_date: date) -> list[CalendarEvent]:
        """
        Récupère les événements du calendrier iCloud pour *target_date*.

        Raises
        ------
        ValueError
            Si les identifiants CalDAV ne sont pas configurés.
        ConnectionError
            Si la connexion à iCloud échoue.
        """
        try:
            calendar = self._connect()

            start_dt = datetime.combine(target_date, time.min)
            end_dt = datetime.combine(target_date, time.max)

            raw_events = calendar.date_search(start=start_dt, end=end_dt, expand=True)

            events: list[CalendarEvent] = []
            for caldav_event in raw_events:
                try:
                    # caldav v2 : utilise icalendar_component (icalendar lib)
                    # caldav v1 : utilisait instance.vevent (vobject lib, supprimé)
                    comp = caldav_event.icalendar_component

                    ev_start = comp.get("DTSTART")
                    ev_end   = comp.get("DTEND")
                    summary  = str(comp.get("SUMMARY", "Sans titre"))

                    if ev_start is None or ev_end is None:
                        logger.debug("Événement sans DTSTART/DTEND ignoré")
                        continue

                    ev_start = ev_start.dt
                    ev_end   = ev_end.dt

                    # Convertit date → datetime si l'événement est journée entière
                    if hasattr(ev_start, "hour") is False:
                        ev_start = datetime.combine(ev_start, time.min)
                    if hasattr(ev_end, "hour") is False:
                        ev_end = datetime.combine(ev_end, time.min)

                    # Normalise en datetime naïf (strip timezone) pour comparaison simple
                    if hasattr(ev_start, "tzinfo") and ev_start.tzinfo:
                        ev_start = ev_start.replace(tzinfo=None)
                    if hasattr(ev_end, "tzinfo") and ev_end.tzinfo:
                        ev_end = ev_end.replace(tzinfo=None)

                    events.append(
                        CalendarEvent(start=ev_start, end=ev_end, summary=summary)
                    )

                except Exception as parse_exc:
                    logger.warning("Impossible de parser un événement : %s", parse_exc)
                    continue

            return sorted(events)

        except (ValueError, ConnectionError):
            raise
        except Exception as exc:
            logger.error("Erreur CalDAV iCloud (lecture) : %s", exc, exc_info=True)
            raise ConnectionError(f"Impossible de lire iCloud : {exc}") from exc

    # ── Écriture ──────────────────────────────────────────────

    def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str = "",
        test_event: bool = False,
    ) -> str:
        """
        Crée un événement dans le calendrier iCloud.

        Parameters
        ----------
        summary:
            Titre du RDV (ex: "Coupe Femme").
        start / end:
            Début et fin du RDV (datetimes naïfs, interprétés en heure locale).
        description:
            Description optionnelle visible dans Calendrier.app.
        test_event:
            Si True, préfixe le titre avec ``TEST_TAG`` pour pouvoir le retrouver
            et le supprimer automatiquement via ``delete_test_events()``.

        Returns
        -------
        str
            UID CalDAV de l'événement créé.
        """
        import uuid as _uuid

        try:
            calendar = self._connect()

            uid = str(_uuid.uuid4())
            title = f"{self.TEST_TAG} {summary}" if test_event else summary
            fmt = "%Y%m%dT%H%M%S"

            ical_data = (
                "BEGIN:VCALENDAR\r\n"
                "VERSION:2.0\r\n"
                "PRODID:-//Kyana//CalDAV//FR\r\n"
                "BEGIN:VEVENT\r\n"
                f"UID:{uid}\r\n"
                f"DTSTAMP:{datetime.utcnow().strftime(fmt)}Z\r\n"
                f"DTSTART:{start.strftime(fmt)}\r\n"
                f"DTEND:{end.strftime(fmt)}\r\n"
                f"SUMMARY:{title}\r\n"
                f"DESCRIPTION:{description}\r\n"
                "END:VEVENT\r\n"
                "END:VCALENDAR\r\n"
            )

            calendar.add_event(ical_data)
            logger.info("Événement créé dans iCloud : %s (%s → %s)", title, start, end)
            return uid

        except (ValueError, ConnectionError):
            raise
        except Exception as exc:
            logger.error("Erreur CalDAV iCloud (création) : %s", exc, exc_info=True)
            raise ConnectionError(f"Impossible de créer l'événement : {exc}") from exc

    # ── Suppression ───────────────────────────────────────────

    def delete_test_events(self, target_date: date | None = None) -> int:
        """
        Supprime tous les événements de test (dont le titre contient ``TEST_TAG``).

        Parameters
        ----------
        target_date:
            Si fourni, limite la suppression à cette journée.
            Si None, cherche sur les 30 prochains jours.

        Returns
        -------
        int
            Nombre d'événements supprimés.
        """
        try:
            calendar = self._connect()

            if target_date:
                start_dt = datetime.combine(target_date, time.min)
                end_dt = datetime.combine(target_date, time.max)
            else:
                start_dt = datetime.now()
                end_dt = start_dt + timedelta(days=30)

            raw_events = calendar.date_search(start=start_dt, end=end_dt, expand=True)
            deleted = 0

            for caldav_event in raw_events:
                try:
                    comp = caldav_event.icalendar_component
                    summary = str(comp.get("SUMMARY", ""))
                    if self.TEST_TAG in summary:
                        caldav_event.delete()
                        deleted += 1
                        logger.info("Événement TEST supprimé : %s", summary)
                except Exception as e:
                    logger.warning("Impossible de supprimer un événement : %s", e)

            logger.info("%d événement(s) TEST supprimé(s) de iCloud", deleted)
            return deleted

        except (ValueError, ConnectionError):
            raise
        except Exception as exc:
            logger.error("Erreur CalDAV iCloud (suppression) : %s", exc, exc_info=True)
            raise ConnectionError(f"Impossible de supprimer les événements : {exc}") from exc


# ─── API publique ─────────────────────────────────────────────────────────────


def get_events(target_date: date) -> list[CalendarEvent]:
    """
    Retourne les événements du calendrier iCloud pour *target_date*.
    """
    return ICloudCalendar().get_events(target_date)


def get_free_slots(target_date: date) -> list[FreeSlot]:
    """
    Calcule les créneaux libres pour *target_date* entre WORK_START et WORK_END.

    Les créneaux inférieurs à MIN_SLOT_MINUTES sont ignorés.

    Returns
    -------
    list[FreeSlot]
        Liste triée des créneaux libres, vide si jour fermé ou planning complet.
    """
    if target_date.weekday() in CLOSED_DAYS:
        return []

    events = get_events(target_date)

    # Bornes de la journée de travail
    day_start = datetime.combine(target_date, WORK_START)
    day_end = datetime.combine(target_date, WORK_END)

    # Clamp chaque événement dans la plage horaire de travail
    occupied: list[tuple[datetime, datetime]] = []
    for ev in events:
        clamped_start = max(ev.start, day_start)
        clamped_end = min(ev.end, day_end)
        if clamped_start < clamped_end:
            occupied.append((clamped_start, clamped_end))

    occupied.sort()

    # Fusionner les intervalles qui se chevauchent
    merged: list[tuple[datetime, datetime]] = []
    for interval_start, interval_end in occupied:
        if merged and interval_start <= merged[-1][1]:
            # Chevauchement : étend le dernier intervalle si nécessaire
            merged[-1] = (merged[-1][0], max(merged[-1][1], interval_end))
        else:
            merged.append((interval_start, interval_end))

    # Identifier les trous entre les RDVs
    free_slots: list[FreeSlot] = []
    scan_position = day_start  # avance au fil des RDVs pour trouver les trous

    for interval_start, interval_end in merged:
        if scan_position < interval_start:
            gap_minutes = (interval_start - scan_position).total_seconds() / 60
            if gap_minutes >= MIN_SLOT_MINUTES:
                free_slots.append(FreeSlot(start=scan_position, end=interval_start))
        scan_position = max(scan_position, interval_end)

    # Créneau après le dernier RDV
    if scan_position < day_end:
        remaining_minutes = (day_end - scan_position).total_seconds() / 60
        if remaining_minutes >= MIN_SLOT_MINUTES:
            free_slots.append(FreeSlot(start=scan_position, end=day_end))

    return free_slots


def build_calendar_context(target_date: date) -> str:
    """
    Retourne une chaîne en français décrivant les disponibilités pour *target_date*.

    Cette chaîne est conçue pour être injectée directement dans le prompt Llama 3.1.

    Example output ::

        📅 Samedi 1er mars — créneaux disponibles :
        • 9h00 → 10h00 (1h)
        • 12h30 → 14h00 (1h30)
        • 17h00 → 18h00 (1h)

    Parameters
    ----------
    target_date:
        La date pour laquelle générer le contexte.

    Returns
    -------
    str
        Texte formaté en français, ou message de fermeture si jour non travaillé.
    """
    DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    MONTHS_FR = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]

    day_name = DAYS_FR[target_date.weekday()]
    month_name = MONTHS_FR[target_date.month - 1]
    day_num = target_date.day
    suffix = "er" if day_num == 1 else ""
    date_label = f"{day_name} {day_num}{suffix} {month_name}"

    if target_date.weekday() in CLOSED_DAYS:
        return f"{date_label.capitalize()} — fermée ce jour-là."

    slots = get_free_slots(target_date)

    if not slots:
        return f"{date_label.capitalize()} — plus aucune disponibilité."

    lines = [f"{date_label.capitalize()} — créneaux disponibles :"]
    for slot in slots:
        lines.append(f"  • {slot.label()}")

    return "\n".join(lines)


def build_ai_system_context(target_date: date | None = None) -> str:
    """
    Construit le bloc de contexte agenda à insérer dans le system prompt de l'IA.

    Inclut les 7 prochains jours pour que l'IA puisse répondre aux questions
    sur n'importe quel jour de la semaine sans inventer de date.

    Parameters
    ----------
    target_date:
        Date de référence (par défaut : aujourd'hui).

    Returns
    -------
    str
        Bloc de texte à concaténer au SYSTEM_PROMPT existant.
    """
    today = target_date or date.today()
    DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

    lines = [
        "\n\n--- AGENDA (informations temps réel, 7 prochains jours) ---",
        f"Aujourd'hui : {DAYS_FR[today.weekday()]} {today.strftime('%d/%m/%Y')} (date ISO : {today.isoformat()})",
    ]

    for i in range(7):
        d = today + timedelta(days=i)
        label = "Aujourd'hui" if i == 0 else ("Demain" if i == 1 else DAYS_FR[d.weekday()].capitalize())
        ctx = build_calendar_context(d)
        lines.append(f"\n[{label} — {d.strftime('%d/%m/%Y')} / ISO : {d.isoformat()}]")
        lines.append(ctx)

    lines.append("----------------------------------------")
    lines.append(
        "IMPORTANT pour les RDVs : utilise TOUJOURS la date ISO exacte (YYYY-MM-DD) dans le champ 'date' du JSON. "
        "Ne devine JAMAIS la date — utilise uniquement les dates ISO fournies ci-dessus.\n"
        "Propose TOUJOURS le premier créneau disponible réel — ne dis jamais 'vendredi' si "
        "un créneau libre existe plus tôt dans la semaine."
    )

    return "\n".join(lines) + "\n"
