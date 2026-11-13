# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.repositories import bus_search as repo


def main():
    default_path = Path(__file__).resolve().parents[1] / "data" / "export.geojson"
    target_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    if not target_path.exists():
        fallback = Path("D:/Download/export.geojson")
        if fallback.exists():
            target_path = fallback
        else:
            print(f"Error: File not found at {target_path}")
            sys.exit(1)

    print(f"Reading OpenStreetMap GeoJSON from: {target_path}")
    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Processing features ({len(data.get('features', []))} elements)...")
    routes_count, stops_count = repo.import_osm_geojson(data, replace_existing=True)

    print(f"Import complete!")
    print(f" - Bus routes imported: {routes_count}")
    print(f" - Bus stops imported:  {stops_count}")


if __name__ == "__main__":
    main()
