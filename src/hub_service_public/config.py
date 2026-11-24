"""Configuration : chemins, URLs de base, chargement du fichier .env."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("HUB_ROOT") or Path(__file__).resolve().parents[2])
DATA_DIR = Path(os.environ.get("HUB_DATA_DIR") or ROOT / "data")
DB_PATH = Path(os.environ.get("HUB_DB") or DATA_DIR / "catalogue.sqlite")
KEYS_FILE = Path(os.environ.get("HUB_KEYS_FILE") or ROOT / "config" / "api_keys.yaml")
ENV_FILE = ROOT / ".env"

API_BASE = os.environ.get("HUB_DATAGOUV_API", "https://www.data.gouv.fr/api/1")
TABULAR_BASE = os.environ.get("HUB_TABULAR_API", "https://tabular-api.data.gouv.fr/api")
SITE_BASE = "https://www.data.gouv.fr"
USER_AGENT = "hub-service-public/1.0 (outil personnel de recherche, lecture seule)"


def load_env(path: Path | None = None) -> None:
    """Charge un fichier .env minimal (KEY=VALUE) sans écraser l'environnement."""
    path = path or ENV_FILE
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

# Sources tierces officielles utilisées par les outils « adresse » (hôtes fixes, jamais fournis par l'utilisateur).
GEOCODE_BASE = os.environ.get("HUB_GEOCODE", "https://data.geopf.fr/geocodage")
ADEME_DPE_LINES = os.environ.get("HUB_ADEME_DPE", "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines")
