"""Pure helpers for parsing MCSS/Minecraft console output.

The API does not directly supply these values. Do not invent TPS from lag warnings.
"""
from __future__ import annotations

import re
from typing import Any

# Java's /list output (vanilla, Forge, Paper, and similar servers).
PLAYER_HEADER = re.compile(
    r"There are\s+(\d+)\s*(?:/\s*\d+|of\s+a\s+max\s+of\s+\d+)"
    r"\s+players?\s+online\s*:\s*(.*)$", re.IGNORECASE
)
PLAYER_NAME = re.compile(r"[A-Za-z0-9_]{3,16}")
ANSI = re.compile(r"\x1b\[[0-9;]*m|§[0-9a-fk-or]", re.IGNORECASE)
PREFIX = re.compile(r"^\[[^\]]+\]\s+\[[^\]]+\](?::\s*|\s+)(?:\[[^\]]+\]:\s*)?(.*)$")
LAG = re.compile(r"Running\s+([\d,]+)\s*ms\s+behind,\s*skipping\s+([\d,]+)\s+tick", re.I)
TPS_TRIPLE = re.compile(
    r"TPS\s+(?:from\s+last|over\s+last)\s+1m\s*,\s*5m\s*,\s*15m\s*:\s*\*?([\d.]+)", re.I
)
TPS_SINGLE = re.compile(r"(?:Mean\s+TPS|(?:Current\s+)?TPS)\s*:\s*\*?([\d.]+)\b", re.I)
VERSION_PATTERNS = (
    re.compile(r"Starting\s+(?:minecraft\s+)?server\s+version\s+(\d+\.\d+(?:\.\d+)?)", re.I),
    re.compile(r"Loading\s+Minecraft\s+(\d+\.\d+(?:\.\d+)?)\s+with\s+Fabric", re.I),
    re.compile(r"for\s+Minecraft\s+(\d+\.\d+(?:\.\d+)?)", re.I),
    re.compile(r"(?:Paper|Purpur|Spigot|CraftBukkit).*?\b(?:MC\s*:\s*|minecraft\s+)(\d+\.\d+(?:\.\d+)?)", re.I),
)
PORT = re.compile(r"Starting\s+(?:Minecraft|Bedrock)\s+server\s+on\s+[^\s:]*:(\d{1,5})\b", re.I)
MOD_COUNT = re.compile(r"\b(?:Loading|Loaded)\s+(\d+)\s+mods\b", re.I)


def message_text(line: Any) -> str:
    """Remove standard timestamp/thread prefix without losing the message itself."""
    value = ANSI.sub("", str(line)).strip()
    match = PREFIX.match(value)
    return match.group(1).strip() if match else value


def _names(text: str) -> list[str] | None:
    """Only accept unambiguous comma-separated Java player names."""
    text = text.strip()
    if not text:
        return []
    tokens = [part.strip() for part in text.split(",")]
    return tokens if all(PLAYER_NAME.fullmatch(part) for part in tokens) else None


def parse_players(lines: list[str], expected_count: int | None = None) -> list[str] | None:
    """Use the most recent *complete* /list response, not a stale first match.

    Return None when no valid matching response is present; [] when it says zero.
    If MCSS stats disagree with /list, discard the old output.
    """
    messages = [message_text(line) for line in lines]
    for index in range(len(messages) - 1, -1, -1):
        match = PLAYER_HEADER.search(messages[index])
        if not match:
            continue
        count = int(match.group(1))
        if expected_count is not None and count != expected_count:
            continue
        if count == 0:
            return []
        names = _names(match.group(2))
        if names is None:
            continue
        if len(names) < count:
            # Some Forge versions emit names on the following line(s).
            for following in messages[index + 1:index + 1 + count + 2]:
                extra = _names(following)
                if extra is None or not extra:
                    break
                names.extend(extra)
                if len(names) >= count:
                    break
        if len(names) == count:
            return names
    return None


def filter_console_lines(lines: list[str], enabled: bool) -> list[str]:
    """Hide /list status lines and subsequent standalone player-name lines."""
    if not enabled:
        return list(lines)
    filtered: list[str] = []
    remaining_names = 0
    for line in lines:
        message = message_text(line)
        match = PLAYER_HEADER.search(message)
        if match:
            count = int(match.group(1))
            inline = _names(match.group(2))
            remaining_names = max(0, count - len(inline or []))
            continue
        if remaining_names:
            names = _names(message)
            if names:
                remaining_names = max(0, remaining_names - len(names))
                continue
            remaining_names = 0
        filtered.append(line)
    return filtered


def parse_tps(lines: list[str]) -> float | None:
    """Read an actual TPS reported by /tps or /forge tps; never infer it from lag."""
    for line in reversed(lines):
        message = message_text(line)
        for pattern in (TPS_TRIPLE, TPS_SINGLE):
            match = pattern.search(message)
            if match:
                value = float(match.group(1))
                if 0 <= value <= 20.1:
                    return round(min(value, 20.0), 2)
    return None


def parse_lag(lines: list[str]) -> tuple[int, int, str] | None:
    """Last lag warning: milliseconds behind, ticks skipped, original line."""
    for line in reversed(lines):
        match = LAG.search(message_text(line))
        if match:
            return int(match.group(1).replace(",", "")), int(match.group(2).replace(",", "")), str(line)
    return None


def parse_metadata(lines: list[str]) -> dict[str, Any]:
    """Extract only information explicitly present in recent server logs."""
    result: dict[str, Any] = {}
    for line in lines:
        message = message_text(line)
        for pattern in VERSION_PATTERNS:
            match = pattern.search(message)
            if match:
                result["version"] = match.group(1)
                break
        match = PORT.search(message)
        if match and 1 <= int(match.group(1)) <= 65535:
            result["port"] = int(match.group(1))
        match = MOD_COUNT.search(message)
        if match:
            result["mod_count"] = int(match.group(1))
    return result
