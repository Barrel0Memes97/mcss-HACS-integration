
from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, CONF_API_KEY_ENTITY

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            host = user_input[CONF_HOST].strip().rstrip("/")
            entity = user_input[CONF_API_KEY_ENTITY]
            try:
                state = self.hass.states.get(entity)
                if not state or not state.state or state.state in ("unknown", "unavailable"):
                    raise ValueError("API key helper unavailable")
                session = async_get_clientsession(self.hass)
                async with session.get(
                    host + "/api/v2/servers",
                    headers={"apiKey": state.state},
                    timeout=10,
                ) as response:
                    if response.status == 401:
                        errors["base"] = "invalid_auth"
                    elif response.status >= 400:
                        errors["base"] = "cannot_connect"
                    else:
                        await response.json()
            except Exception:
                if not errors:
                    errors["base"] = "cannot_connect"
            if not errors:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="MC Server Soft",
                    data={CONF_HOST: host, CONF_API_KEY_ENTITY: entity},
                )

        schema = vol.Schema({
            vol.Required(CONF_HOST, default="http://192.168.254.254:25560"): str,
            vol.Required(
                CONF_API_KEY_ENTITY,
                default="input_text.mcss_apikey"
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="input_text")
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
