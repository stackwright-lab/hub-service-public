"""Recherche dans l'index local (plein texte FTS5, insensible aux accents et à la casse)."""
from __future__ import annotations

import json
import re
import sqlite3

KINDS = {
    "jeux_de_donnees": "datasets",
    "api": "dataservices",
    "organisations": "organizations",
    "reutilisations": "reuses",
    "discussions": "discussions",
}

_TOKEN = re.compile(r"\w+", re.UNICODE)
_STOPWORDS = {"de", "du", "des", "la", "le", "les", "un", "une", "et", "en", "au", "aux", "a", "à", "l", "d", "sur", "pour", "par", "dans", "ou"}

_WEIGHTS = {
    "datasets": "10.0, 8.0, 2.0, 5.0, 3.0, 2.0",
    "dataservices": "10.0, 8.0, 2.0, 5.0, 3.0",
    "organizations": "10.0, 8.0, 2.0",
    "reuses": "10.0, 2.0, 5.0, 3.0",
    "discussions": "10.0, 1.0",
}

_SELECT = {
    "datasets": (
        "b.id, b.slug, b.title, b.organization_name, b.frequency, b.license, b.last_update, b.formats, "
        "b.resource_count, b.tabular_count, b.views, b.page, substr(b.description, 1, 240) AS extrait"
    ),
    "dataservices": (
        "b.id, b.slug, b.title, b.organization_name, b.base_api_url, b.access_type, b.rate_limiting, "
        "b.availability, b.page, substr(b.description, 1, 240) AS extrait"
    ),
    "organizations": (
        "b.id, b.slug, b.name, b.acronym, b.datasets_count, b.dataservices_count, b.reuses_count, b.page, "
        "substr(b.description, 1, 240) AS extrait"
    ),
    "reuses": (
        "b.id, b.slug, b.title, b.type, b.organization_name, b.url, b.page, substr(b.description, 1, 240) AS extrait"
    ),
    "discussions": (
        "b.id, b.title, b.subject_class, b.subject_id, b.created, b.closed, b.messages_count, "
        "substr(b.text, 1, 240) AS extrait"
    ),
}

_DEFAULT_ORDER = {
    "datasets": "b.views DESC",
    "dataservices": "b.title",
    "organizations": "b.datasets_count DESC",
    "reuses": "b.created_at DESC",
    "discussions": "b.created DESC",
}


# Poids de la popularité dans le classement : bm25 - poids x ln(1 + indicateur).
# Réglé sur l'index réel (23/11/2026) : à 2.0, « valeurs foncières » met en tête le jeu officiel DVF
# et « dpe logements » les jeux de l'ADEME, au lieu d'articles de blog sans consultation.
_POPULARITY = {"datasets": ("b.views", 2.0), "organizations": ("b.datasets_count", 1.0)}


def fts_match(query: str, op: str = "AND", prefix: bool = True) -> str | None:
    """Transforme une requête libre en expression FTS5 sûre (mots vides retirés).

    prefix=True : chaque mot de 3 lettres ou plus devient un préfixe (« commun » trouve « communes »).
    """
    tokens = [t for t in _TOKEN.findall(query.lower()) if t]
    significant = [t for t in tokens if t not in _STOPWORDS] or tokens
    if not significant:
        return None
    parts = [f'"{t}"*' if prefix and len(t) >= 3 else f'"{t}"' for t in significant]
    return f" {op} ".join(parts)


def _order(kind: str, ranked: bool) -> str:
    if not ranked:
        return _DEFAULT_ORDER[kind]
    order = f"bm25(fts_{kind}, {_WEIGHTS[kind]})"
    if kind in _POPULARITY:
        column, weight = _POPULARITY[kind]
        order += f" - {weight} * ln1p({column})"
    return order


