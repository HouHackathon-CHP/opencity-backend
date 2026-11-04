# SPDX-License-Identifier: Apache-2.0
"""Tenant-scoped operational counts for the OpenCity admin console."""

from contextlib import closing

from app.repositories.administrative_feedback import feedback_db
from app.repositories.appointments import appointment_db
from app.repositories.bulletins import bulletin_db
from app.repositories.business_feedback import petition_db
from app.repositories.hotlines import hotline_db
from app.repositories.community import community_db
from app.repositories.social_feedback import social_feedback_db
from app.repositories.digital_ward import ward_db
from app.repositories.surveys import survey_db


def grouped_counts(database, table: str, column: str, tenant: str) -> dict:
    # Table and column names are fixed by the caller, never sourced from a request.
    with closing(database()) as connection:
        rows = connection.execute(
            f"SELECT {column}, COUNT(*) AS count FROM {table} "
            f"WHERE tenant = ? GROUP BY {column}", (tenant,),
        ).fetchall()
    by_status = {row[0]: row[1] for row in rows}
    return {"total": sum(by_status.values()), "breakdown": by_status}


def local_counts(tenant: str) -> dict:
    return {
        "appointments": grouped_counts(appointment_db, "appointments", "status", tenant),
        "administrative_feedback": grouped_counts(
            feedback_db, "administrative_feedback", "status", tenant),
        "business_feedback": grouped_counts(
            petition_db, "business_petitions", "status", tenant),
        "bulletins": grouped_counts(bulletin_db, "bulletins", "category", tenant),
        "surveys": grouped_counts(survey_db, "surveys", "status", tenant),
        "hotlines": grouped_counts(hotline_db, "hotlines", "active", tenant),
        "community_groups": grouped_counts(community_db, "community_groups", "area", tenant),
        "social_feedback": grouped_counts(social_feedback_db, "consultation_topics", "status", tenant),
        "digital_ward": grouped_counts(ward_db, "digital_wards", "active", tenant),
    }
