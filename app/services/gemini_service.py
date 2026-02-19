"""
Gemini AI service — generates Instagram-style replies for the hairdresser bot.

Uses the new ``google-genai`` SDK (replaces the deprecated google-generativeai).
The model returns structured JSON with the reply text and a ``needs_human`` flag
indicating whether a human should take over the conversation.
"""

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.models.schemas import GeminiResponse

logger = logging.getLogger(__name__)

# ─── System prompt ────────────────────────────────────────

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

tu DOIS répondre UNIQUEMENT avec un objet JSON valide, sans texte autour :
{
  "response": "ta réponse ici",
  "needs_human": false
}
"""

# ─── Configure the client ─────────────────────────────────

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Lazy‑init the Gemini client (configured once)."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = genai.Client(api_key=settings.gemini_api_key)
        logger.info("Gemini client initialised (google-genai SDK)")
    return _client


# ─── Public API ────────────────────────────────────────────

async def generate_response(
    message: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> GeminiResponse:
    """
    Send *message* (+ optional history) to Gemini and return a typed response.

    Parameters
    ----------
    message:
        The latest message from the Instagram user.
    conversation_history:
        Previous exchanges as ``[{"role": "user"|"model", "parts": ["…"]}]``.

    Returns
    -------
    GeminiResponse
        Contains `.response` (str) and `.needs_human` (bool).
    """
    client = _get_client()

    # Build the conversation contents for context
    contents: list[types.Content] = []
    if conversation_history:
        for entry in conversation_history:
            contents.append(
                types.Content(
                    role=entry["role"],
                    parts=[types.Part(text=p) for p in entry.get("parts", [])],
                )
            )
    contents.append(
        types.Content(role="user", parts=[types.Part(text=message)])
    )

    try:
        result = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
                max_output_tokens=256,
                response_mime_type="application/json",
            ),
        )
        raw_text = result.text.strip() if result.text else ""
        logger.debug("Gemini raw response: %s", raw_text)

        # Parse the structured JSON response
        parsed = json.loads(raw_text)
        return GeminiResponse(
            response=parsed.get("response", raw_text),
            needs_human=parsed.get("needs_human", False),
        )

    except json.JSONDecodeError as exc:
        logger.warning("Gemini returned non‑JSON — treating as plain text: %s", exc)
        raw_fallback = result.text.strip() if result and result.text else ""
        return GeminiResponse(response=raw_fallback, needs_human=True)

    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc, exc_info=True)
        return GeminiResponse(
            response="",
            needs_human=True,
        )
