# SPDX-License-Identifier: Apache-2.0
from contextlib import closing
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sqlite3
import unicodedata
from typing import Any
from uuid import uuid4

FACILITIES_DB_PATH = os.getenv("FACILITIES_DB_PATH", "data/facilities.sqlite3")
FACILITIES_SEED_PATH = os.getenv("FACILITIES_SEED_PATH", "data/facilities_osm.geojson")


def _unaccent(s: str | None) -> str:
    if not s:
        return ""
    normalized = unicodedata.normalize("NFKD", str(s))
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    stripped = stripped.replace("đ", "d").replace("Đ", "d")
    return stripped.lower()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


def _db_connection() -> sqlite3.Connection:
    db_path = Path(FACILITIES_DB_PATH)
    if not db_path.is_absolute():
        backend_root = Path(__file__).resolve().parents[2]
        candidate = backend_root / db_path
        db_path = candidate
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.create_function("py_lower", 1, _unaccent)
    return conn


def _extract_centroid(geom: dict[str, Any]) -> tuple[float, float] | None:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None
    if gtype == "Point":
        return float(coords[1]), float(coords[0])  # lat, lon
    if gtype == "Polygon" and coords and coords[0]:
        ring = coords[0]
        return sum(pt[1] for pt in ring) / len(ring), sum(pt[0] for pt in ring) / len(ring)
    return None


def _classify_osm_facility(props: dict[str, Any], name: str) -> tuple[str, str]:
    amenity = str(props.get("amenity") or "").lower()
    name_lower = name.lower()

    if amenity == "hospital" or "bệnh viện" in name_lower:
        return "hospital", "healthcare"
    if amenity == "clinic" or "phòng khám" in name_lower or "trung tâm y tế" in name_lower:
        return "clinic", "healthcare"
    if amenity == "pharmacy" or "nhà thuốc" in name_lower or "quầy thuốc" in name_lower:
        return "pharmacy", "healthcare"
    if amenity == "university" or any(k in name_lower for k in ["đại học", "học viện"]):
        return "university", "education"
    if amenity == "school":
        if any(k in name_lower for k in ["thpt", "trung học phổ thông", "cấp 3", "chuyên"]):
            return "high_school", "education"
        if any(k in name_lower for k in ["thcs", "trung học cơ sở", "cấp 2"]):
            return "secondary_school", "education"
        if any(k in name_lower for k in ["tiểu học", "cấp 1", "primary"]):
            return "primary_school", "education"
        if any(k in name_lower for k in ["mầm non", "kindergarten"]):
            return "kindergarten", "education"
        return "high_school", "education"

    if any(k in name_lower for k in ["học viện", "đại học", "cao đẳng"]):
        return "university", "education"
    return "high_school", "education"


