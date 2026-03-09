---
name: teslamate
description: "Query real-time Tesla vehicle data via TeslaMate. Use this skill to answer questions about battery level and range, charging state, GPS location, lock status, inside/outside temperature, car state (online/asleep/driving), recent trips, charging history, and cumulative stats. Requires the TeslaMate connector daemon to be running locally."
allowed-tools: ["Bash"]
metadata: {"openclaw": {"requires": {"bins": ["curl"]}, "emoji": "🚗"}}
---

Query the local TeslaMate connector API using curl. The connector runs at `http://127.0.0.1:18790`.

## Available intents

| Intent | When to use | Extra params |
|--------|-------------|-------------|
| `battery_level` | Battery percentage and estimated range | — |
| `charging_state` | Charging status, plugged in or not | — |
| `location` | Current GPS coordinates + map link | — |
| `lock_status` | Whether the car is locked | — |
| `temperature` | Inside and outside temperature | — |
| `car_state` | Overall state: online / asleep / driving / charging | — |
| `full_status` | Summary of all of the above | — |
| `recent_charges` | Last 5 charging sessions | — |
| `recent_drives` | Last 5 trips | — |
| `drives_summary` | Total km / trips / duration in the past N days | `days=7` (default 7) |
| `longest_drive` | The single longest trip ever recorded | — |
| `stats` | Cumulative totals: distance, charges, energy | — |

## How to query

```bash
curl -s "http://127.0.0.1:18790/query?intent=<INTENT>"
```

Extra parameters are appended as additional query string arguments.

### Examples

User asks "What's my battery level?":
```bash
curl -s "http://127.0.0.1:18790/query?intent=battery_level"
```

User asks "How many km did I drive this week?":
```bash
curl -s "http://127.0.0.1:18790/query?intent=drives_summary&days=7"
```

User asks "How many km did I drive this month?":
```bash
curl -s "http://127.0.0.1:18790/query?intent=drives_summary&days=30"
```

User asks "What was my longest trip ever?":
```bash
curl -s "http://127.0.0.1:18790/query?intent=longest_drive"
```

User asks "Give me a full status report":
```bash
curl -s "http://127.0.0.1:18790/query?intent=full_status"
```

## Response format

All responses are JSON:
```json
{"text": "当前电量：82%，预计续航约 310 km"}
```

Return the value of the `"text"` field directly to the user.

## If the connector is not running

If curl returns a connection error, tell the user:
> "TeslaMate connector is not running. Please start it with: `uv run python -m teslamate_connector` in the connector project directory."
