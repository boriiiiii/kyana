# CLAUDE.md — Contexte projet Kyana

## Présentation

Kyana est un assistant IA "incognito" pour une coiffeuse indépendante spécialisée en **cheveux afro, locks et texturés** (nom de la coiffeuse : **Hina**). L'application gère automatiquement les DMs Instagram de la coiffeuse : elle reçoit les messages des clientes via webhook Meta, génère des réponses naturelles via un LLM local (Ollama), et les renvoie comme si c'était Hina elle-même qui écrivait. Un dashboard Next.js permet de superviser les conversations.

---

## Architecture globale

```
┌──────────────┐      webhook      ┌──────────────────┐      API       ┌─────────────┐
│  Instagram   │ ──── POST ──────▶ │  FastAPI Backend  │ ◀──── REST ──▶ │  Next.js     │
│  (Meta API)  │ ◀── send_message  │  (Python 3.11+)   │               │  Dashboard   │
└──────────────┘                   └────────┬─────────┘               └─────────────┘
                                            │
                                   ┌────────┼─────────┐
                                   │        │         │
                              ┌────▼───┐ ┌──▼──┐ ┌───▼────┐
                              │ Ollama │ │ DB  │ │ iCloud │
                              │ Llama  │ │SQLite│ │ CalDAV │
                              └────────┘ └─────┘ └────────┘
```

- **Backend** : FastAPI (Python) → `app/`
- **Frontend** : Next.js 15 + React 19 + TailwindCSS → `frontend/`  
- **LLM** : Ollama + Llama 3.1 (ou modèle fine-tuné "hina") en local
- **BDD** : SQLite via SQLAlchemy 2.0 (`kyana.db`)
- **Calendrier** : iCloud CalDAV (avec mock pour le dev)
- **Messaging** : Instagram Graph API v25.0

---

## Structure des fichiers

```
kyana/
├── app/                          # Backend FastAPI
│   ├── main.py                   # Point d'entrée, lifespan, CORS, routes système (/health, /privacy)
│   ├── core/
│   │   └── config.py             # Pydantic Settings (charge .env)
│   ├── models/
│   │   ├── database.py           # Engine SQLAlchemy, SessionLocal, Base, get_db()
│   │   ├── conversation.py       # ORM : ConversationState, MessageLog (modes auto/manual)
│   │   └── schemas.py            # Pydantic : AIResponse, BookingRequest, ConversationOut, etc.
│   ├── services/
│   │   ├── ollama_service.py     # 🧠 Cœur IA — system prompt, validation prix, appel Ollama
│   │   ├── instagram_service.py  # Envoi de messages Instagram + vérification webhook + délai humain
│   │   ├── calendar_service.py   # iCloud CalDAV : lecture, création, suppression + MockCalendar
│   │   ├── knowledge_service.py  # Charge knowledge_base.json → bloc texte pour le prompt
│   │   ├── qa_loader.py          # Charge qa_pairs.json → exemples Q&R réels pour le prompt
│   │   ├── style_loader.py       # Charge dataset_style_coiffeuse.json → exemples de ton
│   │   └── gemini_service.py     # ⚠️ LEGACY — NE PAS UTILISER (ancienne implémentation avec Google Gemini)
│   └── api/
│       ├── webhook.py            # POST/GET /webhook — debounce, accumulation messages, orchestration IA
│       └── dashboard.py          # CRUD /api/stats, /api/conversations, mode toggle
├── frontend/                     # Dashboard Next.js
│   ├── app/
│   │   ├── layout.tsx            # Layout root
│   │   ├── page.tsx              # Page principale (split layout conversations)
│   │   └── globals.css           # CSS global
│   ├── components/
│   │   ├── StatsBar.tsx          # Barre de stats (total convos, auto, manual, messages)
│   │   ├── ConversationList.tsx  # Liste de conversations (sidebar gauche)
│   │   ├── ConversationItem.tsx  # Item conversation unitaire
│   │   ├── ConversationDetail.tsx # Détail d'une conversation (panel droit)
│   │   ├── MessageBubble.tsx     # Bulle de message (inbound/outbound)
│   │   └── ModeToggle.tsx        # Toggle auto/manuel
│   ├── lib/
│   │   ├── api.ts                # Client fetch vers le backend (proxy via Next.js rewrites)
│   │   └── types.ts              # Types TypeScript (Stats, Conversation, Message)
│   └── next.config.ts            # Rewrites /api/* → http://localhost:8000/api/*
├── data/                         # Données d'entraînement et bases de connaissance
│   ├── knowledge_base.json       # 📚 Source de vérité : tarifs, règles métier, infos pratiques
│   ├── dataset_style_coiffeuse.json  # Exemples de messages Instagram de la coiffeuse (style)
│   ├── dataset.json              # Paires instruction/response extraites des DMs
│   ├── finetune/
│   │   ├── train.jsonl           # Données d'entraînement fine-tuning (format JSONL)
│   │   └── valid.jsonl           # Données de validation fine-tuning
│   ├── inbox/                    # Export brut des conversations Instagram (source)
│   └── script.py                 # Script d'extraction des paires Q&R depuis inbox/
├── models/                       # Modèles LLM locaux
│   ├── hina.gguf                 # Modèle fine-tuné au format GGUF (~1.9GB, Llama 3.2 3B)
│   └── hina-adapter/             # Adaptateurs LoRA (checkpoints de fine-tuning)
├── tests/                        # Tests
│   ├── test_all.py               # Runner de tests
│   ├── test_ollama.py            # Tests diagnostics Ollama
│   ├── test_webhook.py           # Tests du webhook
│   ├── test_calendar.py          # Tests calendrier iCloud
│   ├── test_style_loader.py      # Tests du chargement de style
│   └── seed_icloud_test.py       # Script pour peupler le calendrier de test
├── Makefile                      # Commandes : dev, run, front, start, test, tunnel, setup
├── Modelfile                     # Configuration Ollama du modèle fine-tuné "hina"
├── requirements.txt              # Dépendances Python
├── .env.example                  # Template des variables d'environnement
└── todo.txt                      # Notes de développement (non committé)
```

