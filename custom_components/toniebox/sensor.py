"""Sensor platform for Toniebox integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device_info import (
    household_device_info,
    toniebox_device_info,
    creative_tonie_device_info,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = []

    # ── Household-level sensors (appear on Hub device) ────────────────────────
    for hh_id, hh in coordinator.data.get("households", {}).items():
        entities += [
            HouseholdSensor(coordinator, hh_id, "account",     "Account",              "mdi:account",       lambda d: d.get("me", {}).get("email", "unbekannt")),
            HouseholdCountSensor(coordinator, hh_id, "tonies",      "Creative Tonies",      "mdi:teddy-bear",    "creativetonies"),
            HouseholdCountSensor(coordinator, hh_id, "tonieboxes",  "Tonieboxen",           "mdi:speaker",       "tonieboxes"),
            HouseholdCountSensor(coordinator, hh_id, "children",    "Kinder",               "mdi:account-child", "children"),
            HouseholdCountSensor(coordinator, hh_id, "members",     "Mitglieder",           "mdi:account-group", "memberships"),
            HouseholdNotifSensor(coordinator, hh_id),
            HouseholdInviteSensor(coordinator, hh_id),
        ]

        # ── Toniebox sensors ──────────────────────────────────────────────────
        for tb_id, tb in hh.get("tonieboxes", {}).items():
            tb_name = tb.get("name", tb_id)
            entities += [
                TonieboxFirmwareSensor(coordinator, hh_id, tb_id, tb_name),
                TonieboxLastSeenSensor(coordinator, hh_id, tb_id, tb_name),
            ]

        # ── Creative Tonie sensors ────────────────────────────────────────────
        for t_id, tonie in hh.get("creativetonies", {}).items():
            t_name = tonie.get("name", t_id)
            entities += [
                TonieChapterCountSensor(coordinator, hh_id, t_id, t_name),
                TonieDurationSensor(coordinator, hh_id, t_id, t_name),
            ]

    async_add_entities(entities)


# ── Base ──────────────────────────────────────────────────────────────────────

class _Base(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)

    @property
    def _data(self):
        return self.coordinator.data


# ── Household sensors (on Hub device) ─────────────────────────────────────────

class HouseholdSensor(_Base):
    _attr_has_entity_name = True

    def __init__(self, coordinator, hh_id, key, name, icon, value_fn):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._value_fn = value_fn
        self._attr_unique_id = f"hh_{hh_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon

    @property
    def device_info(self):
        return household_device_info(self.coordinator, self._hh_id)

    @property
    def native_value(self):
        return self._value_fn(self._data)


class HouseholdCountSensor(_Base):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, hh_id, key, name, icon, data_key):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._data_key = data_key
        self._attr_unique_id = f"hh_{hh_id}_{key}_count"
        self._attr_name = name
        self._attr_icon = icon

    @property
    def _hh(self):
        return self._data.get("households", {}).get(self._hh_id, {})

    @property
    def device_info(self):
        return household_device_info(self.coordinator, self._hh_id)

    @property
    def native_value(self):
        val = self._hh.get(self._data_key, {})
        return len(val) if isinstance(val, (dict, list)) else 0


class HouseholdNotifSensor(_Base):
    _attr_has_entity_name = True
    _attr_icon = "mdi:bell"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, hh_id):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._attr_unique_id = f"hh_{hh_id}_notifications"
        self._attr_name = "Benachrichtigungen"

    @property
    def device_info(self):
        return household_device_info(self.coordinator, self._hh_id)

    @property
    def native_value(self):
        return len(self._data.get("notifications", []))

    @property
    def extra_state_attributes(self):
        return {"notifications": self._data.get("notifications", [])}


class HouseholdInviteSensor(_Base):
    _attr_has_entity_name = True
    _attr_icon = "mdi:email-plus"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, hh_id):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._attr_unique_id = f"hh_{hh_id}_invitations"
        self._attr_name = "Offene Einladungen"

    @property
    def device_info(self):
        return household_device_info(self.coordinator, self._hh_id)

    @property
    def native_value(self):
        return len(self._data.get("invitations", []))


# ── Toniebox sensors ──────────────────────────────────────────────────────────

class _TbBase(_Base):
    def __init__(self, coordinator, hh_id, tb_id, tb_name):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._tb_id = tb_id
        self._tb_name = tb_name

    @property
    def _tb(self):
        return self._data.get("households", {}).get(self._hh_id, {}).get("tonieboxes", {}).get(self._tb_id, {})

    @property
    def device_info(self):
        return toniebox_device_info(self.coordinator, self._hh_id, self._tb_id)


class TonieboxFirmwareSensor(_TbBase):
    _attr_has_entity_name = True
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator, hh_id, tb_id, tb_name):
        super().__init__(coordinator, hh_id, tb_id, tb_name)
        self._attr_unique_id = f"tb_{tb_id}_firmware"
        self._attr_name = "Firmware"

    @property
    def native_value(self):
        fw = self._tb.get("firmware", {})
        return fw.get("version") or fw.get("toniesVersion") or "unbekannt"

    @property
    def extra_state_attributes(self):
        return {"firmware_details": self._tb.get("firmware", {})}


class TonieboxLastSeenSensor(_TbBase):
    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, hh_id, tb_id, tb_name):
        super().__init__(coordinator, hh_id, tb_id, tb_name)
        self._attr_unique_id = f"tb_{tb_id}_last_seen"
        self._attr_name = "Zuletzt gesehen"

    @property
    def native_value(self):
        return self._tb.get("last_seen")


# ── Creative Tonie sensors ────────────────────────────────────────────────────

class _TonieBase(_Base):
    def __init__(self, coordinator, hh_id, t_id, t_name):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._t_id = t_id
        self._t_name = t_name

    @property
    def _tonie(self):
        return self._data.get("households", {}).get(self._hh_id, {}).get("creativetonies", {}).get(self._t_id, {})

    @property
    def device_info(self):
        return creative_tonie_device_info(self.coordinator, self._hh_id, self._t_id)


class TonieChapterCountSensor(_TonieBase):
    _attr_has_entity_name = True
    _attr_icon = "mdi:format-list-numbered"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, hh_id, t_id, t_name):
        super().__init__(coordinator, hh_id, t_id, t_name)
        self._attr_unique_id = f"ct_{t_id}_chapter_count"
        self._attr_name = "Kapitel"

    @property
    def native_value(self):
        return self._tonie.get("chapter_count", 0)

    @property
    def extra_state_attributes(self):
        return {
            "chapters": [
                {"title": c["title"], "seconds": c["seconds"], "transcoding": c["transcoding"]}
                for c in self._tonie.get("chapters", [])
            ]
        }


class TonieDurationSensor(_TonieBase):
    _attr_has_entity_name = True
    _attr_icon = "mdi:timer-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator, hh_id, t_id, t_name):
        super().__init__(coordinator, hh_id, t_id, t_name)
        self._attr_unique_id = f"ct_{t_id}_duration"
        self._attr_name = "Gesamtdauer"

    @property
    def native_value(self):
        return round(self._tonie.get("total_seconds", 0) / 60, 1)
