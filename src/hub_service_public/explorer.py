"""Fonctions JSON de l'interface de recherche : index local (hors ligne) + aperçu des fichiers (direct).

Aucune écriture, aucune URL fournie par l'appelant : seuls des identifiants validés partent vers data.gouv.fr.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import answer, db, dpe, live, search



def _conn(db_path) -> sqlite3.Connection:
    return db.connect(Path(db_path), readonly=True)


def _flag(v: str | None) -> bool | None:
    return True if v in ("1", "true", "oui") else None


def api_search(db_path, p: dict) -> dict:
    """p : paramètres de requête simples (q, type, producteur, format, interrogeable, limit, offset)."""
    kind = p.get("type") or "jeux_de_donnees"
    if kind != "tout" and kind not in search.KINDS:
        return {"erreur": f"type inconnu : {kind!r}"}
    try:
        limit = max(1, min(int(p.get("limit") or 12), 50))
        offset = max(0, int(p.get("offset") or 0))
    except ValueError:
        return {"erreur": "limit et offset doivent être des entiers"}
    if kind == "tout":
        limit = min(limit, 6)
    conn = _conn(db_path)
    try:
        res = search.search(conn, (p.get("q") or "")[:200], kind, limit=limit, offset=offset,
                            producteur=(p.get("producteur") or None), format=(p.get("format") or None),
                            interrogeable=_flag(p.get("interrogeable")))
    except ValueError as exc:
        return {"erreur": str(exc)}
    finally:
        conn.close()
    return {"requete": p.get("q") or "", "type": kind, "limit": limit, "offset": offset, "resultats": res}


def api_item(db_path, p: dict) -> dict:
    table = p.get("type") or ""
    ident = (p.get("id") or "")[:200]
    getter = {"datasets": search.get_dataset, "dataservices": search.get_dataservice,
              "organizations": search.get_organization}.get(table)
    if not getter or not ident:
        return {"erreur": "type ou identifiant invalide"}
    conn = _conn(db_path)
    try:
        item = getter(conn, ident)
    finally:
        conn.close()
    return item or {"erreur": "introuvable"}


def api_profile(p: dict) -> dict:
    try:
        return live.tabular_profile(p.get("rid") or "")
    except Exception as exc:  # noqa: BLE001
        return {"erreur": str(exc)[:300]}


def api_rows(p: dict) -> dict:
    """Lignes d'un fichier tabulaire. Filtre optionnel : col + val (contient, insensible à la casse côté API)."""
    try:
        page = max(1, int(p.get("page") or 1))
        kwargs = {"page": page, "page_size": 10}
        if p.get("col") and p.get("val"):
            kwargs["filters"] = {f"{p['col']}__contains": p["val"]}
        return live.tabular_query(p.get("rid") or "", **kwargs)
    except Exception as exc:  # noqa: BLE001
        return {"erreur": str(exc)[:300]}


def api_ask(db_path, p: dict) -> dict:
    """Question libre : intention connue (DPE d'une adresse) ou enquête dans le catalogue (answer.investigate)."""
    q = (p.get("q") or "")[:300]
    conn = _conn(db_path)
    try:
        return answer.repondre(conn, q)
    finally:
        conn.close()
