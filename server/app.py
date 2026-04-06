# ================================================================
# FILE: server/app.py
# PURPOSE: Entry point for OpenEnv multi-mode deployment
# This file is required by OpenEnv validation!
# It simply imports our existing FastAPI app
# ================================================================

from app.main import app

__all__ = ["app"]