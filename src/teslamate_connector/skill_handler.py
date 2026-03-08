"""
Maps OpenClaw intent commands to TeslaMate data queries.

OpenClaw sends JSON messages of the form:
  {"type": "query", "intent": "<intent_name>", "params": {...}}

This module returns a plain-text answer string for each intent.
"""
import logging
from .mqtt_client import MQTTClient
from .rest_client import TeslaMateApiClient

logger = logging.getLogger(__name__)

# Friendly state labels
CHARGING_STATE_LABELS = {
    "Charging": "充电中",
    "Complete": "充电完成",
    "Disconnected": "未接入",
    "Stopped": "已停止",
    "NoPower": "无电源",
}

LOCKED_LABELS = {"true": "已锁车", "false": "未锁车"}

STATE_LABELS = {
    "online": "在线",
    "offline": "离线",
    "asleep": "休眠",
    "charging": "充电中",
    "driving": "行驶中",
    "updating": "更新中",
}


class SkillHandler:
    def __init__(self, mqtt: MQTTClient, rest: TeslaMateApiClient):
        self.mqtt = mqtt
        self.rest = rest

    async def handle(self, message: dict) -> str:
        intent = message.get("intent", "")
        params = message.get("params", {})
        logger.info("Handling intent: %s", intent)

        handlers = {
            "battery_level": self._battery_level,
            "charging_state": self._charging_state,
            "location": self._location,
            "lock_status": self._lock_status,
            "temperature": self._temperature,
            "car_state": self._car_state,
            "recent_charges": self._recent_charges,
            "recent_drives": self._recent_drives,
            "stats": self._stats,
            "full_status": self._full_status,
        }

        handler = handlers.get(intent)
        if handler is None:
            return f"未知指令：{intent}。支持的指令：{', '.join(handlers.keys())}"

        try:
            return await handler(params)
        except Exception as e:
            logger.exception("Error handling intent %s", intent)
            return f"查询失败：{e}"

    async def _battery_level(self, params: dict) -> str:
        level = self.mqtt.get("battery_level")
        est_range = self.mqtt.get("est_battery_range")
        if level is None:
            return "暂无电量数据，MQTT 尚未收到更新。"
        result = f"当前电量：{level}%"
        if est_range:
            result += f"，预计续航约 {float(est_range):.0f} km"
        return result

    async def _charging_state(self, params: dict) -> str:
        state = self.mqtt.get("charging_state")
        plugged = self.mqtt.get("plugged_in")
        if state is None:
            return "暂无充电状态数据。"
        label = CHARGING_STATE_LABELS.get(state, state)
        result = f"充电状态：{label}"
        if plugged is not None:
            result += f"，充电桩：{'已接入' if plugged == 'true' else '未接入'}"
        return result

    async def _location(self, params: dict) -> str:
        lat = self.mqtt.get("latitude")
        lon = self.mqtt.get("longitude")
        if lat is None or lon is None:
            return "暂无位置数据。"
        return f"车辆位置：纬度 {lat}，经度 {lon}\n地图：https://maps.google.com/?q={lat},{lon}"

    async def _lock_status(self, params: dict) -> str:
        locked = self.mqtt.get("locked")
        if locked is None:
            return "暂无车锁状态数据。"
        return f"车锁状态：{LOCKED_LABELS.get(locked, locked)}"

    async def _temperature(self, params: dict) -> str:
        inside = self.mqtt.get("inside_temp")
        outside = self.mqtt.get("outside_temp")
        parts = []
        if inside:
            parts.append(f"车内温度：{inside}°C")
        if outside:
            parts.append(f"车外温度：{outside}°C")
        return "，".join(parts) if parts else "暂无温度数据。"

    async def _car_state(self, params: dict) -> str:
        state = self.mqtt.get("state")
        if state is None:
            return "暂无车辆状态数据。"
        return f"车辆状态：{STATE_LABELS.get(state, state)}"

    async def _full_status(self, params: dict) -> str:
        state = await self._car_state(params)
        battery = await self._battery_level(params)
        charging = await self._charging_state(params)
        lock = await self._lock_status(params)
        temp = await self._temperature(params)
        return "\n".join([state, battery, charging, lock, temp])

    async def _recent_charges(self, params: dict) -> str:
        data = await self.rest.get_charges(page=1)
        charges = data.get("data", [])
        if not charges:
            return "暂无充电记录。"
        lines = ["最近充电记录："]
        for c in charges[:5]:
            start = c.get("start_date", "")[:16]
            added = c.get("charge_energy_added", "")
            cost = c.get("cost", "")
            line = f"  {start}  增加电量：{added} kWh"
            if cost:
                line += f"  费用：{cost}"
            lines.append(line)
        return "\n".join(lines)

    async def _recent_drives(self, params: dict) -> str:
        data = await self.rest.get_drives(page=1)
        drives = data.get("data", [])
        if not drives:
            return "暂无行驶记录。"
        lines = ["最近行驶记录："]
        for d in drives[:5]:
            start = d.get("start_date", "")[:16]
            distance = d.get("distance", "")
            duration = d.get("duration_min", "")
            line = f"  {start}  距离：{distance} km  时长：{duration} 分钟"
            lines.append(line)
        return "\n".join(lines)

    async def _stats(self, params: dict) -> str:
        data = await self.rest.get_stats()
        stats = data.get("data", data)
        total_km = stats.get("total_driven_km", "N/A")
        total_charges = stats.get("total_charges", "N/A")
        total_energy = stats.get("total_energy_used", "N/A")
        return (
            f"车辆统计：\n"
            f"  累计行驶：{total_km} km\n"
            f"  累计充电次数：{total_charges}\n"
            f"  累计用电：{total_energy} kWh"
        )
