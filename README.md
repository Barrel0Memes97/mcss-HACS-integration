![](https://www.mcserversoft.com/assets/preview.png)



**"MC Server Soft is a server wrapper which is a program that doesn't change anything about the Minecraft server itself. It is an UI built on top of the server console, with the purpose of adding additional functionality and ease of management for the server owner." -MC Server Soft Team**

MCSS v2 API integration for MC Server Soft 13.7+.

Useful links:
- MCSS API docs: https://docs.mcserversoft.com/apis/v2
- MCSS Homepage: https://www.mcserversoft.com/
- MCSS Donation Page: https://www.mcserversoft.com/donate




# MC Server Soft Home Assistant Integration

Configured through Home Assistant's UI. It reads the API key from an existing
input_text helper entity and discovers the servers returned by `/api/v2/servers`.

Current defaults:
- MCSS host: http://192.168.254.254:25560
- API key entity: input_text.mcss_apikey
- Poll interval: 15 seconds

Install as a HACS custom repository by pointing HACS at this repository 
`https://github.com/Barrel0Memes97/mcss-HACS-integration`


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

# TO DO:
- Configurable data reload interval
- Server pack icons
- Server uptime
  - Display as `HH:MM:SS`, or even `WW:DD:HH:MM:SS` if needed

- Active players list
  - Player names
  - Potentially player-specific information
    - Player heads?

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

- Server connection information
  - Server address
  - Server port

- Server information
  - Server version
  - Server type/loader
  - Modpack/mod information

