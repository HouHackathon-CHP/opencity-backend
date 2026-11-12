# SPDX-License-Identifier: Apache-2.0
from contextlib import closing
from datetime import datetime, timedelta, timezone
import logging
from uuid import uuid4

logger = logging.getLogger(__name__)

from fastapi import HTTPException

from app.core.security import Caller, can_manage, require_manager
from app.repositories import air_quality as repo
from app.schemas.air_quality import ReadingInput, StationInput, BroadcastAlertInput


def classify_aqi(aqi: int) -> dict:
    if aqi <= 50:
        return {
            "level": "good",
            "label": "Tốt",
            "color": "#10b981",
            "bg_color": "rgba(16, 185, 129, 0.15)",
            "health_effect": "Chất lượng không khí đạt chuẩn, không ảnh hưởng tới sức khỏe.",
            "advice_general": "Thời tiết lý tưởng cho mọi hoạt động ngoài trời.",
            "advice_sensitive": "Không có hạn chế đối với nhóm nhạy cảm.",
            "recommendations": [
                {"icon": "Smile", "text": "Thoải mái tập luyện thể thao ngoài trời"},
                {"icon": "Wind", "text": "Mở cửa thông thoáng đón gió tự nhiên"},
            ],
        }
    elif aqi <= 100:
        return {
            "level": "moderate",
            "label": "Trung bình",
            "color": "#eab308",
            "bg_color": "rgba(234, 179, 8, 0.15)",
            "health_effect": "Chất lượng không khí ở mức chấp nhận được.",
            "advice_general": "Người dân có thể tham gia các hoạt động ngoài trời bình thường.",
            "advice_sensitive": "Nhóm người rất nhạy cảm nên chú ý nếu có triệu chứng khó thở.",
            "recommendations": [
                {"icon": "Check", "text": "Hoạt động ngoài trời bình thường"},
                {"icon": "ShieldAlert", "text": "Nhóm nhạy cảm giảm vận động gắng sức kéo dài"},
            ],
        }
    elif aqi <= 150:
        return {
            "level": "unhealthy_sensitive",
            "label": "Kém",
            "color": "#f97316",
            "bg_color": "rgba(249, 115, 22, 0.15)",
            "health_effect": "Những người nhạy cảm có thể gặp các triệu chứng kích ứng đường hô hấp.",
            "advice_general": "Người khỏe mạnh có thể giảm bớt các hoạt động gắng sức ngoài trời.",
            "advice_sensitive": "Trẻ em, người cao tuổi và người mắc bệnh hô hấp nên ở trong nhà.",
            "recommendations": [
                {"icon": "Mask", "text": "Đeo khẩu trang kháng bụi mịn (N95) khi ra đường"},
                {"icon": "Home", "text": "Đóng bớt cửa sổ đối diện đường lớn giờ cao điểm"},
            ],
        }
    elif aqi <= 200:
        return {
            "level": "unhealthy",
            "label": "Xấu",
            "color": "#ef4444",
            "bg_color": "rgba(239, 68, 68, 0.15)",
            "health_effect": "Bắt đầu ảnh hưởng tới sức khỏe của mọi người, nhóm nhạy cảm bị ảnh hưởng nặng hơn.",
            "advice_general": "Hạn chế ra ngoài, tránh tập thể dục buổi sáng nơi có mật độ giao thông cao.",
            "advice_sensitive": "Bắt buộc ở trong nhà, sử dụng máy lọc không khí nếu có.",
            "recommendations": [
                {"icon": "AlertTriangle", "text": "Tránh các hoạt động gắng sức ngoài trời"},
                {"icon": "AirVent", "text": "Sử dụng máy lọc không khí trong phòng kín"},
                {"icon": "Mask", "text": "Luôn đeo khẩu trang lọc bụi mịn N95/KF94 khi ra ngoài"},
            ],
        }
    elif aqi <= 300:
        return {
            "level": "very_unhealthy",
            "label": "Rất xấu",
            "color": "#8b5cf6",
            "bg_color": "rgba(139, 92, 246, 0.15)",
            "health_effect": "Cảnh báo khẩn cấp: Toàn bộ cư dân có nguy cơ bị ảnh hưởng sức khỏe nghiêm trọng.",
            "advice_general": "Hạn chế tối đa việc ra ngoài, đóng kín toàn bộ cửa sổ nhà.",
            "advice_sensitive": "Người có tiền sử hen suyễn, bệnh tim mạch tuyệt đối không ra ngoài trời.",
            "recommendations": [
                {"icon": "AlertOctagon", "text": "Tuyệt đối không tập thể dục ngoài trời"},
                {"icon": "DoorClosed", "text": "Đóng kín cửa, bật chế độ lọc khí tuần hoàn"},
                {"icon": "FirstAid", "text": "Liên hệ y tế nếu có dấu hiệu ho, khó thở liên tục"},
            ],
        }
    else:
        return {
            "level": "hazardous",
            "label": "Nguy hại",
            "color": "#7f1d1d",
            "bg_color": "rgba(127, 29, 29, 0.2)",
            "health_effect": "Báo động ô nhiễm đặc biệt nguy hại: Ảnh hưởng trực tiếp và nghiêm trọng tới toàn bộ cộng đồng.",
            "advice_general": "Mọi người dân nên ở trong nhà, chuyển sang học tập và làm việc từ xa nếu có thể.",
            "advice_sensitive": "Cần theo dõi y tế chặt chẽ đối với người bệnh mãn tính và trẻ sơ sinh.",
            "recommendations": [
                {"icon": "ShieldX", "text": "Cấm hoàn toàn các hoạt động ngoài trời tập thể"},
                {"icon": "Home", "text": "Ở trong phòng kín có trang bị hệ thống lọc khí"},
            ],
        }


