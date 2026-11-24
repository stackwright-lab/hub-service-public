from hub_service_public import search


def titles(res, kind):
    return [r.get("title") or r.get("name") for r in res[kind]]


def test_recherche_insensible_aux_accents_et_a_la_casse(populated):
    res = search.search(populated, "ENERGIE logements", "jeux_de_donnees")
    assert "Diagnostics de performance énergétique (DPE) des logements" in titles(res, "datasets")


def test_prefixe_et_mots_vides(populated):
    res = search.search(populated, "population des commun", "jeux_de_donnees")
    assert titles(res, "datasets")[0] == "Population légale des communes"


def test_repli_sur_un_des_mots(populated):
    res = search.search(populated, "dvf introuvablemot", "jeux_de_donnees")
    assert "Transactions immobilières (DVF)" in titles(res, "datasets")


def test_filtre_format_et_producteur(populated):
    res = search.search(populated, "", "jeux_de_donnees", format="geojson")
    assert titles(res, "datasets") == ["Transactions immobilières (DVF)"]
    res = search.search(populated, "", "jeux_de_donnees", producteur="ademe")
    assert len(res["datasets"]) == 1


def test_filtre_interrogeable(populated):
    res = search.search(populated, "", "jeux_de_donnees", interrogeable=True)
    ids = {r["id"] for r in res["datasets"]}
    assert ids == {"ds0001", "ds0002"}  # le jeu DVF n'a pas de fichier analysé


def test_api_et_acces(populated):
    res = search.search(populated, "api", "api", acces="restricted")
    assert titles(res, "dataservices") == ["API Impôts particulier"]


def test_recherche_transversale(populated):
    res = search.search(populated, "dpe", "tout")
    assert set(res) == {"datasets", "dataservices", "organizations", "reuses", "discussions"}
    assert res["reuses"] and res["datasets"]


def test_requete_hostile_ne_casse_pas_fts(populated):
    for q in ['"', "a OR b NEAR(", "*", "' ; DROP TABLE datasets; --", "(((("]:
        search.search(populated, q, "tout")


def test_type_inconnu(populated):
    import pytest

    with pytest.raises(ValueError):
        search.search(populated, "x", "nimportequoi")


def test_fiches(populated):
    ds = search.get_dataset(populated, "jeu-1")
    assert ds["discussions"] == 1 and len(ds["ressources"]) == 2
    assert any(r["tabular"] == 1 for r in ds["ressources"])
    assert search.get_dataservice(populated, "api-1")["title"] == "API Sirene"
    org = search.get_organization(populated, "ademe")
    assert org["datasets_count"] == 113 and len(org["jeux_de_donnees_populaires"]) == 1
    assert search.get_dataset(populated, "inconnu") is None


def test_mot_exact_avant_prefixe_et_popularite_des_organisations(conn):
    from hub_service_public import harvest

    spec = harvest.SPECS["organizations"]
    harvest.store_items(conn, spec, [
        {"id": "o1", "slug": "inseec", "name": "Inseec_ODU_Equipe4", "metrics": {"datasets": 0}},
        {"id": "o2", "slug": "insee", "name": "Institut national de la statistique et des études économiques (Insee)", "metrics": {"datasets": 184}},
    ], run_id=1)
    conn.commit()
    names = [r["name"] for r in search.search(conn, "insee", "organisations")["organizations"]]
    assert names[0].startswith("Institut national") and names[1] == "Inseec_ODU_Equipe4"  # exact d'abord, préfixe ensuite


def test_popularite_departage_les_jeux_aussi_pertinents(conn):
    from hub_service_public import harvest
    from tests.conftest import make_dataset

    harvest.store_items(conn, harvest.SPECS["datasets"], [
        make_dataset(1, title="DPE logements", metrics={"views": 0}),
        make_dataset(2, title="DPE logements", metrics={"views": 60000}),
    ], run_id=1)
    conn.commit()
    ids = [r["id"] for r in search.search(conn, "dpe logements", "jeux_de_donnees")["datasets"]]
    assert ids == ["ds0002", "ds0001"]


def test_pagination_stable_sur_deux_passes(populated):
    page1 = search.search(populated, "", "jeux_de_donnees", limit=2)["datasets"]
    page2 = search.search(populated, "", "jeux_de_donnees", limit=2, offset=2)["datasets"]
    assert len(page1) == 2 and len(page2) == 1 and not {r["id"] for r in page1} & {r["id"] for r in page2}
    q1 = search.search(populated, "dpe", "tout", limit=1, offset=0)["datasets"]
    assert len(q1) == 1
