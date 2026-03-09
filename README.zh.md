# TeslaMate OpenClaw Connector

用 OpenClaw AI 助手查询你的特斯拉：「现在电量多少？」「车停在哪里？」「最近一次充电记录？」

本项目是一个运行在你电脑上的后台程序，它通过 Tailscale（一种加密的私人网络隧道）连接到你部署在云端的 TeslaMate，再把车辆数据提供给 OpenClaw AI 助手使用。

---

## 这个项目能做什么

配置完成后，你可以在 OpenClaw 里用自然语言问关于特斯拉的问题：

| 你说的话 | 返回结果示例 |
|---------|------------|
| 现在电量多少？ | 当前电量：82%，预计续航约 310 km |
| 车在充电吗？ | 充电状态：未接入，充电桩：未接入 |
| 车停在哪里？ | 车辆位置：纬度 31.23，经度 121.47（附地图链接）|
| 车锁好了吗？ | 车锁状态：已锁车 |
| 车里多少度？ | 车内温度：22.3°C，车外温度：18.1°C |
| 最近的行程记录 | 列出最近 5 次行驶记录 |
| 最近充电记录 | 列出最近 5 次充电记录 |

---

## 工作原理

```
你 ──对话──▶ OpenClaw AI
                │
                ▼
        OpenClaw Gateway
        (本机 :18789 端口)
                │ WebSocket
                ▼
   teslamate_openclaw_connector   ← 本项目，运行在你的电脑上
                │
                │ Tailscale 加密隧道（无需公网端口）
                ▼
        TeslaMate 云服务器
        ├── MQTT 实时数据流（电量/位置/温度等）
        └── REST API（行程/充电历史）
```

**关键点：** 你的 TeslaMate 不需要对公网开放任何端口，所有通信都通过 Tailscale 的加密隧道进行。

---

## 开始之前，你需要准备好

请逐一确认以下条件：

**1. 已部署 TeslaMate**

你的 TeslaMate 运行在某台云服务器上（VPS、NAS 等均可），并且已经在正常记录特斯拉数据。

**2. 云服务器已安装 Tailscale**

在你的 TeslaMate 云服务器上安装并登录 Tailscale：
```bash
# 在云服务器上执行
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

登录后，在 [Tailscale 管理页面](https://login.tailscale.com/admin/machines) 找到该服务器的 **Tailscale IP**，格式类似 `100.x.x.x`，记下备用。

**3. 本机已安装 Tailscale**

从 [tailscale.com/download](https://tailscale.com/download) 下载并安装，用同一个账号登录，确保本机和云服务器在同一个 tailnet 里。

验证是否连通：
```bash
ping 100.x.x.x   # 替换为你云服务器的 Tailscale IP
```
能 ping 通就表示 Tailscale 隧道正常。

**4. 已安装 Python 3.12+ 和 uv**

检查 Python 版本：
```bash
python3 --version   # 需要 3.12 或更高
```

安装 uv（Python 包管理器）：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**5. OpenClaw 及其 Gateway 已在运行**

本机的 OpenClaw Gateway 默认监听 `ws://127.0.0.1:18789`。如果你的端口不同，后续在配置文件里修改即可。

---

## 安装步骤

### 第一步：下载项目

```bash
git clone https://github.com/orange90/teslamate_openclaw_connector.git
cd teslamate_openclaw_connector
```

### 第二步：安装依赖

```bash
uv sync
```

这会自动创建虚拟环境并安装所有依赖，通常只需几秒钟。

### 第三步：创建配置文件

```bash
cp config.yaml.example config.yaml
```

然后用任意文本编辑器打开 `config.yaml`：

```yaml
teslamate:
  tailscale_ip: "100.x.x.x"    # ← 改成你云服务器的 Tailscale IP
  mqtt_port: 1883               # MQTT 端口，TeslaMate 默认 1883，一般不用改
  api_port: 8080                # TeslaMateApi 端口，一般不用改
  car_id: 1                     # 车辆编号，只有一辆车就填 1

openclaw:
  gateway_url: "ws://127.0.0.1:18789"  # OpenClaw Gateway 地址，一般不用改
  skill_id: "teslamate"                 # 技能标识符，不用改
```

> `config.yaml` 已被加入 `.gitignore`，不会被提交到 Git，你的 Tailscale IP 是安全的。

### 第四步：验证连通性（可选但推荐）

在启动之前，先验证能否从本机访问 TeslaMate 的数据：

