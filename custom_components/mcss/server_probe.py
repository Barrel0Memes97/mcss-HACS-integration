"""Optional Minecraft protocol status: only used when a game address is known."""
from __future__ import annotations

from typing import Any
from mcstatus import JavaServer, BedrockServer


async def probe_game_server(address: str, port: int, loader: str) -> dict[str, Any]:
    """Get advertised version and Forge mod metadata without console commands.

    The Minecraft status protocol cannot reveal modpacks or hidden mods.
    """
    if loader.casefold() == "bedrock":
        status = await BedrockServer(address, port, timeout=2).async_status(tries=1)
        return {"version": str(status.version.name)} if getattr(status, "version", None) else {}

    status = await JavaServer(address, port, timeout=2).async_status(tries=1)
    result: dict[str, Any] = {}
    version = getattr(getattr(status, "version", None), "name", None)
    if version:
        result["version"] = str(version)
    forge_data = getattr(status, "forge_data", None)
    if forge_data and getattr(forge_data, "mods", None) is not None:
        mods = []
        for mod in forge_data.mods:
            name = str(getattr(mod, "name", ""))
            if name:
                marker = str(getattr(mod, "marker", ""))
                mods.append(f"{name} ({marker})" if marker else name)
        result["mods"] = mods
        result["mod_count"] = len(mods)
        result["mod_list_truncated"] = bool(getattr(forge_data, "truncated", False))
    return result
