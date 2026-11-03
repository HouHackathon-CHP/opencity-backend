# SPDX-License-Identifier: Apache-2.0
"""OpenCity domain API behind the DX-OS gateway."""

from fastapi import FastAPI

from app.api.router import api_router


app = FastAPI(title="OpenCity Domain API", docs_url=None, redoc_url=None)
app.include_router(api_router)
