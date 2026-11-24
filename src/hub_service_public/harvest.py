"""Synchronisation de tout data.gouv.fr vers l'index local.

    uv run hub-harvest                      # tout (première fois : plusieurs minutes)
    uv run hub-harvest --only dataservices  # un seul type de contenu
    uv run hub-harvest --incremental        # jeux de données modifiés depuis le dernier passage
    uv run hub-harvest --resume             # reprendre une synchronisation interrompue
    uv run hub-harvest --fill-gaps          # combler les trous après des pages en échec

Principe : une synchronisation complète marque chaque ligne avec un identifiant de passage ; à la fin,
les lignes d'un passage antérieur (retirées du site) sont purgées. Si une page échoue après
plusieurs tentatives, la purge est sautée pour ne rien supprimer à tort.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from . import config, db, net, normalize


@dataclass(frozen=True)
class Spec:
    name: str
    endpoint: str
    table: str
    norm: Callable
    sort: str | None = None
    incremental_sort: str | None = None


SPECS: dict[str, Spec] = {
    s.name: s
    for s in (
        Spec("dataservices", "dataservices/", "dataservices", normalize.norm_dataservice, sort="created"),
        Spec("organizations", "organizations/", "organizations", normalize.norm_organization, sort="created"),
        Spec("reuses", "reuses/", "reuses", normalize.norm_reuse, sort="created"),
        Spec("datasets", "datasets/", "datasets", normalize.norm_dataset, sort="created", incremental_sort="-last_update"),
        Spec("discussions", "discussions/", "discussions", normalize.norm_discussion, sort="created"),
    )
}


# Certains jeux comptent plus de 15 000 fichiers (≈ 21 Mo de JSON) : la limite par défaut (5 Mo) les tronquait.
MAX_BYTES = 80_000_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def fetch_page(spec: Spec, page: int, page_size: int, sort: str | None) -> dict:
    params: dict = {"page": page, "page_size": page_size}
    if sort:
        params["sort"] = sort
    return net.get_json(f"{config.API_BASE}/{spec.endpoint}", params=params, timeout=90, max_bytes=MAX_BYTES)


def _first_page(spec: Spec, page_size: int, sort: str | None) -> tuple[dict, str | None]:
    """Première page ; si le tri demandé est refusé (400), on réessaie sans tri."""
    try:
        return fetch_page(spec, 1, page_size, sort), sort
    except net.HttpError as exc:
        if exc.status == 400 and sort:
            _log(f"[{spec.name}] tri « {sort} » refusé par l'API, synchronisation sans tri")
            return fetch_page(spec, 1, page_size, None), None
        raise


def store_items(conn, spec: Spec, items: list[dict], run_id: int) -> int:
    n = 0
    for raw in items:
        row, fts, resources = spec.norm(raw, run_id)
        if not row["id"]:
            continue
        db.upsert(conn, spec.table, row, fts)
        if spec.table == "datasets":
            db.replace_resources(conn, row["id"], [r for r in resources if r["id"]])
        n += 1
    return n


def _newer_than(item: dict, since: str) -> bool:
    stamp = max(str(item.get("last_update") or ""), str(item.get("last_modified") or ""))
    return stamp >= since or not stamp


def run_incremental(conn, spec: Spec, *, run_id: int, page_size: int, delay: float, max_pages: int | None) -> dict:
    since = db.get_meta(conn, f"harvest:{spec.name}", {}).get("started_at")
    if not since:
        raise SystemExit(f"Aucune synchronisation complète de « {spec.name} » : lance d'abord un passage complet.")
    started = _now()
    stored = page = 0
    while True:
        page += 1
        if max_pages and page > max_pages:
            break
        data = fetch_page(spec, page, page_size, spec.incremental_sort)
        items = data.get("data") or []
        if not items:
            break
        fresh = [i for i in items if _newer_than(i, since)]
        stored += store_items(conn, spec, fresh, run_id)
        conn.commit()
        _log(f"[{spec.name}] incrémental page {page} : {len(fresh)}/{len(items)} récents")
        if len(fresh) < len(items):  # le tri est décroissant : on a atteint des éléments anciens
            break
        time.sleep(delay)
    meta = db.get_meta(conn, f"harvest:{spec.name}", {})
    meta.update({"last_incremental_at": started, "last_incremental_count": stored})
    db.set_meta(conn, f"harvest:{spec.name}", meta)
    conn.commit()
    return {"stored": stored, "failed_pages": []}


def run_full(
    conn,
    spec: Spec,
    *,
    run_id: int,
    page_size: int,
    workers: int,
    delay: float,
    resume: bool,
    max_pages: int | None,
) -> dict:
    started = _now()
    first, sort = _first_page(spec, page_size, spec.sort)
    total = int(first.get("total") or 0)
    pages = max(1, math.ceil(total / page_size)) if total else 1
    if max_pages:
        pages = min(pages, max_pages)

    start = 1
    progress = db.get_meta(conn, f"progress:{spec.name}")
    if resume and progress and progress.get("run_id") == run_id:
        start = int(progress["next_page"])
        _log(f"[{spec.name}] reprise à la page {start}/{pages}")

    stored = 0
    failed: list[int] = []
    t0 = time.time()
    done_pages = 0

    if start == 1:
        stored += store_items(conn, spec, first.get("data") or [], run_id)
        conn.commit()
        start = 2

    todo = list(range(start, pages + 1))
    chunk_size = max(1, workers * 2)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for i in range(0, len(todo), chunk_size):
            chunk = todo[i : i + chunk_size]
            futures = {p: pool.submit(fetch_page, spec, p, page_size, sort) for p in chunk}
            for p in chunk:
                try:
                    data = futures[p].result()
                except Exception as exc:  # noqa: BLE001 - on continue, la page sera listée en échec
                    failed.append(p)
                    _log(f"[{spec.name}] page {p} en échec : {exc}")
                    continue
                stored += store_items(conn, spec, data.get("data") or [], run_id)
            done_pages += len(chunk)
            db.set_meta(conn, f"progress:{spec.name}", {"run_id": run_id, "next_page": chunk[-1] + 1})
            conn.commit()
            elapsed = max(time.time() - t0, 1e-6)
            rate = done_pages / elapsed
            remaining = (len(todo) - done_pages) / rate if rate else 0
            _log(f"[{spec.name}] page {chunk[-1]}/{pages} · {stored} éléments · ~{int(remaining)} s restantes")
            time.sleep(delay)

    db.set_meta(conn, f"failed:{spec.name}", failed)
    if failed:
        _log(
            f"[{spec.name}] {len(failed)} page(s) en échec : {failed}. "
            f"Pour combler les trous : uv run hub-harvest --only {spec.name} --fill-gaps"
        )
    complete = not failed and not max_pages
    removed = 0
    if complete:
        removed = db.purge_stale(conn, spec.table, run_id)
        db.set_meta(
            conn,
            f"harvest:{spec.name}",
            {"started_at": started, "finished_at": _now(), "total_reported": total, "stored": stored, "run_id": run_id, "purged": removed},
        )
        db.set_meta(conn, f"progress:{spec.name}", None)
    conn.commit()
    return {"stored": stored, "failed_pages": failed, "purged": removed, "total": total, "complete": complete}


def fetch_ids_page(spec: Spec, page: int, page_size: int, sort: str | None) -> dict:
    """Page allégée : l'en-tête X-Fields ne demande que les identifiants (≈ 200 fois moins de données)."""
    params: dict = {"page": page, "page_size": page_size}
    if sort:
        params["sort"] = sort
    return net.get_json(
        f"{config.API_BASE}/{spec.endpoint}", params=params,
        headers={"X-Fields": "data{id},total,page,page_size"}, timeout=60,
    )


