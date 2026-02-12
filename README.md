# 💇‍♀️ Kyana — Assistant IA Incognito pour Coiffeuse

Kyana est un backend **FastAPI** qui gère automatiquement les messages privés Instagram d'une coiffeuse indépendante, en utilisant **Google Gemini 1.5 Flash** pour générer des réponses naturelles — comme si c'était la coiffeuse elle-même qui tapait.

---

## ✨ Fonctionnalités

- **Réponses IA naturelles** — ton Instagram, tutoiement, emojis discrets, phrases courtes
- **Logique de doute** — si l'IA n'est pas sûre, la conversation bascule en mode *manuel* et une alerte est émise
- **Délai humain** — simule un temps de réponse réaliste (30–120 secondes)
- **Mode auto / manuel** — chaque conversation peut être gérée par l'IA ou reprise à la main
- **Dashboard API** — endpoints REST prêts pour un futur frontend Next.js
- **Historique complet** — tous les messages sont stockés en base (SQLite)

---

## 📁 Structure du projet

```
kyana/
├── app/
│   ├── __init__.py
│   ├── main.py                ← Point d'entrée FastAPI
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py          ← Configuration (.env)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py        ← Connexion SQLite / SQLAlchemy
│   │   ├── conversation.py    ← Modèles ORM (tables)
│   │   └── schemas.py         ← Schémas Pydantic (API)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini_service.py  ← Logique IA (Gemini)
│   │   └── instagram_service.py ← Envoi de messages + webhook
│   └── api/
│       ├── __init__.py
│       ├── webhook.py         ← Endpoints webhook Instagram
│       └── dashboard.py       ← Endpoints dashboard
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## 📄 Détail de chaque fichier

### `app/main.py` — Point d'entrée

Le cœur de l'application. Ce fichier :
- Crée l'app FastAPI avec métadonnées (titre, description, version)
- Configure le **CORS** pour autoriser `localhost:3000` (futur frontend Next.js)
- Branche les routers (webhook + dashboard)
- Crée les tables en base au démarrage (`lifespan`)
- Expose un endpoint `/health` pour vérifier que le serveur tourne

### `app/core/config.py` — Configuration

Charge les variables d'environnement depuis le fichier `.env` grâce à **Pydantic Settings**. Variables disponibles :

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Clé API Google Gemini |
| `INSTA_VERIFY_TOKEN` | Token de vérification webhook (tu le choisis toi-même) |
| `INSTA_ACCESS_TOKEN` | Token d'accès Instagram Graph API |
| `FB_PAGE_ID` | ID de ta page Facebook liée à Instagram |
| `DATABASE_URL` | URL de la base (par défaut : `sqlite:///./kyana.db`) |

La fonction `get_settings()` est un **singleton** — le fichier `.env` n'est lu qu'une seule fois.

### `app/models/database.py` — Base de données

Configure **SQLAlchemy** avec SQLite :
- `engine` — le moteur de connexion
- `SessionLocal` — la factory de sessions
- `Base` — la classe de base pour tous les modèles ORM
- `get_db()` — une dépendance FastAPI qui fournit une session DB et la ferme après usage

### `app/models/conversation.py` — Modèles ORM (tables)

Définit les deux tables de la base :

**`conversation_states`** — une ligne par client Instagram :
| Colonne | Rôle |
|---------|------|
| `sender_id` | L'identifiant Instagram du client (unique) |
| `mode` | `auto` (IA répond) ou `manual` (tu réponds toi-même) |
| `last_message_at` | Date du dernier message |

**`message_logs`** — l'historique complet des échanges :
| Colonne | Rôle |
|---------|------|
| `conversation_id` | Lien vers la conversation |
| `direction` | `inbound` (client → toi) ou `outbound` (toi → client) |
| `content` | Le texte du message |
| `needs_human` | `true` si l'IA a flaggé ce message comme douteux |

### `app/models/schemas.py` — Schémas Pydantic

Les "formes" des données échangées via l'API :
- `GeminiResponse` — la réponse structurée de Gemini (`response` + `needs_human`)
- `ConversationOut` / `MessageOut` — ce que les endpoints renvoient au frontend
- `ConversationModeUpdate` — le payload pour basculer auto ↔ manuel
- `DashboardStats` — les stats globales (nombre de conversations, messages, alertes)

### `app/services/gemini_service.py` — Service IA

