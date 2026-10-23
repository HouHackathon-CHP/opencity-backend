# License review — 2026-10-23

Original source in this repository is Apache-2.0. The full license text is included in `LICENSE`; source files carry SPDX headers.

Reviewed direct packages: FastAPI 0.158.1 (MIT), Uvicorn 0.54.0 (BSD-3-Clause), HTTPX 0.28.1 (BSD-3-Clause), python-multipart 0.0.32 (Apache-2.0). All four are OSI-approved license identifiers, and `scripts/check_direct_licenses.py` gates new versions or packages pending review.

This direct-package check does **not** prove every transitive Python dependency or base image component is OSI-approved. The sibling core audit has a `typing_extensions` metadata exception (PSF-2.0) and unresolved image-level provenance. Those remain open for the final submission review. No official iHanoi assets, source code, data or APIs are bundled here.
