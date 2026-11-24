"""Contrôle de santé des API du catalogue (lecture seule, un GET par adresse).

    uv run hub-health --sample 50     # échantillon aléatoire d'API ouvertes
    uv run hub-health --all           # toutes les API ouvertes (environ 1 100 hôtes tiers : à faire rarement)

Pour chaque API : la documentation machine répond-elle et est-elle de l'OpenAPI ? l'URL de base
répond-elle (tout code < 500 compte comme « joignable ») ? Les résultats sont enregistrés dans
l'index (table health_checks) et exportés en CSV dans data/health_report.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import yaml

from . import config, db, net


def _is_openapi(body: bytes) -> bool:
    try:
        doc = json.loads(body)
    except ValueError:
        try:
            doc = yaml.safe_load(body.decode("utf-8", errors="replace"))
        except yaml.YAMLError:
            return False
    return isinstance(doc, dict) and ("openapi" in doc or "swagger" in doc)


def check_one(api: dict, timeout: float = 15.0) -> dict:
    result = {
        "dataservice_id": api["id"], "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_status": None, "doc_status": None, "doc_is_openapi": None, "latency_ms": None, "error": None,
    }
    errors = []
    if api.get("base_api_url"):
        t0 = time.time()
        try:
            resp = net.request(api["base_api_url"], timeout=timeout, retries=1, max_bytes=100_000)
            result["base_status"] = resp.status
        except (net.HttpError, net.UnsafeUrlError) as exc:
            result["base_status"] = 0
            errors.append(f"base: {exc}")
        result["latency_ms"] = int((time.time() - t0) * 1000)
    else:
        errors.append("base: URL non renseignée")
    if api.get("machine_documentation_url"):
        try:
            resp = net.request(api["machine_documentation_url"], timeout=timeout, retries=1, max_bytes=8_000_000)
            result["doc_status"] = resp.status
            result["doc_is_openapi"] = int(resp.status < 400 and _is_openapi(resp.body))
        except (net.HttpError, net.UnsafeUrlError) as exc:
            result["doc_status"] = 0
            errors.append(f"doc: {exc}")
    result["error"] = " | ".join(errors)[:400] or None
    return result


def verdict(r: dict) -> str:
    if r["base_status"] is None:
        return "sans_url"
    if r["base_status"] == 0:
        return "injoignable"
    if r["base_status"] >= 500:
        return "erreur_serveur"
    return "joignable"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Teste la joignabilité des API du catalogue")
    ap.add_argument("--sample", type=int, default=50)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--db")
    args = ap.parse_args(argv)

    conn = db.connect(args.db)
    db.init_schema(conn)
    sql = "SELECT * FROM dataservices WHERE access_type = 'open' AND base_api_url != ''"
    if not args.all:
        sql += f" ORDER BY RANDOM() LIMIT {int(args.sample)}"
    apis = [dict(r) for r in conn.execute(sql).fetchall()]
    if not apis:
        print("Aucune API à tester : l'index est-il rempli ? (uv run hub-harvest)", file=sys.stderr)
        return 1

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(check_one, apis))

    for r in results:
        conn.execute(
            "INSERT INTO health_checks(dataservice_id, checked_at, base_status, doc_status, doc_is_openapi, latency_ms, error) "
            "VALUES(:dataservice_id, :checked_at, :base_status, :doc_status, :doc_is_openapi, :latency_ms, :error)", r,
        )
    conn.commit()

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    report = config.DATA_DIR / "health_report.csv"
    by_id = {a["id"]: a for a in apis}
    with report.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["titre", "producteur", "base_api_url", "verdict", "base_status", "doc_status", "doc_openapi", "latence_ms", "erreur"])
        for r in results:
            a = by_id[r["dataservice_id"]]
            w.writerow([a["title"], a["organization_name"], a["base_api_url"], verdict(r), r["base_status"],
                        r["doc_status"], r["doc_is_openapi"], r["latency_ms"], r["error"] or ""])

    summary: dict[str, int] = {}
    for r in results:
        summary[verdict(r)] = summary.get(verdict(r), 0) + 1
    openapi = sum(1 for r in results if r["doc_is_openapi"])
    print(f"{len(results)} API testées : {summary} · documentation OpenAPI valide : {openapi}")
    print(f"Rapport : {report}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
