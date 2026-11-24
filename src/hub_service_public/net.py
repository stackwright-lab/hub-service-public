"""Client HTTP minimal (bibliothèque standard) : lecture seule, nouvelles tentatives,
limite de taille et garde anti-SSRF.

Les URL d'API viennent d'un catalogue alimenté par des tiers : on refuse donc tout hôte
dont l'adresse n'est pas publique (localhost, réseau local, métadonnées cloud…), y compris
après une redirection. Limite connue : un changement de DNS entre la vérification et la
connexion (« DNS rebinding ») n'est pas couvert.
"""
from __future__ import annotations

import ipaddress
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from .config import USER_AGENT


class HttpError(Exception):
    def __init__(self, status: int, message: str, url: str = ""):
        super().__init__(f"HTTP {status} pour {url} : {message}")
        self.status = status
        self.url = url


class UnsafeUrlError(ValueError):
    """URL refusée par les règles de sécurité."""


@dataclass
class Response:
    status: int
    headers: dict = field(default_factory=dict)
    body: bytes = b""
    url: str = ""
    truncated: bool = False

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.body)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - on suit les redirections nous-mêmes
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def assert_public_host(host: str) -> None:
    """Lève UnsafeUrlError si l'hôte n'est pas résolu vers une adresse publique."""
    if not host:
        raise UnsafeUrlError("hôte vide")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:  # panne réseau ou DNS : erreur de transport, pas un refus de sécurité
        raise HttpError(0, f"hôte introuvable ou réseau indisponible : {host}", host) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            raise UnsafeUrlError(f"hôte non public refusé : {host} -> {ip}")


def qs(params: dict | None) -> str:
    """Construit une query string. Une valeur None donne une clé nue (ex. `col__groupby`)."""
    if not params:
        return ""
    parts: list[str] = []
    for key, value in params.items():
        k = urllib.parse.quote(str(key), safe="_-.")
        if value is None:
            parts.append(k)
        elif isinstance(value, (list, tuple)):
            parts.extend(f"{k}={urllib.parse.quote(str(v), safe='')}" for v in value)
        else:
            parts.append(f"{k}={urllib.parse.quote(str(value), safe='')}")
    return "&".join(parts)


def request(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 30.0,
    retries: int = 3,
    backoff: float = 1.5,
    max_bytes: int = 5_000_000,
    allowed_host: str | None = None,
    max_redirects: int = 3,
    check_public: bool = True,
) -> Response:
    """GET uniquement. Réessaie sur erreur réseau, 429 et 5xx. Ne lève pas pour un 4xx/5xx final."""
    if params:
        url += ("&" if "?" in url else "?") + qs(params)
    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, */*;q=0.5",
        "Accept-Encoding": "identity",
    }
    hdrs.update(headers or {})
    attempt = 0
    redirects = 0
    while True:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise UnsafeUrlError(f"schéma refusé : {parts.scheme!r}")
        host = (parts.hostname or "").lower()
        if allowed_host and host != allowed_host.lower():
            raise UnsafeUrlError(f"hôte hors périmètre : {host} (autorisé : {allowed_host})")
        if check_public:
            assert_public_host(host)
        req = urllib.request.Request(url, headers=hdrs, method="GET")
        try:
            with _opener.open(req, timeout=timeout) as resp:
                status = resp.status
                rheaders = {k.lower(): v for k, v in resp.headers.items()}
                body = resp.read(max_bytes + 1)
        except urllib.error.HTTPError as exc:
            status = exc.code
            rheaders = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
            try:
                body = exc.read(max_bytes + 1)
            except Exception:  # noqa: BLE001
                body = b""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            attempt += 1
            if attempt > retries:
                raise HttpError(0, str(exc), url) from exc
            time.sleep(backoff**attempt)
            continue

        if status in (301, 302, 303, 307, 308) and rheaders.get("location"):
            redirects += 1
            if redirects > max_redirects:
                raise HttpError(status, "trop de redirections", url)
            url = urllib.parse.urljoin(url, rheaders["location"])
            continue

        if status == 429 or status >= 500:
            attempt += 1
            if attempt <= retries:
                try:
                    wait = min(float(rheaders.get("retry-after", "")), 60.0)
                except ValueError:
                    wait = backoff**attempt
                time.sleep(wait)
                continue

        return Response(
            status=status,
            headers=rheaders,
            body=body[:max_bytes],
            url=url,
            truncated=len(body) > max_bytes,
        )


def get_json(url: str, params: dict | None = None, **kwargs):
    """GET + décodage JSON ; lève HttpError si le statut est ≥ 400 ou le JSON invalide."""
    resp = request(url, params=params, **kwargs)
    if resp.status >= 400:
        raise HttpError(resp.status, resp.text[:200], resp.url)
    if resp.truncated:
        raise HttpError(resp.status, f"réponse tronquée : dépasse la limite de {kwargs.get('max_bytes', 5_000_000):,} octets", resp.url)
    try:
        return resp.json()
    except ValueError as exc:
        raise HttpError(resp.status, "réponse JSON invalide", resp.url) from exc
