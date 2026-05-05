# Kyana — Agent IA pour salon de coiffure

Backend FastAPI qui automatise les réponses aux messages privés Instagram d'une coiffeuse indépendante. Le modèle fine-tuné reproduit son style de communication comme si c'était elle qui répondait.

## Contexte

Une coiffeuse indépendante passait plusieurs heures par semaine à répondre manuellement à ses DM Instagram : demandes de disponibilités, questions de prix, confirmations de RDV. Kyana automatise ce flux entièrement, avec un modèle entraîné sur ses propres conversations.

## Pipeline IA

```
Conversations Instagram réelles
        ↓
Extraction & nettoyage du dataset
        ↓
Fine-tuning Llama 3.2 3B (MLX LoRA — MacBook Air M2)
        ↓
Conversion & quantisation → GGUF
        ↓
Import dans Ollama comme modèle personnalisé
        ↓
Agent déployé sur Instagram
```

## Fonctionnalités

- Réponses automatiques aux DM Instagram
- Style conversationnel calqué sur la communication réelle de la coiffeuse
- Logique de doute — si l'IA n'est pas sûre, la conversation bascule en mode manuel et une alerte est émise
- Délai humain simulé (30–120 secondes)
- Mode auto / manuel par conversation
- Historique complet en base (SQLite)
- Dashboard API — endpoints REST prêts pour un futur frontend

## Stack

| Composant | Technologie |
|-----------|-------------|
| Backend | FastAPI · Python 3.11+ |
| LLM | Ollama · Llama 3.2 3B (fine-tuné) |
| Fine-tuning | MLX · LoRA · GGUF |
| Base de données | SQLite · SQLAlchemy 2.0 |
| Messaging | Instagram Graph API v25.0 |
| HTTP client | httpx (async) |
| Validation | Pydantic v2 |

## Installation

```bash
git clone https://github.com/boriiiiii/kyana.git
cd kyana

# Setup complet (venv + dépendances + .env)
make setup

# Lancer Ollama en arrière-plan
ollama serve

# Lancer le serveur
make dev
```

## Configuration

```bash
cp .env.example .env
```

| Variable | Description | Défaut |
|----------|-------------|--------|
| `OLLAMA_BASE_URL` | URL du serveur Ollama | `http://localhost:11434` |
| `OLLAMA_MODEL` | Modèle à utiliser | `llama3.2` |
| `INSTA_VERIFY_TOKEN` | Token de vérification webhook | — |
| `INSTA_ACCESS_TOKEN` | Token d'accès Instagram Graph API | — |
| `INSTA_ACCOUNT_ID` | ID du compte Instagram professionnel | — |
| `DATABASE_URL` | URL de la base de données | `sqlite:///./kyana.db` |

## Commandes

| Commande | Description |
|----------|-------------|
| `make dev` | Serveur avec hot-reload |
| `make run` | Serveur production |
| `make test` | Lancer les tests |
| `make install` | Installer les dépendances |
| `make setup` | Setup complet |

## Endpoints API

**Webhook**

| Méthode | URL | Rôle |
|---------|-----|------|
| `GET` | `/webhook` | Vérification Meta (challenge-response) |
| `POST` | `/webhook` | Réception des messages entrants |

**Dashboard**

| Méthode | URL | Rôle |
|---------|-----|------|
| `GET` | `/api/stats` | Stats globales |
| `GET` | `/api/conversations` | Liste des conversations |
| `GET` | `/api/conversations/{id}/messages` | Historique d'une conversation |
| `PATCH` | `/api/conversations/{id}/mode` | Basculer auto / manuel |

## Logique de doute

Quand un message arrive, l'IA répond avec un JSON structuré :

```json
{
  "reply": "salut ! je regarde mon planning et je te dis ça",
  "needs_human": false
}
```

Si `needs_human` est `true`, la conversation bascule en mode manuel, aucune réponse automatique n'est envoyée, et une alerte est loggée.

## Structure

```
kyana/
├── app/
│   ├── main.py                   # Point d'entrée FastAPI
│   ├── core/config.py            # Configuration (.env / Pydantic Settings)
│   ├── models/
│   │   ├── database.py           # Connexion SQLite / SQLAlchemy
│   │   ├── conversation.py       # Modèles ORM
│   │   └── schemas.py            # Schémas Pydantic
│   ├── services/
│   │   ├── ollama_service.py     # Logique IA
│   │   └── instagram_service.py  # Webhook et envoi de messages
│   └── api/
│       ├── webhook.py            # Endpoints webhook
│       └── dashboard.py          # Endpoints dashboard
├── tests/
├── requirements.txt
├── .env.example
└── Makefile
```

> Les données d'entraînement (conversations Instagram) ne sont pas incluses dans ce repo pour des raisons de confidentialité.
