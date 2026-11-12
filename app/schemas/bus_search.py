# SPDX-License-Identifier: Apache-2.0
from typing import Literal
from pydantic import BaseModel, Field


class BusStopSummary(BaseModel):
    id: str
    name: str
    address: str
    latitude: float
    longitude: float
    osm_node_id: str | None = None
    has_shelter: bool = False
    routes: list[str] = Field(default_factory=list)
    active: bool = True


class RouteStopRef(BaseModel):
    stop_id: str
    name: str
    address: str
    latitude: float
    longitude: float
    stop_order: int


class BusRouteSummary(BaseModel):
    id: str
    route_number: str
    name: str
    operator: str
    route_type: Literal["standard", "brt", "electric"]
    from_terminal: str
    to_terminal: str
    operating_hours: str
    frequency: str
    fare: str
    color: str
    osm_relation_id: str | None = None
    total_stops_forward: int = 0
    total_stops_backward: int = 0
    active: bool = True
    updated_at: str | None = None


class BusRouteDetail(BaseModel):
    id: str
    route_number: str
    name: str
    operator: str
    route_type: Literal["standard", "brt", "electric"]
    from_terminal: str
    to_terminal: str
    operating_hours: str
    frequency: str
    fare: str
    color: str
    osm_relation_id: str | None = None
    forward_stops: list[RouteStopRef] = Field(default_factory=list)
    backward_stops: list[RouteStopRef] = Field(default_factory=list)
    forward_path: list[list[float]] = Field(default_factory=list)
    backward_path: list[list[float]] = Field(default_factory=list)
    active: bool = True
    updated_at: str


class BusAuditIssue(BaseModel):
    level: Literal["warning", "info"]
    category: Literal["route", "stop", "geometry"]
    item_id: str
    title: str
    description: str


class BusAuditReport(BaseModel):
    total_routes: int
    total_stops: int
    standard_routes_count: int
    brt_routes_count: int
    electric_routes_count: int
    completeness_percentage: float
    osm_data_source: str
    license: str
    last_synced_at: str | None = None
    issues: list[BusAuditIssue] = Field(default_factory=list)
    overpass_query_sample: str


class RouteRecommendation(BaseModel):
    type: Literal["direct", "transfer"]
    route_number: str
    route_name: str
    operator: str
    color: str
    board_stop: RouteStopRef
    alight_stop: RouteStopRef
    stops_count: int
    estimated_minutes: int
    direction: Literal["forward", "backward"]
    path_segment: list[list[float]] = Field(default_factory=list)
    trip_stops: list[RouteStopRef] = Field(default_factory=list)
    transfer_stop: RouteStopRef | None = None
    second_route_number: str | None = None
    second_board_stop: RouteStopRef | None = None
    second_alight_stop: RouteStopRef | None = None


class BusImportInput(BaseModel):
    source_name: str = "OpenStreetMap"
    data_format: Literal["geojson", "overpass_json", "custom_json"] = "custom_json"
    payload: dict
    replace_existing: bool = False


class BusSyncInput(BaseModel):
    overpass_url: str | None = None
    route_ref: str | None = None


class BusSyncResult(BaseModel):
    success: bool
    routes_synced: int
    stops_synced: int
    message: str
    synced_at: str


class BusRouteCreate(BaseModel):
    route_number: str
    name: str
    operator: str = "Transerco"
    route_type: Literal["standard", "brt", "electric"] = "standard"
    from_terminal: str
    to_terminal: str
    operating_hours: str = "05:00 - 21:00"
    frequency: str = "10 - 15 phút/chuyến"
    fare: str = "10.000 đ/lượt"
    color: str = "#2563eb"
    forward_stops: list[dict] = Field(default_factory=list)
    backward_stops: list[dict] = Field(default_factory=list)
    forward_path: list[list[float]] = Field(default_factory=list)
    backward_path: list[list[float]] = Field(default_factory=list)


class BusRouteUpdate(BaseModel):
    name: str | None = None
    operator: str | None = None
    route_type: Literal["standard", "brt", "electric"] | None = None
    from_terminal: str | None = None
    to_terminal: str | None = None
    operating_hours: str | None = None
    frequency: str | None = None
    fare: str | None = None
    color: str | None = None
    active: bool | None = None


class BusStopCreate(BaseModel):
    name: str
    address: str
    latitude: float
    longitude: float
    has_shelter: bool = False
    routes: list[str] = Field(default_factory=list)


class BusStopUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    has_shelter: bool | None = None
    active: bool | None = None
    routes: list[str] | None = None


