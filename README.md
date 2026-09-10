
# MC Server Soft Home Assistant Integration

MCSS v2 API integration for MC Server Soft 13.7+.

Configured through Home Assistant's UI. It reads the API key from an existing
input_text entity and discovers the servers returned by `/api/v2/servers`.

Current defaults:
- MCSS host: http://192.168.254.74:25566
- API key entity: input_text.mcss_apikey
- Poll interval: 15 seconds

Install as a HACS custom repository by pointing HACS at the repository containing
the `custom_components/mcss` directory.
