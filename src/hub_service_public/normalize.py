"""Transformation des objets JSON de l'API data.gouv.fr en lignes de l'index.

Tout est lu de façon défensive (`.get`) : les champs varient d'un objet à l'autre.
Par respect de la vie privée, on ne conserve pas les noms de personnes physiques :
un producteur sans organisation est indexé comme « Producteur individuel ».
"""
from __future__ import annotations

import json

INDIVIDUAL = "Producteur individuel"


def _txt(value, limit: int | None = None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text[:limit] if limit else text


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _list(value) -> list:
    if isinstance(value, dict):  # certains champs sont paginés : {"data": [...]}
        value = value.get("data") or []
    return value if isinstance(value, list) else []


def _tags(obj: dict) -> list[str]:
    return [str(t) for t in _list(obj.get("tags")) if t]


def _org_name(obj: dict) -> str:
    org = obj.get("organization")
    if isinstance(org, dict) and org.get("name"):
        return _txt(org["name"])
    return INDIVIDUAL


def _page(obj: dict) -> str:
    return _txt(obj.get("page") or obj.get("self_web_url"))


def norm_dataset(d: dict, run_id: int):
    """Retourne (ligne, valeurs FTS, lignes de ressources)."""
    spatial = d.get("spatial") or {}
    temporal = d.get("temporal_coverage") or {}
    quality = d.get("quality") or {}
    metrics = d.get("metrics") or {}
    org = d.get("organization") if isinstance(d.get("organization"), dict) else {}

    resources = []
    for r in _list(d.get("resources")):
        extras = r.get("extras") or {}
        tabular = 1 if (extras.get("analysis:parsing:parsing_table") or extras.get("analysis:parsing:parquet_url")) else 0
        resources.append(
            {
                "id": _txt(r.get("id")),
                "dataset_id": _txt(d.get("id")),
                "title": _txt(r.get("title"), 300),
                "description": _txt(r.get("description"), 1000),
                "format": _txt(r.get("format")).lower(),
                "mime": _txt(r.get("mime")),
                "filesize": _int(r.get("filesize")),
                "url": _txt(r.get("url")),
                "latest": _txt(r.get("latest")),
                "type": _txt(r.get("type")),
                "last_modified": _txt(r.get("last_modified")),
                "tabular": tabular,
                "run_id": run_id,
            }
        )
    formats = sorted({r["format"] for r in resources if r["format"]})
    tags = _tags(d)
    zones = _list(spatial.get("zones"))

    row = {
        "id": _txt(d.get("id")),
        "slug": _txt(d.get("slug")),
        "title": _txt(d.get("title"), 500),
        "acronym": _txt(d.get("acronym")),
        "description": _txt(d.get("description"), 4000),
        "organization_id": _txt(org.get("id")),
        "organization_name": _org_name(d),
        "frequency": _txt(d.get("frequency")),
        "license": _txt(d.get("license")),
        "tags": json.dumps(tags, ensure_ascii=False),
        "created_at": _txt(d.get("created_at")),
        "last_modified": _txt(d.get("last_modified")),
        "last_update": _txt(d.get("last_update")),
        "granularity": _txt(spatial.get("granularity")),
        "zones": json.dumps(zones, ensure_ascii=False),
        "temporal_start": _txt(temporal.get("start")),
        "temporal_end": _txt(temporal.get("end")),
        "quality_score": _float(quality.get("score")),
        "page": _page(d),
        "private": 1 if d.get("private") else 0,
        "archived": 1 if d.get("archived") else 0,
        "resource_count": len(resources),
        "tabular_count": sum(r["tabular"] for r in resources),
        "formats": ",".join(formats),
        "views": _int(metrics.get("views")),
        "reuses": _int(metrics.get("reuses")),
        "followers": _int(metrics.get("followers")),
        "run_id": run_id,
    }
    fichiers = " ".join(f"{r['title']} {r['format']}" for r in resources)[:2000]
    fts = {
        "title": row["title"],
        "acronym": row["acronym"],
        "description": row["description"],
        "tags": " ".join(tags),
        "organization": row["organization_name"],
        "fichiers": fichiers,
    }
    return row, fts, resources


def norm_dataservice(d: dict, run_id: int):
    tags = _tags(d)
    row = {
        "id": _txt(d.get("id")),
        "slug": _txt(d.get("slug")),
        "title": _txt(d.get("title"), 500),
        "acronym": _txt(d.get("acronym")),
        "description": _txt(d.get("description"), 4000),
        "organization_name": _org_name(d),
        "base_api_url": _txt(d.get("base_api_url")),
        "machine_documentation_url": _txt(d.get("machine_documentation_url")),
        "technical_documentation_url": _txt(d.get("technical_documentation_url")),
        "business_documentation_url": _txt(d.get("business_documentation_url")),
        "access_type": _txt(d.get("access_type")),
        "authorization_request_url": _txt(d.get("authorization_request_url")),
        "rate_limiting": _txt(d.get("rate_limiting"), 500),
        "availability": _float(d.get("availability")),
        "license": _txt(d.get("license")),
        "tags": json.dumps(tags, ensure_ascii=False),
        "format": _txt(d.get("format")),
        "page": _page(d),
        "created_at": _txt(d.get("created_at")),
        "run_id": run_id,
    }
    fts = {
        "title": row["title"],
        "acronym": row["acronym"],
        "description": row["description"],
        "tags": " ".join(tags),
        "organization": row["organization_name"],
    }
    return row, fts, []


def norm_organization(d: dict, run_id: int):
    metrics = d.get("metrics") or {}
    row = {
        "id": _txt(d.get("id")),
        "slug": _txt(d.get("slug")),
        "name": _txt(d.get("name"), 300),
        "acronym": _txt(d.get("acronym")),
        "description": _txt(d.get("description"), 3000),
        "url": _txt(d.get("url")),
        "page": _page(d),
        "datasets_count": _int(metrics.get("datasets")),
        "dataservices_count": _int(metrics.get("dataservices")),
        "reuses_count": _int(metrics.get("reuses")),
        "followers": _int(metrics.get("followers")),
        "run_id": run_id,
    }
    fts = {"name": row["name"], "acronym": row["acronym"], "description": row["description"]}
    return row, fts, []


def norm_reuse(d: dict, run_id: int):
    tags = _tags(d)
    dataset_ids = [_txt(x.get("id")) for x in _list(d.get("datasets")) if isinstance(x, dict)]
    row = {
        "id": _txt(d.get("id")),
        "slug": _txt(d.get("slug")),
        "title": _txt(d.get("title"), 500),
        "description": _txt(d.get("description"), 3000),
        "type": _txt(d.get("type")),
        "url": _txt(d.get("url")),
        "organization_name": _org_name(d),
        "tags": json.dumps(tags, ensure_ascii=False),
        "dataset_ids": json.dumps(dataset_ids),
        "created_at": _txt(d.get("created_at")),
        "page": _page(d),
        "run_id": run_id,
    }
    fts = {
        "title": row["title"],
        "description": row["description"],
        "tags": " ".join(tags),
        "organization": row["organization_name"],
    }
    return row, fts, []


def norm_discussion(d: dict, run_id: int):
    subject = d.get("subject") if isinstance(d.get("subject"), dict) else {}
    messages = [m for m in _list(d.get("discussion")) if isinstance(m, dict)]
    text = " ".join(_txt(m.get("content")) for m in messages[:20])[:4000]
    row = {
        "id": _txt(d.get("id")),
        "title": _txt(d.get("title"), 500),
        "subject_class": _txt(subject.get("class")),
        "subject_id": _txt(subject.get("id")),
        "created": _txt(d.get("created")),
        "closed": _txt(d.get("closed")),
        "messages_count": len(messages),
        "text": text,
        "run_id": run_id,
    }
    fts = {"title": row["title"], "text": text}
    return row, fts, []
