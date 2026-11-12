# SPDX-License-Identifier: Apache-2.0
from fastapi import APIRouter, Depends

from app.core.security import Caller, caller
from app.schemas.air_quality import (
    BroadcastAlertInput,
    ReadingInput,
    StationInput,
    StationStatusInput,
    WaqiTokenInput,
)
from app.services import air_quality as service

router = APIRouter()


@router.get("/air-quality/summary")
def get_city_summary(identity: Caller = Depends(caller)) -> dict:
    return service.get_city_summary(identity)


@router.get("/air-quality/stations")
def list_stations(identity: Caller = Depends(caller)) -> list[dict]:
    return service.list_stations(identity)


@router.post("/air-quality/stations", status_code=201)
def create_station(body: StationInput, identity: Caller = Depends(caller)) -> dict:
    return service.create_station(body, identity)


@router.get("/air-quality/stations/{code}")
def get_station_detail(code: str, identity: Caller = Depends(caller)) -> dict:
    return service.get_station_detail(code, identity)


@router.patch("/air-quality/stations/{code}/status")
def update_station_status(
    code: str, body: StationStatusInput, identity: Caller = Depends(caller)
) -> dict:
    return service.update_station_status(code, body.status, identity)


@router.delete("/air-quality/stations/{code}")
def delete_station(code: str, identity: Caller = Depends(caller)) -> dict:
    return service.delete_station(code, identity)


@router.post("/air-quality/broadcast-alert", status_code=201)
def broadcast_air_alert(
    body: BroadcastAlertInput, identity: Caller = Depends(caller)
) -> dict:
    return service.broadcast_air_alert(body, identity)


@router.post("/air-quality/readings", status_code=201)
def add_reading(body: ReadingInput, identity: Caller = Depends(caller)) -> dict:
    return service.add_reading(body, identity)


@router.get("/air-quality/waqi-status")
def get_waqi_status(identity: Caller = Depends(caller)) -> dict:
    return service.get_waqi_status(identity)


@router.post("/air-quality/waqi-token")
def save_waqi_token(body: WaqiTokenInput, identity: Caller = Depends(caller)) -> dict:
    return service.save_waqi_token(body.token, identity)


@router.post("/air-quality/sync")
def sync_live_data(identity: Caller = Depends(caller)) -> dict:
    return service.sync_live_data(identity)
