# TeslaMate Connector — Agent Installation Guide

You are an AI assistant helping the user install and configure the TeslaMate OpenClaw Connector. This project lets the user query their Tesla vehicle data (battery, location, charging state, etc.) through natural language in OpenClaw.

## Architecture (understand this before starting)

```
OpenClaw model
    │  reads description, decides to use skill
    ▼
skills/teslamate/SKILL.md   ← installed at ~/.openclaw/skills/teslamate/
    │  executes Bash tool
    ▼
curl http://127.0.0.1:18790/query?intent=battery_level
    │  local HTTP call
    ▼
teslamate_connector daemon  ← Python process, runs in background
    │  MQTT over Tailscale
    ▼
TeslaMate cloud server
```

The connector is **not** a WebSocket plugin — it is a local HTTP daemon. OpenClaw's skill system calls it via curl.

---

## Step 1 — Check prerequisites

```bash
python3 --version   # must be 3.12+
uv --version        # must be installed
git --version
curl --version
```

**If uv is missing:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Ask the user for two values:**
1. "What is your TeslaMate server's Tailscale IP? (format: 100.x.x.x)"
2. "What is your car's ID in TeslaMate? (default: 1 — check TeslaMate settings if unsure)"

Store these — you will need them in Step 3.

---

## Step 2 — Clone and install

```bash
git clone https://github.com/orange90/teslamate_openclaw_connector.git
cd teslamate_openclaw_connector
uv sync
```

Expected: completes without errors, installs `paho-mqtt`, `httpx`, `pyyaml`.

---

## Step 3 — Create config.yaml

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` using the values from Step 1:

```yaml
teslamate:
  tailscale_ip: "<TAILSCALE_IP>"
  mqtt_port: 1883
  api_port: 8080
  car_id: <CAR_ID>

openclaw:
  http_port: 18790
```

---

## Step 4 — Verify MQTT connectivity

```bash
nc -zv <TAILSCALE_IP> 1883
```

**If this succeeds:** move to Step 5.

**If this fails:** work through the troubleshooting tree:

### 4a — Check Tailscale tunnel
```bash
ping -c 3 <TAILSCALE_IP>
```
- Ping fails → Tailscale is disconnected. Ask the user to check both machines are logged in to the same Tailscale account.
- Ping succeeds but nc fails → continue to 4b.

### 4b — Check mosquitto port on the cloud server
SSH into the cloud server:
```bash
ss -tlnp | grep 1883
```
- No output → mosquitto not running: `docker compose up -d mosquitto`
- Shows `127.0.0.1:1883` → port not exposed externally. Find `/opt/teslamate/docker-compose.yml`, uncomment the mosquitto ports block, then: `docker compose up -d mosquitto`
- Shows `0.0.0.0:1883` but nc still fails → Docker iptables blocking Tailscale:

```bash
# On the cloud server:
iptables -I DOCKER-USER -i tailscale0 -j ACCEPT
apt install iptables-persistent -y && netfilter-persistent save
```

### 4c — Verify data is flowing
```bash
# macOS: brew install mosquitto if needed
mosquitto_sub -h <TAILSCALE_IP> -t "teslamate/cars/#" -v
```
Ask the user to wake their car from the Tesla app. Within 30 seconds you should see lines like `teslamate/cars/1/battery_level 82`. Press Ctrl+C.

**If no data appears:** check TeslaMate logs on the cloud server:
```bash
docker compose logs --tail=30 teslamate | grep -iE 'mqtt|error|domain'
```
If logs show `"non-existing domain"` for Tesla API calls, Docker DNS is broken:
```bash
# On the cloud server:
cat > /etc/docker/daemon.json << 'EOF'
{"dns": ["114.114.114.114", "8.8.8.8"]}
EOF
systemctl restart docker
cd /opt/teslamate && docker compose up -d
```
Wait 15 seconds, then check: `docker compose logs --tail=5 teslamate` — should show `MQTT connection has been established`.

---

## Step 5 — Start the connector daemon

Run this in a terminal (keep it running in the background):

```bash
cd teslamate_openclaw_connector
uv run python -m teslamate_connector
```

Expected output:
```
[INFO] Loaded config: TeslaMate at 100.x.x.x
[INFO] MQTT client started, connecting to 100.x.x.x:1883
[INFO] MQTT connected to 100.x.x.x:1883
[INFO] Subscribed to teslamate/cars/1/#
[INFO] Local HTTP API listening on http://127.0.0.1:18790
[INFO] Connector ready. Query with: curl http://127.0.0.1:18790/query?intent=full_status
```

Verify it works:
```bash
curl -s "http://127.0.0.1:18790/query?intent=battery_level"
```
Expected: `{"text": "当前电量：XX%，预计续航约 XXX km"}`

---

## Step 6 — Install the OpenClaw skill

Copy the skill directory to OpenClaw's skills folder:

```bash
mkdir -p ~/.openclaw/skills
cp -r skills/teslamate ~/.openclaw/skills/teslamate
```

Verify:
```bash
cat ~/.openclaw/skills/teslamate/SKILL.md | head -5
```

OpenClaw loads skills automatically from `~/.openclaw/skills/`. No restart needed if OpenClaw is already running — the skill will be available on the next conversation.

---

## Step 7 — End-to-end verification

Ask the user to send this message in OpenClaw:
> "What's my Tesla's battery level?"

OpenClaw should invoke the `teslamate` skill, which calls:
```bash
curl -s "http://127.0.0.1:18790/query?intent=battery_level"
```
And return the battery percentage to the user.

If OpenClaw says the skill is not available, ask the user to restart OpenClaw or check that `~/.openclaw/skills/teslamate/SKILL.md` exists.

Installation is complete.

---

## Keeping the daemon running

To run the connector automatically at login (macOS):

```bash
# Create a launchd plist — ask the user for the actual project path first
PROJECT_PATH="$(pwd)"  # run this inside the project directory

cat > ~/Library/LaunchAgents/com.teslamate.connector.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.teslamate.connector</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_PATH/.venv/bin/python</string>
        <string>-m</string>
        <string>teslamate_connector</string>
        <string>$PROJECT_PATH/config.yaml</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_PATH</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$PROJECT_PATH/connector.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_PATH/connector.log</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.teslamate.connector.plist
```
