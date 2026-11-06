"""Parser regression tests; can run without Home Assistant installed."""
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / 'custom_components' / 'mcss' / 'parsing.py'
spec = importlib.util.spec_from_file_location('mcss_parsing_test', MODULE)
parsing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parsing)


def test_player_list_vanilla():
    lines = ['[01:59:17] [Server thread/INFO] [minecraft/MinecraftServer]: There are 1 of a max of 20 players online: Barrel0Memes97']
    assert parsing.parse_players(lines, 1) == ['Barrel0Memes97']
    assert parsing.parse_players(lines, 0) is None
    assert parsing.filter_console_lines(lines, True) == []
    assert parsing.filter_console_lines(lines, False) == lines


def test_latest_list_wins_and_zero():
    lines = ['There are 1/10 players online: Alice', 'There are 0/10 players online:']
    assert parsing.parse_players(lines) == []
    assert parsing.parse_players(lines, expected_count=0) == []
    assert parsing.parse_players(lines, expected_count=1) == ['Alice']


def test_multiline_list_and_noise():
    lines = ['[00:00:00] [Server thread/INFO]: There are 2/20 players online:',
             '[00:00:00] [Server thread/INFO]: Alex, Steve',
             '[00:00:00] [Server thread/INFO]: Server saved']
    assert parsing.parse_players(lines, 2) == ['Alex', 'Steve']
    assert parsing.filter_console_lines(lines, True) == [lines[-1]]


def test_bad_names_rejected():
    assert parsing.parse_players(['There are 1/10 players online:', 'Chunk loaded'], 1) is None
    assert parsing.parse_players(['There are 2/10 players online: Alex'], 2) is None


def test_real_tps_not_lag_estimate():
    assert parsing.parse_tps(['[Server/WARN]: Can\'t keep up! Running 2104ms behind, skipping 42 tick(s)']) is None
    assert parsing.parse_lag(['[Server/WARN]: Running 2104ms behind, skipping 42 tick(s)'])[:2] == (2104, 42)
    assert parsing.parse_tps(['[23:59:00] [Server thread/INFO]: TPS from last 1m, 5m, 15m: *19.85, *20.0, 20.0']) == 19.85
    assert parsing.parse_tps(['[23:59:00] [Server thread/INFO]: Mean TPS: 18.76']) == 18.76


def test_server_version_and_port_parsing():
    lines = [
        '[00:10:00] [Server thread/INFO]: Starting minecraft server version 1.20.1',
        '[00:10:02] [Server thread/INFO]: Starting Minecraft server on *:25567',
        '[00:10:05] [main/INFO]: Loaded 135 mods',
    ]
    assert parsing.parse_metadata(lines) == {'version': '1.20.1', 'port': 25567, 'mod_count': 135}
    assert parsing.parse_metadata(['Loading Minecraft 1.21.1 with Fabric Loader 0.16.9'])['version'] == '1.21.1'


def test_multiline_names_with_minecraft_logger_prefix():
    lines = [
        '[01:59:17] [Server thread/INFO] [minecraft/MinecraftServer]: There are 2 of a max of 20 players online:',
        '[01:59:17] [Server thread/INFO] [minecraft/MinecraftServer]: Alex, Steve',
        '[01:59:18] [Server thread/INFO] [minecraft/MinecraftServer]: Done!',
    ]
    assert parsing.parse_players(lines, 2) == ['Alex', 'Steve']
    assert parsing.filter_console_lines(lines, True) == [lines[-1]]