Le cerveau de Kyana. Ce fichier :
- Configure le client **Google Gemini 1.5 Flash**
- Contient le **system prompt** qui force le ton "coiffeuse Instagram" (tutoiement, emojis, brièveté)
- Envoie les messages au modèle avec l'historique de conversation pour le contexte
- Retourne un JSON structuré `{ "response": "...", "needs_human": true/false }`
- Si Gemini renvoie un format inattendu ou une erreur → `needs_human = true` automatiquement

### `app/services/instagram_service.py` — Service Instagram

Gère la communication avec l'API Meta / Instagram :
- `send_message()` — envoie un message via la Graph API (POST)
- `verify_webhook()` — valide le challenge de vérification Meta
- `simulate_human_delay()` — attend 30 à 120 secondes (aléatoire) avant de répondre, pour que ça fasse naturel

### `app/api/webhook.py` — Endpoints Webhook

Les deux endpoints requis par Meta :

**`GET /webhook`** — Vérification initiale. Meta envoie un token et un challenge, le serveur vérifie le token et renvoie le challenge.

**`POST /webhook`** — Réception des messages. Pour chaque message entrant :
1. Récupère ou crée la conversation du client
2. Si le mode est `manual` → log le message, ne fait rien d'autre
3. Appelle Gemini avec le message + historique récent
4. Si `needs_human` → passe en manuel + alerte dans les logs 🚨
5. Sinon → attend un délai aléatoire, puis envoie la réponse

### `app/api/dashboard.py` — Endpoints Dashboard

Les endpoints pour le futur frontend Next.js :

| Méthode | URL | Rôle |
|---------|-----|------|
| `GET` | `/api/stats` | Stats globales (conversations, messages, alertes) |
| `GET` | `/api/conversations` | Liste des conversations avec aperçu du dernier message |
| `GET` | `/api/conversations/{id}/messages` | Historique d'une conversation |
| `PATCH` | `/api/conversations/{id}/mode` | Basculer auto ↔ manuel |

---

## 🚀 Installation

### 1. Cloner le repo

```bash
git clone https://github.com/boriiiiii/kyana.git
cd kyana
```

### 2. Créer l'environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement

```bash
cp .env.example .env
```

Puis ouvre `.env` et remplis tes clés :

```env
GEMINI_API_KEY=ta_cle_gemini
INSTA_VERIFY_TOKEN=un_token_que_tu_inventes
INSTA_ACCESS_TOKEN=ton_token_instagram
FB_PAGE_ID=ton_id_page_facebook
```

### 5. Lancer le serveur

```bash
uvicorn app.main:app --reload
```

Le serveur démarre sur `http://localhost:8000`. La base SQLite (`kyana.db`) est créée automatiquement au premier lancement.

---

## 🧪 Tester

### Vérifier que le serveur tourne

```bash
curl http://localhost:8000/health
# → {"status":"ok","app":"Kyana"}
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

### Documentation interactive

FastAPI génère automatiquement une doc interactive :
- **Swagger UI** : [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc** : [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔗 Configurer le Webhook Meta

1. Va sur [Meta for Developers](https://developers.facebook.com/)
2. Crée une app → ajoute le produit **Messenger** ou **Instagram**
3. Dans la config webhook, entre :
   - **URL** : `https://ton-domaine.com/webhook` (il faut un domaine HTTPS public — utilise [ngrok](https://ngrok.com/) pour le dev)
   - **Token de vérification** : la valeur que tu as mise dans `INSTA_VERIFY_TOKEN`
4. Abonne-toi aux événements `messages`

---

## 🧠 Comment fonctionne la logique de doute

Quand un message arrive, Gemini répond avec un JSON :

```json
{
  "response": "salut ! je regarde mon planning et je te dis ça 😊",
  "needs_human": false
}
```

Si `needs_human` est `true` (question hors sujet, demande de RDV précis, réclamation…) :
- La conversation passe en mode **manuel**
- Un log d'alerte est émis : `🚨 ALERTE — IA pas sûre pour [sender_id]`
- Aucune réponse automatique n'est envoyée
- Tu peux répondre toi-même et remettre en auto via `PATCH /api/conversations/{id}/mode`

---

## 📌 Prochaines étapes

- [ ] Brancher un frontend Next.js sur les endpoints `/api/*`
- [ ] Remplacer le `asyncio.sleep` par une vraie file d'attente (Celery / ARQ)
- [ ] Ajouter l'authentification sur les endpoints dashboard
- [ ] Déployer (Railway, Render, VPS…)

---

## License

MIT
