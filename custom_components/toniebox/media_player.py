"""Media Player platform — one per Creative Tonie + one per Toniebox."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device_info import creative_tonie_device_info, toniebox_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = []

    for hh_id, hh in coordinator.data.get("households", {}).items():
        for t_id in hh.get("creativetonies", {}):
            entities.append(CreativeToniePlayer(coordinator, hh_id, t_id))
        for tb_id in hh.get("tonieboxes", {}):
            entities.append(TonieboxPlayer(coordinator, hh_id, tb_id))

    async_add_entities(entities, update_before_add=True)


# ── Creative Tonie Player ─────────────────────────────────────────────────────

class CreativeToniePlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player representing a Creative Tonie (chapters, cover art)."""

    _attr_has_entity_name = True
    _attr_name = None                       # entity name = device name
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )

    def __init__(self, coordinator, hh_id: str, t_id: str) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._t_id = t_id
        self._attr_unique_id = f"ct_{t_id}_player"

    @property
    def _tonie(self) -> dict:
        return (
            self.coordinator.data
            .get("households", {}).get(self._hh_id, {})
            .get("creativetonies", {}).get(self._t_id, {})
        )

    @property
    def device_info(self) -> dict:
        return creative_tonie_device_info(self.coordinator, self._hh_id, self._t_id)

    @property
    def state(self) -> MediaPlayerState:
        if self._tonie.get("transcoding"):
            return MediaPlayerState.BUFFERING
        return MediaPlayerState.ON if self._tonie.get("chapters") else MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        chapters = self._tonie.get("chapters", [])
        if not chapters:
            return "Keine Kapitel"
        mins = round(sum(c.get("seconds", 0) for c in chapters) / 60, 1)
        return f"{len(chapters)} Kapitel · {mins} Min"

    @property
    def media_image_url(self) -> str | None:
        return self._tonie.get("image_url")

    @property
    def media_image_remotely_accessible(self) -> bool:
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        t = self._tonie
        return {
            "household_id": self._hh_id,
            "tonie_id": self._t_id,
            "chapter_count": t.get("chapter_count", 0),
            "total_minutes": round(t.get("total_seconds", 0) / 60, 1),
            "transcoding": t.get("transcoding", False),
            "live": t.get("live", False),
            "private": t.get("private", False),
            "chapters": [
                {
                    "id": c.get("id", ""),
                    "title": c.get("title", ""),
                    "duration_seconds": c.get("seconds", 0),
                    "transcoding": c.get("transcoding", False),
                }
                for c in t.get("chapters", [])
            ],
        }

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        client = self.coordinator.client
        if media_id.startswith("sort:"):
            await client.sort_chapters(self._hh_id, self._t_id, media_id.split(":", 1)[1])
        elif media_id == "clear":
            await client.clear_chapters(self._hh_id, self._t_id)
        else:
            _LOGGER.warning("Unsupported media_id: %s", media_id)
        await self.coordinator.async_request_refresh()


# ── Toniebox Player ───────────────────────────────────────────────────────────

class TonieboxPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Media player representing a physical Toniebox (shows placed Tonie)."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = MediaPlayerEntityFeature.BROWSE_MEDIA

    def __init__(self, coordinator, hh_id: str, tb_id: str) -> None:
        super().__init__(coordinator)
        self._hh_id = hh_id
        self._tb_id = tb_id
        self._attr_unique_id = f"tb_{tb_id}_player"

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
    def state(self) -> MediaPlayerState:
        placement = self._tb.get("placement", {})
        if placement.get("tonie"):
            return MediaPlayerState.PLAYING
        return MediaPlayerState.ON if self._tb.get("last_seen") else MediaPlayerState.OFF

    @property
    def media_title(self) -> str | None:
        tonie = self._tb.get("placement", {}).get("tonie")
        return tonie.get("name", "Tonie aufgelegt") if tonie else "Kein Tonie aufgelegt"

    @property
    def media_image_url(self) -> str | None:
        tonie = self._tb.get("placement", {}).get("tonie", {})
        return tonie.get("image_url") if tonie else None

    @property
    def media_image_remotely_accessible(self) -> bool:
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        tb = self._tb
        return {
            "household_id": self._hh_id,
            "toniebox_id": self._tb_id,
            "led": tb.get("led", True),
            "skip_mute_detection": tb.get("skip_mute_detection", False),
            "last_seen": tb.get("last_seen"),
            "firmware": tb.get("firmware", {}),
            "placement": tb.get("placement", {}),
        }
