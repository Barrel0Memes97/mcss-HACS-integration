![](https://www.mcserversoft.com/assets/preview.png)



**"MC Server Soft is a server wrapper which is a program that doesn't change anything about the Minecraft server itself. It is an UI built on top of the server console, with the purpose of adding additional functionality and ease of management for the server owner."** -MC Server Soft Team

MCSS v2 API integration for MC Server Soft 13.7+.

Useful links:
- MCSS API docs: https://docs.mcserversoft.com/apis/v2
- MCSS Homepage: https://www.mcserversoft.com/
- MCSS Donation Page: https://www.mcserversoft.com/donate




# MC Server Soft Home Assistant Integration

Configured through Home Assistant's UI. It reads the API key from an existing
input_text helper entity and discovers the servers returned by `/api/v2/servers`.

This intigration dynamically adds newly discovered servers. When MCSS removes a server, its existing HA entities become unavailable; they are not forcibly deleted from the entity registry

Current defaults:
- MCSS host: http://192.168.254.254:25560
- API key entity: input_text.mcss_apikey
- Poll interval: 
  - Integration update interval      :15
  - Console refresh interval         :15
  - Player name update interval      :60

Install as a HACS custom repository by pointing HACS at this repository 
`https://github.com/Barrel0Memes97/mcss-HACS-integration`

# API key

The integration references an existing Home Assistant `input_text` instead of storing a second copy of the key.

Example:

```yaml
input_text:
  mcss_apikey:
    name: MCSS API Key
    mode: password
    max: 200
```

1. Go to Settings / Devices & services / Helpers
2. Find MCSS API Key
3. Click it and enter your API key

Remember to click save

Then select `input_text.mcss_apikey` during setup.


# Features:

- Server controls 
    - Start
    - Stop
    - Force stop
    - Restart
- Current CPU used by the server
- Max players
- Curent player count
- Max RAM allucated
- Total RAM used

Added in V2

- Configurable data reload interval
- Server pack icons
- Server uptime
  - Display as `HH:MM:SS`, or even `WW:DD:HH:MM:SS` if needed

- Active players list
  - Player names
  - Potentially player-specific information
    - ~~Player heads?~~ Definitly not an easy thing for me to add, but would be cool

- Console command input
  - Text field for entering console commands
  - Button/action to send the command to the server

- Most recent console output
  - Entity containing the latest console output
  - Update when new console output is received

- Server status
  - Online/offline
  - Starting
  - Stopping
  - Restarting

# TO DO:

- Server connection information
  - Server address
  - Server port

- Server information
  - Server version
  - Server type/loader
  - Modpack/mod information

- Add TPS counter (**T**icks **P**er **S**econd)
  - Pull server slowdown metrics into HA, for example:
    ``` console
    Can't keep up! Did the system time change, or is the server overloaded? Running 2104ms behind, skipping 42 tick(s)
    ```
- console filter
  - toggle entity to remove messages like
    ``` console
    [01:59:17] [Server thread/INFO] [minecraft/MinecraftServer]: There are 1 of a max of 20 players online: Barrel0Memes97
    ```
    from the console entity that is added already

- Fix player list
  - Bug where the number of connected players is correctly set to 0 when everyone disconnects, but the list of active players keeps a player or two incorrectly.

- Add default server icon unless server provides an icon
