"""Réponse « de bout en bout » à une question libre, sans modèle de langage : c'est un enquêteur, pas un rédacteur.

Pipeline : intention connue (DPE d'une adresse) -> sinon recherche dans le catalogue -> pour les meilleurs jeux dont un fichier
est interrogeable, lecture en direct des premières lignes, filtrées sur le lieu cité (« à Bordeaux ») quand une colonne
de commune existe. Le résultat est un dossier de pièces sourcées ; la rédaction de la réponse revient à Claude (outil MCP
`repondre`) ou à la personne qui lit.
"""
from __future__ import annotations

import re
import sqlite3

from . import dpe, live, search

_CAP = r"[A-ZÉÈÀÂÎÔÛ][\w'’]+"
_PLACE = re.compile(
    rf"\b(?:à|a|de|du|en|pour|sur|dans|autour de)\s+({_CAP}(?:[ -](?:(?:en|de|du|des|la|le|les|sur|sous|lès|lez)[ -])?{_CAP})*)"
)
_PLACE_COL = re.compile(r"^(nom_)?(commune|ville|libelle_commune|lib_commune|nom_commune|libcom|com_name|city|lib_zone|libgeo|nom_com|localite|libelle_geographique)(_.*)?$", re.IGNORECASE)
_NOISE = {"cherche", "chercher", "moi", "donne", "donnes", "trouve", "trouver", "montre", "quel", "quelle", "quels", "quelles",
          "combien", "est", "sont", "il", "y", "a", "svp", "stp", "peux", "tu", "informations", "information", "infos", "info",
          "données", "donnees", "sur", "liste", "voir", "je", "veux", "voudrais", "savoir", "ont", "eu", "lieu", "ayant", "existe", "existent"}


def extract_place(question: str) -> str | None:
    m = _PLACE.search(question or "")
    return m.group(1) if m else None


def keywords(question: str, place: str | None) -> str:
    q = question or ""
    if place:
        q = q.replace(place, " ")
    words = re.findall(r"[\w'’-]+", q.lower())
    return " ".join(w for w in words if w not in _NOISE and len(w) > 1)[:200]


def _columns_and_total(resource_id: str) -> tuple[list[str], dict]:
    r = live.tabular_query(resource_id, page_size=1)
    rows = r.get("lignes") or []
    return (list(rows[0]) if rows else []), r


def investigate(conn: sqlite3.Connection, question: str, max_leads: int = 3) -> dict:
    place = extract_place(question)
    query = keywords(question, place)
    out: dict = {"intention": "general", "question": question, "lieu_detecte": place, "mots_cles": query,
                 "pistes": [], "api": [], "resultats": {}}
    kinds = search.search(conn, query, "tout", limit=6)
    out["resultats"] = {
        k: [{f: (v[:160] if f == "extrait" and isinstance(v, str) else v) for f, v in r.items()
             if f in ("id", "slug", "title", "name", "organization_name", "last_update", "frequency", "page", "extrait",
                      "access_type", "base_api_url", "type", "url")}
            for r in rows[:4]]
        for k, rows in kinds.items() if k != "discussions"}
    out["api"] = [{"id": a["id"], "titre": a["title"], "producteur": a["organization_name"], "acces": a["access_type"], "url_base": a["base_api_url"]}
                  for a in kinds.get("dataservices", [])[:3]]
    ranked = search.search(conn, query, "jeux_de_donnees", limit=10, interrogeable=True)["datasets"]
    if place:  # un jeu qui nomme le lieu (ou un producteur local) passe devant, à pertinence égale
        ranked.sort(key=lambda d: place.lower() not in f"{d['title']} {d['organization_name']}".lower())
    for ds in ranked:
        if len(out["pistes"]) >= max_leads:
            break
        res = conn.execute("SELECT id, title, format FROM resources WHERE dataset_id=? AND tabular=1 "
                           "ORDER BY CASE type WHEN 'main' THEN 0 ELSE 1 END, filesize DESC LIMIT 1", (ds["id"],)).fetchone()
        if not res:
            continue
        piste = {"jeu": ds["title"], "producteur": ds["organization_name"], "page": ds["page"], "fichier": res["title"],
                 "resource_id": res["id"], "filtre": None, "total": None, "colonnes": [], "lignes": []}
        try:
            cols, first = _columns_and_total(res["id"])
            piste["colonnes"] = cols[:40]
            place_col = next((c for c in cols if _PLACE_COL.match(c)), None) if place else None
            if place and place_col:
                piste["filtre"] = f"{place_col} contient « {place} »"
                data = live.tabular_query(res["id"], filters={f"{place_col}__contains": place}, page_size=5)
            else:
                data = first
            piste["total"] = data.get("total")
            piste["lignes"] = (data.get("lignes") or [])[:5]
            piste["avertissement"] = data.get("avertissement")
        except Exception as exc:  # noqa: BLE001 : une piste en échec n'arrête pas les autres
            piste["erreur"] = str(exc)[:200]
        out["pistes"].append(piste)
    out["limites"] = ("Pistes issues d'une recherche par mots-clés : à vérifier avant d'en tirer une conclusion. "
                      "Les lignes sont les premières du fichier (filtrées sur le lieu s'il a pu être détecté), pas une réponse calculée.")
    return out


def repondre(conn: sqlite3.Connection, question: str) -> dict:
    question = (question or "").strip()[:400]
    if len(question) < 3:
        return {"erreur": "question trop courte"}
    if dpe.wants_dpe(question):
        return {"intention": "dpe", "question": question, **dpe.dpe_par_adresse(dpe.extract_address(question))}
    return investigate(conn, question)
