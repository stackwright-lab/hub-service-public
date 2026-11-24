"""DPE d'une adresse : géocodage officiel (Géoplateforme/BAN) puis diagnostics ADEME (logements existants, depuis juillet 2021).

Lecture seule, deux hôtes fixes. Le jeu ADEME ne contient aucun nom d'occupant ou de propriétaire.
Limite : seuls les DPE « logements existants » sont interrogés (ni le neuf, ni le tertiaire, ni les DPE d'avant juillet 2021).
"""
from __future__ import annotations

import re

from . import config, net

FIELDS = [
    "numero_dpe", "date_etablissement_dpe", "date_fin_validite_dpe", "etiquette_dpe", "etiquette_ges", "type_batiment",
    "surface_habitable_logement", "annee_construction", "periode_construction", "conso_5_usages_par_m2_ep",
    "emission_ges_5_usages_par_m2", "type_energie_principale_chauffage", "type_installation_chauffage",
    "cout_total_5_usages", "qualite_isolation_enveloppe", "adresse_ban",
]
_STREET = r"(?:rue|avenue|av|boulevard|bd|chemin|impasse|place|all[ée]e|cours|quai|route|square|passage|cité|cite|résidence|residence)"
ADDRESS_RE = re.compile(rf"\b\d{{1,4}}\s*(?:bis|ter|quater)?\s*,?\s*{_STREET}\b.+", re.IGNORECASE)
INTENT_RE = re.compile(r"\b(dpe|diagnostic|[ée]tiquette\s+[ée]nerg|performance\s+[ée]nerg)", re.IGNORECASE)


def extract_address(text: str) -> str | None:
    """Adresse postale trouvée dans une phrase (« cherche le DPE du 10 rue de Rivoli à Paris »)."""
    m = ADDRESS_RE.search(text or "")
    return re.sub(r"\s+(à|a)\s+", " ", m.group(0).strip(" ?.!"), flags=re.IGNORECASE) if m else None


def wants_dpe(text: str) -> bool:
    return bool(INTENT_RE.search(text or "")) and extract_address(text) is not None


def geocode(address: str) -> dict | None:
    data = net.get_json(f"{config.GEOCODE_BASE}/search/", params={"q": address[:200], "limit": 1}, timeout=20, retries=2)
    feats = data.get("features") or []
    if not feats:
        return None
    p = feats[0].get("properties") or {}
    return {"label": p.get("label"), "score": p.get("score"), "type": p.get("type"), "citycode": p.get("citycode"),
            "postcode": p.get("postcode"), "ville": p.get("city"),
            "coordonnees": (feats[0].get("geometry") or {}).get("coordinates")}


def dpe_par_adresse(address: str, limit: int = 20) -> dict:
    address = (address or "").strip()
    if len(address) < 5:
        return {"erreur": "adresse trop courte"}
    try:
        geo = geocode(address)
    except net.HttpError as exc:
        return {"erreur": f"géocodage indisponible : {exc}"[:300]}
    if not geo or (geo["score"] or 0) < 0.5:
        return {"erreur": "adresse introuvable ou trop imprécise (indiquez numéro, rue et ville)", "geocodage": geo}
    if geo["type"] != "housenumber":
        return {"erreur": "la recherche exige un numéro de rue précis", "adresse_reconnue": geo["label"]}
    limit = max(1, min(int(limit), 50))
    try:
        data = net.get_json(config.ADEME_DPE_LINES, params={
            "adresse_ban_eq": geo["label"], "size": limit, "sort": "-date_etablissement_dpe", "select": ",".join(FIELDS)},
            timeout=30, retries=2)
    except net.HttpError as exc:
        return {"erreur": f"API ADEME indisponible : {exc}"[:300], "adresse_reconnue": geo["label"]}
    rows = data.get("results") or []
    for r in rows:
        r.pop("_score", None)
    return {
        "adresse_reconnue": geo["label"], "score_geocodage": geo["score"], "total": data.get("total", len(rows)),
        "diagnostics": rows,
        "sources": ["data.geopf.fr/geocodage (Base Adresse Nationale)", "data.ademe.fr, jeu « DPE Logements existants (depuis juillet 2021) »"],
        "limites": "Un même immeuble compte un DPE par logement diagnostiqué ; l'absence de résultat ne prouve pas l'absence de DPE "
                   "(logement non diagnostiqué, DPE antérieur à juillet 2021, neuf ou tertiaire).",
    }