def fetch_one(spec: Spec, ident: str) -> dict:
    return net.get_json(f"{config.API_BASE}/{spec.endpoint}{ident}/", timeout=90, max_bytes=MAX_BYTES)


def run_fill_gaps(conn, spec: Spec, *, run_id: int, page_size: int, workers: int, delay: float) -> dict:
    """Compare les identifiants du site à l'index : télécharge les manquants, retire les disparus.

    Les lignes ajoutées gardent l'identifiant de passage en cours, pour ne pas être purgées ensuite.
    Rien n'est supprimé si l'inventaire des identifiants du site est incomplet.
    """
    first = fetch_ids_page(spec, 1, page_size, spec.sort)
    total = int(first.get("total") or 0)
    pages = max(1, math.ceil(total / page_size)) if total else 1
    live: set[str] = {i["id"] for i in first.get("data") or [] if i.get("id")}
    scan_failed: list[int] = []
    todo = list(range(2, pages + 1))
    chunk_size = max(1, workers * 2)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for i in range(0, len(todo), chunk_size):
            chunk = todo[i : i + chunk_size]
            futures = {p: pool.submit(fetch_ids_page, spec, p, page_size, spec.sort) for p in chunk}
            for p in chunk:
                try:
                    live.update(x["id"] for x in futures[p].result().get("data") or [] if x.get("id"))
                except Exception as exc:  # noqa: BLE001
                    scan_failed.append(p)
                    _log(f"[{spec.name}] inventaire : page {p} en échec : {exc}")
            time.sleep(delay)
    _log(f"[{spec.name}] inventaire du site : {len(live)} identifiants sur {total} annoncés")

    known = {r[0] for r in conn.execute(f"SELECT id FROM {spec.table}")}
    missing = sorted(live - known)
    gone = sorted(known - live) if not scan_failed else []
    _log(f"[{spec.name}] à télécharger : {len(missing)} · disparus du site : {len(gone)}")

    stored, failed_ids = 0, []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for i in range(0, len(missing), chunk_size * 4):
            chunk = missing[i : i + chunk_size * 4]
            futures = {ident: pool.submit(fetch_one, spec, ident) for ident in chunk}
            for ident in chunk:
                try:
                    stored += store_items(conn, spec, [futures[ident].result()], run_id)
                except Exception as exc:  # noqa: BLE001
                    failed_ids.append(ident)
                    _log(f"[{spec.name}] {ident} en échec : {exc}")
            conn.commit()
            _log(f"[{spec.name}] {min(i + len(chunk), len(missing))}/{len(missing)} téléchargés")
            time.sleep(delay)

    removed = db.delete_ids(conn, spec.table, gone) if gone else 0
    complete = not scan_failed and not failed_ids
    db.set_meta(conn, f"failed:{spec.name}", {"pages_inventaire": scan_failed, "ids": failed_ids})
    if complete:
        # point de départ du mode incrémental = début de la synchronisation initiale (run_id = horodatage)
        started = datetime.fromtimestamp(run_id, timezone.utc).isoformat(timespec="seconds") if run_id else _now()
        db.set_meta(
            conn, f"harvest:{spec.name}",
            {"started_at": started, "finished_at": _now(), "total_reported": total, "mode": "fill-gaps",
             "stored": conn.execute(f"SELECT COUNT(*) FROM {spec.table}").fetchone()[0], "run_id": run_id, "purged": removed},
        )
        db.set_meta(conn, f"progress:{spec.name}", None)
    conn.commit()
    return {"stored": stored, "missing": len(missing), "removed": removed, "failed_ids": failed_ids,
            "failed_pages": scan_failed, "complete": complete, "total": total}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Synchronise data.gouv.fr vers l'index local")
    ap.add_argument("--only", help=f"types séparés par des virgules parmi : {', '.join(SPECS)}")
    ap.add_argument("--incremental", action="store_true", help="jeux de données modifiés depuis le dernier passage")
    ap.add_argument("--resume", action="store_true", help="reprendre une synchronisation interrompue")
    ap.add_argument("--fill-gaps", action="store_true",
                    help="comparer aux identifiants du site : télécharger les manquants, retirer les disparus (défaut : datasets)")
    ap.add_argument("--workers", type=int, default=3, help="requêtes en parallèle (défaut 3, restez raisonnable)")
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--delay", type=float, default=0.5, help="pause en secondes entre deux lots de requêtes")
    ap.add_argument("--max-pages", type=int, help="limiter le nombre de pages (essai rapide ; désactive la purge)")
    ap.add_argument("--db", help="chemin de la base SQLite")
    args = ap.parse_args(argv)

    names = [n.strip() for n in args.only.split(",")] if args.only else (["datasets"] if args.fill_gaps else list(SPECS))
    unknown = [n for n in names if n not in SPECS]
    if unknown:
        ap.error(f"types inconnus : {', '.join(unknown)}")

    conn = db.connect(args.db)
    db.init_schema(conn)

    if args.incremental or args.fill_gaps:
        run_id = int(db.get_meta(conn, "run_id_current", 0) or 0)
    elif args.resume and db.get_meta(conn, "run_id_current"):
        run_id = int(db.get_meta(conn, "run_id_current"))
    else:
        run_id = int(time.time())
        db.set_meta(conn, "run_id_current", run_id)
        conn.commit()

    exit_code = 0
    for name in names:
        spec = SPECS[name]
        t0 = time.time()
        try:
            if args.fill_gaps:
                res = run_fill_gaps(conn, spec, run_id=run_id, page_size=args.page_size, workers=args.workers, delay=args.delay)
            elif args.incremental and spec.incremental_sort:
                res = run_incremental(conn, spec, run_id=run_id, page_size=args.page_size, delay=args.delay, max_pages=args.max_pages)
            else:
                res = run_full(
                    conn, spec, run_id=run_id, page_size=args.page_size, workers=args.workers,
                    delay=args.delay, resume=args.resume, max_pages=args.max_pages,
                )
        except (net.HttpError, net.UnsafeUrlError) as exc:
            _log(f"[{name}] ÉCHEC : {exc}")
            exit_code = 1
            continue
        if res.get("failed_pages") or res.get("failed_ids"):
            exit_code = 1
        _log(f"[{name}] terminé en {int(time.time() - t0)} s : {res}")

    _log(f"Index : {db.counts(conn)}")
    conn.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