def format_station_payload(station_row, latest_reading_row) -> dict:
    station_dict = dict(station_row)
    if "status" not in station_dict or not station_dict["status"]:
        station_dict["status"] = "active"
    if not latest_reading_row:
        return {
            **station_dict,
            "latest_reading": None,
            "classification": None,
        }

    reading_dict = dict(latest_reading_row)
    classification = classify_aqi(reading_dict["aqi"])
    return {
        **station_dict,
        "latest_reading": reading_dict,
        "classification": classification,
    }


def ensure_fresh_readings(tenant: str) -> None:
    """Automatically ensure readings are kept fresh from WAQI without manual intervention."""
    try:
        from app.services import waqi
        token = waqi.get_effective_waqi_token()
        if not token or token.lower() == "demo":
            return

        with closing(repo.air_quality_db()) as connection:
            row = connection.execute(
                "SELECT recorded_at FROM air_readings WHERE tenant = ? ORDER BY recorded_at DESC LIMIT 1",
                (tenant,),
            ).fetchone()
            if row and row["recorded_at"]:
                last_dt = datetime.fromisoformat(row["recorded_at"])
                if datetime.now(timezone.utc) - last_dt < timedelta(minutes=15):
                    return
        waqi.sync_all_stations(tenant)
    except Exception as exc:
        logger.warning(f"Auto-sync air quality readings failed: {exc}")


def get_city_summary(identity: Caller) -> dict:
    ensure_fresh_readings(identity.tenant)
    with closing(repo.air_quality_db()) as connection:
        repo.ensure_tenant_seed(connection, identity.tenant)
        stations = repo.list_stations(connection, identity.tenant)
        if not stations:
            return {
                "tenant": identity.tenant,
                "total_stations": 0,
                "average_aqi": 0,
                "classification": classify_aqi(0),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "best_station": None,
                "worst_station": None,
                "distribution": {
                    "good": 0,
                    "moderate": 0,
                    "unhealthy_sensitive": 0,
                    "unhealthy": 0,
                    "very_unhealthy": 0,
                    "hazardous": 0,
                },
            }

        station_items = []
        aqi_values = []
        worst_item = None
        best_item = None
        latest_time = None

        for st in stations:
            latest_rd = repo.get_latest_reading(connection, identity.tenant, st["code"])
            formatted = format_station_payload(st, latest_rd)
            station_items.append(formatted)
            if latest_rd:
                aqi = latest_rd["aqi"]
                aqi_values.append(aqi)
                time_str = latest_rd["recorded_at"]
                if not latest_time or time_str > latest_time:
                    latest_time = time_str
                if not worst_item or aqi > worst_item["latest_reading"]["aqi"]:
                    worst_item = formatted
                if not best_item or aqi < best_item["latest_reading"]["aqi"]:
                    best_item = formatted

        active_items = [s for s in station_items if s.get("status") not in ("maintenance", "hidden")]
        active_aqi_values = [s["latest_reading"]["aqi"] for s in active_items if s.get("latest_reading")]
        avg_aqi = round(sum(active_aqi_values) / len(active_aqi_values)) if active_aqi_values else 0
        classification = classify_aqi(avg_aqi)

        distribution = {"good": 0, "moderate": 0, "unhealthy_sensitive": 0, "unhealthy": 0, "very_unhealthy": 0, "hazardous": 0}
        for item in station_items:
            cls = item.get("classification")
            if cls and cls["level"] in distribution:
                distribution[cls["level"]] += 1

        return {
            "tenant": identity.tenant,
            "total_stations": len(stations),
            "average_aqi": avg_aqi,
            "classification": classification,
            "updated_at": latest_time or datetime.now(timezone.utc).isoformat(),
            "best_station": best_item,
            "worst_station": worst_item,
            "distribution": distribution,
        }


