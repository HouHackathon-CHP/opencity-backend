# SPDX-License-Identifier: Apache-2.0
"""Gate direct dependencies by reviewed version and OSI-approved license metadata."""

import re
from importlib.metadata import distribution
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEWED = {
    "fastapi": ("0.158.1", "MIT"),
    "uvicorn": ("0.54.0", "BSD-3-Clause"),
    "httpx": ("0.28.1", "BSD-3-Clause"),
    "python-multipart": ("0.0.32", "Apache-2.0"),
}
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s#]+)$")


def main():
    found = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        match = PIN.fullmatch(line.strip())
        if not match:
            raise SystemExit(f"Unpinned requirement: {line}")
        found[match[1]] = match[2]
    if found.keys() != REVIEWED.keys():
        raise SystemExit("Dependency list changed; update the license review")
    for name, (version, license_id) in REVIEWED.items():
        package = distribution(name)
        observed = package.metadata.get("License-Expression") or package.metadata.get("License")
        if package.version != version or found[name] != version or observed != license_id:
            raise SystemExit(f"Review {name}: expected {version} / {license_id}; got {package.version} / {observed}")
    print("PASS: four direct Python dependencies match reviewed OSI-approved licenses")


if __name__ == "__main__":
    main()
