"""Switch platform — Toniebox hardware switches + Tonie property switches."""
from __future__ import annotations

import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device_info import toniebox_device_info, creative_tonie_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = []

    for hh_id, hh in coordinator.data.get("households", {}).items():
        # Toniebox switches → appear ON the Toniebox device
        for tb_id in hh.get("tonieboxes", {}):
            entities += [
                TonieboxLEDSwitch(coordinator, hh_id, tb_id),
                TonieboxMuteSwitch(coordinator, hh_id, tb_id),
            ]
        # Creative Tonie switches → appear ON the Tonie device
        for t_id in hh.get("creativetonies", {}):
            entities += [
                ToniePrivateSwitch(coordinator, hh_id, t_id),
                TonieLiveSwitch(coordinator, hh_id, t_id),
            ]

    async_add_entities(entities)


# ── Toniebox switches ─────────────────────────────────────────────────────────

class _TbSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, hh_id: str, tb_id: str) -> None:
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

    async def _patch(self, payload: dict) -> None:
        await self.coordinator.client.patch_toniebox(self._hh_id, self._tb_id, payload)
        await self.coordinator.async_request_refresh()


class TonieboxLEDSwitch(_TbSwitch):
    _attr_icon = "mdi:led-on"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_led"
        self._attr_name = "LED"

    @property
    def is_on(self) -> bool:
        return self._tb.get("led", True)

    async def async_turn_on(self, **kw):
        await self._patch({"led": True})

    async def async_turn_off(self, **kw):
        await self._patch({"led": False})


class TonieboxMuteSwitch(_TbSwitch):
    _attr_icon = "mdi:volume-mute"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_skip_mute"
        self._attr_name = "Lautstärke-Kabel ignorieren"

    @property
    def is_on(self) -> bool:
        return self._tb.get("skip_mute_detection", False)

    async def async_turn_on(self, **kw):
        await self._patch({"skip_mute_detection": True})

    async def async_turn_off(self, **kw):
        await self._patch({"skip_mute_detection": False})


# ── Creative Tonie switches ───────────────────────────────────────────────────

class _TonieSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, hh_id: str, t_id: str) -> None:
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

    async def _patch(self, payload: dict) -> None:
        await self.coordinator.client.patch_creative_tonie(self._hh_id, self._t_id, payload)
        await self.coordinator.async_request_refresh()


class ToniePrivateSwitch(_TonieSwitch):
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_private"
        self._attr_name = "Privat"

    @property
    def is_on(self) -> bool:
        return self._tonie.get("private", False)

    async def async_turn_on(self, **kw):
        await self._patch({"private": True})

    async def async_turn_off(self, **kw):
        await self._patch({"private": False})


class TonieLiveSwitch(_TonieSwitch):
    _attr_icon = "mdi:broadcast"

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_live"
        self._attr_name = "Live"

    @property
    def is_on(self) -> bool:
        return self._tonie.get("live", False)

    async def async_turn_on(self, **kw):
        await self._patch({"live": True})

    async def async_turn_off(self, **kw):
        await self._patch({"live": False})
