"""Sensor platform — read-only state and info sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
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
    headphones_device_info,
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
                coordinator, hh_id, "account", "mdi:account",
                lambda d: d.get("me", {}).get("email", "unknown"),
            ),
            HouseholdCountSensor(coordinator, hh_id, "tonies",        "mdi:teddy-bear",         "creativetonies"),
            HouseholdCountSensor(coordinator, hh_id, "content_tonies","mdi:music-box-multiple", "contenttonies"),
            HouseholdCountSensor(coordinator, hh_id, "discs",         "mdi:disc",               "discs"),
            HouseholdCountSensor(coordinator, hh_id, "tonieboxes",    "mdi:speaker",            "tonieboxes"),
            HouseholdCountSensor(coordinator, hh_id, "children",      "mdi:account-child",      "children"),
            HouseholdCountSensor(coordinator, hh_id, "members",       "mdi:account-group",      "memberships"),
            HouseholdNotifSensor(coordinator, hh_id),
            HouseholdInviteSensor(coordinator, hh_id),
        ]

        # ── Toniebox sensors ──────────────────────────────────────────────────
        for tb_id, tb in hh.get("tonieboxes", {}).items():
            features = tb.get("features", [])
            entities += [
                TonieboxCurrentTonieSensor(coordinator, hh_id, tb_id),
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
            # ICI sensors — TNG boxes only (battery, headphones via real-time push)
            generation = tb.get("generation", "")
            if generation == "tng":
                entities += [
                    TonieboxBatterySensor(coordinator, hh_id, tb_id),
                    TonieboxBatteryStatusSensor(coordinator, hh_id, tb_id),
                    HeadphonesTypeSensor(coordinator, hh_id, tb_id),
                    HeadphonesBatterySensor(coordinator, hh_id, tb_id),
                    HeadphonesColorSensor(coordinator, hh_id, tb_id),
                ]

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

    def __init__(self, coordinator, hh_id, key, icon, value_fn):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._value_fn = value_fn
        self._attr_unique_id = f"hh_{hh_id}_{key}"
        self._attr_translation_key = key
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

    def __init__(self, coordinator, hh_id, key, icon, data_key):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._data_key = data_key
        self._attr_unique_id = f"hh_{hh_id}_{key}_count"
        self._attr_translation_key = key
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
    _attr_translation_key = "notifications"

    def __init__(self, coordinator, hh_id):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._attr_unique_id = f"hh_{hh_id}_notifications"

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
    _attr_translation_key = "pending_invitations"

    def __init__(self, coordinator, hh_id):
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._attr_unique_id = f"hh_{hh_id}_invitations"

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
    _attr_translation_key = "firmware"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_firmware"

    @property
    def native_value(self):
        ver = self._tb.get("firmware_version")
        if ver:
            return ver
        fw = self._tb.get("firmware", {})
        return fw.get("version") or fw.get("toniesVersion") or "unknown"

    @property
    def extra_state_attributes(self):
        return {
            "firmware_details": self._tb.get("firmware", {}),
            "settings_applied": self._tb.get("settings_applied"),
        }


class TonieboxLastSeenSensor(_TbBase):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "last_seen"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_last_seen"

    @property
    def native_value(self):
        return self._tb.get("last_seen")


class TonieboxOnlineStateSensor(_TbBase):
    """Reports the API onlineState string: connected / offline / unknown / unsupported."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-check-outline"
    _attr_translation_key = "online_status"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_online_state"

    @property
    def native_value(self):
        return self._tb.get("online_state", "unknown")


class TonieboxGenerationSensor(_TbBase):
    """Toniebox generation: classic / rosered / tng."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:information-outline"
    _attr_translation_key = "generation"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_generation"

    @property
    def native_value(self):
        return self._tb.get("generation")

    @property
    def extra_state_attributes(self):
        return {
            "device_id": self._tb.get("id"),
            "mac_address": self._tb.get("mac_address"),
            "product": self._tb.get("product"),
            "offline_mode": self._tb.get("offline_mode"),
        }


class TonieboxFeaturesSensor(_TbBase):
    """Comma-separated list of features this Toniebox supports."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:feature-search-outline"
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "features"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_features"

    @property
    def native_value(self):
        features = self._tb.get("features", [])
        return ", ".join(features) if features else "none"

    @property
    def extra_state_attributes(self):
        return {"feature_list": self._tb.get("features", [])}


class TonieboxRegisteredAtSensor(_TbBase):
    """When this Toniebox was last added to the household (ISO 8601)."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-clock"
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "registered_at"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_registered_at"

    @property
    def native_value(self):
        return self._tb.get("registered_at")


class TonieboxTimezoneSensor(_TbBase):
    """The configured timezone of the Toniebox."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:earth-clock"
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "timezone"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_timezone"

    @property
    def native_value(self):
        return self._tb.get("timezone")