---

## Stack technique

| Composant | Technologie | Version |
|-----------|------------|---------|
| Backend | FastAPI | ≥0.104 |
| Runtime | Python | 3.11+ |
| LLM | Ollama + Llama 3.1 | local |
| Fine-tuning | LoRA sur Llama 3.2 3B (MLX) | — |
| BDD | SQLite + SQLAlchemy | 2.0+ |
| Validation | Pydantic | v2 |
| HTTP client | httpx | async |
| Calendrier | CalDAV (caldav lib) | ≥1.3.9 |
| Frontend | Next.js | 15.2.3 |
| React | React | 19 |
| Styling | TailwindCSS | 3.4 |
| Data fetching | SWR | 2.3 |
| Package manager (front) | Bun | — |

---

## Concepts clés

### 1. Debounce des messages

Le webhook ne répond pas immédiatement. Quand un message arrive :
1. Le message est logué en BDD
2. Il est ajouté dans une queue en mémoire (`_message_queues[sender_id]`)
3. Un timer asyncio est (re)démarré (`response_debounce_seconds`, défaut 10s)
4. Si d'autres messages arrivent pendant le timer → accumulation, le timer repart
5. À expiration → tous les messages sont concaténés et envoyés à l'IA en une seule requête

Fichier : `app/api/webhook.py`, fonctions `_handle_messaging_event` et `_debounced_respond`.

### 2. Logique auto/manuel

Chaque conversation a un `mode` : `auto` (IA répond) ou `manual` (humaine reprend).  
L'IA bascule une conversation en `manual` quand :
- `needs_human = true` dans la réponse JSON de l'IA
- Un prix hallucinou est détecté par `_validate_prices_in_reply()`

La coiffeuse peut remettre une conversation en `auto` via `PATCH /api/conversations/{id}/mode`.

### 3. System prompt et anti-hallucination

Le prompt est construit dynamiquement dans `ollama_service.py` → `generate_response()` avec 4 blocs injectés :

