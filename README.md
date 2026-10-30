# Anker SOLIX S5000 — Home Assistant Integration

[![Version](https://img.shields.io/github/v/tag/kobusm/AnkerHA?label=version&sort=semver)](https://github.com/kobusm/AnkerHA/tags)

**Version 1.0.2**

A Home Assistant custom integration for the **Anker SOLIX S5000** portable power station (model `AS510`). It also works with the **SOLIX S2000** (`AS220`), which shares the same MQTT message format.

Unlike the EcoFlow Delta Pro, the S5000 has no documented local API. This integration therefore uses the **Anker cloud** to log in and find the device, then the **Anker MQTT server** for real-time push data and control. It is built on [thomluther/anker-solix-api](https://github.com/thomluther/anker-solix-api), which is vendored into the integration so no extra Python package is needed.

> **Status: tested on a real Anker SOLIX S5000.** The library knows the S5000's model code but doesn't decode its MQTT messages itself. This integration reads them with the S2000's message map, which works on the S5000 (see [How It Works](#how-it-works)). S2000 support comes from the library's S2000 mapping and hasn't been tested on S2000 hardware by this project. Please report anything that reads wrong (see [Contributing](#contributing)).

## Requirements

- Anker SOLIX S5000 (or S2000) added to the Anker app and online over Wi-Fi
- The **owner** Anker account (the email/password used in the Anker app). Since Anker app 3.10, one account can be signed in on the app and here at the same time.
- Home Assistant 2024.11 or newer
- Internet access from Home Assistant

## Installation

### HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add this repository's URL as an **Integration**
3. Install **Anker SOLIX S5000**
4. Restart Home Assistant

### Manual

1. Copy `custom_components/anker_solix_s5000/` into your HA `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. **Settings → Integrations → Add Integration → Anker SOLIX S5000**
2. Enter your Anker account email and password
3. Enter the two-letter country code you selected in the Anker app (e.g. `US`, `DE`, `ZA`). It defaults to your Home Assistant country.
4. If the account has more than one supported unit, pick which one to add. Repeat the flow for each additional unit.

If Anker later rejects the stored password, Home Assistant prompts you to re-authenticate.

## Entities

### Sensors

| Sensor | Unit | Default |
|--------|------|---------|
| Battery Level | % | enabled |
| Battery Health | % | enabled (diagnostic) |
| Remaining Time | h | enabled |
| Temperature | °C / °F (follows device setting) | enabled |
| Total Input Power | W | enabled |
| Total Output Power | W | enabled |
| AC Input Power | W | enabled |
| AC Output Power | W | enabled |
| Solar / DC Input Power | W | enabled |
| USB Output Power | W | enabled |
| AC Frequency | Hz | enabled (diagnostic) |
| Firmware Version | — | enabled (diagnostic) |
| Main Battery Level | % | disabled |
| AC Charging Power Max | W | disabled |
| AC Output Timer Remaining | s | disabled |
| Wi-Fi Signal | dBm | disabled |
| Battery / Working Status Code | raw | disabled (codes not decoded yet) |

### Binary Sensors

| Sensor | Description |
|--------|-------------|
| AC Input Connected | Grid / generator plugged in |
| AC Charging | AC input power > 0 |
| Solar / DC Charging | Solar or car input power > 0 |
| USB Output Active | USB ports powered |

### Switches

| Switch | Description |
|--------|-------------|
| AC Output | Enable / disable AC inverter outputs |
| AC Fast Charging | Maximum-rate AC charging |
| Display | Screen on / off |
| Port Memory | Restore output states after restart |

### Number

| Control | Range | Description |
|---------|-------|-------------|
| AC Charging Power | 100 W – device max, step 100 W | AC charge rate limit. The maximum follows the `ac_input_limit_max` value the device reports. |

### Selects

| Select | Options |
|--------|---------|
| Display Brightness | Low, Medium, High |
| Display Timeout (s) | 10, 20, 30, 60, 300, 1800 |
| Device Auto-Off (min) | Never, 30 … 1440 |
| AC Output Auto-Off (min) | Never, 15 … 1440 |
| Max Charge Level (%) | 80, 85, 90, 95, 100 |
| Min Discharge Level (%) | 1, 5, 10, 15, 20 |
| Temperature Unit | Celsius, Fahrenheit |

Options come from the library's command definitions at runtime, so they update when the library learns S5000-specific values.

The library also has S2000 commands for usage mode (UPS / Time-of-Use / Self-Consumption), backup reserve, storm guard and silent-charging schedules. They are deliberately left out for now: the S2000 status messages don't report their current values, so the entities would always show "unknown".

## How It Works

1. Logs in to the Anker cloud and finds the device on your account
2. Registers an **S5000 profile** at runtime ([`s5000.py`](custom_components/anker_solix_s5000/s5000.py)). It copies the library's S2000 (`AS220`) MQTT map to the S5000 (`AS510`) and enables the PPS controls for it. The vendored library itself is left untouched.
3. Connects to Anker's MQTT broker, subscribes to the device topic and requests a full status message
4. Arms the device's real-time stream, so it publishes every ~3–5 s for 300 s, then re-arms it every 240 s
5. Decoded values are pushed to entities as they arrive. Commands are encoded by the library and published over MQTT.

Controls are rejected if the device is in Anker's **local MQTT mode**.

## Development

```bash
python3.14 -m venv .venv
.venv/bin/pip install pytest-homeassistant-custom-component aiofiles
.venv/bin/python -m pytest
```

Tests use the real vendored library with the cloud and MQTT broker replaced by fakes. They cover the S5000 profile, that every control encodes to a valid MQTT command, the config flow (including reauth), and full HA setup with push updates and commands.

### Upgrading the vendored library

Replace `custom_components/anker_solix_s5000/solixapi/` with `src/anker_solix_api/` from a newer anker-solix-api release, update `VENDORED.md`, and run the tests. Once the library maps `AS510` natively, `register_s5000_profile()` leaves its map alone and only enables the controls.

## Contributing

If values look wrong on an S5000, the most useful data is a decoded MQTT dump. Run `mqtt_monitor.py` from [anker-solix-api](https://github.com/thomluther/anker-solix-api) against your device, or enable debug logging:

```yaml
logger:
  logs:
    custom_components.anker_solix_s5000: debug
```

Then share the output in an issue.

## License

MIT. The vendored anker-solix-api library is MIT licensed by its authors; see [`solixapi/LICENSE`](custom_components/anker_solix_s5000/solixapi/LICENSE).
