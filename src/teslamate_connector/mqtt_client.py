import asyncio
import logging
from typing import Callable
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# Topics we subscribe to for each car
TOPICS = [
    "battery_level",
    "charging_state",
    "latitude",
    "longitude",
    "locked",
    "inside_temp",
    "outside_temp",
    "plugged_in",
    "state",
    "speed",
    "odometer",
    "est_battery_range",
    "ideal_battery_range",
]


class MQTTClient:
    def __init__(self, host: str, port: int, car_id: int):
        self.host = host
        self.port = port
        self.car_id = car_id
        self._state: dict[str, str] = {}
        self._on_update: Callable[[str, str], None] | None = None
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._connected = False

    def set_update_callback(self, callback: Callable[[str, str], None]) -> None:
        self._on_update = callback

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self._connected = True
            logger.info("MQTT connected to %s:%s", self.host, self.port)
            topic = f"teslamate/cars/{self.car_id}/#"
            client.subscribe(topic)
            logger.info("Subscribed to %s", topic)
        else:
            logger.error("MQTT connection failed: %s", reason_code)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8", errors="replace")
        # Extract the field name from the topic
        # e.g. "teslamate/cars/1/battery_level" -> "battery_level"
        parts = topic.split("/")
        if len(parts) >= 4:
            field = parts[-1]
            self._state[field] = payload
            logger.debug("MQTT update: %s = %s", field, payload)
            if self._on_update:
                self._on_update(field, payload)

    def get(self, field: str) -> str | None:
        return self._state.get(field)

    def get_all(self) -> dict[str, str]:
        return dict(self._state)

    def connect(self) -> None:
        self._client.connect_async(self.host, self.port, keepalive=60)
        self._client.loop_start()
        logger.info("MQTT client started, connecting to %s:%s", self.host, self.port)

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("MQTT client disconnected")
