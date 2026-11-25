# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.repositories import tourism as repo


def main():
    default_path = Path(__file__).resolve().parents[1] / "data" / "tourism_osm.geojson"
    target_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    if not target_path.exists():
        print(f"Error: Không tìm thấy file dữ liệu GeoJSON tại: {target_path}")
        print("Vui lòng tải file GeoJSON từ Overpass Turbo và lưu vào thư mục 'data/tourism_osm.geojson'")
        sys.exit(1)

    print(f"Reading OpenStreetMap GeoJSON from: {target_path}")
    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Processing features ({len(data.get('features', []))} elements)...")
    imported_count = repo.import_osm_geojson(data, replace_existing=True)

    print(f"Import complete!")
    print(f" - Tourism & Heritage destinations imported: {imported_count}")


if __name__ == "__main__":
    main()
