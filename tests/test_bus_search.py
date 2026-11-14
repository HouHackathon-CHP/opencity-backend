# SPDX-License-Identifier: Apache-2.0
import pytest
from pathlib import Path
import shutil
"""Test suite for OpenCity bus search and route lookup endpoints."""

import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.core import config  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)
BASE_HEADERS = {
    "X-Internal-Secret": "test-secret",
    "X-DXOS-User": "citizen-1",
    "X-DXOS-Tenant": "hanoi",
    "X-DXOS-Roles": "citizen",
}
OPERATOR_HEADERS = {
    **BASE_HEADERS,
    "X-DXOS-User": "bus-operator",
    "X-DXOS-Roles": "bus_search_operator",
}


# Test Fixture Data for CI and isolated tests
from datetime import datetime, timezone
import json
import sqlite3
from app.repositories import bus_search as repo

TEST_FIXTURE_ROUTES = [
    {
        "id": "hn-bus-01",
        "route_number": "01",
        "name": "Bến xe Gia Lâm ⇄ Bến xe Yên Nghĩa",
        "operator": "Transerco (XN Xe buýt Hà Nội)",
        "route_type": "standard",
        "from_terminal": "Bến xe Gia Lâm",
        "to_terminal": "Bến xe Yên Nghĩa",
        "operating_hours": "05:00 - 21:00",
        "frequency": "10 - 15 phút/chuyến",
        "fare": "10.000 đ/lượt",
        "color": "#2563eb",
        "osm_relation_id": "osm-rel-1243101",
        "active": 1,
        "stops": [
            {"id": "stop-gialam-bx", "name": "Bến xe Gia Lâm", "address": "Ngô Gia Khảm, P. Gia Thụy, Q. Long Biên", "latitude": 21.0505, "longitude": 105.8812, "has_shelter": 1},
            {"id": "stop-nvc-540", "name": "540 Nguyễn Văn Cừ", "address": "Nguyễn Văn Cừ, Gia Thụy, Long Biên", "latitude": 21.0478, "longitude": 105.8770, "has_shelter": 1},
            {"id": "stop-nvc-358", "name": "358 Nguyễn Văn Cừ", "address": "Nguyễn Văn Cừ, Bồ Đề, Long Biên", "latitude": 21.0425, "longitude": 105.8678, "has_shelter": 1},
            {"id": "stop-longbien-tc", "name": "Điểm trung chuyển Long Biên", "address": "Đường Yên Phụ, Ba Đình / Hoàn Kiếm", "latitude": 21.0398, "longitude": 105.8495, "has_shelter": 1},
            {"id": "stop-hangdau", "name": "Vườn hoa Hàng Đậu", "address": "Phố Hàng Đậu, Quán Thánh, Ba Đình", "latitude": 21.0392, "longitude": 105.8452, "has_shelter": 1},
            {"id": "stop-cuanam", "name": "Cửa Nam - Phủ Doãn", "address": "Phố Phủ Doãn, Hàng Bông, Hoàn Kiếm", "latitude": 21.0289, "longitude": 105.8465, "has_shelter": 0},
            {"id": "stop-khamthien-ga", "name": "Khâm Thiên (Gần Ga Hà Nội)", "address": "Phố Khâm Thiên, Đống Đa", "latitude": 21.0212, "longitude": 105.8398, "has_shelter": 1},
            {"id": "stop-ochodua", "name": "Ô Chợ Dừa", "address": "Nút giao Ô Chợ Dừa, Đống Đa", "latitude": 21.0185, "longitude": 105.8288, "has_shelter": 1},
            {"id": "stop-tayson-dhcd", "name": "Đại học Công Đoàn - Tây Sơn", "address": "Phố Tây Sơn, Quang Trung, Đống Đa", "latitude": 21.0118, "longitude": 105.8235, "has_shelter": 1},
            {"id": "stop-tayson-dhtl", "name": "Đại học Thủy Lợi - Tây Sơn", "address": "175 Tây Sơn, Trung Liệt, Đống Đa", "latitude": 21.0076, "longitude": 105.8202, "has_shelter": 1},
            {"id": "stop-ngatuso", "name": "Ngã Tư Sở (Royal City)", "address": "Đầu đường Nguyễn Trãi, Thanh Xuân", "latitude": 21.0022, "longitude": 105.8155, "has_shelter": 1},
            {"id": "stop-nguyentrai-dhkh", "name": "ĐH Khoa học Tự nhiên - Nguyễn Trãi", "address": "334 Nguyễn Trãi, Thanh Xuân Trung", "latitude": 20.9950, "longitude": 105.8078, "has_shelter": 1},
            {"id": "stop-nguyentrai-dhhn", "name": "Đại học Hà Nội - Nguyễn Trãi", "address": "Km 9 Nguyễn Trãi, Trung Văn, Nam Từ Liêm", "latitude": 20.9855, "longitude": 105.7952, "has_shelter": 1},
            {"id": "stop-tranphu-hvbc", "name": "Học viện Bưu chính Viễn thông", "address": "Đường Trần Phú, Mộ Lao, Hà Đông", "latitude": 20.9802, "longitude": 105.7876, "has_shelter": 1},
            {"id": "stop-tranphu-buhadong", "name": "Bưu điện Hà Đông", "address": "Đường Quang Trung, P. Quang Trung, Hà Đông", "latitude": 20.9712, "longitude": 105.7765, "has_shelter": 1},
            {"id": "stop-quangtrung-bala", "name": "Ngã ba Ba La", "address": "Quang Trung, Phú La, Hà Đông", "latitude": 20.9592, "longitude": 105.7602, "has_shelter": 1},
            {"id": "stop-yennghia-bx", "name": "Bến xe Yên Nghĩa", "address": "QL6, P. Yên Nghĩa, Q. Hà Đông", "latitude": 20.9495, "longitude": 105.7468, "has_shelter": 1},
        ],
        "forward_path": [
            [105.8812, 21.0505], [105.8770, 21.0478], [105.8678, 21.0425], [105.8560, 21.0410],
            [105.8495, 21.0398], [105.8452, 21.0392], [105.8465, 21.0289], [105.8398, 21.0212],
            [105.8288, 21.0185], [105.8235, 21.0118], [105.8202, 21.0076], [105.8155, 21.0022],
            [105.8078, 20.9950], [105.7952, 20.9855], [105.7876, 20.9802], [105.7765, 20.9712],
            [105.7602, 20.9592], [105.7468, 20.9495]
        ],
    },
    {
        "id": "hn-bus-02",
        "route_number": "02",
        "name": "Bác Cổ ⇄ Bến xe Yên Nghĩa",
        "operator": "Transerco (XN Xe buýt Hà Nội)",
        "route_type": "standard",
        "from_terminal": "Bác Cổ (Bảo tàng Lịch sử)",
        "to_terminal": "Bến xe Yên Nghĩa",
        "operating_hours": "05:00 - 22:30",
        "frequency": "8 - 12 phút/chuyến",
        "fare": "10.000 đ/lượt",
        "color": "#0284c7",
        "osm_relation_id": "osm-rel-1243102",
        "active": 1,
        "stops": [
            {"id": "stop-bacco", "name": "Bác Cổ - Tràng Tiền", "address": "Phố Tràng Tiền, Phan Chu Trinh, Hoàn Kiếm", "latitude": 21.0248, "longitude": 105.8588, "has_shelter": 1},
            {"id": "stop-trangtien-plaza", "name": "Tràng Tiền Plaza", "address": "Đinh Tiên Hoàng - Hàng Bài, Hoàn Kiếm", "latitude": 21.0255, "longitude": 105.8530, "has_shelter": 1},
            {"id": "stop-quansu-bvk", "name": "Bệnh viện K - Quán Sứ", "address": "Phố Quán Sứ, Trần Hưng Đạo, Hoàn Kiếm", "latitude": 21.0240, "longitude": 105.8460, "has_shelter": 1},
            {"id": "stop-gahanoi", "name": "Ga Hà Nội", "address": "Đường Lê Duẩn, Văn Miếu, Đống Đa", "latitude": 21.0245, "longitude": 105.8415, "has_shelter": 1},
            {"id": "stop-khamthien-ga", "name": "Khâm Thiên (Gần Ga Hà Nội)", "address": "Phố Khâm Thiên, Đống Đa", "latitude": 21.0212, "longitude": 105.8398, "has_shelter": 1},
            {"id": "stop-tayson-dhcd", "name": "Đại học Công Đoàn - Tây Sơn", "address": "Phố Tây Sơn, Quang Trung, Đống Đa", "latitude": 21.0118, "longitude": 105.8235, "has_shelter": 1},
            {"id": "stop-ngatuso", "name": "Ngã Tư Sở (Royal City)", "address": "Đầu đường Nguyễn Trãi, Thanh Xuân", "latitude": 21.0022, "longitude": 105.8155, "has_shelter": 1},
            {"id": "stop-nguyentrai-dhhn", "name": "Đại học Hà Nội - Nguyễn Trãi", "address": "Km 9 Nguyễn Trãi, Trung Văn, Nam Từ Liêm", "latitude": 20.9855, "longitude": 105.7952, "has_shelter": 1},
            {"id": "stop-tranphu-hvbc", "name": "Học viện Bưu chính Viễn thông", "address": "Đường Trần Phú, Mộ Lao, Hà Đông", "latitude": 20.9802, "longitude": 105.7876, "has_shelter": 1},
            {"id": "stop-tranphu-buhadong", "name": "Bưu điện Hà Đông", "address": "Đường Quang Trung, P. Quang Trung, Hà Đông", "latitude": 20.9712, "longitude": 105.7765, "has_shelter": 1},
            {"id": "stop-yennghia-bx", "name": "Bến xe Yên Nghĩa", "address": "QL6, P. Yên Nghĩa, Q. Hà Đông", "latitude": 20.9495, "longitude": 105.7468, "has_shelter": 1},
        ],
        "forward_path": [
            [105.8588, 21.0248], [105.8530, 21.0255], [105.8460, 21.0240], [105.8415, 21.0245],
            [105.8398, 21.0212], [105.8235, 21.0118], [105.8155, 21.0022], [105.7952, 20.9855],
            [105.7876, 20.9802], [105.7765, 20.9712], [105.7468, 20.9495]
        ],
    },
    {
        "id": "hn-bus-03a",
        "route_number": "03A",
        "name": "Bến xe Giáp Bát ⇄ Bến xe Gia Lâm",
        "operator": "Transerco (Xí nghiệp Buýt Hà Nội)",
        "route_type": "standard",
        "from_terminal": "Bến xe Giáp Bát",
        "to_terminal": "Bến xe Gia Lâm",
        "operating_hours": "05:00 - 21:00",
        "frequency": "10 - 15 phút/chuyến",
        "fare": "10.000 đ/lượt",
        "color": "#16a34a",
        "osm_relation_id": "osm-rel-1243103",
        "active": 1,
        "stops": [
            {"id": "stop-giapbat-bx", "name": "Bến xe Giáp Bát", "address": "Km 6 Đường Giải Phóng, Giáp Bát, Hoàng Mai", "latitude": 20.9818, "longitude": 105.8425, "has_shelter": 1},
            {"id": "stop-giaiphong-dhbk", "name": "Đại học Bách Khoa - Giải Phóng", "address": "Đường Giải Phóng, Đồng Tâm, Hai Bà Trưng", "latitude": 21.0042, "longitude": 105.8428, "has_shelter": 1},
            {"id": "stop-giaiphong-bachmai", "name": "Bệnh viện Bạch Mai", "address": "78 Giải Phóng, Phương Mai, Đống Đa", "latitude": 21.0025, "longitude": 105.8422, "has_shelter": 1},
            {"id": "stop-gahanoi", "name": "Ga Hà Nội", "address": "Đường Lê Duẩn, Văn Miếu, Đống Đa", "latitude": 21.0245, "longitude": 105.8415, "has_shelter": 1},
            {"id": "stop-trannhatduat", "name": "Trần Nhật Duật (Ô Quan Chưởng)", "address": "Phố Trần Nhật Duật, Hàng Buồm, Hoàn Kiếm", "latitude": 21.0365, "longitude": 105.8542, "has_shelter": 1},
            {"id": "stop-longbien-tc", "name": "Điểm trung chuyển Long Biên", "address": "Đường Yên Phụ, Ba Đình / Hoàn Kiếm", "latitude": 21.0398, "longitude": 105.8495, "has_shelter": 1},
            {"id": "stop-nvc-358", "name": "358 Nguyễn Văn Cừ", "address": "Nguyễn Văn Cừ, Bồ Đề, Long Biên", "latitude": 21.0425, "longitude": 105.8678, "has_shelter": 1},
            {"id": "stop-gialam-bx", "name": "Bến xe Gia Lâm", "address": "Ngô Gia Khảm, P. Gia Thụy, Q. Long Biên", "latitude": 21.0505, "longitude": 105.8812, "has_shelter": 1},
        ],
        "forward_path": [
            [105.8425, 20.9818], [105.8428, 21.0042], [105.8422, 21.0025], [105.8415, 21.0245],
            [105.8542, 21.0365], [105.8495, 21.0398], [105.8678, 21.0425], [105.8812, 21.0505]
        ],
    },
    {
        "id": "hn-bus-32",
        "route_number": "32",
        "name": "Bến xe Giáp Bát ⇄ Nhổn (ĐH Công nghiệp HN)",
        "operator": "Transerco (Xí nghiệp Xe điện Hà Nội)",
        "route_type": "standard",
        "from_terminal": "Bến xe Giáp Bát",
        "to_terminal": "Nhổn (Đại học Công nghiệp)",
        "operating_hours": "05:00 - 22:30",
        "frequency": "5 - 10 phút/chuyến",
        "fare": "10.000 đ/lượt",
        "color": "#d97706",
        "osm_relation_id": "osm-rel-1243132",
        "active": 1,
        "stops": [
            {"id": "stop-giapbat-bx", "name": "Bến xe Giáp Bát", "address": "Km 6 Đường Giải Phóng, Giáp Bát, Hoàng Mai", "latitude": 20.9818, "longitude": 105.8425, "has_shelter": 1},
            {"id": "stop-giaiphong-dhbk", "name": "Đại học Bách Khoa - Giải Phóng", "address": "Đường Giải Phóng, Đồng Tâm, Hai Bà Trưng", "latitude": 21.0042, "longitude": 105.8428, "has_shelter": 1},
            {"id": "stop-gahanoi", "name": "Ga Hà Nội", "address": "Đường Lê Duẩn, Văn Miếu, Đống Đa", "latitude": 21.0245, "longitude": 105.8415, "has_shelter": 1},
            {"id": "stop-nguyenthaihoc", "name": "Nguyễn Thái Học (Cửa Nam)", "address": "Phố Nguyễn Thái Học, Điện Biên, Ba Đình", "latitude": 21.0305, "longitude": 105.8362, "has_shelter": 1},
            {"id": "stop-kimma-tc", "name": "Điểm trung chuyển Cầu Giấy (ĐH GTVT)", "address": "Đường Cầu Giấy, Ngọc Khánh, Ba Đình", "latitude": 21.0322, "longitude": 105.8028, "has_shelter": 1},
            {"id": "stop-xuanthuy-dhqg", "name": "Đại học Quốc gia Hà Nội - Xuân Thủy", "address": "144 Xuân Thủy, Dịch Vọng Hậu, Cầu Giấy", "latitude": 21.0368, "longitude": 105.7820, "has_shelter": 1},
            {"id": "stop-hotungmau-dhtm", "name": "Đại học Thương Mại - Hồ Tùng Mậu", "address": "79 Hồ Tùng Mậu, Mai Dịch, Cầu Giấy", "latitude": 21.0385, "longitude": 105.7725, "has_shelter": 1},
            {"id": "stop-caudien", "name": "Cầu Diễn", "address": "Đường Cầu Diễn, Phúc Diễn, Bắc Từ Liêm", "latitude": 21.0422, "longitude": 105.7558, "has_shelter": 1},
            {"id": "stop-nhon-dhcn", "name": "Bến xe Nhổn (ĐH Công nghiệp)", "address": "QL32, Tây Tựu / Minh Khai, Bắc Từ Liêm", "latitude": 21.0545, "longitude": 105.7342, "has_shelter": 1},
        ],
        "forward_path": [
            [105.8425, 20.9818], [105.8428, 21.0042], [105.8415, 21.0245], [105.8362, 21.0305],
            [105.8028, 21.0322], [105.7820, 21.0368], [105.7725, 21.0385], [105.7558, 21.0422],
            [105.7342, 21.0545]
        ],
    },
    {
        "id": "hn-bus-34",
        "route_number": "34",
        "name": "Bến xe Mỹ Đình ⇄ Bến xe Gia Lâm",
        "operator": "Transerco (Xí nghiệp Buýt 10-10)",
        "route_type": "standard",
        "from_terminal": "Bến xe Mỹ Đình",
        "to_terminal": "Bến xe Gia Lâm",
        "operating_hours": "05:07 - 21:00",
        "frequency": "10 - 15 phút/chuyến",
        "fare": "10.000 đ/lượt",
        "color": "#ea580c",
        "osm_relation_id": "osm-rel-1243134",
        "active": 1,
        "stops": [
            {"id": "stop-mydinh-bx", "name": "Bến xe Mỹ Đình", "address": "Số 20 Phạm Hùng, Mỹ Đình 2, Nam Từ Liêm", "latitude": 21.0285, "longitude": 105.7780, "has_shelter": 1},
            {"id": "stop-xuanthuy-dhqg", "name": "Đại học Quốc gia Hà Nội - Xuân Thủy", "address": "144 Xuân Thủy, Dịch Vọng Hậu, Cầu Giấy", "latitude": 21.0368, "longitude": 105.7820, "has_shelter": 1},
            {"id": "stop-kimma-tc", "name": "Điểm trung chuyển Cầu Giấy (ĐH GTVT)", "address": "Đường Cầu Giấy, Ngọc Khánh, Ba Đình", "latitude": 21.0322, "longitude": 105.8028, "has_shelter": 1},
            {"id": "stop-kimma-535", "name": "535 Kim Mã", "address": "Phố Kim Mã, Ngọc Khánh, Ba Đình", "latitude": 21.0315, "longitude": 105.8150, "has_shelter": 1},
            {"id": "stop-nguyenthaihoc", "name": "Nguyễn Thái Học (Cửa Nam)", "address": "Phố Nguyễn Thái Học, Điện Biên, Ba Đình", "latitude": 21.0305, "longitude": 105.8362, "has_shelter": 1},
            {"id": "stop-hangdau", "name": "Vườn hoa Hàng Đậu", "address": "Phố Hàng Đậu, Quán Thánh, Ba Đình", "latitude": 21.0392, "longitude": 105.8452, "has_shelter": 1},
            {"id": "stop-longbien-tc", "name": "Điểm trung chuyển Long Biên", "address": "Đường Yên Phụ, Ba Đình / Hoàn Kiếm", "latitude": 21.0398, "longitude": 105.8495, "has_shelter": 1},
            {"id": "stop-nvc-358", "name": "358 Nguyễn Văn Cừ", "address": "Nguyễn Văn Cừ, Bồ Đề, Long Biên", "latitude": 21.0425, "longitude": 105.8678, "has_shelter": 1},
            {"id": "stop-gialam-bx", "name": "Bến xe Gia Lâm", "address": "Ngô Gia Khảm, P. Gia Thụy, Q. Long Biên", "latitude": 21.0505, "longitude": 105.8812, "has_shelter": 1},
        ],
        "forward_path": [
            [105.7780, 21.0285], [105.7820, 21.0368], [105.8028, 21.0322], [105.8150, 21.0315],
            [105.8362, 21.0305], [105.8452, 21.0392], [105.8495, 21.0398], [105.8678, 21.0425],
            [105.8812, 21.0505]
        ],
    },
    {
        "id": "hn-bus-brt01",
        "route_number": "BRT 01",
        "name": "Kim Mã ⇄ Bến xe Yên Nghĩa (Buýt nhanh BRT)",
        "operator": "Hanoi BRT (Trung tâm Vận hành BRT)",
        "route_type": "brt",
        "from_terminal": "Bến xe Kim Mã",
        "to_terminal": "Bến xe Yên Nghĩa",
        "operating_hours": "05:00 - 22:00",
        "frequency": "5 - 10 phút/chuyến",
        "fare": "10.000 đ/lượt",
        "color": "#dc2626",
        "osm_relation_id": "osm-rel-6697001",
        "active": 1,
        "stops": [
            {"id": "stop-brt-kimma", "name": "Nhà chờ BRT Kim Mã", "address": "Bến xe Kim Mã, Giảng Võ, Ba Đình", "latitude": 21.0308, "longitude": 105.8242, "has_shelter": 1},
            {"id": "stop-brt-giangvo", "name": "Nhà chờ BRT Giảng Võ", "address": "Đường Giảng Võ, Cát Linh, Đống Đa", "latitude": 21.0268, "longitude": 105.8220, "has_shelter": 1},
            {"id": "stop-brt-vungocphan", "name": "Nhà chờ BRT Vũ Ngọc Phan", "address": "Đường Láng Hạ, Thành Công, Đống Đa", "latitude": 21.0182, "longitude": 105.8142, "has_shelter": 1},
            {"id": "stop-brt-hoangdaothuy", "name": "Nhà chờ BRT Hoàng Đạo Thúy", "address": "Đường Lê Văn Lương, Trung Hòa, Cầu Giấy", "latitude": 21.0078, "longitude": 105.8025, "has_shelter": 1},
            {"id": "stop-brt-khuatduytien", "name": "Nhà chờ BRT Khuất Duy Tiến", "address": "Nút giao Vành đai 3 - Tố Hữu, Thanh Xuân", "latitude": 20.9995, "longitude": 105.7922, "has_shelter": 1},
            {"id": "stop-brt-luongthevinh", "name": "Nhà chờ BRT Lương Thế Vinh", "address": "Đường Tố Hữu, Trung Văn, Nam Từ Liêm", "latitude": 20.9928, "longitude": 105.7845, "has_shelter": 1},
            {"id": "stop-brt-vanphuc", "name": "Nhà chờ BRT Vạn Phúc", "address": "Đường Tố Hữu, P. Vạn Phúc, Hà Đông", "latitude": 20.9805, "longitude": 105.7712, "has_shelter": 1},
            {"id": "stop-brt-lakhe", "name": "Nhà chờ BRT La Khê", "address": "Đường Quang Trung nối dài, La Khê, Hà Đông", "latitude": 20.9675, "longitude": 105.7595, "has_shelter": 1},
            {"id": "stop-quangtrung-bala", "name": "Ngã ba Ba La", "address": "Quang Trung, Phú La, Hà Đông", "latitude": 20.9592, "longitude": 105.7602, "has_shelter": 1},
            {"id": "stop-yennghia-bx", "name": "Bến xe Yên Nghĩa", "address": "QL6, P. Yên Nghĩa, Q. Hà Đông", "latitude": 20.9495, "longitude": 105.7468, "has_shelter": 1},
        ],
        "forward_path": [
            [105.8242, 21.0308], [105.8220, 21.0268], [105.8142, 21.0182], [105.8025, 21.0078],
            [105.7922, 20.9995], [105.7845, 20.9928], [105.7712, 20.9805], [105.7595, 20.9675],
            [105.7602, 20.9592], [105.7468, 20.9495]
        ],
    },
    {
        "id": "hn-bus-e01",
        "route_number": "E01",
        "name": "Bến xe Mỹ Đình ⇄ KĐT Vinhomes Ocean Park (Buýt điện)",
        "operator": "VinBus (Công ty VinBus)",
        "route_type": "electric",
        "from_terminal": "Bến xe Mỹ Đình",
        "to_terminal": "Khu đô thị Vinhomes Ocean Park",
        "operating_hours": "05:00 - 22:00",
        "frequency": "12 - 20 phút/chuyến",
        "fare": "10.000 đ/lượt",
        "color": "#10b981",
        "osm_relation_id": "osm-rel-1301001",
        "active": 1,
        "stops": [
            {"id": "stop-mydinh-bx", "name": "Bến xe Mỹ Đình", "address": "Số 20 Phạm Hùng, Mỹ Đình 2, Nam Từ Liêm", "latitude": 21.0285, "longitude": 105.7780, "has_shelter": 1},
            {"id": "stop-metri-keangnam", "name": "Keangnam Landmark 72", "address": "Đường Phạm Hùng, Mễ Trì, Nam Từ Liêm", "latitude": 21.0168, "longitude": 105.7842, "has_shelter": 1},
            {"id": "stop-ngatuso", "name": "Ngã Tư Sở (Royal City)", "address": "Đầu đường Nguyễn Trãi, Thanh Xuân", "latitude": 21.0022, "longitude": 105.8155, "has_shelter": 1},
            {"id": "stop-giaiphong-bachmai", "name": "Bệnh viện Bạch Mai", "address": "78 Giải Phóng, Phương Mai, Đống Đa", "latitude": 21.0025, "longitude": 105.8422, "has_shelter": 1},
            {"id": "stop-timescity", "name": "Times City (Minh Khai)", "address": "458 Minh Khai, Vĩnh Tuy, Hai Bà Trưng", "latitude": 20.9968, "longitude": 105.8685, "has_shelter": 1},
            {"id": "stop-aeon-longbien", "name": "Aeon Mall Long Biên", "address": "Số 27 Cổ Linh, Long Biên", "latitude": 21.0258, "longitude": 105.9015, "has_shelter": 1},
            {"id": "stop-oceanpark", "name": "KĐT Vinhomes Ocean Park", "address": "Đa Tốn, Gia Lâm, Hà Nội", "latitude": 20.9882, "longitude": 105.9425, "has_shelter": 1},
        ],
        "forward_path": [
            [105.7780, 21.0285], [105.7842, 21.0168], [105.8155, 21.0022], [105.8422, 21.0025],
            [105.8685, 20.9968], [105.9015, 21.0258], [105.9425, 20.9882]
        ],
    },
    {
        "id": "hn-bus-e03",
        "route_number": "E03",
        "name": "Cầu Diễn ⇄ KĐT Vinhomes Ocean Park (Buýt điện)",
        "operator": "VinBus (Công ty VinBus)",
        "route_type": "electric",
        "from_terminal": "Cầu Diễn (Bắc Từ Liêm)",
        "to_terminal": "Khu đô thị Vinhomes Ocean Park",
        "operating_hours": "05:00 - 21:00",
        "frequency": "15 - 20 phút/chuyến",
        "fare": "10.000 đ/lượt",
        "color": "#059669",
        "osm_relation_id": "osm-rel-1301003",
        "active": 1,
        "stops": [
            {"id": "stop-caudien", "name": "Cầu Diễn", "address": "Đường Cầu Diễn, Phúc Diễn, Bắc Từ Liêm", "latitude": 21.0422, "longitude": 105.7558, "has_shelter": 1},
            {"id": "stop-hotungmau-dhtm", "name": "Đại học Thương Mại - Hồ Tùng Mậu", "address": "79 Hồ Tùng Mậu, Mai Dịch, Cầu Giấy", "latitude": 21.0385, "longitude": 105.7725, "has_shelter": 1},
            {"id": "stop-xuanthuy-dhqg", "name": "Đại học Quốc gia Hà Nội - Xuân Thủy", "address": "144 Xuân Thủy, Dịch Vọng Hậu, Cầu Giấy", "latitude": 21.0368, "longitude": 105.7820, "has_shelter": 1},
            {"id": "stop-kimma-tc", "name": "Điểm trung chuyển Cầu Giấy (ĐH GTVT)", "address": "Đường Cầu Giấy, Ngọc Khánh, Ba Đình", "latitude": 21.0322, "longitude": 105.8028, "has_shelter": 1},
            {"id": "stop-nguyenthaihoc", "name": "Nguyễn Thái Học (Cửa Nam)", "address": "Phố Nguyễn Thái Học, Điện Biên, Ba Đình", "latitude": 21.0305, "longitude": 105.8362, "has_shelter": 1},
            {"id": "stop-trangtien-plaza", "name": "Tràng Tiền Plaza", "address": "Đinh Tiên Hoàng - Hàng Bài, Hoàn Kiếm", "latitude": 21.0255, "longitude": 105.8530, "has_shelter": 1},
            {"id": "stop-timescity", "name": "Times City (Minh Khai)", "address": "458 Minh Khai, Vĩnh Tuy, Hai Bà Trưng", "latitude": 20.9968, "longitude": 105.8685, "has_shelter": 1},
            {"id": "stop-oceanpark", "name": "KĐT Vinhomes Ocean Park", "address": "Đa Tốn, Gia Lâm, Hà Nội", "latitude": 20.9882, "longitude": 105.9425, "has_shelter": 1},
        ],
        "forward_path": [
            [105.7558, 21.0422], [105.7725, 21.0385], [105.7820, 21.0368], [105.8028, 21.0322],
            [105.8362, 21.0305], [105.8530, 21.0255], [105.8685, 20.9968], [105.9425, 20.9882]
        ],
    },
]


