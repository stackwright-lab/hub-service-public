"""Contrôle des services de la plateforme (API v1, API tabulaire, MCP officiel...), lecture seule."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import yaml

from . import config, net

SERVICES_FILE = config.ROOT / "config" / "services.yaml"


def load_services(path=None) -> list[dict]:
    doc = yaml.safe_load((path or SERVICES_FILE).read_text(encoding="utf-8")) or {}
    return list(doc.get("services") or [])


def check_service(svc: dict, timeout: float = 15.0) -> dict:
    out = {"id": svc["id"], "type": svc["type"], "nom": svc["nom"], "url": svc["url"],
           "categorie": svc.get("categorie") or "Autres sources",
           "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "status": 0, "latency_ms": None, "error": None}
    t0 = time.time()
    try:
        out["status"] = net.request(svc["url"], timeout=timeout, retries=1, max_bytes=200_000).status
    except net.HttpError as exc:
        out["status"] = exc.status if getattr(exc, "status", 0) else 0
        out["error"] = str(exc)[:200]
    except net.UnsafeUrlError as exc:
        out["error"] = str(exc)[:200]
    out["latency_ms"] = int((time.time() - t0) * 1000)
    out["ok"] = 0 < out["status"] < 500
    return out


def check_all(services: list[dict] | None = None) -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor
    items = services if services is not None else load_services()
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(check_service, items))
