import json
import sqlite3
from pathlib import Path

# Mapping table from postal code prefix / name to Hanoi District
POSTAL_DISTRICT_MAP = {
    "111": "Ba Đình",
    "110": "Hoàn Kiếm",
    "112": "Tây Hồ",
    "118": "Long Biên",
    "113": "Cầu Giấy",
    "115": "Đống Đa",
    "116": "Hai Bà Trưng",
    "117": "Hoàng Mai",
    "114": "Thanh Xuân",
    "122": "Sóc Sơn",
    "123": "Đông Anh",
    "124": "Gia Lâm",
    "119": "Bắc Từ Liêm",
    "120": "Nam Từ Liêm",
    "125": "Thanh Trì",
    "129": "Mê Linh",
    "121": "Hà Đông",
    "127": "Sơn Tây",
    "126": "Ba Vì",
    "128": "Phúc Thọ",
    "130": "Đan Phượng",
    "132": "Hoài Đức",
    "133": "Quốc Oai",
    "131": "Thạch Thất",
    "134": "Chương Mỹ",
    "135": "Thanh Oai",
    "136": "Thường Tín",
    "139": "Phú Xuyên",
    "138": "Ứng Hòa",
    "137": "Mỹ Đức",
}

# Special name-based overrides if any
NAME_DISTRICT_OVERRIDES = {
    "Từ Liêm": "Bắc Từ Liêm",
    "Thanh Liệt": "Thanh Trì",
    "Dương Nội": "Hà Đông",
    "Yên Xuân": "Thạch Thất",
}

def get_district(postal_code: str, name: str) -> str:
    if name in NAME_DISTRICT_OVERRIDES:
        return NAME_DISTRICT_OVERRIDES[name]
    prefix = str(postal_code)[:3]
    if prefix in POSTAL_DISTRICT_MAP:
        return POSTAL_DISTRICT_MAP[prefix]
    # Fallback by name
    for k, v in POSTAL_DISTRICT_MAP.items():
        if v.lower() in name.lower():
            return v
    return "Hà Nội"

def compute_centroid(geometry):
    geom_type = geometry.get("type", "")
    coords = geometry.get("coordinates", [])
    all_points = []
    
    def extract_pts(c):
        if not c:
            return
        if isinstance(c[0], (int, float)):
            all_points.append(c)
        else:
            for sub in c:
                extract_pts(sub)
                
    extract_pts(coords)
    if not all_points:
        return [105.8342, 21.0278]
    
    avg_lon = sum(p[0] for p in all_points) / len(all_points)
    avg_lat = sum(p[1] for p in all_points) / len(all_points)
    return [round(avg_lon, 6), round(avg_lat, 6)]

def build():
    data_dir = Path("d:/HouHackathon-CHP/opencity-backend-main/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    geojson_files_dir = Path("d:/HouHackathon-CHP/opencity-backend-main/scripts/wards_meta.json")
    if not geojson_files_dir.exists():
        print("wards_meta.json not found!")
        return

    with open(geojson_files_dir, "r", encoding="utf-8") as f:
        wards_meta = json.load(f)

    print(f"Loaded metadata for {len(wards_meta)} wards.")

    all_features = []
    db_rows = []

    for idx, w in enumerate(wards_meta, start=1):
        fn = w["file"]
        code = str(w["code"])
        name = w["name"]
        full_name = w["fullName"]
        area_km2 = float(w.get("areaKm2") or 5.0)
        postal = str(w.get("postalCode") or "")
        district = get_district(postal, name)

        admin_type = "Phường"
        if "Xã" in full_name:
            admin_type = "Xã"
        elif "Thị trấn" in full_name:
            admin_type = "Thị trấn"

        # Fetch local or raw file
        import urllib.request, ssl
        raw_url = f"https://raw.githubusercontent.com/thanglequoc/vietnamese-provinces-database/master/json/geojson/01_ha_noi/wards/{fn}"
        req = urllib.request.Request(raw_url, headers={"User-Agent": "Mozilla/5.0"})
        ctx = ssl._create_unverified_context()
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
                ward_json = json.loads(r.read().decode("utf-8"))
                feat = ward_json["features"][0]
        except Exception as e:
            print(f"Error fetching {fn}: {e}")
            continue

        geometry = feat.get("geometry", {})
        center = compute_centroid(geometry)
        bbox = feat.get("bbox", [center[0]-0.02, center[1]-0.02, center[0]+0.02, center[1]+0.02])

        phone = f"024.38{idx%90+10}{idx%80+10}{idx%10}"
        address = f"Trụ sở UBND {full_name}, {district}, TP. Hà Nội"
        office_hours = "08:00 - 17:00 (Thứ Hai - Thứ Sáu)"
        population = int(area_km2 * (15000 if admin_type == "Phường" else 3500))

        feat_props = {
            "id": code,
            "code": code,
            "name": name,
            "fullName": full_name,
            "district": district,
            "type": admin_type,
            "areaKm2": area_km2,
            "postalCode": postal,
            "center": center,
            "bbox": bbox,
            "officeAddress": address,
            "phone": phone,
            "officeHours": office_hours,
            "population": population
        }

        # Keep original feature structure but with enriched properties
        unified_feature = {
            "type": "Feature",
            "id": code,
            "properties": feat_props,
            "geometry": geometry,
            "bbox": bbox
        }
        all_features.append(unified_feature)

        db_rows.append((
            code,
            code,
            name,
            full_name,
            district,
            admin_type,
            area_km2,
            postal,
            center[1], # lat
            center[0], # lon
            bbox[0], # min_lon
            bbox[1], # min_lat
            bbox[2], # max_lon
            bbox[3], # max_lat
            address,
            phone,
            office_hours,
            population
        ))

    # 1. Save unified GeoJSON
    out_geojson = {
        "type": "FeatureCollection",
        "total": len(all_features),
        "features": all_features
    }
    geojson_path = data_dir / "wards_boundaries.geojson"
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(out_geojson, f, ensure_ascii=False)
    print(f"Saved {len(all_features)} features to {geojson_path} ({round(geojson_path.stat().st_size / 1024 / 1024, 2)} MB)")

    # 2. Save SQLite database
    sqlite_path = data_dir / "wards.sqlite3"
    if sqlite_path.exists():
        sqlite_path.unlink()

    conn = sqlite3.connect(sqlite_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE wards (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            full_name TEXT NOT NULL,
            district TEXT NOT NULL,
            type TEXT NOT NULL,
            area_km2 REAL,
            postal_code TEXT,
            center_lat REAL NOT NULL,
            center_lon REAL NOT NULL,
            min_lon REAL,
            min_lat REAL,
            max_lon REAL,
            max_lat REAL,
            office_address TEXT,
            phone TEXT,
            office_hours TEXT,
            population INTEGER
        )
    """)
    cur.execute("CREATE INDEX idx_wards_district ON wards(district)")
    cur.execute("CREATE INDEX idx_wards_name ON wards(name)")
    cur.execute("CREATE INDEX idx_wards_type ON wards(type)")

    cur.executemany("""
        INSERT INTO wards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, db_rows)

    conn.commit()
    conn.close()
    print(f"Saved {len(db_rows)} rows to SQLite database at {sqlite_path}")

if __name__ == "__main__":
    build()
