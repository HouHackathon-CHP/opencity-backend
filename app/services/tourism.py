# SPDX-License-Identifier: Apache-2.0
from typing import Any
from fastapi import HTTPException

from app.core.security import Caller
from app.repositories import tourism as repo
from app.schemas.tourism import (
    TourismCategorySummary,
    TourismDestinationDetail,
    TourismDestinationSummary,
)


def list_destinations(
    identity: Caller,
    keyword: str | None = None,
    category: str | None = None,
    district: str | None = None,
    heritage_level: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
    audio_guide_only: bool = False,
) -> list[TourismDestinationSummary]:
    items = repo.list_destinations(
        keyword=keyword,
        category=category,
        district=district,
        heritage_level=heritage_level,
        audio_guide_only=audio_guide_only,
    )

    result = []
    for item in items:
        dist = None
        if lat is not None and lon is not None:
            dist = repo.haversine_km(lat, lon, item["latitude"], item["longitude"])
            if radius_km is not None and dist > radius_km:
                continue

        result.append(TourismDestinationSummary(
            id=item["id"],
            name=item["name"],
            category=item["category"],
            address=item["address"],
            district=item["district"],
            latitude=item["latitude"],
            longitude=item["longitude"],
            heritage_level=item["heritage_level"],
            opening_hours=item["opening_hours"],
            admission_fee=item["admission_fee"],
            distance_km=dist,
            audio_guide=item["audio_guide"],
            tags=item["tags"],
        ))

    if lat is not None and lon is not None:
        result.sort(key=lambda x: (x.distance_km if x.distance_km is not None else 9999))

    return result


def get_destination_detail(destination_id: str, identity: Caller, lat: float | None = None, lon: float | None = None) -> TourismDestinationDetail:
    item = repo.get_destination_by_id(destination_id)
    if not item:
        raise HTTPException(status_code=404, detail="Tourism destination not found")

    dist = None
    if lat is not None and lon is not None:
        dist = repo.haversine_km(lat, lon, item["latitude"], item["longitude"])

    return TourismDestinationDetail(
        id=item["id"],
        name=item["name"],
        category=item["category"],
        address=item["address"],
        district=item["district"],
        latitude=item["latitude"],
        longitude=item["longitude"],
        heritage_level=item["heritage_level"],
        description=item["description"],
        opening_hours=item["opening_hours"],
        admission_fee=item["admission_fee"],
        connecting_bus_routes=item["connecting_bus_routes"],
        osm_id=item["osm_id"],
        tags=item["tags"],
        audio_guide=item["audio_guide"],
        active=item["active"],
        distance_km=dist,
    )


def get_geojson(identity: Caller, category: str | None = None) -> dict[str, Any]:
    items = repo.list_destinations(category=category)
    features = []
    for item in items:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [item["longitude"], item["latitude"]],
            },
            "properties": {
                "id": item["id"],
                "name": item["name"],
                "category": item["category"],
                "address": item["address"],
                "district": item["district"],
                "heritage_level": item["heritage_level"],
                "opening_hours": item["opening_hours"],
                "admission_fee": item["admission_fee"],
                "connecting_bus_routes": item["connecting_bus_routes"],
                "osm_id": item["osm_id"],
                "audio_guide": item["audio_guide"],
                "tags": item["tags"],
            },
        })
    return {
        "type": "FeatureCollection",
        "name": "hanoi_tourism_and_heritage",
        "features": features,
    }


def get_categories(identity: Caller) -> list[TourismCategorySummary]:
    items = repo.get_category_counts()
    return [TourismCategorySummary(**item) for item in items]


def get_districts(identity: Caller) -> list[str]:
    return repo.get_districts()