def ensure_facilities_db() -> None:
    conn = _db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facilities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                facility_type TEXT NOT NULL,
                address TEXT NOT NULL,
                district TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                operator_type TEXT NOT NULL DEFAULT 'Công lập',
                opening_hours TEXT NOT NULL DEFAULT '07:30 - 17:00',
                phone TEXT,
                emergency_phone TEXT,
                level TEXT,
                description TEXT DEFAULT '',
                website TEXT,
                connecting_bus_routes TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fac_cat ON facilities(category);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fac_type ON facilities(facility_type);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fac_district ON facilities(district);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fac_active ON facilities(active);")

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM facilities;")
        count = cur.fetchone()[0]
        if count == 0:
            osm_candidates = [
                Path("data/facilities_osm.geojson"),
                Path("opencity-backend-main/data/facilities_osm.geojson"),
                Path(__file__).resolve().parents[2] / "data/facilities_osm.geojson",
                Path(FACILITIES_SEED_PATH),
            ]
            osm_path = next((p for p in osm_candidates if p.exists()), None)
            if osm_path:
                now = datetime.now(timezone.utc).isoformat()
                with open(osm_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for idx, feat in enumerate(data.get("features", [])):
                    props = feat.get("properties", {})
                    geom = feat.get("geometry", {})
                    coords = _extract_centroid(geom)
                    if not coords:
                        continue
                    lat, lon = coords
                    name = props.get("name") or props.get("name:vi") or props.get("name:en")
                    if not name or len(name.strip()) < 2:
                        continue
                    name = name.strip()

                    cat, ftype = _classify_osm_facility(props, name)
                    raw_id = props.get("@id") or props.get("id") or f"fac-{idx}"
                    clean_id = f"osm-{str(raw_id).replace('/', '-')}"

                    dist = props.get("addr:district") or props.get("district") or "Hà Nội"
                    if dist in ("Hà Nội", "") or len(dist) > 50:
                        dist = "Hà Nội"

                    street = props.get("addr:street", "")
                    house = props.get("addr:housenumber", "")
                    addr_parts = [house, street, dist if dist != "Hà Nội" else "", "Hà Nội"]
                    addr = ", ".join([p for p in addr_parts if p]) or f"{name}, {dist}"

                    em_phone = "115" if props.get("emergency") == "yes" or cat == "hospital" else None
                    ph = props.get("phone") or props.get("contact:phone")
                    hours = props.get("opening_hours") or ("Cấp cứu 24/7" if em_phone else "07:30 - 17:00")
                    web = props.get("website") or props.get("contact:website")
                    lvl = "Bệnh viện Tuyến Đô thị" if cat == "hospital" else ("Trường Chuẩn Quốc gia" if "school" in cat else None)

                    cur.execute("""
                        INSERT OR IGNORE INTO facilities (
                            id, name, category, facility_type, address, district,
                            latitude, longitude, operator_type, opening_hours,
                            phone, emergency_phone, level, description, website,
                            connecting_bus_routes, tags, active, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', 1, ?, ?);
                    """, (
                        clean_id, name, cat, ftype, addr, dist, lat, lon,
                        props.get("operator:type", "Công lập"), hours,
                        ph, em_phone, lvl, "", web, now, now
                    ))
    conn.close()


def query_facilities(
    keyword: str | None = None,
    category: str | None = None,
    facility_type: str | None = None,
    district: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
    emergency_only: bool = False,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    ensure_facilities_db()
    conn = _db_connection()
    try:
        sql = "SELECT * FROM facilities WHERE 1=1"
        params: list[Any] = []

        if active_only:
            sql += " AND active = 1"
        if category and category != "all":
            sql += " AND category = ?"
            params.append(category)
        if facility_type and facility_type != "all":
            sql += " AND facility_type = ?"
            params.append(facility_type)
        if district and district != "all":
            sql += " AND district = ?"
            params.append(district)
        if emergency_only:
            sql += " AND emergency_phone IS NOT NULL AND emergency_phone != ''"
        if keyword:
            sql += " AND (py_lower(name) LIKE ? OR py_lower(address) LIKE ? OR py_lower(tags) LIKE ?)"
            pat = f"%{_unaccent(keyword)}%"
            params.extend([pat, pat, pat])

        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()

        results = []
        for r in rows:
            dist_km = None
            if lat is not None and lon is not None:
                dist_km = haversine_km(lat, lon, r["latitude"], r["longitude"])
                if radius_km is not None and dist_km > radius_km:
                    continue

            results.append({
                "id": r["id"],
                "name": r["name"],
                "category": r["category"],
                "facility_type": r["facility_type"],
                "address": r["address"],
                "district": r["district"],
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "operator_type": r["operator_type"],
                "opening_hours": r["opening_hours"],
                "phone": r["phone"],
                "emergency_phone": r["emergency_phone"],
                "level": r["level"],
                "distance_km": dist_km,
                "tags": json.loads(r["tags"] or "[]"),
            })

        if lat is not None and lon is not None:
            results.sort(key=lambda x: x["distance_km"] if x["distance_km"] is not None else 99999)
        else:
            results.sort(key=lambda x: x["name"])

        return results
    finally:
        conn.close()


def get_facility_by_id(facility_id: str, lat: float | None = None, lon: float | None = None) -> dict[str, Any] | None:
    ensure_facilities_db()
    conn = _db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM facilities WHERE id = ?;", (facility_id,))
        r = cur.fetchone()
        if not r:
            return None
        dist_km = None
        if lat is not None and lon is not None:
            dist_km = haversine_km(lat, lon, r["latitude"], r["longitude"])

        return {
            "id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "facility_type": r["facility_type"],
            "address": r["address"],
            "district": r["district"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "operator_type": r["operator_type"],
            "opening_hours": r["opening_hours"],
            "phone": r["phone"],
            "emergency_phone": r["emergency_phone"],
            "level": r["level"],
            "description": r["description"] or "",
            "website": r["website"],
            "connecting_bus_routes": json.loads(r["connecting_bus_routes"] or "[]"),
            "tags": json.loads(r["tags"] or "[]"),
            "distance_km": dist_km,
            "active": bool(r["active"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
    finally:
        conn.close()


def get_facility_districts(facility_type: str | None = None) -> list[str]:
    ensure_facilities_db()
    conn = _db_connection()
    try:
        cur = conn.cursor()
        if facility_type and facility_type != "all":
            cur.execute("SELECT DISTINCT district FROM facilities WHERE active = 1 AND facility_type = ? ORDER BY district;", (facility_type,))
        else:
            cur.execute("SELECT DISTINCT district FROM facilities WHERE active = 1 ORDER BY district;")
        rows = cur.fetchall()
        return [r[0] for r in rows if r[0]]
    finally:
        conn.close()


def get_facility_categories() -> list[dict[str, Any]]:
    ensure_facilities_db()
    conn = _db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT category, facility_type, COUNT(*) as cnt
            FROM facilities
            WHERE active = 1
            GROUP BY category, facility_type;
        """)
        rows = cur.fetchall()
        label_map = {
            "hospital": ("Bệnh viện", "HeartPulse", "healthcare"),
            "clinic": ("Phòng khám & TTYT", "Stethoscope", "healthcare"),
            "pharmacy": ("Nhà thuốc GPP", "Pill", "healthcare"),
            "university": ("Đại học & Học viện", "GraduationCap", "education"),
            "high_school": ("Trường THPT", "School", "education"),
            "secondary_school": ("Trường THCS", "BookOpen", "education"),
            "primary_school": ("Trường Tiểu học", "Smile", "education"),
            "kindergarten": ("Trường Mầm non", "Baby", "education"),
        }
        res = []
        for r in rows:
            cat = r["category"]
            meta = label_map.get(cat, (cat.title(), "Building", r["facility_type"]))
            res.append({
                "key": cat,
                "label": meta[0],
                "icon": meta[1],
                "facility_type": meta[2],
                "count": r["cnt"],
            })
        return res
    finally:
        conn.close()


def create_facility(data: dict[str, Any]) -> dict[str, Any]:
    ensure_facilities_db()
    conn = _db_connection()
    try:
        new_id = f"fac-{uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            conn.execute("""
                INSERT INTO facilities (
                    id, name, category, facility_type, address, district,
                    latitude, longitude, operator_type, opening_hours,
                    phone, emergency_phone, level, description, website,
                    connecting_bus_routes, tags, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                new_id, data["name"], data["category"], data.get("facility_type", "healthcare"),
                data["address"], data["district"], data["latitude"], data["longitude"],
                data.get("operator_type", "Công lập"), data.get("opening_hours", "07:30 - 17:00"),
                data.get("phone"), data.get("emergency_phone"), data.get("level"),
                data.get("description", ""), data.get("website"),
                json.dumps(data.get("connecting_bus_routes", []), ensure_ascii=False),
                json.dumps(data.get("tags", []), ensure_ascii=False),
                1 if data.get("active", True) else 0, now, now
            ))
        return get_facility_by_id(new_id)  # type: ignore
    finally:
        conn.close()


def update_facility(facility_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    ensure_facilities_db()
    conn = _db_connection()
    try:
        now = datetime.now(timezone.utc).isoformat()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE facilities
                SET name = ?, category = ?, facility_type = ?, address = ?, district = ?,
                    latitude = ?, longitude = ?, operator_type = ?, opening_hours = ?,
                    phone = ?, emergency_phone = ?, level = ?, description = ?, website = ?,
                    connecting_bus_routes = ?, tags = ?, active = ?, updated_at = ?
                WHERE id = ?;
            """, (
                data["name"], data["category"], data.get("facility_type", "healthcare"),
                data["address"], data["district"], data["latitude"], data["longitude"],
                data.get("operator_type", "Công lập"), data.get("opening_hours", "07:30 - 17:00"),
                data.get("phone"), data.get("emergency_phone"), data.get("level"),
                data.get("description", ""), data.get("website"),
                json.dumps(data.get("connecting_bus_routes", []), ensure_ascii=False),
                json.dumps(data.get("tags", []), ensure_ascii=False),
                1 if data.get("active", True) else 0, now, facility_id
            ))
            if cur.rowcount == 0:
                return None
        return get_facility_by_id(facility_id)
    finally:
        conn.close()


def delete_facility(facility_id: str) -> bool:
    ensure_facilities_db()
    conn = _db_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM facilities WHERE id = ?;", (facility_id,))
            return cur.rowcount > 0
    finally:
        conn.close()
