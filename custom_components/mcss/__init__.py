"""MC Server Soft integration: dynamic server discovery and services."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import (
    ACTION_KILL, ACTION_RESTART, ACTION_START, ACTION_STOP, ATTR_ACTION,
    ATTR_COMMAND, ATTR_SERVER_ID, DOMAIN, PLATFORMS, SERVICE_SEND_COMMAND,
    SERVICE_SERVER_ACTION,
)
from .coordinator import MCSSCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = MCSSCoordinator(hass, entry)
    await coordinator.async_load_preferences()
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        def get_coordinator(sid: str) -> MCSSCoordinator:
            for item in hass.data.get(DOMAIN, {}).values():
                if sid in (item.data or {}):
                    return item
            raise HomeAssistantError(f"Unknown MCSS server: {sid}")

        async def send_command(call: ServiceCall):
            sid = call.data[ATTR_SERVER_ID]
            command = call.data[ATTR_COMMAND].strip()
            if not command:
                raise HomeAssistantError("Command cannot be empty")
            await get_coordinator(sid).async_send_command(sid, command)

        async def server_action(call: ServiceCall):
            sid = call.data[ATTR_SERVER_ID]
            action = int(call.data[ATTR_ACTION])
            if action not in (ACTION_STOP, ACTION_START, ACTION_KILL, ACTION_RESTART):
                raise HomeAssistantError("Invalid MCSS action")
            await get_coordinator(sid).async_action(sid, action)

        hass.services.async_register(
            DOMAIN, SERVICE_SEND_COMMAND, send_command,
            schema=vol.Schema({vol.Required(ATTR_SERVER_ID): str,
                               vol.Required(ATTR_COMMAND): str}),
        )
        hass.services.async_register(
            DOMAIN, SERVICE_SERVER_ACTION, server_action,
            schema=vol.Schema({vol.Required(ATTR_SERVER_ID): str,
                               vol.Required(ATTR_ACTION): vol.Coerce(int)}),
        )

    await hass.config_entries.async_forward_entry_setups(entry, [Platform(p) for p in PLATFORMS])
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, [Platform(p) for p in PLATFORMS])
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN):
            hass.services.async_remove(DOMAIN, SERVICE_SEND_COMMAND)
            hass.services.async_remove(DOMAIN, SERVICE_SERVER_ACTION)
    return unloaded
