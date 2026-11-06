"""Coordinate MC Server Soft API requests and safely cache optional log data."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MCSSApi
from .const import (
    CONF_API_KEY_ENTITY, CONF_CONSOLE_INTERVAL, CONF_CONSOLE_LINES, CONF_FILTER_PLAYER_MESSAGES,
    CONF_HOST, CONF_PLAYER_INTERVAL, CONF_SCAN_INTERVAL, CONF_TPS_INTERVAL,
    DEFAULT_CONSOLE_INTERVAL, DEFAULT_CONSOLE_LINES, DEFAULT_FILTER_PLAYER_MESSAGES,
    DEFAULT_PLAYER_INTERVAL, DEFAULT_SCAN_INTERVAL, DEFAULT_TPS_INTERVAL, DOMAIN,
)
from .parsing import parse_lag, parse_metadata, parse_players, parse_tps
from .server_probe import probe_game_server

_LOGGER = logging.getLogger(__name__)
TPS_DEFAULT_COMMANDS = {"paper": "tps", "spigot": "tps", "purpur": "tps",
                        "craftbukkit": "tps", "forge": "forge tps", "neoforge": "forge tps"}


class MCSSCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    def __init__(self, hass, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        options = entry.options
        self.scan_seconds = int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self.console_seconds = int(options.get(CONF_CONSOLE_INTERVAL, DEFAULT_CONSOLE_INTERVAL))
        self.console_lines = int(options.get(CONF_CONSOLE_LINES, DEFAULT_CONSOLE_LINES))
        self.player_seconds = int(options.get(CONF_PLAYER_INTERVAL, DEFAULT_PLAYER_INTERVAL))
        self.tps_seconds = int(options.get(CONF_TPS_INTERVAL, DEFAULT_TPS_INTERVAL))
        self.default_filter = options.get(CONF_FILTER_PLAYER_MESSAGES, DEFAULT_FILTER_PLAYER_MESSAGES)

        self._last_stats = 0.0
        self._last_console = 0.0
        self._last_players = 0.0
        self._last_tps = 0.0
        self._last_probe = 0.0
        self._servers: dict[str, dict] = {}
        self._console_cache: dict[str, list[str]] = {}
        self._player_cache: dict[str, list[str]] = {}
        self._icon_cache: dict[str, bytes] = {}
        self._metadata: dict[str, dict] = {}
        self._probe_cache: dict[str, dict] = {}
        self._tps_cache: dict[str, tuple[float, float, str]] = {}
        self._lag_cache: dict[str, tuple[int, int, str]] = {}
        self._preferences: dict[str, dict[str, Any]] = {}
        self._store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}_settings")

        # A 5-second console poll must actually run every 5 seconds, even if
        # server stats and discovery refresh only once every 30 seconds.
        seconds = min(self.scan_seconds, self.console_seconds, self.player_seconds)
        if self.tps_seconds:
            seconds = min(seconds, self.tps_seconds)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=seconds))

    async def async_load_preferences(self):
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._preferences = {str(sid): dict(values) for sid, values in stored.items()
                                 if isinstance(values, dict)}

    def preference(self, sid: str, key: str, fallback: Any = None) -> Any:
        return self._preferences.get(sid, {}).get(key, fallback)

    async def async_set_preference(self, sid: str, key: str, value: Any):
        self._preferences.setdefault(sid, {})[key] = value
        await self._store.async_save(self._preferences)
        self._last_probe = 0.0
        self.async_update_listeners()

    def filter_enabled(self, sid: str) -> bool:
        return bool(self.preference(sid, "filter_player_messages", self.default_filter))

    def tps_command(self, sid: str) -> str:
        server = (self.data or {}).get(sid) or self._servers.get(sid, {})
        loader = str(server.get("type") or "").strip().lower()
        default = next((value for prefix, value in TPS_DEFAULT_COMMANDS.items()
                        if loader.startswith(prefix)), "")
        return str(self.preference(sid, "tps_command", default)).strip()

    @property
    def api_key(self) -> str:
        state = self.hass.states.get(self.entry.data[CONF_API_KEY_ENTITY])
        return state.state if state and state.state not in ("", "unknown", "unavailable") else ""

    def _make_api(self) -> MCSSApi:
        return MCSSApi(async_get_clientsession(self.hass), self.entry.data[CONF_HOST], self.api_key)

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        if not self.api_key:
            raise UpdateFailed("The configured API-key input_text is empty or unavailable.")
        api = self._make_api()
        now = time.monotonic()

        try:
            if not self._servers or now - self._last_stats >= self.scan_seconds:
                raw = await api.get_servers()
                if not isinstance(raw, list):
                    raise UpdateFailed("MCSS returned an invalid server list")
                updated: dict[str, dict] = {}

                async def load(server):
                    if not isinstance(server, dict):
                        return
                    sid = str(server.get("serverId") or "")
                    if not sid:
                        return
                    item = dict(server)
                    try:
                        result = await api.get_stats(sid)
                        latest = result.get("latest", {}) if isinstance(result, dict) else {}
                        item["stats"] = latest if isinstance(latest, dict) else {}
                    except (ClientError, asyncio.TimeoutError, ValueError) as err:
                        _LOGGER.debug("Stats unavailable for %s: %s", sid, err)
                        item["stats"] = self._servers.get(sid, {}).get("stats", {})
                    updated[sid] = item

                await asyncio.gather(*(load(server) for server in raw))
                self._servers = updated
                self._last_stats = now

            # Copy nested dicts: the DataUpdateCoordinator must receive fresh data.
            data = {sid: {**item, "stats": dict(item.get("stats") or {})}
                    for sid, item in self._servers.items()}

            # Reconcile counts on every cycle, not only the 60s /list interval.
            for sid, item in data.items():
                stats = item["stats"]
                if item.get("status") != 1 or stats.get("playersOnline") == 0:
                    self._player_cache[sid] = []
                    if item.get("status") != 1:
                        self._tps_cache.pop(sid, None)
                elif "playersOnline" in stats and len(self._player_cache.get(sid, [])) != stats["playersOnline"]:
                    self._player_cache[sid] = []

            if now - self._last_tps >= self.tps_seconds and self.tps_seconds:
                await self._request_tps(api, data)
                self._last_tps = now

            if now - self._last_console >= self.console_seconds:
                await self._refresh_console(api, data)
                self._last_console = now

            if now - self._last_players >= self.player_seconds:
                await self._refresh_players(api, data)
                self._last_players = now

            if now - self._last_probe >= max(60, self.scan_seconds):
                await self._probe_servers(data)
                self._last_probe = now

            for sid, item in data.items():
                item["console"] = list(self._console_cache.get(sid, []))
                item["players"] = list(self._player_cache.get(sid, []))
                item["icon"] = self._icon_cache.get(sid) or b""
                item.update(self._metadata.get(sid, {}))
                for field, value in self._probe_cache.get(sid, {}).items():
                    if value is not None:
                        item[field] = value
                item["address"] = (self.preference(sid, "address") or item.get("address")
                                   or item.get("serverAddress") or item.get("serverIp")
                                   or item.get("ip") or item.get("host"))
                item["version"] = self.preference(sid, "version") or item.get("version")
                item["modpack"] = self.preference(sid, "modpack") or item.get("modpack")
                override = self.preference(sid, "port")
                if override:
                    item["port"] = int(override)
                else:
                    item["port"] = (item.get("port") or item.get("serverPort") or item.get("gamePort"))
                stats = item["stats"]
                if item.get("status") != 1:
                    item["tps"] = None
                elif stats.get("tps") is not None:
                    item["tps"] = stats["tps"]
                else:
                    cached = self._tps_cache.get(sid)
                    item["tps"] = (cached[0] if cached and now - cached[1] <= max(180, 3 * self.tps_seconds)
                                   else None)
                if sid in self._lag_cache:
                    lag_ms, skipped, line = self._lag_cache[sid]
                    item["last_lag_ms"] = lag_ms
                    item["last_skipped_ticks"] = skipped
                    item["last_lag_line"] = line

            return data
        except (ClientError, asyncio.TimeoutError, OSError, ValueError) as err:
            raise UpdateFailed(f"MCSS API request failed: {err}") from err

    async def _refresh_console(self, api: MCSSApi, data: dict):
        async def fetch(sid):
            try:
                lines = await api.get_console(sid, self.console_lines)
                self._accept_console(sid, [str(x) for x in lines])
            except (ClientError, asyncio.TimeoutError) as err:
                _LOGGER.debug("Console refresh failed for %s: %s", sid, err)

            if sid not in self._icon_cache:
                try:
                    icon = await api.get_icon(sid)
                    self._icon_cache[sid] = (icon if isinstance(icon, bytes) and
                                              icon.startswith(b"\x89PNG\r\n\x1a\n") else b"")
                except (ClientError, asyncio.TimeoutError):
                    self._icon_cache[sid] = b""

        await asyncio.gather(*(fetch(sid) for sid in data))

    def _accept_console(self, sid: str, lines: list[str]):
        self._console_cache[sid] = lines
        if lines:
            self._metadata.setdefault(sid, {}).update(parse_metadata(lines))
            tps = parse_tps(lines)
            if tps is not None:
                from .parsing import TPS_TRIPLE, TPS_SINGLE, message_text
                latest = next((line for line in reversed(lines) if
                               TPS_TRIPLE.search(message_text(line)) or TPS_SINGLE.search(message_text(line))), "")
                cached = self._tps_cache.get(sid)
                if not cached or cached[2] != latest:
                    self._tps_cache[sid] = (tps, time.monotonic(), latest)
            lag = parse_lag(lines)
            if lag:
                self._lag_cache[sid] = lag

    async def _probe_servers(self, data: dict):
        """Use Minecraft status to retrieve version/advertised mod info, if reachable."""
        async def one(sid, item):
            if item.get("status") != 1:
                return
            address = (self.preference(sid, "address") or item.get("address")
                       or item.get("serverAddress") or item.get("serverIp")
                       or item.get("ip") or item.get("host"))
            port = (self.preference(sid, "port") or item.get("port")
                    or item.get("serverPort") or item.get("gamePort")
                    or self._metadata.get(sid, {}).get("port"))
            if not address or not port:
                return
            try:
                result = await probe_game_server(str(address), int(port), str(item.get("type") or ""))
                if result:
                    self._probe_cache[sid] = result
            except (OSError, asyncio.TimeoutError, ValueError, TypeError) as err:
                _LOGGER.debug("Minecraft status probe failed for %s (%s:%s): %s", sid, address, port, err)

        await asyncio.gather(*(one(sid, item) for sid, item in data.items()))

    async def _request_tps(self, api: MCSSApi, data: dict):
        async def one(sid, item):
            if item.get("status") != 1:
                self._tps_cache.pop(sid, None)
                return
            command = self.tps_command(sid)
            if not command:
                return
            try:
                await api.command(sid, command)
            except (ClientError, asyncio.TimeoutError) as err:
                _LOGGER.debug("TPS command failed for %s: %s", sid, err)
        await asyncio.gather(*(one(sid, item) for sid, item in data.items()))

    async def _refresh_players(self, api: MCSSApi, data: dict, only: str | None = None):
        targets = [(sid, item) for sid, item in data.items() if only is None or sid == only]
        pending: list[tuple[str, int, list[str]]] = []
        async def issue(sid, item):
            stats = item.get("stats", {})
            count = stats.get("playersOnline")
            if item.get("status") != 1 or count == 0:
                self._player_cache[sid] = []
                return
            if count is None:
                return
            try:
                before = list(self._console_cache.get(sid, []))
                await api.command(sid, "list")
                pending.append((sid, int(count), before))
            except (ClientError, asyncio.TimeoutError) as err:
                _LOGGER.debug("Player-list command failed for %s: %s", sid, err)
        await asyncio.gather(*(issue(sid, item) for sid, item in targets))
        if not pending:
            return
        await asyncio.sleep(0.75)

        async def read(sid, expected, before):
            try:
                lines = [str(x) for x in await api.get_console(sid, max(50, self.console_lines))]
                # Match only newly appended console lines. Old /list results
                # can contain names of players who already disconnected.
                new_lines = lines
                if before:
                    # Find the last old suffix anywhere in the larger read
                    # window (which can exceed the configured console length).
                    match_end = None
                    for size in range(min(len(before), len(lines)), 0, -1):
                        for start in range(len(lines) - size, -1, -1):
                            if before[-size:] == lines[start:start + size]:
                                match_end = start + size
                                break
                        if match_end is not None:
                            break
                    if match_end is not None:
                        new_lines = lines[match_end:]
                    elif lines == before:
                        new_lines = []
                parsed = parse_players(new_lines, expected_count=expected)
                # If a new count doesn't match the last /list response, prefer
                # an empty/unknown list to retaining disconnected players.
                self._player_cache[sid] = parsed if parsed is not None else []
                if lines:
                    self._accept_console(sid, lines[-self.console_lines:])
            except (ClientError, asyncio.TimeoutError) as err:
                _LOGGER.debug("Player-list parse failed for %s: %s", sid, err)
        await asyncio.gather(*(read(sid, expected, before) for sid, expected, before in pending))

    async def async_refresh_players(self, sid: str):
        server = (self.data or {}).get(sid)
        if not server:
            return
        await self._refresh_players(self._make_api(), {sid: server}, only=sid)
        await self.async_request_refresh()

    async def async_send_command(self, server_id: str, command: str):
        await self._make_api().command(server_id, command)
        await self.async_request_refresh()

    async def async_action(self, server_id: str, action: int):
        await self._make_api().action(server_id, action)
        await self.async_request_refresh()

    async def async_get_icon(self, server_id: str) -> bytes | None:
        if server_id in self._icon_cache:
            return self._icon_cache[server_id] or None
        try:
            icon = await self._make_api().get_icon(server_id)
            if isinstance(icon, bytes) and icon.startswith(b"\x89PNG\r\n\x1a\n"):
                self._icon_cache[server_id] = icon
                return icon
        except (ClientError, asyncio.TimeoutError):
            pass
        self._icon_cache[server_id] = b""
        return None
