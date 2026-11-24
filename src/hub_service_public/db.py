"""Index local SQLite : tables du catalogue + recherche plein texte FTS5 (français, sans accents)."""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS datasets (
  id TEXT PRIMARY KEY, slug TEXT, title TEXT, acronym TEXT, description TEXT,
  organization_id TEXT, organization_name TEXT, frequency TEXT, license TEXT, tags TEXT,
  created_at TEXT, last_modified TEXT, last_update TEXT,
  granularity TEXT, zones TEXT, temporal_start TEXT, temporal_end TEXT,
  quality_score REAL, page TEXT, private INTEGER, archived INTEGER,
  resource_count INTEGER, tabular_count INTEGER, formats TEXT,
  views INTEGER, reuses INTEGER, followers INTEGER, run_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_datasets_slug ON datasets(slug);
CREATE INDEX IF NOT EXISTS idx_datasets_org ON datasets(organization_id);

CREATE TABLE IF NOT EXISTS resources (
  id TEXT PRIMARY KEY, dataset_id TEXT, title TEXT, description TEXT, format TEXT, mime TEXT,
  filesize INTEGER, url TEXT, latest TEXT, type TEXT, last_modified TEXT,
  tabular INTEGER, run_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_resources_dataset ON resources(dataset_id);

CREATE TABLE IF NOT EXISTS dataservices (
  id TEXT PRIMARY KEY, slug TEXT, title TEXT, acronym TEXT, description TEXT,
  organization_name TEXT, base_api_url TEXT, machine_documentation_url TEXT,
  technical_documentation_url TEXT, business_documentation_url TEXT,
  access_type TEXT, authorization_request_url TEXT, rate_limiting TEXT,
  availability REAL, license TEXT, tags TEXT, format TEXT, page TEXT,
  created_at TEXT, run_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_dataservices_slug ON dataservices(slug);

CREATE TABLE IF NOT EXISTS organizations (
  id TEXT PRIMARY KEY, slug TEXT, name TEXT, acronym TEXT, description TEXT, url TEXT,
  page TEXT, datasets_count INTEGER, dataservices_count INTEGER, reuses_count INTEGER,
  followers INTEGER, run_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);

CREATE TABLE IF NOT EXISTS reuses (
  id TEXT PRIMARY KEY, slug TEXT, title TEXT, description TEXT, type TEXT, url TEXT,
  organization_name TEXT, tags TEXT, dataset_ids TEXT, created_at TEXT, page TEXT, run_id INTEGER
);

CREATE TABLE IF NOT EXISTS discussions (
  id TEXT PRIMARY KEY, title TEXT, subject_class TEXT, subject_id TEXT, created TEXT,
  closed TEXT, messages_count INTEGER, text TEXT, run_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_discussions_subject ON discussions(subject_id);

CREATE TABLE IF NOT EXISTS health_checks (
  dataservice_id TEXT, checked_at TEXT, base_status INTEGER, doc_status INTEGER,
  doc_is_openapi INTEGER, latency_ms INTEGER, error TEXT
);
CREATE INDEX IF NOT EXISTS idx_health_ds ON health_checks(dataservice_id, checked_at);
"""

# Colonnes indexées en plein texte pour chaque table (le rowid FTS = le rowid de la table de base).
FTS_COLUMNS: dict[str, list[str]] = {
    "datasets": ["title", "acronym", "description", "tags", "organization", "fichiers"],
    "dataservices": ["title", "acronym", "description", "tags", "organization"],
    "organizations": ["name", "acronym", "description"],
    "reuses": ["title", "description", "tags", "organization"],
    "discussions": ["title", "text"],
}

TOKENIZER = "unicode61 remove_diacritics 2"


def connect(path: Path | str | None = None, readonly: bool = False) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    conn.create_function("ln1p", 1, lambda x: math.log1p(x or 0), deterministic=True)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    for table, cols in FTS_COLUMNS.items():
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS fts_{table} "
            f"USING fts5({', '.join(cols)}, tokenize='{TOKENIZER}')"
        )
    conn.commit()


def exists(path: Path | str | None = None) -> bool:
    return Path(path or config.DB_PATH).is_file()


def get_meta(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def set_meta(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, ensure_ascii=False)),
    )


def upsert(conn: sqlite3.Connection, table: str, row: dict, fts_values: dict) -> None:
    """Insère ou met à jour une ligne et rafraîchit son entrée de recherche plein texte."""
    cols = list(row)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "id")
    conn.execute(
        f"INSERT INTO {table}({', '.join(cols)}) VALUES({', '.join('?' * len(cols))}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        [row[c] for c in cols],
    )
    rowid = conn.execute(f"SELECT rowid FROM {table} WHERE id=?", (row["id"],)).fetchone()[0]
    fcols = FTS_COLUMNS[table]
    conn.execute(f"DELETE FROM fts_{table} WHERE rowid=?", (rowid,))
    conn.execute(
        f"INSERT INTO fts_{table}(rowid, {', '.join(fcols)}) VALUES(?, {', '.join('?' * len(fcols))})",
        [rowid, *[fts_values.get(c, "") for c in fcols]],
    )


def replace_resources(conn: sqlite3.Connection, dataset_id: str, rows: list[dict]) -> None:
    conn.execute("DELETE FROM resources WHERE dataset_id=?", (dataset_id,))
    for r in rows:
        cols = list(r)
        conn.execute(
            f"INSERT OR REPLACE INTO resources({', '.join(cols)}) VALUES({', '.join('?' * len(cols))})",
            [r[c] for c in cols],
        )


def purge_stale(conn: sqlite3.Connection, table: str, run_id: int) -> int:
    """Supprime les lignes absentes de la dernière synchronisation complète (retirées du site)."""
    cur = conn.execute(f"DELETE FROM {table} WHERE run_id IS NOT ?", (run_id,))
    removed = cur.rowcount
    if table == "datasets":
        conn.execute("DELETE FROM resources WHERE dataset_id NOT IN (SELECT id FROM datasets)")
    conn.execute(f"DELETE FROM fts_{table} WHERE rowid NOT IN (SELECT rowid FROM {table})")
    return removed


def delete_ids(conn: sqlite3.Connection, table: str, ids: list[str]) -> int:
    """Supprime des lignes (et leurs ressources et entrées de recherche) par identifiant."""
    n = 0
    for ident in ids:
        row = conn.execute(f"SELECT rowid FROM {table} WHERE id=?", (ident,)).fetchone()
        if not row:
            continue
        conn.execute(f"DELETE FROM fts_{table} WHERE rowid=?", (row[0],))
        conn.execute(f"DELETE FROM {table} WHERE id=?", (ident,))
        if table == "datasets":
            conn.execute("DELETE FROM resources WHERE dataset_id=?", (ident,))
        n += 1
    return n


def counts(conn: sqlite3.Connection) -> dict:
    out = {}
    for table in ("datasets", "resources", "dataservices", "organizations", "reuses", "discussions"):
        out[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return out
