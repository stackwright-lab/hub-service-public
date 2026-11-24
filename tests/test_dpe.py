import pytest

from hub_service_public import config, dpe, explorer, net

GEO = {"features": [{"geometry": {"coordinates": [-0.57, 44.85]}, "properties": {
    "label": "10 Rue de Rivoli 75004 Paris", "score": 0.97, "type": "housenumber", "citycode": "75104", "postcode": "75004", "city": "Paris"}}]}
ADEME = {"total": 1, "results": [{"numero_dpe": "2475E0000000X", "etiquette_dpe": "C", "etiquette_ges": "B", "_score": 48.9,
                                   "adresse_ban": "10 Rue de Rivoli 75004 Paris"}]}


@pytest.mark.parametrize("text,addr", [
    ("cherche moi le DPE du 10 rue de Rivoli à Paris", "10 rue de Rivoli Paris"),
    ("DPE 12 bis avenue Thiers, Bordeaux ?", "12 bis avenue Thiers, Bordeaux"),
])
def test_extract_address(text, addr):
    assert dpe.wants_dpe(text) and dpe.extract_address(text) == addr


def test_intent_requires_both_dpe_and_address():
    assert not dpe.wants_dpe("DPE logements ADEME")
    assert not dpe.wants_dpe("population du 5 rue de Paris")
    assert not dpe.wants_dpe("")


def test_dpe_par_adresse_ok(monkeypatch):
    calls = []

    def fake(url, params=None, **kw):
        calls.append((url, params))
        return GEO if url.startswith(config.GEOCODE_BASE) else ADEME
    monkeypatch.setattr(net, "get_json", fake)
    r = dpe.dpe_par_adresse("10 rue de Rivoli Paris")
    assert r["adresse_reconnue"] == "10 Rue de Rivoli 75004 Paris" and r["total"] == 1
    assert "_score" not in r["diagnostics"][0] and r["diagnostics"][0]["etiquette_dpe"] == "C"
    assert calls[1][1]["adresse_ban_eq"] == "10 Rue de Rivoli 75004 Paris" and calls[1][1]["size"] == 20


def test_dpe_refuses_vague_or_failing(monkeypatch):
    street = {"features": [{"properties": {"label": "Rue de Rivoli 75004 Paris", "score": 0.9, "type": "street"}}]}
    monkeypatch.setattr(net, "get_json", lambda *a, **k: street)
    assert "numéro" in dpe.dpe_par_adresse("rue de rivoli paris")["erreur"]
    monkeypatch.setattr(net, "get_json", lambda *a, **k: (_ for _ in ()).throw(net.HttpError(503, "down", "u")))
    assert "indisponible" in dpe.dpe_par_adresse("10 rue de rivoli paris")["erreur"]
    assert dpe.dpe_par_adresse("ab")["erreur"]


def test_ask_routes_to_dpe_or_search(populated, monkeypatch):
    populated.commit()
    path = populated.execute("PRAGMA database_list").fetchone()[2]
    monkeypatch.setattr(dpe, "dpe_par_adresse", lambda a, limit=20: {"adresse_reconnue": a, "diagnostics": []})
    r = explorer.api_ask(path, {"q": "cherche le DPE du 10 rue de Rivoli à Paris"})
    assert r["intention"] == "dpe" and r["adresse_reconnue"] == "10 rue de Rivoli Paris"
    r = explorer.api_ask(path, {"q": "population", "type": "tout"})
    assert r["intention"] == "general" and "resultats" in r
