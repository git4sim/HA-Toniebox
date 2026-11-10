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
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VOLUME_MULTIPLIER_MIN, VOLUME_MULTIPLIER_MAX
from .device_info import (
    toniebox_device_info,
    creative_tonie_device_info,
    content_tonie_device_info,
    disc_device_info,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TbNumberDesc(NumberEntityDescription):
    """Extended description with coordinator-key and API-key."""
    data_key: str = ""       # key in coordinator tb-dict
    api_key: str = ""        # key sent to PATCH API
    feature_required: str = ""   # only shown if feature present (empty = always)
    feature_excluded: str = ""   # hidden if feature present


# ── All number entities ───────────────────────────────────────────────────────
# Volume / headphone limits: any percentage 1–100 (a live box reported 52,
# so the API is not restricted to 25/50/75/100).

_TB_NUMBERS: list[_TbNumberDesc] = [
    # ── TNG-generation (lightring, bedtime) ───────────────────────────────────
    _TbNumberDesc(
        key="lightring_brightness",
        name="Ring Brightness",
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
        name="Bedtime Ring Brightness",
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
        name="Bedtime Max. Box Volume",
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
        name="Bedtime Max. Headphone Volume",
        icon="mdi:headphones",
        native_min_value=1, native_max_value=100, native_step=1,
        native_unit_of_measurement="%",
        mode=NumberMode.SLIDER,
        data_key="bedtime_max_headphone_volume",
        api_key="bedtimeMaxHeadphoneVolume",
        feature_required="tngSettings",
    ),
    # ── All boxes (volume limits in 1 % steps) ────────────────────────────────
    _TbNumberDesc(
        key="max_volume",
        name="Max. Box Volume",
        icon="mdi:volume-high",
        native_min_value=1, native_max_value=100, native_step=1,
        native_unit_of_measurement="%",
        mode=NumberMode.SLIDER,
        data_key="max_volume",
        api_key="maxVolume",
    ),
    _TbNumberDesc(
        key="max_headphone_volume",
        name="Max. Headphone Volume",
        icon="mdi:headphones",
        native_min_value=1, native_max_value=100, native_step=1,
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

    # ── Volume multiplier per Tonie (Creative, Content, Disc) ─────────────────
    known: set[tuple[str, str]] = set()

    def _collect_multipliers() -> list:
        new: list = []
        for hh_id, hh in coordinator.data.get("households", {}).items():
            for kind in ("creativetonies", "contenttonies", "discs"):
                for t_id in hh.get(kind, {}):
                    if (kind, t_id) in known:
                        continue
                    known.add((kind, t_id))
                    new.append(TonieVolumeMultiplierNumber(coordinator, hh_id, t_id, kind))
        return new

    entities += _collect_multipliers()
    async_add_entities(entities)

    @callback
    def _async_add_new() -> None:
        new = _collect_multipliers()
        if new:
            async_add_entities(new)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))


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
        self._attr_translation_key = desc.key
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


_DEVICE_INFO = {
    "creativetonies": creative_tonie_device_info,
    "contenttonies": content_tonie_device_info,
    "discs": disc_device_info,
}
_UID_PREFIX = {"creativetonies": "ct", "contenttonies": "content", "discs": "disc"}


class TonieVolumeMultiplierNumber(CoordinatorEntity, NumberEntity):
    """Per-Tonie volume multiplier (local-only, persisted by the coordinator).

    While this Tonie is on a box, the box's max volume and current volume are
    raised by this factor; removing/replacing the Tonie undoes it.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:volume-plus"
    _attr_translation_key = "volume_multiplier"
    _attr_native_min_value = VOLUME_MULTIPLIER_MIN
    _attr_native_max_value = VOLUME_MULTIPLIER_MAX
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "×"
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, hh_id: str, t_id: str, kind: str) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._t_id = t_id
        self._kind = kind
        self._attr_unique_id = f"{_UID_PREFIX[kind]}_{t_id}_volume_multiplier"

    @property
    def device_info(self) -> dict:
        return _DEVICE_INFO[self._kind](self.coordinator, self._hh_id, self._t_id)

    @property
    def native_value(self) -> float:
        return self.coordinator.get_volume_multiplier(self._t_id)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_volume_multiplier(self._t_id, value)
        self.async_write_ha_state()
