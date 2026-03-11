"""The Toniebox integration — full API v2."""

from __future__ import annotations

import logging
import os
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, UPDATE_INTERVAL_MINUTES
from .tonie_client import TonieCloudClient, TonieCloudAuthError, TonieCloudAPIError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toniebox from a config entry."""
    session = async_get_clientsession(hass)
    client = TonieCloudClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session,
    )

    try:
        await client.authenticate()
    except TonieCloudAuthError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err

    coordinator = TonieboxDataUpdateCoordinator(hass, client, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Could not fetch data: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


# ── Entity lookup helpers ─────────────────────────────────────────────────────

async def _find_creative_tonie(hass: HomeAssistant, entity_id: str):
    """Look up (client, household_id, tonie_id) for a Creative Tonie entity.

    Uses the entity registry to resolve entity_id → unique_id → tonie_id,
    which is robust against renames and special characters in names.
    Falls back to legacy slug matching for backwards compatibility.
    """
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is not None and entry.unique_id.startswith("ct_"):
        # unique_id format: ct_{t_id}_player
        t_id = entry.unique_id[3:].removesuffix("_player")
        for coordinator in hass.data.get(DOMAIN, {}).values():
            for hh_id, hh in coordinator.data.get("households", {}).items():
                if t_id in hh.get("creativetonies", {}):
                    return coordinator.client, hh_id, t_id

    # Legacy fallback: slug matching
    for coordinator in hass.data.get(DOMAIN, {}).values():
        for hh_id, hh in coordinator.data.get("households", {}).items():
            for t_id, t in hh.get("creativetonies", {}).items():
                slug = _slugify(t.get("name", t_id))
                if entity_id in (f"media_player.toniebox_{slug}", entity_id):
                    return coordinator.client, hh_id, t_id

    return None, None, None


async def _find_toniebox(hass: HomeAssistant, entity_id: str):
    """Look up (client, household_id, toniebox_id) for a Toniebox entity."""
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is not None and entry.unique_id.startswith("tb_"):
        tb_id = entry.unique_id[3:].removesuffix("_player")
        for coordinator in hass.data.get(DOMAIN, {}).values():
            for hh_id, hh in coordinator.data.get("households", {}).items():
                if tb_id in hh.get("tonieboxes", {}):
                    return coordinator.client, hh_id, tb_id

    # Legacy fallback
    for coordinator in hass.data.get(DOMAIN, {}).values():
        for hh_id, hh in coordinator.data.get("households", {}).items():
            for tb_id, tb in hh.get("tonieboxes", {}).items():
                slug = _slugify(tb.get("name", tb_id))
                if entity_id in (f"media_player.toniebox_box_{slug}", entity_id):
                    return coordinator.client, hh_id, tb_id

    return None, None, None


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")


# ── Service registration ──────────────────────────────────────────────────────

def _register_services(hass: HomeAssistant) -> None:
    """Register all custom Toniebox services."""
    import voluptuous as vol
    from homeassistant.helpers import config_validation as cv

    if hass.services.has_service(DOMAIN, "clear_chapters"):
        return  # Already registered (e.g. multiple config entries)

    # ── Creative Tonie services ───────────────────────────────────────────────

    async def handle_clear_chapters(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.clear_chapters(hh_id, t_id)
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "clear_chapters", handle_clear_chapters,
        schema=vol.Schema({vol.Required("entity_id"): cv.string}),
    )

    async def handle_sort_chapters(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.sort_chapters(hh_id, t_id, call.data.get("sort_by", "title"))
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "sort_chapters", handle_sort_chapters,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Optional("sort_by", default="title"): vol.In(["title", "filename", "date"]),
        }),
    )

    async def handle_remove_chapter(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.remove_chapter(hh_id, t_id, call.data["chapter_id"])
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "remove_chapter", handle_remove_chapter,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("chapter_id"): cv.string,
        }),
    )

    async def handle_move_chapter(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            try:
                await client.move_chapter(
                    hh_id, t_id,
                    call.data["chapter_id"],
                    call.data.get("direction", "up"),
                )
                await _refresh_all(hass)
            except TonieCloudAPIError as err:
                _LOGGER.error("move_chapter failed: %s", err)

    hass.services.async_register(
        DOMAIN, "move_chapter", handle_move_chapter,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("chapter_id"): cv.string,
            vol.Optional("direction", default="up"): vol.In(["up", "down"]),
        }),
    )

    async def handle_rename_tonie(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.patch_creative_tonie(hh_id, t_id, {"name": call.data["name"]})
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "rename_tonie", handle_rename_tonie,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("name"): cv.string,
        }),
    )

    async def handle_redeem_token(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.redeem_token_to_creative_tonie(hh_id, t_id, call.data["token"])
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "redeem_content_token", handle_redeem_token,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("token"): cv.string,
        }),
    )

    async def handle_apply_tune(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.put_tonie_tune(hh_id, t_id, call.data["tune_id"])
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "apply_tune", handle_apply_tune,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("tune_id"): cv.string,
        }),
    )

    async def handle_remove_tune(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.delete_tonie_tune(hh_id, t_id)
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "remove_tune", handle_remove_tune,
        schema=vol.Schema({vol.Required("entity_id"): cv.string}),
    )

    async def handle_upload_audio(call):
        entity_id = call.data["entity_id"]
        file_path = call.data["file_path"]
        title = call.data.get("title", "")

        if not os.path.isfile(file_path):
            _LOGGER.error("upload_audio: file not found: %s", file_path)
            return

        client, hh_id, t_id = await _find_creative_tonie(hass, entity_id)
        if not client:
            _LOGGER.error("upload_audio: entity not found: %s", entity_id)
            return

        filename = os.path.basename(file_path)
        if not title:
            title = os.path.splitext(filename)[0]

        try:
            with open(file_path, "rb") as f:
                file_data = f.read()
            await client.upload_and_add_chapter(hh_id, t_id, file_data, filename, title)
            await _refresh_all(hass)
            _LOGGER.info("upload_audio: successfully uploaded '%s' to %s", filename, entity_id)
        except Exception as err:
            _LOGGER.error("upload_audio failed for %s: %s", file_path, err)

    hass.services.async_register(
        DOMAIN, "upload_audio", handle_upload_audio,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("file_path"): cv.string,
            vol.Optional("title", default=""): cv.string,
        }),
    )

    # ── Toniebox services ─────────────────────────────────────────────────────

    async def handle_rename_toniebox(call):
        client, hh_id, tb_id = await _find_toniebox(hass, call.data["entity_id"])
        if client:
            await client.patch_toniebox(hh_id, tb_id, {"name": call.data["name"]})
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "rename_toniebox", handle_rename_toniebox,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("name"): cv.string,
        }),
    )

    # ── Voucher service ───────────────────────────────────────────────────────

    async def handle_redeem_voucher(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.client.redeem_voucher(call.data["code"])
            await _refresh_all(hass)
            return

    hass.services.async_register(
        DOMAIN, "redeem_voucher", handle_redeem_voucher,
        schema=vol.Schema({vol.Required("code"): cv.string}),
    )

    # ── Notification services ─────────────────────────────────────────────────

    async def handle_dismiss_notifications(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.client.delete_all_notifications()
            await _refresh_all(hass)
            return

    hass.services.async_register(
        DOMAIN, "dismiss_all_notifications", handle_dismiss_notifications,
        schema=vol.Schema({}),
    )

    # ── Invitation services ───────────────────────────────────────────────────

    async def handle_accept_invitation(call):
        invitation_id = call.data["invitation_id"]
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.client.accept_invitation(invitation_id)
            await _refresh_all(hass)
            return

    hass.services.async_register(
        DOMAIN, "accept_invitation", handle_accept_invitation,
        schema=vol.Schema({vol.Required("invitation_id"): cv.string}),
    )

    async def handle_decline_invitation(call):
        invitation_id = call.data["invitation_id"]
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.client.delete_invitation(invitation_id)
            await _refresh_all(hass)
            return

    hass.services.async_register(
        DOMAIN, "decline_invitation", handle_decline_invitation,
        schema=vol.Schema({vol.Required("invitation_id"): cv.string}),
    )


async def _refresh_all(hass: HomeAssistant) -> None:
    for coordinator in hass.data.get(DOMAIN, {}).values():
        await coordinator.async_request_refresh()


# ── Coordinator ───────────────────────────────────────────────────────────────

class TonieboxDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator: fetches ALL data from Tonie Cloud."""

    def __init__(self, hass: HomeAssistant, client: TonieCloudClient, entry: ConfigEntry) -> None:
        self.client = client
        self.entry = entry
        super().__init__(
            hass, _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )

    async def _async_update_data(self) -> dict:
        try:
            return await self._fetch_all()
        except TonieCloudAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Tonie Cloud error: {err}") from err

    async def _fetch_all(self) -> dict:
        result: dict = {
            "me": {},
            "households": {},
            "notifications": [],
            "system_notifications": [],
            "invitations": [],
        }

        # User profile
        try:
            result["me"] = await self.client.get_me()
        except Exception as e:
            _LOGGER.debug("Could not fetch /me: %s", e)

        # Notifications
        try:
            result["notifications"] = await self.client.get_notifications()
        except Exception as e:
            _LOGGER.debug("Could not fetch notifications: %s", e)

        # System notifications
        try:
            result["system_notifications"] = await self.client.get_system_notifications()
        except Exception as e:
            _LOGGER.debug("Could not fetch system notifications: %s", e)

        # Pending invitations
        try:
            result["invitations"] = await self.client.get_invitations()
        except Exception as e:
            _LOGGER.debug("Could not fetch invitations: %s", e)

        # Households + all nested data
        try:
            households = await self.client.get_households()
        except Exception as e:
            _LOGGER.error("Could not fetch households: %s", e)
            return result

        for hh in households:
            hh_id = hh.get("id", "")
            if not hh_id:
                continue

            hh_data: dict = {
                "id": hh_id,
                "name": hh.get("name", hh_id),
                "creativetonies": {},
                "contenttonies": {},
                "tonieboxes": {},
                "children": [],
                "memberships": [],
            }

            # Creative Tonies
            try:
                tonies = await self.client.get_creative_tonies(hh_id)
                for tonie in tonies:
                    t_id = tonie.get("id", "")
                    if not t_id:
                        continue
                    chapters = [
                        {
                            "id": ch.get("id", ""),
                            "title": ch.get("title", ""),
                            "seconds": ch.get("seconds", 0),
                            "transcoding": ch.get("transcoding", False),
                        }
                        for ch in tonie.get("chapters", [])
                    ]
                    hh_data["creativetonies"][t_id] = {
                        "id": t_id,
                        "name": tonie.get("name", t_id),
                        "image_url": tonie.get("imageUrl") or tonie.get("image_url"),
                        "chapters": chapters,
                        "chapter_count": len(chapters),
                        "total_seconds": sum(c["seconds"] for c in chapters),
                        "household_id": hh_id,
                        "live": tonie.get("live", False),
                        "private": tonie.get("private", False),
                        "transcoding": tonie.get("transcoding", False),
                    }
            except Exception as e:
                _LOGGER.warning("Could not fetch creativetonies for %s: %s", hh_id, e)

            # Content Tonies (purchased/assigned figurines)
            try:
                content_tonies = await self.client.get_content_tonies(hh_id)
                for ct in content_tonies:
                    ct_id = ct.get("id", "")
                    if not ct_id:
                        continue
                    hh_data["contenttonies"][ct_id] = {
                        "id": ct_id,
                        "name": ct.get("name", ct_id),
                        "image_url": ct.get("imageUrl") or ct.get("image_url"),
                        "household_id": hh_id,
                        "sales_id": ct.get("salesId") or ct.get("sales_id"),
                        "locked": ct.get("locked", False),
                    }
            except Exception as e:
                _LOGGER.debug("Could not fetch contenttonies for %s: %s", hh_id, e)

            # Tonieboxes
            try:
                boxes = await self.client.get_tonieboxes(hh_id)
                for box in boxes:
                    b_id = box.get("id", "")
                    if not b_id:
                        continue

                    placement = box.get("placement", {})
                    placed_tonie = placement.get("tonie", {}) if placement else {}

                    # Playback info — only fetch when a tonie is actively placed
                    playback_info: dict = {}
                    if placed_tonie and placed_tonie.get("id"):
                        try:
                            playback_info = await self.client.get_playback_info(
                                b_id, placed_tonie["id"]
                            )
                        except Exception as e:
                            _LOGGER.debug(
                                "Playback info not available for box %s: %s", b_id, e
                            )

                    hh_data["tonieboxes"][b_id] = {
                        "id": b_id,
                        "name": box.get("name", b_id),
                        "household_id": hh_id,
                        "firmware": box.get("firmware", {}),
                        "skip_mute_detection": box.get("skip_mute_detection", False),
                        "led": box.get("led", True),
                        "last_seen": box.get("last_seen"),
                        "placement": placement,
                        "extras": box.get("extras", {}),
                        "playback_info": playback_info,
                    }
            except Exception as e:
                _LOGGER.debug("Could not fetch tonieboxes for %s: %s", hh_id, e)

            # Children
            try:
                hh_data["children"] = await self.client.get_children(hh_id)
            except Exception as e:
                _LOGGER.debug("Could not fetch children for %s: %s", hh_id, e)

            # Memberships
            try:
                hh_data["memberships"] = await self.client.get_memberships(hh_id)
            except Exception as e:
                _LOGGER.debug("Could not fetch memberships for %s: %s", hh_id, e)

            result["households"][hh_id] = hh_data

        return result
