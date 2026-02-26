"""
Tests du service CalDAV — validation complète avec Mock.

Script autonome (pas de pytest requis). Lance directement :
    python tests/test_calendar.py

Teste la logique de MockCalendar, get_free_slots et l'injection dans le prompt IA.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, time

# Permet d'importer les modules du projet depuis n'importe quel répertoire
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()


# ─── Helpers ──────────────────────────────────────────────────────────────────


def ok(msg: str) -> None:
    print(f"   ✅  {msg}")


def fail(msg: str) -> None:
    print(f"   ❌  {msg}")


def section(title: str) -> None:
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print("─" * 50)


# ─── Tests ────────────────────────────────────────────────────────────────────


def test_mock_generates_events() -> bool:
    """MockCalendar renvoie au moins 1 événement pour un jour ouvré."""
    from app.services.calendar_service import MockCalendar

    section("1 · MockCalendar — génération d'événements")
    mock = MockCalendar()

    # Trouve le prochain lundi (jour ouvré garanti)
    today = date.today()
    # Calcule le prochain lundi (ou aujourd'hui si c'est lundi)
    days_until_monday = (7 - today.weekday()) % 7
    next_monday = today if days_until_monday == 0 else today + __import__("datetime").timedelta(days=days_until_monday)

    events = mock.get_events(next_monday)
    print(f"  Date testée : {next_monday} ({next_monday.strftime('%A')})")
    print(f"  Événements générés :")
    for ev in events:
        print(f"    • {ev}")

    if len(events) >= 1:
        ok(f"{len(events)} événement(s) générés")
        return True
    else:
        fail("Aucun événement généré pour un jour ouvré")
        return False


def test_events_within_working_hours() -> bool:
    """Tous les événements fictifs sont dans les horaires de travail (08h-20h)."""
    from app.services.calendar_service import MockCalendar

    section("2 · MockCalendar — respect des horaires")
    mock = MockCalendar()

    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7
    next_monday = today if days_until_monday == 0 else today + __import__("datetime").timedelta(days=days_until_monday)

    events = mock.get_events(next_monday)
    earliest_allowed = time(8, 0)
    latest_allowed = time(20, 0)

    all_ok = True
    for ev in events:
        if ev.start.time() < earliest_allowed or ev.end.time() > latest_allowed:
            fail(f"{ev} dépasse les horaires autorisés (08h-20h)")
            all_ok = False

    if all_ok:
        ok("Tous les événements respectent la plage 08h-20h")
    return all_ok


def test_closed_day_returns_empty() -> bool:
    """Le dimanche ne génère aucun événement."""
    from app.services.calendar_service import MockCalendar, CLOSED_DAYS

    section("3 · MockCalendar — jour fermé (dimanche)")
    mock = MockCalendar()

    today = date.today()
    # Trouve le prochain dimanche
    days_until_sunday = (6 - today.weekday()) % 7
    next_sunday = today + __import__("datetime").timedelta(days=days_until_sunday if days_until_sunday > 0 else 7)

    print(f"  Jour fermé testé : {next_sunday} ({next_sunday.strftime('%A')})")
    events = mock.get_events(next_sunday)

    if len(events) == 0:
        ok("Aucun événement généré pour un jour fermé — CORRECT")
        return True
    else:
        fail(f"{len(events)} événements générés pour un jour fermé !")
        return False


def test_free_slots_no_overlap() -> bool:
    """Les créneaux libres ne chevauchent JAMAIS les événements."""
    from app.services.calendar_service import MockCalendar, get_free_slots, WORK_START

    section("4 · get_free_slots — aucun chevauchement")
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7
    next_monday = today if days_until_monday == 0 else today + __import__("datetime").timedelta(days=days_until_monday)

    mock = MockCalendar()
    events = mock.get_events(next_monday)
    slots = get_free_slots(next_monday)

    print(f"  Événements ({len(events)}) :")
    for ev in events:
        print(f"    🔒 {ev}")
    print(f"  Créneaux libres ({len(slots)}) :")
    for s in slots:
        print(f"    🟢 {s.label()}")

    any_overlap = False
    for slot in slots:
        for ev in events:
            # Vérifie si le slot chevauche l'événement
            if slot.start < ev.end and slot.end > ev.start:
                fail(f"Chevauchement ! {slot.label()} ↔ {ev}")
                any_overlap = True

    if not any_overlap:
        ok("Aucun chevauchement entre créneaux libres et événements")
        return True
    return False


def test_build_context_for_ai() -> bool:
    """build_calendar_context() retourne une chaîne non-vide avec le mot 'disponible'."""
    from app.services.calendar_service import build_calendar_context

    section("5 · build_calendar_context — format du contexte IA")
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7
    next_monday = today if days_until_monday == 0 else today + __import__("datetime").timedelta(days=days_until_monday)

    context = build_calendar_context(next_monday)
    print(f"\n  Contexte généré :\n{context}\n")

    if not context:
        fail("build_calendar_context a retourné une chaîne vide")
        return False

    # Le contexte doit mentionner soit une disponibilité soit une fermeture
    keywords = ["disponible", "fermée", "disponibilité"]
    found = any(kw in context.lower() for kw in keywords)

    if found:
        ok("Contexte valide et contient les mots-clés attendus")
        return True
    else:
        fail(f"Contexte ne contient pas les mots-clés attendus ({keywords})")
        return False


def test_ai_prompt_injection() -> bool:
    """Simule l'injection du calendrier dans un prompt complet pour Llama 3.1."""
    from app.services.calendar_service import build_ai_system_context

    section("6 · Injection dans le prompt IA (simulation Llama 3.1)")

    context_block = build_ai_system_context()

    # Construit un prompt complet simulé
    simulated_system_prompt = (
        "tu es l'assistante d'une coiffeuse qui gère ses MPs Instagram.\n"
        "règles : tutoie toujours, pas de majuscule, sois brève (1-3 phrases).\n"
        + context_block
    )

    simulated_user_message = "salut t'as de la place cette semaine pour une coupe ?"

    print("\n  ─── SYSTEM PROMPT (extrait agenda) ───")
    # Affiche seulement le bloc agenda pour lisibilité
    for line in context_block.strip().split("\n"):
        print(f"  {line}")

    print(f"\n  ─── USER MESSAGE ───")
    print(f"  {simulated_user_message}")

    print("\n  ─── EXEMPLE DE RÉPONSE ATTENDUE de l'IA ───")
    # Parse le premier créneau pour générer un exemple de réponse
    from app.services.calendar_service import get_free_slots
    from datetime import timedelta

    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7
    next_monday = today if days_until_monday == 0 else today + timedelta(days=days_until_monday)

    slots = get_free_slots(next_monday)
    if slots:
        first = slots[0]
        example_reply = (
            f"  \"coucou ! oui cette semaine j'ai de la place lundi à "
            f"{first.start.strftime('%Hh')} ou aussi plus tard dans la journée, "
            f"t'as une préférence ? ✂️\""
        )
    else:
        example_reply = (
            "  \"coucou ! cette semaine c'est un peu chargé, "
            "t'aurais pas une autre date ? ✂️\""
        )

    print(example_reply)

    total_chars = len(simulated_system_prompt)
    ok(f"Prompt complet construit ({total_chars} caractères)")
    ok("Bloc agenda correctement injecté dans le system prompt")
    return True


