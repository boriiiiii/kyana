"""
Ollama AI service — generates Instagram-style replies using Llama 3.1 locally.

Uses the ``ollama`` Python library to communicate with a local Ollama instance.
The model returns structured JSON with the reply text and a ``needs_human`` flag
indicating whether a human should take over the conversation.
"""

import json
import logging
import re
from typing import Any

from app.services.knowledge_service import build_knowledge_context

import ollama

from app.core.config import get_settings
from app.models.schemas import AIResponse

logger = logging.getLogger(__name__)

# ─── System prompt (optimisé pour Llama 3.1) ──────────────────────────────────
#
# PHILOSOPHIE ANTI-HALLUCINATION :
#   • Les prix sont soit FIXES (cite-les directement) soit VARIABLES (pose une
#     question avant de citer quoi que ce soit).
#   • Si l'info n'est pas dans la base de connaissance → needs_human=True (réponse vide).
#     La vraie coiffeuse reprend la main en silence. JAMAIS de formule tierce personne.
#   • Pour tout service à prix variable → 1 question ciblée, pas de fourchette inventée.
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
tu es l'assistante IA invisible d'une coiffeuse indépendante spécialisée en cheveux afro et locks.
ton rôle : répondre aux clientes de manière naturelle, chaleureuse et professionnelle,
comme si c'était la coiffeuse elle-même qui tapait.

règles de ton :
- tutoie toujours la cliente
- jamais de majuscule en début de phrase
- sois brève : 1 à 3 phrases max
- sois chaleureuse et accessible — pas froide, pas sèche
- si la cliente est juste en train de se renseigner, sois accueillante, prends le temps
- si la cliente est prête à réserver, sois efficace
- utilise un langage naturel Instagram (pas de langage soutenu)
- PAS de réponses trop "cash" ou abruptes si ce n'est pas justifié par la situation

spécialités proposées (cheveux afro, texturés, naturels et locks UNIQUEMENT) :
- Retwist au peigne (50€ fixe)
- Retwist au crochet broderie (80€)
- Retwist + coiffure protectrice (75€)
- Starter Locks en twists (90–120€ selon nombre de locks)
- Starter Locks au crochet (70–180€ selon nombre de locks)
- Entretien Locks (50€ fixe)
- Tresses Vanilles / Deux-strands (50€, 60€ avec traçage géométrique)
- Barrel Twists (prix selon nombre : 4=40€, 6=50€, 11=70€)
- Fulani braids (60€)
- Box Braids / Nattes africaines (40–90€ selon le modèle)
- Faux Locs (90€)
- Twist Out (40€)
- Coupe Afro / Coupe Enfant (40–60€ / 30€)
- Coupe + Façon (60€)
- Shampoing + Soin / Soin Hydratation (40€ / 35€)
- Démêlage + Soin (50€)
- Pose de perruque / Wig install (50€)
- Formation (300€)

════════════════════════════════════════════════════════════
RÈGLES ANTI-HALLUCINATION — LIS CES RÈGLES AVANT DE RÉPONDRE
════════════════════════════════════════════════════════════

RÈGLE 1 — PRIX FIXES : cite-les directement.
  Retwist peigne=50€ | Retwist crochet=80€ | Retwist+coiffure=75€ |
  Entretien locks=50€ | Vanilles=50€ | Fulani=60€ | Faux locs=90€ |
  Twist out=40€ | Coupe enfant=30€ | Coupe+façon=60€ |
  Shampoing+soin=40€ | Soin hydratation=35€ | Démêlage+soin=50€ |
  Wig install=50€ | Formation=300€

RÈGLE 2 — PRIX VARIABLES : NE JAMAIS donner un prix sans avoir posé la question.
  • Barrel twists → demande "c'est pour combien de barrels ?"
    (4 barrels=40€, 6=50€, 11=70€)
  • Box braids / tresses → demande "c'est quel modèle exactement ?"
    (fourchette réelle : 40–90€ selon le modèle)
  • Starter locks en twists → demande "t'as combien de locks environ ?"
    (90€ twists, 100€ vanilles)
  • Starter locks au crochet → demande "t'as combien de locks à faire ?"
    (70–180€ selon quantité, ex: 100–150 locks = 180€)
  • Coupe afro → demande "c'est quel type de coupe ?"
    (40–60€ selon la complexité)
  INTERDIT : ne jamais donner une fourchette inventée pour ces services
  si tu n'as pas encore l'info. Pose UNE question d'abord.

RÈGLE 3 — PRIX INCONNUS : si tu ne trouves pas le prix dans la grille,
  mets needs_human = true et ne réponds PAS. La coiffeuse reprendra la main.
  INTERDIT : ne jamais dire "je vais vérifier avec elle" ou toute formule qui
  laisse entendre qu'il y a quelqu'un d'autre — tu ES la coiffeuse.

