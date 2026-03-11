"""Config flow for Toniebox integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD
from .tonie_client import TonieCloudClient, TonieCloudAuthError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate credentials by attempting a real login to the Tonie Cloud."""
    session = async_get_clientsession(hass)
    client = TonieCloudClient(data[CONF_USERNAME], data[CONF_PASSWORD], session)

    # Raises TonieCloudAuthError on bad credentials
    await client.authenticate()

    try:
        me = await client.get_me()
        display_name = me.get("email", data[CONF_USERNAME])
    except Exception:
        display_name = data[CONF_USERNAME]

    return {"title": f"Toniebox ({display_name})"}


class TonieboxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Toniebox."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

            except TonieCloudAuthError as err:
                _LOGGER.warning("Toniebox auth failed: %s", err)
                errors["base"] = "invalid_auth"

            except aiohttp.ClientConnectorError:
                errors["base"] = "cannot_connect"

            except Exception as err:
                _LOGGER.exception("Unexpected error during Toniebox setup: %s", err)
                errors["base"] = "unknown"

            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except TonieCloudAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "unknown"
            else:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                self.hass.config_entries.async_update_entry(entry, data=user_input)
                await self.hass.config_entries.async_reload(self.context["entry_id"])
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
