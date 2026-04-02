"""Shared rate limiter instance for FastAPI application.

Extracted to a separate module to avoid circular imports
between app.py and routers.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
