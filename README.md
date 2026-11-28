<div align="center">

# OpenCity Backend — Layer 2 Domain API

**Tầng API Nghiệp vụ Đô thị Thông minh chạy phía sau DX-OS Core Gateway**

<p>
  <a href="#gioi-thieu">Giới thiệu</a> &bull;
  <a href="#tinh-nang">Phân hệ Nghiệp vụ</a> &bull;
  <a href="#cau-truc">Cấu trúc &amp; Tech Stack</a> &bull;
  <a href="#cai-dat">Cài đặt</a> &bull;
  <a href="#routes">Danh sách API</a> &bull;
  <a href="#thanh-vien">Đội ngũ</a>
</p>

<p>
  <img src="https://img.shields.io/badge/License-Apache_2.0-0f172a?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.158-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Storage-SQLite_%2B_GeoJSON-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Telemetry-WAQI_%2B_OSM-2ea44f?style=flat-square" alt="WAQI OSM">
</p>

</div>

---

## Giới thiệu <a id="gioi-thieu"></a>

**OpenCity Backend** là tầng API nghiệp vụ (Layer 2) phục vụ [Cổng Web OpenCity](https://github.com/HouHackathon-CHP/opencity-frontend) và [Ứng dụng Android Công dân](https://github.com/HouHackathon-CHP/opencity-mobile). Service được triển khai hoàn toàn phía sau API Gateway của [DX-OS Core](https://github.com/HouHackathon-CHP/dxos-core), không mở cổng trực tiếp ra ngoài và mọi yêu cầu đều được xác thực qua gateway headers (`X-DXOS-*`, `X-Internal-Secret`).

Hệ thống kết hợp lưu trữ giao dịch lõi (`dxos-core` Data, SeaweedFS S3, Workflow Engine, AI Triage) với cơ sở dữ liệu SQLite cục bộ và các bộ dữ liệu mở OpenStreetMap / WAQI thời gian thực.

---

## Các Phân hệ Nghiệp vụ Thực tế <a id="tinh-nang"></a>

### 1. Phản ánh Hiện trường, Điều phối SLA & Thông báo
* Tiếp nhận phản ánh kèm ảnh (kiểm tra dung lượng tối đa 10 MB và định dạng JPEG/PNG/WebP) và tọa độ; đồng bộ tạo bản ghi trên `dxos-core` Data, upload ảnh lên SeaweedFS và khởi tạo workflow `report-handling`.
* **Điều phối theo đơn vị (`unit_id`)**: Hỗ trợ `reports_dispatcher` phân công cho 4 đơn vị (`infrastructure`, `environment`, `transport`, `intake`) kèm hạn xử lý `due_at`; hỗ trợ tiếp nhận, cập nhật tiến độ, yêu cầu chuyển đơn vị, từ chối chuyển và hoàn tất.
* **SLA Dashboard & Gợi ý Triage**: Tổng hợp số lượng hồ sơ mới, đang xử lý, chưa phân công, sắp đến hạn 24 giờ và quá hạn; gọi dịch vụ AI nội bộ (`opencity-ai`) gợi ý đơn vị và tìm hồ sơ tương tự.
* **Hộp thư Thông báo (`/notifications`)**: Lưu trạng thái đã đọc theo từng tài khoản và tự động tạo nhắc việc không trùng lặp cho hồ sơ sắp đến hạn / quá hạn.

### 2. Quan trắc Chất lượng Không khí Thời gian thực (`/air-quality`)
* Tự động quét và đồng bộ các trạm quan trắc thực tế tại Hà Nội từ **WAQI Map Bounds API (`api.waqi.info`)** ngay lần truy cập đầu tiên và tự động làm mới mỗi 15 phút (hoặc đồng bộ tức thì qua `/air-quality/sync`).
* Trả về dữ liệu thật (VN-AQI, $\text{PM}_{2.5}$, $\text{PM}_{10}$, nhiệt độ, độ ẩm, $CO, NO_2, O_3, SO_2$) không bịa đặt số liệu khi trạm thiếu dữ liệu; hỗ trợ CRUD trạm, đổi trạng thái (`active`, `maintenance`, `hidden`) và phát cảnh báo ô nhiễm diện rộng.

### 3. Bản đồ 126 Xã/Phường, Xe buýt, Bãi đỗ xe & Tiện ích Đô thị
* **126 Xã/Phường Hà Nội (`/wards`)**: Nạp ranh giới GeoJSON và siêu dữ liệu (diện tích, dân số ước tính, địa chỉ trụ sở, đường dây nóng) từ `data/wards_boundaries.geojson`, hỗ trợ quản trị viên thêm/sửa/xóa.
* **Xe buýt & Tìm đường đi bộ (`/bus/*`)**: Đóng gói sẵn ảnh chụp dữ liệu OpenStreetMap (`data/bus_osm.geojson` — 184 tuyến và 5,052 điểm dừng), hỗ trợ tìm tuyến trực tiếp / chuyển tuyến (`/bus/find`), tính lộ trình đi bộ (`/bus/walk-route`) và ước tính lượng $\text{CO}_2$ tiết kiệm.
* **Bãi đỗ xe thông minh (`/parking`)**: Dữ liệu bãi đỗ xe kèm đa giác phạm vi thực tế (`data/parking_footprints.geojson`, `data/parking_osm.geojson`).
* **Du lịch, Di tích & Cơ sở Công cộng (`/tourism`, `/facilities`)**: Địa điểm du lịch/di tích (`data/tourism_osm.geojson`), cơ sở y tế, nhà thuốc và trường học (`data/facilities_osm.geojson`).

### 4. Hành chính Công, Cộng đồng & Quản trị
* **Đường dây nóng (`/hotlines`)**, **Tin tức & Cảnh báo (`/bulletins`)**, **Khảo sát (`/surveys`)**, **Đặt lịch tiếp công dân (`/appointments`)**.
* **Phản ánh TTHC (`/administrative-feedback`)** & **Kiến nghị Doanh nghiệp (`/business-feedback`)**: Quy trình trao đổi hai chiều có lưu lịch sử chuyển trạng thái đầy đủ.
* **Truyền thông (`/communications`)**, **Nhóm cộng đồng (`/community`)**, **Phản ánh xã hội (`/social-feedback`)**, **Xã/Phường số (`/digital-ward`)** và **Tổng quan Admin (`/admin/overview`)**.

---

## Cấu trúc Dự án & Công nghệ <a id="cau-truc"></a>

```text
opencity-backend/
├── app/
│   ├── api/routes/      # 20 router HTTP (reports, air_quality, ward, bus_search, parking, tourism, facilities...)
│   ├── schemas/         # Pydantic v2 models kiểm tra đầu vào / đầu ra
│   ├── services/        # Business logic, SLA rules, WAQI sync, triage integration
│   ├── repositories/    # Persistence helpers (SQLite + GeoJSON auto-seed)
│   └── core/            # Cấu hình môi trường, xác thực header từ Gateway, client gọi dxos-core
├── data/                # Bộ dữ liệu mở GeoJSON (bus_osm, wards_boundaries, parking_osm, facilities_osm, tourism_osm)
├── scripts/             # provision_roles.py, smoke_app.py, smoke_new_features.py, seed_dashboard_demo.py
├── tests/               # Unit & API tests bằng Pytest
├── compose.stack.yaml   # Cấu hình gắn opencity-backend vào DX-OS Core Compose
└── Dockerfile
```

| Thành phần | Công nghệ | Mục đích |
| --- | --- | --- |
| **API Framework** | FastAPI `0.158` + Uvicorn + Pydantic | Thiết kế API phân lớp rõ ràng, validation chặt chẽ. |
| **HTTP Client** | `httpx` + `urllib` | Giao tiếp nội bộ với `dxos-core`, `opencity-ai`, WAQI API và OSRM. |
| **Local Persistence** | SQLite 3 + GeoJSON | Lưu trữ dữ liệu nghiệp vụ đô thị phân tách theo `tenant`. |
| **Testing & Audit** | Pytest + `check_direct_licenses.py` | Kiểm thử API, RBAC và kiểm toán giấy phép thư viện Python. |

---

## Hướng dẫn Cài đặt & Chạy Local <a id="cai-dat"></a>

Đặt `dxos-core`, `opencity-backend`, `opencity-ai` và `opencity-frontend` ngang hàng nhau. Nếu dùng `opencity-ai`, chạy `git lfs pull` trong `opencity-ai` trước khi build.

```powershell
# 1. Tạo file .env cho dxos-core (điền thêm WAQI_API_TOKEN nếu muốn đồng bộ AQI thực tế)
Copy-Item ..\dxos-core\.env.example ..\dxos-core\.env

# 2. Khởi chạy toàn bộ Docker Compose stack
docker compose --env-file ..\dxos-core\.env -f ..\dxos-core\compose.yaml -f compose.stack.yaml up --build -d

# 3. Khởi tạo tài khoản mẫu, kiểm thử lõi và dữ liệu OpenCity
python ..\dxos-core\scripts\smoke.py
python scripts\smoke_app.py
python scripts\seed_dashboard_demo.py   # (Tùy chọn) Nạp 5 hồ sơ SLA mẫu trên bản đồ Hà Nội
```

* **Kiểm thử Unit & API cục bộ**:
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python scripts\check_direct_licenses.py
.venv\Scripts\python -m pytest -q
```

---

## Danh sách Route Chính <a id="routes"></a>

Mọi route dưới đây được Gateway gắn tiền tố `/api/opencity`. Khi hệ thống đang chạy, xem tài liệu tương tác **Swagger UI** tại `http://localhost:8000/api/opencity/docs` (hoặc **ReDoc** tại `http://localhost:8000/api/opencity/redoc`).

| Nhóm | Route tiêu biểu | Mô tả |
| --- | --- | --- |
| **Hệ thống & Quản trị** | `GET /me/capabilities`, `GET /admin/overview` | Quyền hạn người gọi và tổng quan vận hành toàn tenant |
| **Phản ánh & SLA** | `GET/POST /reports`, `/reports/dashboard`, `/reports/{id}/dispatch`, `/accept`, `/progress`, `/actions/resolve` | Tiếp nhận, gợi ý triage, phân công đơn vị và xử lý hồ sơ |
| **Thông báo** | `GET /notifications`, `POST /notifications/{id}/read` | Hộp thư thông báo và nhắc hạn SLA |
| **Không khí (WAQI)** | `GET /air-quality/summary`, `/stations`, `POST /air-quality/sync`, `/broadcast-alert` | Theo dõi VN-AQI, đồng bộ WAQI và quản trị trạm |
| **126 Xã/Phường** | `GET/POST/PUT/DELETE /wards`, `/wards/{id}` | Bản đồ ranh giới GeoJSON và thông tin đơn vị hành chính |
| **Xe buýt & Đỗ xe** | `GET /bus/routes`, `/bus/stops`, `/bus/find`, `/bus/walk-route`, `/parking`, `/parking/footprints` | Tra cứu tuyến buýt, tìm đường và bãi đỗ xe thông minh |
| **Du lịch & Tiện ích** | `GET/POST/PUT/DELETE /tourism/destinations`, `/facilities` | Điểm du lịch, di tích, y tế, nhà thuốc và trường học |
| **Hành chính & Cộng đồng** | `/bulletins`, `/surveys`, `/appointments`, `/hotlines`, `/administrative-feedback`, `/business-feedback`, `/communications`, `/community/groups`, `/social-feedback`, `/digital-ward` | Tin tức, khảo sát, đặt lịch, đường dây nóng và tương tác công dân/doanh nghiệp |

---

## Thành viên Dự án & Đóng góp <a id="thanh-vien"></a>

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/hieutnago">
        <img src="https://github.com/hieutnago.png" width="96px" alt="Trương Ngọc Hiểu"/><br>
        <sub><b>Trương Ngọc Hiểu</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/HouHackathon-CHP">
        <img src="https://avatars.githubusercontent.com/u/168514215?v=4" width="96px" alt="Trần Trọng Chiến"/><br>
        <sub><b>Trần Trọng Chiến</b></sub>
      </a>
    </td>
    <td align="center">
      <a href="https://github.com/HouHackathon-CHP">
        <img src="https://avatars.githubusercontent.com/u/100331812?v=4" width="96px" alt="Nguyễn Hà Phương"/><br>
        <sub><b>Nguyễn Hà Phương</b></sub>
      </a>
    </td>
  </tr>
</table>

1. Fork repository và tạo nhánh từ `dev`: `git checkout -b feature/ten-tinh-nang`.
2. Đảm bảo thêm `# SPDX-License-Identifier: Apache-2.0` vào tệp mã nguồn mới và chạy `python -m pytest -q` pass trước khi mở Pull Request.

Phát hành theo giấy phép **Apache License 2.0** — xem [LICENSE](LICENSE), [docs/license-audit.md](docs/license-audit.md) và [CHANGELOG.md](CHANGELOG.md).
