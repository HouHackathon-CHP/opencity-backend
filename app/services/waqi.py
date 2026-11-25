# SPDX-License-Identifier: Apache-2.0
import json
import logging
import ssl
from contextlib import closing
from datetime import datetime, timedelta, timezone
import math
from threading import Lock
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import HTTPException

from app.core import config
from app.repositories import air_quality as repo

logger = logging.getLogger(__name__)

SSL_CTX = ssl.create_default_context()
SYNC_LOCK = Lock()
HANOI_BOUNDS = "21.25,105.55,20.75,106.20"  # north, west, south, east


def get_effective_waqi_token() -> str:
    """Retrieve WAQI token from SQLite configuration table or environment."""
    with closing(repo.air_quality_db()) as connection:
        db_token = repo.get_config(connection, "waqi_api_token")
        if db_token and db_token.strip():
            return db_token.strip()
    return config.WAQI_API_TOKEN.strip()


def set_waqi_token(token: str) -> None:
    """Persist WAQI token into SQLite configuration."""
    clean_token = token.strip()
    if "token=" in clean_token:
        clean_token = clean_token.split("token=")[-1].split("&")[0].strip()
    with closing(repo.air_quality_db()) as connection:
        with connection:
            repo.set_config(connection, "waqi_api_token", clean_token)
    config.WAQI_API_TOKEN = clean_token


def _request_waqi(path: str, token: str) -> dict:
    if not token or token.lower() == "demo":
        raise ValueError("Token WAQI chưa được cấu hình hoặc là token thử nghiệm không hợp lệ.")
    separator = "&" if "?" in path else "?"
    url = f"https://api.waqi.info/{path}{separator}{urlencode({'token': token})}"
    req = Request(url, headers={"User-Agent": "OpenCity-AirQuality/1.0"})
    try:
        with urlopen(req, timeout=12, context=SSL_CTX) as response:
            payload = json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError) as exc:
        # urllib exceptions may contain the request URL, including the API token.
        raise ValueError(f"Không thể kết nối tới máy chủ WAQI (api.waqi.info): {type(exc).__name__}") from None

    status = payload.get("status")
    if status != "ok":
        error_msg = str(payload.get("data", "Lỗi không xác định từ WAQI"))
        if "invalid" in error_msg.lower() or "key" in error_msg.lower():
            raise ValueError("Token WAQI không hợp lệ hoặc đã bị khóa. Vui lòng kiểm tra lại token trên aqicn.org.")
        raise ValueError(f"WAQI API báo lỗi: {error_msg}")

    return payload


def _aqi(value: object) -> int | None:
    try:
        result = int(value)
    except (ValueError, TypeError):
        return None
    return result if 0 <= result <= 500 else None


def _value(iaqi: dict, key: str) -> float | None:
    try:
        value = float(iaqi[key]["v"])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _source_time(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).isoformat() if parsed.tzinfo else None
    except ValueError:
        return None


