import math

import pytest

from hub_service_public import db, harvest, net
from tests.conftest import make_dataset


class FakeApi:
    """Sert des pages comme l'API data.gouv.fr (champs total / data / page)."""

    def __init__(self, items, fail_pages=(), reject_sort=False):
        self.items = items
        self.fail_pages = set(fail_pages)
        self.reject_sort = reject_sort
        self.calls = []

    def __call__(self, url, params=None, **kw):
        self.calls.append(dict(params or {}))
        if self.reject_sort and params.get("sort"):
            raise net.HttpError(400, "Input payload validation failed", url)
        page, size = params["page"], params["page_size"]
        if page in self.fail_pages:
            raise net.HttpError(500, "boom", url)
        chunk = self.items[(page - 1) * size : page * size]
        return {"total": len(self.items), "page": page, "page_size": size, "data": chunk}


def run(conn, api, monkeypatch, **kw):
    monkeypatch.setattr(net, "get_json", api)
    args = dict(run_id=1, page_size=10, workers=2, delay=0, resume=False, max_pages=None)
    args.update(kw)
    return harvest.run_full(conn, harvest.SPECS["datasets"], **args)


def test_synchronisation_complete_et_pagination(conn, monkeypatch):
    api = FakeApi([make_dataset(i) for i in range(1, 36)])
    res = run(conn, api, monkeypatch)
    assert res["complete"] and res["stored"] == 35
    assert db.counts(conn)["datasets"] == 35 and db.counts(conn)["resources"] == 70
    assert max(c["page"] for c in api.calls) == math.ceil(35 / 10)
    meta = db.get_meta(conn, "harvest:datasets")
    assert meta["stored"] == 35 and meta["run_id"] == 1


def test_purge_des_elements_retires_du_site(conn, monkeypatch):
    run(conn, FakeApi([make_dataset(i) for i in range(1, 11)]), monkeypatch, run_id=1)
    res = run(conn, FakeApi([make_dataset(i) for i in range(1, 8)]), monkeypatch, run_id=2)
    assert res["purged"] == 3
    assert db.counts(conn)["datasets"] == 7 and db.counts(conn)["resources"] == 14
    assert conn.execute("SELECT COUNT(*) FROM fts_datasets").fetchone()[0] == 7


def test_page_en_echec_pas_de_purge(conn, monkeypatch):
    run(conn, FakeApi([make_dataset(i) for i in range(1, 11)]), monkeypatch, run_id=1)
    res = run(conn, FakeApi([make_dataset(i) for i in range(1, 8)], fail_pages={2}), monkeypatch, run_id=2, page_size=5)
    assert res["failed_pages"] == [2] and not res["complete"] and res["purged"] == 0
    assert db.counts(conn)["datasets"] == 10  # rien n'a été supprimé à tort


def test_tri_refuse_repli_sans_tri(conn, monkeypatch):
    api = FakeApi([make_dataset(i) for i in range(1, 6)], reject_sort=True)
    res = run(conn, api, monkeypatch)
    assert res["stored"] == 5 and api.calls[-1].get("sort") is None


def test_reprise_apres_interruption(conn, monkeypatch):
    items = [make_dataset(i) for i in range(1, 31)]
    run(conn, FakeApi(items), monkeypatch, run_id=5, max_pages=2)  # s'arrête après 2 pages
    db.set_meta(conn, "progress:datasets", {"run_id": 5, "next_page": 3})
    api = FakeApi(items)
    res = run(conn, api, monkeypatch, run_id=5, resume=True)
    assert {c["page"] for c in api.calls} == {1, 3}  # page 1 (total) puis 3
    assert res["complete"] and db.counts(conn)["datasets"] == 30


def test_incremental_s_arrete_aux_elements_anciens(conn, monkeypatch):
    items = [make_dataset(i) for i in range(1, 6)]
    run(conn, FakeApi(items), monkeypatch)
    db.set_meta(conn, "harvest:datasets", {"started_at": "2026-11-10T00:00:00+00:00"})
    recents = [make_dataset(100 + i, last_update="2026-11-20T00:00:00+00:00") for i in range(3)]
    anciens = [make_dataset(200 + i, last_update="2026-01-01T00:00:00+00:00", last_modified="2026-01-01T00:00:00+00:00") for i in range(7)]
    api = FakeApi(recents + anciens)
    monkeypatch.setattr(net, "get_json", api)
    res = harvest.run_incremental(conn, harvest.SPECS["datasets"], run_id=1, page_size=5, delay=0, max_pages=None)
    assert res["stored"] == 3 and len(api.calls) == 1  # une seule page lue
    assert db.counts(conn)["datasets"] == 8


def test_incremental_exige_un_passage_complet(conn):
    with pytest.raises(SystemExit):
        harvest.run_incremental(conn, harvest.SPECS["datasets"], run_id=1, page_size=5, delay=0, max_pages=None)


def test_reseau_coupe_arret_propre(tmp_path, monkeypatch, capsys):
    import socket

    def no_dns(*a, **k):
        raise socket.gaierror("pas de DNS")

    monkeypatch.setattr(net.socket, "getaddrinfo", no_dns)
    monkeypatch.setattr(net.time, "sleep", lambda s: None)
    code = harvest.main(["--only", "dataservices", "--max-pages", "1", "--db", str(tmp_path / "x.sqlite")])
    assert code == 1
    assert "ÉCHEC" in capsys.readouterr().err


