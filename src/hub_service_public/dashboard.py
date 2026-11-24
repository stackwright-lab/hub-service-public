"""Tableau de bord de santé : un fichier HTML autonome généré depuis l'index local.

    uv run hub-dashboard                 # lit l'index, écrit data/dashboard.html
    uv run hub-dashboard --live          # teste d'abord les services (API, MCP) puis génère

Aucun appel réseau sans --live. Les indicateurs sont calculés sur l'index : ils décrivent la santé
du catalogue tel que synchronisé (fraîcheur, complétude, activité), pas le contenu des fichiers.
"""
from __future__ import annotations

import argparse
import html
import json
import secrets
import sys
import threading
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config, dashboard_ui, db, explorer, livefeed, services

# Périodicité attendue en jours (identifiants officiels data.gouv.fr). Absent = aucun engagement de mise à jour.
PERIOD_DAYS = {
    "continuous": 1, "severalTimesADay": 1, "daily": 1, "threeTimesAWeek": 3.5, "weekly": 7,
    "biweekly": 14, "threeTimesAMonth": 10, "monthly": 31, "bimonthly": 61, "quarterly": 92,
    "threeTimesAYear": 122, "semiannual": 183, "annual": 366, "biennial": 731, "triennial": 1096,
    "quinquennial": 1826,
}
FRESH_STATES = ["a_jour", "en_retard", "perime", "sans_engagement"]
FRESH_LABELS = {"a_jour": "À jour", "en_retard": "En retard", "perime": "Périmé", "sans_engagement": "Sans engagement"}
NO_LICENSE = {"", "notspecified", "not-specified", None}


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d if 1990 <= d.year <= datetime.now(timezone.utc).year + 1 else None


def freshness(frequency: str | None, last_update: str | None, now: datetime) -> str:
    period = PERIOD_DAYS.get(frequency or "")
    if period is None:
        return "sans_engagement"
    d = _parse(last_update)
    if d is None:
        return "perime"
    ratio = (now - d).total_seconds() / 86400 / period
    return "a_jour" if ratio <= 1.5 else "en_retard" if ratio <= 3 else "perime"


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}".replace(".", ",") if d else "0"