def list_stations(identity: Caller) -> list[dict]:
    ensure_fresh_readings(identity.tenant)
    with closing(repo.air_quality_db()) as connection:
        repo.ensure_tenant_seed(connection, identity.tenant)
        stations = repo.list_stations(connection, identity.tenant)
        result = []
        is_operator = can_manage(identity, "air_quality")
        for st in stations:
            latest_rd = repo.get_latest_reading(connection, identity.tenant, st["code"])
            payload = format_station_payload(st, latest_rd)
            if not is_operator and payload.get("status") == "hidden":
                continue
            result.append(payload)
        return result


def get_station_detail(code: str, identity: Caller) -> dict:
    with closing(repo.air_quality_db()) as connection:
        repo.ensure_tenant_seed(connection, identity.tenant)
        station = repo.get_station(connection, identity.tenant, code)
        if not station:
            raise HTTPException(status_code=404, detail="Air quality station not found")

        latest_rd = repo.get_latest_reading(connection, identity.tenant, code)
        history_rows = repo.list_recent_readings(connection, identity.tenant, code, limit=24)
        history = [
            {**dict(row), "classification": classify_aqi(row["aqi"])}
            for row in history_rows
        ]

        formatted = format_station_payload(station, latest_rd)
        formatted["history"] = history
        return formatted


