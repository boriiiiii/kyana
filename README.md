# 💇‍♀️ Kyana — Assistant IA Incognito pour Coiffeuse

Kyana est un backend **FastAPI** qui gère automatiquement les messages privés Instagram d'une coiffeuse indépendante, en utilisant **Ollama (Llama 3.1)** en local pour générer des réponses naturelles — comme si c'était la coiffeuse elle-même qui tapait.

---

## ✨ Fonctionnalités

- **IA locale** — utilise Ollama + Llama 3.1, aucun appel cloud, 100 % privé
- **Réponses naturelles** — ton Instagram, tutoiement, emojis discrets, phrases courtes
- **Logique de doute** — si l'IA n'est pas sûre, la conversation bascule en mode *manuel* et une alerte est émise
- **Délai humain** — simule un temps de réponse réaliste (30–120 secondes)
- **Mode auto / manuel** — chaque conversation peut être gérée par l'IA ou reprise à la main
- **Dashboard API** — endpoints REST prêts pour un futur frontend Next.js
- **Historique complet** — tous les messages sont stockés en base (SQLite)
- **Privacy policy** — page `/privacy` intégrée, requise par Meta

---

## 📁 Structure du projet

```
kyana/
├── app/
│   ├── __init__.py
│   ├── main.py                 ← Point d'entrée FastAPI
│   ├── core/
│   │   └── config.py           ← Configuration (.env / Pydantic Settings)
│   ├── models/
│   │   ├── database.py         ← Connexion SQLite / SQLAlchemy
│   │   ├── conversation.py     ← Modèles ORM (tables)
│   │   └── schemas.py          ← Schémas Pydantic (API)
│   ├── services/
│   │   ├── ollama_service.py   ← 🧠 Logique IA (Ollama / Llama 3.1)
│   │   ├── instagram_service.py ← Envoi de messages + webhook
│   │   └── gemini_service.py   ← (legacy — non utilisé)
│   └── api/
│       ├── webhook.py          ← Endpoints webhook Instagram
│       └── dashboard.py        ← Endpoints dashboard
├── tests/
│   ├── test_all.py
│   ├── test_ollama.py
│   └── test_webhook.py
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## 🚀 Lancer le projet

### Prérequis

- **Python 3.11+**
- **Ollama** installé et lancé sur ta machine → [ollama.com](https://ollama.com/)

### 1. Cloner le repo

```bash
git clone https://github.com/boriiiiii/kyana.git
cd kyana
```

### 2. Installer Ollama et le modèle

```bash
# Installer Ollama (macOS)
brew install ollama

# Lancer le serveur Ollama (dans un terminal séparé)
ollama serve

# Télécharger le modèle Llama 3.1
ollama pull llama3.1
```

> **Note :** Ollama doit tourner en arrière-plan (`ollama serve`) avant de lancer Kyana. Par défaut il écoute sur `http://localhost:11434`.

### 3. Créer l'environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Installer les dépendances Python

```bash
pip install -r requirements.txt
```

### 5. Configurer les variables d'environnement

```bash
cp .env.example .env
```

Puis ouvre `.env` et remplis tes valeurs :

```env
# Ollama (optionnel si tu gardes les valeurs par défaut)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1

# Instagram / Meta (requis pour la prod)
INSTA_VERIFY_TOKEN=un_token_que_tu_inventes
INSTA_ACCESS_TOKEN=ton_token_instagram
INSTA_ACCOUNT_ID=ton_id_compte_instagram
```

### 6. Lancer le serveur

```bash
make dev
```

> Équivalent à `uvicorn app.main:app --reload`

Le serveur démarre sur **`http://localhost:8000`**. La base SQLite (`kyana.db`) est créée automatiquement au premier lancement.

### Commandes disponibles

| Commande | Description |
|----------|-------------|
| `make dev` | Lancer le serveur avec hot-reload |
| `make run` | Lancer le serveur (production) |
| `make test` | Lancer les tests |
| `make install` | Installer les dépendances |
| `make setup` | Setup complet (venv + deps + .env) |

---

## 🧪 Tester

### Vérifier que le serveur tourne

```bash
curl http://localhost:8000/health
# → {"status":"ok","app":"Kyana"}
```

