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

TOURISM_DB_PATH = os.getenv("TOURISM_DB_PATH", "data/tourism.sqlite3")
TOURISM_SEED_PATH = os.getenv("TOURISM_SEED_PATH", "data/tourism_osm.geojson")


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
    db_path = Path(TOURISM_DB_PATH)
    if not db_path.exists() or db_path.stat().st_size < 10_000:
        alt_path = Path("opencity-backend-main") / db_path
        if alt_path.exists() and alt_path.stat().st_size > (db_path.stat().st_size if db_path.exists() else 0):
            db_path = alt_path
        elif not db_path.is_absolute():
            backend_root = Path(__file__).resolve().parents[2]
            candidate = backend_root / db_path
            if candidate.exists() and candidate.stat().st_size > (db_path.stat().st_size if db_path.exists() else 0):
                db_path = candidate
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.create_function("py_lower", 1, _unaccent)
    return conn


def _extract_centroid(geometry: dict[str, Any]) -> tuple[float, float] | None:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if not coords:
        return None
    if gtype == "Point":
        return float(coords[1]), float(coords[0])  # lat, lon
    elif gtype == "Polygon":
        ring = coords[0]
        if not ring:
            return None
        lons = [pt[0] for pt in ring]
        lats = [pt[1] for pt in ring]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    elif gtype in ("MultiLineString", "LineString"):
        pts = [pt for line in coords for pt in line] if gtype == "MultiLineString" else coords
        if not pts:
            return None
        lons = [pt[0] for pt in pts]
        lats = [pt[1] for pt in pts]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    elif gtype == "MultiPolygon":
        if not coords or not coords[0] or not coords[0][0]:
            return None
        ring = coords[0][0]
        lons = [pt[0] for pt in ring]
        lats = [pt[1] for pt in ring]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    return None


def _classify_osm_category(props: dict[str, Any], name: str) -> str:
    tourism_tag = str(props.get("tourism") or "").lower()
    historic_tag = str(props.get("historic") or "").lower()
    amenity_tag = str(props.get("amenity") or "").lower()
    name_lower = name.lower()

    if tourism_tag == "museum" or "bảo tàng" in name_lower:
        return "museum"
    if amenity_tag == "place_of_worship" or any(w in name_lower for w in ["chùa", "đền", "miếu", "đình", "nhà thờ"]):
        return "religious"
    if historic_tag in ("monument", "memorial", "castle", "city_gate", "ruins", "archaeological_site", "fort"):
        return "monument"
    if tourism_tag in ("viewpoint", "park", "theme_park") or "hồ " in name_lower or "công viên" in name_lower:
        return "landscape"
    if tourism_tag in ("attraction", "gallery", "artwork") or "nhà hát" in name_lower or "trung tâm văn hóa" in name_lower:
        return "cultural"
    return "monument"


