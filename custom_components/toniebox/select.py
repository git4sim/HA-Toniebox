"""Select platform — sort mode selector on each Creative Tonie device."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SORT_OPTIONS, SORT_BY_TITLE
from .device_info import creative_tonie_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = []

    for hh_id, hh in coordinator.data.get("households", {}).items():
        for t_id in hh.get("creativetonies", {}):
            entities.append(TonieSortSelect(coordinator, hh_id, t_id))

    async_add_entities(entities)


class TonieSortSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True
    _attr_options = SORT_OPTIONS
    _attr_icon = "mdi:sort"
    _attr_name = "Kapitel sortieren"

    def __init__(self, coordinator, hh_id: str, t_id: str) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._t_id = t_id
        self._current = SORT_BY_TITLE
        self._attr_unique_id = f"ct_{t_id}_sort_select"

    @property
    def device_info(self) -> dict:
        return creative_tonie_device_info(self.coordinator, self._hh_id, self._t_id)

    @property
    def current_option(self) -> str:
        return self._current

    async def async_select_option(self, option: str) -> None:
        self._current = option
        await self.coordinator.client.sort_chapters(self._hh_id, self._t_id, option)
        await self.coordinator.async_request_refresh()