1. **SYSTEM_PROMPT** (statique) — règles de ton, grille tarifaire, règles anti-hallucination, processus de RDV, format JSON attendu
2. **Knowledge base** (`knowledge_service.py`) — inject depuis `data/knowledge_base.json`
3. **Exemples Q&R** (`qa_loader.py`) — inject depuis `data/qa_pairs.json` (exemples réels catégorisés)
4. **Exemples de style** (`style_loader.py`) — inject depuis `data/dataset_style_coiffeuse.json`
5. **Contexte calendrier** (`calendar_service.py`) — créneaux libres d'aujourd'hui et demain

L'IA doit répondre en **JSON strict** :
```json
{"reply": "...", "needs_human": false, "book": null}
```

Le champ `book` (optionnel) déclenche la création d'un événement iCloud CalDAV.

### 4. Validation post-génération des prix

`_validate_prices_in_reply()` dans `ollama_service.py` vérifie que les montants en € mentionnés dans la réponse IA correspondent à la grille tarifaire (`_FIXED_PRICES` et `_VARIABLE_RANGES`). Si un prix suspect est détecté → `needs_human=true`, aucun message n'est envoyé.

### 5. Booking automatique (iCloud CalDAV)

Quand l'IA retourne un objet `book` (schéma `BookingRequest`) :
- Le webhook crée un événement dans le calendrier iCloud via `ICloudCalendar.create_event()`
- Le titre contient : nom de la prestation + prénom cliente + @instagram
- La variable `CALENDAR_USE_MOCK` n'est plus utilisée directement ; le code utilise `ICloudCalendar` en production

### 6. Fine-tuning (expérimental)

Un modèle fine-tuné "hina" basé sur Llama 3.2 3B a été entraîné avec MLX (Apple Silicon) :
- Données : `data/finetune/train.jsonl` + `valid.jsonl` (extraites des vrais DMs Instagram)  
- Adaptateurs LoRA : `models/hina-adapter/`
- Modèle fusionné : `models/hina.gguf`
- Config Ollama : `Modelfile` (pour utiliser le modèle avec `ollama create hina -f Modelfile`)

Le système principal utilise encore le modèle vanilla `llama3.1` via le paramètre `OLLAMA_MODEL`.

---

## Variables d'environnement

Fichier `.env` (voir `.env.example`) :

| Variable | Description | Défaut |
|----------|-------------|--------|
| `OLLAMA_BASE_URL` | URL du serveur Ollama | `http://localhost:11434` |
| `OLLAMA_MODEL` | Modèle LLM | `llama3.1` |
| `INSTA_VERIFY_TOKEN` | Token de vérification webhook Meta | — |
| `INSTA_ACCESS_TOKEN` | Token d'accès Instagram Graph API | — |
| `INSTA_ACCOUNT_ID` | ID du compte Instagram professionnel | — |
| `DATABASE_URL` | URL de la BDD | `sqlite:///./kyana.db` |
| `CALDAV_URL` | Serveur CalDAV Apple | `https://caldav.icloud.com` |
| `CALDAV_EMAIL` | Email iCloud | — |
| `CALDAV_APP_PASSWORD` | Mot de passe d'application Apple (pas l'MDP iCloud !) | — |
| `CALDAV_CALENDAR_NAME` | Nom du calendrier (optionnel) | — |
| `CALENDAR_USE_MOCK` | Utiliser le mock calendrier (dev) | `true` |
| `RESPONSE_DEBOUNCE_SECONDS` | Délai d'attente avant réponse IA | `10` |
| `DEBUG` | Mode debug | `false` |

---

## Commandes de développement

```bash
# Backend
make dev          # uvicorn app.main:app --reload (port 8000)
make run          # uvicorn sans reload
make test         # pytest tests/ -v

# Frontend
make front        # cd frontend && npm run dev (port 3000)

# Les deux ensemble
make start        # backend + frontend en parallèle

# Tunnel pour les webhooks Meta
make tunnel       # ngrok http 8000 (alias: make ngrok)

# Setup initial
make setup        # venv + deps + copie .env
```

---

## Endpoints API

### Webhook (Meta/Instagram)
| Méthode | URL | Rôle |
|---------|-----|------|
| `GET` | `/webhook` | Vérification challenge Meta |
| `POST` | `/webhook` | Réception des messages Instagram |

