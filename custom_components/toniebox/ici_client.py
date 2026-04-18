"""ICI MQTT v5 client for real-time Toniebox data (TNG/TB2 only).

Connects to the Tonie Cloud ICI broker via MQTT v5 over WebSocket Secure (WSS)
and receives real-time push updates for battery, online state, and headphones.
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import uuid as uuid_lib
from typing import Any, Callable

import paho.mqtt.client as mqtt

from .const import (
    ICI_HOST,
    ICI_PORT,
    ICI_TOPIC_BATTERY,
    ICI_TOPIC_HEADPHONES,
    ICI_TOPIC_ONLINE,
    ICI_TOPIC_SETTINGS,
)

_LOGGER = logging.getLogger(__name__)

# Topics we subscribe to for each Toniebox
_SUBSCRIBE_TOPICS = [
    ICI_TOPIC_BATTERY,
    ICI_TOPIC_ONLINE,
    ICI_TOPIC_HEADPHONES,
    ICI_TOPIC_SETTINGS,
]


class TonieboxIciClient:
    """MQTT v5 client for ICI real-time push data."""

    def __init__(
        self,
        on_message_callback: Callable[[str, str, dict[str, Any]], None],
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._on_message_callback = on_message_callback
        self._loop = loop
        self._client: mqtt.Client | None = None
        self._connected = False
        self._boxes: list[dict] = []
        self._user_uuid: str | None = None
        self._last_token: str | None = None
        self._auth_failed = False

    @property
    def connected(self) -> bool:
        """Return True if currently connected to the ICI broker."""
        return self._connected

    async def connect(
        self,
        user_uuid: str,
        access_token: str,
        boxes: list[dict],
    ) -> None:
        """Connect to ICI broker and subscribe to topics for all TNG boxes."""
        self._user_uuid = user_uuid
        self._last_token = access_token
        self._boxes = [b for b in boxes if b.get("generation") == "tng"]

        if not self._boxes:
            _LOGGER.debug("No TNG Tonieboxes found, skipping ICI connection")
            return

        if not self._loop:
            self._loop = asyncio.get_running_loop()

        random_id = str(uuid_lib.uuid4())
        client_id = f"{user_uuid}_ha_toniebox_{random_id}"

        def _setup_and_connect():
            """Set up MQTT client (blocking TLS calls) and connect."""
            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
                transport="websockets",
                protocol=mqtt.MQTTv5,
            )
            self._client.ws_set_options(path="/")
            # Use create_default_context() for full cert verification;
            # avoids the deprecated ssl.PROTOCOL_TLS_CLIENT path in paho that
            # can leave _ssl_context unset and break tls_insecure_set().
            ssl_ctx = ssl.create_default_context()
            self._client.tls_set(ssl_context=ssl_ctx)
            self._client.username_pw_set(username=user_uuid, password=access_token)
            self._client.reconnect_delay_set(min_delay=5, max_delay=120)
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.on_disconnect = self._on_disconnect
            self._client.connect_async(ICI_HOST, ICI_PORT, keepalive=60)

        try:
            await self._loop.run_in_executor(None, _setup_and_connect)
            self._client.loop_start()
            _LOGGER.debug("ICI MQTT connection initiated for %d TNG boxes", len(self._boxes))
        except Exception:
            _LOGGER.warning("Failed to connect to ICI broker", exc_info=True)

    async def disconnect(self) -> None:
        """Disconnect from ICI broker."""
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                _LOGGER.debug("Error during ICI disconnect", exc_info=True)
            finally:
                self._client = None
                self._connected = False

    async def reconnect(self, new_token: str) -> None:
        """Reconnect with a new access token."""
        if not self._user_uuid or not self._boxes:
            return
        await self.disconnect()
        await self.connect(self._user_uuid, new_token, self._boxes)

    def on_token_refreshed(self, new_token: str) -> None:
        """Called by TonieCloudClient when the token is refreshed."""
        if not self._user_uuid or not self._loop:
            return
        # Update _last_token immediately so any in-flight _on_disconnect reconnect
        # uses the fresh token rather than the expired one.
        self._last_token = new_token
        self._auth_failed = False
        asyncio.run_coroutine_threadsafe(self.reconnect(new_token), self._loop)

    # ── paho-mqtt callbacks (called from network thread) ──────────────────────

    # Reason code strings that indicate an authentication/authorisation failure.
    _AUTH_FAILURE_CODES = frozenset({
        "Bad user name or password",
        "Not authorized",
        "Not Authorized",
    })

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        rc_str = str(reason_code)
        if rc_str == "Success":
            self._connected = True
            self._auth_failed = False
            _LOGGER.info("ICI MQTT connected")
            self._subscribe_all()
        elif rc_str in self._AUTH_FAILURE_CODES:
            self._connected = False
            if not self._auth_failed:
                self._auth_failed = True
                _LOGGER.warning(
                    "ICI MQTT authentication failed (%s). "
                    "Reconnection suspended until the access token is refreshed.",
                    rc_str,
                )
                # Synchronously tell paho to stop retrying — calling disconnect()
                # from within _on_connect is safe and prevents further attempts
                # before the async cleanup below has a chance to run.
                client.disconnect()
                if self._loop:
                    asyncio.run_coroutine_threadsafe(self.disconnect(), self._loop)
        else:
            self._connected = False
            _LOGGER.warning("ICI MQTT connection failed: %s", rc_str)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self._connected = False
        _LOGGER.debug("ICI MQTT disconnected: %s", reason_code)
        # Don't reconnect on auth failure — wait for on_token_refreshed() to resume.
        if self._auth_failed:
            return
        # Schedule reconnect unless we intentionally disconnected (client set to None)
        if self._client and self._loop and self._last_token:
            _LOGGER.debug("ICI MQTT scheduling reconnect after unexpected disconnect")
            asyncio.run_coroutine_threadsafe(self.reconnect(self._last_token), self._loop)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        # Topic format: external/toniebox/{MAC}/{subtopic}
        parts = topic.split("/", 3)
        if len(parts) < 4 or parts[0] != "external" or parts[1] != "toniebox":
            return

        mac = parts[2]
        subtopic = parts[3]

        try:
            payload = json.loads(msg.payload.decode("utf-8")) if msg.payload else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            _LOGGER.debug("ICI: unparseable payload on %s", topic)
            return

        _LOGGER.debug("ICI message: %s/%s → %s", mac, subtopic, payload)

        if self._loop and self._on_message_callback:
            self._loop.call_soon_threadsafe(
                self._on_message_callback, mac, subtopic, payload
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _subscribe_all(self) -> None:
        """Subscribe to all relevant topics for all TNG boxes."""
        if not self._client:
            return
        for box in self._boxes:
            mac = box.get("macAddress") or box.get("mac_address", "")
            if not mac:
                continue
            name = box.get("name", "?")
            for subtopic in _SUBSCRIBE_TOPICS:
                full_topic = f"external/toniebox/{mac}/{subtopic}"
                self._client.subscribe(full_topic, qos=1)
                _LOGGER.debug("ICI subscribed: %s (%s)", full_topic, name)
