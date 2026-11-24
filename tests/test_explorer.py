from hub_service_public import explorer, live


def _path(conn):
    conn.commit()
    return conn.execute("PRAGMA database_list").fetchone()[2]


def test_search_all_and_filters(populated):
    path = _path(populated)
    r = explorer.api_search(path, {"q": "jeu", "type": "tout"})
    assert r["type"] == "tout" and "datasets" in r["resultats"] and len(r["resultats"]["datasets"]) <= 6
    r = explorer.api_search(path, {"q": "", "type": "jeux_de_donnees", "limit": "2", "offset": "1"})
    assert len(r["resultats"]["datasets"]) == 2
    assert explorer.api_search(path, {"type": "n'importe quoi"})["erreur"]
    assert explorer.api_search(path, {"limit": "abc"})["erreur"]


def test_item_validation(populated):
    path = _path(populated)
    first = explorer.api_search(path, {"q": ""})["resultats"]["datasets"][0]
    assert explorer.api_item(path, {"type": "datasets", "id": first["slug"]})["title"] == first["title"]
    assert explorer.api_item(path, {"type": "sqlite_master", "id": "x"})["erreur"]
    assert explorer.api_item(path, {"type": "datasets", "id": "absent"})["erreur"] == "introuvable"


def test_rows_validates_before_network(monkeypatch):
    seen = {}
    monkeypatch.setattr(live, "tabular_query", lambda rid, **kw: seen.update(rid=rid, **kw) or {"lignes": []})
    explorer.api_rows({"rid": "abcd1234-ef", "col": "commune", "val": "Bordeaux", "page": "2"})
    assert seen["filters"] == {"commune__contains": "Bordeaux"} and seen["page"] == 2 and seen["page_size"] == 10


def test_rows_rejects_bad_input():
    assert "erreur" in explorer.api_rows({"rid": "../../etc"})
    assert "erreur" in explorer.api_rows({"rid": "abcd1234-ef", "col": "x__y", "val": "v"})
