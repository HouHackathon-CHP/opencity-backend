# SPDX-License-Identifier: Apache-2.0
"""Exercise the OpenCity API via the running DX-OS gateway and local demo users."""

import base64
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from provision_roles import provision


ROOT = Path(__file__).resolve().parents[2]
GATEWAY = "http://localhost:8000"
IDENTITY = "http://localhost:8081"


def env_values():
    result = {}
    for line in (ROOT / "dxos-core" / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def send(method, url, *, token=None, body=None, content_type=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            content = response.read()
            return response.status, json.loads(content) if "json" in response.headers.get("Content-Type", "") else content
    except HTTPError as error:
        content = error.read()
        return error.code, json.loads(content) if "json" in error.headers.get("Content-Type", "") else content


def token(username, password):
    form = urlencode({"grant_type": "password", "client_id": "dxos-cli", "username": username, "password": password}).encode()
    status, result = send("POST", f"{IDENTITY}/realms/dxos/protocol/openid-connect/token", body=form, content_type="application/x-www-form-urlencoded")
    assert status == 200, f"Token request returned {status}"
    return result["access_token"]


def multipart(fields, photo):
    boundary = f"----opencity-{uuid4().hex}"
    parts = []
    for key, value in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"sample.png\"\r\nContent-Type: image/png\r\n\r\n".encode() + photo + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def require(actual, expected, result):
    assert actual == expected, f"Expected HTTP {expected}, got {actual}: {result}"
    return result


def main():
    provision()
    values = env_values()
    citizen = token("dxos-citizen", values["DEMO_CITIZEN_PASSWORD"])
    reports_operator = token("dxos-reports", values["DEMO_OPERATOR_PASSWORD"])
    bulletins_operator = token("dxos-bulletins", values["DEMO_OPERATOR_PASSWORD"])
    surveys_operator = token("dxos-surveys", values["DEMO_OPERATOR_PASSWORD"])
    outsider = token("dxos-outsider", values["DEMO_OUTSIDER_PASSWORD"])
    status, result = send("GET", f"{GATEWAY}/api/opencity/reports")
    require(status, 401, result)  # no token
    for user_token, expected in ((reports_operator, ["reports"]),
                                 (bulletins_operator, ["bulletins"]),
                                 (surveys_operator, ["surveys"])):
        status, capabilities = send("GET", f"{GATEWAY}/api/opencity/me/capabilities", token=user_token)
        require(status, 200, capabilities)
        assert capabilities["management"] == expected
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9xVzgAAAAASUVORK5CYII=")
    body, content_type = multipart({
        "title": "Đèn đường hỏng ở ngõ thử nghiệm",
        "description": "Đèn không sáng trong nhiều buổi tối, cần kiểm tra và sửa chữa.",
        "category": "Chiếu sáng", "address": "Ngõ thử nghiệm số 1",
        "latitude": "21.0285", "longitude": "105.8542",
    }, png)
    status, created = send("POST", f"{GATEWAY}/api/opencity/reports", token=citizen, body=body, content_type=content_type)
    require(status, 201, created)
    assert created["state"] == "submitted" and len(created["attachment_ids"]) == 1 and not created["warnings"]
    report_id = created["id"]
    status, detail = send("GET", f"{GATEWAY}/api/opencity/reports/{report_id}", token=citizen)
    require(status, 200, detail)
    assert detail["history"][0]["action"] == "start"
    status, photo_content = send("GET", f"{GATEWAY}/api/opencity/reports/{report_id}/attachments/{created['attachment_ids'][0]}", token=citizen)
    require(status, 200, photo_content)
    assert photo_content == png
    status, result = send("POST", f"{GATEWAY}/api/opencity/reports/{report_id}/actions/triage", token=citizen)
    require(status, 403, result)
    status, result = send("POST", f"{GATEWAY}/api/opencity/reports/{report_id}/actions/triage", token=bulletins_operator)
    require(status, 403, result)
    status, result = send("GET", f"{GATEWAY}/api/data/records", token=reports_operator)
    require(status, 200, result)
    assert report_id not in {item["id"] for item in result}
    status, result = send("GET", f"{GATEWAY}/api/opencity/reports/{report_id}", token=outsider)
    require(status, 404, result)
    status, other_list = send("GET", f"{GATEWAY}/api/opencity/reports", token=outsider)
    require(status, 200, other_list)
    assert report_id not in {item["id"] for item in other_list}
    for action, expected_state in [("triage", "triaged"), ("assign", "assigned"), ("resolve", "resolved")]:
        status, changed = send("POST", f"{GATEWAY}/api/opencity/reports/{report_id}/actions/{action}", token=reports_operator)
        require(status, 200, changed)
        assert changed["state"] == expected_state
    status, finished = send("GET", f"{GATEWAY}/api/opencity/reports/{report_id}", token=citizen)
    require(status, 200, finished)
    assert finished["state"] == "resolved" and len(finished["history"]) == 4
    status, bulletins = send("GET", f"{GATEWAY}/api/opencity/bulletins", token=citizen)
    require(status, 200, bulletins)
    sample_title = "[DEMO] Cảnh báo thử nghiệm khu vực trung tâm"
    if not any(item["title"] == sample_title for item in bulletins):
        sample = {
            "category": "alert", "title": sample_title,
            "summary": "Đây là dữ liệu minh họa để kiểm tra bản đồ và màn cảnh báo OpenCity.",
            "body": "Bản tin này chỉ dùng trong môi trường phát triển. Không phải thông báo chính thức của cơ quan nhà nước.",
            "area": "Hà Nội (mô phỏng)", "latitude": 21.0285, "longitude": 105.8542,
        }
        status, rejected = send(
            "POST", f"{GATEWAY}/api/opencity/bulletins", token=citizen,
            body=json.dumps(sample).encode(), content_type="application/json",
        )
        require(status, 403, rejected)
        status, created_bulletin = send(
            "POST", f"{GATEWAY}/api/opencity/bulletins", token=bulletins_operator,
            body=json.dumps(sample).encode(), content_type="application/json",
        )
        require(status, 201, created_bulletin)
        status, hidden = send(
            "GET", f"{GATEWAY}/api/opencity/bulletins/{created_bulletin['id']}", token=outsider,
        )
        require(status, 404, hidden)
    news_title = "[DEMO] Bản tin cộng đồng OpenCity"
    if not any(item["title"] == news_title for item in bulletins):
        sample_news = {
            "category": "news", "title": news_title,
            "summary": "Bản tin mẫu để kiểm tra mục Tin tức trong ứng dụng công dân.",
            "body": "Đây là nội dung minh họa trong môi trường phát triển, không phải thông báo chính thức. Đơn vị vận hành có thể đăng bản tin thật qua API backend.",
            "area": "Hà Nội (mô phỏng)",
        }
        status, created_news = send(
            "POST", f"{GATEWAY}/api/opencity/bulletins", token=bulletins_operator,
            body=json.dumps(sample_news).encode(), content_type="application/json",
        )
        require(status, 201, created_news)
    status, surveys = send("GET", f"{GATEWAY}/api/opencity/surveys", token=citizen)
    require(status, 200, surveys)
    survey_title = "[DEMO] Ưu tiên cải thiện không gian công cộng"
    demo_survey = next((item for item in surveys if item["title"] == survey_title), None)
    if demo_survey is None:
        sample_survey = {
            "title": survey_title,
            "description": "Khảo sát minh họa để thử tính năng bình chọn; không phải cuộc lấy ý kiến chính thức.",
            "options": ["Thêm cây xanh", "Cải thiện chiếu sáng", "Bổ sung ghế nghỉ"],
        }
        status, rejected = send("POST", f"{GATEWAY}/api/opencity/surveys", token=citizen,
                                body=json.dumps(sample_survey).encode(), content_type="application/json")
        require(status, 403, rejected)
        status, demo_survey = send("POST", f"{GATEWAY}/api/opencity/surveys", token=surveys_operator,
                                   body=json.dumps(sample_survey).encode(), content_type="application/json")
        require(status, 201, demo_survey)
    survey_id = demo_survey["id"]
    status, hidden = send("GET", f"{GATEWAY}/api/opencity/surveys/{survey_id}", token=outsider)
    require(status, 404, hidden)
    status, detail = send("GET", f"{GATEWAY}/api/opencity/surveys/{survey_id}", token=citizen)
    require(status, 200, detail)
    assert detail["status"] == "open" and len(detail["options"]) == 3
    print("OpenCity smoke passed: reports, images, workflows, bulletins, surveys, roles and tenants.")


if __name__ == "__main__":
    main()
