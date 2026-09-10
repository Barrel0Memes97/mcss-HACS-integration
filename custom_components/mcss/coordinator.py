
from __future__ import annotations
import asyncio
from datetime import timedelta
from aiohttp import ClientError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, CONF_HOST, CONF_API_KEY_ENTITY, DEFAULT_SCAN_INTERVAL

class MCSSCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        self.hass = hass
        self.host = entry.data[CONF_HOST].rstrip("/")
        self.api_entity = entry.data[CONF_API_KEY_ENTITY]
        self.session = async_get_clientsession(hass)
        super().__init__(
            hass, None, name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL)
        )

    def _key(self):
        state = self.hass.states.get(self.api_entity)
        if not state or state.state in ("", "unknown", "unavailable"):
            raise UpdateFailed("MCSS API key helper is unavailable")
        return state.state

    async def _get(self, path):
        try:
            async with self.session.get(
                self.host + path,
                headers={"apiKey": self._key()},
                timeout=15
            ) as r:
                if r.status == 401:
                    raise UpdateFailed("MCSS API key rejected")
                if r.status >= 400:
                    raise UpdateFailed(f"MCSS HTTP {r.status}")
                return await r.json()
        except (ClientError, asyncio.TimeoutError) as e:
            raise UpdateFailed(f"MCSS connection failed: {e}") from e

    async def _post(self, path, payload=None):
        try:
            async with self.session.post(
                self.host + path,
                headers={"apiKey": self._key(), "Content-Type":"application/json"},
                json=payload,
                timeout=15
            ) as r:
                if r.status >= 400:
                    raise UpdateFailed(f"MCSS action HTTP {r.status}")
                if r.content_type == "application/json":
                    return await r.json()
                return None
        except (ClientError, asyncio.TimeoutError) as e:
            raise UpdateFailed(f"MCSS action failed: {e}") from e

    async def _async_update_data(self):
        servers = await self._get("/api/v2/servers")
        result = {}
        async def one(server):
            sid = server.get("serverId")
            if not sid:
                return
            try:
                stats = await self._get(f"/api/v2/servers/{sid}/stats")
                server = dict(server)
                server["stats"] = stats.get("latest", {})
            except Exception:
                server = dict(server)
                server["stats"] = {}
            result[sid] = server
        await asyncio.gather(*(one(s) for s in servers))
        return result

    async def action(self, server_id, action):
        await self._post(
            f"/api/v2/servers/{server_id}/execute/action",
            {"action": action}
        )
        await self.async_request_refresh()