def _rows(conn: sqlite3.Connection, kind: str, match: str | None, filters: dict, limit: int, offset: int):
    base = kind
    where, args = [], []
    if match:
        sql_from = f"fts_{kind} f JOIN {base} b ON b.rowid = f.rowid"
        where.append(f"fts_{kind} MATCH ?")
        args.append(match)
        order = _order(kind, True)
    else:
        sql_from = f"{base} b"
        order = _order(kind, False)

    if filters.get("producteur"):
        col = "name" if kind == "organizations" else "organization_name"
        where.append(f"b.{col} LIKE ?")
        args.append(f"%{filters['producteur']}%")
    if kind == "datasets":
        if filters.get("format"):
            where.append("EXISTS (SELECT 1 FROM resources r WHERE r.dataset_id = b.id AND r.format = ?)")
            args.append(str(filters["format"]).lower())
        if filters.get("interrogeable"):
            where.append("b.tabular_count > 0")
        if filters.get("licence"):
            where.append("b.license = ?")
            args.append(filters["licence"])
    if kind == "dataservices" and filters.get("acces"):
        where.append("b.access_type = ?")
        args.append(filters["acces"])

    sql = f"SELECT {_SELECT[kind]} FROM {sql_from}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order} LIMIT ? OFFSET ?"
    args += [limit, offset]
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def search(
    conn: sqlite3.Connection,
    query: str,
    kind: str = "jeux_de_donnees",
    *,
    limit: int = 10,
    offset: int = 0,
    producteur: str | None = None,
    format: str | None = None,
    interrogeable: bool | None = None,
    licence: str | None = None,
    acces: str | None = None,
) -> dict:
    limit = max(1, min(int(limit), 50))
    filters = {"producteur": producteur, "format": format, "interrogeable": interrogeable, "licence": licence, "acces": acces}
    kinds = list(KINDS.values()) if kind == "tout" else [KINDS.get(kind, kind)]
    unknown = [k for k in kinds if k not in _SELECT]
    if unknown:
        raise ValueError(f"type inconnu : {kind!r} (valeurs : {', '.join(KINDS)}, tout)")

    out: dict = {}
    wanted = limit + max(0, int(offset))
    for k in kinds:
        if not fts_match(query or ""):
            out[k] = _rows(conn, k, None, filters, limit, offset)
            continue
        # 1) mots exacts d'abord ; 2) complété par les préfixes (« insee » avant « inseec ») ;
        # 3) en dernier recours, au moins un des mots au lieu de tous.
        rows: list[dict] = []
        for match in (fts_match(query, prefix=False), fts_match(query)):
            seen = {r["id"] for r in rows}
            rows += [r for r in _rows(conn, k, match, filters, wanted, 0) if r["id"] not in seen]
            if len(rows) >= wanted:
                break
        if not rows and " " in query.strip():
            rows = _rows(conn, k, fts_match(query, "OR"), filters, wanted, 0)
        out[k] = rows[offset : offset + limit]
    return out


def _by_id_or_slug(conn: sqlite3.Connection, table: str, ident: str):
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ? OR slug = ? LIMIT 1", (ident, ident)).fetchone()
    return dict(row) if row else None


def get_dataset(conn: sqlite3.Connection, ident: str) -> dict | None:
    ds = _by_id_or_slug(conn, "datasets", ident)
    if not ds:
        return None
    ds["tags"] = json.loads(ds["tags"] or "[]")
    ds["zones"] = json.loads(ds["zones"] or "[]")
    ds["ressources"] = [
        dict(r)
        for r in conn.execute(
            "SELECT id, title, format, mime, filesize, type, last_modified, tabular, url, latest "
            "FROM resources WHERE dataset_id = ? ORDER BY type, title",
            (ds["id"],),
        ).fetchall()
    ]
    ds["discussions"] = conn.execute(
        "SELECT COUNT(*) FROM discussions WHERE subject_id = ?", (ds["id"],)
    ).fetchone()[0]
    return ds


def get_dataservice(conn: sqlite3.Connection, ident: str) -> dict | None:
    row = _by_id_or_slug(conn, "dataservices", ident)
    if row:
        row["tags"] = json.loads(row["tags"] or "[]")
    return row


def get_organization(conn: sqlite3.Connection, ident: str, top: int = 15) -> dict | None:
    org = _by_id_or_slug(conn, "organizations", ident)
    if not org:
        return None
    org["jeux_de_donnees_populaires"] = [
        dict(r)
        for r in conn.execute(
            "SELECT id, slug, title, last_update, formats, views FROM datasets "
            "WHERE organization_id = ? ORDER BY views DESC LIMIT ?",
            (org["id"], top),
        ).fetchall()
    ]
    org["api"] = [
        dict(r)
        for r in conn.execute(
            "SELECT id, slug, title, access_type FROM dataservices WHERE organization_name = ? LIMIT ?",
            (org["name"], top),
        ).fetchall()
    ]
    return org


def get_resource(conn: sqlite3.Connection, resource_id: str) -> dict | None:
    row = conn.execute(
        "SELECT r.*, d.title AS dataset_title, d.slug AS dataset_slug FROM resources r "
        "LEFT JOIN datasets d ON d.id = r.dataset_id WHERE r.id = ?",
        (resource_id,),
    ).fetchone()
    return dict(row) if row else None
