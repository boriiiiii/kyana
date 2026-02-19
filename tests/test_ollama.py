"""
Test Ollama API — diagnostic complet.

Vérifie qu'Ollama tourne, que le modèle est dispo,
et teste un appel réel avec le format JSON attendu.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()


def test_ollama_running():
    """Vérifie qu'Ollama est accessible."""
    import httpx

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    print(f"🔌 Test connexion Ollama ({base_url}) ...")
    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=5)
        assert resp.status_code == 200
        models = resp.json().get("models", [])
        print(f"   ✅ Ollama en ligne — {len(models)} modèle(s) disponible(s)")
        for m in models:
            print(f"      • {m['name']}")
        return True
    except httpx.ConnectError:
        print(f"   ❌ Ollama non accessible ! Lance : ollama serve")
        return False
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        return False


def test_model_available():
    """Vérifie que le modèle configuré est téléchargé."""
    import ollama

    model = os.getenv("OLLAMA_MODEL", "llama3.1")
    print(f"\n📦 Vérification modèle '{model}' ...")
    try:
        client = ollama.Client(host=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
        info = client.show(model)
        print(f"   ✅ Modèle trouvé : {model}")
        if "modelfile" in info:
            print(f"   📋 Family: {info.get('details', {}).get('family', 'N/A')}")
            print(f"   📋 Parameters: {info.get('details', {}).get('parameter_size', 'N/A')}")
        return True
    except Exception as e:
        print(f"   ❌ Modèle non trouvé : {e}")
        print(f"   💡 Télécharge-le : ollama pull {model}")
        return False


def test_generate_json():
    """Teste un appel chat avec sortie JSON structurée."""
    import ollama

    model = os.getenv("OLLAMA_MODEL", "llama3.1")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    print(f"\n🧪 Test appel chat avec {model} (format JSON) ...")
    try:
        client = ollama.Client(host=base_url)
        result = client.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es une coiffeuse. Réponds UNIQUEMENT en JSON : "
                        '{"reply": "ta réponse", "needs_human": false}. '
                        "Pas de texte en dehors du JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": "salut tu fais des balayages ?",
                },
            ],
            format="json",
            options={"temperature": 0.7, "num_predict": 256},
        )

        raw = result.message.content.strip()
        print(f"   📝 Réponse brute : {raw}")

        import json
        parsed = json.loads(raw)
        reply = parsed.get("reply", parsed.get("response", ""))
        needs_human = parsed.get("needs_human", False)

        print(f"   ✅ JSON valide !")
        print(f"   💬 Reply: {reply}")
        print(f"   🚨 Needs human: {needs_human}")
        return True

    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        return False


def test_response_time():
    """Mesure le temps de réponse."""
    import ollama
    import time

    model = os.getenv("OLLAMA_MODEL", "llama3.1")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    print(f"\n⏱️  Test temps de réponse ...")
    try:
        client = ollama.Client(host=base_url)
        start = time.time()
        client.chat(
            model=model,
            messages=[{"role": "user", "content": "dis ok"}],
            format="json",
            options={"num_predict": 50},
        )
        elapsed = time.time() - start
        print(f"   ✅ Temps de réponse : {elapsed:.1f}s")
        if elapsed > 10:
            print(f"   ⚠️  C'est un peu lent — normal pour la 1ère requête (chargement modèle)")
        return True
    except Exception as e:
        print(f"   ❌ Erreur : {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("🔬 DIAGNOSTIC OLLAMA / LLAMA 3.1")
    print("=" * 50)

    if not test_ollama_running():
        print("\n⛔ Ollama non accessible. Lance 'ollama serve' et réessaie.")
        sys.exit(1)

    if not test_model_available():
        sys.exit(1)

    success = test_generate_json()
    test_response_time()

    print("\n" + "=" * 50)
    if success:
        print("✅ TOUT EST OK — Ollama + Llama 3.1 fonctionnent !")
    else:
        print("❌ PROBLÈME DÉTECTÉ — voir les détails ci-dessus")
    print("=" * 50)
