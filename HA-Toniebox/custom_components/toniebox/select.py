"""Select platform for Toniebox integration."""

from __future__ import annotations
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SORT_OPTIONS, SORT_BY_TITLE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for hh_id, hh in coordinator.data.get("households", {}).items():
        for t_id in hh.get("creativetonies", {}):
            entities.append(TonieboxSortSelect(coordinator, hh_id, t_id, entry))
    async_add_entities(entities)


class TonieboxSortSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True
    _attr_options = SORT_OPTIONS
    _attr_icon = "mdi:sort"

    def __init__(self, coordinator, household_id: str, tonie_id: str, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._household_id = household_id
        self._tonie_id = tonie_id
        self._entry = entry
        self._current_option = SORT_BY_TITLE
        self._attr_unique_id = f"{entry.entry_id}_{household_id}_{tonie_id}_sort_select"

    @property
    def _tonie_data(self) -> dict:
        return (self.coordinator.data.get("households", {}).get(self._household_id, {})
                .get("creativetonies", {}).get(self._tonie_id, {}))

    @property
    def name(self) -> str:
        return f"{self._tonie_data.get('name', self._tonie_id)} Sort Chapters"

    @property
    def current_option(self) -> str:
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        self._current_option = option
        await self.coordinator.client.sort_chapters(self._household_id, self._tonie_id, option)
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        hh = self.coordinator.data.get("households", {}).get(self._household_id, {})
        return {"identifiers": {(DOMAIN, self._household_id)}, "name": hh.get("name", "Toniebox"), "manufacturer": "Boxine GmbH", "model": "Toniebox Cloud"}