class TonieboxBedtimeColorSensor(_TbBase):
    """Bedtime lightring color (tng only), shown as hex string."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:palette"
    _attr_translation_key = "bedtime_color"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_bedtime_color"

    @property
    def native_value(self):
        return self._tb.get("bedtime_lightring_color")


# ── ICI real-time sensors (TNG only) ─────────────────────────────────────────

class _TbIciBase(_TbBase, RestoreEntity):
    """Base for ICI sensors that restore their last known state on startup."""

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._restored_state = None
        self._restored_attributes: dict = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) and last.state not in (
            None, "unknown", "unavailable",
        ):
            self._restored_state = last.state
            self._restored_attributes = dict(last.attributes)
        else:
            self._restored_state = None
            self._restored_attributes = {}


class TonieboxBatterySensor(_TbIciBase):
    """Battery level of a TNG Toniebox (via ICI real-time push)."""
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:battery"
    _attr_translation_key = "battery"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_battery"

    @property
    def native_value(self):
        battery = self._tb.get("battery")
        if isinstance(battery, dict):
            return battery.get("percent")
        if self._restored_state is not None:
            try:
                return int(self._restored_state)
            except (ValueError, TypeError):
                pass
        return None

    @property
    def extra_state_attributes(self):
        battery = self._tb.get("battery")
        if isinstance(battery, dict):
            return {
                "raw": battery.get("raw"),
                "status": battery.get("status"),
            }
        return self._restored_attributes if self._restored_attributes else {}


class TonieboxBatteryStatusSensor(_TbIciBase):
    """Charging status of a TNG Toniebox (charging / discharging)."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:battery-charging"
    _attr_translation_key = "battery_status"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_battery_status"

    @property
    def native_value(self):
        battery = self._tb.get("battery")
        if isinstance(battery, dict):
            return battery.get("status")
        return self._restored_state


class _HeadphonesBase(_TbIciBase):
    """Base for sensors belonging to the headphones sub-device."""

    @property
    def device_info(self):
        return headphones_device_info(self.coordinator, self._hh_id, self._tb_id)


class HeadphonesTypeSensor(_TbIciBase):
    """Audio output type: speaker (built-in) or bluetooth (headphones connected)."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:speaker"
    _attr_translation_key = "audio_output"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_audio_output"

    @property
    def native_value(self):
        hp = self._tb.get("headphones")
        if not isinstance(hp, dict):
            return self._restored_state
        connected = hp.get("connected", [])
        if connected:
            first = connected[0] if isinstance(connected[0], dict) else {}
            return first.get("type", "bluetooth")
        return "speaker"


class HeadphonesBatterySensor(_HeadphonesBase):
    """Battery level of headphones connected to a TNG Toniebox (via ICI)."""
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:headphones"
    _attr_translation_key = "headphones_battery"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_headphones_battery"

    @property
    def native_value(self):
        hp = self._tb.get("headphones")
        if isinstance(hp, dict):
            connected = hp.get("connected", [])
            if connected and isinstance(connected[0], dict):
                return connected[0].get("battery")
        if self._restored_state is not None:
            try:
                return int(self._restored_state)
            except (ValueError, TypeError):
                pass
        return None


class HeadphonesColorSensor(_HeadphonesBase):
    """Color code of connected headphones (via ICI)."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:palette"
    _attr_translation_key = "headphones_color"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_headphones_color"

    @property
    def native_value(self):
        hp = self._tb.get("headphones")
        if isinstance(hp, dict):
            connected = hp.get("connected", [])
            if connected and isinstance(connected[0], dict):
                return connected[0].get("color")
        return self._restored_state


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
    _attr_translation_key = "chapter_count"

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_chapter_count"

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
    _attr_translation_key = "total_duration"

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_duration"

    @property
    def native_value(self):
        return round(self._tonie.get("total_seconds", 0) / 60, 1)


class TonieboxSettingsAppliedSensor(_TbBase):
    """Whether the Toniebox has received the latest settings update."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:check-circle-outline"
    _attr_translation_key = "settings_applied"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_settings_applied"

    @property
    def native_value(self):
        val = self._tb.get("settings_applied")
        if val is True:
            return "yes"
        if val is False:
            return "no"
        return "unknown"


class TonieboxWifiSensor(_TbBase):
    """SSID of the Toniebox Wi-Fi setup network."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:wifi"
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "setup_wifi"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_ssid"

    @property
    def native_value(self):
        return self._tb.get("ssid")


class CreativeTonieTranscodingSensor(_TonieBase):
    """Whether a Creative Tonie is currently transcoding."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:cog-sync-outline"
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "transcoding"

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_transcoding"

    @property
    def native_value(self):
        return "active" if self._tonie.get("transcoding") else "inactive"

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
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "free_minutes"

    def __init__(self, coordinator, hh_id, t_id):
        super().__init__(coordinator, hh_id, t_id)
        self._attr_unique_id = f"ct_{t_id}_free_minutes"

    @property
    def native_value(self):
        secs = self._tonie.get("secondsRemaining")
        return round(secs / 60, 1) if secs is not None else None


# ── Toniebox current tonie sensor ─────────────────────────────────────────────

class TonieboxCurrentTonieSensor(_TbBase):
    """The tonie currently placed on the box, enriched with playback-info data."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:music-note"
    _attr_translation_key = "current_tonie"

    def __init__(self, coordinator, hh_id, tb_id):
        super().__init__(coordinator, hh_id, tb_id)
        self._attr_unique_id = f"tb_{tb_id}_current_tonie"

    @property
    def _placement(self) -> dict:
        return self._tb.get("placement") or {}

    @property
    def _placed_tonie(self) -> dict:
        return self._placement.get("tonie") or {}

    @property
    def _playback(self) -> dict:
        return self._tb.get("playback_info") or {}

    @property
    def native_value(self) -> str | None:
        tonie = self._placed_tonie
        return tonie.get("name") or tonie.get("id") or None

    @property
    def entity_picture(self) -> str | None:
        return (
            self._playback.get("imageUrl")
            or self._placed_tonie.get("imageUrl")
            or self._placed_tonie.get("image_url")
        )

    @property
    def extra_state_attributes(self) -> dict:
        tonie = self._placed_tonie
        pi = self._playback
        return {
            "tonie_id": tonie.get("id"),
            "tonie_type": pi.get("tonieType"),
            "playback_status": pi.get("status"),
            "image_url": pi.get("imageUrl") or tonie.get("imageUrl"),
            "chapters": [
                {"title": c.get("title"), "seconds": c.get("seconds")}
                for c in pi.get("chapters", [])
            ],
        }
