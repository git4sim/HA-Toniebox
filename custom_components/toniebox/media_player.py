"""Media Player platform for Toniebox creative tonies."""

from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity, MediaPlayerEntityFeature, MediaPlayerState, MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ATTR_HOUSEHOLD_ID, ATTR_TONIE_ID, ATTR_CHAPTERS, ATTR_CHAPTER_COUNT, ATTR_IMAGE_URL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for hh_id, hh in coordinator.data.get("households", {}).items():
        for t_id in hh.get("creativetonies", {}):
            entities.append(TonieboxMediaPlayer(coordinator, hh_id, t_id, entry))
    async_add_entities(entities, update_before_add=True)


class TonieboxMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Represents a Creative Tonie as a HA media player entity."""

    _attr_has_entity_name = True
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.BROWSE_MEDIA | MediaPlayerEntityFeature.PLAY_MEDIA
    )

    def __init__(self, coordinator, household_id: str, tonie_id: str, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._household_id = household_id
        self._tonie_id = tonie_id
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{household_id}_{tonie_id}"

    @property
    def _tonie_data(self) -> dict:
        return (
            self.coordinator.data
            .get("households", {}).get(self._household_id, {})
            .get("creativetonies", {}).get(self._tonie_id, {})
        )

    @property
    def name(self) -> str:
        return self._tonie_data.get("name", self._tonie_id)

    @property
    def state(self) -> MediaPlayerState:
        return MediaPlayerState.ON

    @property
    def media_title(self) -> str | None:
        chapters = self._tonie_data.get("chapters", [])
        return f"{len(chapters)} chapter(s)" if chapters else "No chapters"

    @property
    def media_image_url(self) -> str | None:
        return self._tonie_data.get("image_url")

    @property
    def media_image_remotely_accessible(self) -> bool:
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        tonie = self._tonie_data
        return {
            ATTR_HOUSEHOLD_ID: self._household_id,
            ATTR_TONIE_ID: self._tonie_id,
            ATTR_CHAPTER_COUNT: tonie.get("chapter_count", 0),
            ATTR_IMAGE_URL: tonie.get("image_url"),
            ATTR_CHAPTERS: [
                {"id": ch.get("id",""), "title": ch.get("title",""),
                 "duration_seconds": ch.get("seconds", 0), "transcoding": ch.get("transcoding", False)}
                for ch in tonie.get("chapters", [])
            ],
        }

    @property
    def device_info(self):
        hh = self.coordinator.data.get("households", {}).get(self._household_id, {})
        return {
            "identifiers": {(DOMAIN, self._household_id)},
            "name": hh.get("name", f"Toniebox Household"),
            "manufacturer": "Boxine GmbH",
            "model": "Toniebox Cloud",
        }

    async def async_play_media(self, media_type: MediaType | str, media_id: str, **kwargs: Any) -> None:
        """Handle sort:/clear commands via media_id."""
        if media_id.startswith("sort:"):
            sort_by = media_id.split(":", 1)[1]
            await self.coordinator.client.sort_chapters(self._household_id, self._tonie_id, sort_by)
        elif media_id == "clear":
            await self.coordinator.client.clear_chapters(self._household_id, self._tonie_id)
        else:
            _LOGGER.warning("Unsupported media_id command: %s", media_id)
        await self.coordinator.async_request_refresh()
