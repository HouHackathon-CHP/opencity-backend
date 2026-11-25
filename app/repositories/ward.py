# SPDX-License-Identifier: Apache-2.0
from contextlib import closing
import json
import math
import os
from pathlib import Path
import sqlite3
import unicodedata
from typing import Any

from app.schemas.ward import DistrictSummary, WardDetail, WardLocateResult, WardSummary

WARDS_DB_PATH = os.getenv("WARDS_DB_PATH", "data/wards.sqlite3")
WARDS_BOUNDARIES_PATH = os.getenv("WARDS_BOUNDARIES_PATH", "data/wards_boundaries.geojson")

_BOUNDARIES_CACHE: dict[str, Any] | None = None


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


def point_in_polygon(lon: float, lat: float, polygon: list) -> bool:
    """Ray casting algorithm for point-in-polygon test."""
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if lat > min(p1y, p2y):
            if lat <= max(p1y, p2y):
                if lon <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or lon <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def point_in_multipolygon(lon: float, lat: float, geometry: dict) -> bool:
    geom_type = geometry.get("type", "")
    coords = geometry.get("coordinates", [])
    if geom_type == "Polygon":
        # First ring is exterior
        if not coords or not point_in_polygon(lon, lat, coords[0]):
            return False
        # Check interior rings (holes)
        for hole in coords[1:]:
            if point_in_polygon(lon, lat, hole):
                return False
        return True
    elif geom_type == "MultiPolygon":
        for poly in coords:
            if poly and point_in_polygon(lon, lat, poly[0]):
                in_hole = False
                for hole in poly[1:]:
                    if point_in_polygon(lon, lat, hole):
                        in_hole = True
                        break
                if not in_hole:
                    return True
    return False


def _resolve_path(rel_path: str) -> Path:
    p = Path(rel_path)
    if p.exists() and p.stat().st_size > 0:
        return p
    alt = Path("opencity-backend-main") / p
    if alt.exists() and alt.stat().st_size > 0:
        return alt
    root = Path(__file__).resolve().parents[2]
    cand = root / p
    if cand.exists() and cand.stat().st_size > 0:
        return cand
    return p


def _db_connection() -> sqlite3.Connection:
    db_path = _resolve_path(WARDS_DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_boundaries() -> dict[str, Any]:
    global _BOUNDARIES_CACHE
    if _BOUNDARIES_CACHE is not None:
        return _BOUNDARIES_CACHE
    path = _resolve_path(WARDS_BOUNDARIES_PATH)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            _BOUNDARIES_CACHE = json.load(f)
            return _BOUNDARIES_CACHE
    return {"type": "FeatureCollection", "features": []}


def list_wards(
    keyword: str | None = None,
    district: str | None = None,
    ward_type: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[WardSummary]:
    with closing(_db_connection()) as conn:
        query = "SELECT * FROM wards WHERE 1=1"
        params: list[Any] = []

        if district and district.strip() and district != "all":
            query += " AND district = ?"
            params.append(district.strip())

        if ward_type and ward_type.strip() and ward_type != "all":
            query += " AND type = ?"
            params.append(ward_type.strip())

        rows = conn.execute(query, params).fetchall()

    items: list[WardSummary] = []
    kw_norm = _unaccent(keyword).strip() if keyword else None

    for r in rows:
        name = r["name"]
        full_name = r["full_name"]
        dist = r["district"]
        addr = r["office_address"]

        if kw_norm:
            combined = _unaccent(f"{name} {full_name} {dist} {addr}")
            if kw_norm not in combined:
                continue

        dist_km = None
        if lat is not None and lon is not None:
            dist_km = haversine_km(lat, lon, r["center_lat"], r["center_lon"])

        items.append(
            WardSummary(
                id=r["id"],
                code=r["code"],
                name=name,
                full_name=full_name,
                district=dist,
                type=r["type"],
                area_km2=round(r["area_km2"], 2) if r["area_km2"] else 0.0,
                postal_code=r["postal_code"] or "",
                center_lat=r["center_lat"],
                center_lon=r["center_lon"],
                office_address=addr or "",
                phone=r["phone"] or "",
                office_hours=r["office_hours"] or "",
                population=r["population"] or 0,
                distance_km=dist_km,
            )
        )

    if lat is not None and lon is not None:
        items.sort(key=lambda x: x.distance_km if x.distance_km is not None else 9999.0)
    else:
        items.sort(key=lambda x: (x.district, x.name))

    return items[offset : offset + limit]


def list_districts() -> list[DistrictSummary]:
    with closing(_db_connection()) as conn:
        rows = conn.execute("""
            SELECT district, COUNT(*) as count, SUM(area_km2) as total_area, SUM(population) as total_pop
            FROM wards
            GROUP BY district
            ORDER BY district
        """).fetchall()

        type_rows = conn.execute("""
            SELECT district, type, COUNT(*) as cnt
            FROM wards
            GROUP BY district, type
        """).fetchall()

    types_by_district: dict[str, dict[str, int]] = {}
    for tr in type_rows:
        d = tr["district"]
        t = tr["type"]
        types_by_district.setdefault(d, {})[t] = tr["cnt"]

    result = []
    for r in rows:
        d = r["district"]
        result.append(
            DistrictSummary(
                district=d,
                ward_count=r["count"],
                total_area_km2=round(r["total_area"] or 0.0, 2),
                total_population=r["total_pop"] or 0,
                types_count=types_by_district.get(d, {}),
            )
        )
    return result


def get_ward_by_id(ward_id: str) -> WardDetail | None:
    with closing(_db_connection()) as conn:
        r = conn.execute("SELECT * FROM wards WHERE id = ? OR code = ?", (ward_id, ward_id)).fetchone()
        if not r:
            return None
        bbox = [r["min_lon"], r["min_lat"], r["max_lon"], r["max_lat"]]
        return WardDetail(
            id=r["id"],
            code=r["code"],
            name=r["name"],
            full_name=r["full_name"],
            district=r["district"],
            type=r["type"],
            area_km2=round(r["area_km2"], 2) if r["area_km2"] else 0.0,
            postal_code=r["postal_code"] or "",
            center_lat=r["center_lat"],
            center_lon=r["center_lon"],
            office_address=r["office_address"] or "",
            phone=r["phone"] or "",
            office_hours=r["office_hours"] or "",
            population=r["population"] or 0,
            bbox=bbox,
        )


def locate_ward(lat: float, lon: float) -> WardLocateResult | None:
    # 1. Try precise point in polygon match against cached boundaries
    fc = get_boundaries()
    for feat in fc.get("features", []):
        geom = feat.get("geometry", {})
        if point_in_multipolygon(lon, lat, geom):
            wid = feat.get("id") or feat.get("properties", {}).get("code")
            ward_detail = get_ward_by_id(wid)
            if ward_detail:
                dist = haversine_km(lat, lon, ward_detail.center_lat, ward_detail.center_lon)
                ward_detail.distance_km = dist
                return WardLocateResult(ward=ward_detail, distance_km=dist, located_inside=True)

    # 2. Fallback: nearest centroid
    all_wards = list_wards(lat=lat, lon=lon, limit=1)
    if all_wards:
        detail = get_ward_by_id(all_wards[0].id)
        if detail:
            dist = all_wards[0].distance_km or 0.0
            detail.distance_km = dist
            return WardLocateResult(ward=detail, distance_km=dist, located_inside=False)

    return None
