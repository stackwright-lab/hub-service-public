"""Jeux d'essai fidèles au format réel de l'API data.gouv.fr (champs relevés le 23/11/2026)."""
from __future__ import annotations

import pytest

from hub_service_public import db


def make_dataset(i: int, **over) -> dict:
    d = {
        "id": f"ds{i:04d}",
        "slug": f"jeu-{i}",
        "title": f"Jeu numéro {i}",
        "acronym": None,
        "description": "Description du jeu.",
        "organization": {"id": "org1", "name": "Rayon Santé", "slug": "rayon-sante"},
        "frequency": "daily",
        "license": "odc-odbl",
        "tags": ["sante", "commune"],
        "created_at": f"2026-11-{(i % 28) + 1:02d}T10:00:00+00:00",
        "last_modified": f"2026-11-{(i % 28) + 1:02d}T10:00:00+00:00",
        "last_update": f"2026-11-{(i % 28) + 1:02d}T10:00:00+00:00",
        "spatial": {"granularity": "fr:commune", "zones": ["country-subset:fr:metro"]},
        "temporal_coverage": {"start": "2020-01-01", "end": "2024-12-31"},
        "quality": {"score": 0.88},
        "metrics": {"views": 100 - i, "reuses": 1, "followers": 2},
        "page": f"https://www.data.gouv.fr/datasets/jeu-{i}/",
        "private": False,
        "archived": None,
        "resources": [
            {
                "id": f"fcaa05c0-0431-43a6-a17d-7aa4fb89{i:04d}",
                "title": "Données communales",
                "format": "csv",
                "mime": "text/csv",
                "filesize": 8953,
                "url": "https://exemple.fr/donnees.csv",
                "latest": f"https://www.data.gouv.fr/api/1/datasets/r/{i}",
                "type": "main",
                "last_modified": "2026-11-22T20:41:29+00:00",
                "extras": {"analysis:parsing:parsing_table": "abc123"},
            },
            {
                "id": f"aaaaaaaa-0000-0000-0000-{i:012d}",
                "title": "Dictionnaire",
                "format": "pdf",
                "type": "documentation",
                "url": "https://exemple.fr/doc.pdf",
                "extras": {},
            },
        ],
    }
    d.update(over)
    return d


def make_dataservice(i: int, **over) -> dict:
    d = {
        "id": f"api{i:04d}",
        "slug": f"api-{i}",
        "title": f"API exemple {i}",
        "acronym": None,
        "description": "API de démonstration.",
        "organization": {"id": "org2", "name": "Institut national de la statistique et des études économiques (Insee)"},
        "base_api_url": "https://api.exemple.fr/v1/",
        "machine_documentation_url": "https://api.exemple.fr/openapi.json",
        "technical_documentation_url": None,
        "business_documentation_url": None,
        "access_type": "open",
        "authorization_request_url": None,
        "rate_limiting": "20 interrogations par seconde",
        "availability": 99.9,
        "license": "lov2",
        "tags": ["entreprises"],
        "format": "REST",
        "self_web_url": f"https://www.data.gouv.fr/dataservices/api-{i}",
        "created_at": "2025-01-01T00:00:00+00:00",
    }
    d.update(over)
    return d


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.sqlite")
    db.init_schema(c)
    yield c
    c.close()


@pytest.fixture
def populated(conn):
    from hub_service_public import harvest, normalize

    ds = harvest.SPECS["datasets"]
    harvest.store_items(
        conn,
        ds,
        [
            make_dataset(1, title="Diagnostics de performance énergétique (DPE) des logements", tags=["energie", "logement"],
                         organization={"id": "ademe", "name": "ADEME"}),
            make_dataset(2, title="Population légale des communes", organization={"id": "insee", "name": "Insee"}, tags=["population"]),
            make_dataset(3, title="Transactions immobilières (DVF)", tags=["immobilier"], resources=[
                {"id": "rr3", "title": "DVF 2024", "format": "geojson", "extras": {}}]),
        ],
        run_id=1,
    )
    harvest.store_items(conn, harvest.SPECS["dataservices"], [
        make_dataservice(1, title="API Sirene", description="Répertoire des entreprises"),
        make_dataservice(2, title="API Données Radar", access_type="open_with_account",
                         authorization_request_url="https://exemple.fr/inscription", base_api_url="https://api2.exemple.fr/"),
        make_dataservice(3, title="API Impôts particulier", access_type="restricted"),
    ], run_id=1)
    harvest.store_items(conn, harvest.SPECS["organizations"], [
        {"id": "ademe", "slug": "ademe", "name": "ADEME", "description": "Agence de la transition écologique",
         "metrics": {"datasets": 113, "reuses": 4}, "page": "https://www.data.gouv.fr/organizations/ademe/"},
    ], run_id=1)
    harvest.store_items(conn, harvest.SPECS["reuses"], [
        {"id": "r1", "slug": "carte-dpe", "title": "Carte des passoires thermiques", "description": "Visualisation des DPE",
         "type": "visualization", "url": "https://exemple.fr", "datasets": [{"id": "ds0001"}], "tags": ["dpe"]},
    ], run_id=1)
    harvest.store_items(conn, harvest.SPECS["discussions"], [
        {"id": "dis1", "title": "Colonnes manquantes", "subject": {"class": "Dataset", "id": "ds0001"},
         "created": "2026-11-01T00:00:00+00:00", "discussion": [{"content": "Il manque la colonne surface."}]},
    ], run_id=1)
    conn.commit()
    return conn
