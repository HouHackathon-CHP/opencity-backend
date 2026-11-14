# SPDX-License-Identifier: Apache-2.0
from fastapi import APIRouter, Depends, Query

from app.core.security import Caller, caller
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
    BusSyncInput,
    BusSyncResult,
    RouteRecommendation,
)
from app.services import bus_search as service

router = APIRouter(prefix="/bus", tags=["bus"])


@router.get("/routes", response_model=list[BusRouteSummary])
def list_routes(
    keyword: str | None = Query(default=None, description="Tìm theo số tuyến hoặc tên bến"),
    route_type: str | None = Query(default=None, description="standard | brt | electric"),
    operator: str | None = Query(default=None, description="Tên đơn vị vận hành"),
    identity: Caller = Depends(caller),
) -> list[BusRouteSummary]:
    return service.list_routes(
        identity=identity,
        keyword=keyword,
        route_type=route_type,
        operator=operator,
    )


@router.get("/routes/{route_id}", response_model=BusRouteDetail)
def get_route_detail(
    route_id: str,
    identity: Caller = Depends(caller),
) -> BusRouteDetail:
    return service.get_route_detail(route_id=route_id, identity=identity)


@router.get("/stops", response_model=list[BusStopSummary])
def list_stops(
    keyword: str | None = Query(default=None, description="Tìm kiếm trạm dừng"),
    lat: float | None = Query(default=None, description="Vĩ độ"),
    lng: float | None = Query(default=None, description="Kinh độ"),
    radius_km: float | None = Query(default=5.0, description="Bán kính tìm kiếm (km)"),
    identity: Caller = Depends(caller),
) -> list[BusStopSummary]:
    return service.list_stops(
        identity=identity,
        keyword=keyword,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
    )


@router.get("/stops/{stop_id}")
def get_stop_detail(
    stop_id: str,
    identity: Caller = Depends(caller),
) -> dict:
    return service.get_stop_detail(stop_id=stop_id, identity=identity)


@router.get("/find", response_model=list[RouteRecommendation])
def find_bus_routes(
    from_query: str | None = Query(default=None, description="Điểm đi (tên trạm hoặc đường)"),
    to_query: str | None = Query(default=None, description="Điểm đến (tên trạm hoặc đường)"),
    from_lat: float | None = Query(default=None),
    from_lng: float | None = Query(default=None),
    to_lat: float | None = Query(default=None),
    to_lng: float | None = Query(default=None),
    identity: Caller = Depends(caller),
) -> list[RouteRecommendation]:
    return service.find_bus_routes(
        identity=identity,
        from_query=from_query,
        to_query=to_query,
        from_lat=from_lat,
        from_lng=from_lng,
        to_lat=to_lat,
        to_lng=to_lng,
    )


@router.get("/audit", response_model=BusAuditReport)
def get_audit_report(
    identity: Caller = Depends(caller),
) -> BusAuditReport:
    return service.get_audit_report(identity=identity)


@router.post("/sync", response_model=BusSyncResult)
def sync_from_osm_overpass(
    body: BusSyncInput | None = None,
    identity: Caller = Depends(caller),
) -> BusSyncResult:
    overpass_url = body.overpass_url if body else None
    route_ref = body.route_ref if body else None
    return service.sync_from_osm_overpass(
        identity=identity,
        overpass_url=overpass_url,
        route_ref=route_ref,
    )


@router.post("/import", response_model=BusSyncResult)
def import_osm_dataset(
    body: BusImportInput,
    identity: Caller = Depends(caller),
) -> BusSyncResult:
    return service.import_osm_dataset(body=body, identity=identity)


@router.post("/routes", response_model=BusRouteDetail, status_code=201)
def create_route(
    body: BusRouteCreate,
    identity: Caller = Depends(caller),
) -> BusRouteDetail:
    return service.create_route(identity=identity, data=body)


@router.put("/routes/{route_id}", response_model=BusRouteDetail)
def update_route(
    route_id: str,
    body: BusRouteUpdate,
    identity: Caller = Depends(caller),
) -> BusRouteDetail:
    return service.update_route(identity=identity, route_id=route_id, data=body)


@router.delete("/routes/{route_id}")
def delete_route(
    route_id: str,
    identity: Caller = Depends(caller),
) -> dict:
    return service.delete_route(identity=identity, route_id=route_id)


@router.post("/stops", response_model=BusStopSummary, status_code=201)
def create_stop(
    body: BusStopCreate,
    identity: Caller = Depends(caller),
) -> BusStopSummary:
    return service.create_stop(identity=identity, data=body)


@router.put("/stops/{stop_id}", response_model=BusStopSummary)
def update_stop(
    stop_id: str,
    body: BusStopUpdate,
    identity: Caller = Depends(caller),
) -> BusStopSummary:
    return service.update_stop(identity=identity, stop_id=stop_id, data=body)


@router.delete("/stops/{stop_id}")
def delete_stop(
    stop_id: str,
    identity: Caller = Depends(caller),
) -> dict:
    return service.delete_stop(identity=identity, stop_id=stop_id)


