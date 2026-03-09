# TeslaMate OpenClaw Connector

Query your Tesla through OpenClaw AI: "What's my battery level?" "Where's my car parked?" "Show me my last charging session."

This connector runs on your local machine, securely fetching vehicle data from a cloud-hosted TeslaMate instance via Tailscale, and exposing it to the OpenClaw AI assistant as a skill.

[中文文档 →](README.zh.md)

---

## What You Can Ask

Once set up, ask OpenClaw anything about your Tesla in natural language:

| Question | Example Response |
|----------|-----------------|
| What's my battery level? | Battery: 82%, estimated range ~310 km |
| Is my car charging? | Charging state: Disconnected |
| Where is my car? | Lat 31.23, Lon 121.47 (Google Maps link) |
| Is my car locked? | Locked |
| What's the temperature inside? | Inside: 22.3°C, Outside: 18.1°C |
| Show my recent trips | Last 5 drives listed |
| Show my charging history | Last 5 charging sessions listed |

---

## How It Works

```
You ──chat──▶ OpenClaw AI
                  │
                  ▼
          OpenClaw Gateway
          (localhost :18789)
                  │ WebSocket
                  ▼
  teslamate_openclaw_connector    ← this project, runs on your machine
                  │
                  │ Tailscale encrypted tunnel (no public ports needed)
                  ▼
          TeslaMate Cloud Server
          ├── MQTT broker  — real-time data (battery, location, temps…)
          └── REST API     — historical data (trips, charges)
```

TeslaMate never needs to expose any ports to the public internet — all traffic flows through Tailscale's encrypted private network.

---

## Prerequisites

Check off each item before proceeding:

**1. TeslaMate is deployed and running**

TeslaMate should be running on a cloud server (VPS, NAS, etc.) and actively recording your Tesla's data.

**2. Tailscale installed on your cloud server**

```bash
# Run on the cloud server
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

After logging in, find the server's **Tailscale IP** (format: `100.x.x.x`) at [login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines).

**3. Tailscale installed on your local machine**

Download from [tailscale.com/download](https://tailscale.com/download) and sign in with the same account. Both machines must be in the same tailnet.

Verify the tunnel:
```bash
ping 100.x.x.x   # replace with your server's Tailscale IP
```

**4. Python 3.12+ and uv**

```bash
python3 --version   # must be 3.12 or higher
```

Install uv (Python package manager):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**5. OpenClaw Gateway running locally**

The connector expects OpenClaw Gateway at `ws://127.0.0.1:18789` by default. Adjust in `config.yaml` if yours differs.

---

## Setup

### Step 1 — Clone the repo

```bash
git clone https://github.com/orange90/teslamate_openclaw_connector.git
cd teslamate_openclaw_connector
```

### Step 2 — Install dependencies

```bash
uv sync
```

This creates a virtual environment and installs everything automatically.

### Step 3 — Configure

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml`:

```yaml
teslamate:
  tailscale_ip: "100.x.x.x"            # ← your server's Tailscale IP
  mqtt_port: 1883                        # default, usually no change needed
  api_port: 8080                         # default, usually no change needed
  car_id: 1                              # change if you have multiple cars

openclaw:
  gateway_url: "ws://127.0.0.1:18789"   # default, usually no change needed
  skill_id: "teslamate"
```

> `config.yaml` is listed in `.gitignore` and will never be committed.

### Step 4 — Verify connectivity (recommended)

```bash
# Install mosquitto clients if needed: brew install mosquitto (macOS)
mosquitto_sub -h 100.x.x.x -t "teslamate/cars/#" -v
```

You should see lines like `teslamate/cars/1/battery_level 82` within a few seconds of waking your car from the Tesla app. Press `Ctrl+C` to stop.

If this step fails, see the [Troubleshooting](#troubleshooting) section below before continuing.

### Step 5 — Start the connector

```bash
uv run python -m teslamate_connector
```

Expected output:
```
[INFO] Loaded config: TeslaMate at 100.x.x.x
[INFO] MQTT client started, connecting to 100.x.x.x:1883
[INFO] Connecting to OpenClaw Gateway: ws://127.0.0.1:18789
[INFO] MQTT connected to 100.x.x.x:1883
[INFO] Subscribed to teslamate/cars/1/#
[INFO] Registered skill 'teslamate' with OpenClaw Gateway
```

### Step 6 — Use in OpenClaw

Import `skills/teslamate.yaml` into OpenClaw, then start chatting:
- "What's my Tesla's battery level?"
- "Where is my car?"
- "Is it locked?"
- "Show me my last charge"

---

## Supported Intents

| Intent | Description |
|--------|-------------|
| `battery_level` | Current charge percentage and estimated range |
| `charging_state` | Charging status and whether plugged in |
| `location` | Current GPS coordinates + Google Maps link |
| `lock_status` | Whether the car is locked |
| `temperature` | Inside and outside temperature |
| `car_state` | Overall state (online / asleep / driving / charging) |
| `full_status` | Combined summary of all of the above |
| `recent_charges` | Last 5 charging sessions (requires REST API) |
| `recent_drives` | Last 5 trips (requires REST API) |
| `stats` | Cumulative stats: total distance, charges, energy used |

> `recent_charges`, `recent_drives`, and `stats` require [TeslaMateApi](https://github.com/tobiasehlert/teslamateapi) to be deployed alongside TeslaMate.

---

## Troubleshooting

These are real issues encountered during deployment, with the fixes that worked.

---

### Issue 1 — `mosquitto_sub` reports "bad file descriptor" or "Connection refused"

**Diagnose first:**
```bash
ping 100.x.x.x        # should succeed if Tailscale tunnel is up
nc -zv 100.x.x.x 1883 # tests whether port 1883 is reachable
```

**Fix A — MQTT port not exposed**

The default TeslaMate `docker-compose.yml` has the mosquitto port commented out:
```yaml
mosquitto:
  # ports:
  #   - 1883:1883