### Vérifier qu'Ollama est connecté

```bash
curl http://localhost:11434/api/tags
# → liste des modèles disponibles (llama3.1 doit y être)
```

### Tester le webhook

```bash
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.verify_token=TON_TOKEN&hub.challenge=TEST123"
# → TEST123
```

### Voir les conversations (vide au début)

```bash
curl http://localhost:8000/api/conversations
# → []
```

### Voir les stats

```bash
curl http://localhost:8000/api/stats
# → {"total_conversations":0,"auto_conversations":0,...}
```

### Lancer les tests

```bash
pytest tests/ -v
```

### Documentation interactive

FastAPI génère automatiquement une doc interactive :
- **Swagger UI** : [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc** : [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## ⚙️ Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `OLLAMA_BASE_URL` | URL du serveur Ollama | `http://localhost:11434` |
| `OLLAMA_MODEL` | Modèle LLM à utiliser | `llama3.1` |
| `INSTA_VERIFY_TOKEN` | Token de vérification webhook (tu le choisis) | — |
| `INSTA_ACCESS_TOKEN` | Token d'accès Instagram Graph API | — |
| `INSTA_ACCOUNT_ID` | ID du compte Instagram professionnel | — |
| `DATABASE_URL` | URL de la base de données | `sqlite:///./kyana.db` |
| `DEBUG` | Mode debug | `false` |

---

## 🔗 Configurer le Webhook Meta

1. Va sur [Meta for Developers](https://developers.facebook.com/)
2. Crée une app → ajoute le produit **Instagram**
3. Dans la config webhook, entre :
   - **URL** : `https://ton-domaine.com/webhook` (il faut un domaine HTTPS public — utilise [ngrok](https://ngrok.com/) pour le dev)
   - **Token de vérification** : la valeur que tu as mise dans `INSTA_VERIFY_TOKEN`
4. Abonne-toi aux événements `messages`

---

## 📡 Endpoints API

### Webhook (Meta/Instagram)

| Méthode | URL | Rôle |
|---------|-----|------|
| `GET` | `/webhook` | Vérification initiale Meta (challenge-response) |
| `POST` | `/webhook` | Réception des messages Instagram entrants |

### Dashboard

| Méthode | URL | Rôle |
|---------|-----|------|
| `GET` | `/api/stats` | Stats globales (conversations, messages, alertes) |
| `GET` | `/api/conversations` | Liste des conversations avec aperçu du dernier message |
| `GET` | `/api/conversations/{id}/messages` | Historique d'une conversation |
| `PATCH` | `/api/conversations/{id}/mode` | Basculer auto ↔ manuel |

### Système

| Méthode | URL | Rôle |
|---------|-----|------|
| `GET` | `/health` | Health check |
| `GET` | `/privacy` | Page de politique de confidentialité (requise par Meta) |

---

## 🧠 Comment fonctionne la logique de doute

Quand un message arrive, l'IA (Llama 3.1 via Ollama) répond avec un JSON :

```json
{
  "reply": "salut ! je regarde mon planning et je te dis ça 😊",
  "needs_human": false
}
```

Si `needs_human` est `true` (question hors sujet, demande de RDV précis, réclamation…) :
- La conversation passe en mode **manuel**
- Un log d'alerte est émis : `🚨 ALERTE — IA pas sûre pour [sender_id]`
- Aucune réponse automatique n'est envoyée
- Tu peux répondre toi-même et remettre en auto via `PATCH /api/conversations/{id}/mode`

---

## 📦 Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | FastAPI (Python 3.11+) |
| LLM | Ollama + Llama 3.1 (local) |
| Base de données | SQLite + SQLAlchemy 2.0 |
| HTTP client | httpx (async) |
| Validation | Pydantic v2 |
| Messaging | Instagram Graph API v25.0 |

---

## 📌 Prochaines étapes

- [ ] Brancher un frontend Next.js sur les endpoints `/api/*`
- [ ] Remplacer le `asyncio.sleep` par une vraie file d'attente (Celery / ARQ)
- [ ] Ajouter l'authentification sur les endpoints dashboard
- [ ] Supprimer le legacy `gemini_service.py`
- [ ] Déployer (Railway, Render, VPS…)

---

## License

MIT
