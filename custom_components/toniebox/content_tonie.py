"""Content Tonie platform — one HA device per physical Content Tonie figurine.

Every Content Tonie gets its own device with these entities:
  - sensor: Aktuell auf Box (which Toniebox it's on right now)
  - sensor: Kapitel-Anzahl
  - sensor: Gesamtdauer (min)
  - sensor: Typ / Serie
  - binary_sensor: Gerade aktiv (is it currently playing on a Toniebox?)
  - binary_sensor: Gesperrt (locked to household)
  - binary_sensor: Transkodierung läuft
  - switch: Im Haushalt sperren (lock)
  - button: Tune entfernen
  - select: Sprache (multi-language Content Tonies only)

This allows per-Content-Tonie automations, e.g.:
  "When 'Benjamin Blümchen' is placed on a box → turn on bedroom light"
"""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .device_info import content_tonie_device_info

_LOGGER = logging.getLogger(__name__)

# Languages supported by multi-language Content Tonies (same as Toniebox)
_LANGUAGES = ["de", "en", "en-us", "fr"]


# ── Base ──────────────────────────────────────────────────────────────────────

class _CTBase(CoordinatorEntity):
    """Base for all Content Tonie entities."""
    _attr_has_entity_name = True

    def __init__(self, coordinator, hh_id: str, ct_id: str) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._ct_id = ct_id

    @property
    def _ct(self) -> dict:
        return (
            self.coordinator.data
            .get("households", {}).get(self._hh_id, {})
            .get("contenttonies", {}).get(self._ct_id, {})
        )

    @property
    def device_info(self) -> dict:
        return content_tonie_device_info(self.coordinator, self._hh_id, self._ct_id)


# ── Sensors ───────────────────────────────────────────────────────────────────

class ContentTonieCurrentBoxSensor(_CTBase, SensorEntity):
    """Which Toniebox this Content Tonie is currently placed on (ID or name)."""
    _attr_icon = "mdi:speaker-wireless"

    def __init__(self, coordinator, hh_id, ct_id):
        super().__init__(coordinator, hh_id, ct_id)
        self._attr_unique_id = f"content_{ct_id}_current_box"
        self._attr_name = "Aktuelle Box"

    @property
    def native_value(self) -> str | None:
        hh = self.coordinator.data.get("households", {}).get(self._hh_id, {})
        # Prefer direct field from API
        box_id = self._ct.get("toniebox_id")
        if not box_id:
            # Fall back: find which toniebox has this content tonie placed on it
            for tb_id, tb in hh.get("tonieboxes", {}).items():
                placement = tb.get("placement", {})
                if isinstance(placement, dict):
                    placed_id = (
                        (placement.get("tonie") or {}).get("id")
                        or placement.get("tonieId")
                        or placement.get("tonie_id")
                    )
                    if placed_id == self._ct_id:
                        box_id = tb_id
                        break
        if not box_id:
            return None
        box = hh.get("tonieboxes", {}).get(box_id, {})
        return box.get("name") or box_id

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "toniebox_id": self._ct.get("toniebox_id") or self._ct.get("tonieboxId"),
            "image_url": self._ct.get("image_url"),
            "sales_id": self._ct.get("sales_id"),
        }


class ContentTonieChapterCountSensor(_CTBase, SensorEntity):
    """Number of chapters on this Content Tonie."""
    _attr_icon = "mdi:format-list-numbered"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, hh_id, ct_id):
        super().__init__(coordinator, hh_id, ct_id)
        self._attr_unique_id = f"content_{ct_id}_chapter_count"
        self._attr_name = "Kapitel"

    @property
    def native_value(self) -> int:
        chapters = self._ct.get("chapters", [])
        return len(chapters)

    @property
    def extra_state_attributes(self) -> dict:
        chapters = self._ct.get("chapters", [])
        return {
            "chapter_titles": [c.get("title", "") for c in chapters],
        }


class ContentTonieDurationSensor(_CTBase, SensorEntity):
    """Total duration of content in minutes."""
    _attr_icon = "mdi:timer-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator, hh_id, ct_id):
        super().__init__(coordinator, hh_id, ct_id)
        self._attr_unique_id = f"content_{ct_id}_duration"
        self._attr_name = "Gesamtdauer"

    @property
    def native_value(self) -> float | None:
        chapters = self._ct.get("chapters", [])
        if not chapters:
            return None
        total = sum(c.get("seconds", 0) for c in chapters)
        return round(total / 60, 1)


class ContentTonieSalesSensor(_CTBase, SensorEntity):
    """Sales/series ID of this Content Tonie — useful for identifying the content."""
    _attr_icon = "mdi:barcode"

    def __init__(self, coordinator, hh_id, ct_id):
        super().__init__(coordinator, hh_id, ct_id)
        self._attr_unique_id = f"content_{ct_id}_sales_id"
        self._attr_name = "Serien-ID"

    @property
    def native_value(self) -> str | None:
        return self._ct.get("sales_id")

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "language": self._ct.get("language"),
            "locked": self._ct.get("locked", False),
            "name": self._ct.get("name"),
        }


# ── Binary Sensors ────────────────────────────────────────────────────────────

