"""Configuration for the Enhanced Dashboard Pro.

Centralizes environment-driven settings so we avoid hard-coded values
inside the main dashboard_pro entrypoint.
"""

from __future__ import annotations

import os

# Network configuration for the dashboard
DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")

# Default port for the dashboard web server
# Can be overridden via DASHBOARD_PORT environment variable.
try:
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8888"))
except ValueError:
    # Fallback to a safe default if the env var is invalid
    DASHBOARD_PORT = 8888

