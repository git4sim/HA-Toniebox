"""Sensor platform for Toniebox integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ATTR_HOUSEHOLD_ID, ATTR_TONIE_ID

_LOGGER = logging.getLogger(__name__)

CHAPTER_COUNT_DESCRIPTION = SensorEntityDescription(
    key="chapter_count",
    name="Chapter Count",
    icon="mdi:music-box-multiple",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="chapters",
)

TOTAL_DURATION_DESCRIPTION = SensorEntityDescription(
    key="total_duration",
    name="Total Duration",
    icon="mdi:clock-outline",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="min",
)

HOUSEHOLD_TONIE_COUNT_DESCRIPTION = SensorEntityDescription(
    key="tonie_count",
    name="Creative Tonies",
    icon="mdi:bear",
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement="tonies",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Toniebox sensor entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for household_id, household in coordinator.data.get("households", {}).items():
        # Per-household sensor
        entities.append(
            TonieboxHouseholdSensor(
                coordinator=coordinator,
                household_id=household_id,
                entry=entry,
                description=HOUSEHOLD_TONIE_COUNT_DESCRIPTION,
            )
        )

        # Per-creative-tonie sensors
        for tonie_id, tonie in household.get("creativetonies", {}).items():
            entities.append(
                TonieboxChapterCountSensor(
                    coordinator=coordinator,
                    household_id=household_id,
                    tonie_id=tonie_id,
                    entry=entry,
                    description=CHAPTER_COUNT_DESCRIPTION,
                )
            )
            entities.append(
                TonieboxTotalDurationSensor(
                    coordinator=coordinator,
                    household_id=household_id,
                    tonie_id=tonie_id,
                    entry=entry,
                    description=TOTAL_DURATION_DESCRIPTION,
                )
            )

    async_add_entities(entities, update_before_add=True)


class TonieboxHouseholdSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the number of creative tonies in a household."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        household_id: str,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._household_id = household_id
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{household_id}_{description.key}"

    @property
    def _household_data(self) -> dict:
        return (
            self.coordinator.data.get("households", {}).get(self._household_id, {})
        )

    @property
    def native_value(self) -> int:
        """Return number of creative tonies."""
        return len(self._household_data.get("creativetonies", {}))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return list of creative tonie names."""
        creativetonies = self._household_data.get("creativetonies", {})
        return {
            "tonie_names": [t.get("name", tid) for tid, t in creativetonies.items()],
            ATTR_HOUSEHOLD_ID: self._household_id,
        }

    @property
    def device_info(self):
        """Return device info."""
        household = self._household_data
        return {
            "identifiers": {(DOMAIN, self._household_id)},
            "name": household.get("name", f"Toniebox Household {self._household_id[:8]}"),
            "manufacturer": "Boxine GmbH",
            "model": "Toniebox Cloud",
        }


class TonieboxChapterCountSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the number of chapters on a creative tonie."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        household_id: str,
        tonie_id: str,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._household_id = household_id
        self._tonie_id = tonie_id
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{household_id}_{tonie_id}_{description.key}"

    @property
    def _tonie_data(self) -> dict:
        return (
            self.coordinator.data
            .get("households", {})
            .get(self._household_id, {})
            .get("creativetonies", {})
            .get(self._tonie_id, {})
        )

    @property
    def name(self) -> str:
        tonie_name = self._tonie_data.get("name", self._tonie_id)
        return f"{tonie_name} Chapter Count"

    @property
    def native_value(self) -> int:
        return self._tonie_data.get("chapter_count", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        chapters = self._tonie_data.get("chapters", [])
        return {
            ATTR_HOUSEHOLD_ID: self._household_id,
            ATTR_TONIE_ID: self._tonie_id,
            "chapter_titles": [ch.get("title", "") for ch in chapters],
        }

    @property
    def device_info(self):
        household = self.coordinator.data.get("households", {}).get(self._household_id, {})
        return {
            "identifiers": {(DOMAIN, self._household_id)},
            "name": household.get("name", f"Toniebox Household {self._household_id[:8]}"),
            "manufacturer": "Boxine GmbH",
            "model": "Toniebox Cloud",
        }


class TonieboxTotalDurationSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the total audio duration on a creative tonie."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        household_id: str,
        tonie_id: str,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._household_id = household_id
        self._tonie_id = tonie_id
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{household_id}_{tonie_id}_{description.key}"

    @property
    def _tonie_data(self) -> dict:
        return (
            self.coordinator.data
            .get("households", {})
            .get(self._household_id, {})
            .get("creativetonies", {})
            .get(self._tonie_id, {})
        )

    @property
    def name(self) -> str:
        tonie_name = self._tonie_data.get("name", self._tonie_id)
        return f"{tonie_name} Total Duration"

    @property
    def native_value(self) -> float:
        """Return total duration in minutes (rounded to 1 decimal)."""
        chapters = self._tonie_data.get("chapters", [])
        total_seconds = sum(ch.get("seconds", 0) for ch in chapters)
        return round(total_seconds / 60, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        chapters = self._tonie_data.get("chapters", [])
        total_seconds = sum(ch.get("seconds", 0) for ch in chapters)
        return {
            ATTR_HOUSEHOLD_ID: self._household_id,
            ATTR_TONIE_ID: self._tonie_id,
            "total_seconds": total_seconds,
        }

    @property
    def device_info(self):
        household = self.coordinator.data.get("households", {}).get(self._household_id, {})
        return {
            "identifiers": {(DOMAIN, self._household_id)},
            "name": household.get("name", f"Toniebox Household {self._household_id[:8]}"),
            "manufacturer": "Boxine GmbH",
            "model": "Toniebox Cloud",
        }