def test_donnees_personnelles_non_conservees(conn):
    d = make_dataset(1, organization=None, owner={"first_name": "Jean", "last_name": "Dupont"})
    harvest.store_items(conn, harvest.SPECS["datasets"], [d], run_id=1)
    row = conn.execute("SELECT organization_name FROM datasets").fetchone()
    assert row[0] == "Producteur individuel"
    dump = " ".join(str(tuple(r)) for r in conn.execute("SELECT * FROM datasets"))
    assert "Dupont" not in dump


# ------------------------------------------------------------------ combler les trous


class FakeSite:
    """Site factice : pages allégées (X-Fields) et fiches par identifiant."""

    def __init__(self, items, fail_scan_pages=(), fail_ids=()):
        self.by_id = {i["id"]: i for i in items}
        self.order = [i["id"] for i in items]
        self.fail_scan_pages, self.fail_ids = set(fail_scan_pages), set(fail_ids)
        self.fetched = []

    def __call__(self, url, params=None, **kw):
        if params and "page" in params:
            assert kw["headers"]["X-Fields"].startswith("data{id}"), "l'inventaire doit rester léger"
            if params["page"] in self.fail_scan_pages:
                raise net.HttpError(500, "boom", url)
            size, page = params["page_size"], params["page"]
            ids = self.order[(page - 1) * size : page * size]
            return {"total": len(self.order), "data": [{"id": i} for i in ids]}
        ident = url.rstrip("/").rsplit("/", 1)[1]
        self.fetched.append(ident)
        if ident in self.fail_ids:
            raise net.HttpError(500, "boom", url)
        return self.by_id[ident]


def fill(conn, site, monkeypatch, run_id=7):
    monkeypatch.setattr(net, "get_json", site)
    return harvest.run_fill_gaps(conn, harvest.SPECS["datasets"], run_id=run_id, page_size=4, workers=2, delay=0)


def test_combler_les_trous_telecharge_les_manquants_et_retire_les_disparus(conn, monkeypatch):
    present = [make_dataset(i) for i in (1, 2, 3, 99)]  # 99 a été retiré du site
    harvest.store_items(conn, harvest.SPECS["datasets"], present, run_id=7)
    site = FakeSite([make_dataset(i) for i in range(1, 11)])  # le site en a 10 : il manque 4..10
    res = fill(conn, site, monkeypatch)
    assert res["complete"] and res["missing"] == 7 and res["removed"] == 1
    assert sorted(site.fetched) == [f"ds{i:04d}" for i in range(4, 11)]  # seuls les manquants sont téléchargés
    assert db.counts(conn)["datasets"] == 10 and db.counts(conn)["resources"] == 20
    assert conn.execute("SELECT COUNT(*) FROM datasets WHERE id='ds0099'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM fts_datasets").fetchone()[0] == 10
    assert {r[0] for r in conn.execute("SELECT DISTINCT run_id FROM datasets")} == {7}  # pas purgeables ensuite
    meta = db.get_meta(conn, "harvest:datasets")
    assert meta["mode"] == "fill-gaps" and meta["stored"] == 10 and meta["started_at"].startswith("1970")


def test_combler_les_trous_inventaire_incomplet_ne_supprime_rien(conn, monkeypatch):
    harvest.store_items(conn, harvest.SPECS["datasets"], [make_dataset(i) for i in (1, 2, 99)], run_id=7)
    site = FakeSite([make_dataset(i) for i in range(1, 9)], fail_scan_pages={2})
    res = fill(conn, site, monkeypatch)
    assert not res["complete"] and res["failed_pages"] == [2] and res["removed"] == 0
    assert conn.execute("SELECT COUNT(*) FROM datasets WHERE id='ds0099'").fetchone()[0] == 1
    assert db.get_meta(conn, "harvest:datasets") is None  # pas déclaré complet


def test_combler_les_trous_jeu_en_echec_est_signale(conn, monkeypatch):
    site = FakeSite([make_dataset(i) for i in range(1, 6)], fail_ids={"ds0003"})
    res = fill(conn, site, monkeypatch)
    assert res["failed_ids"] == ["ds0003"] and not res["complete"] and db.counts(conn)["datasets"] == 4
    assert db.get_meta(conn, "failed:datasets")["ids"] == ["ds0003"]
    res = fill(conn, FakeSite([make_dataset(i) for i in range(1, 6)]), monkeypatch)  # 2e passage : tout rentre
    assert res["complete"] and res["missing"] == 1 and db.counts(conn)["datasets"] == 5


def test_pages_en_echec_memorisees_et_conseil_affiche(conn, monkeypatch, capsys):
    run(conn, FakeApi([make_dataset(i) for i in range(1, 8)], fail_pages={2}), monkeypatch, page_size=3)
    assert db.get_meta(conn, "failed:datasets") == [2]
    assert "--fill-gaps" in capsys.readouterr().err


def test_tres_gros_jeux_ne_sont_pas_tronques(monkeypatch):
    """Régression : des jeux de 5 à 21 Mo (jusqu'à 15 000 fichiers) étaient coupés par la limite de 5 Mo."""
    seen = []

    def capture(url, params=None, **kw):
        seen.append(kw.get("max_bytes"))
        return {"total": 0, "data": []}

    monkeypatch.setattr(net, "get_json", capture)
    spec = harvest.SPECS["datasets"]
    harvest.fetch_page(spec, 1, 100, None)
    harvest.fetch_one(spec, "abc")
    assert all(m and m >= 50_000_000 for m in seen) and len(seen) == 2


def test_get_json_json_tronque_leve_une_erreur_explicite(monkeypatch):
    big = net.Response(status=200, body=b'{"a": "' + b"x" * 10, truncated=True, url="https://x")
    monkeypatch.setattr(net, "request", lambda *a, **k: big)
    with pytest.raises(net.HttpError):
        net.get_json("https://x")
