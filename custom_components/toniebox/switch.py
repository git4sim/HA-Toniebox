"""Switch platform — Toniebox settings switches + Tonie property switches."""
from __future__ import annotations

import logging
from homeassistant.core import callback
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .content_tonie import ContentTonieLockSwitch, DiscLockSwitch
from .device_info import toniebox_device_info, creative_tonie_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = []

    for hh_id, hh in coordinator.data.get("households", {}).items():
        for tb_id, tb in hh.get("tonieboxes", {}).items():
            features = tb.get("features", [])
            is_tng = "tngSettings" in features

            # Always available
            entities += [
                TonieboxSkippingSwitch(coordinator, hh_id, tb_id),
                TonieboxScrubbingSwitch(coordinator, hh_id, tb_id),
                TonieboxOfflineModeSwitch(coordinator, hh_id, tb_id),
            ]
            # Older boxes only (no tngSettings feature)
            if not is_tng:
                entities.append(TonieboxAccelerometerSwitch(coordinator, hh_id, tb_id))

        for t_id in hh.get("creativetonies", {}):
            entities += [
                ToniePrivateSwitch(coordinator, hh_id, t_id),
                TonieLiveSwitch(coordinator, hh_id, t_id),
            ]

    # ── Content Tonie switches ────────────────────────────────────────────────
    for hh_id, hh in coordinator.data.get("households", {}).items():
        for ct_id in hh.get("contenttonies", {}):
            entities.append(ContentTonieLockSwitch(coordinator, hh_id, ct_id))
        for disc_id in hh.get("discs", {}):
            entities.append(DiscLockSwitch(coordinator, hh_id, disc_id))

    async_add_entities(entities)


# ── Base helpers ──────────────────────────────────────────────────────────────

class _TbSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, hh_id: str, tb_id: str) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._tb_id = tb_id
        self._optimistic_state: bool | None = None

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

    @callback
    def _handle_coordinator_update(self) -> None:
        self._optimistic_state = None
        super()._handle_coordinator_update()

    async def _patch(self, payload: dict) -> None:
        await self.coordinator.client.patch_toniebox(self._hh_id, self._tb_id, payload)
        await self.coordinator.async_request_refresh()

    def _optimistic_toggle(self, new_state: bool) -> None:
        self._optimistic_state = new_state
        self.async_write_ha_state()


# ── Toniebox switches ─────────────────────────────────────────────────────────

class TonieboxSkippingSwitch(_TbSwitch):
    """Whether tapping the box skips chapters."""
    _attr_icon = "mdi:skip-next"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_skipping"
        self._attr_name = "Kapitel überspringen"

    @property
    def is_on(self) -> bool:
        if self._optimistic_state is not None:
            return self._optimistic_state
        # API default: enabled
        val = self._tb.get("skipping_enabled")
        return val if val is not None else True

    async def async_turn_on(self, **kw):
        self._optimistic_toggle(True)
        await self._patch({"skippingEnabled": True})

    async def async_turn_off(self, **kw):
        self._optimistic_toggle(False)
        await self._patch({"skippingEnabled": False})


class TonieboxScrubbingSwitch(_TbSwitch):
    """Whether tilting the box fast-forwards / rewinds."""
    _attr_icon = "mdi:fast-forward"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_scrubbing"
        self._attr_name = "Vorspulen / Zurückspulen"

    @property
    def is_on(self) -> bool:
        if self._optimistic_state is not None:
            return self._optimistic_state
        val = self._tb.get("scrubbing_enabled")
        return val if val is not None else True

    async def async_turn_on(self, **kw):
        self._optimistic_toggle(True)
        await self._patch({"scrubbingEnabled": True})

    async def async_turn_off(self, **kw):
        self._optimistic_toggle(False)
        await self._patch({"scrubbingEnabled": False})


class TonieboxOfflineModeSwitch(_TbSwitch):
    """Whether the box is running in offline mode (no cloud contact)."""
    _attr_icon = "mdi:cloud-off-outline"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_offline_mode"
        self._attr_name = "Offline-Modus"

    @property
    def is_on(self) -> bool:
        if self._optimistic_state is not None:
            return self._optimistic_state
        return self._tb.get("offline_mode", False)

    # offlineMode is read-only in the API — switch is display-only
    @property
    def available(self) -> bool:
        return True

    async def async_turn_on(self, **kw):
        _LOGGER.warning("offlineMode is read-only via REST API and cannot be changed here.")

    async def async_turn_off(self, **kw):
        _LOGGER.warning("offlineMode is read-only via REST API and cannot be changed here.")


class TonieboxAccelerometerSwitch(_TbSwitch):
    """Tilting & tapping enabled (older boxes without tngSettings only)."""
    _attr_icon = "mdi:axis-arrow"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_accelerometer"
        self._attr_name = "Kippen & Klopfen"

    @property
    def is_on(self) -> bool:
        if self._optimistic_state is not None:
            return self._optimistic_state
        val = self._tb.get("accelerometer_enabled")
        return val if val is not None else True

    async def async_turn_on(self, **kw):
        self._optimistic_toggle(True)
        await self._patch({"accelerometerEnabled": True})

    async def async_turn_off(self, **kw):
        self._optimistic_toggle(False)
        await self._patch({"accelerometerEnabled": False})


# ── Creative Tonie switches ───────────────────────────────────────────────────

class _TonieSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, hh_id: str, t_id: str) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._t_id = t_id
        self._optimistic_state: bool | None = None

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

    @callback
    def _handle_coordinator_update(self) -> None:
        self._optimistic_state = None
        super()._handle_coordinator_update()

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
        if self._optimistic_state is not None:
            return self._optimistic_state
        return self._tonie.get("private", False)

    async def async_turn_on(self, **kw):
        self._optimistic_state = True
        self.async_write_ha_state()
        await self._patch({"private": True})

    async def async_turn_off(self, **kw):
        self._optimistic_state = False
        self.async_write_ha_state()
        await self._patch({"private": False})


class TonieLiveSwitch(_TonieSwitch):
    _attr_icon = "mdi:broadcast"

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_live"
        self._attr_name = "Live"

    @property
    def is_on(self) -> bool:
        if self._optimistic_state is not None:
            return self._optimistic_state
        return self._tonie.get("live", False)

    async def async_turn_on(self, **kw):
        self._optimistic_state = True
        self.async_write_ha_state()
        await self._patch({"live": True})

    async def async_turn_off(self, **kw):
        self._optimistic_state = False
        self.async_write_ha_state()
        await self._patch({"live": False})