def _generate_osm_id(props: dict[str, Any], name: str, idx: int) -> str:
    raw_id = props.get("@id") or props.get("id")
    if raw_id:
        return f"osm-{str(raw_id).replace('/', '-')}"
    unaccented = _unaccent(name).replace(" ", "-")
    clean = "".join(c for c in unaccented if c.isalnum() or c == "-")
    return f"{clean}-{idx}" if clean else f"osm-poi-{idx}"


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tourism_destinations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            address TEXT NOT NULL,
            district TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            heritage_level TEXT NOT NULL,
            description TEXT NOT NULL,
            opening_hours TEXT NOT NULL,
            admission_fee TEXT NOT NULL,
            connecting_bus_routes TEXT NOT NULL,
            osm_id TEXT,
            tags TEXT NOT NULL,
            audio_guide INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tourism_category ON tourism_destinations (category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tourism_district ON tourism_destinations (district)")


def init_db() -> None:
    with closing(_db_connection()) as conn, conn:
        _ensure_tables(conn)
        count = conn.execute("SELECT COUNT(*) FROM tourism_destinations").fetchone()[0]
        if count == 0:
            osm_file = Path("data/tourism_osm.geojson")
            if not osm_file.exists():
                osm_file = Path("opencity-backend-main/data/tourism_osm.geojson")
            
            target = osm_file if osm_file.exists() else Path(TOURISM_SEED_PATH)
            if not target.exists():
                target = Path("opencity-backend-main") / target
            if target.exists():
                with open(target, "r", encoding="utf-8") as f:
                    _populate_features(conn, json.load(f), replace_existing=False)


def import_osm_geojson(data: dict, replace_existing: bool = False) -> int:
    """Import raw OpenStreetMap GeoJSON FeatureCollection into tourism database."""
    with closing(_db_connection()) as conn, conn:
        _ensure_tables(conn)
        return _populate_features(conn, data, replace_existing=replace_existing)


def _populate_features(conn: sqlite3.Connection, data: dict, replace_existing: bool = False) -> int:
    features = data.get("features", [])
    now_str = datetime.now(timezone.utc).isoformat()
    rows = []

    for idx, feat in enumerate(features):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        if not geom:
            continue

        centroid = _extract_centroid(geom)
        if not centroid:
            continue
        lat, lon = centroid

        name = props.get("name") or props.get("name:vi") or props.get("name:en")
        if not name or len(name.strip()) < 2:
            continue
        name = name.strip()

        # Filter: Must be tourism or historic or place_of_worship or monument
        has_tourism = bool(props.get("tourism"))
        has_historic = bool(props.get("historic"))
        has_worship = props.get("amenity") == "place_of_worship"
        has_category = bool(props.get("category"))
        is_heritage = "heritage" in props or "heritage:operator" in props or "heritage_level" in props
        if not (has_tourism or has_historic or has_worship or is_heritage or has_category):
            # Check if name contains heritage indicators
            lower_name = name.lower()
            if not any(k in lower_name for k in ["văn miếu", "hoàng thành", "chùa", "đền", "bảo tàng", "di tích"]):
                continue

        dest_id = props.get("id") or _generate_osm_id(props, name, idx)
        category = props.get("category") or _classify_osm_category(props, name)

        # Address construction
        addr_parts = []
        if props.get("addr:housenumber"):
            addr_parts.append(str(props["addr:housenumber"]))
        if props.get("addr:street"):
            addr_parts.append(str(props["addr:street"]))
        district = props.get("district") or props.get("addr:district") or props.get("addr:subdistrict") or "Hà Nội"
        if district and district not in ("Hà Nội", ""):
            addr_parts.append(district)
        addr_parts.append("Hà Nội")
        address = props.get("address") or ", ".join(addr_parts)

        # Heritage level
        heritage_level = props.get("heritage_level")
        if not heritage_level:
            if "unesco" in props or "heritage:operator" in props:
                heritage_level = "Di sản Thế giới (UNESCO)"
            elif props.get("heritage") in ("1", "national") or "đặc biệt" in name.lower():
                heritage_level = "Di tích Quốc gia đặc biệt"
            else:
                heritage_level = "Di tích Lịch sử - Văn hóa"

        # Description
        description = props.get("description")
        if not description:
            wiki = props.get("wikipedia") or props.get("wikidata")
            if wiki:
                description = f"Điểm đến di sản văn hóa OpenStreetMap (Tham chiếu: {wiki})."
            else:
                description = f"Điểm đến du lịch & di tích văn hóa lịch sử {name} tại {district}, Hà Nội."

        opening_hours = props.get("opening_hours") or "08:00 - 17:00"
        fee = props.get("admission_fee") or props.get("fee") or "Vé tham quan tiêu chuẩn"
        bus_routes = props.get("connecting_bus_routes") or []
        osm_id = props.get("osm_id") or str(props.get("@id") or feat.get("id") or "")
        tags = props.get("tags") or [category, district.lower()]
        audio_guide = 1 if props.get("audio_guide") else 0

        rows.append((
            dest_id,
            name,
            category,
            address,
            district,
            float(lat),
            float(lon),
            heritage_level,
            description,
            opening_hours,
            fee,
            json.dumps(bus_routes, ensure_ascii=False),
            osm_id,
            json.dumps(tags, ensure_ascii=False),
            audio_guide,
            1,
            now_str,
            now_str,
        ))

    with closing(_db_connection()) as conn, conn:
        if replace_existing:
            conn.execute("DELETE FROM tourism_destinations")
        conn.executemany("""
            INSERT OR REPLACE INTO tourism_destinations (
                id, name, category, address, district, latitude, longitude,
                heritage_level, description, opening_hours, admission_fee,
                connecting_bus_routes, osm_id, tags, audio_guide, active,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

    return len(rows)


def list_destinations(
    keyword: str | None = None,
    category: str | None = None,
    district: str | None = None,
    heritage_level: str | None = None,
    audio_guide_only: bool = False,
) -> list[dict[str, Any]]:
    init_db()
    query = "SELECT * FROM tourism_destinations WHERE active = 1"
    params: list[Any] = []

    if keyword:
        kw = f"%{_unaccent(keyword.strip())}%"
        query += " AND (py_lower(name) LIKE ? OR py_lower(address) LIKE ? OR py_lower(tags) LIKE ?)"
        params.extend([kw, kw, kw])
    if category:
        query += " AND category = ?"
        params.append(category)
    if district:
        query += " AND py_lower(district) = py_lower(?)"
        params.append(district)
    if heritage_level:
        query += " AND py_lower(heritage_level) LIKE ?"
        params.append(f"%{heritage_level}%")
    if audio_guide_only:
        query += " AND audio_guide = 1"

    query += " ORDER BY CASE category WHEN 'monument' THEN 1 WHEN 'museum' THEN 2 WHEN 'religious' THEN 3 WHEN 'landscape' THEN 4 ELSE 5 END, name ASC"

    with closing(_db_connection()) as conn:
        rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["connecting_bus_routes"] = json.loads(d.get("connecting_bus_routes") or "[]")
            d["tags"] = json.loads(d.get("tags") or "[]")
            d["audio_guide"] = bool(d.get("audio_guide"))
            d["active"] = bool(d.get("active"))
            result.append(d)
        return result


def get_destination_by_id(destination_id: str) -> dict[str, Any] | None:
    init_db()
    with closing(_db_connection()) as conn:
        row = conn.execute(
            "SELECT * FROM tourism_destinations WHERE id = ? AND active = 1",
            (destination_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["connecting_bus_routes"] = json.loads(d.get("connecting_bus_routes") or "[]")
        d["tags"] = json.loads(d.get("tags") or "[]")
        d["audio_guide"] = bool(d.get("audio_guide"))
        d["active"] = bool(d.get("active"))
        return d


def get_category_counts() -> list[dict[str, Any]]:
    init_db()
    labels = {
        "monument": ("Di tích lịch sử - Văn hóa", "account_balance"),
        "museum": ("Bảo tàng & Nhà triển lãm", "museum"),
        "religious": ("Đền, Chùa, Nhà thờ cổ", "temple_buddhist"),
        "cultural": ("Kiến trúc & Không gian nghệ thuật", "theater_comedy"),
        "landscape": ("Danh thắng & Không gian xanh", "park"),
    }
    with closing(_db_connection()) as conn:
        rows = conn.execute("""
            SELECT category, COUNT(*) as cnt
            FROM tourism_destinations
            WHERE active = 1
            GROUP BY category
            ORDER BY cnt DESC
        """).fetchall()
        result = []
        for r in rows:
            cat = r["category"]
            label, icon = labels.get(cat, (cat.capitalize(), "place"))
            result.append({
                "key": cat,
                "label": label,
                "count": r["cnt"],
                "icon": icon,
            })
        return result


def get_districts() -> list[str]:
    init_db()
    with closing(_db_connection()) as conn:
        rows = conn.execute("""
            SELECT DISTINCT district
            FROM tourism_destinations
            WHERE active = 1 AND district != 'Hà Nội' AND district != ''
            ORDER BY district ASC
        """).fetchall()
        return [r[0] for r in rows]


def create_destination(data: dict[str, Any]) -> dict[str, Any]:
    init_db()
    dest_id = data.get("id") or f"custom-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    bus_routes = json.dumps(data.get("connecting_bus_routes") or [])
    tags = json.dumps(data.get("tags") or [])
    with closing(_db_connection()) as conn, conn:
        conn.execute(
            """
            INSERT INTO tourism_destinations (
                id, name, category, address, district, latitude, longitude,
                heritage_level, description, opening_hours, admission_fee,
                connecting_bus_routes, osm_id, tags, audio_guide, active,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dest_id,
                data["name"],
                data.get("category", "monument"),
                data.get("address", ""),
                data.get("district", "Hà Nội"),
                float(data["latitude"]),
                float(data["longitude"]),
                data.get("heritage_level", "Di tích Lịch sử - Văn hóa"),
                data.get("description", ""),
                data.get("opening_hours", "8:00 - 17:00"),
                data.get("admission_fee", "Miễn phí"),
                bus_routes,
                data.get("osm_id", None),
                tags,
                1 if data.get("audio_guide") else 0,
                1 if data.get("active", True) else 0,
                now,
                now,
            ),
        )
    return get_destination_by_id(dest_id) or data


def update_destination(destination_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    bus_routes = json.dumps(data.get("connecting_bus_routes") or [])
    tags = json.dumps(data.get("tags") or [])
    with closing(_db_connection()) as conn, conn:
        cursor = conn.execute(
            """
            UPDATE tourism_destinations SET
                name = ?, category = ?, address = ?, district = ?,
                latitude = ?, longitude = ?, heritage_level = ?,
                description = ?, opening_hours = ?, admission_fee = ?,
                connecting_bus_routes = ?, tags = ?, audio_guide = ?,
                active = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                data["name"],
                data.get("category", "monument"),
                data.get("address", ""),
                data.get("district", "Hà Nội"),
                float(data["latitude"]),
                float(data["longitude"]),
                data.get("heritage_level", "Di tích Lịch sử - Văn hóa"),
                data.get("description", ""),
                data.get("opening_hours", "8:00 - 17:00"),
                data.get("admission_fee", "Miễn phí"),
                bus_routes,
                tags,
                1 if data.get("audio_guide") else 0,
                1 if data.get("active", True) else 0,
                now,
                destination_id,
            ),
        )
        if cursor.rowcount == 0:
            return None
    return get_destination_by_id(destination_id)


def delete_destination(destination_id: str) -> bool:
    init_db()
    with closing(_db_connection()) as conn, conn:
        cursor = conn.execute("DELETE FROM tourism_destinations WHERE id = ?", (destination_id,))
        return cursor.rowcount > 0

