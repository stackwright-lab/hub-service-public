"""Page web locale du hub : questions, santé des données et état des sources, dans le navigateur.

    uv run hub-web              # ouvre http://127.0.0.1:8765/ dans le navigateur
    uv run hub-web --port 8766 --no-browser

La page est la même que celle publiée dans l'application Claude (interface/index.html). Ici, un petit
adaptateur (interface/local.js) remplace l'application : les outils du hub sont appelés directement en
local, et les réponses rédigées passent par l'API Anthropic si la variable ANTHROPIC_API_KEY est définie
(fichier .env). Sans clé, la page reste utilisable : elle présente les pistes sourcées trouvées par le hub.

Sécurité : écoute uniquement sur 127.0.0.1, refuse les autres noms d'hôte (DNS rebinding), exige un jeton
tiré à chaque lancement pour tout appel, n'expose qu'une liste fermée d'outils, et la clé d'API ne quitte
jamais ce processus (seul api.anthropic.com la reçoit).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config, server

INTERFACE_DIR = config.ROOT / "interface"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_BODY = 2_000_000

TOOLS = {
    "disponibilite_sources", "sante_des_donnees", "synchroniser_index", "repondre", "dpe_par_adresse", "rechercher",
    "fiche_jeu_de_donnees", "fiche_api", "fiche_organisation", "profil_fichier", "interroger_fichier",
    "documentation_api", "appeler_api",
}


def ai_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def call_tool(name: str, args: dict) -> object:
    if name not in TOOLS:
        raise KeyError(name)
    fn = getattr(server, name)
    return fn(**(args or {}))


def call_anthropic(messages: list, tools: list, opener=urllib.request.urlopen) -> dict:
    body = {
        "model": os.environ.get("HUB_CLAUDE_MODEL", DEFAULT_MODEL),
        "max_tokens": int(os.environ.get("HUB_CLAUDE_MAX_TOKENS", "4096")),
        "messages": messages,
        "tools": [{"name": t["name"], "description": t.get("description", ""), "input_schema": t.get("input_schema") or {"type": "object"}}
                  for t in tools if t.get("name") in TOOLS],
    }
    req = urllib.request.Request(ANTHROPIC_URL, data=json.dumps(body).encode(), method="POST", headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with opener(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        return {"error": f"API Anthropic : HTTP {exc.code} {detail}"}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"error": f"API Anthropic injoignable : {exc}"}
    return {"content": data.get("content", []), "stop_reason": data.get("stop_reason")}


def page_html(token: str) -> str:
    html = (INTERFACE_DIR / "index.html").read_text(encoding="utf-8")
    boot = f'<script>window.HUB_LOCAL={{token:{json.dumps(token)}}};</script>\n<script src="/local.js"></script>\n'
    return html.replace("<script>\n{", boot + "<script>\n{", 1)


def make_handler(token: str, port: int):
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"))

        def do_GET(self):
            if self.headers.get("Host", "") not in hosts:
                return self._json(403, {"code": "forbidden", "message": "hôte refusé"})
            if self.path in ("/", "/index.html"):
                return self._send(200, page_html(token).encode("utf-8"), "text/html; charset=utf-8")
            if self.path == "/local.js":
                return self._send(200, (INTERFACE_DIR / "local.js").read_bytes(), "text/javascript; charset=utf-8")
            self._json(404, {"code": "not_found", "message": "introuvable"})

        def do_POST(self):
            if self.headers.get("Host", "") not in hosts:
                return self._json(403, {"code": "forbidden", "message": "hôte refusé"})
            if not secrets.compare_digest(self.headers.get("X-Token", ""), token):
                return self._json(403, {"code": "forbidden", "message": "jeton invalide"})
            try:
                size = int(self.headers.get("Content-Length") or 0)
                if size > MAX_BODY:
                    return self._json(413, {"code": "bad_request", "message": "requête trop grosse"})
                payload = json.loads(self.rfile.read(size) or b"{}")
            except (ValueError, json.JSONDecodeError):
                return self._json(400, {"code": "bad_request", "message": "JSON invalide"})
            if self.path == "/api/llm/status":
                return self._json(200, {"ia": ai_enabled(), "modele": os.environ.get("HUB_CLAUDE_MODEL", DEFAULT_MODEL)})
            if self.path == "/api/llm":
                if not ai_enabled():
                    return self._json(501, {"code": "not_granted", "message": "aucune clé ANTHROPIC_API_KEY"})
                return self._json(200, call_anthropic(payload.get("messages") or [], payload.get("tools") or []))
            if self.path.startswith("/api/tool/"):
                name = self.path.rsplit("/", 1)[-1]
                if name not in TOOLS:
                    return self._json(404, {"code": "not_in_manifest", "message": f"outil inconnu : {name}"})
                try:
                    return self._json(200, {"payload": call_tool(name, payload if isinstance(payload, dict) else {})})
                except TypeError as exc:
                    return self._json(400, {"code": "bad_request", "message": str(exc)[:300]})
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {"code": "tool_error", "message": str(exc)[:300]})
            self._json(404, {"code": "not_found", "message": "introuvable"})

    return Handler


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ouvre la page web locale du Hub Service Public")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    args = ap.parse_args(argv)
    config.load_env()
    token = secrets.token_urlsafe(24)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(token, args.port))
    except OSError:
        print(f"Le port {args.port} est déjà utilisé : la page tourne peut-être déjà sur http://127.0.0.1:{args.port}/ "
              f"(sinon : uv run hub-web --port {args.port + 1})", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Hub Service Public : {url}")
    print("Réponses rédigées par Claude : " + ("activées" if ai_enabled() else "désactivées (ajoutez ANTHROPIC_API_KEY dans .env)"))
    print("Laissez cette fenêtre ouverte ; Ctrl+C pour arrêter.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
