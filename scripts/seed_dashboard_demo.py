# SPDX-License-Identifier: Apache-2.0
"""Seed varied, clearly marked local cases for the report map and SLA dashboard.

Run only against the local DX-OS demo stack after smoke.py has provisioned users.
Repeated runs do not create duplicate reports or reassign existing cases.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from smoke_app import GATEWAY, env_values, post_json, require, send, token


CASES = [
    ("[DEMO SLA] Hố ga hư tại phố Trần Hưng Đạo", "Hạ tầng", "Phố Trần Hưng Đạo, Hoàn Kiếm",
     21.0186, 105.8489, "infrastructure", 2),
    ("[DEMO SLA] Rác tồn đọng gần công viên Thống Nhất", "Môi trường", "Công viên Thống Nhất, Hai Bà Trưng",
     21.0128, 105.8467, "environment", 72),
    ("[DEMO SLA] Đèn tín hiệu chập chờn tại Kim Mã", "Giao thông", "Phố Kim Mã, Ba Đình",
     21.0326, 105.8170, "transport", 5),
    ("[DEMO SLA] Cây xanh nghiêng trên đường Láng", "Cây xanh", "Đường Láng, Đống Đa",
     21.0227, 105.8093, None, None),
    ("[DEMO SLA] Vỉa hè xuống cấp tại Nguyễn Trãi", "Hạ tầng", "Đường Nguyễn Trãi, Thanh Xuân",
     20.9982, 105.8090, "infrastructure", 96),
]


def multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = f"----opencity-demo-{uuid4().hex}"
    parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode()
             for key, value in fields.items()]
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def main() -> None:
    values = env_values()
    citizen = token("dxos-citizen", values["DEMO_CITIZEN_PASSWORD"])
    dispatcher = token("dxos-dispatcher", values["DEMO_OPERATOR_PASSWORD"])
    status, existing = send("GET", f"{GATEWAY}/api/opencity/reports", token=dispatcher)
    require(status, 200, existing)
    by_title = {item["title"]: item for item in existing}
    created = 0
    assigned = 0
    for title, category, address, latitude, longitude, unit, hours in CASES:
        report = by_title.get(title)
        if report is None:
            body, content_type = multipart({
                "title": title,
                "description": "Dữ liệu mô phỏng phục vụ kiểm thử dashboard và bản đồ OpenCity; không phải phản ánh thực tế.",
                "category": category, "address": address,
                "latitude": str(latitude), "longitude": str(longitude),
            })
            status, report = send("POST", f"{GATEWAY}/api/opencity/reports", token=citizen,
                                  body=body, content_type=content_type)
            require(status, 201, report)
            created += 1
        if unit and not report["assigned_unit"] and report["state"] != "resolved":
            due_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
            status, report = post_json(f"{GATEWAY}/api/opencity/reports/{report['id']}/dispatch", dispatcher,
                                       {"unit_id": unit, "due_at": due_at,
                                        "note": "Phân công hồ sơ mô phỏng để kiểm thử SLA."})
            require(status, 200, report)
            assigned += 1
    print(f"Dashboard demo ready: {len(CASES)} cases, {created} created, {assigned} assigned.")


if __name__ == "__main__":
    main()
