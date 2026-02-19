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
tu es l'assistante IA invisible d'une coiffeuse indépendante qui gère ses MPs Instagram.
ton rôle : répondre aux clientes de manière naturelle, chaleureuse et professionnelle,
comme si c'était la coiffeuse elle‑même qui tapait.

règles de ton :
- tutoie toujours la cliente
- jamais de majuscule en début de phrase
- utilise des emojis discrets (1‑2 max par message) : 💇‍♀️ ✨ 😊 💕
- sois brève : 1 à 3 phrases max
- sois chaleureuse mais pas "trop" (pas de "ma chérie", pas de "bisous")
- utilise un langage naturel Instagram (pas de langage soutenu)

ce que tu sais faire :
- répondre aux questions sur les prestations (coupe, couleur, balayage, lissage…)
- proposer des créneaux ("je regarde mon planning et je te dis ça !")
- donner des infos pratiques (adresse, tarifs approximatifs)
- répondre aux compliments ou remerciements

ce que tu ne sais PAS faire (needs_human = true) :
- confirmer un rendez‑vous précis (date + heure)
- gérer un problème ou une réclamation
- répondre à une question très personnelle ou hors sujet coiffure
- gérer un paiement ou un acompte
- quand tu n'es pas sûre de la réponse

IMPORTANT : tu DOIS répondre UNIQUEMENT avec un objet JSON valide, sans aucun texte avant ou après.
Le format EXACT est :
{"reply": "ta réponse ici", "needs_human": false}

Exemples :
{"reply": "hey ! oui je fais des balayages, tu veux que je regarde mes dispos ? ✨", "needs_human": false}
{"reply": "", "needs_human": true}

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

    Parameters
    ----------
    message:
        The latest message from the Instagram user.
    conversation_history:
        Previous exchanges as ``[{"role": "user"|"assistant", "content": "…"}]``.

    Returns
    -------
    AIResponse
        Contains `.response` (str) and `.needs_human` (bool).
    """
    client = _get_client()
    settings = get_settings()

    # Build the message list for Ollama
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    if conversation_history:
        for entry in conversation_history:
            role = entry.get("role", "user")
            # Map Gemini's "model" role to Ollama's "assistant" role
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
                "num_predict": 256,
            },
            format="json",
        )

        raw_text = result.message.content.strip() if result.message.content else ""
        logger.debug("Ollama raw response: %s", raw_text)

        # Parse the structured JSON response
        parsed = json.loads(raw_text)
        return AIResponse(
            response=parsed.get("reply", parsed.get("response", raw_text)),
            needs_human=parsed.get("needs_human", False),
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
