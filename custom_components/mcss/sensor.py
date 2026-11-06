"""Minecraft server statistics, connection details, and console metrics."""
from __future__ import annotations

from datetime import datetime, timezone
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfInformation

from .const import DOMAIN
from .entity import MCSSEntity
from .parsing import filter_console_lines


def duration_text(seconds: int) -> str:
    seconds = max(0, int(seconds))
    weeks, rem = divmod(seconds, 604800)
    days, rem = divmod(rem, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    clock = f"{hours:02d}:{minutes:02d}:{secs:02d}"
    if weeks:
        return f"{weeks}w {days}d {clock}"
    if days:
        return f"{days}d {clock}"
    return clock


NAMES = {
    "status": "Status", "players": "Players", "player_list": "Player list",
    "cpu": "CPU", "memory": "Memory used", "memory_percent": "Memory usage",
    "uptime": "Uptime", "uptime_text": "Uptime display", "console": "Latest console output",
    "tps": "TPS", "address": "Server address", "port": "Server port",
    "version": "Server version", "loader": "Server type", "modpack": "Modpack / mods",
    "mod_count": "Loaded mods", "lag_ms": "Last lag warning", "skipped_ticks": "Last skipped ticks",
}
ICONS = {
    "status": "mdi:minecraft", "players": "mdi:account-group", "player_list": "mdi:account-multiple",
    "cpu": "mdi:cpu-64-bit", "memory": "mdi:memory", "memory_percent": "mdi:memory",
    "uptime": "mdi:timer-outline", "uptime_text": "mdi:timer-outline", "console": "mdi:console",
    "tps": "mdi:speedometer", "address": "mdi:ip-network", "port": "mdi:ethernet",
    "version": "mdi:information", "loader": "mdi:package-variant", "modpack": "mdi:package-variant-closed",
    "mod_count": "mdi:package-variant-closed", "lag_ms": "mdi:clock-alert-outline",
    "skipped_ticks": "mdi:alert-circle-outline",
}


class MCSSSensor(MCSSEntity, SensorEntity):
    def __init__(self, coordinator, server_id, kind):
        super().__init__(coordinator, server_id)
        self.kind = kind
        # Keep all original IDs stable across upgrades.
        self._attr_unique_id = f"{server_id}_{kind}"
        self._attr_name = NAMES[kind]
        self._attr_icon = ICONS[kind]

    @property
    def native_value(self):
        s = self.server
        st = s.get("stats") or {}
        kind = self.kind
        if kind == "status":
            status = s.get("status")
            return {0: "Offline", 1: "Running"}.get(status, f"Status {status}" if status is not None else None)
        if kind == "players":
            return st.get("playersOnline")
        if kind == "player_list":
            players = s.get("players") or []
            return ", ".join(players) if players else "No players"
        if kind == "cpu":
            return st.get("cpu")
        if kind == "memory":
            return st.get("memoryUsed")
        if kind == "memory_percent":
            used, limit = st.get("memoryUsed"), st.get("memoryLimit")
            return round(used * 100 / limit, 1) if used is not None and limit else None
        if kind in ("uptime", "uptime_text"):
            try:
                start = float(st.get("startDate") or 0)
            except (ValueError, TypeError):
                start = 0
            if start > 10**12:  # Support milliseconds if a newer MCSS uses them.
                start /= 1000
            if start <= 0 or s.get("status") != 1:
                return 0 if kind == "uptime" else "00:00:00"
            elapsed = max(0, int(datetime.now(timezone.utc).timestamp() - start))
            return elapsed if kind == "uptime" else duration_text(elapsed)
        if kind == "console":
            lines = filter_console_lines(s.get("console") or [], self.coordinator.filter_enabled(self.server_id))
            return lines[-1][:255] if lines else "No console output"
        if kind == "tps":
            return s.get("tps")
        if kind == "address":
            return s.get("address") or None
        if kind == "port":
            return s.get("port")
        if kind == "version":
            return s.get("version") or s.get("minecraftVersion") or None
        if kind == "loader":
            return s.get("type") or s.get("loader") or s.get("serverType") or None
        if kind == "modpack":
            value = s.get("modpackName") or s.get("modpack")
            if isinstance(value, dict):
                return str(value.get("name") or "")[0:255] or None
            if isinstance(value, str):
                return value[:255] or None
            mods = s.get("mods")
            if isinstance(mods, list):
                return f"{len(mods)} mods"
            return None
        if kind == "mod_count":
            mods = s.get("mods")
            return len(mods) if isinstance(mods, list) else s.get("mod_count")
        if kind == "lag_ms":
            return s.get("last_lag_ms")
        if kind == "skipped_ticks":
            return s.get("last_skipped_ticks")
        return None

    @property
    def extra_state_attributes(self):
        s = self.server
        if self.kind in ("players", "player_list"):
            return {"players": s.get("players") or [], "player_count": len(s.get("players") or [])}
        if self.kind == "console":
            return {"lines": filter_console_lines(s.get("console") or [], self.coordinator.filter_enabled(self.server_id))}
        if self.kind in ("lag_ms", "skipped_ticks") and s.get("last_lag_line"):
            return {"source_warning": s["last_lag_line"]}
        if self.kind == "modpack" and isinstance(s.get("mods"), list):
            return {"mods": s["mods"][:100]}
        return None

    @property
    def native_unit_of_measurement(self):
        return {
            "cpu": PERCENTAGE, "memory": UnitOfInformation.MEGABYTES,
            "memory_percent": PERCENTAGE, "uptime": "s", "tps": "TPS",
            "lag_ms": "ms", "skipped_ticks": "ticks",
        }.get(self.kind)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = {}

    def sync():
        new = []
        for sid in coordinator.data or {}:
            for kind in NAMES:
                key = (sid, kind)
                if key not in entities:
                    entities[key] = MCSSSensor(coordinator, sid, kind)
                    new.append(entities[key])
        if new:
            async_add_entities(new)

    sync()
    entry.async_on_unload(coordinator.async_add_listener(sync))