class ContentTonieActiveBinarySensor(_CTBase, BinarySensorEntity):
    """True when this Content Tonie is currently placed on a Toniebox in this household."""
    _attr_icon = "mdi:play-circle-outline"
    _attr_device_class = None

    def __init__(self, coordinator, hh_id, ct_id):
        super().__init__(coordinator, hh_id, ct_id)
        self._attr_unique_id = f"content_{ct_id}_active"
        self._attr_name = "Gerade aktiv"

    @property
    def is_on(self) -> bool:
        # A Content Tonie is "active" if any Toniebox in this household has it placed
        hh = self.coordinator.data.get("households", {}).get(self._hh_id, {})
        for tb in hh.get("tonieboxes", {}).values():
            placement = tb.get("placement", {})
            if isinstance(placement, dict):
                # API returns placement = {"tonie": {"id": "...", ...}}
                placed_id = (
                    (placement.get("tonie") or {}).get("id")
                    or placement.get("tonieId")
                    or placement.get("tonie_id")
                    or placement.get("id")
                )
                if placed_id == self._ct_id:
                    return True
            elif isinstance(placement, str) and placement == self._ct_id:
                return True
        return False


class ContentTonieLockBinarySensor(_CTBase, BinarySensorEntity):
    """True when this Content Tonie is locked to the current household."""
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator, hh_id, ct_id):
        super().__init__(coordinator, hh_id, ct_id)
        self._attr_unique_id = f"content_{ct_id}_locked_bs"
        self._attr_name = "Im Haushalt gesperrt"

    @property
    def is_on(self) -> bool:
        return bool(self._ct.get("locked", False))


class ContentTonieTranscodingBinarySensor(_CTBase, BinarySensorEntity):
    """True while the Content Tonie is being transcoded."""
    _attr_icon = "mdi:cog-sync-outline"

    def __init__(self, coordinator, hh_id, ct_id):
        super().__init__(coordinator, hh_id, ct_id)
        self._attr_unique_id = f"content_{ct_id}_transcoding"
        self._attr_name = "Transkodierung aktiv"

    @property
    def is_on(self) -> bool:
        return bool(self._ct.get("transcoding", False))


# ── Switch: Lock to household ─────────────────────────────────────────────────

class ContentTonieLockSwitch(_CTBase, SwitchEntity):
    """Lock/unlock this Content Tonie to the current household."""
    _attr_icon = "mdi:lock-outline"

    def __init__(self, coordinator, hh_id, ct_id):
        super().__init__(coordinator, hh_id, ct_id)
        self._attr_unique_id = f"content_{ct_id}_lock_switch"
        self._attr_name = "Im Haushalt sperren"
        self._optimistic_state: bool | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        self._optimistic_state = None
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool:
        if self._optimistic_state is not None:
            return self._optimistic_state
        return bool(self._ct.get("locked", False))

    async def async_turn_on(self, **kw) -> None:
        self._optimistic_state = True
        self.async_write_ha_state()
        await self.coordinator.client.patch_content_tonie(
            self._hh_id, self._ct_id, {"lock": True}
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kw) -> None:
        self._optimistic_state = False
        self.async_write_ha_state()
        await self.coordinator.client.patch_content_tonie(
            self._hh_id, self._ct_id, {"lock": False}
        )
        await self.coordinator.async_request_refresh()


# ── Button: Remove active Tune ────────────────────────────────────────────────

class ContentTonieTuneRemoveButton(_CTBase, ButtonEntity):
    """Remove the currently active Tune from this Content Tonie."""
    _attr_icon = "mdi:music-off"
    _attr_entity_registry_enabled_default = False  # only relevant when a Tune is active

    def __init__(self, coordinator, hh_id, ct_id):
        super().__init__(coordinator, hh_id, ct_id)
        self._attr_unique_id = f"content_{ct_id}_remove_tune"
        self._attr_name = "Tune entfernen"

    async def async_press(self) -> None:
        await self.coordinator.client.delete_tonie_tune(self._hh_id, self._ct_id)
        await self.coordinator.async_request_refresh()


# ── Select: Language (multi-language Content Tonies) ─────────────────────────

class ContentTonieLanguageSelect(_CTBase, SelectEntity):
    """Language selector for multi-language Content Tonies."""
    _attr_icon = "mdi:translate"
    _attr_options = _LANGUAGES
    # Hidden by default — only relevant for multi-language Content Tonies
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, hh_id, ct_id):
        super().__init__(coordinator, hh_id, ct_id)
        self._attr_unique_id = f"content_{ct_id}_language"
        self._attr_name = "Sprache"
        self._optimistic: str | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        self._optimistic = None
        super()._handle_coordinator_update()

    @property
    def current_option(self) -> str:
        if self._optimistic:
            return self._optimistic
        lang = self._ct.get("language")
        return lang if lang in _LANGUAGES else _LANGUAGES[0]

    @property
    def available(self) -> bool:
        # Only meaningful when the API returns a language field
        return self._ct.get("language") is not None

    async def async_select_option(self, option: str) -> None:
        self._optimistic = option
        self.async_write_ha_state()
        await self.coordinator.client.patch_content_tonie(
            self._hh_id, self._ct_id, {"language": option}
        )
        await self.coordinator.async_request_refresh()
