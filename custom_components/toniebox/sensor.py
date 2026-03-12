"""Sensor platform — read-only state and info sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .content_tonie import (
    ContentTonieCurrentBoxSensor,
    ContentTonieChapterCountSensor,
    ContentTonieDurationSensor,
    ContentTonieSalesSensor,
    DiscCurrentBoxSensor,
    DiscSalesSensor,
)
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

    for hh_id, hh in coordinator.data.get("households", {}).items():
        # ── Household sensors ─────────────────────────────────────────────────
        entities += [
            HouseholdSensor(
                coordinator, hh_id, "account", "Account", "mdi:account",
                lambda d: d.get("me", {}).get("email", "unbekannt"),
            ),
            HouseholdCountSensor(coordinator, hh_id, "tonies",        "Creative Tonies",  "mdi:teddy-bear",         "creativetonies"),
            HouseholdCountSensor(coordinator, hh_id, "content_tonies","Content Tonies",   "mdi:music-box-multiple", "contenttonies"),
            HouseholdCountSensor(coordinator, hh_id, "discs",         "Content Discs",    "mdi:disc",               "discs"),
            HouseholdCountSensor(coordinator, hh_id, "tonieboxes",    "Tonieboxen",        "mdi:speaker",            "tonieboxes"),
            HouseholdCountSensor(coordinator, hh_id, "children",      "Kinder",            "mdi:account-child",      "children"),
            HouseholdCountSensor(coordinator, hh_id, "members",       "Mitglieder",        "mdi:account-group",      "memberships"),
            HouseholdNotifSensor(coordinator, hh_id),
            HouseholdInviteSensor(coordinator, hh_id),
        ]

        # ── Toniebox sensors ──────────────────────────────────────────────────
        for tb_id, tb in hh.get("tonieboxes", {}).items():
            features = tb.get("features", [])
            entities += [
                TonieboxFirmwareSensor(coordinator, hh_id, tb_id),
                TonieboxLastSeenSensor(coordinator, hh_id, tb_id),
                TonieboxOnlineStateSensor(coordinator, hh_id, tb_id),
                TonieboxGenerationSensor(coordinator, hh_id, tb_id),
                TonieboxFeaturesSensor(coordinator, hh_id, tb_id),
                TonieboxRegisteredAtSensor(coordinator, hh_id, tb_id),
                TonieboxSettingsAppliedSensor(coordinator, hh_id, tb_id),
                TonieboxWifiSensor(coordinator, hh_id, tb_id),
            ]
            # Timezone sensor — always useful
            entities.append(TonieboxTimezoneSensor(coordinator, hh_id, tb_id))
            # Bedtime color — only on tng
            if "tngSettings" in features:
                entities.append(TonieboxBedtimeColorSensor(coordinator, hh_id, tb_id))

        # ── Creative Tonie sensors ────────────────────────────────────────────
        for t_id in hh.get("creativetonies", {}):
            entities += [
                TonieChapterCountSensor(coordinator, hh_id, t_id),
                TonieDurationSensor(coordinator, hh_id, t_id),
                CreativeTonieTranscodingSensor(coordinator, hh_id, t_id),
                CreativeTonieCapacitySensor(coordinator, hh_id, t_id),
            ]

        # ── Content Tonie sensors (one device per figurine) ───────────────────
        for ct_id in hh.get("contenttonies", {}):
            entities += [
                ContentTonieCurrentBoxSensor(coordinator, hh_id, ct_id),
                ContentTonieChapterCountSensor(coordinator, hh_id, ct_id),
                ContentTonieDurationSensor(coordinator, hh_id, ct_id),
                ContentTonieSalesSensor(coordinator, hh_id, ct_id),
            ]

        # ── Content Disc sensors (one device per disc) ────────────────────────
        for disc_id in hh.get("discs", {}):
            entities += [
                DiscCurrentBoxSensor(coordinator, hh_id, disc_id),
                DiscSalesSensor(coordinator, hh_id, disc_id),
            ]

    async_add_entities(entities)


# ── Base ──────────────────────────────────────────────────────────────────────

class _Base(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)

    @property
    def _data(self):
        return self.coordinator.data


# ── Household sensors ─────────────────────────────────────────────────────────

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


# ── Toniebox sensors (read-only) ──────────────────────────────────────────────

class _TbBase(_Base):
    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._tb_id = tb_id

    @property
    def _tb(self):
        return self._data.get("households", {}).get(self._hh_id, {}).get("tonieboxes", {}).get(self._tb_id, {})

    @property
    def device_info(self):
        return toniebox_device_info(self.coordinator, self._hh_id, self._tb_id)


class TonieboxFirmwareSensor(_TbBase):
    _attr_has_entity_name = True
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_firmware"
        self._attr_name = "Firmware"

    @property
    def native_value(self):
        # New API field: firmwareVersion (string directly)
        ver = self._tb.get("firmware_version")
        if ver:
            return ver
        # Legacy fallback: firmware dict
        fw = self._tb.get("firmware", {})
        return fw.get("version") or fw.get("toniesVersion") or "unbekannt"

    @property
    def extra_state_attributes(self):
        return {
            "firmware_details": self._tb.get("firmware", {}),
            "settings_applied": self._tb.get("settings_applied"),
        }


class TonieboxLastSeenSensor(_TbBase):
    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_last_seen"
        self._attr_name = "Zuletzt gesehen"

    @property
    def native_value(self):
        return self._tb.get("last_seen")


class TonieboxOnlineStateSensor(_TbBase):
    """Reports the API onlineState string: connected / offline / unknown / unsupported."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-check-outline"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_online_state"
        self._attr_name = "Online-Status"

    @property
    def native_value(self):
        return self._tb.get("online_state", "unknown")


