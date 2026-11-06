"""Server icon camera, showing a bundled fallback image on 404/missing icons."""
from __future__ import annotations

from pathlib import Path
from homeassistant.components.camera import Camera
from .const import DOMAIN
from .entity import MCSSEntity


class MCSSIconCamera(MCSSEntity, Camera):
    def __init__(self, coordinator, server_id, fallback):
        Camera.__init__(self)
        MCSSEntity.__init__(self, coordinator, server_id)
        self._fallback = fallback
        self._attr_unique_id = f"{server_id}_icon"
        self._attr_name = "Server icon"
        self._attr_icon = "mdi:minecraft"
        self._attr_content_type = "image/png"

    async def async_camera_image(self, width=None, height=None):
        return (self.server.get("icon") or
                await self.coordinator.async_get_icon(self.server_id) or self._fallback)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    fallback = await hass.async_add_executor_job(
        (Path(__file__).parent / "brand" / "minecraft-icon.png").read_bytes
    )
    entities = {}

    def sync():
        new = []
        for sid in coordinator.data or {}:
            if sid not in entities:
                entities[sid] = MCSSIconCamera(coordinator, sid, fallback)
                new.append(entities[sid])
        if new:
            async_add_entities(new)

    sync()
    entry.async_on_unload(coordinator.async_add_listener(sync))
