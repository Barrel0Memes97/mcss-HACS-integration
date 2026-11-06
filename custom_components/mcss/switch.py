"""Per-server toggle for filtering /list responses from the console sensor."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN
from .entity import MCSSEntity


class MCSSConsoleFilter(MCSSEntity, SwitchEntity):
    _attr_name = "Filter player-list console messages"
    _attr_icon = "mdi:filter-outline"

    def __init__(self, coordinator, server_id):
        super().__init__(coordinator, server_id)
        self._attr_unique_id = f"{server_id}_console_filter"

    @property
    def is_on(self):
        return self.coordinator.filter_enabled(self.server_id)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_preference(self.server_id, "filter_player_messages", True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_preference(self.server_id, "filter_player_messages", False)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = {}

    def sync():
        new = []
        for sid in coordinator.data or {}:
            if sid not in entities:
                entities[sid] = MCSSConsoleFilter(coordinator, sid)
                new.append(entities[sid])
        if new:
            async_add_entities(new)

    sync()
    entry.async_on_unload(coordinator.async_add_listener(sync))
