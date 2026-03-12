"""Tonie Cloud API Client — Full v2 implementation.

Covers ALL documented REST endpoints from https://api.tonie.cloud/v2/doc/

Authentication: Keycloak OpenID Connect (Resource Owner Password Flow)
  POST https://login.tonies.com/auth/realms/tonies/protocol/openid-connect/token

API Base: https://api.tonie.cloud/v2
"""

from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_TOKEN_URL = "https://login.tonies.com/auth/realms/tonies/protocol/openid-connect/token"
_API_BASE = "https://api.tonie.cloud/v2"
_CLIENT_ID = "meine-tonies"
_TOKEN_REFRESH_BUFFER = 60

# Supported audio content types by file extension
_AUDIO_CONTENT_TYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "wav": "audio/wav",
    "flac": "audio/flac",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "opus": "audio/opus",
}


class TonieCloudAuthError(Exception):
    """Raised when authentication fails."""


class TonieCloudAPIError(Exception):
    """Raised on API errors."""


class TonieCloudClient:
    """Full async client for the Tonie Cloud REST API."""

    def __init__(self, username: str, password: str, session: aiohttp.ClientSession) -> None:
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

    # ── Authentication ────────────────────────────────────────────────────────

    async def authenticate(self) -> None:
        """Authenticate with Keycloak (Resource Owner Password flow)."""
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
                    raise TonieCloudAuthError("Invalid credentials.")
                if resp.status != 200:
                    body = await resp.text()
                    raise TonieCloudAuthError(f"Auth failed ({resp.status}): {body}")
                token_data = await resp.json()
                self._access_token = token_data["access_token"]
                self._refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in", 300)
                self._token_expires_at = time.monotonic() + expires_in
                _LOGGER.debug("Authenticated, token valid for %ss", expires_in)
        except aiohttp.ClientError as err:
            raise TonieCloudAuthError(f"Network error: {err}") from err

    async def _refresh_access_token(self) -> None:
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
                    await self.authenticate()
                    return
                token_data = await resp.json()
                self._access_token = token_data["access_token"]
                self._refresh_token = token_data.get("refresh_token", self._refresh_token)
                expires_in = token_data.get("expires_in", 300)
                self._token_expires_at = time.monotonic() + expires_in
        except aiohttp.ClientError:
            await self.authenticate()

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    async def _ensure_auth(self) -> None:
        if self._is_token_expired():
            await self._refresh_access_token()

    async def _get(self, path: str) -> Any:
        await self._ensure_auth()
        url = f"{_API_BASE}{path}"
        async with self._session.get(url, headers=self._auth_headers) as resp:
            if resp.status == 401:
                await self.authenticate()
                async with self._session.get(url, headers=self._auth_headers) as r2:
                    r2.raise_for_status()
                    return await r2.json()
            resp.raise_for_status()
            return await resp.json()

    async def _post(self, path: str, payload: dict | None = None) -> Any:
        await self._ensure_auth()
        url = f"{_API_BASE}{path}"
        async with self._session.post(
            url,
            json=payload or {},
            headers={**self._auth_headers, "Content-Type": "application/json"},
        ) as resp:
            resp.raise_for_status()
            try:
                return await resp.json()
            except Exception:
                return {}

    async def _put(self, path: str, payload: dict) -> Any:
        await self._ensure_auth()
        url = f"{_API_BASE}{path}"
        async with self._session.put(
            url,
            json=payload,
            headers={**self._auth_headers, "Content-Type": "application/json"},
        ) as resp:
            resp.raise_for_status()
            try:
                return await resp.json()
            except Exception:
                return {}

    async def _patch(self, path: str, payload: dict) -> Any:
        await self._ensure_auth()
        url = f"{_API_BASE}{path}"
        async with self._session.patch(
            url,
            json=payload,
            headers={**self._auth_headers, "Content-Type": "application/json"},
        ) as resp:
            resp.raise_for_status()
            try:
                return await resp.json()
            except Exception:
                return {}

    async def _delete(self, path: str) -> None:
        await self._ensure_auth()
        url = f"{_API_BASE}{path}"
        async with self._session.delete(url, headers=self._auth_headers) as resp:
            resp.raise_for_status()

    # ── /me ──────────────────────────────────────────────────────────────────

    async def get_me(self) -> dict:
        """GET /me — authenticated user profile."""
        return await self._get("/me")

    async def patch_me(self, payload: dict) -> dict:
        """PATCH /me — update user profile."""
        return await self._patch("/me", payload)

    # ── /config ───────────────────────────────────────────────────────────────

    async def get_config(self) -> dict:
        """GET /config — global app config."""
        return await self._get("/config")

    # ── /version ─────────────────────────────────────────────────────────────

    async def get_version(self) -> dict:
        """GET /version — API version info."""
        return await self._get("/version")

    # ── /geoip ───────────────────────────────────────────────────────────────

    async def get_geoip(self) -> dict:
        """GET /geoip — geo location of current IP."""
        return await self._get("/geoip")

    # ── /flags ───────────────────────────────────────────────────────────────

    async def get_flags(self) -> dict:
        """GET /flags — feature flags."""
        return await self._get("/flags")

    # ── /timezones ────────────────────────────────────────────────────────────

    async def get_timezones(self) -> list:
        """GET /timezones — list of supported timezones."""
        return await self._get("/timezones")

    # ── /toniebox-languages ───────────────────────────────────────────────────

    async def get_toniebox_languages(self) -> list:
        """GET /toniebox-languages — list of supported toniebox languages."""
        return await self._get("/toniebox-languages")

    # ── /notifications ────────────────────────────────────────────────────────

    async def get_notifications(self) -> list:
        """GET /notifications — user notifications."""
        data = await self._get("/notifications")
        return data if isinstance(data, list) else data.get("results", [])

    async def delete_all_notifications(self) -> None:
        """DELETE /notifications — clear all notifications."""
        await self._delete("/notifications")

    async def get_notification(self, notification_id: str) -> dict:
        """GET /notifications/{id}."""
        return await self._get(f"/notifications/{notification_id}")

    async def patch_notification(self, notification_id: str, payload: dict) -> dict:
        """PATCH /notifications/{id} — e.g. mark as read."""
        return await self._patch(f"/notifications/{notification_id}", payload)

    async def delete_notification(self, notification_id: str) -> None:
        """DELETE /notifications/{id}."""
        await self._delete(f"/notifications/{notification_id}")

    # ── /system-notifications ─────────────────────────────────────────────────

    async def get_system_notifications(self) -> list:
        """GET /system-notifications — system-wide announcements."""
        data = await self._get("/system-notifications")
        return data if isinstance(data, list) else data.get("results", [])

    async def get_system_notification(self, notification_id: str) -> dict:
        """GET /system-notifications/{id}."""
        return await self._get(f"/system-notifications/{notification_id}")

    async def delete_system_notification(self, notification_id: str) -> None:
        """DELETE /system-notifications/{id}."""
        await self._delete(f"/system-notifications/{notification_id}")

    # ── /consents ─────────────────────────────────────────────────────────────

    async def get_consent(self, consent_type: str) -> dict:
        """GET /consents/{consent_type}."""
        return await self._get(f"/consents/{consent_type}")

    async def patch_consent(self, consent_type: str, payload: dict) -> dict:
        """PATCH /consents/{consent_type}."""
        return await self._patch(f"/consents/{consent_type}", payload)

    # ── /invitations ──────────────────────────────────────────────────────────

    async def get_invitations(self) -> list:
        """GET /invitations — pending invitations for current user."""
        data = await self._get("/invitations")
        return data if isinstance(data, list) else data.get("results", [])

    async def get_invitation(self, invitation_id: str) -> dict:
        """GET /invitations/{id}."""
        return await self._get(f"/invitations/{invitation_id}")

    async def delete_invitation(self, invitation_id: str) -> None:
        """DELETE /invitations/{id} — decline invitation."""
        await self._delete(f"/invitations/{invitation_id}")

    async def accept_invitation(self, invitation_id: str) -> dict:
        """POST /invitations/{id}/accept."""
        return await self._post(f"/invitations/{invitation_id}/accept")

    # ── /households ───────────────────────────────────────────────────────────

    async def get_households(self) -> list[dict]:
        """GET /households."""
        data = await self._get("/households")
        return data if isinstance(data, list) else data.get("households", [])

    async def create_household(self, payload: dict) -> dict:
        """POST /households."""
        return await self._post("/households", payload)

    async def get_household(self, household_id: str) -> dict:
        """GET /households/{id}."""
        return await self._get(f"/households/{household_id}")

    async def patch_household(self, household_id: str, payload: dict) -> dict:
        """PATCH /households/{id}."""
        return await self._patch(f"/households/{household_id}", payload)

    async def delete_household(self, household_id: str) -> None:
        """DELETE /households/{id}."""
        await self._delete(f"/households/{household_id}")

    # ── /households/{id}/children ─────────────────────────────────────────────

    async def get_children(self, household_id: str) -> list:
        """GET /households/{hh}/children."""
        data = await self._get(f"/households/{household_id}/children")
        return data if isinstance(data, list) else data.get("results", [])

    async def create_child(self, household_id: str, payload: dict) -> dict:
        """POST /households/{hh}/children."""
        return await self._post(f"/households/{household_id}/children", payload)

    async def get_child(self, household_id: str, child_id: str) -> dict:
        """GET /households/{hh}/children/{id}."""
        return await self._get(f"/households/{household_id}/children/{child_id}")

    async def patch_child(self, household_id: str, child_id: str, payload: dict) -> dict:
        """PATCH /households/{hh}/children/{id}."""
        return await self._patch(f"/households/{household_id}/children/{child_id}", payload)

    async def delete_child(self, household_id: str, child_id: str) -> None:
        """DELETE /households/{hh}/children/{id}."""
        await self._delete(f"/households/{household_id}/children/{child_id}")

    # ── /households/{id}/memberships ──────────────────────────────────────────

    async def get_memberships(self, household_id: str) -> list:
        """GET /households/{hh}/memberships."""
        data = await self._get(f"/households/{household_id}/memberships")
        return data if isinstance(data, list) else data.get("results", [])

    async def get_membership(self, household_id: str, membership_id: str) -> dict:
        """GET /households/{hh}/memberships/{id}."""
        return await self._get(f"/households/{household_id}/memberships/{membership_id}")

    async def patch_membership(self, household_id: str, membership_id: str, payload: dict) -> dict:
        """PATCH /households/{hh}/memberships/{id}."""
        return await self._patch(f"/households/{household_id}/memberships/{membership_id}", payload)

    async def delete_membership(self, household_id: str, membership_id: str) -> None:
        """DELETE /households/{hh}/memberships/{id}."""
        await self._delete(f"/households/{household_id}/memberships/{membership_id}")

    async def get_eligible_owners(self, household_id: str) -> list:
        """GET /households/{hh}/eligible-owners."""
        data = await self._get(f"/households/{household_id}/eligible-owners")
        return data if isinstance(data, list) else data.get("results", [])

    # ── /households/{id}/invitations ──────────────────────────────────────────

    async def get_household_invitations(self, household_id: str) -> list:
        """GET /households/{hh}/invitations."""
        data = await self._get(f"/households/{household_id}/invitations")
        return data if isinstance(data, list) else data.get("results", [])

    async def create_household_invitation(self, household_id: str, payload: dict) -> dict:
        """POST /households/{hh}/invitations — invite by email."""
        return await self._post(f"/households/{household_id}/invitations", payload)

    async def resend_household_invitation(self, household_id: str, invitation_id: str) -> dict:
        """POST /households/{hh}/invitations/{id}/resend."""
        return await self._post(f"/households/{household_id}/invitations/{invitation_id}/resend")

    async def delete_household_invitation(self, household_id: str, invitation_id: str) -> None:
        """DELETE /households/{hh}/invitations/{id}."""
        await self._delete(f"/households/{household_id}/invitations/{invitation_id}")


    async def get_membership_permissions(self, household_id: str, membership_id: str) -> list:
        """GET /households/{hh}/memberships/{id}/permissions — Creative Tonies this member can access."""
        data = await self._get(
            f"/households/{household_id}/memberships/{membership_id}/permissions"
        )
        return data if isinstance(data, list) else data.get("results", [])

    async def put_membership(self, household_id: str, membership_id: str, payload: dict) -> dict:
        """PUT /households/{hh}/memberships/{id} — change membership type / transfer ownership."""
        return await self._put(
            f"/households/{household_id}/memberships/{membership_id}", payload
        )

    async def get_household_invitation(self, household_id: str, invitation_id: str) -> dict:
        """GET /households/{hh}/invitations/{id}."""
        return await self._get(f"/households/{household_id}/invitations/{invitation_id}")

    async def put_household_invitation(self, household_id: str, invitation_id: str, payload: dict) -> dict:
        """PUT /households/{hh}/invitations/{id} — change invitation type."""
        return await self._put(
            f"/households/{household_id}/invitations/{invitation_id}", payload
        )

    async def patch_household_invitation(self, household_id: str, invitation_id: str, payload: dict) -> dict:
        """PATCH /households/{hh}/invitations/{id}."""
        return await self._patch(
            f"/households/{household_id}/invitations/{invitation_id}", payload
        )

    # ── /households/{id}/tonieboxes ───────────────────────────────────────────

    async def get_tonieboxes(self, household_id: str) -> list[dict]:
        """GET /households/{hh}/tonieboxes."""
        data = await self._get(f"/households/{household_id}/tonieboxes")
        return data if isinstance(data, list) else data.get("results", [])

    async def get_toniebox(self, household_id: str, toniebox_id: str) -> dict:
        """GET /households/{hh}/tonieboxes/{id}."""
        return await self._get(f"/households/{household_id}/tonieboxes/{toniebox_id}")

    async def patch_toniebox(self, household_id: str, toniebox_id: str, payload: dict) -> dict:
        """PATCH /households/{hh}/tonieboxes/{id} — rename, set timezone/language etc."""
        return await self._patch(f"/households/{household_id}/tonieboxes/{toniebox_id}", payload)

    async def delete_toniebox(self, household_id: str, toniebox_id: str) -> None:
        """DELETE /households/{hh}/tonieboxes/{id} — remove from household."""
        await self._delete(f"/households/{household_id}/tonieboxes/{toniebox_id}")


    async def put_toniebox(self, household_id: str, toniebox_id: str, payload: dict) -> dict:
        """PUT /households/{hh}/tonieboxes/{id} — replace all Toniebox settings."""
        return await self._put(f"/households/{household_id}/tonieboxes/{toniebox_id}", payload)

    async def reset_toniebox(self, household_id: str, toniebox_id: str) -> dict:
        """Factory-reset Toniebox settings (keep in household) via PATCH reset=true."""
        return await self._patch(
            f"/households/{household_id}/tonieboxes/{toniebox_id}", {"reset": True}
        )

    async def create_toniebox(self, household_id: str, payload: dict) -> dict:
        """POST /households/{hh}/tonieboxes — add Toniebox to household."""
        return await self._post(f"/households/{household_id}/tonieboxes", payload)

    async def get_toniebox_by_id(self, toniebox_id: str) -> dict:
        """GET /tonieboxes/{id} — direct lookup without household."""
        return await self._get(f"/tonieboxes/{toniebox_id}")

    # ── /playback-info ────────────────────────────────────────────────────────

    async def get_playback_info(self, toniebox_id: str, tonie_id: str) -> dict:
        """GET /playback-info/{toniebox_id}/{tonie_id} — current playback state."""
        return await self._get(f"/playback-info/{toniebox_id}/{tonie_id}")

    # ── /households/{id}/creativetonies ───────────────────────────────────────

    async def get_creative_tonies(self, household_id: str) -> list[dict]:
        """GET /households/{hh}/creativetonies."""
        data = await self._get(f"/households/{household_id}/creativetonies")
        return data if isinstance(data, list) else data.get("creativetonies", [])

    async def get_creative_tonie(self, household_id: str, tonie_id: str) -> dict:
        """GET /households/{hh}/creativetonies/{id}."""
        return await self._get(f"/households/{household_id}/creativetonies/{tonie_id}")

    async def patch_creative_tonie(self, household_id: str, tonie_id: str, payload: dict) -> dict:
        """PATCH /households/{hh}/creativetonies/{id}."""
        return await self._patch(f"/households/{household_id}/creativetonies/{tonie_id}", payload)

    async def delete_creative_tonie(self, household_id: str, tonie_id: str) -> None:
        """DELETE /households/{hh}/creativetonies/{id}."""
        await self._delete(f"/households/{household_id}/creativetonies/{tonie_id}")

    async def redeem_token_to_creative_tonie(
        self, household_id: str, tonie_id: str, token: str
    ) -> dict:
        """POST /households/{hh}/creativetonies/{id}/redeem-token."""
        return await self._post(
            f"/households/{household_id}/creativetonies/{tonie_id}/redeem-token",
            {"token": token},
        )

    async def get_creative_tonie_permissions(self, household_id: str, tonie_id: str) -> list:
        """GET /households/{hh}/creativetonies/{id}/permissions."""
        data = await self._get(
            f"/households/{household_id}/creativetonies/{tonie_id}/permissions"
        )
        return data if isinstance(data, list) else data.get("results", [])

    async def put_creative_tonie_permission(
        self, household_id: str, tonie_id: str, permission_id: str, payload: dict
    ) -> dict:
        """PUT /households/{hh}/creativetonies/{id}/permissions/{pid}."""
        return await self._put(
            f"/households/{household_id}/creativetonies/{tonie_id}/permissions/{permission_id}",
            payload,
        )

    # ── Chapter helpers ───────────────────────────────────────────────────────

    async def sort_chapters(self, household_id: str, tonie_id: str, sort_by: str = "title") -> None:
        """Sort chapters on a creative tonie."""
        tonie = await self.get_creative_tonie(household_id, tonie_id)
        chapters = tonie.get("chapters", [])
        if sort_by == "title":
            chapters.sort(key=lambda c: c.get("title", "").lower())
        elif sort_by == "filename":
            chapters.sort(key=lambda c: c.get("file", c.get("title", "")).lower())
        elif sort_by == "date":
            chapters.sort(key=lambda c: c.get("id", ""))
        await self.patch_creative_tonie(household_id, tonie_id, {"chapters": chapters})

    async def clear_chapters(self, household_id: str, tonie_id: str) -> None:
        """Remove all chapters from a creative tonie."""
        await self.patch_creative_tonie(household_id, tonie_id, {"chapters": []})

    async def remove_chapter(self, household_id: str, tonie_id: str, chapter_id: str) -> None:
        """Remove a single chapter by ID."""
        tonie = await self.get_creative_tonie(household_id, tonie_id)
        chapters = [c for c in tonie.get("chapters", []) if c.get("id") != chapter_id]
        await self.patch_creative_tonie(household_id, tonie_id, {"chapters": chapters})

    async def move_chapter(
        self, household_id: str, tonie_id: str, chapter_id: str, direction: str
    ) -> None:
        """Move a chapter one position up or down.

        Args:
            direction: 'up' to move earlier in the list, 'down' to move later.
        """
        tonie = await self.get_creative_tonie(household_id, tonie_id)
        chapters = list(tonie.get("chapters", []))
        idx = next(
            (i for i, c in enumerate(chapters) if c.get("id") == chapter_id), None
        )
        if idx is None:
            raise TonieCloudAPIError(f"Chapter {chapter_id} not found on tonie {tonie_id}")

        if direction == "up" and idx > 0:
            chapters[idx], chapters[idx - 1] = chapters[idx - 1], chapters[idx]
        elif direction == "down" and idx < len(chapters) - 1:
            chapters[idx], chapters[idx + 1] = chapters[idx + 1], chapters[idx]
        else:
            _LOGGER.debug("move_chapter: chapter already at boundary, no change needed")
            return

        await self.patch_creative_tonie(household_id, tonie_id, {"chapters": chapters})

    # ── /households/{id}/contenttonies ────────────────────────────────────────

    async def get_content_tonies(self, household_id: str) -> list[dict]:
        """GET /households/{hh}/contenttonies — all purchased/assigned content tonies."""
        data = await self._get(f"/households/{household_id}/contenttonies")
        _LOGGER.debug(
            "get_content_tonies(%s): response type=%s, %s",
            household_id, type(data).__name__,
            f"keys={list(data.keys())}" if isinstance(data, dict) else f"len={len(data)}",
        )
        if isinstance(data, list):
            if data:
                _LOGGER.debug("get_content_tonies: first item fields: %s", list(data[0].keys()) if isinstance(data[0], dict) else type(data[0]).__name__)
            return data
        if isinstance(data, dict):
            # Try known wrapper keys (both snake_case and camelCase)
            for key in (
                "contenttonies", "contentTonies", "content_tonies",
                "data", "items", "results", "tonies", "tonie",
                "figurines", "tonieFigurines",
            ):
                if key in data and isinstance(data[key], list):
                    _LOGGER.debug("get_content_tonies: found list under key '%s'", key)
                    return data[key]
            # Fallback: return the first list value found
            for key, val in data.items():
                if isinstance(val, list):
                    _LOGGER.warning(
                        "get_content_tonies: unexpected response key '%s'. "
                        "Top-level keys: %s", key, list(data.keys())
                    )
                    return val
            _LOGGER.warning(
                "get_content_tonies: response contains no list. "
                "Top-level keys: %s", list(data.keys())
            )
        return []

    async def patch_content_tonie(self, household_id: str, tonie_id: str, payload: dict) -> dict:
        """PATCH /households/{hh}/contenttonies/{id} — e.g. lock to household."""
        return await self._patch(f"/households/{household_id}/contenttonies/{tonie_id}", payload)

    async def delete_content_tonie(self, household_id: str, tonie_id: str) -> None:
        """DELETE /households/{hh}/contenttonies/{id}."""
        await self._delete(f"/households/{household_id}/contenttonies/{tonie_id}")

    async def put_content_tonie_permission(
        self, household_id: str, tonie_id: str, permission_id: str, payload: dict
    ) -> dict:
        """PUT /households/{hh}/contenttonies/{id}/permissions/{pid}."""
        return await self._put(
            f"/households/{household_id}/contenttonies/{tonie_id}/permissions/{permission_id}",
            payload,
        )


    async def patch_content_tonie_permission(
        self, household_id: str, tonie_id: str, permission_id: str, payload: dict
    ) -> dict:
        """PATCH /households/{hh}/contenttonies/{id}/permissions/{pid}."""
        return await self._patch(
            f"/households/{household_id}/contenttonies/{tonie_id}/permissions/{permission_id}",
            payload,
        )

    async def get_content_tonie_permissions(self, household_id: str, tonie_id: str) -> list:
        """GET /households/{hh}/contenttonies/{id}/permissions."""
        data = await self._get(
            f"/households/{household_id}/contenttonies/{tonie_id}/permissions"
        )
        return data if isinstance(data, list) else data.get("results", [])

    # ── /households/{id}/discs ────────────────────────────────────────────────

    async def get_discs(self, household_id: str) -> list[dict]:
        """GET /households/{hh}/discs — all content discs."""
        data = await self._get(f"/households/{household_id}/discs")
        _LOGGER.debug(
            "get_discs(%s): response type=%s, %s",
            household_id, type(data).__name__,
            f"keys={list(data.keys())}" if isinstance(data, dict) else f"len={len(data)}",
        )
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("discs", "data", "items", "results"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            # Fallback: first list value
            for val in data.values():
                if isinstance(val, list):
                    return val
        return []

    async def patch_disc(self, household_id: str, disc_id: str, payload: dict) -> dict:
        """PATCH /households/{hh}/discs/{id} — e.g. lock disc."""
        return await self._patch(f"/households/{household_id}/discs/{disc_id}", payload)

    async def delete_disc(self, household_id: str, disc_id: str) -> None:
        """DELETE /households/{hh}/discs/{id}."""
        await self._delete(f"/households/{household_id}/discs/{disc_id}")

    async def put_disc_permission(
        self, household_id: str, disc_id: str, permission_id: str, payload: dict
    ) -> dict:
        """PUT /households/{hh}/discs/{id}/permissions/{pid}."""
        return await self._put(
            f"/households/{household_id}/discs/{disc_id}/permissions/{permission_id}",
            payload,
        )


    async def patch_disc_permission(
        self, household_id: str, disc_id: str, permission_id: str, payload: dict
    ) -> dict:
        """PATCH /households/{hh}/discs/{disc_pk}/permissions/{id}."""
        return await self._patch(
            f"/households/{household_id}/discs/{disc_id}/permissions/{permission_id}",
            payload,
        )

    # ── /households/{id}/tonie tune ───────────────────────────────────────────

    async def put_tonie_tune(self, household_id: str, tonie_id: str, tune_id: str) -> dict:
        """PUT /households/{hh}/tonie/{id}/tune/{tune_id} — apply Tune to Tonie."""
        return await self._put(
            f"/households/{household_id}/tonie/{tonie_id}/tune/{tune_id}", {}
        )

    async def delete_tonie_tune(self, household_id: str, tonie_id: str) -> None:
        """DELETE /households/{hh}/tonie/{id}/tune — remove active Tune."""
        await self._delete(f"/households/{household_id}/tonie/{tonie_id}/tune")

    # ── /file (audio upload) ──────────────────────────────────────────────────

    async def upload_file(self, file_data: bytes, filename: str) -> dict:
        """POST /file — upload audio file, returns file reference for chapter creation."""
        await self._ensure_auth()
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "mp3"
        content_type = _AUDIO_CONTENT_TYPES.get(ext, "audio/mpeg")
        form = aiohttp.FormData()
        form.add_field("file", file_data, filename=filename, content_type=content_type)
        url = f"{_API_BASE}/file"
        async with self._session.post(url, data=form, headers=self._auth_headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def upload_and_add_chapter(
        self,
        household_id: str,
        tonie_id: str,
        file_data: bytes,
        filename: str,
        title: str,
    ) -> dict:
        """Upload an audio file and append it as a new chapter on a Creative Tonie.

        This is a two-step operation:
          1. POST /file  →  get file ID
          2. PATCH /creativetonies/{id}  →  append chapter with that file ID
        """
        # Step 1: upload
        upload_result = await self.upload_file(file_data, filename)
        file_id = upload_result.get("id") or upload_result.get("fileId")
        if not file_id:
            raise TonieCloudAPIError(
                f"Upload succeeded but returned no file ID. Response: {upload_result}"
            )

        # Step 2: append chapter
        tonie = await self.get_creative_tonie(household_id, tonie_id)
        chapters = list(tonie.get("chapters", []))
        chapters.append({"id": file_id, "title": title or filename})
        return await self.patch_creative_tonie(
            household_id, tonie_id, {"chapters": chapters}
        )

    # ── /check-tune-status ────────────────────────────────────────────────────

    async def check_tune_status(self, payload: dict) -> dict:
        """POST /check-tune-status."""
        return await self._post("/check-tune-status", payload)

    # ── /box-item-previews ────────────────────────────────────────────────────

    async def get_box_item_previews(self) -> list:
        """GET /box-item-previews — preview data for toniebox items."""
        data = await self._get("/box-item-previews")
        return data if isinstance(data, list) else data.get("results", [])

    # ── /toniebox-setup ───────────────────────────────────────────────────────

    async def get_toniebox_setup(self, setup_id: str) -> dict:
        """GET /toniebox-setup/{id}."""
        return await self._get(f"/toniebox-setup/{setup_id}")

    async def patch_toniebox_setup(self, setup_id: str, payload: dict) -> dict:
        """PATCH /toniebox-setup/{id}."""
        return await self._patch(f"/toniebox-setup/{setup_id}", payload)

    async def patch_toniebox_setup_frontend_status(self, toniebox_id: str, payload: dict) -> dict:
        """PATCH /toniebox-setup/{toniebox_id}/frontendstatus."""
        return await self._patch(f"/toniebox-setup/{toniebox_id}/frontendstatus", payload)


    async def create_toniebox_setup(self, setup_id: str, payload: dict) -> dict:
        """POST /toniebox-setup/{id} — start automatic Toniebox setup."""
        return await self._post(f"/toniebox-setup/{setup_id}", payload)

    async def create_wifi_setup(self, setup_id: str, payload: dict) -> dict:
        """POST /wifi-setup/{id} — start Wi-Fi-only setup."""
        return await self._post(f"/wifi-setup/{setup_id}", payload)

    # ── /wifi-setup ───────────────────────────────────────────────────────────

    async def get_wifi_setup(self, setup_id: str) -> dict:
        """GET /wifi-setup/{id}."""
        return await self._get(f"/wifi-setup/{setup_id}")

    async def patch_wifi_setup_frontend_status(self, toniebox_id: str, payload: dict) -> dict:
        """PATCH /wifi-setup/{toniebox_id}/frontend-status."""
        return await self._patch(f"/wifi-setup/{toniebox_id}/frontend-status", payload)

    # ── /tunes-vouchers ───────────────────────────────────────────────────────

    async def redeem_voucher(self, code: str) -> dict:
        """POST /tunes-vouchers/{code} — redeem a Tunes voucher."""
        return await self._post(f"/tunes-vouchers/{code}")

    # ── /contenttonieitems ────────────────────────────────────────────────────

    async def get_compatible_tunes_for_content_tonie(self, sales_id: str) -> list:
        """GET /contenttonieitems/{sales_id}/compatibletunes-item-sales-ids."""
        data = await self._get(f"/contenttonieitems/{sales_id}/compatibletunes-item-sales-ids")
        return data if isinstance(data, list) else data.get("results", [])

    # ── /tunesitems ───────────────────────────────────────────────────────────

    async def get_compatible_content_tonies_for_tune(self, sales_id: str) -> list:
        """GET /tunesitems/{sales_id}/compatible-contenttonie-item-sales-ids."""
        data = await self._get(f"/tunesitems/{sales_id}/compatible-contenttonie-item-sales-ids")
        return data if isinstance(data, list) else data.get("results", [])
