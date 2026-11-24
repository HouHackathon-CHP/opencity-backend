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

PARKING_DB_PATH = os.getenv("PARKING_DB_PATH", "data/parking.sqlite3")
PARKING_SEED_PATH = os.getenv("PARKING_SEED_PATH", "data/parking_osm.geojson")
PARKING_FOOTPRINTS_PATH = os.getenv("PARKING_FOOTPRINTS_PATH", "data/parking_footprints.geojson")

HANOI_DISTRICT_CENTERS = [
    ("Hoàn Kiếm", 21.0285, 105.8542),
    ("Ba Đình", 21.0345, 105.8242),
    ("Đống Đa", 21.0135, 105.8258),
    ("Hai Bà Trưng", 21.0068, 105.8562),
    ("Cầu Giấy", 21.0360, 105.7905),
    ("Tây Hồ", 21.0712, 105.8245),
    ("Thanh Xuân", 20.9930, 105.8010),
    ("Hoàng Mai", 20.9725, 105.8530),
    ("Long Biên", 21.0450, 105.8900),
    ("Hà Đông", 20.9720, 105.7730),
    ("Nam Từ Liêm", 21.0150, 105.7650),
    ("Bắc Từ Liêm", 21.0650, 105.7600),
    ("Gia Lâm", 21.0200, 105.9400),
    ("Đông Anh", 21.1400, 105.8450),
    ("Thanh Trì", 20.9450, 105.8400),
    ("Hoài Đức", 21.0200, 105.7000),
]


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


def _guess_district(lat: float, lon: float) -> str:
    best_dist = "Hoàn Kiếm"
    min_d = float("inf")
    for d_name, d_lat, d_lon in HANOI_DISTRICT_CENTERS:
        d = haversine_km(lat, lon, d_lat, d_lon)
        if d < min_d:
            min_d = d
            best_dist = d_name
    return best_dist


def _db_connection() -> sqlite3.Connection:
    db_path = Path(PARKING_DB_PATH)
    if not db_path.is_absolute():
        backend_root = Path(__file__).resolve().parents[2]
        candidate = backend_root / db_path
        db_path = candidate
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.create_function("py_lower", 1, _unaccent)
    return conn


def _extract_coords(geom: dict[str, Any]) -> tuple[float, float] | None:
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


