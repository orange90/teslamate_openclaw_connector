"""
TeslaMate OpenClaw Connector

Connects to TeslaMate (via Tailscale) and exposes vehicle data
to OpenClaw AI assistant through a WebSocket skill interface.
"""
import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

import websockets

from .config import load_config
from .mqtt_client import MQTTClient
from .rest_client import TeslaMateApiClient
from .skill_handler import SkillHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run(config_path: str = "config.yaml") -> None:
    config = load_config(config_path)
    logger.info("Loaded config: TeslaMate at %s", config.teslamate.tailscale_ip)

    mqtt = MQTTClient(
        host=config.teslamate.mqtt_host,
        port=config.teslamate.mqtt_port,
        car_id=config.teslamate.car_id,
    )
    rest = TeslaMateApiClient(
        base_url=config.teslamate.api_base_url,
        car_id=config.teslamate.car_id,
    )
    handler = SkillHandler(mqtt=mqtt, rest=rest)

    mqtt.connect()

    stop_event = asyncio.Event()

    def _handle_signal():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    try:
        await _gateway_loop(config, handler, stop_event)
    finally:
        mqtt.disconnect()
        await rest.aclose()
        logger.info("Connector stopped.")


async def _gateway_loop(config, handler: SkillHandler, stop_event: asyncio.Event) -> None:
    gateway_url = config.openclaw.gateway_url
    skill_id = config.openclaw.skill_id
    reconnect_delay = 5

    while not stop_event.is_set():
        try:
            logger.info("Connecting to OpenClaw Gateway: %s", gateway_url)
            async with websockets.connect(gateway_url) as ws:
                # Register this skill with the gateway
                await ws.send(json.dumps({
                    "type": "register",
                    "skill_id": skill_id,
                    "name": "TeslaMate",
                    "description": "查询特斯拉车辆实时数据（电量、位置、充电状态等）",
                }))
                logger.info("Registered skill '%s' with OpenClaw Gateway", skill_id)

                async def _recv_loop():
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            logger.warning("Received non-JSON message: %s", raw)
                            continue

                        msg_type = msg.get("type")
                        if msg_type == "query":
                            reply = await handler.handle(msg)
                            await ws.send(json.dumps({
                                "type": "response",
                                "request_id": msg.get("request_id"),
                                "text": reply,
                            }))
                        elif msg_type == "ping":
                            await ws.send(json.dumps({"type": "pong"}))
                        else:
                            logger.debug("Unhandled message type: %s", msg_type)

                recv_task = asyncio.create_task(_recv_loop())
                stop_task = asyncio.create_task(stop_event.wait())
                done, pending = await asyncio.wait(
                    [recv_task, stop_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
                if stop_event.is_set():
                    break

        except (websockets.ConnectionClosed, OSError) as e:
            if stop_event.is_set():
                break
            logger.warning("Gateway connection lost (%s), retrying in %ds…", e, reconnect_delay)
            await asyncio.sleep(reconnect_delay)


def main() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    asyncio.run(run(config_path))


if __name__ == "__main__":
    main()
