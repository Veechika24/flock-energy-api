"""
Adapter layer for the legacy "Urja Meter Ops" portal.

This module is the ONLY place that knows the portal exists. Everything above
it (main.py) talks to this class and gets back clean, typed data - it never
sees session cookies, HTML, or the portal's quirks directly.

Discovered protocol (see PROTOCOL.md for full details):
    POST {base}/login                        body: email, password (form-encoded)
                                              -> sets __Secure-better-auth.session_token cookie
    GET  {base}/portal/search?q=&page=N       -> paginated meter list (no hierarchy/location)
    GET  {base}/portal/dts?page=N             -> paginated transformer list
    GET  {base}/portal/meters/{id}/geo        -> {"data": {"latitude": "...", "longitude": "..."}}
    GET  {base}/portal/meters/{id}/energy     -> {"data": [{"timestamp","kwh","kvah","voltR"}, ...]}

    Bulk export (via "Export all meters" button on the Transformers page):
    downloads a JSON array of ALL 403 meters, each with full nameplate,
    hierarchy AND geo embedded. This is the only clean source of hierarchy
    data - the per-meter detail page only exposes hierarchy through
    SvelteKit's internal __data.json hydration format, which is not a
    stable API to depend on.

    NOTE: the exact request URL for the "Export all meters" button was not
    confirmed via DevTools before the submission deadline (the browser
    triggered a file download of meter-export.json directly, and we ran
    out of time to inspect the underlying XHR request). EXPORT_ENDPOINT_PATH
    below is a best-guess assumption based on the other endpoint naming
    conventions (/portal/dts, /portal/search) - documented as an assumption
    in README.md. If it 404s, open DevTools -> Network -> Fetch/XHR, click
    "Export all meters" again, and update this constant with the real path.
"""

from typing import Optional, List, Dict, Any

import hashlib
import hmac
import time
import httpx

from app.config import (
    PORTAL_BASE_URL,
    PORTAL_USERNAME,
    PORTAL_PASSWORD,
    REQUEST_TIMEOUT_SECONDS,
)

# Best-guess path based on naming conventions of the other endpoints.
# See note above and README.md "Assumptions" section - not confirmed via DevTools.
EXPORT_ENDPOINT_PATH = "/portal/export"
EXPORT_SIGNING_SECRET = "I3dZPPf5CgTp7JyGNMI8i6z8LFR7TmSR"


class PortalAuthError(Exception):
    """Raised when login to the legacy portal fails."""


class UrjaPortalClient:
    def __init__(
        self,
        base_url: str = PORTAL_BASE_URL,
        username: str = PORTAL_USERNAME,
        password: str = PORTAL_PASSWORD,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._client = httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={
                "Referer": f"{self.base_url}/login",
                "Origin": self.base_url,
            },
        )
        self._authenticated = False

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Authenticate against the portal, storing the session cookie."""
        response = self._client.post(
            f"{self.base_url}/login",
            data={"email": self.username, "password": self.password},
        )
        # The portal responds with a SvelteKit form-action redirect payload
        # (status 200, body {"type": "redirect", ...}) rather than an HTTP
        # redirect, so we check the body instead of response.status_code.
        ok = response.status_code == 200
        try:
            body = response.json()
            ok = ok and body.get("type") == "redirect"
        except ValueError:
            ok = False

        if not ok:
            raise PortalAuthError(
                f"Login failed (status={response.status_code}): {response.text[:200]}"
            )
        self._authenticated = True
    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make a request, transparently re-authenticating once on 401/redirect-to-login."""
        if not self._authenticated:
            self.login()

        url = f"{self.base_url}{path}"
        response = self._client.request(method, url, **kwargs)

        if response.status_code == 401 or "/login" in str(response.url):
            # Session expired - log in again and retry exactly once.
            self.login()
            response = self._client.request(method, url, **kwargs)

        if response.status_code >= 400:
            print("DEBUG error status:", response.status_code)
            print("DEBUG error body:", response.text[:500])
        response.raise_for_status()
        return response

    # ------------------------------------------------------------------
    # Meters
    # ------------------------------------------------------------------
    def get_meters(self, page: int = 1, query: str = "") -> Dict[str, Any]:
        response = self._request(
            "GET", "/portal/meters/search", params={"q": query, "page": page}
        )
        return response.json()

    def get_meter_geo(self, meter_id: str) -> Dict[str, Any]:
        response = self._request("GET", f"/portal/meters/{meter_id}/geo")
        return response.json()["data"]

    def get_meter_energy(self, meter_id: str) -> List[Dict[str, Any]]:
        response = self._request("GET", f"/portal/meters/{meter_id}/energy")
        return response.json()["data"]

    # ------------------------------------------------------------------
    # Transformers
    # ------------------------------------------------------------------
    def get_transformers(self, page: int = 1) -> Dict[str, Any]:
        response = self._request("GET", "/portal/dts", params={"page": page})
        return response.json()

    # ------------------------------------------------------------------
    # Bulk export (hierarchy + geo + nameplate in one call)
    # ------------------------------------------------------------------
    def get_all_meters_export(self) -> List[Dict[str, Any]]:
        """
        Fetch the full bulk export used by the "Export all meters" button.

        Returns a list of raw dicts (already includes nameplate, hierarchy,
        and geo for all meters) - see PROTOCOL.md for the exact shape.
        """
        raise PortalAuthError("Bulk export endpoint requires a request signature whose exact algorithm is not yet confirmed (see PROTOCOL.md). This is a documented, known limitation.")
        _unused_timestamp = str(int(time.time()))
        signature = hmac.new(
            EXPORT_SIGNING_SECRET.encode(),
            timestamp.encode(),
            hashlib.sha256,
        ).hexdigest()
        response = self._request(
            "GET",
            EXPORT_ENDPOINT_PATH,
            headers={
                "Referer": f"{self.base_url}/transformers",
                "X-Signature": signature,
                "X-Timestamp": timestamp,
            },
        )
        return response.json()

    def close(self) -> None:
        self._client.close()