def ensure_parking_db() -> None:
    conn = _db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS parking (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                parking_type TEXT NOT NULL,
                address TEXT NOT NULL,
                district TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                fee TEXT NOT NULL DEFAULT 'Có phí',
                fee_details TEXT,
                capacity INTEGER,
                access TEXT NOT NULL DEFAULT 'Công cộng',
                supervised INTEGER NOT NULL DEFAULT 1,
                opening_hours TEXT NOT NULL DEFAULT '24/7',
                operator TEXT,
                description TEXT DEFAULT '',
                contact TEXT,
                tags TEXT DEFAULT '[]',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_park_cat ON parking(category);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_park_type ON parking(parking_type);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_park_district ON parking(district);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_park_active ON parking(active);")

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM parking;")
        count = cur.fetchone()[0]
        if count == 0:
            candidates = [
                Path("data/parking_osm.geojson"),
                Path("opencity-backend-main/data/parking_osm.geojson"),
                Path(__file__).resolve().parents[2] / "data/parking_osm.geojson",
                Path(PARKING_SEED_PATH),
            ]
            osm_path = next((p for p in candidates if p.exists()), None)
            if osm_path:
                now = datetime.now(timezone.utc).isoformat()
                with open(osm_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                counter = 1
                for idx, feat in enumerate(data.get("features", [])):
                    props = feat.get("properties", {})
                    geom = feat.get("geometry", {})
                    coords = _extract_coords(geom)
                    if not coords:
                        continue
                    lat, lon = coords
                    if not (20.5 <= lat <= 21.5 and 105.3 <= lon <= 106.3):
                        continue

                    raw_id = str(props.get("osm_id") or props.get("id") or props.get("@id") or feat.get("id") or f"park-{idx}").replace("/", "-").replace("@", "")
                    clean_id = f"osm-park-{raw_id}"

                    amenity = str(props.get("amenity") or "parking").lower()
                    ptype_raw = str(props.get("parking") or "surface").lower()

                    # Classify category
                    if amenity == "motorcycle_parking":
                        category = "motorcycle_parking"
                    elif ptype_raw in ("street_side", "lane", "on_kerb"):
                        category = "street_parking"
                    elif ptype_raw in ("underground", "multi-storey"):
                        category = "car_parking"
                    else:
                        category = "car_parking" if idx % 3 == 0 else "mixed_parking"

                    # Classify parking_type
                    if ptype_raw in ("underground", "basement"):
                        parking_type = "underground"
                    elif ptype_raw in ("multi-storey", "building"):
                        parking_type = "multi-storey"
                    elif ptype_raw in ("street_side", "lane", "shoulder", "on_kerb"):
                        parking_type = "street_side"
                    elif ptype_raw in ("rooftop",):
                        parking_type = "rooftop"
                    else:
                        parking_type = "surface"

                    # District
                    dist = props.get("addr:district") or props.get("district")
                    if not dist or dist == "Hà Nội" or len(dist) > 50:
                        dist = _guess_district(lat, lon)

                    # Street & Address
                    street = props.get("addr:street") or props.get("street") or ""
                    house = props.get("addr:housenumber") or ""

                    # Name
                    name = props.get("name") or props.get("name:vi") or props.get("name:en")
                    if not name or len(name.strip()) < 2:
                        if category == "motorcycle_parking":
                            prefix = "Bãi gửi xe máy"
                        elif parking_type == "underground":
                            prefix = "Hầm đỗ xe thông minh"
                        elif parking_type == "multi-storey":
                            prefix = "Nhà để xe cao tầng"
                        elif parking_type == "street_side":
                            prefix = "Điểm đỗ xe lòng đường"
                        else:
                            prefix = "Bãi đỗ xe công cộng"

                        loc_str = street if street else f"Khu vực {dist}"
                        name = f"{prefix} {loc_str}"
                        if street and house:
                            name = f"{prefix} {house} {street}"
                    else:
                        name = name.strip()

                    # Address formatting
                    addr_parts = [house, street, dist, "Hà Nội"]
                    addr = ", ".join([p for p in addr_parts if p]) if (house or street) else f"{name}, {dist}, Hà Nội"

                    # Fee
                    fee_raw = str(props.get("fee") or "").lower()
                    if fee_raw == "no" or "miễn phí" in name.lower():
                        fee = "Miễn phí"
                        fee_details = "Miễn phí cho khách gửi"
                    else:
                        fee = "Có phí"
                        if category == "motorcycle_parking":
                            fee_details = "5.000đ - 10.000đ / lượt"
                        elif category == "car_parking":
                            fee_details = "25.000đ - 50.000đ / lượt (hoặc theo giờ)"
                        else:
                            fee_details = "5.000đ (xe máy) • 25.000đ - 30.000đ (ô tô)"

                    # Capacity
                    cap_raw = props.get("capacity")
                    capacity = None
                    if cap_raw:
                        try:
                            capacity = int(str(cap_raw).split(";")[0].strip())
                        except ValueError:
                            pass
                    if not capacity:
                        if parking_type == "multi-storey":
                            capacity = 150 + (counter * 17) % 350
                        elif parking_type == "underground":
                            capacity = 200 + (counter * 23) % 400
                        elif parking_type == "street_side":
                            capacity = 20 + (counter * 7) % 40
                        else:
                            capacity = 50 + (counter * 13) % 150

                    # Access
                    acc_raw = str(props.get("access") or "").lower()
                    if acc_raw in ("private", "no"):
                        access = "Nội bộ"
                    elif acc_raw in ("customers", "permit"):
                        access = "Khách hàng"
                    else:
                        access = "Công cộng"

                    # Supervised
                    sup_raw = str(props.get("supervised") or "").lower()
                    supervised = 1 if sup_raw != "no" else 1  # hầu hết bãi ở HN có người trông

                    # Hours
                    hours = props.get("opening_hours") or ("24/7" if idx % 2 == 0 else "06:00 - 23:00")
                    operator_val = props.get("operator") or "UBND Quận / Công ty Khai thác Điểm đỗ xe Hà Nội"

                    tags = [category, parking_type, dist]
                    if fee == "Miễn phí":
                        tags.append("miễn phí")
                    if hours == "24/7":
                        tags.append("24/7")

                    cur.execute("""
                        INSERT OR IGNORE INTO parking (
                            id, name, category, parking_type, address, district,
                            latitude, longitude, fee, fee_details, capacity,
                            access, supervised, opening_hours, operator,
                            description, contact, tags, active, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, 1, ?, ?);
                    """, (
                        clean_id, name, category, parking_type, addr, dist,
                        lat, lon, fee, fee_details, capacity, access, supervised,
                        hours, operator_val, props.get("phone"), json.dumps(tags), now, now
                    ))
                    counter += 1
    conn.close()


def query_parking(
    keyword: str | None = None,
    category: str | None = None,
    parking_type: str | None = None,
    district: str | None = None,
    fee_type: str | None = None,
    is_24_7: bool = False,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
) -> list[dict[str, Any]]:
    ensure_parking_db()
    conn = _db_connection()
    with closing(conn.cursor()) as cur:
        conditions = ["active = 1"]
        params: list[Any] = []

        if keyword and keyword.strip():
            kw = f"%{_unaccent(keyword.strip())}%"
            conditions.append("(py_lower(name) LIKE ? OR py_lower(address) LIKE ? OR py_lower(operator) LIKE ?)")
            params.extend([kw, kw, kw])

        if category and category != "all":
            conditions.append("category = ?")
            params.append(category)

        if parking_type and parking_type != "all":
            conditions.append("parking_type = ?")
            params.append(parking_type)

        if district and district != "all":
            conditions.append("district = ?")
            params.append(district)

        if fee_type and fee_type != "all":
            if fee_type == "free":
                conditions.append("fee = 'Miễn phí'")
            elif fee_type == "paid":
                conditions.append("fee = 'Có phí'")

        if is_24_7:
            conditions.append("(opening_hours = '24/7' OR py_lower(opening_hours) LIKE '%24/7%')")

        where_clause = " WHERE " + " AND ".join(conditions)
        sql = f"""
            SELECT id, name, category, parking_type, address, district,
                   latitude, longitude, fee, fee_details, capacity, access,
                   supervised, opening_hours, operator, tags
            FROM parking
            {where_clause}
            ORDER BY name ASC;
        """
        cur.execute(sql, params)
        rows = cur.fetchall()

    conn.close()

    results: list[dict[str, Any]] = []
    has_gps = lat is not None and lon is not None

    for r in rows:
        d_km = None
        if has_gps:
            d_km = haversine_km(lat, lon, r["latitude"], r["longitude"])
            if radius_km and d_km > radius_km:
                continue

        try:
            tags_list = json.loads(r["tags"] or "[]")
        except Exception:
            tags_list = []

        results.append({
            "id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "parking_type": r["parking_type"],
            "address": r["address"],
            "district": r["district"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "fee": r["fee"],
            "fee_details": r["fee_details"],
            "capacity": r["capacity"],
            "access": r["access"],
            "supervised": bool(r["supervised"]),
            "opening_hours": r["opening_hours"],
            "operator": r["operator"],
            "distance_km": d_km,
            "tags": tags_list,
        })

    if has_gps:
        results.sort(key=lambda x: (x["distance_km"] if x["distance_km"] is not None else 9999))

    return results


def get_parking_by_id(parking_id: str, lat: float | None = None, lon: float | None = None) -> dict[str, Any] | None:
    ensure_parking_db()
    conn = _db_connection()
    with closing(conn.cursor()) as cur:
        cur.execute("""
            SELECT id, name, category, parking_type, address, district,
                   latitude, longitude, fee, fee_details, capacity, access,
                   supervised, opening_hours, operator, description, contact,
                   tags, active, created_at, updated_at
            FROM parking
            WHERE id = ? AND active = 1;
        """, (parking_id,))
        row = cur.fetchone()
    conn.close()

    if not row:
        return None

    d_km = None
    if lat is not None and lon is not None:
        d_km = haversine_km(lat, lon, row["latitude"], row["longitude"])

    try:
        tags_list = json.loads(row["tags"] or "[]")
    except Exception:
        tags_list = []

    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "parking_type": row["parking_type"],
        "address": row["address"],
        "district": row["district"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "fee": row["fee"],
        "fee_details": row["fee_details"],
        "capacity": row["capacity"],
        "access": row["access"],
        "supervised": bool(row["supervised"]),
        "opening_hours": row["opening_hours"],
        "operator": row["operator"],
        "description": row["description"] or "",
        "contact": row["contact"],
        "distance_km": d_km,
        "tags": tags_list,
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_parking_categories() -> list[dict[str, Any]]:
    ensure_parking_db()
    conn = _db_connection()
    with closing(conn.cursor()) as cur:
        cur.execute("SELECT category, COUNT(*) as cnt FROM parking WHERE active = 1 GROUP BY category;")
        counts = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()

    cat_defs = [
        {"key": "all", "label": "Tất cả điểm đỗ", "icon": "SquareParking"},
        {"key": "car_parking", "label": "Bãi đỗ ô tô", "icon": "Car"},
        {"key": "motorcycle_parking", "label": "Điểm đỗ xe máy", "icon": "Bike"},
        {"key": "mixed_parking", "label": "Bãi gửi chung", "icon": "Layers"},
        {"key": "street_parking", "label": "Đỗ xe lòng đường", "icon": "Road"},
    ]

    result = []
    total = sum(counts.values())
    for cd in cat_defs:
        c = total if cd["key"] == "all" else counts.get(cd["key"], 0)
        result.append({
            "key": cd["key"],
            "label": cd["label"],
            "count": c,
            "icon": cd["icon"],
        })
    return result


def get_parking_districts() -> list[str]:
    ensure_parking_db()
    conn = _db_connection()
    with closing(conn.cursor()) as cur:
        cur.execute("""
            SELECT DISTINCT district FROM parking
            WHERE active = 1 AND district IS NOT NULL AND district != ''
            ORDER BY district ASC;
        """)
        dists = [r[0] for r in cur.fetchall()]
    conn.close()
    return dists


def create_parking(data: dict[str, Any]) -> dict[str, Any]:
    ensure_parking_db()
    conn = _db_connection()
    now = datetime.now(timezone.utc).isoformat()
    pid = f"park-{uuid4().hex[:10]}"

    tags_json = json.dumps(data.get("tags") or [data.get("category", "car_parking"), data.get("district", "Hà Nội")])
    with conn:
        conn.execute("""
            INSERT INTO parking (
                id, name, category, parking_type, address, district,
                latitude, longitude, fee, fee_details, capacity,
                access, supervised, opening_hours, operator,
                description, contact, tags, active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            pid,
            data["name"],
            data.get("category", "car_parking"),
            data.get("parking_type", "surface"),
            data["address"],
            data["district"],
            float(data["latitude"]),
            float(data["longitude"]),
            data.get("fee", "Có phí"),
            data.get("fee_details"),
            data.get("capacity"),
            data.get("access", "Công cộng"),
            1 if data.get("supervised", True) else 0,
            data.get("opening_hours", "24/7"),
            data.get("operator"),
            data.get("description", ""),
            data.get("contact"),
            tags_json,
            1 if data.get("active", True) else 0,
            now,
            now,
        ))
    conn.close()
    return get_parking_by_id(pid)  # type: ignore


def update_parking(parking_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    ensure_parking_db()
    conn = _db_connection()
    now = datetime.now(timezone.utc).isoformat()

    existing = get_parking_by_id(parking_id)
    if not existing:
        conn.close()
        return None

    tags_json = json.dumps(data.get("tags") or existing.get("tags", []))
    with conn:
        conn.execute("""
            UPDATE parking
            SET name = ?, category = ?, parking_type = ?, address = ?, district = ?,
                latitude = ?, longitude = ?, fee = ?, fee_details = ?, capacity = ?,
                access = ?, supervised = ?, opening_hours = ?, operator = ?,
                description = ?, contact = ?, tags = ?, active = ?, updated_at = ?
            WHERE id = ?;
        """, (
            data.get("name", existing["name"]),
            data.get("category", existing["category"]),
            data.get("parking_type", existing["parking_type"]),
            data.get("address", existing["address"]),
            data.get("district", existing["district"]),
            float(data.get("latitude", existing["latitude"])),
            float(data.get("longitude", existing["longitude"])),
            data.get("fee", existing["fee"]),
            data.get("fee_details", existing.get("fee_details")),
            data.get("capacity", existing.get("capacity")),
            data.get("access", existing["access"]),
            1 if data.get("supervised", existing["supervised"]) else 0,
            data.get("opening_hours", existing["opening_hours"]),
            data.get("operator", existing.get("operator")),
            data.get("description", existing.get("description", "")),
            data.get("contact", existing.get("contact")),
            tags_json,
            1 if data.get("active", existing.get("active", True)) else 0,
            now,
            parking_id,
        ))
    conn.close()
    return get_parking_by_id(parking_id)


def delete_parking(parking_id: str) -> bool:
    ensure_parking_db()
    conn = _db_connection()
    with conn:
        cur = conn.execute("UPDATE parking SET active = 0, updated_at = ? WHERE id = ?;", (
            datetime.now(timezone.utc).isoformat(),
            parking_id,
        ))
        rowcount = cur.rowcount
    conn.close()
    return rowcount > 0


_footprints_cache: dict[str, Any] | None = None


def get_footprints() -> dict[str, Any]:
    global _footprints_cache
    if _footprints_cache is not None:
        return _footprints_cache

    candidates = [
        Path(PARKING_FOOTPRINTS_PATH),
        Path("opencity-backend-main") / PARKING_FOOTPRINTS_PATH,
        Path(__file__).resolve().parents[2] / PARKING_FOOTPRINTS_PATH,
        Path("/service/data/parking_footprints.geojson"),
    ]
    for p in candidates:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                _footprints_cache = json.load(f)
                return _footprints_cache

    return {"type": "FeatureCollection", "features": []}
