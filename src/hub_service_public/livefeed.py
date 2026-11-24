"""Informations en direct pour le tableau de bord : totaux réels du site, derniers jeux publiés, services.

Un seul instantané partagé, mis en cache 30 secondes : plusieurs onglets ne multiplient pas les appels.
Chaque bloc échoue séparément (valeur None + message) : un service en panne n'efface pas le reste.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import config, net, services

TTL = 30.0
ENDPOINTS = {"datasets": "datasets/", "dataservices": "dataservices/", "organizations": "organizations/",
             "reuses": "reuses/", "discussions": "discussions/"}
LATEST_MASK = "data{id,title,page,created_at,last_update,organization{name}},total"

_lock = threading.Lock()
_cache: dict = {"at": 0.0, "value": None}


def _total(name: str):
    try:
        data = net.get_json(f"{config.API_BASE}/{ENDPOINTS[name]}", params={"page_size": 1},
                            headers={"X-Fields": "total"}, timeout=15, retries=1)
        return name, int(data["total"]), None
    except (net.HttpError, net.UnsafeUrlError, KeyError, ValueError, TypeError) as exc:
        return name, None, str(exc)[:160]


def _latest():
    try:
        data = net.get_json(f"{config.API_BASE}/datasets/", params={"page_size": 8, "sort": "-created"},
                            headers={"X-Fields": LATEST_MASK}, timeout=15, retries=1)
        return [{"title": d.get("title"), "page": d.get("page"), "created_at": d.get("created_at"),
                 "organization": (d.get("organization") or {}).get("name") or "Producteur individuel"}
                for d in data.get("data", [])], None
    except (net.HttpError, net.UnsafeUrlError, ValueError, TypeError) as exc:
        return [], str(exc)[:160]


def snapshot(force: bool = False) -> dict:
    with _lock:
        if not force and _cache["value"] and time.time() - _cache["at"] < TTL:
            return _cache["value"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            totals_f = [pool.submit(_total, n) for n in ENDPOINTS]
            latest_f = pool.submit(_latest)
            svc_f = pool.submit(services.check_all)
            totals, errors = {}, {}
            for f in totals_f:
                name, value, err = f.result()
                totals[name] = value
                if err:
                    errors[name] = err
            latest, lerr = latest_f.result()
            svcs = svc_f.result()
        if lerr:
            errors["latest"] = lerr
        value = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "totals": totals,
                 "latest": latest, "services": svcs, "errors": errors}
        _cache.update(at=time.time(), value=value)
        return value
