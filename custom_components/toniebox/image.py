"""Image platform — Toniebox preview image based on bleColorId."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device_info import toniebox_device_info

# bleColorId → CDN preview thumbnail (from boxItemPreviews GraphQL query).
# Note: these URLs are sourced from the Toniebox CDN and may change over time.
# The image_url API fallback is used when no mapping is found.
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

    for hh_id, hh in coordinator.data.get("households", {}).items():
        for tb_id in hh.get("tonieboxes", {}):
            entities.append(TonieboxImage(coordinator, hh_id, tb_id))

    async_add_entities(entities)


class TonieboxImage(CoordinatorEntity, ImageEntity):
    """Preview image of a Toniebox based on its color (bleColorId)."""

    _attr_has_entity_name = True
    _attr_translation_key = "toniebox_image"

    def __init__(self, coordinator, hh_id, tb_id):
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, coordinator.hass)
        self._hh_id = hh_id
        self._tb_id = tb_id
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

    @property
    def image_url(self) -> str | None:
        color_id = self._tb.get("ble_color_id")
        if color_id is not None and color_id in BLE_COLOR_THUMBNAILS:
            return BLE_COLOR_THUMBNAILS[color_id]
        # Fallback to API imageUrl (classic boxes and unknown TNG colors)
        return self._tb.get("image_url")

    @property
    def extra_state_attributes(self):
        color_id = self._tb.get("ble_color_id")
        if color_id is None:
            return {}
        attrs: dict = {"ble_color_id": color_id}
        if color_id in BLE_COLOR_NAMES:
            attrs["color_name"] = BLE_COLOR_NAMES[color_id]
        return attrs
