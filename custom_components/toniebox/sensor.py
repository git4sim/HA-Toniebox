"""Sensor platform for Toniebox integration."""
from __future__ import annotations

import logging
from homeassistant.components.sensor import SensorEntity, SensorStateClass
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

    # User sensors
    entities.append(TonieNotificationCountSensor(coordinator))
    entities.append(TonieUserEmailSensor(coordinator))
    entities.append(ToniePendingInvitationsSensor(coordinator))

    for hh_id, hh in coordinator.data.get("households", {}).items():
        hh_name = hh.get("name", hh_id)

        # Per-household
        entities.append(TonieCreativeToniCountSensor(coordinator, hh_id, hh_name))
        entities.append(TonieTonieboxCountSensor(coordinator, hh_id, hh_name))
        entities.append(TonieChildrenCountSensor(coordinator, hh_id, hh_name))
        entities.append(TonieMembershipCountSensor(coordinator, hh_id, hh_name))

        # Per Toniebox
        for tb_id, tb in hh.get("tonieboxes", {}).items():
            entities.append(TonieboxFirmwareSensor(coordinator, hh_id, tb_id, tb.get("name", tb_id)))
            entities.append(TonieboxLastSeenSensor(coordinator, hh_id, tb_id, tb.get("name", tb_id)))

        # Per Creative Tonie
        for t_id, tonie in hh.get("creativetonies", {}).items():
            t_name = tonie.get("name", t_id)
            entities.append(TonieChapterCountSensor(coordinator, hh_id, t_id, t_name))
            entities.append(TonieTotalDurationSensor(coordinator, hh_id, t_id, t_name))

    async_add_entities(entities)


# ── Base ──────────────────────────────────────────────────────────────────────

class TonieBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)

    @property
    def _data(self):
        return self.coordinator.data


# ── Global sensors ────────────────────────────────────────────────────────────

class TonieNotificationCountSensor(TonieBaseSensor):
    _attr_icon = "mdi:bell"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_notification_count"
        self._attr_name = "Toniebox Notifications"

    @property
    def native_value(self):
        return len(self._data.get("notifications", []))

    @property
    def extra_state_attributes(self):
        return {"notifications": self._data.get("notifications", [])}


class TonieUserEmailSensor(TonieBaseSensor):
    _attr_icon = "mdi:account"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_user_email"
        self._attr_name = "Toniebox Account"

    @property
    def native_value(self):
        return self._data.get("me", {}).get("email", "unknown")

    @property
    def extra_state_attributes(self):
        me = self._data.get("me", {})
        return {
            "locale": me.get("locale"),
            "newsletter": me.get("newsletter"),
        }


class ToniePendingInvitationsSensor(TonieBaseSensor):
    _attr_icon = "mdi:email-plus"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pending_invitations"
        self._attr_name = "Toniebox Pending Invitations"

    @property
    def native_value(self):
        return len(self._data.get("invitations", []))

    @property
    def extra_state_attributes(self):
        return {"invitations": self._data.get("invitations", [])}


# ── Household sensors ─────────────────────────────────────────────────────────

class TonieHouseholdBaseSensor(TonieBaseSensor):
    def __init__(self, coordinator, hh_id, hh_name):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._hh_name = hh_name

    @property
    def _hh(self):
        return self._data.get("households", {}).get(self._hh_id, {})

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._hh_id)},
            "name": self._hh_name,
            "manufacturer": "Boxine GmbH",
            "model": "Household",
        }


class TonieCreativeToniCountSensor(TonieHouseholdBaseSensor):
    _attr_icon = "mdi:teddy-bear"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, hh_id, hh_name):
        super().__init__(coordinator, hh_id, hh_name)
        self._attr_unique_id = f"{hh_id}_creative_tonie_count"
        self._attr_name = f"{hh_name} Creative Tonies"

    @property
    def native_value(self):
        return len(self._hh.get("creativetonies", {}))


