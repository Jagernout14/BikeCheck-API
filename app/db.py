"""SQLite database: connection, schema and seed data.

We use the standard library `sqlite3` module directly (no ORM) to keep
the project small and the SQL easy to read.
"""

from typing import Optional
import os
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone

DB_PATH = os.getenv("BIKECHECK_DB", "bikecheck.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

-- Shared catalog: visible to everyone, editable only by its author.
-- author_id IS NULL means a built-in (seed) item that nobody can edit.
CREATE TABLE IF NOT EXISTS catalog_components (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    brand         TEXT,
    category      TEXT    NOT NULL,
    weight_g      INTEGER,
    needs_service INTEGER NOT NULL DEFAULT 1,
    author_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at    TEXT    NOT NULL
);

-- Private: every bike belongs to one user.
CREATE TABLE IF NOT EXISTS bikes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    photo_url   TEXT,
    created_at  TEXT    NOT NULL
);

-- A catalog component installed on a specific bike.
-- RESTRICT: a catalog item cannot be deleted while it is installed somewhere.
CREATE TABLE IF NOT EXISTS bike_components (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    bike_id       INTEGER NOT NULL REFERENCES bikes(id) ON DELETE CASCADE,
    catalog_id    INTEGER NOT NULL REFERENCES catalog_components(id) ON DELETE RESTRICT,
    installed_at  TEXT    NOT NULL,
    note          TEXT
);

-- Maintenance records for an installed component.
CREATE TABLE IF NOT EXISTS services (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id  INTEGER NOT NULL REFERENCES bike_components(id) ON DELETE CASCADE,
    done_at       TEXT    NOT NULL,
    mileage_km    INTEGER NOT NULL,
    note          TEXT,
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bikes_owner        ON bikes(owner_id);
CREATE INDEX IF NOT EXISTS idx_components_bike    ON bike_components(bike_id);
CREATE INDEX IF NOT EXISTS idx_components_catalog ON bike_components(catalog_id);
CREATE INDEX IF NOT EXISTS idx_services_component ON services(component_id);
"""

# (name, brand, category, weight_g, needs_service)
SEED_CATALOG = [
    ("Sentinel Frame", "Transition", "frame", 3300, True),
    ("Capra Frame", "YT", "frame", 3500, True),
    ("ZEB Ultimate 170", "RockShox", "fork", 2300, True),
    ("38 Factory 170", "Fox", "fork", 2400, True),
    ("EX 511 Rims", "DT Swiss", "rims", 1100, False),
    ("Flow MK4 Rims", "Stan's", "rims", 1000, False),
    ("Hydra Hubs", "Industry Nine", "hubs", 520, True),
    ("350 Hubs", "DT Swiss", "hubs", 560, True),
    ("XO Eagle Transmission", "SRAM", "drivetrain", 1650, True),
    ("Deore XT M8100", "Shimano", "drivetrain", 1450, True),
    ("No.42 Headset", "Cane Creek", "headset", 110, True),
    ("Atlas Handlebar 35", "Race Face", "cockpit", 310, False),
    ("Code RSC", "SRAM", "brakes", 560, True),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Optional[str] = None) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM catalog_components").fetchone()[0]
        if count == 0:
            now = utc_now()
            conn.executemany(
                "INSERT INTO catalog_components "
                "(name, brand, category, weight_g, needs_service, author_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, NULL, ?)",
                [(n, b, c, w, int(s), now) for n, b, c, w, s in SEED_CATALOG],
            )
        conn.commit()
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
