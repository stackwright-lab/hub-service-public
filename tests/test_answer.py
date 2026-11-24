from hub_service_public import answer, dpe, live


def test_place_and_keywords():
    q = "cherche moi le nombre de transactions immobilières à Saint-Médard-en-Jalles"
    place = answer.extract_place(q)
    assert place == "Saint-Médard-en-Jalles"
    kw = answer.keywords(q, place).split()
    assert "transactions" in kw and "immobilières" in kw and "cherche" not in kw and "moi" not in kw and "Saint-Médard-en-Jalles".lower() not in kw
    assert answer.extract_place("population légale") is None


def test_investigate_filters_on_place_column(populated, monkeypatch):
    calls = []

    def fake_query(rid, **kw):
        calls.append(kw)
        row = {"commune": "Bordeaux", "valeur": 1}
        return {"total": 7, "lignes": [row], "avertissement": "données tierces"}
    monkeypatch.setattr(live, "tabular_query", fake_query)
    r = answer.repondre(populated, "population des communes à Bordeaux")
    assert r["intention"] == "general" and r["lieu_detecte"] == "Bordeaux"
    assert r["pistes"], "au moins une piste interrogeable"
    p = r["pistes"][0]
    assert p["filtre"] == "commune contient « Bordeaux »" and p["total"] == 7
    assert calls[-1]["filters"] == {"commune__contains": "Bordeaux"}
    assert r["limites"]


def test_one_failing_lead_does_not_stop_others(populated, monkeypatch):
    def boom(rid, **kw):
        raise RuntimeError("fichier indisponible")
    monkeypatch.setattr(live, "tabular_query", boom)
    r = answer.repondre(populated, "population des communes")
    assert r["pistes"] and "erreur" in r["pistes"][0]


def test_dpe_intent_and_short_question(populated, monkeypatch):
    monkeypatch.setattr(dpe, "dpe_par_adresse", lambda a, limit=20: {"adresse_reconnue": a})
    assert answer.repondre(populated, "DPE du 10 rue de Rivoli à Paris")["intention"] == "dpe"
    assert "erreur" in answer.repondre(populated, "a")


def test_place_column_variants():
    for c in ["commune", "lib_zone", "nom_commune", "libgeo", "LIBELLE_COMMUNE"]:
        assert answer._PLACE_COL.match(c), c
    assert not answer._PLACE_COL.match("code_zone")
