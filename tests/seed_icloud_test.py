"""
Seed iCloud Test — crée de faux RDVs dans ton calendrier Apple pour tester.

Ce script :
  1. Se connecte à iCloud via CalDAV (credentials dans .env)
  2. Injecte ~5 RDVs fictifs de coiffeuse pour AUJOURD'HUI et DEMAIN
  3. Lit en retour les événements créés
  4. Calcule et affiche les créneaux libres
  5. Te demande si tu veux nettoyer (supprime les événements [TEST-KYANA])

Usage :
    python tests/seed_icloud_test.py              # crée + demande confirmation pour supprimer
    python tests/seed_icloud_test.py --cleanup    # supprime uniquement les événements TEST
    python tests/seed_icloud_test.py --no-cleanup # crée sans supprimer (laisse dans le calendrier)
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()


# ── Faux RDVs à injecter ──────────────────────────────────────────────────────

FAKE_APPOINTMENTS: list[tuple[str, int, int, int, int]] = [
    # (résumé, h_start, m_start, h_end, m_end)
    ("Retwist",             9,  0, 10, 30),
    ("Box Braids",          10, 30, 13, 30),
    ("Coupe Afro",          14,  0, 14, 45),
    ("Entretien Locks",     15,  0, 16,  0),
    ("Soin Hydratation",    16, 30, 17, 15),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def header(msg: str) -> None:
    print(f"\n{'═' * 52}")
    print(f"  {msg}")
    print("═" * 52)


def section(msg: str) -> None:
    print(f"\n{'─' * 52}")
    print(f"  {msg}")
    print("─" * 52)


def ok(msg: str)   -> None: print(f"  ✅  {msg}")
def fail(msg: str) -> None: print(f"  ❌  {msg}")
def info(msg: str) -> None: print(f"  ℹ️   {msg}")


# ── Étapes ────────────────────────────────────────────────────────────────────

def step_connect() -> "ICloudCalendar | None":  # type: ignore[name-defined]
    """Vérifie la connexion à iCloud et retourne une instance connectée."""
    from app.services.calendar_service import ICloudCalendar

    section("1 · Connexion à iCloud CalDAV")
    try:
        cal = ICloudCalendar()
        cal._connect()  # lève une exception si les credentials sont invalides
        ok("Connexion iCloud réussie !")
        return cal
    except ValueError as e:
        fail(f"Credentials manquants : {e}")
        print("\n  → Vérifie ton .env : CALDAV_EMAIL et CALDAV_APP_PASSWORD")
        print("  → CALDAV_EMAIL doit être une adresse iCloud (pas Gmail)")
        return None
    except ConnectionError as e:
        fail(f"Impossible de se connecter : {e}")
        print("\n  Causes possibles :")
        print("  • Email Gmail au lieu d'iCloud (@icloud.com / @me.com / @mac.com)")
        print("  • Mot de passe d'application incorrect ou expiré")
        print("  → Régénère-le sur : appleid.apple.com → Sécurité → Mots de passe d'apps")
        return None
    except Exception as e:
        fail(f"Erreur inattendue : {e}")
        return None


def step_create_events(cal, target_date: date) -> list[str]:
    """Crée les faux RDVs dans iCloud. Retourne les UIDs créés."""
    from app.services.calendar_service import ICloudCalendar

    section(f"2 · Création des RDVs fictifs ({target_date.strftime('%A %d/%m/%Y')})")
    created_uids: list[str] = []

    for summary, h_s, m_s, h_e, m_e in FAKE_APPOINTMENTS:
        start = datetime.combine(target_date, time(h_s, m_s))
        end   = datetime.combine(target_date, time(h_e, m_e))
        try:
            uid = cal.create_event(
                summary=summary,
                start=start,
                end=end,
                description="Événement de test généré par Kyana",
                test_event=True,   # préfixe [TEST-KYANA] dans le titre
            )
            created_uids.append(uid)
            ok(f"{summary:30s}  {start.strftime('%Hh%M')} → {end.strftime('%Hh%M')}")
        except Exception as e:
            fail(f"Impossible de créer '{summary}' : {e}")

    print(f"\n  {len(created_uids)}/{len(FAKE_APPOINTMENTS)} RDVs créés dans ton calendrier Apple.")
    return created_uids


def step_read_and_display(cal, target_date: date) -> None:
    """Relit les événements depuis iCloud et affiche les créneaux libres."""
    from app.services.calendar_service import get_free_slots, build_calendar_context
    import os

    section(f"3 · Lecture des événements depuis iCloud ({target_date.strftime('%d/%m/%Y')})")

    # Recharge les settings pour s'assurer que le cache est propre
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    events = cal.get_events(target_date)
    if not events:
        fail("Aucun événement lu depuis iCloud — les créations ont-elles fonctionné ?")
        return

    print(f"\n  Événements lus ({len(events)}) :")
    for ev in events:
        tag = " 🧪" if "[TEST-KYANA]" in ev.summary else ""
        print(f"    🔒 {ev}{tag}")

    section(f"4 · Créneaux libres calculés par Kyana")
    context = build_calendar_context(target_date)
    print(f"\n{context}\n")

    slots = get_free_slots(target_date)
    if slots:
        ok(f"{len(slots)} créneau(x) libre(s) identifié(s)")
        DAYS_FR = ["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"]
        day_fr = DAYS_FR[target_date.weekday()]
        print("\n  💬 Exemple de réponse que l'IA génèrerait :")
        first = slots[0]
        h = first.start.strftime("%Hh")
        print(f'  "coucou ! oui j\'ai de la place {day_fr} à {h}')
        if len(slots) > 1:
            second = slots[1]
            print(f'   ou sinon à {second.start.strftime("%Hh")}, t\'as une préférence ? ✂️"')
        else:
            print(f'   tu veux que je te bloque ça ? ✂️"')
    else:
        info("Aucun créneau libre — planning complet pour ce jour")


def step_cleanup(cal, target_date: date, ask: bool = True) -> None:
    """Supprime les événements [TEST-KYANA] du calendrier."""
    section("5 · Nettoyage des RDVs de test")

    if ask:
        print("\n  Les RDVs [TEST-KYANA] sont visibles dans ton Calendrier Apple.")
        answer = input("  → Veux-tu les supprimer maintenant ? [o/N] : ").strip().lower()
        if answer not in ("o", "oui", "y", "yes"):
            info("Nettoyage annulé — supprime-les manuellement dans Calendrier.app")
            info("Ou relance avec : python tests/seed_icloud_test.py --cleanup")
            return

    try:
        deleted = cal.delete_test_events(target_date)
        if deleted:
            ok(f"{deleted} événement(s) [TEST-KYANA] supprimé(s) de iCloud ✓")
        else:
            info("Aucun événement [TEST-KYANA] trouvé à supprimer")
    except Exception as e:
        fail(f"Erreur lors du nettoyage : {e}")


# ── Point d'entrée ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    cleanup_only = "--cleanup" in args
    no_cleanup   = "--no-cleanup" in args

    header("🧪 SEED iCLOUD — Test en conditions réelles")
    print(f"  Date cible : aujourd'hui ({date.today().strftime('%A %d/%m/%Y')})")
    print(f"  Mode : {'NETTOYAGE UNIQUEMENT' if cleanup_only else 'CREATION + LECTURE'}")

    # ── 1. Connexion ──
    cal = step_connect()
    if cal is None:
        sys.exit(1)

    target_date = date.today()

    # ── Mode nettoyage seul ──
    if cleanup_only:
        step_cleanup(cal, target_date=None, ask=False)  # type:ignore  # cherche sur 30j
        sys.exit(0)

    # ── 2. Création ──
    created = step_create_events(cal, target_date)
    if not created:
        fail("Aucun événement créé — abandon")
        sys.exit(1)

    print("\n  ⏳ Quelques secondes pour que iCloud propage les changements...")
    import time as _time
    _time.sleep(3)

    # ── 3 & 4. Lecture + Analyse ──
    step_read_and_display(cal, target_date)

    # ── 5. Nettoyage ──
    if no_cleanup:
        info("--no-cleanup : les RDVs [TEST-KYANA] restent dans ton calendrier")
        info("Supprime-les avec : python tests/seed_icloud_test.py --cleanup")
    else:
        step_cleanup(cal, target_date, ask=True)

    header("✅ TEST TERMINÉ")
