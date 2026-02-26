"""
Ollama AI service — generates Instagram-style replies using Llama 3.1 locally.

Uses the ``ollama`` Python library to communicate with a local Ollama instance.
The model returns structured JSON with the reply text and a ``needs_human`` flag
indicating whether a human should take over the conversation.
"""

import json
import logging
from typing import Any

import ollama

from app.core.config import get_settings
from app.models.schemas import AIResponse

logger = logging.getLogger(__name__)

# ─── System prompt (optimised for Llama 3.1) ──────────────

SYSTEM_PROMPT = """\
tu es l'assistante IA invisible d'une coiffeuse indépendante spécialisée en cheveux afro et locks.
ton rôle : répondre aux clientes de manière naturelle, chaleureuse et professionnelle,
comme si c'était la coiffeuse elle-même qui tapait.

règles de ton :
- tutoie toujours la cliente
- jamais de majuscule en début de phrase
- sois brève : 1 à 3 phrases max
- sois chaleureuse mais pas "trop" (pas de "ma chérie", pas de "bisous")
- utilise un langage naturel Instagram (pas de langage soutenu)

spécialités proposées (cheveux afro, texturés, naturels et locks) :
- Retwist (entretien et resserrement des locks)
- Starter Locks (création de locks)
- Entretien Locks
- Tresses Vanilles (twists / deux-strands)
- Box Braids / Nattes africaines
- Faux Locs
- Twist Out
- Coupe Afro / Coupe Enfant
- Coupe + Façon
- Shampoing + Soin / Soin Hydratation
- Démêlage + Soin
- Pose de perruque / Wig install

ce que tu sais faire :
- répondre aux questions sur les prestations listées ci-dessus
- consulter l'agenda (créneaux libres fournis ci-dessous) et proposer des RDVs
- POSER UN RDV directement si la cliente demande un créneau précis et qu'il est libre
- donner des infos pratiques (adresse, tarifs approximatifs)
- répondre aux compliments ou remerciements

règles pour les RDVs :
- si la cliente demande un créneau disponible → utilise le champ "book" pour le poser
- si le créneau demandé est déjà pris → propose les créneaux libres listés dans l'agenda
- si tu n'as pas assez d'info (prestation pas claire, date floue) → demande des précisions
- durées estimées selon la prestation :
  retwist=90min, starter locks=180min, entretien locks=60min,
  tresses vanilles=120min, box braids=180min, faux locs=240min,
  twist out=60min, coupe afro=45min, coupe enfant=30min, coupe+façon=60min,
  shampoing+soin=60min, soin hydratation=45min, démêalage+soin=90min, wig install=90min

needs_human = true UNIQUEMENT pour :
- insulte explicite ou manque de respect clair envers la coiffeuse
- réclamation sérieuse ou problème client grave
- gestion d'un paiement ou d'un acompte
NE JAMAIS mettre needs_human = true pour une demande de RDV ou une question normale.

IMPORTANT : tu DOIS répondre UNIQUEMENT avec un objet JSON valide, sans aucun texte avant ou après.
Le format EXACT est :
{"reply": "ta réponse ici", "needs_human": false, "book": null}

Quand tu poses un RDV, remplis le champ book :
{"reply": "top ! je te bloque lundi à 9h pour un retwist", "needs_human": false, "book": {"service": "Retwist", "date": "YYYY-MM-DD", "hour": 9, "minute": 0, "duration_minutes": 90}}

Quand tu n'as pas besoin de poser de RDV :
{"reply": "hey ! oui je fais les box braids, tu veux que je regarde mes dispos ?", "needs_human": false, "book": null}

Ne mets JAMAIS de texte en dehors du JSON. Pas de ```json, pas d'explication, juste le JSON brut.
"""


# ─── Client setup ─────────────────────────────────────────

_client: ollama.Client | None = None


def _get_client() -> ollama.Client:
    """Lazy‑init the Ollama client (configured once)."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = ollama.Client(host=settings.ollama_base_url)
        logger.info("Ollama client initialised (host=%s)", settings.ollama_base_url)
    return _client


# ─── Public API ────────────────────────────────────────────

async def generate_response(
    message: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> AIResponse:
    """
    Send *message* (+ optional history) to Ollama/Llama 3.1 and return a typed response.

    Le contexte calendrier (créneaux libres du jour) est injecté automatiquement
    dans le system prompt à chaque appel.
    """
    from app.services.calendar_service import build_ai_system_context
    from app.models.schemas import BookingRequest

    client = _get_client()
    settings = get_settings()

    # Injecte l'agenda en temps réel dans le system prompt
    try:
        calendar_context = build_ai_system_context()
    except Exception as cal_exc:
        logger.warning("Impossible de récupérer le calendrier : %s", cal_exc)
        calendar_context = ""

    system_content = SYSTEM_PROMPT + calendar_context

    # Build the message list for Ollama
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_content},
    ]

    if conversation_history:
        for entry in conversation_history:
            role = entry.get("role", "user")
            if role == "model":
                role = "assistant"
            content = entry.get("content") or " ".join(entry.get("parts", []))
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})

    try:
        result = client.chat(
            model=settings.ollama_model,
            messages=messages,
            options={
                "temperature": 0.7,
                "num_predict": 350,
            },
            format="json",
        )

        raw_text = result.message.content.strip() if result.message.content else ""
        logger.debug("Ollama raw response: %s", raw_text)

        # Parse the structured JSON response
        parsed = json.loads(raw_text)

        # Parse le champ book optionnel
        book_data = parsed.get("book")
        book: BookingRequest | None = None
        if isinstance(book_data, dict):
            try:
                book = BookingRequest(**book_data)
                logger.info("📅 IA demande RDV : %s le %s à %sh%02d",
                            book.service, book.date, book.hour, book.minute)
            except Exception as e:
                logger.warning("Champ 'book' invalide ignoré : %s", e)

        return AIResponse(
            response=parsed.get("reply", parsed.get("response", raw_text)),
            needs_human=parsed.get("needs_human", False),
            book=book,
        )

    except json.JSONDecodeError as exc:
        logger.warning("Ollama returned non‑JSON — treating as plain text: %s", exc)
        raw_fallback = raw_text if raw_text else ""
        return AIResponse(response=raw_fallback, needs_human=True)

    except Exception as exc:
        logger.error("Ollama API call failed: %s", exc, exc_info=True)
        return AIResponse(
            response="",
            needs_human=True,
        )
