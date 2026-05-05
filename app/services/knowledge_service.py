"""
Knowledge service — charge la base de connaissance (tarifs, règles métier, infos)
et formate un bloc de contexte injecté dans le system prompt.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_KB_PATH = Path(__file__).parent.parent.parent / "data" / "knowledge_base.json"


@lru_cache(maxsize=1)
def _load_knowledge_base() -> dict:
    """Charge knowledge_base.json une seule fois (mis en cache)."""
    try:
        with open(_KB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Impossible de charger knowledge_base.json : %s", exc)
        return {}


def build_knowledge_context() -> str:
    """
    Retourne un bloc texte structuré à injecter dans le system prompt.
    Contient : grille tarifaire, règles métier, infos pratiques,
    et les règles explicites pour les prix variables.
    """
    kb = _load_knowledge_base()
    if not kb:
        return ""

    lines = ["\n━━━ BASE DE CONNAISSANCE — SOURCE DE VÉRITÉ ABSOLUE ━━━"]

    # ── Infos pratiques ──────────────────────────────────────
    infos = kb.get("infos_pratiques", {})
    if infos:
        lines.append("\n📍 INFOS PRATIQUES :")
        lines.append(f"  adresse : {infos.get('adresse', 'N/A')}")
        lines.append(f"  code portail : {infos.get('code_portail', 'N/A')}")
        lines.append(f"  paiement : {infos.get('paiement', 'N/A')}")
        lines.append(f"  disponibilités : {infos.get('disponibilites', 'N/A')}")

    # ── Grille tarifaire ─────────────────────────────────────
    tarifs = kb.get("tarifs", {})
    if tarifs:
        lines.append("\nGRILLE TARIFAIRE OFFICIELLE (utilise UNIQUEMENT ces prix) :")
        services_variables = set(kb.get("services_prix_variable", []))

        for key, t in tarifs.items():
            label = t.get("label", key)

            if t.get("prix_par_unite"):
                # Prix par unité (ex: barrel twists)
                grille = t.get("grille", "prix variable")
                lines.append(f"  • {label} → {grille} [DEMANDER LE NOMBRE AVANT DE CITER UN PRIX]")
            elif "prix" in t:
                prix_str = f"{t['prix']}€"
                note = f" ({t['note']})" if t.get("note") else ""
                marker = " [PRIX VARIABLE]" if key in services_variables else ""
                lines.append(f"  • {label} → {prix_str}{note}{marker}")
            elif "prix_min" in t and "prix_max" in t:
                prix_str = f"{t['prix_min']}–{t['prix_max']}€"
                note = f" ({t['note']})" if t.get("note") else ""
                lines.append(f"  • {label} → {prix_str}{note} [PRIX VARIABLE — DEMANDER INFOS AVANT]")
            else:
                lines.append(f"  • {label} → prix variable")

    # ── Règles prix variables ──────────────────────────────────
    regles_prix = kb.get("regles_prix_variables", {})
    if regles_prix:
        lines.append("\nREGLES ANTI-HALLUCINATION — PRIX VARIABLES :")
        lines.append("  Pour ces services, NE DONNE JAMAIS un prix sans avoir les infos :")
        for service, regle in regles_prix.items():
            lines.append(f"  • {service} → {regle}")

    # ── Règles métier ─────────────────────────────────────────
    regles = kb.get("regles_metier", {})
    if regles:
        lines.append("\nREGLES METIER STRICTES :")
        if regles.get("tarifs_non_negociables"):
            lines.append("  - les tarifs sont FIXES — ne jamais négocier, même si la cliente insiste")
        if not regles.get("remise_etudiant"):
            lines.append("  - pas de tarif étudiant ni de remise spéciale")
        if not regles.get("remise_fidelite"):
            lines.append("  - pas de remise fidélité")
        if not regles.get("avec_rajouts_meches"):
            lines.append("  - pas de coiffures avec mèches ou rajouts")
        if not regles.get("coupe_contours"):
            lines.append("  - pas de coupe/contours")
        if regles.get("photo_requise_avant_rdv"):
            lines.append("  - toujours demander une photo des cheveux avant de confirmer le RDV")
        if regles.get("cheveux_propres_requis"):
            lines.append("  - rappeler que les cheveux doivent être propres et démêlés le jour du RDV")
        if regles.get("paiement"):
            lines.append(f"  - paiement : {regles['paiement']}")

    # ── Prestations non proposées ─────────────────────────────
    non_dispo = kb.get("prestations_non_proposees", [])
    if non_dispo:
        lines.append("\nPRESTATIONS NON PROPOSEES (refuse poliment, sans exception) :")
        for item in non_dispo:
            lines.append(f"  • {item}")

    lines.append("")
    lines.append("REGLES ABSOLUES :")
    lines.append("  1. Ne JAMAIS inventer un prix — cite uniquement les tarifs de la grille ci-dessus.")
    lines.append("  2. Pour tout service à prix variable → pose UNE question pour obtenir l'info manquante.")
    lines.append("  3. Si une cliente demande un service non proposé → refuse clairement mais gentiment.")
    lines.append("  4. Ne jamais dire 'environ', 'à peu près', 'je pense que c'est' pour un prix.")
    lines.append("  5. CRUCIAL : tu ES la coiffeuse — ne jamais dire 'je vais demander', 'je vais vérifier avec elle',")
    lines.append("     ou toute formule qui révèle qu'il y a une autre personne. Si tu ne sais pas → needs_human=true.")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    return "\n".join(lines)