```

Uncomment it on your cloud server:
```yaml
mosquitto:
  ports:
    - 1883:1883
```

Then restart:
```bash
docker compose up -d mosquitto
```

**Fix B — Docker iptables blocking Tailscale traffic**

Docker's auto-generated iptables rules sometimes don't cover the Tailscale interface (`tailscale0`). Run on your cloud server:

```bash
iptables -I DOCKER-USER -i tailscale0 -j ACCEPT

# Persist across reboots
apt install iptables-persistent -y
netfilter-persistent save
```

---

### Issue 2 — Port is reachable, but no MQTT data arrives

**Symptom:** `nc -zv` succeeds, `mosquitto_sub` connects without error, but no messages appear even after waking the car.

**Cause:** Two mosquitto containers are running. The one with the exposed port is empty — TeslaMate is publishing to a different, internal mosquitto container.

**Diagnose:**
```bash
docker ps --format 'table {{.Names}}\t{{.Networks}}\t{{.Ports}}' | grep mosquitto
```

If you see two mosquitto containers, the one in TeslaMate's Docker network (likely without a host port mapping) is the active one.

**Fix:**
1. Stop the extra mosquitto container (e.g. `docker compose down` in `/root` if you created one there)
2. Add port mapping to TeslaMate's mosquitto service (see Fix A above)
3. Restart: `docker compose up -d mosquitto`

---

### Issue 3 — Mosquitto has data internally, but TeslaMate isn't publishing

**Diagnose from inside the container:**
```bash
# On your cloud server
docker compose exec mosquitto mosquitto_sub -t "teslamate/cars/#" -v

# Check TeslaMate logs
docker compose logs --tail=50 teslamate
```

**Cause — DNS resolution failure inside Docker**

If TeslaMate logs show:
```
GET https://owner-api.tesla.cn/... -> error: "non-existing domain"
```

The Docker container can't resolve Tesla's API domains. This usually happens when the host's DNS service (`systemd-resolved`) is broken.

**Fix — Set external DNS for Docker:**
```bash
# On your cloud server
cat > /etc/docker/daemon.json << 'EOF'
{
  "dns": ["114.114.114.114", "8.8.8.8"]
}
EOF

systemctl restart docker
cd /path/to/teslamate
docker compose up -d
```

After restart, TeslaMate logs should show:
```
POST https://auth.tesla.cn/oauth2/v3/token -> 200
MQTT connection has been established
car_id=1 Start / :online
```

---

## Local Development

To develop without a real TeslaMate, use the included Docker Compose file to run a local MQTT broker and publish mock data:

```bash
docker compose up -d

# Set tailscale_ip to 127.0.0.1 in config.yaml, then publish test data:
mosquitto_pub -h 127.0.0.1 -t "teslamate/cars/1/battery_level" -m "75"
mosquitto_pub -h 127.0.0.1 -t "teslamate/cars/1/state" -m "online"
mosquitto_pub -h 127.0.0.1 -t "teslamate/cars/1/locked" -m "true"

uv run python -m teslamate_connector
```

---

## Project Structure

```
teslamate_openclaw_connector/
├── config.yaml.example          # configuration template
├── pyproject.toml               # Python project and dependencies
├── skills/
│   └── teslamate.yaml           # OpenClaw skill definition (intent list)
├── src/
│   └── teslamate_connector/
│       ├── main.py              # entry point, WebSocket loop with auto-reconnect
│       ├── config.py            # loads config.yaml
│       ├── mqtt_client.py       # subscribes to TeslaMate MQTT topics
│       ├── rest_client.py       # calls TeslaMateApi REST endpoints
│       └── skill_handler.py     # maps OpenClaw intents to data queries
└── docker-compose.yml           # local Mosquitto broker for development
```

---

## Security

- **No public ports required** — all communication goes through Tailscale's encrypted tunnel
- **Read-only** — this connector never sends control commands to the vehicle
- **Config is gitignored** — `config.yaml` (containing your Tailscale IP) will never be accidentally committed
