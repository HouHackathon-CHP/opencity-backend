# SPDX-License-Identifier: Apache-2.0
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core import config

def air_quality_db() -> sqlite3.Connection:
    path = Path(config.AIR_QUALITY_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS air_stations (
            code TEXT NOT NULL,
            tenant TEXT NOT NULL,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            area_type TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            PRIMARY KEY (tenant, code)
        );
        CREATE TABLE IF NOT EXISTS air_readings (
            id TEXT PRIMARY KEY,
            station_code TEXT NOT NULL,
            tenant TEXT NOT NULL,
            aqi INTEGER NOT NULL,
            pm25 REAL NOT NULL,
            pm10 REAL,
            temperature REAL,
            humidity REAL,
            co REAL,
            no2 REAL,
            o3 REAL,
            so2 REAL,
            note TEXT,
            recorded_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS air_readings_lookup
            ON air_readings(tenant, station_code, recorded_at DESC);
        CREATE TABLE IF NOT EXISTS air_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    try:
        connection.execute("ALTER TABLE air_stations ADD COLUMN status TEXT DEFAULT 'active'")
    except sqlite3.OperationalError:
        pass
    return connection


def ensure_tenant_seed(connection: sqlite3.Connection, tenant: str) -> None:
    """Dynamic storage - stations and telemetry are managed via API and live sensors."""
    pass


def list_stations(connection: sqlite3.Connection, tenant: str) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT * FROM air_stations WHERE tenant = ? ORDER BY code ASC",
        (tenant,)
    ).fetchall()


def get_station(connection: sqlite3.Connection, tenant: str, code: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM air_stations WHERE tenant = ? AND code = ?",
        (tenant, code)
    ).fetchone()


def insert_station(
    connection: sqlite3.Connection,
    tenant: str,
    code: str,
    name: str,
    address: str,
    area_type: str,
    latitude: float,
    longitude: float,
    status: str = "active",
    created_at: str | None = None,
) -> None:
    now_iso = created_at or datetime.now(timezone.utc).isoformat()
    connection.execute("""
        INSERT INTO air_stations
            (code, tenant, name, address, area_type, latitude, longitude, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (code, tenant, name, address, area_type, latitude, longitude, status, now_iso))


def update_station_status(
    connection: sqlite3.Connection, tenant: str, code: str, status: str
) -> None:
    connection.execute(
        "UPDATE air_stations SET status = ? WHERE tenant = ? AND code = ?",
        (status, tenant, code),
    )


def delete_station(connection: sqlite3.Connection, tenant: str, code: str) -> None:
    connection.execute(
        "DELETE FROM air_readings WHERE tenant = ? AND station_code = ?",
        (tenant, code),
    )
    connection.execute(
        "DELETE FROM air_stations WHERE tenant = ? AND code = ?",
        (tenant, code),
    )


def get_latest_reading(connection: sqlite3.Connection, tenant: str, station_code: str) -> sqlite3.Row | None:
    return connection.execute(
        """SELECT * FROM air_readings
           WHERE tenant = ? AND station_code = ?
           ORDER BY recorded_at DESC, rowid DESC LIMIT 1""",
        (tenant, station_code)
    ).fetchone()


def list_recent_readings(
    connection: sqlite3.Connection, tenant: str, station_code: str, limit: int = 24
) -> list[sqlite3.Row]:
    return connection.execute(
        """SELECT * FROM air_readings
           WHERE tenant = ? AND station_code = ?
           ORDER BY recorded_at DESC, rowid DESC LIMIT ?""",
        (tenant, station_code, limit)
    ).fetchall()


def insert_reading(
    connection: sqlite3.Connection,
    reading_id: str,
    tenant: str,
    station_code: str,
    aqi: int,
    pm25: float,
    pm10: float | None,
    temperature: float | None,
    humidity: float | None,
    co: float | None,
    no2: float | None,
    o3: float | None,
    so2: float | None,
    note: str | None,
    recorded_at: str,
) -> None:
    connection.execute("""
        INSERT INTO air_readings
            (id, station_code, tenant, aqi, pm25, pm10, temperature, humidity, co, no2, o3, so2, note, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        reading_id, station_code, tenant, aqi, pm25, pm10,
        temperature, humidity, co, no2, o3, so2, note, recorded_at
    ))



def get_config(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute("SELECT value FROM air_config WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_config(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute("INSERT OR REPLACE INTO air_config (key, value) VALUES (?, ?)", (key, value))
