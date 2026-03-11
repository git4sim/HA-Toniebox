"""Select platform — enum settings for Tonieboxes + sort selector for Creative Tonies."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SORT_OPTIONS, SORT_BY_TITLE
from .device_info import creative_tonie_device_info, toniebox_device_info

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TbSelectDesc:
    key: str
    name: str
    icon: str
    options: list[str]
    data_key: str         # key in coordinator tb-dict
    api_key: str          # key sent to PATCH API
    feature_required: str = ""
    feature_excluded: str = ""
    default: str = ""


_TB_SELECTS: list[_TbSelectDesc] = [
    # ledLevel — older boxes only (no tngSettings)
    _TbSelectDesc(
        key="led_level",
        name="LED-Helligkeit",
        icon="mdi:led-on",
        options=["on", "off", "dimmed"],
        data_key="led_level",
        api_key="ledLevel",
        feature_excluded="tngSettings",
        default="on",
    ),
    # skippingDirection — applies to boxes WITH tngSettings
    _TbSelectDesc(
        key="skipping_direction",
        name="Kapitelsprung-Richtung",
        icon="mdi:gesture-tap",
        options=["right", "left"],
        data_key="skipping_direction",
        api_key="skippingDirection",
        feature_required="tngSettings",
        default="right",
    ),
    # tapDirection — older boxes only
    _TbSelectDesc(
        key="tap_direction",
        name="Klopf-Richtung",
        icon="mdi:gesture-tap",
        options=["left", "right"],
        data_key="tap_direction",
        api_key="tapDirection",
        feature_excluded="tngSettings",
        default="left",
    ),
    # ageMode — only on boxes with "ageMode" feature
    _TbSelectDesc(
        key="age_mode",
        name="Altersgruppe",
        icon="mdi:baby-face-outline",
        options=["1+", "3+"],
        data_key="age_mode",
        api_key="ageMode",
        feature_required="ageMode",
        default="3+",
    ),
    # language — only on boxes with "language" feature
    _TbSelectDesc(
        key="language",
        name="Sprache",
        icon="mdi:translate",
        options=["de", "en", "en-us", "fr"],
        data_key="language",
        api_key="language",
        feature_required="language",
        default="de",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = []

    for hh_id, hh in coordinator.data.get("households", {}).items():
        # Toniebox selects
        for tb_id, tb in hh.get("tonieboxes", {}).items():
            features = tb.get("features", [])
            for desc in _TB_SELECTS:
                if desc.feature_required and desc.feature_required not in features:
                    continue
                if desc.feature_excluded and desc.feature_excluded in features:
                    continue
                entities.append(TonieboxSelect(coordinator, hh_id, tb_id, desc))

        # Creative Tonie: sort selector
        for t_id in hh.get("creativetonies", {}):
            entities.append(TonieSortSelect(coordinator, hh_id, t_id))

    async_add_entities(entities)


# ── Toniebox enum selects ─────────────────────────────────────────────────────

class TonieboxSelect(CoordinatorEntity, SelectEntity):
    """A writable enum setting of a Toniebox."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, hh_id: str, tb_id: str, desc: _TbSelectDesc) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._tb_id = tb_id
        self._desc = desc
        self._attr_unique_id = f"tb_{tb_id}_{desc.key}"
        self._attr_name = desc.name
        self._attr_icon = desc.icon
        self._attr_options = desc.options
        self._optimistic: str | None = None

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
        self._optimistic = None
        super()._handle_coordinator_update()

    @property
    def current_option(self) -> str | None:
        if self._optimistic is not None:
            return self._optimistic
        val = self._tb.get(self._desc.data_key)
        if val is not None and str(val) in self._desc.options:
            return str(val)
        return self._desc.default if self._desc.default else self._desc.options[0]

    async def async_select_option(self, option: str) -> None:
        self._optimistic = option
        self.async_write_ha_state()
        await self.coordinator.client.patch_toniebox(
            self._hh_id, self._tb_id, {self._desc.api_key: option}
        )
        await self.coordinator.async_request_refresh()


# ── Creative Tonie sort selector ──────────────────────────────────────────────

class TonieSortSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True
    _attr_options = SORT_OPTIONS
    _attr_icon = "mdi:sort"
    _attr_name = "Kapitel sortieren"

    def __init__(self, coordinator, hh_id: str, t_id: str) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._t_id = t_id
        self._current = SORT_BY_TITLE
        self._attr_unique_id = f"ct_{t_id}_sort_select"

    @property
    def device_info(self) -> dict:
        return creative_tonie_device_info(self.coordinator, self._hh_id, self._t_id)

    @property
    def current_option(self) -> str:
        return self._current

    async def async_select_option(self, option: str) -> None:
        self._current = option
        await self.coordinator.client.sort_chapters(self._hh_id, self._t_id, option)
        await self.coordinator.async_request_refresh()