def collect(conn, now: datetime | None = None, service_checks: list[dict] | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    out: dict = {"generated_at": now.isoformat(timespec="seconds"), "counts": db.counts(conn)}

    # ---- Jeux de données
    fresh = dict.fromkeys(FRESH_STATES, 0)
    late_rows: list[list] = []
    by_freq: dict[str, dict] = {}
    flags = dict(no_license=0, short_desc=0, no_tags=0, no_resource=0, no_org=0, archived=0, total=0)
    by_org: dict[str, dict] = {}
    for r in conn.execute(
        "SELECT id, title, organization_name, frequency, last_update, license, description, tags, "
        "resource_count, archived, views FROM datasets WHERE COALESCE(private,0)=0"
    ):
        flags["total"] += 1
        st = freshness(r["frequency"], r["last_update"], now)
        fresh[st] += 1
        bf = by_freq.setdefault(r["frequency"] or "unknown", dict.fromkeys(FRESH_STATES, 0))
        bf[st] += 1
        flags["no_license"] += r["license"] in NO_LICENSE
        flags["short_desc"] += len(r["description"] or "") < 30
        flags["no_tags"] += (r["tags"] or "").strip() in ("", "[]")
        flags["no_resource"] += not (r["resource_count"] or 0)
        flags["no_org"] += not r["organization_name"]
        flags["archived"] += bool(r["archived"])
        o = by_org.setdefault(r["organization_name"] or "(sans organisation)", {"n": 0, "bad": 0})
        o["n"] += 1
        o["bad"] += st in ("en_retard", "perime")
        if st in ("en_retard", "perime"):
            late_rows.append([r["title"], r["organization_name"], r["frequency"], (r["last_update"] or "")[:10], st, r["views"] or 0])
    late_rows.sort(key=lambda x: -x[5])
    for v in by_freq.values():
        v["total"] = sum(v.values())
    out["datasets"] = {"fresh": fresh, "flags": flags, "by_freq": by_freq, "late_rows": late_rows[:300]}
    out["orgs_late"] = [list(t) for t in sorted(
        ((k, v["bad"], v["n"]) for k, v in by_org.items() if v["n"] >= 20 and v["bad"]),
        key=lambda t: (-t[1] / t[2], -t[1]),
    )[:12]]
    fmt: dict[str, int] = {}
    for (f,) in conn.execute("SELECT format FROM resources"):
        k = (f or "inconnu").strip().lower() or "inconnu"
        fmt[k] = fmt.get(k, 0) + 1
    tab = conn.execute("SELECT COUNT(*), SUM(tabular) FROM resources").fetchone()
    out["resources"] = {"total": tab[0], "tabular": tab[1] or 0,
                        "formats": [list(t) for t in sorted(fmt.items(), key=lambda t: -t[1])[:8]]}

    # ---- API (dataservices)
    a = conn.execute(
        "SELECT COUNT(*), SUM(access_type='open'), SUM(access_type='open_with_account'), SUM(access_type='restricted'), "
        "SUM(COALESCE(base_api_url,'')=''), SUM(COALESCE(machine_documentation_url,'')=''), "
        "SUM(COALESCE(technical_documentation_url,'')=''), SUM(COALESCE(rate_limiting,'')='') FROM dataservices"
    ).fetchone()
    api = dict(zip(["total", "open", "account", "restricted", "no_base", "no_machine_doc", "no_tech_doc", "no_rate"],
                   [x or 0 for x in a]))
    hc = conn.execute(
        "SELECT h.* FROM health_checks h JOIN (SELECT dataservice_id, MAX(checked_at) m FROM health_checks "
        "GROUP BY dataservice_id) x ON x.dataservice_id=h.dataservice_id AND x.m=h.checked_at"
    ).fetchall()
    live = {"tested": len(hc), "reachable": 0, "server_error": 0, "down": 0, "openapi": 0, "lat": []}
    for h in hc:
        bs = h["base_status"]
        if bs is None or bs == 0:
            live["down"] += 1
        elif bs >= 500:
            live["server_error"] += 1
        else:
            live["reachable"] += 1
        live["openapi"] += bool(h["doc_is_openapi"])
        if h["latency_ms"] is not None:
            live["lat"].append(h["latency_ms"])
    lat = sorted(live.pop("lat"))
    live["median_ms"] = lat[len(lat) // 2] if lat else None
    live["last_check"] = max((h["checked_at"] for h in hc), default=None)
    api["live"] = live
    out["apis"] = api

    # ---- Organisations
    o = conn.execute(
        "SELECT COUNT(*), SUM(datasets_count=0 AND dataservices_count=0), SUM(COALESCE(description,'')=''), "
        "SUM(COALESCE(url,'')='') FROM organizations").fetchone()
    out["orgs"] = dict(zip(["total", "empty", "no_desc", "no_url"], [x or 0 for x in o]))

    # ---- Réutilisations
    r = conn.execute(
        "SELECT COUNT(*), SUM(COALESCE(url,'')=''), SUM(COALESCE(dataset_ids,'') IN ('','[]')), "
        "SUM(COALESCE(description,'')='') FROM reuses").fetchone()
    out["reuses"] = dict(zip(["total", "no_url", "no_dataset", "no_desc"], [x or 0 for x in r]))
    out["reuse_types"] = conn.execute(
        "SELECT COALESCE(type,'autre') t, COUNT(*) FROM reuses GROUP BY t ORDER BY 2 DESC LIMIT 6").fetchall()
    out["reuse_types"] = [[a, b] for a, b in out["reuse_types"]]

    # ---- Discussions
    cutoff = now.timestamp() - 30 * 86400
    dtot = dopen = dstale = 0
    for d in conn.execute("SELECT created, closed, messages_count FROM discussions"):
        dtot += 1
        if not d["closed"]:
            dopen += 1
            c = _parse(d["created"])
            if (d["messages_count"] or 0) <= 1 and c and c.timestamp() < cutoff:
                dstale += 1
    out["discussions"] = {"total": dtot, "open": dopen, "unanswered_30d": dstale}
    out["services"] = service_checks or db.get_meta(conn, "service_checks", []) or []
    out["services_at"] = db.get_meta(conn, "service_checks_at")
    out["index_age"] = db.get_meta(conn, "last_harvest_at") if hasattr(db, "get_meta") else None
    return out


def render(d: dict, token: str | None = None) -> str:
    """Page HTML autonome. Avec un jeton (mode serveur) : direct, bouton de synchronisation."""
    return dashboard_ui.build(d, token)


class UpdateJob:
    """Une seule mise à jour à la fois : synchronisation incrémentale, échantillon d'API, services, puis régénération."""

    def __init__(self, db_path, sample: int = 60):
        self.db_path, self.sample = db_path, sample
        self.lock = threading.Lock()
        self.state = {"running": False, "step": "", "error": None, "done_at": None}

    def snapshot(self) -> dict:
        return dict(self.state)

    def start(self) -> bool:
        if not self.lock.acquire(blocking=False):
            return False
        self.state.update(running=True, step="démarrage", error=None)
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _step(self, label: str) -> None:
        self.state["step"] = label

    def _run(self) -> None:
        try:
            from . import harvest, health
            self._step("synchronisation incrémentale du catalogue")
            harvest.main(["--incremental", "--db", str(self.db_path)])
            self._step(f"contrôle de {self.sample} API")
            health.main(["--sample", str(self.sample), "--db", str(self.db_path)])
            self._step("contrôle des services")
            checks = services.check_all()
            conn = db.connect(self.db_path)
            db.set_meta(conn, "service_checks", checks)
            db.set_meta(conn, "service_checks_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
            conn.commit()
            conn.close()
            self.state["done_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        except BaseException as exc:  # noqa: BLE001 : on remonte l'erreur à l'interface
            self.state["error"] = (str(exc) or type(exc).__name__)[:300]
        finally:
            self.state.update(running=False, step="")
            self.lock.release()


def make_handler(db_path, token: str, job: UpdateJob, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silencieux
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in allowed_hosts  # contre le DNS rebinding

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, b'{"error":"hote refuse"}')
            url = urllib.parse.urlsplit(self.path)
            if url.path.startswith("/api/") and url.path != "/api/live":
                q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
                route = {"/api/search": lambda: explorer.api_search(db_path, q),
                         "/api/ask": lambda: explorer.api_ask(db_path, q),
                         "/api/item": lambda: explorer.api_item(db_path, q),
                         "/api/profile": lambda: explorer.api_profile(q),
                         "/api/rows": lambda: explorer.api_rows(q)}.get(url.path)
                if not route:
                    return self._send(404, b'{"erreur":"introuvable"}')
                return self._send(200, json.dumps(route(), ensure_ascii=False, default=str).encode())
            if url.path == "/api/live":
                return self._send(200, json.dumps(livefeed.snapshot(), ensure_ascii=False).encode())
            if url.path == "/status":
                return self._send(200, json.dumps(job.snapshot()).encode())
            if url.path in ("/", "/index.html"):
                conn = db.connect(db_path, readonly=True)
                try:
                    page = render(collect(conn), token=token)
                finally:
                    conn.close()
                return self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            self._send(404, b'{"error":"introuvable"}')

        def do_POST(self):
            if not self._host_ok() or self.path != "/update":
                return self._send(403, b'{"error":"refuse"}')
            if not secrets.compare_digest(self.headers.get("X-Token", ""), token):
                return self._send(403, b'{"error":"jeton invalide"}')
            ok = job.start()
            self._send(202 if ok else 409, json.dumps({"started": ok}).encode())

    return Handler


def serve(db_path, port: int = 8765) -> None:
    token = secrets.token_urlsafe(24)
    job = UpdateJob(db_path)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(db_path, token, job, port))
    print(f"Tableau de bord : http://127.0.0.1:{port}/  (Ctrl+C pour arrêter)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Génère le tableau de bord de santé (HTML autonome)")
    ap.add_argument("--db")
    ap.add_argument("--out", default=str(config.DATA_DIR / "dashboard.html"))
    ap.add_argument("--live", action="store_true", help="teste d'abord les services (API, MCP) : accès réseau")
    ap.add_argument("--serve", action="store_true", help="serveur local avec bouton « Mettre à jour »")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    if not db.exists(args.db):
        print("Index absent : lancer d'abord uv run hub-harvest", file=sys.stderr)
        return 1
    if args.serve:
        serve(Path(args.db or config.DB_PATH), args.port)
        return 0
    conn = db.connect(args.db, readonly=True)
    checks = services.check_all() if args.live else None
    page = render(collect(conn, service_checks=checks))
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    print(f"Tableau de bord écrit : {path} ({len(page) // 1024} Ko)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
