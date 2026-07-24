"""
Configuration for the Flock Energy API service.

Portal credentials are read from environment variables so they are never
hard-coded into source control. Create a .env file (see .env.example) or
export these variables in your shell before running the app.
"""

import os

PORTAL_BASE_URL = os.environ.get("URJA_BASE_URL", "https://urja-ops.flockenergy.tech")
PORTAL_USERNAME = os.environ.get("URJA_USERNAME", "")
PORTAL_PASSWORD = os.environ.get("URJA_PASSWORD", "")

# How long to wait on any single request to the legacy portal before giving up.
REQUEST_TIMEOUT_SECONDS = 15.0

# Default page size used when paginating through the portal's list endpoints.
DEFAULT_PAGE_SIZE = 20
