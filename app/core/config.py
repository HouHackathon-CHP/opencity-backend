# SPDX-License-Identifier: Apache-2.0
"""Shared OpenCity configuration."""

import os

INTERNAL_SECRET = os.getenv("INTERNAL_GATEWAY_SECRET", "")
DATA_URL = os.getenv("DATA_URL", "http://data:8000")
WORKFLOW_URL = os.getenv("WORKFLOW_URL", "http://workflow:8000")
INSIGHT_URL = os.getenv("INSIGHT_URL", "http://insight:8000")
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
    "administrative_feedback": "administrative_feedback_operator",
    "business_feedback": "business_feedback_operator",
    "bulletins": "bulletins_operator",
    "surveys": "surveys_operator",
    "appointments": "appointments_operator",
    "air_quality": "air_quality_operator",
    "hotlines": "hotlines_operator",
    "communications": "communications_operator",
    "community_groups": "community_groups_operator",
    "social_feedback": "social_feedback_operator",
    "digital_ward": "digital_ward_operator",
}
NEWS_DB_PATH = os.getenv("NEWS_DB_PATH", "data/bulletins.sqlite3")
SURVEY_DB_PATH = os.getenv("SURVEY_DB_PATH", "data/surveys.sqlite3")
REPORT_DB_PATH = os.getenv("REPORT_DB_PATH", "data/report-routing.sqlite3")
APPOINTMENT_DB_PATH = os.getenv("APPOINTMENT_DB_PATH", "data/appointments.sqlite3")
ADMIN_FEEDBACK_DB_PATH = os.getenv("ADMIN_FEEDBACK_DB_PATH", "data/administrative-feedback.sqlite3")
AIR_QUALITY_DB_PATH = os.getenv("AIR_QUALITY_DB_PATH", "data/air-quality.sqlite3")
WAQI_API_TOKEN = os.getenv("WAQI_API_TOKEN", "")
BUSINESS_FEEDBACK_DB_PATH = os.getenv("BUSINESS_FEEDBACK_DB_PATH", "data/business-feedback.sqlite3")
HOTLINES_DB_PATH = os.getenv("HOTLINES_DB_PATH", "data/hotlines.sqlite3")
COMMUNITY_DB_PATH = os.getenv("COMMUNITY_DB_PATH", "data/community.sqlite3")
SOCIAL_FEEDBACK_DB_PATH = os.getenv("SOCIAL_FEEDBACK_DB_PATH", "data/social-feedback.sqlite3")
DIGITAL_WARD_DB_PATH = os.getenv("DIGITAL_WARD_DB_PATH", "data/digital-ward.sqlite3")
VALID_UNITS = frozenset(REPORT_UNITS.values())