def add_reading(body: ReadingInput, identity: Caller) -> dict:
    require_manager(identity, "air_quality")
    with closing(repo.air_quality_db()) as connection:
        repo.ensure_tenant_seed(connection, identity.tenant)
        station = repo.get_station(connection, identity.tenant, body.station_code)
        if not station:
            raise HTTPException(status_code=404, detail=f"Station '{body.station_code}' not found")

        reading_id = str(uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        with connection:
            repo.insert_reading(
                connection,
                reading_id=reading_id,
                tenant=identity.tenant,
                station_code=body.station_code,
                aqi=body.aqi,
                pm25=body.pm25,
                pm10=body.pm10,
                temperature=body.temperature,
                humidity=body.humidity,
                co=body.co,
                no2=body.no2,
                o3=body.o3,
                so2=body.so2,
                note=body.note,
                recorded_at=now_iso,
            )

        latest_rd = repo.get_latest_reading(connection, identity.tenant, body.station_code)
        return format_station_payload(station, latest_rd)


def sync_live_data(identity: Caller) -> dict:
    require_manager(identity, "air_quality")
    from app.services import waqi
    sync_result = waqi.sync_all_stations(identity.tenant)
    summary = get_city_summary(identity)
    return {
        "sync_result": sync_result,
        "summary": summary,
    }


def get_waqi_status(identity: Caller) -> dict:
    from app.services import waqi
    token = waqi.get_effective_waqi_token()
    has_token = bool(token and token.lower() != "demo")
    preview = f"{token[:4]}...{token[-4:]}" if has_token and len(token) > 8 else ("Configured" if has_token else "")
    return {
        "has_token": has_token,
        "token_preview": preview,
        "provider": "World Air Quality Index (WAQI / aqicn.org)",
    }


def save_waqi_token(token_str: str, identity: Caller) -> dict:
    require_manager(identity, "air_quality")
    from app.services import waqi
    clean = token_str.strip()
    waqi.set_waqi_token(clean)
    return get_waqi_status(identity)


def create_station(body: StationInput, identity: Caller) -> dict:
    require_manager(identity, "air_quality")
    code = body.code.strip().upper()
    with closing(repo.air_quality_db()) as connection:
        repo.ensure_tenant_seed(connection, identity.tenant)
        existing = repo.get_station(connection, identity.tenant, code)
        if existing:
            raise HTTPException(status_code=409, detail=f"Mã trạm '{code}' đã tồn tại trong mạng lưới.")

        now_utc = datetime.now(timezone.utc)
        with connection:
            repo.insert_station(
                connection,
                tenant=identity.tenant,
                code=code,
                name=body.name.strip(),
                address=body.address.strip(),
                area_type=body.area_type.strip(),
                latitude=body.latitude,
                longitude=body.longitude,
                status="active",
                created_at=now_utc.isoformat(),
            )
            repo.insert_reading(
                connection,
                reading_id=str(uuid4()),
                tenant=identity.tenant,
                station_code=code,
                aqi=45,
                pm25=11.5,
                pm10=20.0,
                temperature=28.0,
                humidity=68.0,
                co=0.8,
                no2=22.0,
                o3=38.0,
                so2=10.0,
                note="Trạm mới đưa vào vận hành mạng lưới đô thị",
                recorded_at=now_utc.isoformat(),
            )
        st = repo.get_station(connection, identity.tenant, code)
        latest_rd = repo.get_latest_reading(connection, identity.tenant, code)
        return format_station_payload(st, latest_rd)


def update_station_status(code: str, status: str, identity: Caller) -> dict:
    require_manager(identity, "air_quality")
    target_code = code.strip().upper()
    if status not in ("active", "maintenance", "hidden"):
        raise HTTPException(status_code=422, detail="Trạng thái chỉ có thể là 'active', 'maintenance' hoặc 'hidden'")
    with closing(repo.air_quality_db()) as connection:
        repo.ensure_tenant_seed(connection, identity.tenant)
        station = repo.get_station(connection, identity.tenant, target_code)
        if not station:
            raise HTTPException(status_code=404, detail="Trạm quan trắc không tồn tại")
        with connection:
            repo.update_station_status(connection, identity.tenant, target_code, status)
        updated = repo.get_station(connection, identity.tenant, target_code)
        latest_rd = repo.get_latest_reading(connection, identity.tenant, target_code)
        return format_station_payload(updated, latest_rd)


def delete_station(code: str, identity: Caller) -> dict:
    require_manager(identity, "air_quality")
    target_code = code.strip().upper()
    with closing(repo.air_quality_db()) as connection:
        repo.ensure_tenant_seed(connection, identity.tenant)
        station = repo.get_station(connection, identity.tenant, target_code)
        if not station:
            raise HTTPException(status_code=404, detail="Trạm quan trắc không tồn tại")
        with connection:
            repo.delete_station(connection, identity.tenant, target_code)
        return {"ok": True, "deleted_code": target_code}


def broadcast_air_alert(body: BroadcastAlertInput, identity: Caller) -> dict:
    require_manager(identity, "air_quality")
    from app.repositories.bulletins import bulletin_db, bulletin_view
    target_code = body.station_code.strip().upper()
    with closing(repo.air_quality_db()) as connection:
        station = repo.get_station(connection, identity.tenant, target_code)
        if not station:
            raise HTTPException(status_code=404, detail="Trạm quan trắc không tồn tại")
        latest = repo.get_latest_reading(connection, identity.tenant, target_code)
        aqi_val = latest["aqi"] if latest else 100
        classification = classify_aqi(aqi_val)

    now_iso = datetime.now(timezone.utc).isoformat()
    bulletin_id = str(uuid4())
    full_body = (
        f"Cảnh báo môi trường khẩn cấp từ Trung tâm Quan trắc Môi trường Đô thị OpenCity:\n"
        f"Tại trạm {station['name']} ({station['address']}), chỉ số ô nhiễm không khí ghi nhận mức {aqi_val} - {classification['label']}.\n"
        f"Tác động sức khỏe: {classification['health_effect']}\n"
        f"Khuyến nghị người dân: {classification['advice_general']}\n"
        f"Khuyến nghị nhóm người nhạy cảm (trẻ nhỏ, người già, người mắc bệnh hô hấp): {classification['advice_sensitive']}."
    )
    with closing(bulletin_db()) as b_conn:
        with b_conn:
            b_conn.execute(
                """INSERT INTO bulletins
                   (id, tenant, category, title, summary, body, area, latitude, longitude, published_at, created_by)
                   VALUES (?, ?, 'alert', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    bulletin_id, identity.tenant, body.title.strip(), body.summary.strip(),
                    full_body, station["area_type"], station["latitude"], station["longitude"],
                    now_iso, identity.user,
                ),
            )
        row = b_conn.execute("SELECT * FROM bulletins WHERE id = ?", (bulletin_id,)).fetchone()
    return bulletin_view(row)
