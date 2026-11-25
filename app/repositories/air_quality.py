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


DEFAULT_HANOI_STATIONS = [
    {"code": "HN-HOANKIEM", "name": "Trạm Hoàn Kiếm", "address": "Phố Hàng Đậu, Hoàn Kiếm, Hà Nội", "area_type": "Đô thị trung tâm", "latitude": 21.039, "longitude": 105.849, "base_aqi": 65, "base_pm25": 22.4, "base_pm10": 45.0},
    {"code": "HN-BADINH", "name": "Trạm Ba Đình", "address": "Phố Đội Cấn, Ba Đình, Hà Nội", "area_type": "Đô thị mật độ cao", "latitude": 21.034, "longitude": 105.819, "base_aqi": 58, "base_pm25": 19.8, "base_pm10": 38.5},
    {"code": "HN-TAYHO", "name": "Trạm Tây Hồ", "address": "Đường Lạc Long Quân, Tây Hồ, Hà Nội", "area_type": "Sinh thái ven hồ", "latitude": 21.066, "longitude": 105.815, "base_aqi": 42, "base_pm25": 14.0, "base_pm10": 28.0},
    {"code": "HN-DONGDA", "name": "Trạm Đống Đa", "address": "Đường Nguyễn Lương Bằng, Đống Đa, Hà Nội", "area_type": "Giao thông đô thị", "latitude": 21.018, "longitude": 105.828, "base_aqi": 88, "base_pm25": 32.5, "base_pm10": 62.0},
    {"code": "HN-CAUGIAY", "name": "Trạm Cầu Giấy", "address": "Đường Cầu Giấy, Cầu Giấy, Hà Nội", "area_type": "Trục giao thông chính", "latitude": 21.035, "longitude": 105.792, "base_aqi": 112, "base_pm25": 42.0, "base_pm10": 84.0},
    {"code": "HN-HAIBATRUNG", "name": "Trạm Hai Bà Trưng", "address": "Phố Bà Triệu, Hai Bà Trưng, Hà Nội", "area_type": "Thương mại - Dịch vụ", "latitude": 21.012, "longitude": 105.850, "base_aqi": 72, "base_pm25": 25.0, "base_pm10": 50.0},
    {"code": "HN-LONGHIEN", "name": "Trạm Long Biên", "address": "Đường Ngô Gia Tự, Long Biên, Hà Nội", "area_type": "Dân cư sinh thái", "latitude": 21.055, "longitude": 105.892, "base_aqi": 48, "base_pm25": 16.2, "base_pm10": 32.0},
    {"code": "HN-HADONG", "name": "Trạm Hà Đông", "address": "Đường Quang Trung, Hà Đông, Hà Nội", "area_type": "Đô thị mở rộng", "latitude": 20.972, "longitude": 105.776, "base_aqi": 95, "base_pm25": 35.0, "base_pm10": 68.0},
]


def ensure_tenant_seed(connection: sqlite3.Connection, tenant: str) -> None:
    """Seed initial monitoring stations for demo tenant when empty."""
    if tenant != "demo":
        return
    existing = connection.execute("SELECT COUNT(*) FROM air_stations WHERE tenant = ?", (tenant,)).fetchone()[0]
    if existing > 0:
        return
    from datetime import timedelta
    now_dt = datetime.now(timezone.utc)
    for s in DEFAULT_HANOI_STATIONS:
        insert_station(
            connection,
            tenant=tenant,
            code=s["code"],
            name=s["name"],
            address=s["address"],
            area_type=s["area_type"],
            latitude=s["latitude"],
            longitude=s["longitude"],
            status="active",
            created_at=now_dt.isoformat(),
        )
        for h in range(24, -1, -1):
            rec_dt = now_dt - timedelta(hours=h)
            variance = ((h * 7 + int(s["latitude"] * 100)) % 15) - 7
            aqi = max(15, s["base_aqi"] + variance)
            pm25 = max(5.0, s["base_pm25"] + variance * 0.4)
            pm10 = max(10.0, s["base_pm10"] + variance * 0.7)
            insert_reading(
                connection,
                reading_id=str(uuid4()),
                tenant=tenant,
                station_code=s["code"],
                aqi=aqi,
                pm25=pm25,
                pm10=pm10,
                temperature=round(26.0 + variance * 0.15, 1),
                humidity=round(68.0 - variance * 0.3, 1),
                co=round(0.8 + variance * 0.02, 2),
                no2=round(28.0 + variance * 0.5, 1),
                o3=round(45.0 + variance * 0.8, 1),
                so2=round(12.0 + variance * 0.2, 1),
                note="Dữ liệu quan trắc tự động QCVN 05:2023/BTNMT",
                recorded_at=rec_dt.isoformat(),
            )


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
