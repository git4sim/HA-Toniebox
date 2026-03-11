"""Button platform for Toniebox integration."""

from __future__ import annotations
import logging
from dataclasses import dataclass, field

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class TonieboxButtonDescription(ButtonEntityDescription):
    action: str = ""
    action_args: dict = field(default_factory=dict)


TONIE_BUTTONS = [
    TonieboxButtonDescription(key="clear_chapters", name="Clear All Chapters", icon="mdi:delete-sweep", action="clear_chapters"),
    TonieboxButtonDescription(key="sort_by_title", name="Sort by Title", icon="mdi:sort-alphabetical-ascending", action="sort_chapters", action_args={"sort_by": "title"}),
    TonieboxButtonDescription(key="sort_by_filename", name="Sort by Filename", icon="mdi:sort-variant", action="sort_chapters", action_args={"sort_by": "filename"}),
    TonieboxButtonDescription(key="sort_by_date", name="Sort by Date", icon="mdi:sort-calendar-ascending", action="sort_chapters", action_args={"sort_by": "date"}),
    TonieboxButtonDescription(key="refresh", name="Refresh", icon="mdi:refresh", action="refresh"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for hh_id, hh in coordinator.data.get("households", {}).items():
        for t_id in hh.get("creativetonies", {}):
            for desc in TONIE_BUTTONS:
                entities.append(TonieboxButton(coordinator, hh_id, t_id, entry, desc))
    async_add_entities(entities)


class TonieboxButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, household_id: str, tonie_id: str, entry: ConfigEntry, description: TonieboxButtonDescription) -> None:
        super().__init__(coordinator)
        self._household_id = household_id
        self._tonie_id = tonie_id
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{household_id}_{tonie_id}_{description.key}"

    @property
    def _tonie_data(self) -> dict:
        return (self.coordinator.data.get("households", {}).get(self._household_id, {})
                .get("creativetonies", {}).get(self._tonie_id, {}))

    @property
    def name(self) -> str:
        return f"{self._tonie_data.get('name', self._tonie_id)} {self.entity_description.name}"

    async def async_press(self) -> None:
        action = self.entity_description.action
        args = self.entity_description.action_args
        client = self.coordinator.client

        if action == "refresh":
            await self.coordinator.async_request_refresh()
            return
        elif action == "clear_chapters":
            await client.clear_chapters(self._household_id, self._tonie_id)
        elif action == "sort_chapters":
            await client.sort_chapters(self._household_id, self._tonie_id, args.get("sort_by", "title"))

        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        hh = self.coordinator.data.get("households", {}).get(self._household_id, {})
        return {"identifiers": {(DOMAIN, self._household_id)}, "name": hh.get("name", "Toniebox"), "manufacturer": "Boxine GmbH", "model": "Toniebox Cloud"}
