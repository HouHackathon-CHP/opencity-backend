# SPDX-License-Identifier: Apache-2.0
"""Shared OpenCity configuration."""

import os

INTERNAL_SECRET = os.getenv("INTERNAL_GATEWAY_SECRET", "")
DATA_URL = os.getenv("DATA_URL", "http://data:8000")
WORKFLOW_URL = os.getenv("WORKFLOW_URL", "http://workflow:8000")
MAX_PHOTO_BYTES = 10 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
REPORT_CATEGORIES = {"Hạ tầng", "Môi trường", "Giao thông", "Chiếu sáng", "Cây xanh", "Khác"}
REPORT_UNITS = {
    "Hạ tầng": "infrastructure", "Chiếu sáng": "infrastructure",
    "Môi trường": "environment", "Cây xanh": "environment",
    "Giao thông": "transport", "Khác": "intake",
}
MANAGEMENT_ROLES = {
    "reports": "reports_operator",
    "bulletins": "bulletins_operator",
    "surveys": "surveys_operator",
}
NEWS_DB_PATH = os.getenv("NEWS_DB_PATH", "data/bulletins.sqlite3")
SURVEY_DB_PATH = os.getenv("SURVEY_DB_PATH", "data/surveys.sqlite3")
REPORT_DB_PATH = os.getenv("REPORT_DB_PATH", "data/report-routing.sqlite3")
VALID_UNITS = frozenset(REPORT_UNITS.values())
