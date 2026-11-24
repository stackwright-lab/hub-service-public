import io
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from hub_service_public import server, web


@pytest.fixture
def site(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: None)
    port = srv.server_address[1]
    srv.RequestHandlerClass = web.make_handler("tok", port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield port
    srv.shutdown()
    srv.server_close()


def req(port, path, body=None, token="tok", host=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Token"] = token
    if host:
        headers["Host"] = host
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_page_injects_local_adapter(site):
    code, html = req(site, "/")
    assert code == 200 and 'window.HUB_LOCAL={token:"tok"}' in html and '<script src="/local.js"></script>' in html
    assert html.index("/local.js") < html.index("<script>\n{")
    code, js = req(site, "/local.js")
    assert code == 200 and "window.claude" in js


def test_tool_calls_are_whitelisted_and_token_protected(site, monkeypatch):
    monkeypatch.setattr(server, "rechercher", lambda **kw: {"ok": kw})
    code, body = req(site, "/api/tool/rechercher", {"requete": "dpe"})
    assert code == 200 and json.loads(body)["payload"] == {"ok": {"requete": "dpe"}}
    assert req(site, "/api/tool/rechercher", {"requete": "x"}, token="mauvais")[0] == 403
    assert req(site, "/api/tool/main", {})[0] == 404
    assert req(site, "/api/tool/rechercher", {"requete": "x"}, host="evil.example")[0] == 403
    assert req(site, "/api/tool/rechercher", {"inconnu": 1})[0] in (400, 200)


def test_llm_disabled_without_key(site, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    code, body = req(site, "/api/llm/status", {})
    assert code == 200 and json.loads(body)["ia"] is False
    assert req(site, "/api/llm", {"messages": []})[0] == 501


def test_call_anthropic_sends_key_only_to_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    seen = {}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["key"] = request.get_header("X-api-key")
        seen["body"] = json.loads(request.data)
        return Resp(json.dumps({"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"}).encode())

    out = web.call_anthropic([{"role": "user", "content": "q"}], [{"name": "repondre", "input_schema": {"type": "object"}}, {"name": "rm_rf"}], opener=opener)
    assert out == {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"}
    assert seen["url"] == web.ANTHROPIC_URL and seen["key"] == "sk-test"
    assert [t["name"] for t in seen["body"]["tools"]] == ["repondre"]
