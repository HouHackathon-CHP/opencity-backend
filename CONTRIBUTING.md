# Hướng dẫn Đóng góp Dự án (OpenCity Backend)

Xin chân thành cảm ơn sự quan tâm và đóng góp của bạn cho **OpenCity Backend** (`HouHackathon-CHP`).
Chúng tôi luôn chào đón mọi hình thức đóng góp, bao gồm báo cáo lỗi, đề xuất cải tiến và gửi Pull Request.

## Thông báo Lỗi & Đề xuất Cải tiến

- Kiểm tra tab **Issues** để xác minh vấn đề chưa được báo cáo trước đó.
- Sử dụng tiêu đề cụ thể, rõ ràng theo đúng phân hệ (`reports`, `air-quality`, `wards`, `bus`, `parking`, `tourism`, `facilities`, `auth`, ...).
- Cung cấp đầy đủ thông tin: môi trường (Docker Compose / Python), các bước tái tạo lỗi, log lỗi và kết quả mong muốn.

## Quy trình Pull Request

1. Fork repository này về tài khoản cá nhân.
2. Tạo nhánh làm việc mới từ `dev` (hoặc `main`): `git checkout -b fix/ten-loi` hoặc `feature/ten-tinh-nang`.
3. Chia nhỏ commit theo từng thay đổi có ý nghĩa (khuyến khích chuẩn Conventional Commits để `git-cliff` phân loại tự động vào `CHANGELOG.md`).
4. Đảm bảo tệp mã nguồn Python mới có dòng `# SPDX-License-Identifier: Apache-2.0` ở đầu tệp.
5. Chạy kiểm tra trước khi mở Pull Request:
   - `python scripts/check_direct_licenses.py`
   - `python -m pytest -q`
6. Push lên fork cá nhân và tạo Pull Request kèm mô tả rõ các endpoint hoặc schema bị ảnh hưởng.

## Tiêu chuẩn Mã nguồn & Giấy phép

- Tuân thủ kiến trúc phân lớp (`app/api/routes` -> `app/schemas` -> `app/services` -> `app/repositories`).
- Không commit tệp `.env`, token API (`WAQI_API_TOKEN`) hoặc các tệp cơ sở dữ liệu `.sqlite3`.
- Thư viện phụ thuộc mới phải được kiểm toán tương thích giấy phép OSI.

## Nguyên tắc Cộng đồng

- Tôn trọng mọi thành viên và tuân thủ [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Giữ thái độ trao đổi xây dựng, minh bạch và chuyên nghiệp.

## Liên hệ Hỗ trợ

Khi cần hỗ trợ, bạn có thể tạo Issue mới trên repository hoặc liên hệ nhóm phát triển qua:
- **Email**: trantrongchien05@gmail.com
