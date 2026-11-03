# SPDX-License-Identifier: Apache-2.0
"""Prepare tenant-scoped report text for the generic DX-OS insight service."""

from fastapi import HTTPException

from app.core import config, core_client
from app.core.security import Caller
from app.repositories.reports import save_triage_suggestion, triage_suggestion_for
from app.services.reports import get_report_record, visible_report_views


SEED_EXAMPLES = [
    ("infrastructure", "đèn đường hỏng không sáng cần sửa chiếu sáng"),
    ("infrastructure", "ổ gà mặt đường xuống cấp vỉa hè hư hỏng"),
    ("infrastructure", "cống thoát nước tắc ngập đường"),
    ("environment", "rác thải không được thu gom ô nhiễm"),
    ("environment", "cây xanh gãy đổ cành cây nguy hiểm"),
    ("environment", "nước thải khói bụi ô nhiễm môi trường"),
    ("transport", "ùn tắc giao thông xe cộ kẹt đường"),
    ("transport", "đèn tín hiệu giao thông không hoạt động"),
    ("transport", "xe buýt chậm tuyến xe sai lịch"),
    ("intake", "kiến nghị khác cần được tiếp nhận và xem xét"),
    ("intake", "nội dung chưa rõ đơn vị xử lý cần hỗ trợ"),
    ("intake", "thông tin chung đề xuất cải thiện dịch vụ"),
]

URGENCY_EXAMPLES = [
    ("high", "dây điện đứt nguy hiểm có người bị thương cần xử lý khẩn cấp"),
    ("high", "cây đổ chắn đường gây tai nạn nguy hiểm"),
    ("high", "ngập sâu sạt lở cháy nổ đe dọa an toàn"),
    ("normal", "đèn đường hỏng cần sửa trong tuần"),
    ("normal", "rác thải chưa được thu gom nhiều ngày"),
    ("normal", "ổ gà trên đường cần bảo trì"),
    ("low", "đề xuất cải thiện cảnh quan khu phố"),
    ("low", "góp ý thêm biển chỉ dẫn thuận tiện"),
    ("low", "kiến nghị nâng cấp tiện ích khi có kế hoạch"),
]


def report_text(report: dict) -> str:
    return " ".join(str(report.get(field) or "") for field in ("title", "description", "address"))[:2000]


async def generate_suggestion(report_id: str, identity: Caller) -> dict:
    record = await get_report_record(report_id, identity)
    reports = await visible_report_views(identity)
    target = next((item for item in reports if item["id"] == report_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if target["state"] == "resolved":
        raise HTTPException(status_code=409, detail="Resolved reports need no triage")
    others = [item for item in reports if item["id"] != report_id]
    examples = [{"label": unit, "text": text} for unit, text in SEED_EXAMPLES]
    examples.extend({"label": item["assigned_unit"], "text": report_text(item)}
                    for item in others if item["assigned_unit"] in config.VALID_UNITS)
    candidates = [{"id": item["id"], "text": report_text(item)} for item in others[:150]]
    analysis = await core_client.core_json(
        config.INSIGHT_URL, "/analyze", identity, "POST",
        json_body={
            "text": report_text(target),
            "labels": sorted(config.VALID_UNITS),
            "examples": examples[:120],
            "candidates": candidates,
        },
    )
    ranked = analysis.get("ranked_labels")
    if (not isinstance(ranked, list) or not ranked or
            ranked[0].get("label") not in config.VALID_UNITS):
        raise HTTPException(status_code=502, detail="Insight service returned an invalid unit")
    urgency = await core_client.core_json(
        config.INSIGHT_URL, "/analyze", identity, "POST",
        json_body={
            "text": report_text(target),
            "labels": ["high", "normal", "low"],
            "examples": [{"label": level, "text": text} for level, text in URGENCY_EXAMPLES],
        },
    )
    urgency_ranked = urgency.get("ranked_labels")
    if (not isinstance(urgency_ranked, list) or not urgency_ranked or
            urgency_ranked[0].get("label") not in {"high", "normal", "low"}):
        raise HTTPException(status_code=502, detail="Insight service returned an invalid urgency")
    analysis["urgency"] = urgency_ranked[0]["label"]
    analysis["urgency_ranked"] = urgency_ranked
    return save_triage_suggestion(identity, report_id, record["updated_at"], analysis)


async def latest_suggestion(report_id: str, identity: Caller) -> dict:
    record = await get_report_record(report_id, identity)
    suggestion = triage_suggestion_for(identity.tenant, report_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="No triage suggestion yet")
    return {**suggestion, "stale": suggestion["source_updated_at"] != record["updated_at"]}
