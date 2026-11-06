"""Server command input plus persistent per-server connection/TPS settings."""
from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import MCSSEntity


class MCSSText(MCSSEntity, TextEntity):
    def __init__(self, coordinator, server_id, kind):
        super().__init__(coordinator, server_id)
        self.kind = kind
        self._attr_unique_id = f"{server_id}_{kind}"
        self._attr_name = {
            "console_command": "Console command",
            "server_address_setting": "Configured server address",
            "server_port_setting": "Configured server port",
            "tps_command_setting": "TPS command",
            "server_version_setting": "Configured Minecraft version",
            "modpack_name_setting": "Configured modpack name",
        }[kind]
        self._attr_icon = {
            "console_command": "mdi:console-line",
            "server_address_setting": "mdi:ip-network",
            "server_port_setting": "mdi:ethernet",
            "tps_command_setting": "mdi:speedometer",
            "server_version_setting": "mdi:information-outline",
            "modpack_name_setting": "mdi:package-variant-closed",
        }[kind]
        self._attr_native_min = 0
        self._attr_native_max = 500 if kind == "console_command" else 255
        self._attr_mode = TextMode.TEXT

    @property
    def native_value(self):
        if self.kind == "console_command":
            return ""
        if self.kind == "tps_command_setting":
            return self.coordinator.tps_command(self.server_id)
        key = {"server_address_setting": "address", "server_port_setting": "port",
               "server_version_setting": "version", "modpack_name_setting": "modpack"}[self.kind]
        return str(self.coordinator.preference(self.server_id, key, ""))

    async def async_set_value(self, value: str):
        value = value.strip()
        if self.kind == "console_command":
            if value:
                await self.coordinator.async_send_command(self.server_id, value)
            self.async_write_ha_state()
            return
        if self.kind == "server_port_setting" and value:
            if not value.isdecimal() or not 1 <= int(value) <= 65535:
                raise HomeAssistantError("Server port must be a number from 1 to 65535")
        if self.kind == "server_address_setting" and ("://" in value or "/" in value):
            raise HomeAssistantError("Enter only the hostname or IP address, not an URL")
        key = {
            "server_address_setting": "address",
            "server_port_setting": "port",
            "tps_command_setting": "tps_command",
            "server_version_setting": "version",
            "modpack_name_setting": "modpack",
        }[self.kind]
        await self.coordinator.async_set_preference(self.server_id, key, value)
        if key in ("address", "port", "version", "modpack"):
            await self.coordinator.async_request_refresh()


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = {}
    kinds = ("console_command", "server_address_setting", "server_port_setting",
             "tps_command_setting", "server_version_setting", "modpack_name_setting")

    def sync():
        new = []
        for sid in coordinator.data or {}:
            for kind in kinds:
                key = (sid, kind)
                if key not in entities:
                    entities[key] = MCSSText(coordinator, sid, kind)
                    new.append(entities[key])
        if new:
            async_add_entities(new)

    sync()
    entry.async_on_unload(coordinator.async_add_listener(sync))
