"""Media Player platform — one per Creative Tonie + one per Toniebox."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ICI_VOLUME_MAX_LEVEL
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
    """Media player representing a physical Toniebox.

    Shows the currently placed Tonie and live playback position when available.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC

    # Live playback control (play/pause/skip/volume) works only over ICI, which
    # is exclusive to the Toniebox 2 (TNG). Classic boxes get no controls.
    _TNG_FEATURES = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        # Turn OFF = put to sleep. Turn ON isn't possible (box is offline and
        # can't be woken over the cloud), so TURN_ON is intentionally omitted.
        | MediaPlayerEntityFeature.TURN_OFF
        # Browse the placed Tonie's chapters and jump to any of them.
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )

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
    def _is_tng(self) -> bool:
        return self._tb.get("generation") == "tng"

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        # Only the TNG (Toniebox 2) can be controlled remotely; a classic
        # Toniebox 1 has no ICI connection, so it stays a display-only player.
        return self._TNG_FEATURES if self._is_tng else MediaPlayerEntityFeature(0)

    @property
    def _mac(self) -> str:
        return self._tb.get("mac_address") or ""

    @property
    def device_info(self) -> dict:
        return toniebox_device_info(self.coordinator, self._hh_id, self._tb_id)

    def _placed_tonie(self) -> dict:
        """Return the tonie object currently placed on this box, or {}."""
        return (self._tb.get("placement") or {}).get("tonie") or {}

    def _resolve_tonie_name(self, tonie_id: str) -> str | None:
        """Look up tonie name from known creative/content tonies by ID."""
        known = self._known_tonie(tonie_id)
        return known.get("name") if known else None

    def _known_tonie(self, tonie_id: str) -> dict | None:
        """The full known record (with chapters) for a tonie ID, if any."""
        hh = self.coordinator.data.get("households", {}).get(self._hh_id, {})
        return (
            hh.get("creativetonies", {}).get(tonie_id)
            or hh.get("contenttonies", {}).get(tonie_id)
            or hh.get("discs", {}).get(tonie_id)
        )

    @property
    def _playback_state(self) -> dict:
        """Live playback state pushed via ICI (position/chapter/paused)."""
        return self._tb.get("playback_state") or {}

    def _chapters(self) -> list[dict]:
        """Chapter list of the currently placed Tonie (each a dict with a title).

        Prefers the box's playback_info, falls back to the known tonie record
        (creative tonies carry their own chapter list).
        """
        info = self._tb.get("playback_info", {})
        chapters = info.get("chapters")
        if not chapters:
            known = self._known_tonie(self._placed_tonie().get("id", ""))
            chapters = known.get("chapters") if known else None
        return [c for c in (chapters or []) if isinstance(c, dict)]

    def _chapter_title(self) -> str | None:
        """Resolve the title of the currently playing chapter.

        Verified live (tests/chapter_index_test.py): the box's `chapter` field is
        a 0-based index into the chapter list (setPosition N -> plays list[N]).
        """
        chapter = self._playback_state.get("chapter")
        if not isinstance(chapter, int) or chapter < 0:
            return None
        chapters = self._chapters()
        if 0 <= chapter < len(chapters):
            ch = chapters[chapter]
            return ch.get("title") or ch.get("tuneTitle")
        return None

    @property
    def state(self) -> MediaPlayerState:
        # A box that is offline (e.g. put to sleep) reads as OFF.
        if self._tb.get("online_state") == "offline":
            return MediaPlayerState.OFF
        if not self._placed_tonie():
            return MediaPlayerState.ON if self._tb.get("last_seen") else MediaPlayerState.OFF
        ps = self._playback_state
        if ps.get("ended"):
            return MediaPlayerState.IDLE
        if ps.get("paused"):
            return MediaPlayerState.PAUSED
        return MediaPlayerState.PLAYING

    @property
    def media_title(self) -> str | None:
        """Main line: the current chapter (what's playing right now)."""
        tonie = self._placed_tonie()
        if not tonie:
            return "Kein Tonie aufgelegt"
        chapter_title = self._chapter_title()
        if chapter_title:
            return chapter_title
        chapter = self._playback_state.get("chapter")
        if isinstance(chapter, int) and chapter >= 0:
            # chapter is 0-based; show a human-friendly 1-based number.
            return f"Kapitel {chapter + 1}"
        # No live chapter info yet — fall back to the tonie's own name.
        tonie_id = tonie.get("id", "")
        return tonie.get("name") or self._resolve_tonie_name(tonie_id) or tonie_id

    @property
    def media_artist(self) -> str | None:
        """Secondary line: the Tonie figure name (e.g. 'Rubie')."""
        tonie = self._placed_tonie()
        if not tonie:
            return None
        tonie_id = tonie.get("id", "")
        return tonie.get("name") or self._resolve_tonie_name(tonie_id) or None

    @property
    def media_image_url(self) -> str | None:
        tonie = self._placed_tonie()
        return tonie.get("imageUrl") or tonie.get("image_url")

    @property
    def media_image_remotely_accessible(self) -> bool:
        return True

    @property
    def media_position(self) -> int | None:
        """Elapsed seconds within the current chapter (from ICI live state)."""
        pos = self._playback_state.get("position")
        return int(pos) if isinstance(pos, (int, float)) else None

    @property
    def media_duration(self) -> int | None:
        """Duration of the current chapter in seconds (from ICI live state)."""
        dur = self._playback_state.get("chapter_duration")
        return int(dur) if isinstance(dur, (int, float)) else None

    @property
    def media_position_updated_at(self):
        """When media_position was last measured — lets HA extrapolate the bar."""
        return self._playback_state.get("updated_at")

    # ── Volume ────────────────────────────────────────────────────────────────

    @property
    def _volume(self) -> dict:
        return self._tb.get("volume") or {}

    @property
    def volume_level(self) -> float | None:
        """Current playback volume as 0.0–1.0 (from the box's live hardware %)."""
        pct = self._volume.get("hardware_percentage")
        if isinstance(pct, (int, float)):
            return max(0.0, min(1.0, pct / 100))
        level = self._volume.get("level")
        if isinstance(level, (int, float)):
            return max(0.0, min(1.0, level / ICI_VOLUME_MAX_LEVEL))
        return None

    # ── Controls (published to the ICI broker, mirroring the Tonies app) ───────

    async def async_media_play(self) -> None:
        if self._is_tng:
            self.coordinator.ici_playback_command(self._mac, "start")

    async def async_media_pause(self) -> None:
        if self._is_tng:
            self.coordinator.ici_playback_command(self._mac, "pause")

    async def async_media_next_track(self) -> None:
        if not self._is_tng:
            return
        chapter = self._playback_state.get("chapter")
        if isinstance(chapter, int):
            self.coordinator.ici_playback_command(
                self._mac, "setPosition", chapter=chapter + 1, ms=0
            )

    async def async_media_previous_track(self) -> None:
        if not self._is_tng:
            return
        chapter = self._playback_state.get("chapter")
        # chapter is 0-based; chapter 0 is the first, so guard at >= 1.
        if isinstance(chapter, int) and chapter >= 1:
            self.coordinator.ici_playback_command(
                self._mac, "setPosition", chapter=chapter - 1, ms=0
            )

    async def async_set_volume_level(self, volume: float) -> None:
        if not self._is_tng:
            return
        level = round(volume * ICI_VOLUME_MAX_LEVEL)
        self.coordinator.ici_set_volume_level(self._mac, level)

    async def async_volume_up(self) -> None:
        if not self._is_tng:
            return
        current = self._volume.get("level")
        base = current if isinstance(current, int) else 0
        self.coordinator.ici_set_volume_level(self._mac, base + 1)

    async def async_volume_down(self) -> None:
        if not self._is_tng:
            return
        current = self._volume.get("level")
        base = current if isinstance(current, int) else 1
        self.coordinator.ici_set_volume_level(self._mac, base - 1)

    async def async_turn_off(self) -> None:
        """Put the Toniebox to sleep (it goes offline). Cannot be turned on again."""
        if self._is_tng:
            self.coordinator.ici_sleep_now(self._mac)

    # ── Chapter browsing / jumping ─────────────────────────────────────────────

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Expose the placed Tonie's chapters as a browsable list.

        The box addresses chapters 0-based (verified live), so the
        media_content_id carries the 0-based index while the label shows a
        human-friendly 1-based number.
        """
        current = self._playback_state.get("chapter")   # 0-based box index
        children = []
        for idx, ch in enumerate(self._chapters()):     # idx = 0-based box index
            title = ch.get("title") or ch.get("tuneTitle") or f"Kapitel {idx + 1}"
            # Mark the chapter that is playing right now.
            label = f"▶ {title}" if idx == current else title
            children.append(
                BrowseMedia(
                    title=label,
                    media_class=MediaClass.TRACK,
                    media_content_type=MediaType.MUSIC,
                    media_content_id=f"chapter:{idx}",
                    can_play=True,
                    can_expand=False,
                )
            )
        tonie = self._placed_tonie()
        return BrowseMedia(
            title=tonie.get("name") or "Kapitel",
            media_class=MediaClass.DIRECTORY,
            media_content_type="chapters",
            media_content_id="chapters",
            can_play=False,
            can_expand=True,
            children=children,
            children_media_class=MediaClass.TRACK,
        )

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Jump to a chapter selected from the browse list (media_id 'chapter:N').

        N is the box's 0-based chapter index (see async_browse_media).
        """
        if not self._is_tng or not media_id.startswith("chapter:"):
            return
        try:
            chapter = int(media_id.split(":", 1)[1])
        except ValueError:
            return
        if chapter >= 0:
            self.coordinator.ici_playback_command(
                self._mac, "setPosition", chapter=chapter, ms=0
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        tb = self._tb
        info = tb.get("playback_info", {})
        ps = tb.get("playback_state") or {}
        attrs: dict[str, Any] = {
            "household_id": self._hh_id,
            "toniebox_id": self._tb_id,
            "led": tb.get("led", True),
            "skip_mute_detection": tb.get("skip_mute_detection", False),
            "last_seen": tb.get("last_seen"),
            "firmware": tb.get("firmware", {}),
            "placement": tb.get("placement") or {},
            # 1-based for humans; the box reports a 0-based chapter internally.
            "current_chapter": (
                ps["chapter"] + 1 if isinstance(ps.get("chapter"), int) else None
            ),
            "paused": ps.get("paused"),
        }
        if info:
            attrs["playback_info"] = info
        return attrs