def _unaccent(s: str | None) -> str:
    if not s:
        return ""
    normalized = unicodedata.normalize('NFKD', str(s))
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    stripped = stripped.replace('đ', 'd').replace('Đ', 'd')
    return stripped.lower()


def _db_connection() -> sqlite3.Connection:
    db_path = Path(config.BUS_SEARCH_DB_PATH)
    if not db_path.exists() or db_path.stat().st_size < 100_000:
        alt_path = Path("opencity-backend-main") / db_path
        if alt_path.exists() and alt_path.stat().st_size > (db_path.stat().st_size if db_path.exists() else 0):
            db_path = alt_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.create_function("py_lower", 1, _unaccent)
    return conn


def init_db() -> None:
    with closing(_db_connection()) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bus_routes (
                id TEXT PRIMARY KEY,
                route_number TEXT NOT NULL,
                name TEXT NOT NULL,
                operator TEXT NOT NULL,
                route_type TEXT NOT NULL,
                from_terminal TEXT NOT NULL,
                to_terminal TEXT NOT NULL,
                operating_hours TEXT NOT NULL,
                frequency TEXT NOT NULL,
                fare TEXT NOT NULL,
                color TEXT NOT NULL,
                osm_relation_id TEXT,
                direction_forward_path TEXT NOT NULL,
                direction_backward_path TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bus_stops (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                osm_node_id TEXT,
                has_shelter INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bus_route_stops (
                id TEXT PRIMARY KEY,
                route_id TEXT NOT NULL,
                stop_id TEXT NOT NULL,
                direction TEXT NOT NULL,
                stop_order INTEGER NOT NULL,
                FOREIGN KEY (route_id) REFERENCES bus_routes(id),
                FOREIGN KEY (stop_id) REFERENCES bus_stops(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bus_sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bus_routes_num ON bus_routes(route_number)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bus_route_stops_route ON bus_route_stops(route_id, direction)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bus_route_stops_stop ON bus_route_stops(stop_id)")

        # Check if seed is needed
        row = conn.execute("SELECT COUNT(*) as count FROM bus_routes").fetchone()
        if row and row["count"] == 0:
            _seed_test_data(conn)


def _seed_test_data(conn: sqlite3.Connection) -> None:
    now_str = datetime.now(timezone.utc).isoformat()
    seen_stops: dict[str, dict] = {}

    for r in TEST_FIXTURE_ROUTES:
        # Backward path is reversed forward path
        forward_path = r["forward_path"]
        backward_path = list(reversed(forward_path))

        conn.execute("""
            INSERT OR REPLACE INTO bus_routes (
                id, route_number, name, operator, route_type, from_terminal,
                to_terminal, operating_hours, frequency, fare, color,
                osm_relation_id, direction_forward_path, direction_backward_path,
                active, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            r["id"], r["route_number"], r["name"], r["operator"], r["route_type"],
            r["from_terminal"], r["to_terminal"], r["operating_hours"], r["frequency"],
            r["fare"], r["color"], r.get("osm_relation_id"),
            json.dumps(forward_path), json.dumps(backward_path), now_str
        ))

        stops = r["stops"]
        for idx, stop in enumerate(stops, start=1):
            if stop["id"] not in seen_stops:
                seen_stops[stop["id"]] = stop
                conn.execute("""
                    INSERT OR REPLACE INTO bus_stops (
                        id, name, address, latitude, longitude, osm_node_id,
                        has_shelter, active, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """, (
                    stop["id"], stop["name"], stop["address"], stop["latitude"],
                    stop["longitude"], f"osm-node-{stop['id']}", stop.get("has_shelter", 0),
                    now_str
                ))

            # Forward stop order
            conn.execute("""
                INSERT OR REPLACE INTO bus_route_stops (
                    id, route_id, stop_id, direction, stop_order
                ) VALUES (?, ?, ?, 'forward', ?)
            """, (f"{r['id']}-fwd-{idx}", r["id"], stop["id"], idx))

            # Backward stop order (reversed)
            backward_idx = len(stops) - idx + 1
            conn.execute("""
                INSERT OR REPLACE INTO bus_route_stops (
                    id, route_id, stop_id, direction, stop_order
                ) VALUES (?, ?, ?, 'backward', ?)
            """, (f"{r['id']}-bwd-{backward_idx}", r["id"], stop["id"], backward_idx))

    conn.execute("""
        INSERT OR REPLACE INTO bus_sync_meta (key, value)
        VALUES ('last_synced_at', ?), ('data_source', 'OpenStreetMap Public Transport Schema v2 (ODbL 1.0)')
    """, (now_str,))




@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_bus.sqlite3"
    monkeypatch.setattr(config, "BUS_SEARCH_DB_PATH", str(test_db))
    repo.init_db()
    with repo.closing(repo._db_connection()) as conn, conn:
        _seed_test_data(conn)


def test_bus_routes_list_and_filter(monkeypatch, tmp_path):

    assert client.get("/bus/routes").status_code == 403

    resp = client.get("/bus/routes", headers=BASE_HEADERS)
    assert resp.status_code == 200
    routes = resp.json()
    assert len(routes) >= 7
    numbers = [r["route_number"] for r in routes]
    assert "01" in numbers
    assert "32" in numbers
    assert any(brt in numbers for brt in ("BRT 01", "BRT01"))
    assert "E01" in numbers

    filter_resp = client.get("/bus/routes?keyword=01", headers=BASE_HEADERS)
    assert filter_resp.status_code == 200
    filtered_numbers = [r["route_number"] for r in filter_resp.json()]
    assert "01" in filtered_numbers

    brt_resp = client.get("/bus/routes?route_type=brt", headers=BASE_HEADERS)
    assert brt_resp.status_code == 200
    assert len(brt_resp.json()) == 1
    assert brt_resp.json()[0]["route_number"] in ("BRT 01", "BRT01")


def test_bus_route_detail(monkeypatch, tmp_path):

    resp = client.get("/bus/routes/hn-bus-01", headers=BASE_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["route_number"] == "01"
    assert len(data["forward_stops"]) > 0
    assert len(data["backward_stops"]) > 0
    assert len(data["forward_path"]) > 0
    assert data["forward_stops"][0]["name"] == "Bến xe Gia Lâm"

    assert client.get("/bus/routes/non-existent-route", headers=BASE_HEADERS).status_code == 404


def test_bus_stops_list_and_detail(monkeypatch, tmp_path):

    resp = client.get("/bus/stops", headers=BASE_HEADERS)
    assert resp.status_code == 200
    stops = resp.json()
    assert len(stops) > 0

    filter_resp = client.get("/bus/stops?keyword=Gia%20L%C3%A2m", headers=BASE_HEADERS)
    assert filter_resp.status_code == 200
    matching = filter_resp.json()
    assert any("Gia Lâm" in s["name"] for s in matching)

    stop_id = stops[0]["id"]
    detail_resp = client.get(f"/bus/stops/{stop_id}", headers=BASE_HEADERS)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == stop_id
    assert "passing_routes" in detail_resp.json()


def test_bus_find_connection(monkeypatch, tmp_path):

    resp = client.get("/bus/find?from_query=Gia%20L%C3%A2m&to_query=Y%C3%AAn%20Ngh%C4%A9a", headers=BASE_HEADERS)
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) > 0
    assert recs[0]["route_number"] == "01"
    assert recs[0]["board_stop"]["name"] == "Bến xe Gia Lâm"
    assert recs[0]["alight_stop"]["name"] == "Bến xe Yên Nghĩa"


def test_bus_audit_report(monkeypatch, tmp_path):

    resp = client.get("/bus/audit", headers=BASE_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_routes"] >= 7
    assert data["total_stops"] >= 15
    assert data["completeness_percentage"] > 0
    assert "OpenStreetMap" in data["osm_data_source"]
    assert "ODbL" in data["license"]
    assert "overpass_query_sample" in data


def test_bus_import_and_sync(monkeypatch, tmp_path):

    sample_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [105.80, 21.02]},
                "properties": {"name": "Trạm Thử Nghiệm", "shelter": "yes", "ref": "999"}
            }
        ]
    }
    assert client.post(
        "/bus/import",
        headers=BASE_HEADERS,
        json={"source_name": "Test", "data_format": "geojson", "payload": sample_geojson}
    ).status_code == 403
    assert client.post(
        "/bus/import",
        headers={**BASE_HEADERS, "X-DXOS-Roles": "reports_operator"},
        json={"source_name": "Test", "data_format": "geojson", "payload": sample_geojson}
    ).status_code == 403
    assert client.post("/bus/sync", headers=BASE_HEADERS, json={}).status_code == 403
    assert client.post(
        "/bus/sync",
        headers=OPERATOR_HEADERS,
        json={"overpass_url": "http://127.0.0.1:8081/admin"},
    ).status_code == 422

    import_resp = client.post(
        "/bus/import",
        headers=OPERATOR_HEADERS,
        json={"source_name": "Test", "data_format": "geojson", "payload": sample_geojson}
    )
    assert import_resp.status_code == 200
    assert import_resp.json()["success"] is True

    sync_resp = client.post("/bus/sync", headers=OPERATOR_HEADERS, json={})
    assert sync_resp.status_code == 200
    assert "routes_synced" in sync_resp.json()


def test_manual_route_crud(monkeypatch, tmp_path):

    route_payload = {
        "route_number": "999",
        "name": "Tuyến 999: Mỹ Đình - Long Biên",
        "operator": "Transerco",
        "route_type": "standard",
        "from_terminal": "Bến xe Mỹ Đình",
        "to_terminal": "Bến xe Long Biên",
        "operating_hours": "05:00 - 21:00",
        "frequency": "15 phút/chuyến",
        "fare": "8.000 đ/lượt",
        "color": "#16a34a",
    }

    assert client.post("/bus/routes", headers=BASE_HEADERS, json=route_payload).status_code == 403

    create_resp = client.post("/bus/routes", headers=OPERATOR_HEADERS, json=route_payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["route_number"] == "999"
    assert created["name"] == "Tuyến 999: Mỹ Đình - Long Biên"
    route_id = created["id"]

    assert client.put(f"/bus/routes/{route_id}", headers=BASE_HEADERS, json={"name": "Tuyến 999 Mới"}).status_code == 403

    update_resp = client.put(f"/bus/routes/{route_id}", headers=OPERATOR_HEADERS, json={"name": "Tuyến 999 Mới"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Tuyến 999 Mới"

    delete_resp = client.delete(f"/bus/routes/{route_id}", headers=OPERATOR_HEADERS)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["success"] is True

    assert client.get(f"/bus/routes/{route_id}", headers=BASE_HEADERS).status_code == 404


def test_manual_stop_crud(monkeypatch, tmp_path):

    stop_payload = {
        "name": "Trạm Thử Nghiệm Mới 123",
        "address": "45 Cầu Giấy, Hà Nội",
        "latitude": 21.031,
        "longitude": 105.795,
        "has_shelter": True,
        "routes": ["01", "32"],
    }

    assert client.post("/bus/stops", headers=BASE_HEADERS, json=stop_payload).status_code == 403

    create_resp = client.post("/bus/stops", headers=OPERATOR_HEADERS, json=stop_payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "Trạm Thử Nghiệm Mới 123"
    assert created["has_shelter"] is True
    stop_id = created["id"]

    update_resp = client.put(f"/bus/stops/{stop_id}", headers=OPERATOR_HEADERS, json={"name": "Trạm Cầu Giấy Cập Nhật"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Trạm Cầu Giấy Cập Nhật"

    delete_resp = client.delete(f"/bus/stops/{stop_id}", headers=OPERATOR_HEADERS)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["success"] is True

    assert client.get(f"/bus/stops/{stop_id}", headers=BASE_HEADERS).status_code == 404