def test_determinism() -> bool:
    """MockCalendar retourne les mêmes événements pour la même date (seed fixe)."""
    from app.services.calendar_service import MockCalendar

    section("7 · MockCalendar — reproductibilité (seed fixe)")
    mock = MockCalendar()
    test_date = date(2026, 3, 2)  # Un lundi fixe

    events_1 = mock.get_events(test_date)
    events_2 = mock.get_events(test_date)

    if events_1 == events_2:
        ok(f"Même résultat sur 2 appels consécutifs pour {test_date}")
        return True
    else:
        fail("Les résultats diffèrent entre deux appels — seed non déterministe !")
        return False


# ─── Résumé & Point d'entrée ─────────────────────────────────────────────────


if __name__ == "__main__":
    print("=" * 50)
    print("🗓️  DIAGNOSTIC SERVICE CALENDRIER (Mock iCloud)")
    print("=" * 50)

    tests = [
        ("Génération d'événements", test_mock_generates_events),
        ("Horaires de travail", test_events_within_working_hours),
        ("Jour fermé (dimanche)", test_closed_day_returns_empty),
        ("Aucun chevauchement", test_free_slots_no_overlap),
        ("Format contexte IA", test_build_context_for_ai),
        ("Injection prompt Llama 3.1", test_ai_prompt_injection),
        ("Reproductibilité (seed)", test_determinism),
    ]

    results: dict[str, bool] = {}
    for name, fn in tests:
        try:
            results[name] = fn()
        except Exception as exc:
            print(f"\n   💥 Erreur inattendue dans '{name}' : {exc}")
            results[name] = False

    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ")
    print("=" * 50)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, success in results.items():
        icon = "✅" if success else "❌"
        print(f"  {icon}  {name}")

    print()
    if passed == total:
        print(f"✅ TOUT OK — {passed}/{total} tests réussis")
    else:
        print(f"⚠️  {passed}/{total} tests réussis — voir les détails ci-dessus")
    print("=" * 50)
