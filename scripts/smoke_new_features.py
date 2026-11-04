# SPDX-License-Identifier: Apache-2.0
"""Exercise the five new catalog modules through Keycloak and the DX-OS gateway.

Run after provisioning roles and starting the local Compose stack. Uses only clearly
marked demo records in the local demo tenant; repeated runs reuse existing records.
"""

import json

from smoke_app import GATEWAY, env_values, require, send, token


def json_request(method: str, path: str, auth: str, payload: dict | None = None):
    return send(method, f"{GATEWAY}/api/opencity{path}", token=auth,
                body=json.dumps(payload).encode() if payload is not None else None,
                content_type="application/json" if payload is not None else None)


def main() -> None:
    values = env_values()
    citizen = token("dxos-citizen", values["DEMO_CITIZEN_PASSWORD"])
    outsider = token("dxos-outsider", values["DEMO_OUTSIDER_PASSWORD"])
    staff = {feature: token(user, values["DEMO_OPERATOR_PASSWORD"]) for feature, user in (
        ("hotlines", "dxos-hotlines"),
        ("communications", "dxos-communications"),
        ("community_groups", "dxos-community"),
        ("social_feedback", "dxos-social-feedback"),
        ("digital_ward", "dxos-digital-ward"),
    )}
    for feature, auth in staff.items():
        status, capabilities = json_request("GET", "/me/capabilities", auth)
        require(status, 200, capabilities)
        assert capabilities["management"] == [feature], (feature, capabilities)

    def find_or_create(path: str, auth: str, key: str, value: str, body: dict):
        status, rows = json_request("GET", path, auth)
        require(status, 200, rows)
        existing = next((row for row in rows if row[key] == value), None)
        if existing is not None:
            return existing
        status, created = json_request("POST", path, auth, body)
        require(status, 201, created)
        return created

    hotline = find_or_create("/hotlines", staff["hotlines"], "name", "[DEMO] Hỗ trợ OpenCity",
                             {"name": "[DEMO] Hỗ trợ OpenCity", "unit": "Đơn vị thử nghiệm",
                              "phone": "0000000000", "hours": "Demo only", "active": True})
    assert hotline["phone"] == "0000000000"
    communication = find_or_create("/communications", staff["communications"], "title",
                                   "[DEMO] Truyền thông OpenCity",
                                   {"title": "[DEMO] Truyền thông OpenCity",
                                    "summary": "Thông tin minh họa cho môi trường thử nghiệm.",
                                    "body": "Đây là nội dung minh họa, không phải thông báo của cơ quan nhà nước."})
    assert communication["category"] == "campaign"
    status, news = json_request("GET", "/bulletins", citizen)
    require(status, 200, news)
    assert all(item["id"] != communication["id"] for item in news)

    group = find_or_create("/community/groups", staff["community_groups"], "title",
                           "[DEMO] Nhóm cộng đồng OpenCity",
                           {"title": "[DEMO] Nhóm cộng đồng OpenCity",
                            "description": "Nhóm minh họa trao đổi của cư dân trong môi trường thử nghiệm."})
    status, joined = json_request("POST", f"/community/groups/{group['id']}/join", citizen)
    require(status, 200, joined)
    assert joined["joined"]
    status, posts = json_request("GET", f"/community/groups/{group['id']}/posts", citizen)
    require(status, 200, posts)
    if not any(post["body"] == "[DEMO] Bài viết thử nghiệm của cư dân." for post in posts):
        status, post = json_request("POST", f"/community/groups/{group['id']}/posts", citizen,
                                    {"body": "[DEMO] Bài viết thử nghiệm của cư dân."})
        require(status, 201, post)

    topic = find_or_create("/social-feedback/topics", staff["social_feedback"], "title",
                           "[DEMO] Chủ đề lấy ý kiến OpenCity",
                           {"title": "[DEMO] Chủ đề lấy ý kiến OpenCity",
                            "description": "Chủ đề minh họa để kiểm thử chức năng góp ý của cư dân."})
    assert topic["status"] == "open"
    status, opinion = json_request("PUT", f"/social-feedback/topics/{topic['id']}/opinion", citizen,
                                   {"body": "[DEMO] Tôi đồng ý với chủ đề minh họa này."})
    require(status, 200, opinion)
    status, denied = json_request("GET", f"/social-feedback/topics/{topic['id']}/opinions", citizen)
    require(status, 403, denied)
    status, opinions = json_request("GET", f"/social-feedback/topics/{topic['id']}/opinions", staff["social_feedback"])
    require(status, 200, opinions)
    assert any(item["id"] == opinion["id"] for item in opinions)

    ward = find_or_create("/digital-wards", staff["digital_ward"], "code", "DEMO-01",
                          {"code": "DEMO-01", "name": "[DEMO] Phường OpenCity",
                           "address": "Số 1 đường Thử Nghiệm", "phone": "0000000000",
                           "office_hours": "Giờ minh họa", "description": "Điểm phục vụ minh họa, không phải địa chỉ hành chính thật.",
                           "active": True})
    assert ward["active"] and ward["phone"] == "0000000000"

    for path, item_id in (("/communications", communication["id"]),
                          ("/community/groups", group["id"]),
                          ("/social-feedback/topics", topic["id"]),
                          ("/digital-wards", ward["id"])):
        status, rows = json_request("GET", path, citizen)
        require(status, 200, rows)
        assert any(row["id"] == item_id for row in rows), path
        status, other_rows = json_request("GET", path, outsider)
        require(status, 200, other_rows)
        assert all(row["id"] != item_id for row in other_rows), path
    print("PASS: five feature APIs through Keycloak and DX-OS gateway")


if __name__ == "__main__":
    main()
