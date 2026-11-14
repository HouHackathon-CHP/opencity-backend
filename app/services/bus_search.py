# SPDX-License-Identifier: Apache-2.0
from datetime import datetime, timezone
import json
import logging
import ssl
from typing import Any
import urllib.parse
import urllib.request

from fastapi import HTTPException

from app.core import config
from app.core.security import Caller, require_manager
from app.repositories import bus_search as repo
from app.schemas.bus_search import (
    BusAuditReport,
    BusImportInput,
    BusRouteCreate,
    BusRouteDetail,
    BusRouteSummary,
    BusRouteUpdate,
    BusStopCreate,
    BusStopSummary,
    BusStopUpdate,
    BusSyncResult,
    RouteRecommendation,
)

logger = logging.getLogger(__name__)

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def list_routes(
    identity: Caller,
    keyword: str | None = None,
    route_type: str | None = None,
    operator: str | None = None,
) -> list[BusRouteSummary]:
    routes = repo.list_routes(keyword=keyword, route_type=route_type, operator=operator)
    return [BusRouteSummary(**r) for r in routes]


def get_route_detail(route_id: str, identity: Caller) -> BusRouteDetail:
    route = repo.get_route_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Không tìm thấy tuyến xe buýt")
    return BusRouteDetail(**route)


def list_stops(
    identity: Caller,
    keyword: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    radius_km: float | None = 5.0,
) -> list[BusStopSummary]:
    stops = repo.list_stops(keyword=keyword, lat=lat, lng=lng, radius_km=radius_km)
    return [BusStopSummary(**s) for s in stops]


