# SPDX-License-Identifier: Apache-2.0
"""Register the HTTP routes exposed by the OpenCity backend."""

from fastapi import APIRouter

from app.api.routes import admin, administrative_feedback, appointments, bulletins, business_feedback, communications, community, digital_ward, hotlines, notifications, reports, social_feedback, surveys, system


api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(admin.router)
api_router.include_router(notifications.router)
api_router.include_router(bulletins.router)
api_router.include_router(communications.router)
api_router.include_router(community.router)
api_router.include_router(social_feedback.router)
api_router.include_router(digital_ward.router)
api_router.include_router(surveys.router)
api_router.include_router(appointments.router)
api_router.include_router(administrative_feedback.router)
api_router.include_router(business_feedback.router)
api_router.include_router(hotlines.router)
api_router.include_router(reports.router)
