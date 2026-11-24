import asyncio
import json

import pytest

from hub_service_public import config, db, harvest, server
from tests.conftest import make_dataset, make_dataservice

TOOLS = {
    "rechercher", "fiche_jeu_de_donnees", "fiche_api", "fiche_organisation", "profil_fichier",
    "interroger_fichier", "documentation_api", "appeler_api", "etat_du_hub", "dpe_par_adresse", "repondre", "disponibilite_sources", "synchroniser_index", "sante_des_donnees",
}


@pytest.fixture
def index(tmp_path, monkeypatch):
    path = tmp_path / "idx.sqlite"
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "KEYS_FILE", tmp_path / "absent.yaml")
    c = db.connect(path)
    db.init_schema(c)
    harvest.store_items(c, harvest.SPECS["datasets"], [make_dataset(1, title="Élections municipales")], run_id=1)
    harvest.store_items(c, harvest.SPECS["dataservices"], [
        make_dataservice(1, title="API Sirene"),
        make_dataservice(2, title="API fermée", access_type="restricted"),
        make_dataservice(3, title="API compte", access_type="open_with_account", authorization_request_url="https://inscription"),
    ], run_id=1)
    c.commit()
    c.close()
    return path


def call(name, **args):
    res = asyncio.run(server.mcp.call_tool(name, args))
    return json.loads(res.content[0].text)


def test_tous_les_outils_sont_declares_en_lecture_seule():
    """Tous en lecture seule, sauf synchroniser_index qui n'écrit que dans l'index local, jamais de façon destructive."""
    tools = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in tools} == TOOLS
    assert all(not t.annotations.destructive_hint for t in tools)
    assert {t.name for t in tools if not t.annotations.read_only_hint} == {"synchroniser_index"}


def test_sans_index_message_clair(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "absent.sqlite")
    out = call("rechercher", requete="energie")
    assert "uv run hub-harvest" in out["action"]


def test_recherche_via_outil(index):
    out = call("rechercher", requete="elections", type="jeux_de_donnees")
    assert out["datasets"][0]["title"] == "Élections municipales"


def test_fiche_api_etat_acces(index):
    assert call("fiche_api", identifiant="api-1")["utilisable_maintenant"] is True
    assert call("fiche_api", identifiant="api-2")["utilisable_maintenant"] is False
    compte = call("fiche_api", identifiant="api-3")
    assert compte["utilisable_maintenant"] is False and compte["cle_declaree"] is False
    assert "erreur" in call("fiche_api", identifiant="inconnue")


def test_api_restreinte_via_outil(index):
    assert "restreint" in call("appeler_api", identifiant="api-2", chemin="/x")["erreur"]


def test_etat_du_hub(index):
    out = call("etat_du_hub")
    assert out["index"]["datasets"] == 1 and out["acces_api"]["open"] == 1


def test_disponibilite_sources(populated, monkeypatch, tmp_path):
    from hub_service_public import db, services
    populated.commit()
    path = populated.execute("PRAGMA database_list").fetchone()[2]
    monkeypatch.setattr(services, "check_all", lambda: [{"id": "x", "nom": "X", "type": "API", "ok": True, "status": 200, "latency_ms": 5}])
    monkeypatch.setattr(db, "DEFAULT_PATH", path, raising=False)
    monkeypatch.setenv("HUB_DB", path)
    import importlib
    from hub_service_public import config
    monkeypatch.setattr(config, "DB_PATH", __import__("pathlib").Path(path))
    r = server.disponibilite_sources()
    assert r["services"][0]["ok"] is True
    assert r["index"]["par_type"]["datasets"]["elements"] > 0
    assert "api_catalogue" in r


def test_sante_des_donnees_et_synchro(populated, monkeypatch):
    from pathlib import Path
    from hub_service_public import config, harvest, health
    populated.commit()
    path = populated.execute("PRAGMA database_list").fetchone()[2]
    monkeypatch.setattr(config, "DB_PATH", Path(path))
    d = server.sante_des_donnees()
    assert d["datasets"]["flags"]["total"] > 0 and "by_freq" in d["datasets"]
    import threading
    done = threading.Event()
    monkeypatch.setattr(harvest, "main", lambda argv: None)
    monkeypatch.setattr(health, "main", lambda argv: done.set())
    r = server.synchroniser_index()
    assert r["lance"] is True
    assert done.wait(5)
    for _ in range(50):
        if not server._SYNC["en_cours"]:
            break
        __import__("time").sleep(0.05)
    assert server._SYNC["en_cours"] is False and server._SYNC["erreur"] is None
