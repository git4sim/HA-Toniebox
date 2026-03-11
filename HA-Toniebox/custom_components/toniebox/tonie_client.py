"""Tonie Cloud API Client.

Direct async implementation against the official Tonie Cloud REST API.
No external tonie-api library needed — uses only aiohttp (already in HA).

Authentication: Keycloak OpenID Connect (Resource Owner Password Flow)
  POST https://login.tonies.com/auth/realms/tonies/protocol/openid-connect/token

API Base: https://api.tonie.cloud/v2/

Endpoints (from maximilianvoss/toniebox-api Constants.java):
  GET  /v2/me
  GET  /v2/households
  GET  /v2/households/{hid}/creativetonies
  GET  /v2/households/{hid}/creativetonies/{tid}
  PATCH /v2/households/{hid}/creativetonies/{tid}
  POST /v2/file  (upload)
"""

from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# --- API Constants (source: maximilianvoss/toniebox-api) ---
_TOKEN_URL = "https://login.tonies.com/auth/realms/tonies/protocol/openid-connect/token"
_API_BASE = "https://api.tonie.cloud/v2"
_CLIENT_ID = "meine-tonies"

# Token refresh buffer: refresh 60 seconds before expiry
_TOKEN_REFRESH_BUFFER = 60


class TonieCloudAuthError(Exception):
    """Raised when authentication fails."""


class TonieCloudAPIError(Exception):
    """Raised on API errors."""


class TonieCloudClient:
    """Async client for the Tonie Cloud REST API.
    
    Usage:
        client = TonieCloudClient(username, password, session)
        await client.authenticate()
        me = await client.get_me()
        households = await client.get_households()
    """

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _is_token_expired(self) -> bool:
        return time.monotonic() >= (self._token_expires_at - _TOKEN_REFRESH_BUFFER)

    async def authenticate(self) -> None:
        """Authenticate with Keycloak and obtain an access token.
        
        Uses Resource Owner Password Credentials flow (direct grant).
        Keycloak realm: tonies, client_id: meine-tonies
        """
        data = {
            "client_id": _CLIENT_ID,
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
            "scope": "openid",
        }

        try:
            async with self._session.post(
                _TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                if resp.status == 401:
                    raise TonieCloudAuthError(
                        "Invalid credentials. Check your email and password."
                    )
                if resp.status != 200:
                    body = await resp.text()
                    raise TonieCloudAuthError(
                        f"Authentication failed (HTTP {resp.status}): {body}"
                    )

                token_data = await resp.json()
                self._access_token = token_data["access_token"]
                self._refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in", 300)
                self._token_expires_at = time.monotonic() + expires_in

                _LOGGER.debug("Tonie Cloud authentication successful, token valid for %ss", expires_in)

        except aiohttp.ClientError as err:
            raise TonieCloudAuthError(f"Network error during authentication: {err}") from err

    async def _refresh_access_token(self) -> None:
        """Silently refresh the access token using the refresh token."""
        if not self._refresh_token:
            await self.authenticate()
            return

        data = {
            "client_id": _CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }

        try:
            async with self._session.post(
                _TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Token refresh failed, re-authenticating")
                    await self.authenticate()
                    return

                token_data = await resp.json()
                self._access_token = token_data["access_token"]
                self._refresh_token = token_data.get("refresh_token", self._refresh_token)
                expires_in = token_data.get("expires_in", 300)
                self._token_expires_at = time.monotonic() + expires_in

        except aiohttp.ClientError:
            await self.authenticate()

    async def _get(self, path: str) -> Any:
        """Make an authenticated GET request."""
        if self._is_token_expired():
            await self._refresh_access_token()

        url = f"{_API_BASE}{path}"
        async with self._session.get(url, headers=self._auth_headers) as resp:
            if resp.status == 401:
                # Try re-auth once
                await self.authenticate()
                async with self._session.get(url, headers=self._auth_headers) as resp2:
                    resp2.raise_for_status()
                    return await resp2.json()
            resp.raise_for_status()
            return await resp.json()

    async def _patch(self, path: str, payload: dict) -> Any:
        """Make an authenticated PATCH request."""
        if self._is_token_expired():
            await self._refresh_access_token()

        url = f"{_API_BASE}{path}"
        async with self._session.patch(
            url,
            json=payload,
            headers={**self._auth_headers, "Content-Type": "application/json"},
        ) as resp:
            resp.raise_for_status()
            if resp.content_length and resp.content_length > 0:
                return await resp.json()
            return {}

    # ---- Public API methods ----

    async def get_me(self) -> dict:
        """GET /v2/me — returns the authenticated user's profile."""
        return await self._get("/me")

    async def get_households(self) -> list[dict]:
        """GET /v2/households — returns list of households."""
        data = await self._get("/households")
        if isinstance(data, list):
            return data
        return data.get("households", [])

    async def get_creative_tonies(self, household_id: str) -> list[dict]:
        """GET /v2/households/{hid}/creativetonies"""
        data = await self._get(f"/households/{household_id}/creativetonies")
        if isinstance(data, list):
            return data
        return data.get("creativetonies", [])

    async def get_creative_tonie(self, household_id: str, tonie_id: str) -> dict:
        """GET /v2/households/{hid}/creativetonies/{tid}"""
        return await self._get(f"/households/{household_id}/creativetonies/{tonie_id}")

    async def patch_creative_tonie(
        self, household_id: str, tonie_id: str, payload: dict
    ) -> dict:
        """PATCH /v2/households/{hid}/creativetonies/{tid}"""
        return await self._patch(
            f"/households/{household_id}/creativetonies/{tonie_id}", payload
        )

    async def sort_chapters(
        self, household_id: str, tonie_id: str, sort_by: str = "title"
    ) -> None:
        """Sort chapters on a creative tonie by the given criteria."""
        tonie = await self.get_creative_tonie(household_id, tonie_id)
        chapters = tonie.get("chapters", [])

        if sort_by == "title":
            chapters.sort(key=lambda c: c.get("title", "").lower())
        elif sort_by == "filename":
            chapters.sort(key=lambda c: c.get("file", c.get("title", "")).lower())
        elif sort_by == "date":
            # Sort by chapter id or transcoding timestamp if available
            chapters.sort(key=lambda c: c.get("id", ""))

        await self.patch_creative_tonie(
            household_id, tonie_id, {"chapters": chapters}
        )

    async def clear_chapters(self, household_id: str, tonie_id: str) -> None:
        """Remove all chapters from a creative tonie."""
        await self.patch_creative_tonie(
            household_id, tonie_id, {"chapters": []}
        )

    async def remove_chapter(
        self, household_id: str, tonie_id: str, chapter_id: str
    ) -> None:
        """Remove a single chapter by its ID."""
        tonie = await self.get_creative_tonie(household_id, tonie_id)
        chapters = [c for c in tonie.get("chapters", []) if c.get("id") != chapter_id]
        await self.patch_creative_tonie(
            household_id, tonie_id, {"chapters": chapters}
        )