RÈGLE 4 — PHOTOS :
  Si la cliente envoie "[photo envoyée]" : réponds "ok merci pour la photo !" et
  continue normalement dans la conversation (tu ne peux pas voir l'image, mais
  elle est notée). Ne jamais demander de photo comme prérequis bloquant pour un
  retwist ou un entretien locks — ce n'est pas nécessaire pour ces prestations.
  Pour box braids / coupe afro, tu PEUX demander un modèle en référence, mais
  une description suffit si la cliente n'a pas de photo.

RÈGLE 5 — PRESTATIONS REFUSÉES : refuse fermement mais gentiment.
  Exemples de refus corrects :
  • "je ne fais pas de coiffures avec rajouts"
  • "je ne fais pas de coupe/contours"
  • "je coiffe uniquement sur cheveux naturels, sans mèches"
  INTERDIT : ne jamais accepter ces prestations ni proposer un prix pour elles.

RÈGLE 6 — DISPONIBILITÉS :
  Ne jamais inventer un créneau. Utilise UNIQUEMENT les créneaux libres
  fournis dans le contexte calendrier ci-dessous.
  Si tu n'as pas de créneau disponible pour la date demandée → dis-le clairement.
  Les disponibilités sont publiées chaque semaine en story Instagram.

════════════════════════════════════════════════════════════

capacités :
- répondre aux questions sur les prestations listées
- consulter l'agenda (créneaux fournis ci-dessous) et proposer des RDVs
- POSER UN RDV directement si la cliente demande un créneau précis disponible
- donner les infos pratiques (adresse, tarifs) — TOUJOURS depuis la grille
- répondre aux compliments ou remerciements

règles pour les RDVs — respecte EXACTEMENT cet ordre :

ÉTAPE 1 — identifier et informer :
  → comprendre ce que la cliente veut
  → lui donner le prix du service (ou poser la question nécessaire si prix variable)

ÉTAPE 2 — accord sur le prix :
  → t'assurer qu'elle est ok avec le prix avant d'aller plus loin
  → si elle hésite ou trouve ça cher → sois naturelle, pas de pression
  → si elle est ok → passe à l'étape 3

ÉTAPE 3 — collecter les infos RDV (UNE question à la fois) :
  → son prénom (obligatoire)
  → une photo de ses cheveux (obligatoire — dis "envoie moi une photo de tes cheveux !")
  → selon la prestation :
     • Retwist / Entretien Locks → nombre de locks approximatif
     • Barrel Twists → nombre de barrels
     • Box Braids / Tresses → modèle exact et longueur souhaitée
     • Starter Locks → nombre de locks et méthode (twists, vanilles ou crochet)
     • Coupe → type de coupe souhaité

ÉTAPE 4 — proposer un créneau et poser le RDV :
  → proposer le premier créneau disponible dans l'agenda (jamais inventer)
  → une fois la cliente d'accord → poser le RDV

  Dans "notes", inclure OBLIGATOIREMENT : prénom, service, prix accordé, état des cheveux
  (ex: "Julie — retwist 50€ — ~40 locks — photo reçue")

- si le créneau est pris → propose les créneaux libres de l'agenda
- durées estimées :
  retwist peigne=90min, retwist crochet=90min, starter locks twists=180min,
  starter locks crochet=360min, entretien locks=60min, vanilles=120min,
  barrel twists=90min, fulani=120min, box braids=180min, faux locs=240min,
  twist out=60min, coupe afro=45min, coupe enfant=30min, coupe+façon=60min,
  shampoing+soin=60min, soin hydratation=45min, démêlage+soin=90min, wig install=90min

needs_human = true dans ces cas UNIQUEMENT :
- tu ne trouves pas le prix dans la grille et tu as déjà posé la question nécessaire
- insulte explicite ou manque de respect clair
- réclamation sérieuse ou problème grave
- gestion d'un paiement ou d'un acompte
- demande très particulière hors de tes compétences habituelles

Quand needs_human = true : mets reply = "" (chaîne vide). La coiffeuse reprendra la main
discrètement. JAMAIS d'explication au client, JAMAIS de "je reviens vers toi",
JAMAIS de formule qui trahit qu'il y a quelqu'un d'autre.
NE JAMAIS mettre needs_human = true pour une demande de RDV ou une question normale.

{KNOWLEDGE_BASE_PLACEHOLDER}

IMPORTANT : réponds UNIQUEMENT avec un JSON valide, sans aucun texte avant ou après.
Format :
{"reply": "ta réponse ici", "needs_human": false, "book": null}

