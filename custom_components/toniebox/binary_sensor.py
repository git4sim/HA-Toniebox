"""Binary sensor platform for Toniebox integration."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, TONIEBOX_ONLINE_TIMEOUT_MINUTES
from .content_tonie import (
    ContentTonieActiveBinarySensor,
    ContentTonieLockBinarySensor,
    ContentTonieTranscodingBinarySensor,
    DiscActiveBinarySensor,
    DiscLockBinarySensor,
)
from .device_info import toniebox_device_info


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
    # ── Content Tonie binary sensors ─────────────────────────────────────────
    for hh_id, hh in coordinator.data.get("households", {}).items():
        for ct_id in hh.get("contenttonies", {}):
            entities += [
                ContentTonieActiveBinarySensor(coordinator, hh_id, ct_id),
                ContentTonieLockBinarySensor(coordinator, hh_id, ct_id),
                ContentTonieTranscodingBinarySensor(coordinator, hh_id, ct_id),
            ]
        for disc_id in hh.get("discs", {}):
            entities += [
                DiscActiveBinarySensor(coordinator, hh_id, disc_id),
                DiscLockBinarySensor(coordinator, hh_id, disc_id),
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
    """Binary sensor that is True only when the Toniebox has been seen recently.

    Uses TONIEBOX_ONLINE_TIMEOUT_MINUTES to determine staleness. This prevents
    a box that has been offline for weeks from still showing as 'Online'.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:wifi"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_online"
        self._attr_name = "Online"

    @property
    def is_on(self) -> bool:
        last_seen = self._tb.get("last_seen")
        if not last_seen:
            return False
        try:
            if isinstance(last_seen, (int, float)):
                ts = datetime.fromtimestamp(last_seen, tz=timezone.utc)
            else:
                ts = datetime.fromisoformat(str(last_seen))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            cutoff = datetime.now(timezone.utc) - timedelta(
                minutes=TONIEBOX_ONLINE_TIMEOUT_MINUTES
            )
            return ts > cutoff
        except (ValueError, TypeError, OSError):
            return False


class TonieboxLEDSensor(_TbBin):
    _attr_icon = "mdi:led-on"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_led_binary"
        self._attr_name = "LED aktiv"

    @property
    def is_on(self) -> bool:
        return self._tb.get("led", True)


