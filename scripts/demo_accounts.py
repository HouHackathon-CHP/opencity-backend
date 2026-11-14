# SPDX-License-Identifier: Apache-2.0
"""Local-only demo account configuration shared by provisioning and smoke tests."""

from typing import Mapping


# Key: .env suffix. Value: default username, Keycloak realm role, report unit.
ACCOUNTS = {
    "ADMIN": ("dxos-admin", "admin", None),
    "DISPATCHER": ("dxos-dispatcher", "reports_dispatcher", None),
    "REPORTS": ("dxos-reports", "reports_operator", "infrastructure"),
    "REPORTS_ENVIRONMENT": ("dxos-reports-environment", "reports_operator", "environment"),
    "BULLETINS": ("dxos-bulletins", "bulletins_operator", None),
    "SURVEYS": ("dxos-surveys", "surveys_operator", None),
    "APPOINTMENTS": ("dxos-appointments", "appointments_operator", None),
    "ADMINISTRATIVE_FEEDBACK": ("dxos-administrative-feedback", "administrative_feedback_operator", None),
    "AIR_QUALITY": ("dxos-air-quality", "air_quality_operator", None),
    "BUSINESS_FEEDBACK": ("dxos-business-feedback", "business_feedback_operator", None),
    "HOTLINES": ("dxos-hotlines", "hotlines_operator", None),
    "COMMUNICATIONS": ("dxos-communications", "communications_operator", None),
    "COMMUNITY": ("dxos-community", "community_groups_operator", None),
    "SOCIAL_FEEDBACK": ("dxos-social-feedback", "social_feedback_operator", None),
    "DIGITAL_WARD": ("dxos-digital-ward", "digital_ward_operator", None),
    "BUS_SEARCH": ("dxos-bus-search", "bus_search_operator", None),
}


def credentials(values: Mapping[str, str], account: str) -> tuple[str, str]:
    """Resolve an account, retaining the old shared password for existing .env files."""
    default_username, _, _ = ACCOUNTS[account]
    username = values.get(f"DEMO_{account}_USERNAME", default_username).strip()
    password = values.get(f"DEMO_{account}_PASSWORD")
    if password is None and account != "ADMIN":
        password = values.get("DEMO_OPERATOR_PASSWORD")
    if not username or not password:
        raise ValueError(f"Configure DEMO_{account}_USERNAME and DEMO_{account}_PASSWORD in dxos-core/.env")
    return username, password
