"""The Toniebox integration for Home Assistant.

Directly implements the Tonie Cloud REST API via aiohttp.
No external library required.

Auth: Keycloak OpenID Connect (login.tonies.com)
API:  api.tonie.cloud/v2
"""

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
        raise ConfigEntryAuthFailed(f"Toniebox authentication failed: {err}") from err

    coordinator = TonieboxDataUpdateCoordinator(hass, client, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Could not fetch Toniebox data: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    """Register custom services."""
    import voluptuous as vol
    from homeassistant.helpers import config_validation as cv

    if hass.services.has_service(DOMAIN, "upload_audio"):
        return

    async def _get_client_and_ids(entity_id: str):
        """Find coordinator + household_id + tonie_id for an entity_id."""
        for coordinator in hass.data.get(DOMAIN, {}).values():
            for hh_id, hh in coordinator.data.get("households", {}).items():
                for t_id, t in hh.get("creativetonies", {}).items():
                    slug = _slugify(t.get("name", t_id))
                    if entity_id in (
                        f"media_player.toniebox_{slug}",
                        f"media_player.{slug}",
                        entity_id,  # allow matching by tonie_id directly too
                    ):
                        return coordinator.client, hh_id, t_id
        return None, None, None

    async def handle_clear_chapters(call):
        entity_id = call.data["entity_id"]
        client, hh_id, t_id = await _get_client_and_ids(entity_id)
        if client:
            await client.clear_chapters(hh_id, t_id)
            for coord in hass.data.get(DOMAIN, {}).values():
                await coord.async_request_refresh()

    hass.services.async_register(
        DOMAIN, "clear_chapters", handle_clear_chapters,
        schema=vol.Schema({vol.Required("entity_id"): cv.string}),
    )

    async def handle_sort_chapters(call):
        entity_id = call.data["entity_id"]
        sort_by = call.data.get("sort_by", "title")
        client, hh_id, t_id = await _get_client_and_ids(entity_id)
        if client:
            await client.sort_chapters(hh_id, t_id, sort_by)
            for coord in hass.data.get(DOMAIN, {}).values():
                await coord.async_request_refresh()

    hass.services.async_register(
        DOMAIN, "sort_chapters", handle_sort_chapters,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Optional("sort_by", default="title"): vol.In(["title", "filename", "date"]),
        }),
    )


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")


class TonieboxDataUpdateCoordinator(DataUpdateCoordinator):
    """Async coordinator: polls Tonie Cloud every N minutes."""

    def __init__(self, hass: HomeAssistant, client: TonieCloudClient, entry: ConfigEntry) -> None:
        self.client = client
        self.entry = entry
        super().__init__(
            hass, _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )

    async def _async_update_data(self) -> dict:
        """Fetch all data from the Tonie Cloud API."""
        try:
            return await self._fetch_all()
        except TonieCloudAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Tonie Cloud API error: {err}") from err

    async def _fetch_all(self) -> dict:
        result: dict = {"me": {}, "households": {}}

        try:
            result["me"] = await self.client.get_me()
        except Exception as e:
            _LOGGER.debug("Could not fetch /me: %s", e)

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
            }

            try:
                tonies = await self.client.get_creative_tonies(hh_id)
                for tonie in tonies:
                    t_id = tonie.get("id", "")
                    if not t_id:
                        continue

                    chapters = []
                    for ch in tonie.get("chapters", []):
                        chapters.append({
                            "id": ch.get("id", ""),
                            "title": ch.get("title", ""),
                            "seconds": ch.get("seconds", 0),
                            "transcoding": ch.get("transcoding", False),
                        })

                    hh_data["creativetonies"][t_id] = {
                        "id": t_id,
                        "name": tonie.get("name", t_id),
                        "image_url": tonie.get("imageUrl") or tonie.get("image_url"),
                        "chapters": chapters,
                        "chapter_count": len(chapters),
                        "household_id": hh_id,
                    }
            except Exception as e:
                _LOGGER.warning("Could not fetch tonies for household %s: %s", hh_id, e)

            result["households"][hh_id] = hh_data

        return result
