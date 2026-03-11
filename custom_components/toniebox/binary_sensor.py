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
from .device_info import toniebox_device_info, creative_tonie_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = []

    for hh_id, hh in coordinator.data.get("households", {}).items():
        for tb_id in hh.get("tonieboxes", {}):
            entities += [
                TonieboxOnlineSensor(coordinator, hh_id, tb_id),
                TonieboxLEDSensor(coordinator, hh_id, tb_id),
            ]
        for t_id in hh.get("creativetonies", {}):
            entities += [
                TonieTranscodingSensor(coordinator, hh_id, t_id),
                TonieLiveSensor(coordinator, hh_id, t_id),
                ToniePrivateSensor(coordinator, hh_id, t_id),
            ]

    async_add_entities(entities)


# ── Toniebox binary sensors ───────────────────────────────────────────────────

class _TbBin(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._tb_id = tb_id

    @property
    def _tb(self) -> dict:
        return (
            self.coordinator.data
            .get("households", {}).get(self._hh_id, {})
            .get("tonieboxes", {}).get(self._tb_id, {})
        )

    @property
    def device_info(self) -> dict:
        return toniebox_device_info(self.coordinator, self._hh_id, self._tb_id)


class TonieboxOnlineSensor(_TbBin):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:wifi"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_online"
        self._attr_name = "Online"

    @property
    def is_on(self) -> bool:
        return bool(
            self._tb.get("placement", {}).get("tonie")
            or self._tb.get("last_seen")
        )


class TonieboxLEDSensor(_TbBin):
    _attr_icon = "mdi:led-on"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_led_binary"
        self._attr_name = "LED aktiv"

    @property
    def is_on(self) -> bool:
        return self._tb.get("led", True)


# ── Creative Tonie binary sensors ─────────────────────────────────────────────

class _TonieBin(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._t_id = t_id

    @property
    def _tonie(self) -> dict:
        return (
            self.coordinator.data
            .get("households", {}).get(self._hh_id, {})
            .get("creativetonies", {}).get(self._t_id, {})
        )

    @property
    def device_info(self) -> dict:
        return creative_tonie_device_info(self.coordinator, self._hh_id, self._t_id)


class TonieTranscodingSensor(_TonieBin):
    _attr_icon = "mdi:cog-sync"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_transcoding"
        self._attr_name = "Wird verarbeitet"

    @property
    def is_on(self) -> bool:
        return self._tonie.get("transcoding", False)


class TonieLiveSensor(_TonieBin):
    _attr_icon = "mdi:broadcast"

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_live_binary"
        self._attr_name = "Live"

    @property
    def is_on(self) -> bool:
        return self._tonie.get("live", False)


class ToniePrivateSensor(_TonieBin):
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_private_binary"
        self._attr_name = "Privat"

    @property
    def is_on(self) -> bool:
        return self._tonie.get("private", False)
