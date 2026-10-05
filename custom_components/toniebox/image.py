"""Image platform — Toniebox preview image based on bleColorId."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device_info import toniebox_device_info

_LOGGER = logging.getLogger(__name__)

# bleColorId → CDN preview thumbnail. Fallback only: Tonies moves these CDN
# paths without notice (yellow already returns 403), so the thumbnails from
# GET /box-item-previews are preferred whenever the API provides them.
BLE_COLOR_THUMBNAILS: dict[int, str] = {
    0: "https://cdn.tonies.de/upload/tb2_preview_blue.png",
    1: "https://cdn.tonies.de/upload/tb2_preview_grey.png",
    2: "https://cdn.tonies.de/upload/tb2_preview_red.png",
    3: "https://cdn.tonies.de/upload/tb2_preview_pink.png",
    4: "https://cdn.tonies.de/upload/tb2_preview_teal.png",
    5: "https://cdn.tonies.de/upload/tb2_preview_yellow.png",
}

BLE_COLOR_NAMES: dict[int, str] = {
    0: "Himmelblau",
    1: "Mondgrau",
    2: "Rot",
    3: "Rosa",
    4: "Meeresgrün",
    5: "Blitzgelb",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = []

    previews: dict[int, str] = {}
    try:
        for item in await coordinator.client.get_box_item_previews():
            color_id = item.get("bleColorId")
            thumbnail = item.get("thumbnail")
            if isinstance(color_id, int) and thumbnail:
                previews[color_id] = thumbnail
    except Exception:
        _LOGGER.debug("Could not fetch Toniebox item previews", exc_info=True)

    for hh_id, hh in coordinator.data.get("households", {}).items():
        for tb_id in hh.get("tonieboxes", {}):
            entities.append(TonieboxImage(coordinator, hh_id, tb_id, previews))

    async_add_entities(entities)


class TonieboxImage(CoordinatorEntity, ImageEntity):
    """Preview image of a Toniebox based on its color (bleColorId)."""

    _attr_has_entity_name = True
    _attr_translation_key = "toniebox_image"

    def __init__(self, coordinator, hh_id, tb_id, previews: dict[int, str]):
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._hh_id = hh_id
        self._tb_id = tb_id
        self._previews = previews
        self._image_cache: tuple[tuple[str, ...], bytes] | None = None
        self._attr_unique_id = f"tb_{tb_id}_image"
        # Use current time so HA treats the image as fresh on first load
        self._attr_image_last_updated = datetime.now(timezone.utc)

    @property
    def _tb(self):
        return (
            self.coordinator.data
            .get("households", {}).get(self._hh_id, {})
            .get("tonieboxes", {}).get(self._tb_id, {})
        )

    @property
    def device_info(self):
        return toniebox_device_info(self.coordinator, self._hh_id, self._tb_id)

    def _candidate_urls(self) -> tuple[str, ...]:
        """Image URLs in order of preference, without duplicates."""
        color_id = self._tb.get("ble_color_id")
        urls = (
            self._previews.get(color_id),
            BLE_COLOR_THUMBNAILS.get(color_id),
            # API imageUrl (classic boxes and unknown TNG colors)
            self._tb.get("image_url"),
        )
        return tuple(dict.fromkeys(u for u in urls if u))

    async def async_image(self) -> bytes | None:
        """Return the first candidate image that actually loads."""
        candidates = self._candidate_urls()
        if self._image_cache and self._image_cache[0] == candidates:
            return self._image_cache[1]
        for url in candidates:
            try:
                response = await self._client.get(url, timeout=10, follow_redirects=True)
                response.raise_for_status()
            except httpx.HTTPError as err:
                _LOGGER.debug("Toniebox image %s not available: %s", url, err)
                continue
            content_type = response.headers.get("content-type", "").split(";")[0]
            if not content_type.startswith("image/"):
                _LOGGER.debug("Toniebox image %s is not an image (%s)", url, content_type)
                continue
            self._attr_content_type = content_type
            self._image_cache = (candidates, response.content)
            return response.content
        return None

    @property
    def extra_state_attributes(self):
        color_id = self._tb.get("ble_color_id")
        if color_id is None:
            return {}
        attrs: dict = {"ble_color_id": color_id}
        if color_id in BLE_COLOR_NAMES:
            attrs["color_name"] = BLE_COLOR_NAMES[color_id]
        return attrs
