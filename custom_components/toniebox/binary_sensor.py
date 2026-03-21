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
        for tb_id, tb in hh.get("tonieboxes", {}).items():
            entities += [
                TonieboxOnlineSensor(coordinator, hh_id, tb_id),
                TonieboxLEDSensor(coordinator, hh_id, tb_id),
            ]
            # Charging sensor — TNG boxes only (via ICI real-time push)
            if tb.get("generation") == "tng":
                entities.append(TonieboxChargingSensor(coordinator, hh_id, tb_id))
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
    """Binary sensor that reflects the Toniebox online state.

    For TNG boxes with ICI, online_state is updated in real-time via MQTT push.
    For classic boxes, falls back to last_seen timestamp comparison.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:wifi"

    _attr_translation_key = "online"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_online"

    @property
    def is_on(self) -> bool:
        # ICI provides reliable real-time state for TNG boxes
        online_state = self._tb.get("online_state")
        if online_state in ("connected", "offline"):
            return online_state == "connected"

        # Fallback: last_seen timestamp for classic boxes or when ICI is unavailable
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
    _attr_translation_key = "led_active"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_led_binary"

    @property
    def is_on(self) -> bool:
        return self._tb.get("led", True)


class TonieboxChargingSensor(_TbBin):
    """Whether a TNG Toniebox is currently charging (via ICI real-time push)."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_icon = "mdi:battery-charging"
    _attr_translation_key = "charging"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_charging"

    @property
    def is_on(self) -> bool | None:
        battery = self._tb.get("battery")
        if isinstance(battery, dict):
            return battery.get("status") == "charging"
        return None


