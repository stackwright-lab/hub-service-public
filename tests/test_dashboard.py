from datetime import datetime, timezone

from hub_service_public import dashboard

NOW = datetime(2026, 11, 23, tzinfo=timezone.utc)


def test_freshness_classes():
    assert dashboard.freshness("daily", "2026-11-22T00:00:00+00:00", NOW) == "a_jour"
    assert dashboard.freshness("daily", "2026-11-20T00:00:00+00:00", NOW) == "en_retard"
    assert dashboard.freshness("daily", "2026-01-01T00:00:00+00:00", NOW) == "perime"
    assert dashboard.freshness("annual", "2026-03-01T00:00:00+00:00", NOW) == "a_jour"
    assert dashboard.freshness("unknown", "2026-01-01T00:00:00+00:00", NOW) == "sans_engagement"
    assert dashboard.freshness("daily", None, NOW) == "perime"
    assert dashboard.freshness("daily", "0025-10-02T00:00:00+00:00", NOW) == "perime"


def test_collect_and_render(populated):
    data = dashboard.collect(populated, now=NOW, service_checks=[
        {"type": "MCP", "nom": "MCP </script><b>", "status": 405, "latency_ms": 12, "ok": True}])
    assert data["counts"]["datasets"] > 0
    assert sum(data["datasets"]["fresh"].values()) == data["datasets"]["flags"]["total"]
    page = dashboard.render(data)
    assert page.startswith("<!doctype html>") and "santé des données" in page.lower()
    assert "MCP <\\/script><b>" in page
    assert "</script><" not in page.split('id="data">', 1)[1].split("</script>", 1)[0]  # JSON inerte


def test_main_writes_file(tmp_path, populated):
    from hub_service_public import config
    import sqlite3
    out = tmp_path / "d.html"
    populated.commit()
    path = populated.execute("PRAGMA database_list").fetchone()[2]
    assert dashboard.main(["--db", path, "--out", str(out)]) == 0
    txt = out.read_text(encoding="utf-8")
    assert "p-overview" in txt and 'id="data"' in txt


# ---- serveur local et bouton « Mettre à jour »
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest


@pytest.fixture
def server(tmp_path, populated, monkeypatch):
    populated.commit()
    path = populated.execute("PRAGMA database_list").fetchone()[2]
    ran = []
    monkeypatch.setattr(dashboard.UpdateJob, "_run", lambda self: (ran.append(1), self.state.update(running=False), self.lock.release()))
    job = dashboard.UpdateJob(path)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: None)
    port = srv.server_address[1]
    srv.RequestHandlerClass = dashboard.make_handler(path, "tok", job, port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield port, ran
    srv.shutdown()
    srv.server_close()


def _req(port, path, method="GET", headers=None):
    r = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method, headers=headers or {}, data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_served_page_has_button_and_static_page_does_not(server, populated):
    port, _ = server
    code, body = _req(port, "/")
    assert code == 200 and "TOKEN=\"tok\"" in body
    assert "TOKEN=null" in dashboard.render(dashboard.collect(populated, now=NOW))


def test_update_requires_token_and_runs_once(server):
    port, ran = server
    assert _req(port, "/update", "POST")[0] == 403
    assert _req(port, "/update", "POST", {"X-Token": "mauvais"})[0] == 403
    code, body = _req(port, "/update", "POST", {"X-Token": "tok"})
    assert code == 202 and json.loads(body)["started"] is True
    assert ran == [1]


def test_bad_host_refused(server):
    port, _ = server
    code, _ = _req(port, "/status", headers={"Host": "evil.example"})
    assert code == 403


def test_live_endpoint(server, monkeypatch):
    port, _ = server
    from hub_service_public import livefeed
    monkeypatch.setattr(livefeed, "snapshot", lambda force=False: {"at": "x", "totals": {"datasets": 5}, "latest": [], "services": [], "errors": {}})
    code, body = _req(port, "/api/live")
    assert code == 200 and json.loads(body)["totals"]["datasets"] == 5


def test_search_routes_over_http(server):
    port, _ = server
    code, body = _req(port, "/api/search?q=jeu&type=jeux_de_donnees&limit=2")
    assert code == 200 and len(json.loads(body)["resultats"]["datasets"]) == 2
    assert _req(port, "/api/inconnu")[0] == 404
    assert _req(port, "/api/search?q=x", headers={"Host": "evil.example"})[0] == 403
