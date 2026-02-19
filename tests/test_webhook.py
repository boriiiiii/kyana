"""
Test webhook endpoints — simule les appels Meta vers ton serveur.
"""

import sys
import os
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

BASE_URL = "http://localhost:8000"


def test_health():
    """Vérifie que le serveur est en ligne."""
    print("🏥 Test /health ...")
    try:
        resp = httpx.get(f"{BASE_URL}/health", timeout=5)
        data = resp.json()
        assert resp.status_code == 200
        assert data["status"] == "ok"
        print(f"   ✅ Serveur en ligne : {data}")
        return True
    except httpx.ConnectError:
        print("   ❌ Serveur non accessible ! Lance : uvicorn app.main:app --reload --port 8000")
        return False


def test_webhook_verify():
    """Simule la vérification webhook de Meta."""
    print("\n🔐 Test GET /webhook (vérification Meta) ...")
    token = os.getenv("INSTA_VERIFY_TOKEN", "")
    resp = httpx.get(f"{BASE_URL}/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": token,
        "hub.challenge": "test_challenge_999",
    }, timeout=5)

    if resp.status_code == 200 and resp.text == "test_challenge_999":
        print(f"   ✅ Vérification OK — challenge retourné correctement")
        return True
    else:
        print(f"   ❌ Échec (status={resp.status_code}, body={resp.text})")
        return False


def test_webhook_verify_bad_token():
    """Vérifie qu'un mauvais token est rejeté."""
    print("\n🚫 Test GET /webhook (mauvais token) ...")
    resp = httpx.get(f"{BASE_URL}/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_token",
        "hub.challenge": "should_not_work",
    }, timeout=5)

    if resp.status_code == 403:
        print(f"   ✅ Mauvais token correctement rejeté (403)")
        return True
    else:
        print(f"   ❌ Devrait retourner 403, a retourné {resp.status_code}")
        return False


def test_webhook_post_message():
    """Simule un message Instagram entrant."""
    print("\n💬 Test POST /webhook (message entrant) ...")
    payload = {
        "entry": [{
            "id": "test_entry",
            "time": 1708700000,
            "messaging": [{
                "sender": {"id": "test_sender_42"},
                "recipient": {"id": "test_recipient"},
                "message": {
                    "mid": "test_mid_001",
                    "text": "Salut ! Est-ce que tu fais des balayages ?"
                }
            }]
        }]
    }

    resp = httpx.post(f"{BASE_URL}/webhook", json=payload, timeout=30)
    data = resp.json()

    if resp.status_code == 200 and data.get("status") == "ok":
        print(f"   ✅ Message traité — réponse : {data}")
        return True
    else:
        print(f"   ❌ Échec (status={resp.status_code}, body={resp.text})")
        return False


def test_webhook_post_no_text():
    """Vérifie qu'un message sans texte est ignoré."""
    print("\n🖼️  Test POST /webhook (message image, sans texte) ...")
    payload = {
        "entry": [{
            "id": "test_entry",
            "time": 1708700000,
            "messaging": [{
                "sender": {"id": "test_sender_img"},
                "recipient": {"id": "test_recipient"},
                "message": {
                    "mid": "test_mid_img",
                    "attachments": [{"type": "image", "payload": {"url": "http://example.com/img.jpg"}}]
                }
            }]
        }]
    }

    resp = httpx.post(f"{BASE_URL}/webhook", json=payload, timeout=10)
    if resp.status_code == 200:
        print(f"   ✅ Message sans texte correctement ignoré")
        return True
    else:
        print(f"   ❌ Erreur inattendue : {resp.status_code}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("🧪 TESTS WEBHOOK")
    print("=" * 50)

    results = []

    if not test_health():
        print("\n⛔ Serveur non accessible, impossible de continuer.")
        sys.exit(1)

    results.append(test_webhook_verify())
    results.append(test_webhook_verify_bad_token())
    results.append(test_webhook_post_message())
    results.append(test_webhook_post_no_text())

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    if passed == total:
        print(f"✅ {passed}/{total} TESTS PASSÉS")
    else:
        print(f"⚠️  {passed}/{total} TESTS PASSÉS — {total - passed} ÉCHOUÉ(S)")
    print("=" * 50)
