"""The Toniebox integration — full API v2 with ICI real-time push."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, CONF_USERNAME, CONF_PASSWORD, UPDATE_INTERVAL_MINUTES,
    ICI_TOPIC_BATTERY, ICI_TOPIC_ONLINE, ICI_TOPIC_HEADPHONES, ICI_TOPIC_SETTINGS,
    ICI_TOPIC_PLAYBACK, ICI_TOPIC_VOLUME, ICI_TOPIC_BEDTIME,
    ICI_CMD_PLAYBACK, ICI_CMD_VOLUME, ICI_VOLUME_MAX_LEVEL,
    ICI_CMD_SLEEP_TIMER, ICI_CMD_SLEEP_NOW,
)
from .ici_client import TonieboxIciClient
from .tonie_client import TonieCloudClient, TonieCloudAuthError, TonieCloudAPIError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.IMAGE,
    Platform.MEDIA_PLAYER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Toniebox from a config entry."""
    session = async_get_clientsession(hass)
    client = TonieCloudClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session,
    )

    try:
        await client.authenticate()
    except TonieCloudAuthError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err

    coordinator = TonieboxDataUpdateCoordinator(hass, client, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Could not fetch data: {err}") from err

    # Start ICI real-time connection for TNG boxes
    await coordinator.async_start_ici()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator and coordinator.ici_client:
        await coordinator.ici_client.disconnect()
        coordinator.client.remove_token_listener(coordinator.ici_client.on_token_refreshed)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


# ── Entity lookup helpers ─────────────────────────────────────────────────────

async def _find_creative_tonie(hass: HomeAssistant, entity_id: str):
    """Look up (client, household_id, tonie_id) for any Creative Tonie entity."""
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is not None and entry.unique_id.startswith("ct_"):
        uid = entry.unique_id[3:]  # strip "ct_"
        for coordinator in hass.data.get(DOMAIN, {}).values():
            for hh_id, hh in coordinator.data.get("households", {}).items():
                for t_id in hh.get("creativetonies", {}):
                    if uid == t_id or uid.startswith(t_id + "_"):
                        return coordinator.client, hh_id, t_id

    return None, None, None


async def _find_toniebox(hass: HomeAssistant, entity_id: str):
    """Look up (client, household_id, toniebox_id) for any Toniebox entity."""
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is not None and entry.unique_id.startswith("tb_"):
        uid = entry.unique_id[3:]  # strip "tb_"
        for coordinator in hass.data.get(DOMAIN, {}).values():
            for hh_id, hh in coordinator.data.get("households", {}).items():
                for tb_id in hh.get("tonieboxes", {}):
                    if uid == tb_id or uid.startswith(tb_id + "_"):
                        return coordinator.client, hh_id, tb_id

    return None, None, None


async def _find_toniebox_target(hass: HomeAssistant, entity_id: str):
    """Look up (coordinator, hh_id, tb_id, tb_dict) for any Toniebox entity.

    Unlike _find_toniebox this returns the coordinator and the box data dict, so
    callers can access the MAC / generation and invoke coordinator ICI commands.
    """
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is not None and entry.unique_id.startswith("tb_"):
        uid = entry.unique_id[3:]  # strip "tb_"
        for coordinator in hass.data.get(DOMAIN, {}).values():
            for hh_id, hh in coordinator.data.get("households", {}).items():
                for tb_id, tb in hh.get("tonieboxes", {}).items():
                    if uid == tb_id or uid.startswith(tb_id + "_"):
                        return coordinator, hh_id, tb_id, tb

    return None, None, None, None


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")


# ── Service registration ──────────────────────────────────────────────────────

def _register_services(hass: HomeAssistant) -> None:
    """Register all custom Toniebox services."""
    import voluptuous as vol
    from homeassistant.helpers import config_validation as cv

    if hass.services.has_service(DOMAIN, "clear_chapters"):
        return  # Already registered (e.g. multiple config entries)

    # ── Creative Tonie services ───────────────────────────────────────────────

    async def handle_clear_chapters(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.clear_chapters(hh_id, t_id)
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "clear_chapters", handle_clear_chapters,
        schema=vol.Schema({vol.Required("entity_id"): cv.string}),
    )

    async def handle_sort_chapters(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.sort_chapters(hh_id, t_id, call.data.get("sort_by", "title"))
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "sort_chapters", handle_sort_chapters,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Optional("sort_by", default="title"): vol.In(["title", "filename", "date"]),
        }),
    )

    async def handle_remove_chapter(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.remove_chapter(hh_id, t_id, call.data["chapter_id"])
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "remove_chapter", handle_remove_chapter,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("chapter_id"): cv.string,
        }),
    )

    async def handle_move_chapter(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            try:
                await client.move_chapter(
                    hh_id, t_id,
                    call.data["chapter_id"],
                    call.data.get("direction", "up"),
                )
                await _refresh_all(hass)
            except TonieCloudAPIError as err:
                _LOGGER.error("move_chapter failed: %s", err)

    hass.services.async_register(
        DOMAIN, "move_chapter", handle_move_chapter,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("chapter_id"): cv.string,
            vol.Optional("direction", default="up"): vol.In(["up", "down"]),
        }),
    )

    async def handle_rename_tonie(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.patch_creative_tonie(hh_id, t_id, {"name": call.data["name"]})
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "rename_tonie", handle_rename_tonie,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("name"): cv.string,
        }),
    )

    async def handle_redeem_token(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.redeem_token_to_creative_tonie(hh_id, t_id, call.data["token"])
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "redeem_content_token", handle_redeem_token,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("token"): cv.string,
        }),
    )

    async def handle_apply_tune(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.put_tonie_tune(hh_id, t_id, call.data["tune_id"])
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "apply_tune", handle_apply_tune,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("tune_id"): cv.string,
        }),
    )

    async def handle_remove_tune(call):
        client, hh_id, t_id = await _find_creative_tonie(hass, call.data["entity_id"])
        if client:
            await client.delete_tonie_tune(hh_id, t_id)
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "remove_tune", handle_remove_tune,
        schema=vol.Schema({vol.Required("entity_id"): cv.string}),
    )

    async def handle_upload_audio(call):
        entity_id = call.data["entity_id"]
        file_path = call.data["file_path"]
        title = call.data.get("title", "")

        if not os.path.isfile(file_path):
            _LOGGER.error("upload_audio: file not found: %s", file_path)
            return

        client, hh_id, t_id = await _find_creative_tonie(hass, entity_id)
        if not client:
            _LOGGER.error("upload_audio: entity not found: %s", entity_id)
            return

        filename = os.path.basename(file_path)
        if not title:
            title = os.path.splitext(filename)[0]

        try:
            with open(file_path, "rb") as f:
                file_data = f.read()
            await client.upload_and_add_chapter(hh_id, t_id, file_data, filename, title)
            await _refresh_all(hass)
            _LOGGER.info("upload_audio: successfully uploaded '%s' to %s", filename, entity_id)
        except Exception as err:
            _LOGGER.error("upload_audio failed for %s: %s", file_path, err)

    hass.services.async_register(
        DOMAIN, "upload_audio", handle_upload_audio,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("file_path"): cv.string,
            vol.Optional("title", default=""): cv.string,
        }),
    )

    # ── Toniebox services ─────────────────────────────────────────────────────

    async def handle_rename_toniebox(call):
        client, hh_id, tb_id = await _find_toniebox(hass, call.data["entity_id"])
        if client:
            await client.patch_toniebox(hh_id, tb_id, {"name": call.data["name"]})
            await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "rename_toniebox", handle_rename_toniebox,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("name"): cv.string,
        }),
    )

    async def handle_sleeptimer(call):
        coordinator, hh_id, tb_id, tb = await _find_toniebox_target(
            hass, call.data["entity_id"]
        )
        if not coordinator or not tb:
            _LOGGER.error("sleeptimer: Toniebox not found for %s", call.data["entity_id"])
            return
        if tb.get("generation") != "tng":
            _LOGGER.warning(
                "sleeptimer: only supported on Toniebox 2 (TNG); %s is %s",
                call.data["entity_id"], tb.get("generation"),
            )
            return
        mac = tb.get("mac_address") or ""
        minutes = call.data["minutes"]
        if minutes <= 0:
            coordinator.ici_cancel_sleep_timer(mac)
        else:
            coordinator.ici_set_sleep_timer(mac, minutes * 60)

    hass.services.async_register(
        DOMAIN, "sleeptimer", handle_sleeptimer,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        }),
    )

    # ── Voucher service ───────────────────────────────────────────────────────

    async def handle_redeem_voucher(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.client.redeem_voucher(call.data["code"])
            await _refresh_all(hass)
            return

    hass.services.async_register(
        DOMAIN, "redeem_voucher", handle_redeem_voucher,
        schema=vol.Schema({vol.Required("code"): cv.string}),
    )

    # ── Notification services ─────────────────────────────────────────────────

    async def handle_dismiss_notifications(call):
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.client.delete_all_notifications()
            await _refresh_all(hass)
            return

    hass.services.async_register(
        DOMAIN, "dismiss_all_notifications", handle_dismiss_notifications,
        schema=vol.Schema({}),
    )

    # ── Invitation services ───────────────────────────────────────────────────

    async def handle_accept_invitation(call):
        invitation_id = call.data["invitation_id"]
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.client.accept_invitation(invitation_id)
            await _refresh_all(hass)
            return

    hass.services.async_register(
        DOMAIN, "accept_invitation", handle_accept_invitation,
        schema=vol.Schema({vol.Required("invitation_id"): cv.string}),
    )

    async def handle_decline_invitation(call):
        invitation_id = call.data["invitation_id"]
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.client.delete_invitation(invitation_id)
            await _refresh_all(hass)
            return

    hass.services.async_register(
        DOMAIN, "decline_invitation", handle_decline_invitation,
        schema=vol.Schema({vol.Required("invitation_id"): cv.string}),
    )


async def _refresh_all(hass: HomeAssistant) -> None:
    for coordinator in hass.data.get(DOMAIN, {}).values():
        await coordinator.async_request_refresh()


# ── Coordinator ───────────────────────────────────────────────────────────────

class TonieboxDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator: fetches ALL data from Tonie Cloud + ICI real-time push."""

    def __init__(self, hass: HomeAssistant, client: TonieCloudClient, entry: ConfigEntry) -> None:
        self.client = client
        self.entry = entry
        self.ici_client: TonieboxIciClient | None = None
        self._mac_to_tb: dict[str, tuple[str, str]] = {}  # mac → (hh_id, tb_id)
        super().__init__(
            hass, _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )

    async def async_start_ici(self) -> None:
        """Start ICI MQTT connection for real-time TNG box data."""
        try:
            user_uuid = await self.client.get_user_uuid()
            if not user_uuid:
                _LOGGER.debug("No user UUID available, skipping ICI")
                return

            # Collect all TNG boxes with their MAC addresses
            all_boxes = []
            for hh_id, hh in self.data.get("households", {}).items():
                for tb_id, tb in hh.get("tonieboxes", {}).items():
                    mac = tb.get("mac_address") or ""
                    if mac:
                        self._mac_to_tb[mac.upper()] = (hh_id, tb_id)
                    all_boxes.append({
                        "id": tb_id,
                        "name": tb.get("name", tb_id),
                        "macAddress": mac,
                        "generation": tb.get("generation"),
                    })

            tng_boxes = [b for b in all_boxes if b.get("generation") == "tng"]
            if not tng_boxes:
                _LOGGER.debug("No TNG boxes found, ICI not needed")
                return

            self.ici_client = TonieboxIciClient(
                on_message_callback=self._on_ici_message,
                loop=asyncio.get_running_loop(),
            )
            self.client.add_token_listener(self.ici_client.on_token_refreshed)

            token = self.client.access_token
            if token:
                await self.ici_client.connect(user_uuid, token, all_boxes)
                _LOGGER.info("ICI MQTT started for %d TNG boxes", len(tng_boxes))
        except Exception:
            _LOGGER.warning("Failed to start ICI MQTT", exc_info=True)

    @staticmethod
    def _parse_playback_state(payload: dict) -> dict:
        """Derive a media-player-friendly live playback state from an ICI
        playback/state payload.

        chapterUntilMs is an absolute epoch-ms timestamp for when the current
        chapter ends; combined with chapterDuration we compute the elapsed
        position *at message-receipt time* and store updated_at, so Home
        Assistant extrapolates the progress bar forward while playing and
        freezes it while paused.
        """
        now = datetime.now(timezone.utc)
        duration = payload.get("chapterDuration")
        until_ms = payload.get("chapterUntilMs")
        position_ms = payload.get("chapterPositionMs")
        position = None
        if isinstance(position_ms, (int, float)):
            # Paused: box reports an exact position within the chapter.
            position = position_ms / 1000
            if isinstance(duration, (int, float)):
                position = max(0.0, min(float(duration), position))
        elif isinstance(duration, (int, float)) and isinstance(until_ms, (int, float)):
            # Playing: derive elapsed from the chapter's absolute end timestamp.
            remaining = until_ms / 1000 - now.timestamp()
            position = max(0.0, min(float(duration), float(duration) - remaining))
        return {
            "paused": payload.get("paused"),
            "ended": payload.get("ended"),
            "blocked": payload.get("blocked"),
            "downloading": payload.get("downloading"),
            "chapter": payload.get("chapter"),
            "chapter_duration": duration,
            "position": position,
            "updated_at": now,
        }

    def _on_ici_message(self, mac: str, subtopic: str, payload: dict) -> None:
        """Handle an ICI MQTT message (called from the event loop)."""
        lookup_mac = mac.upper()
        tb_ref = self._mac_to_tb.get(lookup_mac)
        if not tb_ref:
            _LOGGER.debug("ICI message for unknown MAC %s", mac)
            return

        hh_id, tb_id = tb_ref
        data = self.data
        if not data:
            return

        tb = (
            data.get("households", {})
            .get(hh_id, {})
            .get("tonieboxes", {})
            .get(tb_id)
        )
        if not tb:
            return

        updated = False

        if subtopic == ICI_TOPIC_BATTERY and isinstance(payload, dict):
            battery = {
                "percent": payload.get("percent"),
                "raw": payload.get("raw"),
                "status": payload.get("status"),
            }
            tb["battery"] = battery
            tb["last_battery"] = battery.copy()
            updated = True

        elif subtopic == ICI_TOPIC_ONLINE and isinstance(payload, dict):
            state = payload.get("onlineState")
            if state:
                tb["online_state"] = state
                if state == "connected":
                    tb["last_online_at"] = datetime.now(timezone.utc)
                updated = True

        elif subtopic == ICI_TOPIC_HEADPHONES and isinstance(payload, dict):
            tb["headphones"] = {
                "output": payload.get("speaker", {}).get("output") if isinstance(payload.get("speaker"), dict) else None,
                "connected": payload.get("connected", []),
            }
            updated = True

        elif subtopic == ICI_TOPIC_SETTINGS:
            tb["settings_applied"] = True
            updated = True

        elif subtopic == ICI_TOPIC_VOLUME and isinstance(payload, dict):
            # Live playback volume: {"level": N, "hardwarePercentage": P}.
            tb["volume"] = {
                "level": payload.get("level"),
                "hardware_percentage": payload.get("hardwarePercentage"),
            }
            updated = True

        elif subtopic == ICI_TOPIC_BEDTIME:
            # {"stl": {"state": "on"|"off"|"completed", "duration": <s>, "until": <epoch>}}
            stl = payload.get("stl") if isinstance(payload, dict) else None
            if isinstance(stl, dict):
                tb["sleep_timer"] = {
                    "state": stl.get("state"),
                    "duration": stl.get("duration"),
                    "until": stl.get("until"),
                }
            else:
                tb["sleep_timer"] = {}
            updated = True

        elif subtopic == ICI_TOPIC_PLAYBACK:
            # Verified against a live account: {"tonie": "<id>", "paused": bool,
            # "chapter": int, "chapterUntilMs": <epoch ms>, "chapterDuration":
            # <seconds>, "ended": bool, ...} — "tonie" is a flat ID string, not a
            # nested object. An empty/None payload means the Tonie was removed.
            if not payload:
                tb["placement"] = {}
                tb["playback_state"] = {}
            elif isinstance(payload, dict):
                raw_tonie = payload.get("tonie")
                if isinstance(raw_tonie, dict):
                    tonie = raw_tonie if raw_tonie.get("id") else None
                elif isinstance(raw_tonie, str) and raw_tonie:
                    tonie = {"id": raw_tonie}
                else:
                    flat_id = payload.get("tonieId") or payload.get("id")
                    tonie = {"id": flat_id} if flat_id else None
                tb["placement"] = {"tonie": tonie} if tonie else {}
                tb["playback_state"] = self._parse_playback_state(payload)
            updated = True
            # MQTT gives us the identity of the placed Tonie immediately, but not
            # chapters/cover art — request a full coordinator refresh so REST/
            # GraphQL (get_playback_info) fills in the rest shortly after.
            self.hass.async_create_task(self.async_request_refresh())

        if updated:
            tb["last_seen"] = datetime.now(timezone.utc)
            self.async_set_updated_data(data)

    # ── ICI app-control commands (mirror the official Tonies app) ──────────────

    def _ici_publish(self, mac: str, command_type: str, payload: dict) -> bool:
        """Send an app-control command to a box via the ICI broker."""
        if not self.ici_client or not mac:
            _LOGGER.warning("Cannot send ICI command %s: no ICI client / MAC", command_type)
            return False
        # State topics are delivered on the upper-case MAC; commands use the same.
        return self.ici_client.publish_command(mac.upper(), command_type, payload)

    def ici_playback_command(
        self, mac: str, action: str,
        chapter: int | None = None, ms: int | None = None,
    ) -> bool:
        """Play/pause/seek. action = 'start' | 'pause' | 'setPosition'."""
        payload: dict = {"action": action}
        if chapter is not None:
            payload["chapter"] = chapter
        if ms is not None:
            payload["ms"] = ms
        return self._ici_publish(mac, ICI_CMD_PLAYBACK, payload)

    def ici_set_volume_level(self, mac: str, level: int) -> bool:
        """Set the playback volume by discrete level (clamped to the box scale)."""
        level = max(0, min(ICI_VOLUME_MAX_LEVEL, int(level)))
        return self._ici_publish(mac, ICI_CMD_VOLUME, {"level": level})

    def ici_sleep_now(self, mac: str) -> bool:
        """Put the box to sleep immediately (it goes offline).

        Mirrors the official app: set a short sleep timer, then send `sleep`.
        Waking the box back up over the cloud is not possible.
        """
        self._ici_publish(mac, ICI_CMD_SLEEP_TIMER, {"state": "on", "duration": 300})
        return self._ici_publish(mac, ICI_CMD_SLEEP_NOW, {})

    def ici_set_sleep_timer(self, mac: str, seconds: int) -> bool:
        """Arm a sleep timer: the box falls asleep on its own after `seconds`."""
        return self._ici_publish(
            mac, ICI_CMD_SLEEP_TIMER, {"state": "on", "duration": int(seconds)}
        )

    def ici_cancel_sleep_timer(self, mac: str) -> bool:
        """Cancel a running sleep timer."""
        return self._ici_publish(mac, ICI_CMD_SLEEP_TIMER, {"state": "off"})

    async def _async_update_data(self) -> dict:
        try:
            return await self._fetch_all()
        except TonieCloudAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Tonie Cloud error: {err}") from err

    async def _fetch_all(self) -> dict:
        result: dict = {
            "me": {},
            "households": {},
            "notifications": [],
            "system_notifications": [],
            "invitations": [],
        }

        # User profile
        try:
            result["me"] = await self.client.get_me()
        except Exception as e:
            _LOGGER.debug("Could not fetch /me: %s", e)

        # Notifications
        try:
            result["notifications"] = await self.client.get_notifications()
        except Exception as e:
            _LOGGER.debug("Could not fetch notifications: %s", e)

        # System notifications
        try:
            result["system_notifications"] = await self.client.get_system_notifications()
        except Exception as e:
            _LOGGER.debug("Could not fetch system notifications: %s", e)

        # Pending invitations
        try:
            result["invitations"] = await self.client.get_invitations()
        except Exception as e:
            _LOGGER.debug("Could not fetch invitations: %s", e)

        # Households + all nested data
        try:
            households = await self.client.get_households()
        except Exception as e:
            _LOGGER.error("Could not fetch households: %s", e)
            return result

        for hh in households:
            hh_id = hh.get("id", "")
            if not hh_id:
                continue

            hh_data: dict = {
                "id": hh_id,
                "name": hh.get("name", hh_id),
                "creativetonies": {},
                "contenttonies": {},
                "discs": {},
                "tonieboxes": {},
                "children": [],
                "memberships": [],
            }

            # ── Creative Tonies ───────────────────────────────────────────────
            # GET /households/{hh}/creativetonies returns creative tonies.
            # In practice the API may also return content tonies / discs here
            # with an undocumented "type" field — handle that opportunistically
            # with flexible matching, then supplement with dedicated endpoints.
            try:
                all_tonies = await self.client.get_creative_tonies(hh_id)
                _LOGGER.debug("get_creative_tonies(%s): %d items", hh_id, len(all_tonies))
                for tonie in all_tonies:
                    if not isinstance(tonie, dict):
                        continue
                    t_id = tonie.get("id", "")
                    if not t_id:
                        continue

                    # Flexible type detection — the field is undocumented and
                    # its values vary.  Match substrings case-insensitively.
                    tonie_type_raw = (
                        tonie.get("type")
                        or tonie.get("tonieType")
                        or ""
                    ).lower()

                    chapters = [
                        {
                            "id": ch.get("id", ""),
                            "title": ch.get("title", ""),
                            "seconds": ch.get("seconds", 0),
                            "transcoding": ch.get("transcoding", False),
                        }
                        for ch in tonie.get("chapters", [])
                        if isinstance(ch, dict)
                    ]
                    image_url = (
                        tonie.get("imageUrl")
                        or tonie.get("image_url")
                        or tonie.get("image")
                    )

                    if "disc" in tonie_type_raw or tonie_type_raw in ("tonieplay",):
                        hh_data["discs"][t_id] = {
                            "id": t_id,
                            "name": tonie.get("name", t_id),
                            "image_url": image_url,
                            "household_id": hh_id,
                            "sales_id": tonie.get("salesId") or tonie.get("sales_id"),
                            "item_id": tonie.get("itemId") or tonie.get("item_id"),
                            "locked": tonie.get("locked", tonie.get("lock", False)),
                            "language": tonie.get("language"),
                            "toniebox_id": tonie.get("tonieboxId") or tonie.get("toniebox_id"),
                        }
                    elif "content" in tonie_type_raw:
                        hh_data["contenttonies"][t_id] = {
                            "id": t_id,
                            "name": tonie.get("name", t_id),
                            "image_url": image_url,
                            "household_id": hh_id,
                            "sales_id": tonie.get("salesId") or tonie.get("sales_id"),
                            "item_id": tonie.get("itemId") or tonie.get("item_id"),
                            "locked": tonie.get("locked", tonie.get("lock", False)),
                            "language": tonie.get("language"),
                            "chapters": chapters,
                            "chapter_count": len(chapters),
                            "total_seconds": sum(c["seconds"] for c in chapters),
                            "transcoding": tonie.get("transcoding", False),
                            "transcoding_errors": tonie.get("transcodingErrors", []),
                            "toniebox_id": tonie.get("tonieboxId") or tonie.get("toniebox_id"),
                            "tune_id": tonie.get("tuneId") or tonie.get("tune_id"),
                        }
                    else:
                        # "creative" or unknown type → creative tonie bucket
                        hh_data["creativetonies"][t_id] = {
                            "id": t_id,
                            "name": tonie.get("name", t_id),
                            "image_url": image_url,
                            "chapters": chapters,
                            "chapter_count": len(chapters),
                            "total_seconds": sum(c["seconds"] for c in chapters),
                            "household_id": hh_id,
                            "live": tonie.get("live", False),
                            "private": tonie.get("private", False),
                            "transcoding": tonie.get("transcoding", False),
                        }

            except Exception as e:
                _LOGGER.warning("Could not fetch creative tonies for %s: %s", hh_id, e)

            # ── Content Tonies, Discs & Placement via GraphQL ─────────────────
            # The official API doc states: "We use GraphQL for read-only requests".
            # The REST list endpoints for content tonies and discs return 404, and
            # the Toniebox REST response contains no placement data.
            # All three are available via GraphQL at /v2/graphql.
            gql_placements: dict[str, dict] = {}  # box_id → placement dict
            try:
                # The GraphQL API uses Relay-style pagination: each "my*" query
                # returns a Connection type with edges[].node instead of a plain list.
                # Field names verified via schema introspection (see
                # tests/gql_introspect*.py). Content tonies use `title` +
                # `series { name }` (there is no `name`), `lock` (not `locked`),
                # and `languageName`. Discs use `title`/`coverImageUrl`. The
                # Toniebox node has NO `placement` field — placement comes from
                # ICI (see _on_ici_message), so it is not queried here.
                gql_resp = await self.client.graphql_query("""
                    {
                      myContentTonies {
                        edges {
                          node {
                            id
                            householdId
                            title
                            imageUrl
                            coverUrl
                            lock
                            languageName
                            salesId
                            series { name }
                            chapters { id title seconds transcoding }
                          }
                        }
                      }
                      myDiscs {
                        edges {
                          node {
                            id
                            householdId
                            title
                            coverImageUrl
                            discImageUrl
                            lock
                            language
                            salesId
                          }
                        }
                      }
                    }
                """)
                gql_errors = gql_resp.get("errors")
                if gql_errors:
                    _LOGGER.debug("GraphQL returned errors: %s", gql_errors)
                gql_data = gql_resp.get("data") or {}

                def _relay_nodes(connection) -> list:
                    """Extract node list from a Relay Connection or plain list."""
                    if isinstance(connection, list):
                        return connection
                    if isinstance(connection, dict):
                        edges = connection.get("edges") or []
                        return [e["node"] for e in edges if isinstance(e, dict) and isinstance(e.get("node"), dict)]
                    return []

                # Content Tonies
                for tonie in _relay_nodes(gql_data.get("myContentTonies")):
                    if tonie.get("householdId") != hh_id:
                        continue
                    t_id = tonie.get("id", "")
                    if not t_id or t_id in hh_data["contenttonies"]:
                        continue
                    chapters = [
                        {
                            "id": ch.get("id", ""),
                            "title": ch.get("title", ""),
                            "seconds": ch.get("seconds", 0),
                            "transcoding": ch.get("transcoding", False),
                        }
                        for ch in (tonie.get("chapters") or [])
                        if isinstance(ch, dict)
                    ]
                    series_name = (tonie.get("series") or {}).get("name")
                    hh_data["contenttonies"][t_id] = {
                        "id": t_id,
                        # title is the specific content name (e.g. "Schlummerjaguar
                        # - …"); series.name is the product line ("Schlummerbande").
                        "name": tonie.get("title") or series_name or t_id,
                        "series": series_name,
                        "image_url": tonie.get("imageUrl") or tonie.get("coverUrl"),
                        "household_id": hh_id,
                        "locked": tonie.get("lock", False),
                        "language": tonie.get("languageName"),
                        "chapters": chapters,
                        "chapter_count": len(chapters),
                        "total_seconds": sum(c["seconds"] for c in chapters),
                        "transcoding": False,
                        "transcoding_errors": [],
                        "tune_id": None,
                        "sales_id": tonie.get("salesId"),
                        "item_id": None,
                        "toniebox_id": None,
                    }

                # Discs
                for disc in _relay_nodes(gql_data.get("myDiscs")):
                    if disc.get("householdId") != hh_id:
                        continue
                    d_id = disc.get("id", "")
                    if not d_id or d_id in hh_data["discs"]:
                        continue
                    hh_data["discs"][d_id] = {
                        "id": d_id,
                        "name": disc.get("title") or d_id,
                        "image_url": disc.get("coverImageUrl") or disc.get("discImageUrl"),
                        "household_id": hh_id,
                        "locked": disc.get("lock", False),
                        "language": disc.get("language"),
                        "sales_id": disc.get("salesId"),
                        "item_id": None,
                        "toniebox_id": None,
                    }
                # Note: placement is NOT available via GraphQL (the Toniebox node
                # has no such field); it is provided in real time by ICI instead.

            except Exception as e:
                _LOGGER.debug("GraphQL query failed for %s: %s", hh_id, e)

            _LOGGER.info(
                "household %s: %d creative, %d content, %d discs",
                hh_id,
                len(hh_data["creativetonies"]),
                len(hh_data["contenttonies"]),
                len(hh_data["discs"]),
            )

            # Tonieboxes
            try:
                boxes = await self.client.get_tonieboxes(hh_id)
                for box in boxes:
                    b_id = box.get("id", "")
                    if not b_id:
                        continue

                    # Previous coordinator data for this box — holds the ICI
                    # real-time values (battery, online, placement) that REST/
                    # GraphQL don't reliably provide.
                    prev_tb = (
                        (self.data or {})
                        .get("households", {}).get(hh_id, {})
                        .get("tonieboxes", {}).get(b_id, {})
                    )

                    # REST API does not include placement, and GraphQL returns it
                    # only for some accounts (400 for others). Fall back to the ICI
                    # real-time placement (set by _on_ici_message) so the currently
                    # placed Tonie survives a poll cycle instead of being wiped to {}.
                    placement = (
                        gql_placements.get(b_id)
                        or box.get("placement")
                        or prev_tb.get("placement")
                        or {}
                    )
                    placed_tonie = placement.get("tonie") or {}

                    # Normalize: API may return tonieId/tonie_id/id flat instead of
                    # a nested "tonie" sub-object.  Build a synthetic tonie dict and
                    # inject it back so all downstream code can use placement["tonie"].
                    if not placed_tonie.get("id"):
                        flat_id = (
                            placement.get("tonieId")
                            or placement.get("tonie_id")
                            or placement.get("id")
                        )
                        if flat_id:
                            placed_tonie = {
                                "id": flat_id,
                                "name": (
                                    placement.get("tonieName")
                                    or placement.get("name")
                                ),
                                "imageUrl": (
                                    placement.get("tonieImageUrl")
                                    or placement.get("imageUrl")
                                    or placement.get("image_url")
                                ),
                                "type": (
                                    placement.get("tonieType")
                                    or placement.get("type")
                                ),
                            }
                            placement = {**placement, "tonie": placed_tonie}

                    # Playback info — only fetch when a tonie is actively placed
                    playback_info: dict = {}
                    if placed_tonie and placed_tonie.get("id"):
                        try:
                            playback_info = await self.client.get_playback_info(
                                b_id, placed_tonie["id"]
                            )
                        except Exception as e:
                            _LOGGER.debug(
                                "Playback info not available for box %s: %s", b_id, e
                            )

                    # If placed tonie is not a known creative tonie, add it to
                    # contenttonies or discs (derived from placement + playback_info)
                    if isinstance(placed_tonie, dict) and placed_tonie.get("id"):
                        placed_id = placed_tonie["id"]
                        already_known = (
                            placed_id in hh_data["creativetonies"]
                            or placed_id in hh_data["contenttonies"]
                            or placed_id in hh_data["discs"]
                        )
                        if not already_known:
                            pi_type = (
                                playback_info.get("tonieType")
                                or playback_info.get("type")
                                or placed_tonie.get("type")
                                or placed_tonie.get("tonieType")
                                or "content"
                            ).lower()
                            image_url = (
                                playback_info.get("tonieImageUrl")
                                or playback_info.get("coverUrl")
                                or placed_tonie.get("imageUrl")
                                or placed_tonie.get("image_url")
                            )
                            # API: series = Tonie character name (e.g. "Benjamin Blümchen")
                            #      title  = content title (longer form)
                            name = (
                                placed_tonie.get("name")
                                or playback_info.get("series")
                                or playback_info.get("title")
                                or placed_id
                            )
                            _LOGGER.debug(
                                "Adding %s tonie %s (%s) from placement on box %s",
                                pi_type, placed_id, name, b_id,
                            )
                            entry = {
                                "id": placed_id,
                                "name": name,
                                "image_url": image_url,
                                "household_id": hh_id,
                                "toniebox_id": b_id,
                            }
                            if pi_type == "disc":
                                hh_data["discs"][placed_id] = {
                                    **entry,
                                    "locked": False,
                                    "language": None,
                                    "sales_id": None,
                                    "item_id": None,
                                }
                            else:
                                hh_data["contenttonies"][placed_id] = {
                                    **entry,
                                    "chapters": [],
                                    "chapter_count": 0,
                                    "total_seconds": 0,
                                    "locked": False,
                                    "language": None,
                                    "transcoding": False,
                                    "transcoding_errors": [],
                                    "tune_id": None,
                                    "sales_id": None,
                                    "item_id": None,
                                }

                    # Enrich placed tonie with name/image from known tonies
                    if isinstance(placed_tonie, dict) and placed_tonie.get("id"):
                        placed_id = placed_tonie["id"]
                        known = (
                            hh_data["creativetonies"].get(placed_id)
                            or hh_data["contenttonies"].get(placed_id)
                            or hh_data["discs"].get(placed_id)
                        )
                        if known:
                            placed_tonie["name"] = placed_tonie.get("name") or known.get("name")
                            placed_tonie["imageUrl"] = placed_tonie.get("imageUrl") or known.get("image_url")

                    # Preserve ICI real-time online state across REST polling
                    # (prev_tb was looked up above, before placement resolution).
                    ici_online = prev_tb.get("online_state")
                    rest_online = box.get("onlineState")
                    # Keep ICI value if REST returns "unsupported" or None
                    effective_online = (
                        ici_online
                        if ici_online in ("connected", "offline") and rest_online in (None, "unsupported")
                        else rest_online
                    )

                    hh_data["tonieboxes"][b_id] = {
                        # Identity
                        "id": b_id,
                        "name": box.get("name", b_id),
                        "household_id": hh_id,
                        "image_url": box.get("imageUrl") or box.get("image_url"),
                        "generation": box.get("generation"),
                        "product": box.get("product"),
                        "features": box.get("features", []),
                        # State
                        "online_state": effective_online,
                        # ICI real-time data (preserved across REST polling)
                        "battery": prev_tb.get("battery"),
                        "last_battery": prev_tb.get("last_battery"),
                        "last_online_at": prev_tb.get("last_online_at"),
                        "headphones": prev_tb.get("headphones"),
                        "offline_mode": box.get("offlineMode", False),
                        "firmware_version": box.get("firmwareVersion"),
                        "ssid": box.get("ssid"),
                        "ble_color_id": box.get("bleColorId"),
                        "mac_address": box.get("macAddress"),
                        "item_id": box.get("itemId"),
                        "last_seen": box.get("last_seen"),
                        "settings_applied": box.get("settingsApplied", True),
                        "registered_at": box.get("registeredAt"),
                        # LED
                        "led_level": box.get("ledLevel"),
                        "lightring_brightness": box.get("lightringBrightness"),
                        # Bedtime (tng only)
                        "bedtime_lightring_brightness": box.get("bedtimeLightringBrightness"),
                        "bedtime_lightring_color": box.get("bedtimeLightringColor"),
                        "bedtime_max_volume": box.get("bedtimeMaxVolume"),
                        "bedtime_max_headphone_volume": box.get("bedtimeMaxHeadphoneVolume"),
                        # Playback behaviour
                        "skipping_enabled": box.get("skippingEnabled"),
                        "skipping_direction": box.get("skippingDirection"),
                        "scrubbing_enabled": box.get("scrubbingEnabled"),
                        # Volume limits
                        "max_volume": box.get("maxVolume"),
                        "max_headphone_volume": box.get("maxHeadphoneVolume"),
                        # Older boxes only
                        "accelerometer_enabled": box.get("accelerometerEnabled"),
                        "tap_direction": box.get("tapDirection"),
                        # Language / locale
                        "language": box.get("language"),
                        "timezone": box.get("timezone"),
                        "age_mode": box.get("ageMode"),
                        # Legacy / unchanged
                        "firmware": box.get("firmware", {}),
                        "placement": placement,
                        # Live playback state from ICI (position/chapter/paused);
                        # REST/GraphQL don't provide it, so carry it across polls.
                        "playback_state": prev_tb.get("playback_state") or {},
                        # Live playback volume from ICI (level/hardware %).
                        "volume": prev_tb.get("volume") or {},
                        # Live sleep-timer state from ICI (stl).
                        "sleep_timer": prev_tb.get("sleep_timer") or {},
                        "extras": box.get("extras", {}),
                        "playback_info": playback_info,
                    }
            except Exception as e:
                _LOGGER.debug("Could not fetch tonieboxes for %s: %s", hh_id, e)

            # Children
            try:
                hh_data["children"] = await self.client.get_children(hh_id)
            except Exception as e:
                _LOGGER.debug("Could not fetch children for %s: %s", hh_id, e)

            # Memberships
            try:
                hh_data["memberships"] = await self.client.get_memberships(hh_id)
            except Exception as e:
                _LOGGER.debug("Could not fetch memberships for %s: %s", hh_id, e)

            result["households"][hh_id] = hh_data

        return result