```bash
# 验证 MQTT 数据流（需要安装 mosquitto-clients）
# macOS: brew install mosquitto
mosquitto_sub -h 100.x.x.x -t "teslamate/cars/#" -v
```

如果看到类似 `teslamate/cars/1/battery_level 82` 这样的输出，说明 MQTT 连接正常。按 `Ctrl+C` 退出。

```bash
# 验证 REST API（需要 TeslaMateApi 已部署）
curl http://100.x.x.x:8080/api/v1/cars
```

> 注意：REST API 查询（行程/充电历史）需要 [TeslaMateApi](https://github.com/tobiasehlert/teslamateapi) 服务单独部署。实时数据（电量/位置/温度等）只需要 MQTT，无需 REST API。

### 第五步：启动连接器

```bash
uv run python -m teslamate_connector
```

正常启动后你会看到类似输出：
```
2024-01-01 12:00:00 [INFO] Loaded config: TeslaMate at 100.x.x.x
2024-01-01 12:00:00 [INFO] MQTT client started, connecting to 100.x.x.x:1883
2024-01-01 12:00:00 [INFO] Connecting to OpenClaw Gateway: ws://127.0.0.1:18789
2024-01-01 12:00:00 [INFO] MQTT connected to 100.x.x.x:1883
2024-01-01 12:00:00 [INFO] Subscribed to teslamate/cars/1/#
2024-01-01 12:00:00 [INFO] Registered skill 'teslamate' with OpenClaw Gateway
```

### 第六步：在 OpenClaw 中使用

连接器运行后，在 OpenClaw 对话框里直接用中文提问即可，例如：
- "我的特斯拉现在电量多少？"
- "车停在哪里？"
- "最近一次充电记录"

---

## 常见问题

**Q: 连接器启动后马上断开怎么办？**

检查 OpenClaw Gateway 是否正在运行，以及 `config.yaml` 里的 `gateway_url` 是否正确。

**Q: MQTT 连接失败怎么办？**

1. 确认 Tailscale 隧道正常：`ping 100.x.x.x`
2. 确认云服务器上的 TeslaMate MQTT 在监听：`telnet 100.x.x.x 1883`
3. 某些 TeslaMate 部署中 MQTT 只绑定了 `localhost`，需要修改 TeslaMate 的 `docker-compose.yml` 让 MQTT 监听 `0.0.0.0`（Tailscale 网络内仍然安全）

**Q: 查询结果显示「暂无数据」？**

MQTT 是订阅模式，连接器启动后需要等待 TeslaMate 推送新数据（车辆有活动时才会推送）。如果车辆处于休眠状态，可能需要等待一段时间或先在特斯拉 App 里唤醒车辆。

**Q: 行程和充电记录查询不到？**

这两个功能依赖 TeslaMateApi REST 服务，需要额外部署。参考 [TeslaMateApi 项目](https://github.com/tobiasehlert/teslamateapi) 的部署文档。

**Q: 有多辆特斯拉怎么办？**

修改 `config.yaml` 中的 `car_id`，改为对应车辆的编号（在 TeslaMate 管理界面可以查到）。目前每个连接器实例管理一辆车。

---

## 本地开发 / 不连真实 TeslaMate 测试

如果你想在没有真实 TeslaMate 的情况下开发或测试，可以用 Docker 启动一个本地 MQTT broker 来模拟：

```bash
# 启动本地 Mosquitto MQTT broker
docker compose up -d

# 修改 config.yaml，让连接器连接本地 broker
# tailscale_ip: "127.0.0.1"

# 向本地 broker 发布模拟数据
mosquitto_pub -h 127.0.0.1 -t "teslamate/cars/1/battery_level" -m "75"
mosquitto_pub -h 127.0.0.1 -t "teslamate/cars/1/state" -m "online"
mosquitto_pub -h 127.0.0.1 -t "teslamate/cars/1/locked" -m "true"

# 启动连接器
uv run python -m teslamate_connector
```

---

## 项目结构

```
teslamate_openclaw_connector/
├── config.yaml.example              # 配置文件模板（复制为 config.yaml 后填写）
├── pyproject.toml                   # Python 项目依赖声明
├── skills/
│   └── teslamate.yaml               # OpenClaw Skill 定义（意图列表）
├── src/
│   └── teslamate_connector/
│       ├── main.py                  # 程序入口，管理 WebSocket 连接和重连
│       ├── config.py                # 读取 config.yaml
│       ├── mqtt_client.py           # 订阅 TeslaMate MQTT 实时数据
│       ├── rest_client.py           # 调用 TeslaMateApi REST 接口
│       └── skill_handler.py         # 将 OpenClaw 指令映射为数据查询和中文回答
└── docker-compose.yml               # 本地开发用 MQTT broker
```

---

## 安全说明

- **无需公网端口**：TeslaMate 的 MQTT 和 API 端口不需要对外网开放，所有通信都在 Tailscale 加密隧道内进行
- **只读模式**：本项目当前版本只读取数据，不会向特斯拉发送任何控制指令
- **配置安全**：`config.yaml`（含 Tailscale IP）已加入 `.gitignore`，不会意外提交到 Git 仓库

---

## 故障排查：已知问题与修复记录

以下是实际部署中遇到的问题及解决方法，供参考。

---

### 问题一：`mosquitto_sub` 报 "bad file descriptor" 或 "Connection refused"

**现象：** 在本机运行 `mosquitto_sub -h <tailscale-ip> -t "teslamate/cars/#"` 报错。

**诊断步骤：**
```bash
# 1. 确认 Tailscale 隧道是否正常
ping <tailscale-ip>

# 2. 确认 1883 端口是否可达
nc -zv <tailscale-ip> 1883
```

**原因 A：MQTT 端口未对外暴露**

TeslaMate 的 `docker-compose.yml` 中 mosquitto 端口默认被注释掉：
```yaml
mosquitto:
  # ports:
  #   - 1883:1883    # ← 被注释了
```

修复：在云服务器上编辑 `/opt/teslamate/docker-compose.yml`（或你的实际路径），取消注释：
```yaml
mosquitto:
  ports:
    - 1883:1883
```
然后重启：
```bash
docker compose up -d mosquitto
```

**原因 B：Docker 与 Tailscale 的 iptables 冲突**

Docker 自动添加的 iptables 规则有时不覆盖 Tailscale 网卡（`tailscale0`）进来的流量。

修复（在云服务器执行）：
```bash
iptables -I DOCKER-USER -i tailscale0 -j ACCEPT

# 持久化（重启后生效）
apt install iptables-persistent -y
netfilter-persistent save
```

---

### 问题二：有两个 mosquitto 容器，连上了空的那个

**现象：** `nc -zv` 端口通了，但 `mosquitto_sub` 一直没有数据。

**原因：** 手动启动了一个额外的 mosquitto 容器（比如在 `/root/docker-compose.yml` 里），这个容器暴露了 1883 端口，但 TeslaMate 实际上把数据发往另一个内部的 mosquitto 容器（无外部端口）。

**诊断：**
```bash
docker ps --format 'table {{.Names}}\t{{.Networks}}\t{{.Ports}}' | grep mosquitto
```

如果看到两个 mosquitto 容器，其中 TeslaMate 所在网络的那个没有端口映射，就是这个问题。

**修复：**
1. 停掉多余的 mosquitto 容器
2. 给 TeslaMate 的 mosquitto 容器添加端口映射（见问题一的修复方法）
3. 重启

---

### 问题三：MQTT 连接正常，但始终没有车辆数据

**现象：** `mosquitto_sub` 连接成功（无报错），但等待很久也没有任何消息输出。

**诊断：在云服务器上从容器内部订阅**
```bash
docker compose exec mosquitto mosquitto_sub -t "teslamate/cars/#" -v
```

如果内部也没有数据，说明 TeslaMate 没有在发布，查看 TeslaMate 日志：
```bash
docker compose logs --tail=50 teslamate
```

**原因：TeslaMate 容器内 DNS 解析失败**

日志中若出现：
```
GET https://owner-api.tesla.cn/... -> error: "non-existing domain"
```

说明 Docker 容器无法解析 Tesla API 的域名，通常是因为宿主机的 DNS 服务（systemd-resolved）异常。

**修复：为 Docker 配置外部 DNS 服务器**

在云服务器上：
```bash
# 创建或编辑 Docker daemon 配置
cat > /etc/docker/daemon.json << 'EOF'
{
  "dns": ["114.114.114.114", "8.8.8.8"]
}
EOF

# 重启 Docker 和所有服务
systemctl restart docker
cd /opt/teslamate   # 替换为你的实际路径
docker compose up -d
```

重启后查看日志，应看到：
```
POST https://auth.tesla.cn/oauth2/v3/token -> 200
MQTT connection has been established
car_id=1 Start / :online
```
