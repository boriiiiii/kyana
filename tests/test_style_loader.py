"""
test_style_loader.py
────────────────────
Vérifie le chargement et le filtrage du dataset style.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()


def test_dataset_loads():
    """Le dataset se charge sans erreur et retourne des exemples."""
    from app.services.style_loader import get_style_examples

    examples = get_style_examples(10)
    print(f"\n📦 Dataset chargé — {len(examples)} exemples demandés")
    assert len(examples) == 10, f"Attendu 10, reçu {len(examples)}"
    print("   ✅ get_style_examples(10) retourne bien 10 éléments")


def test_no_sensitive_data():
    """Aucun exemple ne contient de données sensibles."""
    from app.services.style_loader import get_style_examples

    for _ in range(5):  # plusieurs tirages
        examples = get_style_examples(20)
        for ex in examples:
            assert "[TEL]" not in ex, f"Donnée sensible trouvée : {ex!r}"
            assert ex.strip(), "Exemple vide détecté"
    print("   ✅ Aucune donnée sensible dans les exemples")


def test_randomness():
    """Deux appels successifs ne retournent pas exactement les mêmes exemples."""
    from app.services.style_loader import get_style_examples

    batch1 = get_style_examples(20)
    batch2 = get_style_examples(20)
    # Avec 20 tirages sur +5000 exemples, la proba d'identité est ~0
    assert batch1 != batch2, "Les deux tirages sont identiques — randomisation KO"
    print("   ✅ Randomisation OK — les lots sont différents")


def test_examples_length():
    """Chaque exemple respecte les limites de longueur."""
    from app.services.style_loader import get_style_examples, MIN_LEN, MAX_LEN

    examples = get_style_examples(50)
    for ex in examples:
        assert MIN_LEN <= len(ex) <= MAX_LEN, (
            f"Longueur hors limites ({len(ex)}) : {ex!r}"
        )
    print(f"   ✅ Toutes les longueurs entre {MIN_LEN} et {MAX_LEN} chars")


def test_injection_preview():
    """Affiche les exemples tels qu'ils apparaîtront dans le system prompt."""
    from app.services.style_loader import get_style_examples

    examples = get_style_examples(12)
    block = (
        "\nexemples réels de ton style d'écriture — imite-les naturellement :\n"
        + "\n".join(f'- "{ex}"' for ex in examples)
        + "\n"
    )
    print(f"\n📝 Aperçu du bloc few-shot injecté dans le system prompt :\n{block}")


if __name__ == "__main__":
    print("=" * 55)
    print("🔬 TEST STYLE LOADER")
    print("=" * 55)

    test_dataset_loads()
    test_no_sensitive_data()
    test_randomness()
    test_examples_length()
    test_injection_preview()

    print("\n" + "=" * 55)
    print("✅ Tous les tests style loader sont OK !")
    print("=" * 55)