class TonieTonieboxCountSensor(TonieHouseholdBaseSensor):
    _attr_icon = "mdi:speaker"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, hh_id, hh_name):
        super().__init__(coordinator, hh_id, hh_name)
        self._attr_unique_id = f"{hh_id}_toniebox_count"
        self._attr_name = f"{hh_name} Tonieboxes"

    @property
    def native_value(self):
        return len(self._hh.get("tonieboxes", {}))


class TonieChildrenCountSensor(TonieHouseholdBaseSensor):
    _attr_icon = "mdi:account-child"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, hh_id, hh_name):
        super().__init__(coordinator, hh_id, hh_name)
        self._attr_unique_id = f"{hh_id}_children_count"
        self._attr_name = f"{hh_name} Children"

    @property
    def native_value(self):
        return len(self._hh.get("children", []))

    @property
    def extra_state_attributes(self):
        return {"children": self._hh.get("children", [])}


class TonieMembershipCountSensor(TonieHouseholdBaseSensor):
    _attr_icon = "mdi:account-group"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, hh_id, hh_name):
        super().__init__(coordinator, hh_id, hh_name)
        self._attr_unique_id = f"{hh_id}_membership_count"
        self._attr_name = f"{hh_name} Members"

    @property
    def native_value(self):
        return len(self._hh.get("memberships", []))


# ── Toniebox sensors ──────────────────────────────────────────────────────────

class TonieboxBaseSensor(TonieBaseSensor):
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
        return {
            "identifiers": {(DOMAIN, self._tb_id)},
            "name": self._tb_name,
            "manufacturer": "Boxine GmbH",
            "model": "Toniebox",
            "via_device": (DOMAIN, self._hh_id),
        }


class TonieboxFirmwareSensor(TonieboxBaseSensor):
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator, hh_id, tb_id, tb_name):
        super().__init__(coordinator, hh_id, tb_id, tb_name)
        self._attr_unique_id = f"{tb_id}_firmware"
        self._attr_name = f"{tb_name} Firmware"

    @property
    def native_value(self):
        fw = self._tb.get("firmware", {})
        return fw.get("version") or fw.get("toniesVersion") or "unknown"

    @property
    def extra_state_attributes(self):
        return {"firmware": self._tb.get("firmware", {})}


class TonieboxLastSeenSensor(TonieboxBaseSensor):
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, hh_id, tb_id, tb_name):
        super().__init__(coordinator, hh_id, tb_id, tb_name)
        self._attr_unique_id = f"{tb_id}_last_seen"
        self._attr_name = f"{tb_name} Last Seen"

    @property
    def native_value(self):
        return self._tb.get("last_seen")


# ── Creative Tonie sensors ────────────────────────────────────────────────────

class TonieBaseTonieSensor(TonieBaseSensor):
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
        return {
            "identifiers": {(DOMAIN, self._t_id)},
            "name": self._t_name,
            "manufacturer": "Boxine GmbH",
            "model": "Creative Tonie",
            "via_device": (DOMAIN, self._hh_id),
        }


class TonieChapterCountSensor(TonieBaseTonieSensor):
    _attr_icon = "mdi:format-list-numbered"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, hh_id, t_id, t_name):
        super().__init__(coordinator, hh_id, t_id, t_name)
        self._attr_unique_id = f"{t_id}_chapter_count"
        self._attr_name = f"{t_name} Chapter Count"

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


class TonieTotalDurationSensor(TonieBaseTonieSensor):
    _attr_icon = "mdi:timer-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator, hh_id, t_id, t_name):
        super().__init__(coordinator, hh_id, t_id, t_name)
        self._attr_unique_id = f"{t_id}_total_duration"
        self._attr_name = f"{t_name} Total Duration"

    @property
    def native_value(self):
        total = self._tonie.get("total_seconds", 0)
        return round(total / 60, 1)