class TonieboxGenerationSensor(_TbBase):
    """Toniebox generation: classic / rosered / tng."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_generation"
        self._attr_name = "Generation"

    @property
    def native_value(self):
        return self._tb.get("generation")

    @property
    def extra_state_attributes(self):
        return {
            "product": self._tb.get("product"),
            "offline_mode": self._tb.get("offline_mode"),
        }


class TonieboxFeaturesSensor(_TbBase):
    """Comma-separated list of features this Toniebox supports."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:feature-search-outline"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_features"
        self._attr_name = "Features"

    @property
    def native_value(self):
        features = self._tb.get("features", [])
        return ", ".join(features) if features else "keine"

    @property
    def extra_state_attributes(self):
        return {"feature_list": self._tb.get("features", [])}


class TonieboxRegisteredAtSensor(_TbBase):
    """When this Toniebox was last added to the household (ISO 8601)."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_registered_at"
        self._attr_name = "Hinzugefügt am"

    @property
    def native_value(self):
        return self._tb.get("registered_at")


class TonieboxTimezoneSensor(_TbBase):
    """The configured timezone of the Toniebox."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:earth-clock"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_timezone"
        self._attr_name = "Zeitzone"

    @property
    def native_value(self):
        return self._tb.get("timezone")


class TonieboxBedtimeColorSensor(_TbBase):
    """Bedtime lightring color (tng only), shown as hex string."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:palette"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_bedtime_color"
        self._attr_name = "Schlafenszeit-Farbe"

    @property
    def native_value(self):
        return self._tb.get("bedtime_lightring_color")


# ── Creative Tonie sensors ────────────────────────────────────────────────────

class _TonieBase(_Base):
    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._t_id = t_id

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

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
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

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_duration"
        self._attr_name = "Gesamtdauer"

    @property
    def native_value(self):
        return round(self._tonie.get("total_seconds", 0) / 60, 1)


class TonieboxSettingsAppliedSensor(_TbBase):
    """Whether the Toniebox has received the latest settings update."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_settings_applied"
        self._attr_name = "Einstellungen übertragen"

    @property
    def native_value(self):
        val = self._tb.get("settings_applied")
        if val is True:
            return "ja"
        if val is False:
            return "nein"
        return "unbekannt"


class TonieboxWifiSensor(_TbBase):
    """SSID of the Toniebox Wi-Fi setup network."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:wifi"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_ssid"
        self._attr_name = "Setup-WLAN (SSID)"

    @property
    def native_value(self):
        return self._tb.get("ssid")


class CreativeTonieTranscodingSensor(_TonieBase):
    """Whether a Creative Tonie is currently transcoding."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:cog-sync-outline"

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_transcoding"
        self._attr_name = "Transkodierung"

    @property
    def native_value(self):
        return "aktiv" if self._tonie.get("transcoding") else "inaktiv"

    @property
    def extra_state_attributes(self):
        return {
            "seconds_remaining": self._tonie.get("secondsRemaining"),
            "seconds_present": self._tonie.get("secondsPresent"),
            "chapters_remaining": self._tonie.get("chaptersRemaining"),
            "chapters_present": self._tonie.get("chaptersPresent"),
            "last_update": self._tonie.get("lastUpdate"),
            "transcoding_errors": self._tonie.get("transcodingErrors", []),
        }


class CreativeTonieCapacitySensor(_TonieBase):
    """Free time in minutes remaining on a Creative Tonie (max 90 min)."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-plus-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_free_minutes"
        self._attr_name = "Freie Zeit"

    @property
    def native_value(self):
        secs = self._tonie.get("secondsRemaining")
        return round(secs / 60, 1) if secs is not None else None
