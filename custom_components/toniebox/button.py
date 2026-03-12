"""Button platform — buttons on their respective devices."""
from __future__ import annotations

from dataclasses import dataclass, field
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .content_tonie import ContentTonieTuneRemoveButton
from .device_info import creative_tonie_device_info, toniebox_device_info, household_device_info


@dataclass
class _BtnDesc(ButtonEntityDescription):
    action: str = ""
    args: dict = field(default_factory=dict)
    disabled_default: bool = False


_TONIE_BUTTONS = [
    _BtnDesc(key="clear",         name="Alle Kapitel löschen",     icon="mdi:delete-sweep",              action="clear", disabled_default=True),
    _BtnDesc(key="sort_title",    name="Nach Titel sortieren",      icon="mdi:sort-alphabetical-ascending", action="sort", args={"sort_by": "title"}),
    _BtnDesc(key="sort_filename", name="Nach Dateiname sortieren",  icon="mdi:sort-variant",               action="sort", args={"sort_by": "filename"}),
    _BtnDesc(key="sort_date",     name="Nach Datum sortieren",      icon="mdi:sort-calendar-ascending",    action="sort", args={"sort_by": "date"}),
    _BtnDesc(key="refresh",       name="Aktualisieren",             icon="mdi:refresh",                    action="refresh"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = []

    for hh_id, hh in coordinator.data.get("households", {}).items():
        # Household-level: global refresh button
        entities.append(HouseholdRefreshButton(coordinator, hh_id))

        # Per Creative Tonie: sort + clear + refresh buttons
        for t_id in hh.get("creativetonies", {}):
            for desc in _TONIE_BUTTONS:
                entities.append(CreativeTonieButton(coordinator, hh_id, t_id, desc))

        # Per Toniebox: refresh + reset buttons
        for tb_id in hh.get("tonieboxes", {}):
            entities.append(TonieboxRefreshButton(coordinator, hh_id, tb_id))
            entities.append(TonieboxResetButton(coordinator, hh_id, tb_id))

    # ── Content Tonie buttons ─────────────────────────────────────────────────
    for hh_id, hh in coordinator.data.get("households", {}).items():
        for ct_id in hh.get("contenttonies", {}):
            entities.append(ContentTonieTuneRemoveButton(coordinator, hh_id, ct_id))

    async_add_entities(entities)


# ── Household refresh button (on Hub device) ──────────────────────────────────

class HouseholdRefreshButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Alle aktualisieren"
    _attr_icon = "mdi:cloud-sync"

    def __init__(self, coordinator, hh_id: str) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._attr_unique_id = f"hh_{hh_id}_refresh"

    @property
    def device_info(self) -> dict:
        return household_device_info(self.coordinator, self._hh_id)

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


# ── Creative Tonie buttons ────────────────────────────────────────────────────

class CreativeTonieButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, hh_id: str, t_id: str, desc: _BtnDesc) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._t_id = t_id
        self.entity_description = desc
        self._attr_unique_id = f"ct_{t_id}_btn_{desc.key}"
        if desc.disabled_default:
            self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> dict:
        return creative_tonie_device_info(self.coordinator, self._hh_id, self._t_id)

    async def async_press(self) -> None:
        client = self.coordinator.client
        action = self.entity_description.action
        if action == "clear":
            await client.clear_chapters(self._hh_id, self._t_id)
        elif action == "sort":
            await client.sort_chapters(self._hh_id, self._t_id, self.entity_description.args.get("sort_by", "title"))
        await self.coordinator.async_request_refresh()


# ── Toniebox refresh button ───────────────────────────────────────────────────

class TonieboxRefreshButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Aktualisieren"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator, hh_id: str, tb_id: str) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._tb_id = tb_id
        self._attr_unique_id = f"tb_{tb_id}_btn_refresh"

    @property
    def device_info(self) -> dict:
        return toniebox_device_info(self.coordinator, self._hh_id, self._tb_id)

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


# ── Toniebox settings reset button ────────────────────────────────────────────

class TonieboxResetButton(CoordinatorEntity, ButtonEntity):
    """Resets all Toniebox settings to factory defaults (except name & language)."""
    _attr_has_entity_name = True
    _attr_name = "Auf Werkseinstellungen zurücksetzen"
    _attr_icon = "mdi:restore"
    _attr_entity_registry_enabled_default = False  # deliberately hidden by default — destructive action

    def __init__(self, coordinator, hh_id: str, tb_id: str) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._tb_id = tb_id
        self._attr_unique_id = f"tb_{tb_id}_btn_reset"

    @property
    def device_info(self) -> dict:
        return toniebox_device_info(self.coordinator, self._hh_id, self._tb_id)

    async def async_press(self) -> None:
        await self.coordinator.client.patch_toniebox(
            self._hh_id, self._tb_id, {"reset": True}
        )
        await self.coordinator.async_request_refresh()
