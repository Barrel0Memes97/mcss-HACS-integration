"""Shared MCSS entity metadata and availability."""
from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .coordinator import MCSSCoordinator


class MCSSEntity(CoordinatorEntity[MCSSCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator, server_id):
        super().__init__(coordinator)
        self.server_id = server_id

    @property
    def server(self):
        return (self.coordinator.data or {}).get(self.server_id, {})

    @property
    def available(self):
        return super().available and self.server_id in (self.coordinator.data or {})

    @property
    def device_info(self):
        server = self.server
        return {
            "identifiers": {(DOMAIN, self.server_id)},
            "name": server.get("name", self.server_id),
            "manufacturer": "MC Server Soft",
            "model": server.get("type") or "Minecraft Server",
            "sw_version": server.get("version"),
            "configuration_url": self.coordinator.entry.data.get("host"),
        }
