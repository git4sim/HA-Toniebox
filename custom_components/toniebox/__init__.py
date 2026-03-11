"""The Toniebox integration — full API v2."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, UPDATE_INTERVAL_MINUTES
from .tonie_client import TonieCloudClient, TonieCloudAuthError

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


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")


def _register_services(hass: HomeAssistant) -> None:
    """Register all custom services."""
    import voluptuous as vol
    from homeassistant.helpers import config_validation as cv

    if hass.services.has_service(DOMAIN, "clear_chapters"):
        return

    async def _find(entity_id: str):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            for hh_id, hh in coordinator.data.get("households", {}).items():
                for t_id, t in hh.get("creativetonies", {}).items():
                    slug = _slugify(t.get("name", t_id))
                    if entity_id in (f"media_player.toniebox_{slug}", entity_id):
                        return coordinator.client, hh_id, t_id
        return None, None, None

    async def _find_toniebox(entity_id: str):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            for hh_id, hh in coordinator.data.get("households", {}).items():
                for tb_id, tb in hh.get("tonieboxes", {}).items():
                    slug = _slugify(tb.get("name", tb_id))
                    if entity_id in (f"media_player.toniebox_box_{slug}", entity_id):
                        return coordinator.client, hh_id, tb_id
        return None, None, None

    # ── Creative Tonie services ───────────────────────────────────────────────

    async def handle_clear_chapters(call):
        client, hh_id, t_id = await _find(call.data["entity_id"])
        if client:
            await client.clear_chapters(hh_id, t_id)
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "clear_chapters", handle_clear_chapters,
        schema=vol.Schema({vol.Required("entity_id"): cv.string}),
    )

    async def handle_sort_chapters(call):
        client, hh_id, t_id = await _find(call.data["entity_id"])
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
        client, hh_id, t_id = await _find(call.data["entity_id"])
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

    async def handle_rename_tonie(call):
        client, hh_id, t_id = await _find(call.data["entity_id"])
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
        client, hh_id, t_id = await _find(call.data["entity_id"])
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
        client, hh_id, t_id = await _find(call.data["entity_id"])
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
        client, hh_id, t_id = await _find(call.data["entity_id"])
        if client:
            await client.delete_tonie_tune(hh_id, t_id)
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "remove_tune", handle_remove_tune,
        schema=vol.Schema({vol.Required("entity_id"): cv.string}),
    )

    # ── Toniebox services ─────────────────────────────────────────────────────

    async def handle_rename_toniebox(call):
        client, hh_id, tb_id = await _find_toniebox(call.data["entity_id"])
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


async def _refresh_all(hass: HomeAssistant) -> None:
    for coordinator in hass.data.get(DOMAIN, {}).values():
        await coordinator.async_request_refresh()


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

            hh_data = {
                "id": hh_id,
                "name": hh.get("name", hh_id),
                "creativetonies": {},
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

            # Tonieboxes
            try:
                boxes = await self.client.get_tonieboxes(hh_id)
                for box in boxes:
                    b_id = box.get("id", "")
                    if not b_id:
                        continue
                    hh_data["tonieboxes"][b_id] = {
                        "id": b_id,
                        "name": box.get("name", b_id),
                        "household_id": hh_id,
                        "firmware": box.get("firmware", {}),
                        "skip_mute_detection": box.get("skip_mute_detection", False),
                        "led": box.get("led", True),
                        "last_seen": box.get("last_seen"),
                        "placement": box.get("placement", {}),
                        "extras": box.get("extras", {}),
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
