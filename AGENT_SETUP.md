# TeslaMate Connector — Agent Installation Guide

You are an AI assistant helping the user install and configure the TeslaMate OpenClaw Connector. This project lets the user query their Tesla vehicle data (battery, location, charging state, etc.) through natural language.

Follow the steps below in order. At each step, run the commands, check the output, and handle errors before moving on. Ask the user only when their input is genuinely required.

---

## Step 1 — Check prerequisites

Run the following checks. If anything is missing, install it before continuing.

```bash
# Python 3.12+
python3 --version

# uv
uv --version

# git
git --version
```

**If uv is missing:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Tailscale check — ask the user:**
> "What is your TeslaMate server's Tailscale IP? (format: 100.x.x.x)"

Also ask:
> "What car ID is your Tesla in TeslaMate? (default: 1)"

Store these answers — you will need them in Step 3.

---

## Step 2 — Clone and install

```bash
git clone https://github.com/orange90/teslamate_openclaw_connector.git
cd teslamate_openclaw_connector
uv sync
```

Expected: `uv sync` completes without errors and installs all packages including `paho-mqtt`, `httpx`, `websockets`, `pyyaml`.

---

## Step 3 — Create config.yaml

Fill in the values collected in Step 1:

```bash
cp config.yaml.example config.yaml
```

Then edit `config.yaml` with the user's Tailscale IP and car ID:

```yaml
teslamate:
  tailscale_ip: "<TAILSCALE_IP>"   # from Step 1
  mqtt_port: 1883
  api_port: 8080
  car_id: <CAR_ID>                 # from Step 1

openclaw:
  gateway_url: "ws://127.0.0.1:18789"
  skill_id: "teslamate"
```

---

## Step 4 — Verify MQTT connectivity

```bash
nc -zv <TAILSCALE_IP> 1883
```

**If this succeeds:** move on to Step 5.

**If this fails ("Connection refused" or timeout):** follow the troubleshooting tree below.

### Troubleshooting tree

#### 4a — Check Tailscale tunnel first
```bash
ping -c 3 <TAILSCALE_IP>
```
- If ping fails: Tailscale is not connected. Ask the user to check that both machines are logged in to the same Tailscale account.
- If ping succeeds but nc fails: continue to 4b.

#### 4b — Check if mosquitto port is exposed on the server
SSH into the cloud server and run:
```bash
ss -tlnp | grep 1883
```

- If no output: mosquitto is not running. Ask the user to start it: `docker compose up -d mosquitto`
- If output shows `127.0.0.1:1883`: port is only listening locally. Fix:

On the cloud server, find the TeslaMate docker-compose.yml (usually `/opt/teslamate/docker-compose.yml`) and change the mosquitto service:
```yaml
# Before (commented out):
mosquitto:
  # ports:
  #   - 1883:1883

# After:
mosquitto:
  ports:
    - 1883:1883
```
Then restart: `docker compose up -d mosquitto`

- If output shows `0.0.0.0:1883` but nc still fails: Docker iptables may be blocking Tailscale traffic. Fix:

```bash
# On the cloud server:
iptables -I DOCKER-USER -i tailscale0 -j ACCEPT
apt install iptables-persistent -y && netfilter-persistent save
```

#### 4c — Verify data is actually flowing

Once nc succeeds, subscribe to MQTT and ask the user to wake their car from the Tesla app:

```bash
# Install if needed: brew install mosquitto (macOS)
mosquitto_sub -h <TAILSCALE_IP> -t "teslamate/cars/#" -v
```

Wait up to 30 seconds. If data like `teslamate/cars/1/battery_level 82` appears, MQTT is working. Press Ctrl+C.

**If no data appears after 30 seconds:** TeslaMate may not be publishing. On the cloud server:

```bash
docker compose logs --tail=30 teslamate | grep -iE 'mqtt|error|domain'
```

If logs show `"non-existing domain"` for Tesla API calls, Docker DNS is broken. Fix:

```bash
# On the cloud server:
cat > /etc/docker/daemon.json << 'EOF'
{
  "dns": ["114.114.114.114", "8.8.8.8"]
}
EOF
systemctl restart docker
cd /opt/teslamate && docker compose up -d
```

Wait ~15 seconds, then check logs again:
```bash
docker compose logs --tail=10 teslamate | grep -iE 'mqtt|token|online'
```
Should show: `MQTT connection has been established` and `car_id=1 Start / :online`

---

## Step 5 — Start the connector

From the project directory:

```bash
uv run python -m teslamate_connector
```

Confirm the following lines appear in the output:
- `MQTT connected to <TAILSCALE_IP>:1883`
- `Subscribed to teslamate/cars/1/#`
- `Registered skill 'teslamate' with OpenClaw Gateway`

If the Gateway connection fails (`OSError` or `ConnectionClosed`), it will auto-retry every 5 seconds — this is expected if OpenClaw Gateway is not yet running.

---

## Step 6 — Register the skill with OpenClaw

Import the skill definition file into OpenClaw:

```
skills/teslamate.yaml
```

This file defines 10 intents. After importing, the following natural language queries will work:

| Say this | Intent triggered |
|----------|-----------------|
| "What's my battery level?" | `battery_level` |
| "Is my car charging?" | `charging_state` |
| "Where is my car?" | `location` |
| "Is it locked?" | `lock_status` |
| "What's the temperature inside?" | `temperature` |
| "What state is the car in?" | `car_state` |
| "Give me a full status" | `full_status` |
| "Show my recent charges" | `recent_charges` |
| "Show my recent trips" | `recent_drives` |
| "What are my total stats?" | `stats` |

---

## Step 7 — Verify end-to-end

Ask the user to send this message in OpenClaw:
> "What's my Tesla's battery level?"

The connector should log `Handling intent: battery_level` and OpenClaw should reply with the current charge percentage.

Installation is complete.

---

## Reference — What each file does

| File | Purpose |
|------|---------|
| `config.yaml` | Your local config (gitignored) |
| `src/teslamate_connector/main.py` | Entry point, WebSocket loop |
| `src/teslamate_connector/mqtt_client.py` | Subscribes to TeslaMate MQTT |
| `src/teslamate_connector/rest_client.py` | Calls TeslaMateApi REST |
| `src/teslamate_connector/skill_handler.py` | Maps intents to data queries |
| `skills/teslamate.yaml` | OpenClaw skill definition |