def fetch_waqi_stations(token: str) -> list[dict]:
    """List every WAQI map point in the configured Hanoi bounds."""
    payload = _request_waqi(f"v2/map/bounds/?latlng={HANOI_BOUNDS}", token)
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("Danh sách trạm WAQI không đúng cấu trúc.")
    stations = []
    for item in data:
        try:
            uid = int(item["uid"])
            lat, lon = float(item["lat"]), float(item["lon"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            name = str(item["station"]["name"]).strip()
            if not name:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        stations.append({
            "uid": uid, "code": f"WAQI-{'N' if uid < 0 else 'P'}{abs(uid)}",
            "latitude": lat, "longitude": lon, "name": name,
            "aqi": _aqi(item.get("aqi")),
            "recorded_at": _source_time(item.get("station", {}).get("time")),
        })
    if not stations:
        raise ValueError("WAQI không trả về trạm hợp lệ trong khu vực Hà Nội.")
    return stations


def fetch_waqi_reading(uid: int, token: str) -> dict:
    """Fetch the exact station by UID, avoiding a nearest-station geo lookup."""
    data = _request_waqi(f"feed/@{uid}/", token).get("data")
    if not isinstance(data, dict):
        raise ValueError("Chi tiết trạm WAQI không đúng cấu trúc.")
    iaqi = data.get("iaqi") or {}
    city = data.get("city") or {}
    attributions = data.get("attributions") or []
    names = [str(item.get("name", "")).strip() for item in attributions if isinstance(item, dict)]
    note = "Nguồn: " + ", ".join(name for name in names if name)

    return {
        "aqi": _aqi(data.get("aqi")),
        "pm25": _value(iaqi, "pm25"), "pm10": _value(iaqi, "pm10"),
        "temperature": _value(iaqi, "t"), "humidity": _value(iaqi, "h"),
        "co": _value(iaqi, "co"), "no2": _value(iaqi, "no2"),
        "o3": _value(iaqi, "o3"), "so2": _value(iaqi, "so2"),
        "recorded_at": _source_time((data.get("time") or {}).get("iso")),
        "address": str(city.get("location") or "Hà Nội"),
        "note": note[:500],
    }


def sync_all_stations(tenant: str, only_if_stale: bool = False) -> dict:
    """Synchronize all map points, including stations without a current AQI."""
    token = get_effective_waqi_token()
    if not token or token.lower() == "demo":
        raise HTTPException(
            status_code=400,
            detail=(
                "Chưa cấu hình Token WAQI!"
            ),
        )

    with SYNC_LOCK:
        if only_if_stale:
            with closing(repo.air_quality_db()) as connection:
                last_sync = repo.get_config(connection, f"waqi_last_sync_at:{tenant}")
                if last_sync:
                    try:
                        if datetime.now(timezone.utc) - datetime.fromisoformat(last_sync) < timedelta(minutes=15):
                            count = connection.execute(
                                "SELECT COUNT(*) FROM air_stations WHERE tenant = ? AND code LIKE 'WAQI-%'",
                                (tenant,),
                            ).fetchone()[0]
                            return {"synced_count": count, "total_stations": count, "source": "WAQI cache", "synced_at": last_sync}
                    except ValueError:
                        pass
        try:
            stations = fetch_waqi_stations(token)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        details = {}
        for station in stations:
            try:
                details[station["code"]] = fetch_waqi_reading(station["uid"], token)
            except Exception as exc:
                logger.warning("WAQI detail unavailable for %s: %s", station["code"], exc)

        now_iso = datetime.now(timezone.utc).isoformat()
        synced_count = 0
        with closing(repo.air_quality_db()) as connection, connection:
            current_codes = set()
            for station in stations:
                code = station["code"]
                current_codes.add(code)
                detail = details.get(code) or {}
                repo.upsert_waqi_station(
                    connection, tenant, code, station["name"],
                    detail.get("address") or "Hà Nội",
                    station["latitude"], station["longitude"],
                )
                # Keep only the source's current observation; '-' means no current AQI.
                connection.execute(
                    "DELETE FROM air_readings WHERE tenant = ? AND station_code = ?", (tenant, code)
                )
                aqi = detail.get("aqi") if detail.get("aqi") is not None else station["aqi"]
                recorded_at = detail.get("recorded_at") or station["recorded_at"]
                if aqi is None or recorded_at is None:
                    continue
                repo.insert_reading(
                    connection, reading_id=str(uuid4()), tenant=tenant,
                    station_code=code, aqi=aqi, pm25=detail.get("pm25"),
                    pm10=detail.get("pm10"), temperature=detail.get("temperature"),
                    humidity=detail.get("humidity"), co=detail.get("co"),
                    no2=detail.get("no2"), o3=detail.get("o3"),
                    so2=detail.get("so2"),
                    note=detail.get("note") or "Nguồn: World Air Quality Index Project",
                    recorded_at=recorded_at,
                )
                synced_count += 1

            for old in repo.list_stations(connection, tenant):
                if old["code"] == "HN-HOANKIEM-DEMO" or (
                    old["code"].startswith("WAQI-") and old["code"] not in current_codes
                ):
                    repo.delete_station(connection, tenant, old["code"])
            repo.set_config(connection, f"waqi_last_sync_at:{tenant}", now_iso)

        return {
            "synced_count": synced_count, "total_stations": len(stations),
            "unavailable_count": len(stations) - synced_count,
            "source": "World Air Quality Index Project / WAQI map bounds",
            "has_waqi_token": True, "synced_at": now_iso,
        }
