"""Switch platform for Toniebox integration."""
from __future__ import annotations

import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for hh_id, hh in coordinator.data.get("households", {}).items():
        # Toniebox switches
        for tb_id, tb in hh.get("tonieboxes", {}).items():
            tb_name = tb.get("name", tb_id)
            entities.append(TonieboxLEDSwitch(coordinator, hh_id, tb_id, tb_name))
            entities.append(TonieboxSkipMuteSwitch(coordinator, hh_id, tb_id, tb_name))

        # Creative Tonie switches
        for t_id, tonie in hh.get("creativetonies", {}).items():
            t_name = tonie.get("name", t_id)
            entities.append(ToniePrivateSwitch(coordinator, hh_id, t_id, t_name))
            entities.append(TonieLiveSwitch(coordinator, hh_id, t_id, t_name))

    async_add_entities(entities)


# ── Base ──────────────────────────────────────────────────────────────────────

class TonieboxBaseSwitch(CoordinatorEntity, SwitchEntity):
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


class TonieboxLEDSwitch(TonieboxBaseSwitch):
    _attr_icon = "mdi:led-on"

    def __init__(self, coordinator, hh_id, tb_id, tb_name):
        super().__init__(coordinator, hh_id, tb_id, tb_name)
        self._attr_unique_id = f"{tb_id}_led_switch"
        self._attr_name = f"{tb_name} LED"

    @property
    def is_on(self):
        return self._tb.get("led", True)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.client.patch_toniebox(self._hh_id, self._tb_id, {"led": True})
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.client.patch_toniebox(self._hh_id, self._tb_id, {"led": False})
        await self.coordinator.async_request_refresh()


class TonieboxSkipMuteSwitch(TonieboxBaseSwitch):
    _attr_icon = "mdi:volume-off"

    def __init__(self, coordinator, hh_id, tb_id, tb_name):
        super().__init__(coordinator, hh_id, tb_id, tb_name)
        self._attr_unique_id = f"{tb_id}_skip_mute"
        self._attr_name = f"{tb_name} Skip Mute Detection"

    @property
    def is_on(self):
        return self._tb.get("skip_mute_detection", False)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.client.patch_toniebox(self._hh_id, self._tb_id, {"skip_mute_detection": True})
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.client.patch_toniebox(self._hh_id, self._tb_id, {"skip_mute_detection": False})
        await self.coordinator.async_request_refresh()


# ── Creative Tonie switches ───────────────────────────────────────────────────

class TonieTonieSwitchBase(CoordinatorEntity, SwitchEntity):
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


class ToniePrivateSwitch(TonieTonieSwitchBase):
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator, hh_id, t_id, t_name):
        super().__init__(coordinator, hh_id, t_id, t_name)
        self._attr_unique_id = f"{t_id}_private_switch"
        self._attr_name = f"{t_name} Private"

    @property
    def is_on(self):
        return self._tonie.get("private", False)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.client.patch_creative_tonie(self._hh_id, self._t_id, {"private": True})
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.client.patch_creative_tonie(self._hh_id, self._t_id, {"private": False})
        await self.coordinator.async_request_refresh()


class TonieLiveSwitch(TonieTonieSwitchBase):
    _attr_icon = "mdi:broadcast"

    def __init__(self, coordinator, hh_id, t_id, t_name):
        super().__init__(coordinator, hh_id, t_id, t_name)
        self._attr_unique_id = f"{t_id}_live_switch"
        self._attr_name = f"{t_name} Live"

    @property
    def is_on(self):
        return self._tonie.get("live", False)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.client.patch_creative_tonie(self._hh_id, self._t_id, {"live": True})
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.client.patch_creative_tonie(self._hh_id, self._t_id, {"live": False})
        await self.coordinator.async_request_refresh()