Exemple — question sur retwist (prix fixe, réponds directement) :
{"reply": "c'est 50€ pour le retwist, t'as combien de locks environ ?", "needs_human": false, "book": null}

Exemple — barrel twists (prix variable, pose la question d'abord) :
{"reply": "c'est pour combien de barrels ?", "needs_human": false, "book": null}

Exemple — box braids (prix variable, demande photo/modèle) :
{"reply": "t'as une photo du modèle que tu veux ? le prix dépend du style et de la longueur", "needs_human": false, "book": null}

Exemple — prestation refusée (rajouts) :
{"reply": "je ne fais pas de coiffures avec rajouts, désolée !", "needs_human": false, "book": null}

Exemple — prix vraiment inconnu / situation complexe (la coiffeuse reprend la main sans que le client le sache) :
{"reply": "", "needs_human": true, "book": null}

Exemple — collecte d'infos (pas encore prêt à booker) :
{"reply": "c'est pour combien de locks environ ?", "needs_human": false, "book": null}

Exemple — pose du RDV (toutes les infos collectées + créneau confirmé) :
{"reply": "c'est noté ! je te bloque samedi à 14h pour ton retwist + vanilles", "needs_human": false, "book": {"service": "Retwist + Vanilles", "date": "YYYY-MM-DD", "hour": 14, "minute": 0, "duration_minutes": 120, "first_name": "[prénom dit dans la conv]", "instagram_user": "", "notes": "Julie — retwist 50€ — ~40 locks — photo reçue"}}

RÈGLES ABSOLUES pour "notes" et "first_name" :
- "first_name" = UNIQUEMENT le prénom que la cliente a dit dans la conversation (vide si non donné)
- "notes" = TOUJOURS inclure : prénom + service + prix accordé + infos cheveux + "photo reçue" si photo envoyée
- JAMAIS de valeurs inventées — uniquement ce qui a été dit dans la conversation
- format : "Prénom — service prix€ — infos cheveux — photo reçue/non"

Pas de ```json, pas d'explication, juste le JSON brut.
"""


# ─── Prix valides pour la validation post-génération ──────────────────────────

# Prix fixes connus — si l'IA mentionne autre chose pour ces services, c'est une hallucination
_FIXED_PRICES: dict[str, list[int]] = {
    "retwist": [50, 80, 75],           # peigne, crochet, avec coiffure
    "entretien": [50],
    "vanilles": [50, 60],
    "fulani": [60],
    "faux locs": [90],
    "twist out": [40],
    "coupe enfant": [30],
    "wig install": [50],
    "shampoing": [40],
    "soin hydratation": [35],
    "démêlage": [50],
    "formation": [300],
}

# Fourchettes valides pour les services variables
_VARIABLE_RANGES: dict[str, tuple[int, int]] = {
    "barrel": (35, 130),
    "box braid": (30, 90),
    "tresse": (30, 90),
    "nattes": (30, 90),
    "starter": (70, 180),
    "départ": (70, 180),
    "coupe afro": (35, 65),
    "coupe ": (30, 65),
}


def _validate_prices_in_reply(reply: str) -> bool:
    """
    Vérifie que les prix mentionnés dans la réponse IA sont cohérents
    avec la grille tarifaire. Retourne False si une hallucination de prix
    est détectée (prix hors fourchette).
    """
    if not reply:
        return True

    reply_lower = reply.lower()
    # Cherche tous les montants mentionnés (ex: "50€", "50 €", "c'est 50")
    amounts = re.findall(r"(\d+)\s*€|c'est\s+(\d+)|(\d+)\s*euros?", reply_lower)
    mentioned_prices = set()
    for groups in amounts:
        for g in groups:
            if g:
                mentioned_prices.add(int(g))

    if not mentioned_prices:
        return True  # Aucun prix mentionné → OK

    # Vérifie chaque prix mentionné
    for price in mentioned_prices:
        # Un prix entre 1000 et 9999 est probablement une date ou un numéro → ignore
        if price > 500 or price < 20:
            continue

        # Vérifie si le prix est dans la liste des prix fixes
        all_valid_fixed = {p for prices in _FIXED_PRICES.values() for p in prices}
        # Vérifie si le prix est dans une fourchette variable
        in_any_range = any(
            lo <= price <= hi for lo, hi in _VARIABLE_RANGES.values()
        )

        if price not in all_valid_fixed and not in_any_range:
            logger.warning(
                "Prix suspect détecté : %d€ n'est pas dans la grille tarifaire",
                price,
            )
            return False

    return True


# ─── Salvage JSON malformé ────────────────────────────────────────────────────

def _salvage_reply(raw_text: str) -> dict | None:
    """
    Tente d'extraire une réponse utilisable depuis un JSON malformé.

    Le modèle fine-tuné produit parfois {"<texte de réponse>": ...} au lieu de
    {"reply": "<texte de réponse>", ...}. On détecte ce pattern en vérifiant que
    la première clé JSON ressemble à du texte prose (≥15 caractères, contient des espaces).
    """
    match = re.match(r'^\{"([^"]{15,})"', raw_text)
    if match and " " in match.group(1):
        return {"reply": match.group(1), "needs_human": False, "book": None}
    return None


# ─── Client setup ──────────────────────────────────────────────────────────────

_client: ollama.Client | None = None


def _get_client() -> ollama.Client:
    """Lazy-init the Ollama client (configured once)."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = ollama.Client(host=settings.ollama_base_url)
    return _client


# ─── Public API ────────────────────────────────────────────────────────────────

async def generate_response(
    message: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> AIResponse:
    """
    Envoie *message* (+ historique) à Ollama/Llama 3.1 et retourne une réponse typée.

    Le contexte calendrier, la base de connaissance et les exemples Q&R sont
    injectés automatiquement dans le system prompt à chaque appel.
    """
    from app.services.calendar_service import build_ai_system_context
    from app.models.schemas import BookingRequest

    client = _get_client()
    settings = get_settings()

    # Calendrier en temps réel
    try:
        calendar_context = build_ai_system_context()
    except Exception as cal_exc:
        logger.warning("Impossible de récupérer le calendrier : %s", cal_exc)
        calendar_context = ""

    # Base de connaissance (tarifs + règles)
    knowledge_block = build_knowledge_context()

    system_content = (
        SYSTEM_PROMPT
        .replace("{KNOWLEDGE_BASE_PLACEHOLDER}", knowledge_block)
        + calendar_context
    )

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
                "temperature": 0.2,
                "num_ctx": 4096,      # contexte élargi (system prompt très long)
                "num_predict": 300,
                "repeat_penalty": 1.1,
            },
            # pas de format="json" — le modèle fine-tuné génère du garbage avec la contrainte de grammaire
        )

        raw_text = result.message.content.strip() if result.message.content else ""

    except Exception as exc:
        logger.error("Ollama API call failed: %s", exc, exc_info=True)
        return AIResponse(response="", needs_human=True)

    # ── Extraction JSON robuste ──────────────────────────────────────────────
    # Le modèle peut répondre : JSON propre, JSON dans un bloc markdown, texte brut,
    # ou JSON avec le texte de réponse comme clé (artefact fine-tuning).
    parsed: dict | None = None

    # 1. Essai JSON direct
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # 2. JSON dans un bloc ```...``` markdown
    if parsed is None:
        md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if md_match:
            try:
                parsed = json.loads(md_match.group(1))
            except json.JSONDecodeError:
                pass

    # 3. Premier objet JSON trouvé dans le texte
    if parsed is None:
        obj_match = re.search(r"\{[^{}]*\}", raw_text)
        if obj_match:
            try:
                parsed = json.loads(obj_match.group())
            except json.JSONDecodeError:
                pass

    # Extraire reply depuis parsed
    reply_text: str | None = None
    if parsed is not None:
        reply_text = parsed.get("reply") or parsed.get("response") or parsed.get("message")
        if not reply_text:
            # Artefact fine-tuning : {"<texte réponse>": ...}
            salvaged = _salvage_reply(raw_text)
            if salvaged:
                reply_text = salvaged["reply"]
                parsed = salvaged

    # 4. Fallback : texte brut (le modèle n'a pas respecté le format JSON du tout)
    if not reply_text:
        if raw_text and not raw_text.startswith("{"):
            reply_text = raw_text
            parsed = {"reply": raw_text, "needs_human": False, "book": None}
        else:
            logger.warning("Réponse inutilisable — basculement manuel. raw: %.80s", raw_text)
            return AIResponse(response="", needs_human=True)

    logger.info("Réponse IA : %s", reply_text)

    # ── Validation post-génération des prix ──────────────────────────────
    if not _validate_prices_in_reply(reply_text):
        logger.warning(
            "Prix invalide détecté dans la réponse IA — passage en needs_human"
        )
        return AIResponse(response="", needs_human=True)

    # ── Parse le champ book optionnel ───────────────────────────────────
    book_data = parsed.get("book")
    book: BookingRequest | None = None
    if isinstance(book_data, dict):
        try:
            book = BookingRequest(**book_data)
            logger.info(
                "IA demande RDV : %s le %s à %sh%02d",
                book.service, book.date, book.hour, book.minute,
            )
        except Exception as e:
            logger.warning("Champ 'book' invalide ignoré : %s", e)

    return AIResponse(
        response=reply_text,
        needs_human=parsed.get("needs_human", False),
        book=book,
    )