### Dashboard
| Méthode | URL | Rôle |
|---------|-----|------|
| `GET` | `/api/stats` | Stats globales |
| `GET` | `/api/conversations` | Liste des conversations |
| `GET` | `/api/conversations/{id}/messages` | Historique d'une conversation |
| `PATCH` | `/api/conversations/{id}/mode` | Toggle auto ↔ manuel |

### Système
| Méthode | URL | Rôle |
|---------|-----|------|
| `GET` | `/health` | Health check |
| `GET` | `/privacy` | Page privacy (requise par Meta) |

---

## Conventions de code

### Backend (Python)
- **Typage statique** partout (annotations de types, `Mapped[]` pour SQLAlchemy)
- **Async** : les endpoints et services Instagram/IA sont async
- **Logging** structuré avec emojis : `logger.info("✅ ...")`, `logger.warning("🚨 ...")`
- **Sections séparées** dans chaque fichier avec des commentaires `# ─── Titre ───`
- **Docstrings** en anglais (format Google/NumPy), commentaires inline en français
- **Imports** groupés : stdlib → third-party → app
- **Configuration** centralisée via `get_settings()` (Pydantic Settings, singleton avec `@lru_cache`)
- Le pattern `get_db()` est utilisé comme dépendance FastAPI pour les sessions DB
- Les **clés JSON** de l'IA utilisent `reply` (pas `response`) — le code gère les deux via `parsed.get("reply", parsed.get("response", ...))`

### Frontend (TypeScript/React)
- **Next.js App Router** (dossier `app/`)
- **Client components** (`"use client"`) — pas de SSR pour le dashboard
- **SWR** pour le data fetching avec polling automatique
- **TailwindCSS** pour le styling (dark theme, palette basée sur `#0d0d0d`/`#141414`)
- **Proxy API** : les requêtes `/api/*` du frontend sont redirigées vers le backend via `next.config.ts` rewrites
- Package manager : **Bun** (fichier `bun.lockb`)

### Données
- `knowledge_base.json` est la **source de vérité unique** pour les tarifs et règles
- Si un tarif change → modifier `knowledge_base.json` ET la grille dans `SYSTEM_PROMPT` (dans `ollama_service.py`)
- Les fichiers `data/` (dataset, inbox) sont dans `.gitignore`

---

## Fichiers legacy / à supprimer

- `app/services/gemini_service.py` — ancienne implémentation avec Google Gemini, **non utilisée**. Référence un schema `GeminiResponse` qui n'existe plus dans `schemas.py`. À supprimer.

---

## Points d'attention pour les modifications

1. **System prompt** (`ollama_service.py`) : très long et structuré avec des règles strictes anti-hallucination. Ne pas simplifier sans raison — chaque règle corrige un problème réel observé.

2. **Debounce** : système en mémoire (`_pending_tasks`, `_message_queues`). Ne survit pas à un redémarrage du serveur. Attention aux race conditions.

3. **CalDAV** : la connexion iCloud est mise en cache dans l'instance `ICloudCalendar`. Le mock n'est plus branché par défaut (le code utilise `ICloudCalendar()` directement).

4. **Délai humain** : actuellement fixé à 5s en dur (`instagram_service.py` ligne 87), le vrai délai `random.uniform(30, 120)` est commenté.

5. **CORS** : seuls `localhost:3000` et `127.0.0.1:3000` sont autorisés (dev uniquement).

6. **Base SQLite** : créée au premier lancement via `Base.metadata.create_all()` dans le lifespan.

7. **Le champ `response` vs `reply`** : dans `AIResponse` le champ est `response`, mais le LLM est instruit à retourner `reply`. Le parsing dans `ollama_service.py` gère les deux.

---

## TODOs connus (du propriétaire)

- Améliorer la cohérence contextuelle (l'IA doit mieux utiliser l'historique de conversation)
- Ajouter les prix dans le prompt (✅ fait)
- Collecter le prénom pour la prise de RDV (✅ fait)
- Gérer les reply de story Instagram
- Remplacer `asyncio.sleep` par une vraie file d'attente (Celery/ARQ)
- Ajouter l'authentification sur les endpoints dashboard
- Supprimer `gemini_service.py`
- Déployer en production
