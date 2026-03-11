"""Number platform — all writable integer settings of a Toniebox."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device_info import toniebox_device_info

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TbNumberDesc(NumberEntityDescription):
    """Extended description with coordinator-key and API-key."""
    data_key: str = ""       # key in coordinator tb-dict
    api_key: str = ""        # key sent to PATCH API
    feature_required: str = ""   # only shown if feature present (empty = always)
    feature_excluded: str = ""   # hidden if feature present


# ── All number entities ───────────────────────────────────────────────────────
# Volume / headphone limits  (enum: 25 / 50 / 75 / 100 per API)
_VOLUME_LEVELS = [25, 50, 75, 100]

_TB_NUMBERS: list[_TbNumberDesc] = [
    # ── TNG-generation (lightring, bedtime) ───────────────────────────────────
    _TbNumberDesc(
        key="lightring_brightness",
        name="Lautstärke Leuchtring",
        icon="mdi:brightness-5",
        native_min_value=0, native_max_value=100, native_step=1,
        native_unit_of_measurement="%",
        mode=NumberMode.SLIDER,
        data_key="lightring_brightness",
        api_key="lightringBrightness",
        feature_required="tngSettings",
    ),
    _TbNumberDesc(
        key="bedtime_lightring_brightness",
        name="Leuchtring-Helligkeit (Schlafenszeit)",
        icon="mdi:brightness-3",
        native_min_value=0, native_max_value=100, native_step=1,
        native_unit_of_measurement="%",
        mode=NumberMode.SLIDER,
        data_key="bedtime_lightring_brightness",
        api_key="bedtimeLightringBrightness",
        feature_required="tngSettings",
    ),
    _TbNumberDesc(
        key="bedtime_max_volume",
        name="Max. Lautstärke (Schlafenszeit)",
        icon="mdi:volume-low",
        native_min_value=1, native_max_value=100, native_step=1,
        native_unit_of_measurement="%",
        mode=NumberMode.SLIDER,
        data_key="bedtime_max_volume",
        api_key="bedtimeMaxVolume",
        feature_required="tngSettings",
    ),
    _TbNumberDesc(
        key="bedtime_max_headphone_volume",
        name="Max. Kopfhörer-Lautstärke (Schlafenszeit)",
        icon="mdi:headphones",
        native_min_value=1, native_max_value=100, native_step=1,
        native_unit_of_measurement="%",
        mode=NumberMode.SLIDER,
        data_key="bedtime_max_headphone_volume",
        api_key="bedtimeMaxHeadphoneVolume",
        feature_required="tngSettings",
    ),
    # ── Classic / all boxes (volume enum: 25/50/75/100) ───────────────────────
    _TbNumberDesc(
        key="max_volume",
        name="Max. Lautstärke (Lautsprecher)",
        icon="mdi:volume-high",
        native_min_value=25, native_max_value=100, native_step=25,
        native_unit_of_measurement="%",
        mode=NumberMode.SLIDER,
        data_key="max_volume",
        api_key="maxVolume",
    ),
    _TbNumberDesc(
        key="max_headphone_volume",
        name="Max. Kopfhörer-Lautstärke",
        icon="mdi:headphones",
        native_min_value=25, native_max_value=100, native_step=25,
        native_unit_of_measurement="%",
        mode=NumberMode.SLIDER,
        data_key="max_headphone_volume",
        api_key="maxHeadphoneVolume",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = []

    for hh_id, hh in coordinator.data.get("households", {}).items():
        for tb_id, tb in hh.get("tonieboxes", {}).items():
            features = tb.get("features", [])
            for desc in _TB_NUMBERS:
                if desc.feature_required and desc.feature_required not in features:
                    continue
                if desc.feature_excluded and desc.feature_excluded in features:
                    continue
                entities.append(TonieboxNumber(coordinator, hh_id, tb_id, desc))

    async_add_entities(entities)


class TonieboxNumber(CoordinatorEntity, NumberEntity):
    """A writable numeric setting of a Toniebox."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        hh_id: str,
        tb_id: str,
        desc: _TbNumberDesc,
    ) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._tb_id = tb_id
        self._desc = desc
        self.entity_description = desc
        self._attr_unique_id = f"tb_{tb_id}_{desc.key}"
        self._optimistic_value: float | None = None

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

    @property
    def native_value(self) -> float | None:
        if self._optimistic_value is not None:
            return self._optimistic_value
        val = self._tb.get(self._desc.data_key)
        return float(val) if val is not None else None

    @property
    def available(self) -> bool:
        return self._tb.get(self._desc.data_key) is not None or self._optimistic_value is not None

    def _handle_coordinator_update(self) -> None:
        self._optimistic_value = None
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        self._optimistic_value = value
        self.async_write_ha_state()
        await self.coordinator.client.patch_toniebox(
            self._hh_id, self._tb_id, {self._desc.api_key: int(value)}
        )
        await self.coordinator.async_request_refresh()
