"""Binary sensor platform for Toniebox integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for hh_id, hh in coordinator.data.get("households", {}).items():
        hh_name = hh.get("name", hh_id)

        # Toniebox binary sensors
        for tb_id, tb in hh.get("tonieboxes", {}).items():
            tb_name = tb.get("name", tb_id)
            entities.append(TonieboxOnlineSensor(coordinator, hh_id, tb_id, tb_name))
            entities.append(TonieboxLEDSensor(coordinator, hh_id, tb_id, tb_name))

        # Creative Tonie binary sensors
        for t_id, tonie in hh.get("creativetonies", {}).items():
            t_name = tonie.get("name", t_id)
            entities.append(TonieTranscodingSensor(coordinator, hh_id, t_id, t_name))
            entities.append(TonieLiveSensor(coordinator, hh_id, t_id, t_name))
            entities.append(ToniePrivateSensor(coordinator, hh_id, t_id, t_name))

    async_add_entities(entities)


class TonieboxBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, hh_id, tb_id, tb_name):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._tb_id = tb_id
        self._tb_name = tb_name

    @property
    def _tb(self):
        return self.coordinator.data.get("households", {}).get(self._hh_id, {}).get("tonieboxes", {}).get(self._tb_id, {})

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._tb_id)},
            "name": self._tb_name,
            "manufacturer": "Boxine GmbH",
            "model": "Toniebox",
            "via_device": (DOMAIN, self._hh_id),
        }


class TonieboxOnlineSensor(TonieboxBaseBinarySensor):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:wifi"

    def __init__(self, coordinator, hh_id, tb_id, tb_name):
        super().__init__(coordinator, hh_id, tb_id, tb_name)
        self._attr_unique_id = f"{tb_id}_online"
        self._attr_name = f"{tb_name} Online"

    @property
    def is_on(self):
        # Toniebox is "online" if last_seen is recent or placement has active tonie
        placement = self._tb.get("placement", {})
        return bool(placement.get("tonie") or self._tb.get("last_seen"))


class TonieboxLEDSensor(TonieboxBaseBinarySensor):
    _attr_icon = "mdi:led-on"

    def __init__(self, coordinator, hh_id, tb_id, tb_name):
        super().__init__(coordinator, hh_id, tb_id, tb_name)
        self._attr_unique_id = f"{tb_id}_led"
        self._attr_name = f"{tb_name} LED"

    @property
    def is_on(self):
        return self._tb.get("led", True)


class TonieTonieBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, hh_id, t_id, t_name):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._t_id = t_id
        self._t_name = t_name

    @property
    def _tonie(self):
        return self.coordinator.data.get("households", {}).get(self._hh_id, {}).get("creativetonies", {}).get(self._t_id, {})

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._t_id)},
            "name": self._t_name,
            "manufacturer": "Boxine GmbH",
            "model": "Creative Tonie",
            "via_device": (DOMAIN, self._hh_id),
        }


class TonieTranscodingSensor(TonieTonieBinarySensor):
    _attr_icon = "mdi:cog-sync"

    def __init__(self, coordinator, hh_id, t_id, t_name):
        super().__init__(coordinator, hh_id, t_id, t_name)
        self._attr_unique_id = f"{t_id}_transcoding"
        self._attr_name = f"{t_name} Transcoding"

    @property
    def is_on(self):
        return self._tonie.get("transcoding", False)


class TonieLiveSensor(TonieTonieBinarySensor):
    _attr_icon = "mdi:broadcast"

    def __init__(self, coordinator, hh_id, t_id, t_name):
        super().__init__(coordinator, hh_id, t_id, t_name)
        self._attr_unique_id = f"{t_id}_live"
        self._attr_name = f"{t_name} Live"

    @property
    def is_on(self):
        return self._tonie.get("live", False)


class ToniePrivateSensor(TonieTonieBinarySensor):
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator, hh_id, t_id, t_name):
        super().__init__(coordinator, hh_id, t_id, t_name)
        self._attr_unique_id = f"{t_id}_private"
        self._attr_name = f"{t_name} Private"

    @property
    def is_on(self):
        return self._tonie.get("private", False)
