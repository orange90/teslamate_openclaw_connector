# TeslaMate OpenClaw Connector

通过 Tailscale 安全连接 TeslaMate，将特斯拉车辆数据接入 OpenClaw AI 助手。

## 系统架构

```
[OpenClaw] ──── WebSocket ──── [OpenClaw Gateway :18789]
                                        │
                             [teslamate_openclaw_connector]
                                        │ (Tailscale VPN)
                               [TeslaMate Cloud Server]
                               ├── MQTT Broker (:1883)
                               ├── TeslaMateApi REST (:8080)
                               └── PostgreSQL (:5432)
```

## 快速开始

### 1. 前置条件

- 本机已安装并登录 [Tailscale](https://tailscale.com/)
- TeslaMate 云服务器在同一 Tailscale 网络中，且 MQTT（1883）和 API（8080）端口可访问
- Python 3.12+ 和 [uv](https://docs.astral.sh/uv/) 包管理器

### 2. 安装依赖

```bash
uv sync
```

### 3. 配置

```bash
cp config.yaml.example config.yaml
# 编辑 config.yaml，填入 TeslaMate 服务器的 Tailscale IP
```

### 4. 验证连通性

```bash
# 验证 Tailscale 隧道
ping <tailscale-ip>

# 验证 MQTT
mosquitto_sub -h <tailscale-ip> -t "teslamate/cars/#" -v

# 验证 REST API
curl http://<tailscale-ip>:8080/api/v1/cars
```

### 5. 启动连接器

```bash
uv run python -m teslamate_connector
# 或者
uv run teslamate-connector
```

### 6. 注册 OpenClaw Skill

将 `skills/teslamate.yaml` 中的 skill 定义导入 OpenClaw，然后在对话中测试：

- "我的特斯拉现在电量多少？"
- "车停在哪里？"
- "车锁好了吗？"
- "最近一次充电记录"

## 配置说明

```yaml
teslamate:
  tailscale_ip: "100.x.x.x"  # TeslaMate 服务器的 Tailscale IP
  mqtt_port: 1883              # MQTT broker 端口（默认 1883）
  api_port: 8080               # TeslaMateApi 端口（默认 8080）
  car_id: 1                    # 车辆 ID（多车时修改）

openclaw:
  gateway_url: "ws://127.0.0.1:18789"  # OpenClaw Gateway WebSocket 地址
  skill_id: "teslamate"                 # Skill 标识符
```

## 支持的查询指令

| Intent | 说明 |
|--------|------|
| `battery_level` | 当前电量和预计续航 |
| `charging_state` | 充电状态和是否接入充电桩 |
| `location` | 车辆当前位置（经纬度 + Google Maps 链接）|
| `lock_status` | 车门锁定状态 |
| `temperature` | 车内外温度 |
| `car_state` | 车辆整体状态（在线/休眠/行驶中）|
| `full_status` | 完整状态摘要 |
| `recent_charges` | 最近充电记录（REST API）|
| `recent_drives` | 最近行驶记录（REST API）|
| `stats` | 累计统计数据（REST API）|

## 数据来源

- **实时数据**（电量、位置、温度等）：通过 MQTT 订阅 `teslamate/cars/{car_id}/#`
- **历史数据**（行程、充电记录）：通过 TeslaMateApi REST 接口

## 安全说明

- `config.yaml` 已加入 `.gitignore`，避免 Tailscale IP 泄露
- 数据通过 Tailscale 加密隧道传输，无需公网暴露端口
- 当前版本仅支持读取数据，不执行任何车辆控制指令

## 本地开发

使用 Docker Compose 启动本地 MQTT broker 进行测试：

```bash
docker compose up -d
# 修改 config.yaml 中 tailscale_ip 为 127.0.0.1
uv run python -m teslamate_connector
```
