# SPDX-License-Identifier: Apache-2.0
from contextlib import closing
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from typing import Any
import unicodedata
import uuid

from app.core import config

def _unaccent(s: str | None) -> str:
    if not s:
        return ""
    normalized = unicodedata.normalize('NFKD', str(s))
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    stripped = stripped.replace('đ', 'd').replace('Đ', 'd')
    return stripped.lower()


def _db_connection() -> sqlite3.Connection:
    db_path = Path(config.BUS_SEARCH_DB_PATH)
    if not db_path.exists() or db_path.stat().st_size < 100_000:
        alt_path = Path("opencity-backend-main") / db_path
        if alt_path.exists() and alt_path.stat().st_size > (db_path.stat().st_size if db_path.exists() else 0):
            db_path = alt_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.create_function("py_lower", 1, _unaccent)
    return conn


def init_db() -> None:
    with closing(_db_connection()) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bus_routes (
                id TEXT PRIMARY KEY,
                route_number TEXT NOT NULL,
                name TEXT NOT NULL,
                operator TEXT NOT NULL,
                route_type TEXT NOT NULL,
                from_terminal TEXT NOT NULL,
                to_terminal TEXT NOT NULL,
                operating_hours TEXT NOT NULL,
                frequency TEXT NOT NULL,
                fare TEXT NOT NULL,
                color TEXT NOT NULL,
                osm_relation_id TEXT,
                direction_forward_path TEXT NOT NULL,
                direction_backward_path TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bus_stops (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                osm_node_id TEXT,
                has_shelter INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bus_route_stops (
                id TEXT PRIMARY KEY,
                route_id TEXT NOT NULL,
                stop_id TEXT NOT NULL,
                direction TEXT NOT NULL,
                stop_order INTEGER NOT NULL,
                FOREIGN KEY (route_id) REFERENCES bus_routes(id),
                FOREIGN KEY (stop_id) REFERENCES bus_stops(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bus_sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bus_routes_num ON bus_routes(route_number)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bus_route_stops_route ON bus_route_stops(route_id, direction)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bus_route_stops_stop ON bus_route_stops(stop_id)")

        row = conn.execute("SELECT count(*) FROM bus_routes").fetchone()
        if row and row[0] == 0:
            geojson_path = Path(config.BUS_SEARCH_DB_PATH).parent / "export.geojson"
            if not geojson_path.exists():
                geojson_path = Path(__file__).resolve().parents[2] / "data" / "export.geojson"
            if geojson_path.exists():
                try:
                    import json
                    with open(geojson_path, "r", encoding="utf-8") as f:
                        geo_data = json.load(f)
                    import_osm_geojson(geo_data, replace_existing=False)
                except Exception:
                    pass


def list_routes(
    keyword: str | None = None,
    route_type: str | None = None,
    operator: str | None = None,
) -> list[dict]:
    init_db()
    with closing(_db_connection()) as conn:
        query = "SELECT * FROM bus_routes WHERE active = 1"
        params: list[Any] = []

        if keyword:
            kw = f"%{_unaccent(keyword)}%"
            query += " AND (py_lower(route_number) LIKE ? OR py_lower(name) LIKE ? OR py_lower(from_terminal) LIKE ? OR py_lower(to_terminal) LIKE ?)"
            params.extend([kw, kw, kw, kw])

        if route_type:
            query += " AND route_type = ?"
            params.append(route_type.strip().lower())

        if operator:
            query += " AND py_lower(operator) LIKE ?"
            params.append(f"%{_unaccent(operator)}%")

        query += " ORDER BY CAST(route_number AS INTEGER), route_number ASC"
        rows = conn.execute(query, params).fetchall()

        result = []
        for r in rows:
            route_id = r["id"]
            fwd_count = conn.execute(
                "SELECT COUNT(*) FROM bus_route_stops WHERE route_id = ? AND direction = 'forward'",
                (route_id,)
            ).fetchone()[0]
            bwd_count = conn.execute(
                "SELECT COUNT(*) FROM bus_route_stops WHERE route_id = ? AND direction = 'backward'",
                (route_id,)
            ).fetchone()[0]

            result.append({
                "id": r["id"],
                "route_number": r["route_number"],
                "name": r["name"],
                "operator": r["operator"],
                "route_type": r["route_type"],
                "from_terminal": r["from_terminal"],
                "to_terminal": r["to_terminal"],
                "operating_hours": r["operating_hours"],
                "frequency": r["frequency"],
                "fare": r["fare"],
                "color": r["color"],
                "osm_relation_id": r["osm_relation_id"],
                "total_stops_forward": fwd_count,
                "total_stops_backward": bwd_count,
                "active": bool(r["active"]),
                "updated_at": r["updated_at"],
            })
        return result


def get_route_by_id(route_id: str) -> dict | None:
    init_db()
    with closing(_db_connection()) as conn:
        row = conn.execute("SELECT * FROM bus_routes WHERE id = ?", (route_id,)).fetchone()
        if not row:
            row = conn.execute("SELECT * FROM bus_routes WHERE route_number = ?", (route_id,)).fetchone()
            if not row:
                return None

        actual_id = row["id"]

        fwd_stops_rows = conn.execute("""
            SELECT s.id as stop_id, s.name, s.address, s.latitude, s.longitude, brs.stop_order
            FROM bus_route_stops brs
            JOIN bus_stops s ON brs.stop_id = s.id
            WHERE brs.route_id = ? AND brs.direction = 'forward'
            ORDER BY brs.stop_order ASC
        """, (actual_id,)).fetchall()

        bwd_stops_rows = conn.execute("""
            SELECT s.id as stop_id, s.name, s.address, s.latitude, s.longitude, brs.stop_order
            FROM bus_route_stops brs
            JOIN bus_stops s ON brs.stop_id = s.id
            WHERE brs.route_id = ? AND brs.direction = 'backward'
            ORDER BY brs.stop_order ASC
        """, (actual_id,)).fetchall()

        forward_path = json.loads(row["direction_forward_path"]) if row["direction_forward_path"] else []
        backward_path = json.loads(row["direction_backward_path"]) if row["direction_backward_path"] else []

        return {
            "id": row["id"],
            "route_number": row["route_number"],
            "name": row["name"],
            "operator": row["operator"],
            "route_type": row["route_type"],
            "from_terminal": row["from_terminal"],
            "to_terminal": row["to_terminal"],
            "operating_hours": row["operating_hours"],
            "frequency": row["frequency"],
            "fare": row["fare"],
            "color": row["color"],
            "osm_relation_id": row["osm_relation_id"],
            "forward_stops": [dict(s) for s in fwd_stops_rows],
            "backward_stops": [dict(s) for s in bwd_stops_rows],
            "forward_path": forward_path,
            "backward_path": backward_path,
            "active": bool(row["active"]),
            "updated_at": row["updated_at"],
        }


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def list_stops(
    keyword: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = 5.0,
) -> list[dict]:
    init_db()
    with closing(_db_connection()) as conn:
        query = "SELECT * FROM bus_stops WHERE active = 1"
        params: list[Any] = []

        if keyword:
            kw = f"%{_unaccent(keyword)}%"
            query += " AND (py_lower(name) LIKE ? OR py_lower(address) LIKE ?)"
            params.extend([kw, kw])

        rows = conn.execute(query, params).fetchall()

        results = []
        for r in rows:
            stop_lat = r["latitude"]
            stop_lng = r["longitude"]

            distance_km = None
            if lat is not None and lng is not None:
                distance_km = _haversine_distance_km(lat, lng, stop_lat, stop_lng)
                if radius_km is not None and distance_km > radius_km:
                    continue

            routes_rows = conn.execute("""
                SELECT DISTINCT r.route_number
                FROM bus_route_stops brs
                JOIN bus_routes r ON brs.route_id = r.id
                WHERE brs.stop_id = ? AND r.active = 1
                ORDER BY CAST(r.route_number AS INTEGER), r.route_number ASC
            """, (r["id"],)).fetchall()

            routes_list = [ro["route_number"] for ro in routes_rows]

            results.append({
                "id": r["id"],
                "name": r["name"],
                "address": r["address"],
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "osm_node_id": r["osm_node_id"],
                "has_shelter": bool(r["has_shelter"]),
                "routes": routes_list,
                "active": bool(r["active"]),
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
            })

        if lat is not None and lng is not None:
            results.sort(key=lambda s: s["distance_km"] if s["distance_km"] is not None else 9999)

        return results


def get_stop_by_id(stop_id: str) -> dict | None:
    init_db()
    with closing(_db_connection()) as conn:
        row = conn.execute("SELECT * FROM bus_stops WHERE id = ?", (stop_id,)).fetchone()
        if not row:
            return None

        routes_rows = conn.execute("""
            SELECT DISTINCT r.id, r.route_number, r.name, r.operator, r.color, r.route_type
            FROM bus_route_stops brs
            JOIN bus_routes r ON brs.route_id = r.id
            WHERE brs.stop_id = ? AND r.active = 1
            ORDER BY CAST(r.route_number AS INTEGER), r.route_number ASC
        """, (stop_id,)).fetchall()

        routes_list = [r["route_number"] for r in routes_rows]

        return {
            "id": row["id"],
            "name": row["name"],
            "address": row["address"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "osm_node_id": row["osm_node_id"],
            "has_shelter": bool(row["has_shelter"]),
            "routes": routes_list,
            "passing_routes": [dict(r) for r in routes_rows],
            "active": bool(row["active"]),
            "updated_at": row["updated_at"],
        }


def _sort_stops_along_path(stops: list[dict], path: list[list[float]]) -> list[dict]:
    if not path or len(path) < 2 or len(stops) < 2:
        return stops

    def _proj(s: dict) -> int:
        lat = s.get("latitude", 0.0)
        lng = s.get("longitude", 0.0)
        min_d = float("inf")
        best_i = 0
        for i, pt in enumerate(path):
            d = (pt[0] - lng) ** 2 + (pt[1] - lat) ** 2
            if d < min_d:
                min_d = d
                best_i = i
        return best_i

    return sorted(stops, key=_proj)


def _slice_path_between_stops(
    path: list[list[float]],
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
) -> list[list[float]]:
    if not path or len(path) < 2:
        return [[start_lng, start_lat], [end_lng, end_lat]]

    start_idx = 0
    min_start_dist = float("inf")
    for i, pt in enumerate(path):
        d = (pt[0] - start_lng) ** 2 + (pt[1] - start_lat) ** 2
        if d < min_start_dist:
            min_start_dist = d
            start_idx = i

    end_idx = len(path) - 1
    min_end_dist = float("inf")
    for i, pt in enumerate(path):
        d = (pt[0] - end_lng) ** 2 + (pt[1] - end_lat) ** 2
        if d < min_end_dist:
            min_end_dist = d
            end_idx = i

    if start_idx <= end_idx:
        sliced = path[start_idx : end_idx + 1]
    else:
        sliced = list(reversed(path[end_idx : start_idx + 1]))

    res: list[list[float]] = [[start_lng, start_lat]]
    for pt in sliced:
        if (pt[0] - res[-1][0]) ** 2 + (pt[1] - res[-1][1]) ** 2 > 1e-8:
            res.append(pt)
    if (end_lng - res[-1][0]) ** 2 + (end_lat - res[-1][1]) ** 2 > 1e-8:
        res.append([end_lng, end_lat])

    return res


def find_bus_connections(
    from_query: str | None = None,
    to_query: str | None = None,
    from_lat: float | None = None,
    from_lng: float | None = None,
    to_lat: float | None = None,
    to_lng: float | None = None,
) -> list[dict]:
    """Find direct or single-transfer bus routes connecting origin and destination."""
    init_db()

    with closing(_db_connection()) as conn:
        origin_stops: list[sqlite3.Row] = []
        if from_lat is not None and from_lng is not None:
            all_stops = conn.execute("SELECT * FROM bus_stops WHERE active = 1").fetchall()
            sorted_stops = sorted(
                all_stops,
                key=lambda s: _haversine_distance_km(from_lat, from_lng, s["latitude"], s["longitude"])
            )
            origin_stops = sorted_stops[:12]
        elif from_query:
            kw = f"%{_unaccent(from_query)}%"
            origin_stops = conn.execute(
                "SELECT * FROM bus_stops WHERE active = 1 AND (py_lower(name) LIKE ? OR py_lower(address) LIKE ?) LIMIT 50",
                (kw, kw)
            ).fetchall()

        dest_stops: list[sqlite3.Row] = []
        if to_lat is not None and to_lng is not None:
            all_stops = conn.execute("SELECT * FROM bus_stops WHERE active = 1").fetchall()
            sorted_stops = sorted(
                all_stops,
                key=lambda s: _haversine_distance_km(to_lat, to_lng, s["latitude"], s["longitude"])
            )
            dest_stops = sorted_stops[:12]
        elif to_query:
            kw = f"%{_unaccent(to_query)}%"
            dest_stops = conn.execute(
                "SELECT * FROM bus_stops WHERE active = 1 AND (py_lower(name) LIKE ? OR py_lower(address) LIKE ?) LIMIT 50",
                (kw, kw)
            ).fetchall()

        recommendations: list[dict] = []
        direct_by_key: dict[str, dict] = {}

        for o_stop in origin_stops:
            for d_stop in dest_stops:
                if o_stop["id"] == d_stop["id"]:
                    continue

                direct_matches = conn.execute("""
                    SELECT r.id as route_id, r.route_number, r.name as route_name,
                           r.operator, r.color, brs1.direction,
                           brs1.stop_order as board_order, brs2.stop_order as alight_order,
                           r.direction_forward_path, r.direction_backward_path
                    FROM bus_route_stops brs1
                    JOIN bus_route_stops brs2 ON brs1.route_id = brs2.route_id AND brs1.direction = brs2.direction
                    JOIN bus_routes r ON brs1.route_id = r.id
                    WHERE brs1.stop_id = ? AND brs2.stop_id = ? AND brs1.stop_order < brs2.stop_order AND r.active = 1
                """, (o_stop["id"], d_stop["id"])).fetchall()

                for m in direct_matches:
                    key = f"{m['route_number']}-{m['direction']}"

                    if from_lat is not None and from_lng is not None and to_lat is not None and to_lng is not None:
                        walk_dist = (
                            _haversine_distance_km(from_lat, from_lng, o_stop["latitude"], o_stop["longitude"]) +
                            _haversine_distance_km(to_lat, to_lng, d_stop["latitude"], d_stop["longitude"])
                        )
                        if key in direct_by_key and direct_by_key[key]["walk_dist"] <= walk_dist:
                            continue
                    else:
                        span = m["alight_order"] - m["board_order"]
                        if key in direct_by_key and direct_by_key[key]["span"] >= span:
                            continue

                    trip_stops_rows = conn.execute("""
                        SELECT s.id as stop_id, s.name, s.address, s.latitude, s.longitude, brs.stop_order
                        FROM bus_route_stops brs
                        JOIN bus_stops s ON brs.stop_id = s.id
                        WHERE brs.route_id = ? AND brs.direction = ? AND brs.stop_order >= ? AND brs.stop_order <= ?
                        ORDER BY brs.stop_order ASC
                    """, (m["route_id"], m["direction"], m["board_order"], m["alight_order"])).fetchall()
                    trip_stops = [dict(s) for s in trip_stops_rows]
                    stops_count = max(1, len(trip_stops))
                    estimated_mins = max(5, int((stops_count - 1) * 2.5))

                    full_path = json.loads(m["direction_forward_path"] if m["direction"] == "forward" else m["direction_backward_path"])
                    sliced_path = _slice_path_between_stops(
                        full_path,
                        o_stop["latitude"],
                        o_stop["longitude"],
                        d_stop["latitude"],
                        d_stop["longitude"],
                    )
                    rec = {
                        "type": "direct",
                        "route_number": m["route_number"],
                        "route_name": m["route_name"],
                        "operator": m["operator"],
                        "color": m["color"],
                        "board_stop": {
                            "stop_id": o_stop["id"],
                            "name": o_stop["name"],
                            "address": o_stop["address"],
                            "latitude": o_stop["latitude"],
                            "longitude": o_stop["longitude"],
                            "stop_order": m["board_order"],
                        },
                        "alight_stop": {
                            "stop_id": d_stop["id"],
                            "name": d_stop["name"],
                            "address": d_stop["address"],
                            "latitude": d_stop["latitude"],
                            "longitude": d_stop["longitude"],
                            "stop_order": m["alight_order"],
                        },
                        "stops_count": stops_count,
                        "estimated_minutes": estimated_mins,
                        "direction": m["direction"],
                        "path_segment": sliced_path,
                        "trip_stops": trip_stops,
                    }

                    span = m["alight_order"] - m["board_order"]
                    walk_d = 0.0
                    if from_lat is not None and from_lng is not None and to_lat is not None and to_lng is not None:
                        walk_d = (
                            _haversine_distance_km(from_lat, from_lng, o_stop["latitude"], o_stop["longitude"]) +
                            _haversine_distance_km(to_lat, to_lng, d_stop["latitude"], d_stop["longitude"])
                        )
                    direct_by_key[key] = {
                        "rec": rec,
                        "span": span,
                        "walk_dist": walk_d,
                    }

        recommendations.extend([v["rec"] for v in direct_by_key.values()])

        if len(recommendations) < 3 and origin_stops and dest_stops:
            seen_transfers: set[str] = set()

            for o_stop in origin_stops[:4]:
                if len(recommendations) >= 5:
                    break
                for d_stop in dest_stops[:4]:
                    if len(recommendations) >= 5:
                        break

                    transfer_matches = conn.execute("""
                        SELECT
                            r1.id as r1_id, r1.route_number as r1_num, r1.name as r1_name, r1.operator as r1_op, r1.color as r1_color,
                            r1.direction_forward_path as r1_fwd, r1.direction_backward_path as r1_bwd, brs1_start.direction as r1_dir,
                            r2.id as r2_id, r2.route_number as r2_num, r2.name as r2_name, r2.operator as r2_op, r2.color as r2_color,
                            r2.direction_forward_path as r2_fwd, r2.direction_backward_path as r2_bwd, brs2_transfer.direction as r2_dir,
                            t_stop.id as t_id, t_stop.name as t_name, t_stop.address as t_addr,
                            t_stop.latitude as t_lat, t_stop.longitude as t_lng,
                            brs1_start.stop_order as r1_board_order, brs1_transfer.stop_order as r1_alight_order,
                            brs2_transfer.stop_order as r2_board_order, brs2_dest.stop_order as r2_alight_order
                        FROM bus_route_stops brs1_start
                        JOIN bus_route_stops brs1_transfer ON brs1_start.route_id = brs1_transfer.route_id
                            AND brs1_start.direction = brs1_transfer.direction
                            AND brs1_start.stop_order < brs1_transfer.stop_order
                        JOIN bus_stops t_stop ON brs1_transfer.stop_id = t_stop.id
                        JOIN bus_route_stops brs2_transfer ON brs2_transfer.stop_id = t_stop.id
                        JOIN bus_route_stops brs2_dest ON brs2_transfer.route_id = brs2_dest.route_id
                            AND brs2_transfer.direction = brs2_dest.direction
                            AND brs2_transfer.stop_order < brs2_dest.stop_order
                        JOIN bus_routes r1 ON brs1_start.route_id = r1.id
                        JOIN bus_routes r2 ON brs2_transfer.route_id = r2.id
                        WHERE brs1_start.stop_id = ? AND brs2_dest.stop_id = ?
                          AND r1.id != r2.id
                          AND r1.active = 1 AND r2.active = 1
                        LIMIT 2
                    """, (o_stop["id"], d_stop["id"])).fetchall()

                    for tm in transfer_matches:
                        t_key = f"{tm['r1_num']}->{tm['r2_num']}"
                        if t_key in seen_transfers:
                            continue
                        seen_transfers.add(t_key)

                        leg1_stops_rows = conn.execute("""
                            SELECT s.id as stop_id, s.name, s.address, s.latitude, s.longitude, brs.stop_order
                            FROM bus_route_stops brs
                            JOIN bus_stops s ON brs.stop_id = s.id
                            WHERE brs.route_id = ? AND brs.direction = ? AND brs.stop_order >= ? AND brs.stop_order <= ?
                            ORDER BY brs.stop_order ASC
                        """, (tm["r1_id"], tm["r1_dir"], tm["r1_board_order"], tm["r1_alight_order"])).fetchall()

                        leg2_stops_rows = conn.execute("""
                            SELECT s.id as stop_id, s.name, s.address, s.latitude, s.longitude, brs.stop_order
                            FROM bus_route_stops brs
                            JOIN bus_stops s ON brs.stop_id = s.id
                            WHERE brs.route_id = ? AND brs.direction = ? AND brs.stop_order >= ? AND brs.stop_order <= ?
                            ORDER BY brs.stop_order ASC
                        """, (tm["r2_id"], tm["r2_dir"], tm["r2_board_order"], tm["r2_alight_order"])).fetchall()

                        leg1_stops = [dict(s) for s in leg1_stops_rows]
                        leg2_stops = [dict(s) for s in leg2_stops_rows]
                        combined_stops = leg1_stops + (leg2_stops[1:] if len(leg2_stops) > 1 else leg2_stops)
                        total_stops = len(combined_stops)
                        estimated_mins = max(10, int((total_stops - 1) * 2.5) + 10)

                        r1_full = json.loads(tm["r1_fwd"] if tm["r1_dir"] == "forward" else tm["r1_bwd"])
                        r2_full = json.loads(tm["r2_fwd"] if tm["r2_dir"] == "forward" else tm["r2_bwd"])
                        seg1 = _slice_path_between_stops(r1_full, o_stop["latitude"], o_stop["longitude"], tm["t_lat"], tm["t_lng"])
                        seg2 = _slice_path_between_stops(r2_full, tm["t_lat"], tm["t_lng"], d_stop["latitude"], d_stop["longitude"])
                        combined_path = seg1 + seg2

                        recommendations.append({
                            "type": "transfer",
                            "route_number": tm["r1_num"],
                            "route_name": tm["r1_name"],
                            "operator": tm["r1_op"],
                            "color": tm["r1_color"],
                            "board_stop": {
                                "stop_id": o_stop["id"],
                                "name": o_stop["name"],
                                "address": o_stop["address"],
                                "latitude": o_stop["latitude"],
                                "longitude": o_stop["longitude"],
                                "stop_order": tm["r1_board_order"],
                            },
                            "alight_stop": {
                                "stop_id": d_stop["id"],
                                "name": d_stop["name"],
                                "address": d_stop["address"],
                                "latitude": d_stop["latitude"],
                                "longitude": d_stop["longitude"],
                                "stop_order": tm["r2_alight_order"],
                            },
                            "stops_count": total_stops,
                            "estimated_minutes": estimated_mins,
                            "direction": "forward",
                            "path_segment": combined_path,
                            "trip_stops": combined_stops,
                            "transfer_stop": {
                                "stop_id": tm["t_id"],
                                "name": tm["t_name"],
                                "address": tm["t_addr"],
                                "latitude": tm["t_lat"],
                                "longitude": tm["t_lng"],
                                "stop_order": tm["r1_alight_order"],
                            },
                            "second_route_number": tm["r2_num"],
                            "second_board_stop": {
                                "stop_id": tm["t_id"],
                                "name": tm["t_name"],
                                "address": tm["t_addr"],
                                "latitude": tm["t_lat"],
                                "longitude": tm["t_lng"],
                                "stop_order": tm["r2_board_order"],
                            },
                            "second_alight_stop": {
                                "stop_id": d_stop["id"],
                                "name": d_stop["name"],
                                "address": d_stop["address"],
                                "latitude": d_stop["latitude"],
                                "longitude": d_stop["longitude"],
                                "stop_order": tm["r2_alight_order"],
                            },
                        })

        recommendations.sort(key=lambda r: (0 if r["type"] == "direct" else 1, r["estimated_minutes"]))
        return recommendations


def get_audit_report() -> dict:
    """Generate completeness audit report matching OpenStreetMap community data note."""
    init_db()
    with closing(_db_connection()) as conn:
        total_routes = conn.execute("SELECT COUNT(*) FROM bus_routes WHERE active = 1").fetchone()[0]
        total_stops = conn.execute("SELECT COUNT(*) FROM bus_stops WHERE active = 1").fetchone()[0]

        standard_count = conn.execute("SELECT COUNT(*) FROM bus_routes WHERE route_type = 'standard' AND active = 1").fetchone()[0]
        brt_count = conn.execute("SELECT COUNT(*) FROM bus_routes WHERE route_type = 'brt' AND active = 1").fetchone()[0]
        electric_count = conn.execute("SELECT COUNT(*) FROM bus_routes WHERE route_type = 'electric' AND active = 1").fetchone()[0]

        last_sync_row = conn.execute("SELECT value FROM bus_sync_meta WHERE key = 'last_synced_at'").fetchone()
        last_synced_at = last_sync_row["value"] if last_sync_row else None

        issues = []

        routes = conn.execute("SELECT * FROM bus_routes WHERE active = 1").fetchall()
        routes_with_complete_directions = 0

        for r in routes:
            r_id = r["id"]
            fwd_count = conn.execute(
                "SELECT COUNT(*) FROM bus_route_stops WHERE route_id = ? AND direction = 'forward'",
                (r_id,)
            ).fetchone()[0]
            bwd_count = conn.execute(
                "SELECT COUNT(*) FROM bus_route_stops WHERE route_id = ? AND direction = 'backward'",
                (r_id,)
            ).fetchone()[0]

            if fwd_count == 0 or bwd_count == 0:
                issues.append({
                    "level": "warning",
                    "category": "route",
                    "item_id": r_id,
                    "title": f"Tuyến {r['route_number']} chưa đủ dữ liệu hai chiều",
                    "description": f"Tuyến có {fwd_count} điểm dừng chiều đi và {bwd_count} điểm dừng chiều về.",
                })
            else:
                routes_with_complete_directions += 1

            if not r["osm_relation_id"]:
                issues.append({
                    "level": "info",
                    "category": "route",
                    "item_id": r_id,
                    "title": f"Tuyến {r['route_number']} chưa liên kết OpenStreetMap Relation ID",
                    "description": "Cần đối chiếu với quan hệ giao thông công cộng trên OpenStreetMap.",
                })

        no_shelter_count = conn.execute("SELECT COUNT(*) FROM bus_stops WHERE has_shelter = 0 AND active = 1").fetchone()[0]
        if no_shelter_count > 0:
            issues.append({
                "level": "info",
                "category": "stop",
                "item_id": "all-stops-shelter",
                "title": f"{no_shelter_count} trạm dừng chưa khảo sát thông tin nhà chờ (shelter)",
                "description": "Thẻ shelter=* trên OpenStreetMap hỗ trợ cộng đồng kiểm tra tiện nghi nhà chờ xe buýt.",
            })

        completeness_pct = round(
            (routes_with_complete_directions / max(total_routes, 1)) * 100, 1
        )

        overpass_query_sample = (
            "[out:json][timeout:60];\n"
            "// Khu vực Hà Nội (Bounding Box chuẩn xác không phụ thuộc định danh tên)\n"
            "(\n"
            '  relation["route"="bus"](20.80,105.65,21.20,106.00);\n'
            '  node["highway"="bus_stop"](20.80,105.65,21.20,106.00);\n'
            ");\n"
            "out body;\n"
            ">;\n"
            "out skel qt;"
        )

        return {
            "total_routes": total_routes,
            "total_stops": total_stops,
            "standard_routes_count": standard_count,
            "brt_routes_count": brt_count,
            "electric_routes_count": electric_count,
            "completeness_percentage": completeness_pct,
            "osm_data_source": "OpenStreetMap Public Transport Schema v2 (ODbL 1.0)",
            "license": "Open Data Commons Open Database License (ODbL) / SPDX: Apache-2.0",
            "last_synced_at": last_synced_at,
            "issues": issues,
            "overpass_query_sample": overpass_query_sample,
        }


def save_or_update_route(
    route: dict,
    forward_stops: list[dict],
    backward_stops: list[dict],
) -> None:
    init_db()
    now_str = datetime.now(timezone.utc).isoformat()
    route_id = route.get("id") or f"hn-bus-{route['route_number'].lower()}"

    forward_stops = _sort_stops_along_path(forward_stops, route.get("forward_path", []))
    backward_stops = _sort_stops_along_path(backward_stops, route.get("backward_path", []))

    with closing(_db_connection()) as conn, conn:
        conn.execute("""
            INSERT OR REPLACE INTO bus_routes (
                id, route_number, name, operator, route_type, from_terminal,
                to_terminal, operating_hours, frequency, fare, color,
                osm_relation_id, direction_forward_path, direction_backward_path,
                active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            route_id,
            route.get("route_number", ""),
            route.get("name", ""),
            route.get("operator", "Transerco"),
            route.get("route_type", "standard"),
            route.get("from_terminal", ""),
            route.get("to_terminal", ""),
            route.get("operating_hours", "05:00 - 21:00"),
            route.get("frequency", "10 - 15 phút/chuyến"),
            route.get("fare", "10.000 đ/lượt"),
            route.get("color", "#2563eb"),
            route.get("osm_relation_id"),
            json.dumps(route.get("forward_path", [])),
            json.dumps(route.get("backward_path", [])),
            1 if route.get("active", True) else 0,
            now_str,
        ))

        conn.execute("DELETE FROM bus_route_stops WHERE route_id = ?", (route_id,))

        for idx, stop in enumerate(forward_stops, start=1):
            stop_id = stop.get("id") or f"stop-{idx}"
            conn.execute("""
                INSERT OR REPLACE INTO bus_stops (
                    id, name, address, latitude, longitude, osm_node_id, has_shelter, active, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                stop_id,
                stop.get("name", "Trạm dừng xe buýt"),
                stop.get("address", ""),
                stop["latitude"],
                stop["longitude"],
                stop.get("osm_node_id"),
                1 if stop.get("has_shelter", False) else 0,
                now_str,
            ))
            conn.execute("""
                INSERT INTO bus_route_stops (id, route_id, stop_id, direction, stop_order)
                VALUES (?, ?, ?, 'forward', ?)
            """, (f"{route_id}-fwd-{idx}", route_id, stop_id, idx))

        for idx, stop in enumerate(backward_stops, start=1):
            stop_id = stop.get("id") or f"stop-bwd-{idx}"
            conn.execute("""
                INSERT OR REPLACE INTO bus_stops (
                    id, name, address, latitude, longitude, osm_node_id, has_shelter, active, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                stop_id,
                stop.get("name", "Trạm dừng xe buýt"),
                stop.get("address", ""),
                stop["latitude"],
                stop["longitude"],
                stop.get("osm_node_id"),
                1 if stop.get("has_shelter", False) else 0,
                now_str,
            ))
            conn.execute("""
                INSERT INTO bus_route_stops (id, route_id, stop_id, direction, stop_order)
                VALUES (?, ?, ?, 'backward', ?)
            """, (f"{route_id}-bwd-{idx}", route_id, stop_id, idx))


def _chain_multilinestring_segments(segments: list[list[list[float]]]) -> list[list[float]]:
    if not segments:
        return []
    segs = [list(s) for s in segments if len(s) >= 2]
    if not segs:
        return []
    segs.sort(key=len, reverse=True)
    chain = list(segs[0])
    remaining = segs[1:]

    while remaining:
        head = chain[0]
        tail = chain[-1]
        best_dist = float('inf')
        best_idx = -1
        attach_mode = None

        for idx, seg in enumerate(remaining):
            s_start = seg[0]
            s_end = seg[-1]
            d_tail_start = math.hypot(tail[0] - s_start[0], tail[1] - s_start[1])
            d_tail_end = math.hypot(tail[0] - s_end[0], tail[1] - s_end[1])
            d_head_start = math.hypot(head[0] - s_start[0], head[1] - s_start[1])
            d_head_end = math.hypot(head[0] - s_end[0], head[1] - s_end[1])
            m = min(d_tail_start, d_tail_end, d_head_start, d_head_end)
            if m < best_dist:
                best_dist = m
                best_idx = idx
                if m == d_tail_start:
                    attach_mode = 'tail-start'
                elif m == d_tail_end:
                    attach_mode = 'tail-end'
                elif m == d_head_end:
                    attach_mode = 'head-end'
                else:
                    attach_mode = 'head-start'

        seg = remaining.pop(best_idx)
        if best_dist * 111000 > 3000:
            continue

        if attach_mode == 'tail-start':
            chain.extend(seg)
        elif attach_mode == 'tail-end':
            chain.extend(reversed(seg))
        elif attach_mode == 'head-end':
            chain = list(seg) + chain
        elif attach_mode == 'head-start':
            chain = list(reversed(seg)) + chain

    return chain


def import_osm_geojson(data: dict, replace_existing: bool = False) -> tuple[int, int]:
    """Import OpenStreetMap GeoJSON feature collection with bidirectional route separation and stop linking."""
    from collections import defaultdict
    init_db()
    features = data.get("features", [])
    now_str = datetime.now(timezone.utc).isoformat()

    stops_by_id = {}
    stops_by_rel_id = defaultdict(list)

    for f in features:
        geom = f.get("geometry", {})
        props = f.get("properties", {})
        if geom.get("type") == "Point":
            raw_id = str(props.get("@id") or props.get("id") or "").replace("node/", "")
            if not raw_id:
                raw_id = str(props.get("ref", "pt"))
            stop_id = f"osm-{raw_id}"
            coords = geom.get("coordinates", [0, 0])
            name = props.get("name") or props.get("name:vi") or f"Trạm {raw_id}"
            street = props.get("addr:street") or props.get("street") or "Hà Nội"
            has_shelter = 1 if props.get("shelter") == "yes" else 0

            stops_by_id[stop_id] = {
                "id": stop_id,
                "name": name,
                "address": street,
                "latitude": coords[1],
                "longitude": coords[0],
                "osm_node_id": raw_id,
                "has_shelter": has_shelter,
                "active": 1,
                "updated_at": now_str,
            }

            for rel in props.get("@relations", []):
                rel_id = str(rel.get("rel"))
                if stop_id not in stops_by_rel_id[rel_id]:
                    stops_by_rel_id[rel_id].append(stop_id)

    routes_relations = defaultdict(list)
    for f in features:
        geom = f.get("geometry", {})
        props = f.get("properties", {})
        g_type = geom.get("type")
        ref = str(props.get("ref", "")).strip()
        if g_type in ("LineString", "MultiLineString") and ref:
            rel_id = str(props.get("@id", "")).replace("relation/", "")
            if g_type == "MultiLineString":
                coords = _chain_multilinestring_segments(geom.get("coordinates", []))
            else:
                coords = geom.get("coordinates", [])

            name = props.get("name") or f"Tuyến {ref}: {props.get('from', '')} ⇄ {props.get('to', '')}"
            op = props.get("operator", "Transerco")
            r_from = props.get("from", "")
            r_to = props.get("to", "")
            hours = props.get("opening_hours", "05:00 - 21:00")
            interval = props.get("interval", "10 - 15 phút/chuyến")
            fare = props.get("charge") or props.get("fee") or "10.000 đ/lượt"
            color = props.get("colour", "#2563eb")

            routes_relations[ref].append({
                "rel_id": rel_id,
                "name": name,
                "operator": op,
                "from": r_from,
                "to": r_to,
                "hours": hours,
                "interval": interval,
                "fare": fare,
                "color": color,
                "coords": coords,
            })

    routes_to_insert = []
    route_stops_to_insert = []

    def _proj_key(sid: str, path: list[list[float]]) -> int:
        s = stops_by_id.get(sid)
        if not s or not path:
            return 0
        lng, lat = s["longitude"], s["latitude"]
        min_d = float("inf")
        best_i = 0
        for i, pt in enumerate(path):
            d = (pt[0] - lng) ** 2 + (pt[1] - lat) ** 2
            if d < min_d:
                min_d = d
                best_i = i
        return best_i

    for ref, rels in routes_relations.items():
        route_id = f"hn-bus-{ref.lower().replace(' ', '-')}"

        ref_low = ref.lower()
        if "brt" in ref_low:
            r_type = "brt"
        elif ref_low.startswith("e"):
            r_type = "electric"
        else:
            r_type = "standard"

        if len(rels) == 1:
            rel = rels[0]
            fwd_rel = rel
            bwd_rel = None
            fwd_path = rel["coords"]
            bwd_path = list(reversed(fwd_path))
            name = rel["name"]
            op = rel["operator"]
            from_t = rel["from"]
            to_t = rel["to"]
            hours = rel["hours"]
            interval = rel["interval"]
            fare = rel["fare"]
            color = rel["color"]
            osm_id = f"osm-rel-{rel['rel_id']}"

            fwd_stop_ids = stops_by_rel_id.get(rel["rel_id"], [])
            sorted_fwd = sorted(fwd_stop_ids, key=lambda sid: _proj_key(sid, fwd_path))
            sorted_bwd = list(reversed(sorted_fwd))
        else:
            r1, r2 = rels[0], rels[1]
            if "về" in r1["name"].lower() or "chieu ve" in r1["name"].lower():
                fwd_rel, bwd_rel = r2, r1
            else:
                fwd_rel, bwd_rel = r1, r2

            name = fwd_rel["name"]
            op = fwd_rel["operator"]
            from_t = fwd_rel["from"] or (bwd_rel["to"] if bwd_rel else "")
            to_t = fwd_rel["to"] or (bwd_rel["from"] if bwd_rel else "")
            hours = fwd_rel["hours"]
            interval = fwd_rel["interval"]
            fare = fwd_rel["fare"]
            color = fwd_rel["color"]
            osm_id = f"osm-rel-{fwd_rel['rel_id']}"

            fwd_path = fwd_rel["coords"]
            bwd_path = bwd_rel["coords"]

            if len(fwd_path) >= 2 and len(bwd_path) >= 2:
                d_starts = math.hypot(fwd_path[0][0] - bwd_path[0][0], fwd_path[0][1] - bwd_path[0][1]) + \
                           math.hypot(fwd_path[-1][0] - bwd_path[-1][0], fwd_path[-1][1] - bwd_path[-1][1])
                d_cross = math.hypot(fwd_path[0][0] - bwd_path[-1][0], fwd_path[0][1] - bwd_path[-1][1]) + \
                          math.hypot(fwd_path[-1][0] - bwd_path[0][0], fwd_path[-1][1] - bwd_path[0][1])
                if d_starts < d_cross:
                    bwd_path = list(reversed(bwd_path))

            fwd_stop_ids = stops_by_rel_id.get(fwd_rel["rel_id"], [])
            bwd_stop_ids = stops_by_rel_id.get(bwd_rel["rel_id"], [])

            if not fwd_stop_ids and bwd_stop_ids:
                fwd_stop_ids = list(reversed(bwd_stop_ids))
            if not bwd_stop_ids and fwd_stop_ids:
                bwd_stop_ids = list(reversed(fwd_stop_ids))

            sorted_fwd = sorted(fwd_stop_ids, key=lambda sid: _proj_key(sid, fwd_path))
            sorted_bwd = sorted(bwd_stop_ids, key=lambda sid: _proj_key(sid, bwd_path))

        routes_to_insert.append((
            route_id, ref, name, op, r_type, from_t, to_t, hours, interval,
            fare, color, osm_id, json.dumps(fwd_path), json.dumps(bwd_path), 1, now_str
        ))

        for idx, sid in enumerate(sorted_fwd, 1):
            route_stops_to_insert.append((
                f"{route_id}-fwd-{idx}", route_id, sid, "forward", idx
            ))

        for idx, sid in enumerate(sorted_bwd, 1):
            route_stops_to_insert.append((
                f"{route_id}-bwd-{idx}", route_id, sid, "backward", idx
            ))

    with closing(_db_connection()) as conn, conn:
        if replace_existing:
            conn.execute("DELETE FROM bus_route_stops")
            conn.execute("DELETE FROM bus_routes")
            conn.execute("DELETE FROM bus_stops")

        if stops_by_id:
            stops_rows = [
                (
                    s["id"], s["name"], s["address"], s["latitude"], s["longitude"],
                    s["osm_node_id"], s["has_shelter"], s["active"], s["updated_at"]
                )
                for s in stops_by_id.values()
            ]
            conn.executemany("""
                INSERT OR REPLACE INTO bus_stops (
                    id, name, address, latitude, longitude, osm_node_id, has_shelter, active, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, stops_rows)

        if routes_to_insert:
            conn.executemany("""
                INSERT OR REPLACE INTO bus_routes (
                    id, route_number, name, operator, route_type, from_terminal,
                    to_terminal, operating_hours, frequency, fare, color,
                    osm_relation_id, direction_forward_path, direction_backward_path,
                    active, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, routes_to_insert)

        if route_stops_to_insert:
            conn.executemany("""
                INSERT OR REPLACE INTO bus_route_stops (id, route_id, stop_id, direction, stop_order)
                VALUES (?, ?, ?, ?, ?)
            """, route_stops_to_insert)

        conn.execute("""
            INSERT OR REPLACE INTO bus_sync_meta (key, value)
            VALUES ('last_synced_at', ?), ('data_source', 'OpenStreetMap Public Transport Schema v2 (export.geojson - bidirectional separation)')
        """, (now_str,))

    return len(routes_relations), len(stops_by_id)


def create_route(data: dict) -> dict:
    init_db()
    now_str = datetime.now(timezone.utc).isoformat()
    route_num = data.get("route_number", "").strip().upper()
    route_id = f"hn-bus-{route_num.lower()}"

    with closing(_db_connection()) as conn, conn:
        existing = conn.execute("SELECT id FROM bus_routes WHERE id = ?", (route_id,)).fetchone()
        if existing:
            route_id = f"hn-bus-{route_num.lower()}-{uuid.uuid4().hex[:6]}"

        conn.execute("""
            INSERT INTO bus_routes (
                id, route_number, name, operator, route_type, from_terminal,
                to_terminal, operating_hours, frequency, fare, color,
                osm_relation_id, direction_forward_path, direction_backward_path,
                active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            route_id,
            route_num,
            data.get("name", f"Tuyến {route_num}"),
            data.get("operator", "Transerco"),
            data.get("route_type", "standard"),
            data.get("from_terminal", ""),
            data.get("to_terminal", ""),
            data.get("operating_hours", "05:00 - 21:00"),
            data.get("frequency", "10 - 15 phút/chuyến"),
            data.get("fare", "10.000 đ/lượt"),
            data.get("color", "#2563eb"),
            None,
            json.dumps(data.get("forward_path", [])),
            json.dumps(data.get("backward_path", [])),
            now_str,
        ))

        for idx, stop in enumerate(data.get("forward_stops", []), start=1):
            stop_id = stop.get("id") or stop.get("stop_id")
            if stop_id:
                conn.execute("""
                    INSERT OR REPLACE INTO bus_route_stops (id, route_id, stop_id, direction, stop_order)
                    VALUES (?, ?, ?, 'forward', ?)
                """, (f"{route_id}-fwd-{idx}", route_id, stop_id, idx))

        for idx, stop in enumerate(data.get("backward_stops", []), start=1):
            stop_id = stop.get("id") or stop.get("stop_id")
            if stop_id:
                conn.execute("""
                    INSERT OR REPLACE INTO bus_route_stops (id, route_id, stop_id, direction, stop_order)
                    VALUES (?, ?, ?, 'backward', ?)
                """, (f"{route_id}-bwd-{idx}", route_id, stop_id, idx))

    return get_route_by_id(route_id)


def update_route(route_id: str, data: dict) -> dict | None:
    init_db()
    now_str = datetime.now(timezone.utc).isoformat()
    fields = []
    values = []

    for key in ("name", "operator", "route_type", "from_terminal", "to_terminal",
                "operating_hours", "frequency", "fare", "color"):
        if data.get(key) is not None:
            fields.append(f"{key} = ?")
            values.append(data[key])

    if data.get("active") is not None:
        fields.append("active = ?")
        values.append(1 if data["active"] else 0)

    if not fields:
        return get_route_by_id(route_id)

    fields.append("updated_at = ?")
    values.append(now_str)
    values.append(route_id)

    with closing(_db_connection()) as conn, conn:
        cur = conn.execute(f"UPDATE bus_routes SET {', '.join(fields)} WHERE id = ?", tuple(values))
        if cur.rowcount == 0:
            return None

    return get_route_by_id(route_id)


def delete_route(route_id: str) -> bool:
    init_db()
    with closing(_db_connection()) as conn, conn:
        conn.execute("DELETE FROM bus_route_stops WHERE route_id = ?", (route_id,))
        cur = conn.execute("DELETE FROM bus_routes WHERE id = ?", (route_id,))
        return cur.rowcount > 0


def create_stop(data: dict) -> dict:
    init_db()
    now_str = datetime.now(timezone.utc).isoformat()
    stop_id = f"stop-manual-{uuid.uuid4().hex[:8]}"

    with closing(_db_connection()) as conn, conn:
        conn.execute("""
            INSERT INTO bus_stops (
                id, name, address, latitude, longitude, osm_node_id, has_shelter, active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            stop_id,
            data.get("name", "Trạm xe buýt mới"),
            data.get("address", "Hà Nội"),
            float(data["latitude"]),
            float(data["longitude"]),
            f"manual-{stop_id}",
            1 if data.get("has_shelter", False) else 0,
            now_str,
        ))

        for r_num in data.get("routes", []):
            clean_r = str(r_num).strip().upper()
            r_row = conn.execute("SELECT id FROM bus_routes WHERE UPPER(route_number) = ?", (clean_r,)).fetchone()
            if r_row:
                r_id = r_row["id"]
                max_order = conn.execute(
                    "SELECT COALESCE(MAX(stop_order), 0) as max_ord FROM bus_route_stops WHERE route_id = ? AND direction = 'forward'",
                    (r_id,)
                ).fetchone()["max_ord"]
                conn.execute("""
                    INSERT OR REPLACE INTO bus_route_stops (id, route_id, stop_id, direction, stop_order)
                    VALUES (?, ?, ?, 'forward', ?)
                """, (f"{r_id}-fwd-{max_order + 1}", r_id, stop_id, max_order + 1))

    return get_stop_by_id(stop_id)


def update_stop(stop_id: str, data: dict) -> dict | None:
    init_db()
    now_str = datetime.now(timezone.utc).isoformat()
    fields = []
    values = []

    for key in ("name", "address"):
        if data.get(key) is not None:
            fields.append(f"{key} = ?")
            values.append(data[key])

    for key in ("latitude", "longitude"):
        if data.get(key) is not None:
            fields.append(f"{key} = ?")
            values.append(float(data[key]))

    if data.get("has_shelter") is not None:
        fields.append("has_shelter = ?")
        values.append(1 if data["has_shelter"] else 0)

    if data.get("active") is not None:
        fields.append("active = ?")
        values.append(1 if data["active"] else 0)

    with closing(_db_connection()) as conn, conn:
        if fields:
            fields.append("updated_at = ?")
            values.append(now_str)
            values.append(stop_id)
            cur = conn.execute(f"UPDATE bus_stops SET {', '.join(fields)} WHERE id = ?", tuple(values))
            if cur.rowcount == 0:
                return None

        if data.get("routes") is not None:
            conn.execute("DELETE FROM bus_route_stops WHERE stop_id = ?", (stop_id,))
            for r_num in data["routes"]:
                clean_r = str(r_num).strip().upper()
                r_row = conn.execute("SELECT id FROM bus_routes WHERE UPPER(route_number) = ?", (clean_r,)).fetchone()
                if r_row:
                    r_id = r_row["id"]
                    max_order = conn.execute(
                        "SELECT COALESCE(MAX(stop_order), 0) as max_ord FROM bus_route_stops WHERE route_id = ? AND direction = 'forward'",
                        (r_id,)
                    ).fetchone()["max_ord"]
                    conn.execute("""
                        INSERT OR REPLACE INTO bus_route_stops (id, route_id, stop_id, direction, stop_order)
                        VALUES (?, ?, ?, 'forward', ?)
                    """, (f"{r_id}-fwd-{max_order + 1}", r_id, stop_id, max_order + 1))

    return get_stop_by_id(stop_id)


def delete_stop(stop_id: str) -> bool:
    init_db()
    with closing(_db_connection()) as conn, conn:
        conn.execute("DELETE FROM bus_route_stops WHERE stop_id = ?", (stop_id,))
        cur = conn.execute("DELETE FROM bus_stops WHERE id = ?", (stop_id,))
        return cur.rowcount > 0


