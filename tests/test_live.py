import json

import pytest

from hub_service_public import config, live, net

API = {
    "id": "api1", "slug": "api-1", "title": "API", "access_type": "open",
    "base_api_url": "https://api.exemple.fr/v1/", "machine_documentation_url": "https://api.exemple.fr/openapi.json",
    "authorization_request_url": "", "page": "https://www.data.gouv.fr/dataservices/api-1",
}


def fake_response(status=200, body=b"{}", headers=None):
    return net.Response(status=status, headers=headers or {"content-type": "application/json"}, body=body, url="https://x")


# ------------------------------------------------------------------ API tabulaire


def test_parametres_tabulaires_verifies():
    p = live.build_tabular_params(
        columns=["commune", "population"],
        filters={"commune__contains": "bordeaux", "annee": 2024, "code__in": ["33", "75"], "nom__isnull": True},
        sort={"population": "desc"}, group_by=["commune"], count=["commune"], page=2, page_size=500,
    )
    assert p["page_size"] == 50  # plafond constaté sur l'API réelle
    assert p["columns"] == "commune,population"
    assert p["commune__contains"] == "bordeaux" and p["annee__exact"] == 2024
    assert p["code__in"] == "33,75" and p["nom__isnull"] is None
    assert p["population__sort"] == "desc" and "commune__groupby" in p and "commune__count" in p


@pytest.mark.parametrize("filters", [{"a__bidon": 1}, {"a b": 1}, {"a&b=1": 1}, {"../x": 1}])
def test_parametres_invalides(filters):
    with pytest.raises(ValueError):
        live.build_tabular_params(filters=filters)


def test_query_string_cle_nue():
    p = live.build_tabular_params(group_by=["colonne"], page_size=3)
    assert "colonne__groupby" in net.qs(p).split("&")  # forme vérifiée sur l'API réelle (sans « = »)


def test_identifiant_de_ressource_invalide():
    with pytest.raises(ValueError):
        live.tabular_query("../../etc/passwd")


def test_ressource_non_interrogeable(monkeypatch):
    monkeypatch.setattr(net, "request", lambda *a, **k: fake_response(404, b"{}"))
    out = live.tabular_query("fcaa05c0-0431-43a6-a17d-7aa4fb89220b")
    assert "non interrogeable" in out["erreur"]


def test_resultat_tabulaire(monkeypatch):
    body = json.dumps({"data": [{"a": 1}], "meta": {"page": 1, "page_size": 20, "total": 68}, "links": {"next": "n"}}).encode()
    monkeypatch.setattr(net, "request", lambda *a, **k: fake_response(200, body))
    out = live.tabular_query("fcaa05c0-0431-43a6-a17d-7aa4fb89220b")
    assert out["total"] == 68 and out["lignes"] == [{"a": 1}] and "tiers" in out["avertissement"]


# ------------------------------------------------------------------ appel d'API : garde-fous


def test_api_restreinte_jamais_appelee(monkeypatch):
    monkeypatch.setattr(net, "request", lambda *a, **k: pytest.fail("ne doit pas appeler le réseau"))
    out = live.call_api({**API, "access_type": "restricted"}, "/x")
    assert "restreint" in out["erreur"]


def test_api_avec_compte_sans_cle(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "KEYS_FILE", tmp_path / "absent.yaml")
    monkeypatch.setattr(net, "request", lambda *a, **k: pytest.fail("ne doit pas appeler le réseau"))
    out = live.call_api({**API, "access_type": "open_with_account", "authorization_request_url": "https://inscription"}, "/x")
    assert "clé" in out["erreur"] and out["demarche"] == "https://inscription"


def test_cle_declaree_envoyee_en_en_tete_jamais_renvoyee(monkeypatch, tmp_path):
    keys = tmp_path / "keys.yaml"
    keys.write_text("api-1:\n  header: X-API-Key\n  env: MA_CLE_TEST\n  prefix: ''\n", encoding="utf-8")
    monkeypatch.setattr(config, "KEYS_FILE", keys)
    monkeypatch.setenv("MA_CLE_TEST", "secret-123")
    seen = {}

    def fake(url, **kw):
        seen.update(kw, url=url)
        return fake_response(200, b'{"ok": true}')

    monkeypatch.setattr(net, "request", fake)
    out = live.call_api({**API, "access_type": "open_with_account"}, "/siren/1", {"q": "x"})
    assert seen["headers"] == {"X-API-Key": "secret-123"} and seen["allowed_host"] == "api.exemple.fr"
    assert "secret-123" not in json.dumps(out)
    assert out["statut"] == 200 and out["url_appelee"] == "https://api.exemple.fr/v1/siren/1?q=x"


