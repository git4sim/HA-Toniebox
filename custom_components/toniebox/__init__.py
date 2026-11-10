"""The Toniebox integration — full API v2 with ICI real-time push."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, SupportsResponse, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, CONF_USERNAME, CONF_PASSWORD, UPDATE_INTERVAL_MINUTES,
    ICI_TOPIC_BATTERY, ICI_TOPIC_ONLINE, ICI_TOPIC_HEADPHONES, ICI_TOPIC_SETTINGS,
    ICI_TOPIC_PLAYBACK, ICI_TOPIC_VOLUME, ICI_TOPIC_BEDTIME,
    ICI_CMD_PLAYBACK, ICI_CMD_VOLUME, ICI_VOLUME_MAX_LEVEL,
    ICI_CMD_SLEEP_TIMER, ICI_CMD_SLEEP_NOW,
    SORT_BY_RANDOM, STORAGE_VERSION, STORAGE_KEY_SHUFFLE,
    STORAGE_KEY_VOLUME_BOOST,
    VOLUME_MULTIPLIER_MIN, VOLUME_MULTIPLIER_MAX,
    BOOST_SETTINGS_TIMEOUT, BOOST_SETTLE_DELAY, BOOST_LEVEL_WAIT, BOOST_LEVEL_ATTEMPTS,
    is_tng_box,
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

    # Load persisted "shuffle on swap" state (switches + last Tonie per box)
    # and the volume-boost state before the first refresh, so a swap done
    # while HA was down is detected and a pending boost can be undone.
    await coordinator.async_load_shuffle()

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Could not fetch data: {err}") from err

    # Start ICI real-time connection for TNG boxes
    await coordinator.async_start_ici()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Remove devices of Tonies / Tonieboxes that are no longer part of the
    # household (instead of leaving them behind as "unavailable"). Runs once
    # now and after every successful cloud poll.
    coordinator.async_remove_stale_devices()
    entry.async_on_unload(
        coordinator.async_add_listener(coordinator.async_remove_stale_devices)
    )

    _register_services(hass)
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow manual removal of a device that is no longer in the Tonie Cloud.

    Devices that still exist in the household are refused, because they would
    be re-created on the next poll anyway.
    """
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None or not coordinator.data:
        return True
    active = coordinator.active_device_identifiers()
    return not any(
        domain == DOMAIN and ident in active
        for domain, ident in device_entry.identifiers
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator:
        await coordinator.async_stop_ici()
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


def _read_file(path: str) -> bytes | None:
    """Read a file outside the event loop (used via async_add_executor_job).

    Returns None if the path is not a regular file.
    """
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return f.read()


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
            vol.Optional("sort_by", default="title"): vol.In(["title", "filename", "date", "random"]),
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

        client, hh_id, t_id = await _find_creative_tonie(hass, entity_id)
        if not client:
            _LOGGER.error("upload_audio: entity not found: %s", entity_id)
            return

        filename = os.path.basename(file_path)
        if not title:
            title = os.path.splitext(filename)[0]

        # isfile() is blocking I/O too, so it runs in the executor with the read.
        file_data = await hass.async_add_executor_job(_read_file, file_path)
        if file_data is None:
            raise ServiceValidationError(f"upload_audio: file not found: {file_path}")

        try:
            await client.upload_and_add_chapter(hh_id, t_id, file_data, filename, title)
            await _refresh_all(hass)
            _LOGGER.info("upload_audio: successfully uploaded '%s' to %s", filename, entity_id)
        except Exception as err:
            _LOGGER.error("upload_audio failed for %s: %s", file_path, err)

    # Admin-only: the service reads an arbitrary path on the host and sends it
    # to the Tonie Cloud, so non-admin users must not be able to call it.
    async_register_admin_service(
        hass, DOMAIN, "upload_audio", handle_upload_audio,
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
        if not is_tng_box(tb):
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
            alarm = call.data.get("alarm")
            coordinator.ici_set_sleep_timer(
                mac,
                minutes * 60,
                {
                    "morningLight": bool(alarm.get("morning_light", True)),
                    "tone": alarm.get("tone", "alarmLoop1.opus"),
                    "volume": int(alarm.get("volume", 100)),
                } if alarm else None,
                bool(call.data.get("one_time_alarm", False)),
            )

    hass.services.async_register(
        DOMAIN, "sleeptimer", handle_sleeptimer,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=0, max=1092)),
            vol.Optional("one_time_alarm", default=False): bool,
            vol.Optional("alarm"): vol.Schema({
                vol.Optional("tone", default="alarmLoop1.opus"): str,
                vol.Optional("volume", default=100): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                vol.Optional("morning_light", default=True): bool,
            }),
        }),
    )

    schedule_fields = {
        "name": "name", "sleep_time": "sleepTime", "wakeup_time": "wakeupTime", "days": "days",
        "enabled": "enabled", "alarm_enabled": "alarmEnabled", "alarm_morning_light": "alarmMorningLight",
        "alarm_tone": "alarmTone", "alarm_volume": "alarmVolume",
    }

    async def handle_set_bedtime_schedule(call):
        client, hh_id, tb_id = await _find_toniebox(hass, call.data["entity_id"])
        if not client:
            raise ServiceValidationError(f"{call.data['entity_id']} is not a Toniebox")
        payload = {api: call.data[key] for key, api in schedule_fields.items() if key in call.data}
        if "schedule_id" in call.data:
            result = await client.patch_bedtime_schedule(hh_id, tb_id, call.data["schedule_id"], payload)
        else:
            result = await client.create_bedtime_schedule(hh_id, tb_id, payload)
        await _refresh_all(hass)
        return result if isinstance(result, dict) else {}

    async def handle_delete_bedtime_schedule(call):
        client, hh_id, tb_id = await _find_toniebox(hass, call.data["entity_id"])
        if not client:
            raise ServiceValidationError(f"{call.data['entity_id']} is not a Toniebox")
        await client.delete_bedtime_schedule(hh_id, tb_id, call.data["schedule_id"])
        await _refresh_all(hass)

    hass.services.async_register(
        DOMAIN, "set_bedtime_schedule", handle_set_bedtime_schedule,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Optional("schedule_id"): cv.string,
            vol.Optional("name"): cv.string,
            vol.Optional("sleep_time"): vol.All(cv.time, lambda t: t.strftime("%H:%M")),
            vol.Optional("wakeup_time"): vol.All(cv.time, lambda t: t.strftime("%H:%M")),
            vol.Optional("days"): [vol.In(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])],
            vol.Optional("enabled"): cv.boolean,
            vol.Optional("alarm_enabled"): cv.boolean,
            vol.Optional("alarm_morning_light"): cv.boolean,
            vol.Optional("alarm_tone"): cv.string,
            vol.Optional("alarm_volume"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        }),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, "delete_bedtime_schedule", handle_delete_bedtime_schedule,
        schema=vol.Schema({
            vol.Required("entity_id"): cv.string,
            vol.Required("schedule_id"): cv.string,
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
        self._token_refresh_unsub: CALLBACK_TYPE | None = None
        self._mac_to_tb: dict[str, tuple[str, str]] = {}  # mac → (hh_id, tb_id)
        # ── Shuffle on swap ──
        # Persisted per-Creative-Tonie toggle (tonie_id → bool).
        self.shuffle_enabled: dict[str, bool] = {}
        self._shuffle_store: Store | None = None
        # Last Tonie that was on each box (box_id → tonie_id). Deliberately NOT
        # cleared when the box goes empty: the normal swap is "lift A off, put
        # B on", so the predecessor must survive the empty phase. Persisted.
        self._last_placed: dict[str, str] = {}
        # Boxes whose placement is delivered in real time via ICI. For these the
        # (slower, possibly stale) poll result is not used for swap detection.
        self._ici_placement_boxes: set[str] = set()
        # Creative Tonies with a shuffle currently in flight (dedupe).
        self._shuffle_in_flight: set[str] = set()
        self._stale_retry = False
        # ── Volume boost per Tonie ──
        # tonie_id → multiplier (> 1.0 = louder). Persisted.
        self.volume_multipliers: dict[str, float] = {}
        # Boost currently applied per box, persisted so it can be undone even
        # after a restart: tb_id → {tonie_id, factor, orig_max, boosted_max,
        # orig_level, boosted_level}.
        self._active_boosts: dict[str, dict] = {}
        self._boost_locks: dict[str, asyncio.Lock] = {}
        self._boost_store: Store | None = None
        # Signals from the box (ICI): settings applied / volume reported.
        self._settings_events: dict[str, asyncio.Event] = {}
        self._volume_events: dict[str, asyncio.Event] = {}
        # Last volume level seen per box (persisted fallback after a restart).
        self._last_levels: dict[str, int] = {}
        # ── Stale device cleanup ──
        # Incremented on every completed cloud poll; cleanup runs once per poll
        # (not on every ICI push, which also notifies coordinator listeners).
        self._poll_seq = 0
        self._cleanup_seq = -1
        super().__init__(
            hass, _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )

    # ── Shuffle on swap ────────────────────────────────────────────────────────

    async def async_load_shuffle(self) -> None:
        """Load persisted 'shuffle on swap' switch states from the Store."""
        self._shuffle_store = Store(
            self.hass, STORAGE_VERSION, f"{STORAGE_KEY_SHUFFLE}_{self.entry.entry_id}"
        )
        try:
            stored = await self._shuffle_store.async_load()
        except Exception:
            _LOGGER.warning("Could not load shuffle-on-swap state", exc_info=True)
            stored = None
        stored = stored or {}
        enabled = stored.get("shuffleEnabled")
        if isinstance(enabled, dict):
            self.shuffle_enabled = {k: bool(v) for k, v in enabled.items()}
        last = stored.get("lastPlaced")
        if isinstance(last, dict):
            self._last_placed = {k: v for k, v in last.items() if isinstance(v, str) and v}

        # Volume boost state lives in its own store.
        self._boost_store = Store(
            self.hass, STORAGE_VERSION, f"{STORAGE_KEY_VOLUME_BOOST}_{self.entry.entry_id}"
        )
        try:
            boost = await self._boost_store.async_load() or {}
        except Exception:
            _LOGGER.warning("Could not load volume-boost state", exc_info=True)
            boost = {}
        mult = boost.get("multipliers")
        if isinstance(mult, dict):
            self.volume_multipliers = {
                k: float(v) for k, v in mult.items() if isinstance(v, (int, float))
            }
        levels = boost.get("lastLevels")
        if isinstance(levels, dict):
            self._last_levels = {
                k: int(v) for k, v in levels.items() if isinstance(v, (int, float))
            }
        active = boost.get("active")
        if isinstance(active, dict):
            self._active_boosts = {
                k: v for k, v in active.items() if isinstance(v, dict) and v.get("tonie_id")
            }

    def _save_boost_state(self) -> None:
        if self._boost_store:
            # Write immediately (no long delay): this is what lets us undo a
            # boost after a crash/restart.
            self._boost_store.async_delay_save(
                lambda: {
                    "multipliers": self.volume_multipliers,
                    "active": self._active_boosts,
                    "lastLevels": self._last_levels,
                },
                0,
            )

    # ── Volume boost per Tonie ─────────────────────────────────────────────────

    def get_volume_multiplier(self, tonie_id: str) -> float:
        return float(self.volume_multipliers.get(tonie_id, 1.0))

    async def async_set_volume_multiplier(self, tonie_id: str, factor: float) -> None:
        """Set a Tonie's multiplier and re-apply it if it is currently placed."""
        factor = round(max(VOLUME_MULTIPLIER_MIN, min(VOLUME_MULTIPLIER_MAX, factor)), 2)
        if factor == 1.0:
            self.volume_multipliers.pop(tonie_id, None)
        else:
            self.volume_multipliers[tonie_id] = factor
        self._save_boost_state()
        # Boxes where this Tonie sits (or is currently boosted) → reconcile.
        for hh_id, hh in (self.data or {}).get("households", {}).items():
            for tb_id, tb in hh.get("tonieboxes", {}).items():
                active = self._active_boosts.get(tb_id) or {}
                if self._placed_tonie_id(tb) == tonie_id or active.get("tonie_id") == tonie_id:
                    if active.get("tonie_id") == tonie_id:
                        # Undo the old factor first, then apply the new one.
                        await self._async_sync_volume_boost(hh_id, tb_id, force_revert=True)
                    await self._async_sync_volume_boost(hh_id, tb_id)

    def _schedule_volume_sync(self, tb_id: str) -> None:
        """Reconcile the volume boost of a box after its placement changed."""
        for hh_id, hh in (self.data or {}).get("households", {}).items():
            if tb_id in hh.get("tonieboxes", {}):
                self.hass.async_create_task(self._async_sync_volume_boost(hh_id, tb_id))
                return

    @staticmethod
    def _boost_max_volume(orig: int, factor: float) -> int:
        """orig × factor, capped at 100 % (the box accepts any value 1–100)."""
        return max(1, min(100, round(orig * factor)))

    @staticmethod
    def _rescale_level(level: float, max_before: float, max_after: float, factor: float) -> int:
        """Level that gives `factor` × the loudness of `level` after a max change.

        The box's volume level is RELATIVE to its max volume (13 = 100 % of the
        max). Loudness ≈ level/13 × max, so the new level is
        level × max_before × factor / max_after. (Verified on a live box: max
        52 → 100 made the box re-report level 12 as 7 — same loudness.)
        """
        if not max_after:
            return int(level)
        target = round(level * max_before * factor / max_after)
        return max(1, min(ICI_VOLUME_MAX_LEVEL, target))

    async def _async_sync_volume_boost(
        self, hh_id: str, tb_id: str, force_revert: bool = False
    ) -> None:
        """Make the box's volume match the Tonie currently on it.

        Idempotent: compares the persisted active boost with the Tonie placed
        right now. Runs serialized per box so fast swaps can't interleave.
        """
        lock = self._boost_locks.setdefault(tb_id, asyncio.Lock())
        async with lock:
            tb = (
                (self.data or {}).get("households", {}).get(hh_id, {})
                .get("tonieboxes", {}).get(tb_id)
            )
            if tb is None:
                return
            current = self._placed_tonie_id(tb)
            active = self._active_boosts.get(tb_id)

            # 1) Undo a boost that no longer belongs to the placed Tonie.
            if active and (force_revert or active.get("tonie_id") != current):
                await self._async_revert_boost(hh_id, tb_id, tb, active)
                if tb_id in self._active_boosts:
                    return  # undo failed → keep record, retry on next sync
                active = None

            # 2) Apply the boost for the newly placed Tonie.
            if active or not current:
                return
            factor = self.get_volume_multiplier(current)
            if factor <= 1.0:
                return
            await self._async_apply_boost(hh_id, tb_id, tb, current, factor)

    async def _async_change_max_and_wait(
        self, hh_id: str, tb_id: str, tb: dict, new_max: int
    ) -> bool:
        """PATCH the max volume, then wait until the box has applied it.

        The PATCH only reaches the cloud; the box gets the new limit a few
        seconds later and then re-reports its (rescaled) volume level. Any level
        we send before that would be overwritten by that rescale.
        """
        vol_ev = self._box_event(self._volume_events, tb_id)
        vol_ev.clear()
        try:
            await self.client.patch_toniebox(hh_id, tb_id, {"maxVolume": new_max})
        except Exception as err:
            _LOGGER.warning("Volume boost: could not set max volume %s on %s: %s",
                            new_max, tb_id, err)
            return False
        tb["max_volume"] = new_max
        live = self._get_tb(hh_id, tb_id)
        if live is not None:
            live["max_volume"] = new_max
        try:
            await asyncio.wait_for(vol_ev.wait(), BOOST_SETTINGS_TIMEOUT)
            _LOGGER.debug("Volume boost: box %s applied max %s (now reports level %s)",
                          tb_id, new_max, self._current_level(hh_id, tb_id))
        except asyncio.TimeoutError:
            _LOGGER.debug("Volume boost: box %s sent no volume update within %ss after max change",
                          tb_id, BOOST_SETTINGS_TIMEOUT)
        await asyncio.sleep(BOOST_SETTLE_DELAY)
        return True

    async def _async_apply_boost(
        self, hh_id: str, tb_id: str, tb: dict, tonie_id: str, factor: float
    ) -> None:
        orig_max = tb.get("max_volume")
        # Level BEFORE the max change (the box rescales it afterwards).
        level = self._current_level(hh_id, tb_id)
        if level is None:
            level = await self._async_wait_for_level(hh_id, tb_id, BOOST_LEVEL_WAIT)
        if level is None:
            level = self._last_levels.get(tb_id)

        record: dict = {"tonie_id": tonie_id, "factor": factor}
        if isinstance(orig_max, (int, float)):
            record["orig_max"] = int(orig_max)
            record["boosted_max"] = self._boost_max_volume(int(orig_max), factor)
        if level is not None:
            record["orig_level"] = int(level)
        # Persist BEFORE changing anything, so it can always be undone.
        self._active_boosts[tb_id] = record
        self._save_boost_state()

        # ── Step 1: max volume, and wait until the box has applied it ──
        max_before = record.get("orig_max")
        max_after = max_before
        if max_before is not None and record["boosted_max"] != max_before:
            if await self._async_change_max_and_wait(hh_id, tb_id, tb, record["boosted_max"]):
                max_after = record["boosted_max"]
            else:
                record["boosted_max"] = max_before
            self._save_boost_state()

        if self._placed_tonie_id(self._get_tb(hh_id, tb_id) or {}) != tonie_id:
            _LOGGER.debug("Volume boost: Tonie %s left box %s before level change", tonie_id, tb_id)
            return

        # ── Step 2: current volume — only now, after the box's rescale ──
        if level is None:
            _LOGGER.warning(
                "Volume boost: current volume of box %s unknown — only max volume "
                "was raised. Change the volume once on the box so it gets known.",
                tb_id,
            )
        else:
            target = self._rescale_level(level, max_before or 100, max_after or 100, factor)
            record["boosted_level"] = target
            self._save_boost_state()
            await self._async_set_level_verified(hh_id, tb_id, target)
        self._save_boost_state()
        _LOGGER.info(
            "Volume boost ×%s for Tonie %s on box %s: max %s→%s, level %s→%s",
            factor, tonie_id, tb_id,
            record.get("orig_max"), record.get("boosted_max"),
            record.get("orig_level"), record.get("boosted_level"),
        )
        self.async_update_listeners()

    def _get_tb(self, hh_id: str, tb_id: str) -> dict | None:
        """Fresh box dict (a poll replaces the whole data tree)."""
        return (
            (self.data or {}).get("households", {}).get(hh_id, {})
            .get("tonieboxes", {}).get(tb_id)
        )

    def _current_level(self, hh_id: str, tb_id: str) -> int | None:
        level = ((self._get_tb(hh_id, tb_id) or {}).get("volume") or {}).get("level")
        return int(level) if isinstance(level, (int, float)) else None

    @staticmethod
    def _box_event(store: dict, tb_id: str) -> asyncio.Event:
        ev = store.get(tb_id)
        if ev is None:
            ev = store[tb_id] = asyncio.Event()
        return ev

    async def _async_wait_for_level(self, hh_id: str, tb_id: str, timeout: float) -> int | None:
        ev = self._box_event(self._volume_events, tb_id)
        ev.clear()
        try:
            await asyncio.wait_for(ev.wait(), timeout)
        except asyncio.TimeoutError:
            pass
        return self._current_level(hh_id, tb_id)

    async def _async_set_level_verified(self, hh_id: str, tb_id: str, target: int) -> bool:
        """Send a volume level and make sure it sticks.

        Checks the box's echo, then watches a little longer: a late rescale
        from a max change would overwrite our level, so we re-send if needed.
        """
        for attempt in range(1, BOOST_LEVEL_ATTEMPTS + 1):
            if self._current_level(hh_id, tb_id) != target:
                tb = self._get_tb(hh_id, tb_id) or {}
                ev = self._box_event(self._volume_events, tb_id)
                ev.clear()
                if not self.ici_set_volume_level(tb.get("mac_address") or "", target):
                    return False
                try:
                    await asyncio.wait_for(ev.wait(), BOOST_LEVEL_WAIT)
                except asyncio.TimeoutError:
                    pass
            # Stability check: does it stay there?
            ev = self._box_event(self._volume_events, tb_id)
            ev.clear()
            try:
                await asyncio.wait_for(ev.wait(), BOOST_SETTLE_DELAY * 2)
            except asyncio.TimeoutError:
                pass
            reported = self._current_level(hh_id, tb_id)
            if reported == target:
                _LOGGER.debug("Volume boost: box %s stays at level %s", tb_id, target)
                return True
            _LOGGER.debug(
                "Volume boost: box %s reports level %s instead of %s (attempt %s)",
                tb_id, reported, target, attempt,
            )
        _LOGGER.warning(
            "Volume boost: box %s did not keep level %s (reports %s)",
            tb_id, target, self._current_level(hh_id, tb_id),
        )
        return False

    async def _async_revert_boost(self, hh_id: str, tb_id: str, tb: dict, active: dict) -> None:
        """Restore exactly the max volume and level from before the boost.

        Same order as applying: max first, wait for the box's rescale, then
        set the level (otherwise the rescale would overwrite it).
        """
        tb = self._get_tb(hh_id, tb_id) or tb
        orig_max = active.get("orig_max")
        boosted_max = active.get("boosted_max")
        ok = True

        if orig_max is not None and boosted_max is not None and boosted_max != orig_max:
            cur_max = tb.get("max_volume")
            # Changed by hand in the meantime → leave the user's value alone.
            if cur_max is None or cur_max == boosted_max:
                ok = await self._async_change_max_and_wait(hh_id, tb_id, tb, orig_max)

        if ok and active.get("orig_level") is not None:
            await self._async_set_level_verified(hh_id, tb_id, int(active["orig_level"]))

        if ok:
            self._active_boosts.pop(tb_id, None)
            self._save_boost_state()
            _LOGGER.info(
                "Volume boost undone for Tonie %s on box %s (max %s, level %s)",
                active.get("tonie_id"), tb_id, orig_max, active.get("orig_level"),
            )
        self.async_update_listeners()

    def _save_shuffle_state(self) -> None:
        if self._shuffle_store:
            self._shuffle_store.async_delay_save(
                lambda: {
                    "shuffleEnabled": self.shuffle_enabled,
                    "lastPlaced": self._last_placed,
                },
                1,
            )

    def is_shuffle_enabled(self, tonie_id: str) -> bool:
        """Return True if 'shuffle on swap' is active for this Creative Tonie."""
        return bool(self.shuffle_enabled.get(tonie_id))

    async def async_set_shuffle_enabled(self, tonie_id: str, enabled: bool) -> None:
        """Persist the 'shuffle on swap' toggle for a Creative Tonie."""
        self.shuffle_enabled[tonie_id] = enabled
        self._save_shuffle_state()

    def _find_creative_tonie(self, tonie_id: str, data: dict) -> tuple[str | None, dict | None]:
        """Return (household_id, tonie_dict) for a Creative Tonie id, or (None, None)."""
        for hh_id, hh in (data or {}).get("households", {}).items():
            tonie = hh.get("creativetonies", {}).get(tonie_id)
            if tonie is not None:
                return hh_id, tonie
        return None, None

    @staticmethod
    def _placed_tonie_id(tb: dict) -> str | None:
        placed = (tb.get("placement") or {}).get("tonie") or {}
        return placed.get("id") if isinstance(placed, dict) else None

    def _is_placed_elsewhere(self, tonie_id: str, except_tb_id: str, data: dict) -> bool:
        """True if the Tonie currently sits on another box (moved, not swapped out)."""
        for hh in (data or {}).get("households", {}).values():
            for tb_id, tb in hh.get("tonieboxes", {}).items():
                if tb_id != except_tb_id and self._placed_tonie_id(tb) == tonie_id:
                    return True
        return False

    def _note_placement(self, tb_id: str, current_tonie_id: str | None, data: dict) -> None:
        """Update last-placed tracking for a box and shuffle the displaced Tonie.

        A shuffle is triggered when a Creative Tonie with the switch enabled
        (and ≥ 2 chapters) is followed on the same box by a *different* Tonie —
        no matter whether it was a direct swap or "lift off, (pause), put the
        next one on". Lifting a Tonie off and putting the *same* one back never
        shuffles, so it continues where it left off.
        """
        if not current_tonie_id:
            return  # box emptied → keep remembering the predecessor
        old_tonie_id = self._last_placed.get(tb_id)
        if old_tonie_id == current_tonie_id:
            return  # same Tonie back on the box → no change
        self._last_placed[tb_id] = current_tonie_id
        self._save_shuffle_state()
        if old_tonie_id is None:
            return  # first placement ever seen for this box → no predecessor
        _LOGGER.debug(
            "Tonie swap on box %s: %s → %s", tb_id, old_tonie_id, current_tonie_id
        )
        if not self.is_shuffle_enabled(old_tonie_id):
            return
        hh_id, tonie = self._find_creative_tonie(old_tonie_id, data)
        if tonie is None:
            return  # not a Creative Tonie (content tonies/discs can't be reordered)
        if self._is_placed_elsewhere(old_tonie_id, tb_id, data):
            return  # it was moved to another box and is playing there
        if old_tonie_id in self._shuffle_in_flight:
            return
        self._shuffle_in_flight.add(old_tonie_id)
        self.hass.async_create_task(self._async_shuffle_on_swap(hh_id, old_tonie_id))

    def _process_placements(self, data: dict) -> None:
        """Feed polled placements into the swap detector.

        Boxes with real-time ICI placement are skipped: a poll takes several
        seconds and may return a placement that is already outdated, which
        would look like a swap back and forth (wrong/double shuffles).
        """
        for hh in data.get("households", {}).values():
            for tb_id, tb in hh.get("tonieboxes", {}).items():
                if tb_id in self._ici_placement_boxes:
                    continue
                self._note_placement(tb_id, self._placed_tonie_id(tb), data)

    async def _async_shuffle_on_swap(self, hh_id: str, tonie_id: str) -> None:
        """Shuffle a Creative Tonie's chapters after it was swapped out."""
        try:
            # Re-check right before executing — state/content may have changed.
            if not self.is_shuffle_enabled(tonie_id):
                return
            found_hh, tonie = self._find_creative_tonie(tonie_id, self.data or {})
            hh_id = found_hh or hh_id
            if tonie is None:
                return
            # sort_chapters fetches the live chapter list itself and is a no-op
            # for < 2 chapters, so no reliance on possibly stale cached counts.
            await self.client.sort_chapters(hh_id, tonie_id, SORT_BY_RANDOM)
            _LOGGER.info(
                "Auto-shuffled chapters of Creative Tonie %s after it was swapped out",
                tonie_id,
            )
            await self.async_request_refresh()
        except Exception as err:
            _LOGGER.warning("Auto-shuffle failed for Creative Tonie %s: %s", tonie_id, err)
        finally:
            self._shuffle_in_flight.discard(tonie_id)

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
                        "features": tb.get("features", []),
                    })

            tng_boxes = [b for b in all_boxes if is_tng_box(b)]
            if not tng_boxes:
                _LOGGER.debug("No TNG boxes found, ICI not needed")
                return

            self.ici_client = TonieboxIciClient(
                on_message_callback=self._on_ici_message,
                loop=asyncio.get_running_loop(),
                on_auth_failed=self._on_ici_auth_failed,
            )
            self.client.add_token_listener(self.ici_client.on_token_refreshed)
            # The ICI broker drops the session once the token it connected with
            # expires; paho's auto-reconnect then retries with that expired token
            # and is rejected. Refresh ahead of expiry so ICI always reconnects
            # with a valid token instead of waiting for the next REST poll.
            self.client.add_token_listener(self._schedule_token_refresh)
            self._schedule_token_refresh()

            token = self.client.access_token
            if token:
                await self.ici_client.connect(user_uuid, token, all_boxes)
                _LOGGER.info("ICI MQTT started for %d TNG boxes", len(tng_boxes))
        except Exception:
            _LOGGER.warning("Failed to start ICI MQTT", exc_info=True)

    @callback
    def _schedule_token_refresh(self, _token: str | None = None, delay: float | None = None) -> None:
        """(Re)arm the proactive token refresh timer."""
        if self._token_refresh_unsub:
            self._token_refresh_unsub()
        if delay is None:
            delay = max(10.0, self.client.seconds_until_token_refresh())
        self._token_refresh_unsub = async_call_later(
            self.hass, delay, self._async_proactive_token_refresh
        )

    async def _async_proactive_token_refresh(self, _now) -> None:
        """Refresh the access token before it expires (keeps ICI authorised)."""
        self._token_refresh_unsub = None
        try:
            # On success the token listeners fire, which re-arms this timer and
            # reconnects ICI with the new token.
            await self.client.async_refresh_token()
        except Exception:
            _LOGGER.debug("Proactive token refresh failed, retrying in 60s", exc_info=True)
            self._schedule_token_refresh(delay=60)

    async def async_stop_ici(self) -> None:
        """Stop ICI and the proactive token refresh (config entry unload)."""
        if self._token_refresh_unsub:
            self._token_refresh_unsub()
            self._token_refresh_unsub = None
        self.client.remove_token_listener(self._schedule_token_refresh)
        if self.ici_client:
            await self.ici_client.disconnect()
            self.client.remove_token_listener(self.ici_client.on_token_refreshed)

    async def _on_ici_auth_failed(self) -> None:
        """Called by the ICI client when the MQTT broker rejects the access token.

        Forces an immediate REST token refresh instead of waiting for the next
        poll cycle; the refresh notifies the ICI client's token listener, which
        reconnects with the new token.
        """
        try:
            await self.client.async_refresh_token()
        except Exception:
            _LOGGER.debug("Proactive token refresh after ICI auth failure failed", exc_info=True)

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

    @staticmethod
    def _enrich_placed_tonie(tonie: dict, tb: dict, hh_data: dict) -> dict:
        """Fill name/image/type of an ICI-reported placed Tonie.

        ICI playback/state only carries the Tonie ID and is re-sent on every
        chapter change. Without this, each push would replace the enriched
        placement from the last poll with a bare {"id": ...}, so the current
        Tonie sensor drops to unknown until the follow-up refresh re-enriches it.
        """
        tonie_id = tonie.get("id")
        prev = (tb.get("placement") or {}).get("tonie") or {}
        known = (
            hh_data.get("creativetonies", {}).get(tonie_id)
            or hh_data.get("contenttonies", {}).get(tonie_id)
            or hh_data.get("discs", {}).get(tonie_id)
            or {}
        )
        base = dict(prev) if prev.get("id") == tonie_id else {}
        merged = {**base, **{k: v for k, v in tonie.items() if v}}
        merged["name"] = merged.get("name") or known.get("name")
        merged["imageUrl"] = merged.get("imageUrl") or known.get("image_url")
        return merged

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
            # A Toniebox going offline sends a final battery payload with all
            # values null. Don't let that null out last_battery — keep the
            # last known-good reading so consumers (e.g. RestoreEntity-backed
            # sensors) don't lose it.
            if battery.get("percent") is not None or battery.get("raw") is not None:
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
            self._box_event(self._settings_events, tb_id).set()
            updated = True

        elif subtopic == ICI_TOPIC_VOLUME and isinstance(payload, dict):
            # Live playback volume: {"level": N, "hardwarePercentage": P}.
            tb["volume"] = {
                "level": payload.get("level"),
                "hardware_percentage": payload.get("hardwarePercentage"),
            }
            level = payload.get("level")
            if isinstance(level, (int, float)) and self._last_levels.get(tb_id) != int(level):
                self._last_levels[tb_id] = int(level)
                self._save_boost_state()
            self._box_event(self._volume_events, tb_id).set()
            updated = True

        elif subtopic == ICI_TOPIC_BEDTIME:
            # {"stl": {"state": "on"|"off"|"completed", "duration": <s>, "until": <epoch>}}
            stl = payload.get("stl") if isinstance(payload, dict) else None
            if isinstance(stl, dict):
                tb["sleep_timer"] = {
                    "state": stl.get("state"),
                    "duration": stl.get("duration"),
                    "until": stl.get("until"),
                    "alarm": stl.get("alarm"),
                }
            else:
                tb["sleep_timer"] = {}
            updated = True

        elif subtopic == ICI_TOPIC_PLAYBACK:
            # Verified against a live account: {"tonie": "<id>", "paused": bool,
            # "chapter": int, "chapterUntilMs": <epoch ms>, "chapterDuration":
            # <seconds>, "ended": bool, ...} — "tonie" is a flat ID string, not a
            # nested object. An empty/None payload means the Tonie was removed.
            self._ici_placement_boxes.add(tb_id)
            if not payload:
                tb["placement"] = {}
                tb["playback_state"] = {}
                # Tonie removed → undo its volume boost.
                self._schedule_volume_sync(tb_id)
            elif isinstance(payload, dict):
                raw_tonie = payload.get("tonie")
                if isinstance(raw_tonie, dict):
                    tonie = raw_tonie if raw_tonie.get("id") else None
                elif isinstance(raw_tonie, str) and raw_tonie:
                    tonie = {"id": raw_tonie}
                else:
                    flat_id = payload.get("tonieId") or payload.get("id")
                    tonie = {"id": flat_id} if flat_id else None
                if tonie:
                    tonie = self._enrich_placed_tonie(tonie, tb, data.get("households", {}).get(hh_id, {}))
                tb["placement"] = {"tonie": tonie} if tonie else {}
                tb["playback_state"] = self._parse_playback_state(payload)
                # Real-time swap detection: shuffle a displaced Creative Tonie.
                try:
                    self._note_placement(
                        tb_id, tonie.get("id") if tonie else None, data
                    )
                except Exception:
                    _LOGGER.warning("Shuffle-on-swap push processing failed", exc_info=True)
                # Apply / undo the per-Tonie volume boost for this box.
                self._schedule_volume_sync(tb_id)
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

    def ici_set_sleep_timer(
        self,
        mac: str,
        seconds: int,
        alarm: dict | None = None,
        one_time_alarm: bool = False,
    ) -> bool:
        """Arm a sleep timer: the box falls asleep on its own after `seconds`.

        `seconds` is sent as a uint16 field, so it must stay below 65536
        (max 1092 minutes); larger values wrap on the box.

        `alarm` arms the alarm that fires when the timer ends, in the shape the
        official app sends: {"morningLight": bool, "tone": str, "volume": int}.
        Without it the box only ever gets a plain timer, never an alarm.
        """
        payload: dict = {"state": "on", "duration": int(seconds)}
        if one_time_alarm:
            payload["oneTimeAlarm"] = True
        if alarm:
            # the app sends this first; without it the box jumps to full volume
            self._ici_publish(mac, "alarm-preview", {"tone": None})
            payload["alarm"] = alarm
        return self._ici_publish(mac, ICI_CMD_SLEEP_TIMER, payload)

    def ici_cancel_sleep_timer(self, mac: str) -> bool:
        """Cancel a running sleep timer."""
        return self._ici_publish(mac, ICI_CMD_SLEEP_TIMER, {"state": "off"})

    async def _async_update_data(self) -> dict:
        try:
            result = await self._fetch_all()
        except TonieCloudAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Tonie Cloud error: {err}") from err
        self._poll_seq += 1
        # ICI may have reported a new placement while the (multi-request) poll
        # was running; the poll result then carries the old one. Keep the live
        # ICI placement and fetch again so playback info matches it.
        stale = False
        for hh_id, hh in result.get("households", {}).items():
            for tb_id, tb in hh.get("tonieboxes", {}).items():
                if tb_id not in self._ici_placement_boxes:
                    continue
                live_tb = (
                    (self.data or {}).get("households", {}).get(hh_id, {})
                    .get("tonieboxes", {}).get(tb_id)
                )
                if not live_tb:
                    continue
                if self._placed_tonie_id(live_tb) != self._placed_tonie_id(tb):
                    tb["placement"] = live_tb.get("placement") or {}
                    tb["playback_state"] = live_tb.get("playback_state") or {}
                    stale = True
        if stale and not self._stale_retry:
            self._stale_retry = True  # retry once, never loop
            self.hass.async_create_task(self.async_request_refresh())
        else:
            self._stale_retry = False
        # Detect Tonie swaps from the freshly polled placement and, if enabled,
        # shuffle any displaced Creative Tonie. Never let this break the poll.
        try:
            self._process_placements(result)
        except Exception:
            _LOGGER.warning("Shuffle-on-swap poll processing failed", exc_info=True)
        # Volume boost: reconcile every box (idempotent). Also retries undoing
        # a boost that failed earlier, and undoes a stale boost after restart.
        # TNG boxes are only handled once their live placement is known —
        # otherwise a restart would wrongly undo the boost of a Tonie that is
        # still on the box.
        for hh_id, hh in result.get("households", {}).items():
            for tb_id, tb in hh.get("tonieboxes", {}).items():
                if is_tng_box(tb) and tb_id not in self._ici_placement_boxes:
                    continue
                if tb_id in self._active_boosts or self._placed_tonie_id(tb):
                    self.hass.async_create_task(
                        self._async_sync_volume_boost(hh_id, tb_id)
                    )
        return result

    # ── Stale device cleanup ───────────────────────────────────────────────────

    def active_device_identifiers(self) -> set[str]:
        """Return the device identifiers backed by the current cloud data."""
        active: set[str] = set()
        for hh_id, hh in (self.data or {}).get("households", {}).items():
            active.add(f"hh_{hh_id}")
            for tb_id in hh.get("tonieboxes", {}):
                active.add(f"tb_{tb_id}")
                active.add(f"tb_{tb_id}_headphones")
            for t_id in hh.get("creativetonies", {}):
                active.add(f"ct_{t_id}")
            for t_id in hh.get("contenttonies", {}):
                active.add(f"content_{t_id}")
            for d_id in hh.get("discs", {}):
                active.add(f"disc_{d_id}")
        return active

    def _cleanup_prefixes(self) -> tuple[str, ...]:
        """Identifier prefixes that may be cleaned up after this poll.

        A category is only eligible if its source was fetched successfully for
        every household; otherwise a missing item may just be an API hiccup.
        """
        data = self.data or {}
        households = data.get("households", {})
        if not data.get("households_ok") or not households:
            return ()

        def _ok(source: str) -> bool:
            return all(
                hh.get("sources_ok", {}).get(source) for hh in households.values()
            )

        prefixes: list[str] = ["hh_"]
        if _ok("tonieboxes"):
            prefixes.append("tb_")
        if _ok("creativetonies"):
            prefixes.append("ct_")
        if _ok("contenttonies"):
            prefixes.append("content_")
        if _ok("discs"):
            prefixes.append("disc_")
        return tuple(prefixes)

    @callback
    def async_remove_stale_devices(self) -> None:
        """Remove devices whose Tonie / Toniebox left the household.

        Without this, a Tonie removed in the Tonies app stays in Home Assistant
        forever as an "unavailable" device with unavailable entities.
        """
        if not self.last_update_success or self._cleanup_seq == self._poll_seq:
            return
        self._cleanup_seq = self._poll_seq

        prefixes = self._cleanup_prefixes()
        if not prefixes:
            return
        active = self.active_device_identifiers()
        dev_reg = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(dev_reg, self.entry.entry_id):
            idents = [i for d, i in device.identifiers if d == DOMAIN]
            if not idents or any(i in active for i in idents):
                continue
            if not all(i.startswith(prefixes) for i in idents):
                continue
            _LOGGER.info(
                "Removing device %s (%s): no longer part of the Tonie household",
                device.name_by_user or device.name, ", ".join(idents),
            )
            # A device belongs to a single config entry, so remove the device
            # itself. Detaching it via remove_config_entry_id is deprecated
            # and stops working in Home Assistant 2027.8.
            dev_reg.async_remove_device(device.id)

    async def _fetch_bedtime_schedules(
        self, hh_id: str, tb_id: str, box: dict, prev_tb: dict
    ) -> list:
        """Bedtime schedules of an alarm-capable box.

        Fetched on its own so a failing request never drops the box from the
        poll; the last known schedules are kept instead.
        """
        if "sleepTimerAlarm" not in box.get("features", []):
            return []
        try:
            schedules = await self.client.get_bedtime_schedules(hh_id, tb_id)
        except Exception as e:
            _LOGGER.debug("Could not fetch bedtime schedules for %s: %s", tb_id, e)
            return prev_tb.get("bedtime_schedules") or []
        return schedules if isinstance(schedules, list) else []

    async def _fetch_all(self) -> dict:
        result: dict = {
            "me": {},
            "households": {},
            "notifications": [],
            "system_notifications": [],
            "invitations": [],
            # True only if the household list itself was fetched successfully.
            # Used to decide whether stale devices may be removed safely.
            "households_ok": False,
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
        result["households_ok"] = isinstance(households, list) and bool(households)

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
                # Which sources were fetched completely in this poll. Devices of
                # a category are only cleaned up when its source succeeded, so a
                # transient API error never removes anything.
                "sources_ok": {
                    "creativetonies": False,
                    "contenttonies": False,
                    "discs": False,
                    "tonieboxes": False,
                },
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
                            "transcoding_errors": tonie.get("transcodingErrors", []),
                            "seconds_remaining": tonie.get("secondsRemaining"),
                            "seconds_present": tonie.get("secondsPresent"),
                            "chapters_remaining": tonie.get("chaptersRemaining"),
                            "chapters_present": tonie.get("chaptersPresent"),
                            "last_update": tonie.get("lastUpdate"),
                        }

                hh_data["sources_ok"]["creativetonies"] = True
            except Exception as e:
                _LOGGER.warning("Could not fetch creative tonies for %s: %s", hh_id, e)

            # ── Content Tonies, Discs & Placement via GraphQL ─────────────────
            # The official API doc states: "We use GraphQL for read-only requests".
            # The REST list endpoints for content tonies and discs return 404, and
            # the Toniebox REST response contains no placement data.
            # All three are available via GraphQL at /v2/graphql.
            try:
                # The GraphQL API uses Relay-style pagination: each "my*" query
                # returns a Connection type with edges[].node instead of a plain
                # list, capped at ~100 items per page. Field names verified via
                # schema introspection. Content tonies use `title` + `series {
                # name }` (there is no `name`), `lock` (not `locked`), and
                # `languageName`. Discs use `title`/`coverImageUrl`. The Toniebox
                # node has NO `placement` field — placement comes from ICI (see
                # _on_ici_message), so it is not queried here.
                async def _fetch_relay_all(field: str, node_selection: str) -> list:
                    """Fetch every node of a Relay-paginated `field` query,
                    following pageInfo.hasNextPage until it's exhausted."""
                    nodes: list = []
                    cursor: str | None = None
                    while True:
                        resp = await self.client.graphql_query(
                            f"""
                                query($cursor: String) {{
                                  {field}(first: 100, after: $cursor) {{
                                    pageInfo {{ hasNextPage endCursor }}
                                    edges {{ node {{ {node_selection} }} }}
                                  }}
                                }}
                            """,
                            {"cursor": cursor},
                        )
                        errors = resp.get("errors")
                        if errors:
                            _LOGGER.debug("GraphQL returned errors for %s: %s", field, errors)
                        connection = (resp.get("data") or {}).get(field)
                        if not isinstance(connection, dict):
                            # No usable data — treat as a failed fetch instead
                            # of an empty list (which would look like "all
                            # Tonies were removed").
                            raise TonieCloudAPIError(
                                f"GraphQL {field} returned no data: {errors}"
                            )
                        edges = connection.get("edges") or []
                        nodes.extend(
                            e["node"] for e in edges
                            if isinstance(e, dict) and isinstance(e.get("node"), dict)
                        )
                        page_info = connection.get("pageInfo") or {}
                        cursor = page_info.get("endCursor")
                        if not page_info.get("hasNextPage") or not cursor:
                            break
                    return nodes

                content_tonies = await _fetch_relay_all(
                    "myContentTonies",
                    """
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
                    """,
                )

                # Content Tonies
                for tonie in content_tonies:
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

                hh_data["sources_ok"]["contenttonies"] = True

                # Discs — fetched separately so a failing myDiscs query keeps
                # the Content Tonies loaded above (and only blocks disc cleanup).
                try:
                    discs = await _fetch_relay_all(
                        "myDiscs",
                        """
                        id
                        householdId
                        title
                        coverImageUrl
                        discImageUrl
                        lock
                        language
                        salesId
                        """,
                    )
                    for disc in discs:
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
                    hh_data["sources_ok"]["discs"] = True
                except Exception as e:
                    _LOGGER.debug("GraphQL discs query failed for %s: %s", hh_id, e)
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

                    # REST API does not include placement, and GraphQL has no
                    # placement field on the Toniebox node. Fall back to the ICI
                    # real-time placement (set by _on_ici_message) so the currently
                    # placed Tonie survives a poll cycle instead of being wiped to {}.
                    placement = box.get("placement") or prev_tb.get("placement") or {}
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
                        "last_seen": box.get("lastSeen") or box.get("last_seen"),
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
                        "bedtime_schedules": await self._fetch_bedtime_schedules(
                            hh_id, b_id, box, prev_tb
                        ),
                    }
                hh_data["sources_ok"]["tonieboxes"] = True
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
