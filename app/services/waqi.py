# SPDX-License-Identifier: Apache-2.0
import json
import logging
import ssl
from contextlib import closing
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import HTTPException

from app.core import config
from app.repositories import air_quality as repo

logger = logging.getLogger(__name__)

SSL_CTX = ssl._create_unverified_context()


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


def fetch_waqi_reading(lat: float, lon: float, token: str) -> dict:
    """Call the official WAQI Feed API for a geographic coordinate."""
    if not token or token.lower() == "demo":
        raise ValueError("Token WAQI chưa được cấu hình hoặc là token thử nghiệm không hợp lệ.")

    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={token}"
    req = Request(url, headers={"User-Agent": "OpenCity-AirQuality/1.0"})

    try:
        with urlopen(req, timeout=12, context=SSL_CTX) as response:
            payload = json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ValueError(f"Không thể kết nối tới máy chủ WAQI (api.waqi.info): {exc}")

    status = payload.get("status")
    if status != "ok":
        error_msg = str(payload.get("data", "Lỗi không xác định từ WAQI"))
        if "invalid" in error_msg.lower() or "key" in error_msg.lower():
            raise ValueError("Token WAQI không hợp lệ hoặc đã bị khóa. Vui lòng kiểm tra lại token trên aqicn.org.")
        raise ValueError(f"WAQI API báo lỗi: {error_msg}")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Dữ liệu trả về từ WAQI không đúng cấu trúc.")

    iaqi = data.get("iaqi", {})
    city_info = data.get("city", {})
    station_name = city_info.get("name", "Trạm đo thực tế WAQI")

    aqi_val = data.get("aqi")
    try:
        aqi_int = int(aqi_val)
    except (ValueError, TypeError):
        aqi_int = 50

    pm25_val = float(iaqi.get("pm25", {}).get("v", 15.0))
    pm10_val = float(iaqi.get("pm10", {}).get("v", 30.0))
    temp_val = float(iaqi.get("t", {}).get("v", 26.0))
    hum_val = float(iaqi.get("h", {}).get("v", 70.0))
    co_val = float(iaqi.get("co", {}).get("v", 0.0)) if "co" in iaqi else None
    no2_val = float(iaqi.get("no2", {}).get("v", 0.0)) if "no2" in iaqi else None
    o3_val = float(iaqi.get("o3", {}).get("v", 0.0)) if "o3" in iaqi else None
    so2_val = float(iaqi.get("so2", {}).get("v", 0.0)) if "so2" in iaqi else None

    return {
        "source": f"WAQI: {station_name}",
        "station_name": station_name,
        "aqi": aqi_int,
        "pm25": pm25_val,
        "pm10": pm10_val,
        "temperature": temp_val,
        "humidity": hum_val,
        "co": co_val,
        "no2": no2_val,
        "o3": o3_val,
        "so2": so2_val,
        "note": f"Dữ liệu trực tiếp từ trạm {station_name} qua mạng lưới WAQI/aqicn.org",
    }


def sync_all_stations(tenant: str) -> dict:
    """Synchronize live data from WAQI API.
    """
    token = get_effective_waqi_token()
    if not token or token.lower() == "demo":
        raise HTTPException(
            status_code=400,
            detail=(
                "Chưa cấu hình Token WAQI!"
            ),
        )

    with closing(repo.air_quality_db()) as connection:
        repo.ensure_tenant_seed(connection, tenant)
        stations = repo.list_stations(connection, tenant)
        if not stations:
            return {"synced_count": 0, "total_stations": 0, "source": "None"}

        synced_count = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        primary_source = ""
        last_error = None

        with connection:
            for st in stations:
                try:
                    reading = fetch_waqi_reading(st["latitude"], st["longitude"], token)
                    primary_source = reading["source"]
                    reading_id = str(uuid4())
                    repo.insert_reading(
                        connection,
                        reading_id=reading_id,
                        tenant=tenant,
                        station_code=st["code"],
                        aqi=reading["aqi"],
                        pm25=reading["pm25"],
                        pm10=reading["pm10"],
                        temperature=reading["temperature"],
                        humidity=reading["humidity"],
                        co=reading["co"],
                        no2=reading["no2"],
                        o3=reading["o3"],
                        so2=reading["so2"],
                        note=reading["note"],
                        recorded_at=now_iso,
                    )
                    synced_count += 1
                except Exception as exc:
                    logger.warning("Failed to sync station %s via WAQI: %s", st["code"], exc)
                    last_error = exc

        if synced_count == 0 and last_error:
            raise HTTPException(status_code=400, detail=str(last_error))

        return {
            "synced_count": synced_count,
            "total_stations": len(stations),
            "source": primary_source or "WAQI API Server",
            "has_waqi_token": True,
            "synced_at": now_iso,
        }