def test_cle_jamais_envoyee_en_http(monkeypatch, tmp_path):
    keys = tmp_path / "keys.yaml"
    keys.write_text("api-1:\n  header: X-API-Key\n  env: MA_CLE_TEST\n", encoding="utf-8")
    monkeypatch.setattr(config, "KEYS_FILE", keys)
    monkeypatch.setenv("MA_CLE_TEST", "secret-123")
    monkeypatch.setattr(net, "request", lambda *a, **k: pytest.fail("pas d'appel"))
    out = live.call_api({**API, "base_api_url": "http://api.exemple.fr/v1/", "access_type": "open_with_account"}, "/x")
    assert "non chiffrée" in out["erreur"]


@pytest.mark.parametrize("path", ["../../etc/passwd", "http://evil.example/x", "/a?b=c", "/a#frag", "\\\\hote\\partage"])
def test_chemins_interdits(path, monkeypatch):
    monkeypatch.setattr(net, "request", lambda *a, **k: pytest.fail("pas d'appel"))
    assert "refusé" in live.call_api(API, path)["erreur"]


def test_hote_prive_refuse(monkeypatch):
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("192.168.1.10", 0))])
    out = live.call_api({**API, "base_api_url": "https://interne.exemple.fr/"}, "/x")
    assert "non public" in out["erreur"]


def test_localhost_et_metadonnees_cloud_refuses(monkeypatch):
    for ip in ("127.0.0.1", "169.254.169.254", "10.0.0.5", "::1"):
        monkeypatch.setattr(net.socket, "getaddrinfo", lambda *a, ip=ip, **k: [(2, 1, 6, "", (ip, 0))])
        with pytest.raises(net.UnsafeUrlError):
            net.assert_public_host("exemple.fr")


def test_redirection_vers_autre_hote_refusee(monkeypatch):
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    calls = []

    class FakeOpener:
        def open(self, req, timeout=None):
            calls.append(req.full_url)
            import urllib.error, email.message
            h = email.message.Message()
            h["Location"] = "https://autre-hote.exemple.org/vole"
            raise urllib.error.HTTPError(req.full_url, 302, "Found", h, None)

    monkeypatch.setattr(net, "_opener", FakeOpener())
    out = live.call_api(API, "/x")
    assert "hors périmètre" in out["erreur"] and len(calls) == 1


def test_reponse_json_tronquee(monkeypatch):
    big = json.dumps({"x": "a" * 100_000}).encode()
    monkeypatch.setattr(net, "request", lambda *a, **k: fake_response(200, big))
    out = live.call_api(API, "/x")
    assert out["reponse_tronquee"] and len(out["contenu"]) <= live.MAX_TOOL_CHARS


# ------------------------------------------------------------------ OpenAPI


def test_resume_openapi_3_et_swagger_2():
    doc3 = {"openapi": "3.0.0", "info": {"title": "T", "version": "1"}, "servers": [{"url": "https://api.exemple.fr/v3"}],
            "paths": {"/a": {"get": {"summary": "lire", "parameters": [{"name": "q"}]}, "post": {}}}}
    s = live.summarize_openapi(doc3)
    assert s["serveurs"] == ["https://api.exemple.fr/v3"] and s["nombre_operations"] == 2
    assert s["operations_get"][0]["parametres"] == ["q"] and s["autres_operations_ignorees"] == 1
    doc2 = {"swagger": "2.0", "host": "h.exemple.fr", "basePath": "/v2", "schemes": ["https"], "paths": {}}
    assert live.summarize_openapi(doc2)["serveurs"] == ["https://h.exemple.fr/v2"]


def test_documentation_non_openapi(monkeypatch):
    monkeypatch.setattr(net, "request", lambda *a, **k: fake_response(200, b"<html>page web</html>", {"content-type": "text/html"}))
    out = live.fetch_openapi(API)
    assert "OpenAPI" in out["avertissement"]


def test_serveur_openapi_utilise_comme_base(monkeypatch):
    doc = json.dumps({"openapi": "3.0.0", "servers": [{"url": "https://vrai-api.exemple.fr/v9"}], "paths": {}}).encode()
    urls = []

    def fake(url, **kw):
        urls.append((url, kw.get("allowed_host")))
        return fake_response(200, doc if url.endswith("openapi.json") else b'{"ok":1}')

    monkeypatch.setattr(net, "request", fake)
    out = live.call_api({**API, "base_api_url": "https://portail.exemple.fr/page"}, "/ping", use_openapi_server=True)
    assert urls[-1] == ("https://vrai-api.exemple.fr/v9/ping", "vrai-api.exemple.fr") and out["statut"] == 200