def get_stop_detail(stop_id: str, identity: Caller) -> dict:
    stop = repo.get_stop_by_id(stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Không tìm thấy trạm dừng xe buýt")
    return stop


def find_bus_routes(
    identity: Caller,
    from_query: str | None = None,
    to_query: str | None = None,
    from_lat: float | None = None,
    from_lng: float | None = None,
    to_lat: float | None = None,
    to_lng: float | None = None,
) -> list[RouteRecommendation]:
    recs = repo.find_bus_connections(
        from_query=from_query,
        to_query=to_query,
        from_lat=from_lat,
        from_lng=from_lng,
        to_lat=to_lat,
        to_lng=to_lng,
    )
    return [RouteRecommendation(**r) for r in recs]


def get_audit_report(identity: Caller) -> BusAuditReport:
    report = repo.get_audit_report()
    return BusAuditReport(**report)


def sync_from_osm_overpass(
    identity: Caller,
    overpass_url: str | None = None,
    route_ref: str | None = None,
) -> BusSyncResult:
    require_manager(identity, "bus_search")
    allowed_sources = set(OVERPASS_MIRRORS)
    if config.OSM_OVERPASS_URL:
        allowed_sources.add(config.OSM_OVERPASS_URL)
    if overpass_url and overpass_url not in allowed_sources:
        raise HTTPException(status_code=422, detail="Nguồn Overpass không được phép")
    target_url = overpass_url or config.OSM_OVERPASS_URL or OVERPASS_MIRRORS[0]

    if route_ref:
        ref_clean = route_ref.strip()
        ql_query = f"""[out:json][timeout:25];
(
  relation["type"="route"]["route"="bus"]["ref"="{ref_clean}"](20.90,105.70,21.15,105.95);
);
out body;
>;
out skel qt;
"""
    else:
        ql_query = """[out:json][timeout:25];
(
  relation["type"="route"]["route"="bus"](20.95,105.75,21.10,105.90);
);
out body;
>;
out skel qt;
"""

    encoded_query = urllib.parse.quote(ql_query)
    full_url = f"{target_url}?data={encoded_query}"

    ctx = ssl.create_default_context()

    data = None
    last_err = None

    candidate_urls = [full_url]
    for mirror in OVERPASS_MIRRORS:
        if mirror not in target_url:
            candidate_urls.append(f"{mirror}?data={encoded_query}")

    for try_url in candidate_urls:
        try:
            req = urllib.request.Request(
                try_url,
                headers={"User-Agent": "OpenCity-BusSearch/1.0 (https://opencity.vn)"}
            )
            with urllib.request.urlopen(req, context=ctx, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                break
        except Exception as e:
            last_err = e
            logger.warning(f"Overpass sync failed on {try_url}: {e}")

    now_iso = datetime.now(timezone.utc).isoformat()

    if not data or "elements" not in data:
        report = repo.get_audit_report()
        return BusSyncResult(
            success=False,
            routes_synced=report["total_routes"],
            stops_synced=report["total_stops"],
            message=(
                f"Không thể kết nối đến máy chủ Overpass ({last_err or 'Timeout'}). "
                f"Hệ thống duy trì dữ liệu bản đồ OpenStreetMap hiện hành ({report['total_routes']} tuyến, {report['total_stops']} trạm dừng). "
                "Bạn có thể nạp dữ liệu thủ công qua chức năng Import hoặc thử lại sau."
            ),
            synced_at=now_iso,
        )

    # Process
    elements = data.get("elements", [])
    nodes = {el["id"]: el for el in elements if el.get("type") == "node"}
    relations = [el for el in elements if el.get("type") == "relation"]

    synced_routes = 0
    synced_stops = 0

    for rel in relations:
        tags = rel.get("tags", {})
        ref = tags.get("ref", "")
        if not ref:
            continue

        name = tags.get("name") or f"Tuyến buýt số {ref}: {tags.get('from', '')} ⇄ {tags.get('to', '')}"
        op = tags.get("operator", "Transerco")
        r_type = "brt" if "brt" in ref.lower() else ("electric" if "e" in ref.lower() else "standard")

        members = rel.get("members", [])
        forward_stops = []
        path_coords = []

        for m in members:
            m_type = m.get("type")
            m_ref = m.get("ref")
            role = m.get("role", "")

            if m_type == "node" and m_ref in nodes:
                node = nodes[m_ref]
                n_tags = node.get("tags", {})
                stop_name = n_tags.get("name") or f"Trạm {ref} ({m_ref})"
                lat, lon = node["lat"], node["lon"]

                forward_stops.append({
                    "id": f"osm-node-{m_ref}",
                    "name": stop_name,
                    "address": n_tags.get("addr:street", ""),
                    "latitude": lat,
                    "longitude": lon,
                    "osm_node_id": str(m_ref),
                    "has_shelter": n_tags.get("shelter") == "yes",
                })
                path_coords.append([lon, lat])
                synced_stops += 1

        route_payload = {
            "id": f"hn-bus-{ref.lower()}",
            "route_number": ref,
            "name": name,
            "operator": op,
            "route_type": r_type,
            "from_terminal": tags.get("from", ""),
            "to_terminal": tags.get("to", ""),
            "operating_hours": tags.get("opening_hours", "05:00 - 21:00"),
            "frequency": tags.get("interval", "10 - 15 phút/chuyến"),
            "fare": tags.get("fee", "10.000 đ/lượt"),
            "color": tags.get("colour", "#2563eb"),
            "osm_relation_id": f"osm-rel-{rel['id']}",
            "forward_path": path_coords,
            "backward_path": list(reversed(path_coords)),
            "active": True,
        }

        repo.save_or_update_route(
            route_payload,
            forward_stops,
            list(reversed(forward_stops)),
        )
        synced_routes += 1

    return BusSyncResult(
        success=True,
        routes_synced=synced_routes,
        stops_synced=synced_stops,
        message=f"Đã đồng bộ thành công {synced_routes} tuyến và {synced_stops} trạm dừng từ OpenStreetMap.",
        synced_at=now_iso,
    )


def import_osm_dataset(body: BusImportInput, identity: Caller) -> BusSyncResult:
    """Import user-provided OpenStreetMap GeoJSON or custom JSON data."""
    require_manager(identity, "bus_search")

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = body.payload

    if body.data_format == "geojson" or "features" in payload:
        routes_count, stops_count = repo.import_osm_geojson(payload, body.replace_existing)
        return BusSyncResult(
            success=True,
            routes_synced=routes_count,
            stops_synced=stops_count,
            message=f"Đã nạp thành công {routes_count} tuyến và {stops_count} trạm dừng từ tệp OpenStreetMap GeoJSON.",
            synced_at=now_iso,
        )

    if "routes" in payload:
        routes_in = payload.get("routes", [])
        routes_count = 0
        stops_count = 0
        for r in routes_in:
            fwd_stops = r.get("forward_stops", r.get("stops", []))
            bwd_stops = r.get("backward_stops", list(reversed(fwd_stops)))
            repo.save_or_update_route(r, fwd_stops, bwd_stops)
            routes_count += 1
            stops_count += len(fwd_stops)

        return BusSyncResult(
            success=True,
            routes_synced=routes_count,
            stops_synced=stops_count,
            message=f"Đã nạp thành công {routes_count} tuyến và {stops_count} trạm dừng.",
            synced_at=now_iso,
        )

    raise HTTPException(
        status_code=422,
        detail="Định dạng dữ liệu không hợp lệ. Vui lòng cung cấp tệp GeoJSON (FeatureCollection) hoặc JSON hợp lệ từ OpenStreetMap.",
    )


def create_route(identity: Caller, data: BusRouteCreate) -> BusRouteDetail:
    require_manager(identity, "bus_search")
    created = repo.create_route(data.model_dump())
    if not created:
        raise HTTPException(status_code=400, detail="Không thể tạo tuyến xe buýt")
    return BusRouteDetail(**created)


def update_route(identity: Caller, route_id: str, data: BusRouteUpdate) -> BusRouteDetail:
    require_manager(identity, "bus_search")
    updated = repo.update_route(route_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy tuyến xe buýt để cập nhật")
    return BusRouteDetail(**updated)


def delete_route(identity: Caller, route_id: str) -> dict:
    require_manager(identity, "bus_search")
    success = repo.delete_route(route_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy tuyến xe buýt để xóa")
    return {"success": True, "message": f"Đã xóa thành công tuyến xe buýt {route_id}"}


def create_stop(identity: Caller, data: BusStopCreate) -> BusStopSummary:
    require_manager(identity, "bus_search")
    created = repo.create_stop(data.model_dump())
    if not created:
        raise HTTPException(status_code=400, detail="Không thể tạo trạm dừng xe buýt")
    return BusStopSummary(**created)


def update_stop(identity: Caller, stop_id: str, data: BusStopUpdate) -> BusStopSummary:
    require_manager(identity, "bus_search")
    updated = repo.update_stop(stop_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy trạm dừng để cập nhật")
    return BusStopSummary(**updated)


def delete_stop(identity: Caller, stop_id: str) -> dict:
    require_manager(identity, "bus_search")
    success = repo.delete_stop(stop_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy trạm dừng để xóa")
    return {"success": True, "message": f"Đã xóa thành công trạm dừng {stop_id}"}

