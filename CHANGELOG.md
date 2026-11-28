# Nhật ký thay đổi

Tất cả các thay đổi đáng chú ý của dự án này sẽ được ghi lại trong file này.

Định dạng dựa trên [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
và dự án này tuân thủ [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Chưa phát hành

### Đã sửa

- Cập nhật `Dockerfile` copy `data/bus_osm.geojson` vào `./seed/bus_osm.geojson` thay cho `data/export.geojson`.
- Bật Swagger UI (`/docs`), ReDoc (`/redoc`) và OpenAPI schema (`/openapi.json`) trong `app/main.py`.

## [1.0.0] - 2026-11-27

### Đã thêm

- Sync all WAQI map stations without fabricated readings - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [40c749d](https://github.com/HouHackathon-CHP/opencity-backend/commit/40c749d1e5e23b42028b0f5beb57f1b16f8c1e48)
- Sync all WAQI map stations without fabricated readings - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [45a6791](https://github.com/HouHackathon-CHP/opencity-backend/commit/45a6791a59803ae90ec040f393de024c3a8ad8b6)
- Keep staff accounts outside citizen registration group - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [97382b4](https://github.com/HouHackathon-CHP/opencity-backend/commit/97382b495eeca768de754893d7e3fb0b77e1522e)
- Keep staff accounts outside citizen registration group - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [28020d8](https://github.com/HouHackathon-CHP/opencity-backend/commit/28020d810a179afd6f5f8b6a05abcb013f3b4827)
- Route report triage to separate OpenCity AI service - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [8f558aa](https://github.com/HouHackathon-CHP/opencity-backend/commit/8f558aa160d94dd6ac0f23bc7c7746957080ffeb)
- Route report triage to separate OpenCity AI service - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [7110080](https://github.com/HouHackathon-CHP/opencity-backend/commit/7110080a38d6acb32999b3319c19e6499955aa57)
- feat: thêm API cập nhật thông tin trụ sở và dân số xã/phường cho admin - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [f3f85b6](https://github.com/HouHackathon-CHP/opencity-backend/commit/f3f85b6e0e5e602c1fa45325d7c7e7f115ef357f)
- feat(ward): bổ sung API ranh giới phường tại Hà Nội và dịch vụ dữ liệu GeoJSON - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [0d33d4a](https://github.com/HouHackathon-CHP/opencity-backend/commit/0d33d4ae4cfe2426bdc313c561dfdd9bb5f7f6e3)
- feat(parking): hoàn thiện dữ liệu bao phủ dạng đa giác cho tất cả các điểm đỗ xe tại Hà Nội - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [0e65a43](https://github.com/HouHackathon-CHP/opencity-backend/commit/0e65a43a11d8e1c92b075d2ad44670d3b8b7ae13)
- feat(parking): thêm điểm cuối API cho phạm vi chiếm chỗ (footprints) và tập dữ liệu GeoJSON dạng đa giác - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [d4876c9](https://github.com/HouHackathon-CHP/opencity-backend/commit/d4876c95048d1a7bc40420a9fc331c50bf8e3dc7)
- feat(parking): thêm API tìm kiếm bãi đỗ xe tại Hà Nội từ dữ liệu OSM với 994 địa điểm - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [27082d7](https://github.com/HouHackathon-CHP/opencity-backend/commit/27082d7c50546f4559be6d88d30da0ad3b4996ef)
- feat: thêm bản đồ cơ sở y tế & trường học 3D và thanh phân trang đánh số - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [8d8883f](https://github.com/HouHackathon-CHP/opencity-backend/commit/8d8883f44e03379495e18bf322ff38ff0d1a043c)
- feat(tourism): hoàn thiện bản đồ di tích 3D, chuẩn hóa UI xe buýt và dialog xóa - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [a2e0e6e](https://github.com/HouHackathon-CHP/opencity-backend/commit/a2e0e6e8f87dbc26e0a8ef3913612e85494d4e72)
- added bus data - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [807025c](https://github.com/HouHackathon-CHP/opencity-backend/commit/807025c9fa64e11d0683c8538a1d2bc23891a172)
- Configure public OpenCity reads and hide private stations - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [baf60b7](https://github.com/HouHackathon-CHP/opencity-backend/commit/baf60b757f80d26a3b6854b9879481679af3bc9d)
- Restrict bus sync and verify external TLS - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [2262e2f](https://github.com/HouHackathon-CHP/opencity-backend/commit/2262e2ff2ec61e7b00ad7d851afd4e6b85881d4f)
- Add digital ward service directory - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [0571fb1](https://github.com/HouHackathon-CHP/opencity-backend/commit/0571fb1c50c119e643a0bed31e4016efa2487c5c)
- Add social consultation topics and opinions - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [97c654f](https://github.com/HouHackathon-CHP/opencity-backend/commit/97c654fdf8395cf4709de7c27f159ba4d925c92a)
- Add tenant-scoped community groups - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [4736df3](https://github.com/HouHackathon-CHP/opencity-backend/commit/4736df3d204afb274d55b4400e6762253ed75562)
- Add tenant-scoped communications channel - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [0e1b163](https://github.com/HouHackathon-CHP/opencity-backend/commit/0e1b163dbb8d9a9f0baec0b0cc203727173679f5)
- feat: add tenant hotline directory API - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [7aea009](https://github.com/HouHackathon-CHP/opencity-backend/commit/7aea009553e9ef102d6ca2d83665e2f3b896f395)
- feat: add admin operations overview API - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [c4c4606](https://github.com/HouHackathon-CHP/opencity-backend/commit/c4c460647d3e1a713089780f71d3cbab60da0343)
- feat: add business petition workflow - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [0eb70dc](https://github.com/HouHackathon-CHP/opencity-backend/commit/0eb70dc577cfeeb5d7e82686e356c16a331b3bb9)
- feat: add administrative procedure feedback workflow - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [0a7ee8a](https://github.com/HouHackathon-CHP/opencity-backend/commit/0a7ee8a15a033644524101a28bfabc95d2de43e9)
- Add human-reviewed report triage suggestions - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [5c2ea48](https://github.com/HouHackathon-CHP/opencity-backend/commit/5c2ea48e96055eeb2ad8a8b00b6b1d54de3e92e6)
- Add citizen reception appointment module - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [2a0b419](https://github.com/HouHackathon-CHP/opencity-backend/commit/2a0b419cb93edcced12d8489cb299439cdb70741)
- Add scoped report SLA dashboard API and demo seed - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [a60901d](https://github.com/HouHackathon-CHP/opencity-backend/commit/a60901dd4b9e4200cb33ed0af76280cd75b2e1ed)
- Add scoped report notifications and deadline reminders - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [f4680c2](https://github.com/HouHackathon-CHP/opencity-backend/commit/f4680c24de4dc720ebb994c835615dc3aa39fb48)
- Implement report dispatch and unit workflow - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [373e711](https://github.com/HouHackathon-CHP/opencity-backend/commit/373e711bf99ccc4283b3f0ac797b4ee63bacce92)
- Enforce feature scoped OpenCity operator roles - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [227a957](https://github.com/HouHackathon-CHP/opencity-backend/commit/227a9575987e206735cdc58f71c1fe40d758917b)
- Add tenant-scoped citizen surveys - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [d7a3f5d](https://github.com/HouHackathon-CHP/opencity-backend/commit/d7a3f5dde5b25a6aa0755c34764873d712e69844)
- Add tenant-scoped news and alerts API - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [2334dae](https://github.com/HouHackathon-CHP/opencity-backend/commit/2334daecbca7c43d165cbe15bed14400eda80865)
- Add OpenCity domain API and integration stack - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [9c1de29](https://github.com/HouHackathon-CHP/opencity-backend/commit/9c1de2954d28b14359b711441dfaf14c0acbb65d)

### Đã sửa

- fix(bus): seed bundled OSM routes in backend container - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [18ad119](https://github.com/HouHackathon-CHP/opencity-backend/commit/18ad1199f6da61b7210873562a6ff69673c1af49)
- fix(bus): seed bundled OSM routes in backend container - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [aee876e](https://github.com/HouHackathon-CHP/opencity-backend/commit/aee876ed505a642c999ac06371b5dbc9e272a6e2)
- fixed test - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [70bd8e8](https://github.com/HouHackathon-CHP/opencity-backend/commit/70bd8e87d3ba6b19887256dfe64146a497167b3d)

### Kiểm thử

- test quy trình CI - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [ba80605](https://github.com/HouHackathon-CHP/opencity-backend/commit/ba806057cd8be1d8406edf595925726fd9468056)

### Tài liệu

- Document WAQI token and station setup - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [a7260fb](https://github.com/HouHackathon-CHP/opencity-backend/commit/a7260fb0ce5fa5ea905ee158e6df8fd98fde9ccf)
- docs: update OpenCity setup and feature guides - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [18a65f1](https://github.com/HouHackathon-CHP/opencity-backend/commit/18a65f1accca3f850ef5651fed0882d93dc8797c)

### Các thay đổi khác

- Merge pull request #23 from HouHackathon-CHP/dev - Nguyễn Hà Phương in [8b1010c](https://github.com/HouHackathon-CHP/opencity-backend/commit/8b1010ce46e94dcc0056fc63e16521812e1b24dc)
- Merge remote-tracking branch 'origin/main' into HEAD - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [527235c](https://github.com/HouHackathon-CHP/opencity-backend/commit/527235c8f0cf64b723aa34cfc09a12e978036b3c)
- Merge pull request #19 from HouHackathon-CHP/feature/separate-ai-service - Nguyễn Hà Phương in [8e8043b](https://github.com/HouHackathon-CHP/opencity-backend/commit/8e8043bba035a3cdef3c960c386f110ec2de5ebf)
- Merge pull request #20 from HouHackathon-CHP/feature/citizen-registration - Nguyễn Hà Phương in [186c91c](https://github.com/HouHackathon-CHP/opencity-backend/commit/186c91ce9341f97a011fa5de0f1a52667d8e47d8)
- Merge pull request #21 from HouHackathon-CHP/fix/bus-seed - Nguyễn Hà Phương in [b62312d](https://github.com/HouHackathon-CHP/opencity-backend/commit/b62312d87b90b682fdc8911c883df5f3930286c7)
- Merge pull request #22 from HouHackathon-CHP/feature/waqi-all-stations - Nguyễn Hà Phương in [594d448](https://github.com/HouHackathon-CHP/opencity-backend/commit/594d448d4d366e0841987dc0a1e101185a34bfa0)
- Merge pull request #18 from HouHackathon-CHP/feature/osm-ward-map - Nguyễn Hà Phương in [6a2de1e](https://github.com/HouHackathon-CHP/opencity-backend/commit/6a2de1e897f8e35eea902a3011caa0d1baa49ed2)
- Merge remote-tracking branch 'origin/dev' into HEAD - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [0bef07a](https://github.com/HouHackathon-CHP/opencity-backend/commit/0bef07ae06ed7e534a0af315e16cb40f167e9337)
- Merge pull request #14 from HouHackathon-CHP/fea-weather-and-bus-search - Trần Trọng Chiến in [e090e31](https://github.com/HouHackathon-CHP/opencity-backend/commit/e090e31b2b83eb0d805f160295ad52debe3db9bf)
- Merge pull request #15 from HouHackathon-CHP/feature/osm-tourism-and-heritage - Trần Trọng Chiến in [326bdb2](https://github.com/HouHackathon-CHP/opencity-backend/commit/326bdb222527abc20b694f1bf1ce99360b20d5c7)
- chore: track tourism osm geojson in gitignore - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [2a96d93](https://github.com/HouHackathon-CHP/opencity-backend/commit/2a96d939ad26653543e3dc5bce51794b61895bcf)
- Tính năng (du lịch): bổ sung bản đồ du lịch và di sản Hà Nội 3D tương tác - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [cb1a66a](https://github.com/HouHackathon-CHP/opencity-backend/commit/cb1a66a6f66f059a3533678717ed6892a5bd4c92)
- thêm lộ trình di chuyển từ vị trí đến trạm - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [180f47b](https://github.com/HouHackathon-CHP/opencity-backend/commit/180f47bbdc270de98b92348f80e3cd0ea25c1965)
- Merge pull request #12 from HouHackathon-CHP/dev - Trần Trọng Chiến in [4aff8c8](https://github.com/HouHackathon-CHP/opencity-backend/commit/4aff8c88fea888879e6a33fc71299c4965977970)
- Merge pull request #13 from HouHackathon-CHP/fea-weather-and-bus-search - Trần Trọng Chiến in [31c4254](https://github.com/HouHackathon-CHP/opencity-backend/commit/31c4254f7a8e66fb3835baebb30609733d90fb6f)
- Provision separate demo credentials for each OpenCity role - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [19e74a3](https://github.com/HouHackathon-CHP/opencity-backend/commit/19e74a30a5913450bf22cf948e2fd822eee1cabb)
- Merge pull request #11 from HouHackathon-CHP/dev - Trần Trọng Chiến in [4a803e4](https://github.com/HouHackathon-CHP/opencity-backend/commit/4a803e47feb36914151a600f3e888596e246ddde)
- Limit air quality provider status to operators - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [0d9dfa4](https://github.com/HouHackathon-CHP/opencity-backend/commit/0d9dfa450fc061ae427ff84ed0b13ac13ae1f1da)
- Merge pull request #10 from HouHackathon-CHP/fea-weather-and-bus-search - Trần Trọng Chiến in [9f4da97](https://github.com/HouHackathon-CHP/opencity-backend/commit/9f4da971294eaa54ee181abbaea0ac823b19e5d3)
- update bus route & data - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [eb86a3a](https://github.com/HouHackathon-CHP/opencity-backend/commit/eb86a3ae0096dc088a9243ee7be9ffe9e0c3aa18)
- update backend chất lượng không khí - ourstorycomics ([@ourstorycomic](https://github.com/ourstorycomic)) in [b1b2562](https://github.com/HouHackathon-CHP/opencity-backend/commit/b1b25627ca5b80d9a3ec033d62bf5515329f7cb3)
- Merge pull request #9 from HouHackathon-CHP/dev - Trần Trọng Chiến in [913cda6](https://github.com/HouHackathon-CHP/opencity-backend/commit/913cda651af8ce4d46ecf29f1acc15b9f6287b2e)
- Merge pull request #8 from HouHackathon-CHP/dev - Trần Trọng Chiến in [eda26e3](https://github.com/HouHackathon-CHP/opencity-backend/commit/eda26e3f72e0b9af74e41b1e5c4eb729f3cbdb7c)
- Merge pull request #7 from HouHackathon-CHP/dev - Trần Trọng Chiến in [c7feefa](https://github.com/HouHackathon-CHP/opencity-backend/commit/c7feefa3278c739dc4e6a0f1cbdb2a5af3ae96ac)
- Merge pull request #6 from HouHackathon-CHP/dev - Trần Trọng Chiến in [6a67c56](https://github.com/HouHackathon-CHP/opencity-backend/commit/6a67c56a97242a8762707e92502d82ad1631353c)
- Merge pull request #5 from HouHackathon-CHP/dev - Trần Trọng Chiến in [edd5c48](https://github.com/HouHackathon-CHP/opencity-backend/commit/edd5c48da83d5801d78083408e60f18a8752fc56)
- Merge pull request #4 from HouHackathon-CHP/dev - Trần Trọng Chiến in [e8dcc72](https://github.com/HouHackathon-CHP/opencity-backend/commit/e8dcc7297e36bc0f6b63da161cf34da9fa3e07cb)
- Merge pull request #3 from HouHackathon-CHP/dev - Trần Trọng Chiến in [98b44a6](https://github.com/HouHackathon-CHP/opencity-backend/commit/98b44a671c7cdad21dc377ed201ccf4b5eaa9aa2)
- Merge pull request #2 from HouHackathon-CHP/dev - Trần Trọng Chiến in [aec0b69](https://github.com/HouHackathon-CHP/opencity-backend/commit/aec0b69c0388d08560a15a481e3e6f0049ccad4f)
- Merge pull request #1 from HouHackathon-CHP/dev - Trần Trọng Chiến in [74be8f0](https://github.com/HouHackathon-CHP/opencity-backend/commit/74be8f0d7b37ec767d9759b1ad5f4910f232732b)
- Handle uncertain triage and concurrent review - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [c1bc36a](https://github.com/HouHackathon-CHP/opencity-backend/commit/c1bc36a5448d9bd4b1d13705ac9104e78aec31a0)
- Standardize OpenCity backend layered layout - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [be361a7](https://github.com/HouHackathon-CHP/opencity-backend/commit/be361a71b3b8637e4bb79e9aa471f6d1edfe4513)
- Organize OpenCity backend by feature - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [b22e97f](https://github.com/HouHackathon-CHP/opencity-backend/commit/b22e97f04d834ee4b2c2e8f650e08f04855d7655)
- Scope report access to operator units - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [0745aed](https://github.com/HouHackathon-CHP/opencity-backend/commit/0745aed8c82ecc97746e8ecd701bd80236b8d5ea)
- Rename API repository references to OpenCity Backend - Chien Tran ([@blueMonkey23](https://github.com/blueMonkey23)) in [ac08aff](https://github.com/HouHackathon-CHP/opencity-backend/commit/ac08affc80bea2a08ff88860785c8c12f6bc0a1a)

---
*Changelog được tạo tự động bởi [git-cliff](https://git-cliff.org). Xem hướng dẫn tại [docs/GIT_CLIFF_GUIDE.md](docs/GIT_CLIFF_GUIDE.md)*
