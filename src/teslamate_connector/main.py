"""
TeslaMate OpenClaw Connector

Maintains an MQTT connection to TeslaMate (via Tailscale) and serves
vehicle data through a local HTTP API consumed by the OpenClaw skill.
"""
import asyncio
import json
import logging
import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse

from .config import load_config
from .mqtt_client import MQTTClient
from .rest_client import TeslaMateApiClient
from .skill_handler import SkillHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_handler: SkillHandler | None = None
_loop: asyncio.AbstractEventLoop | None = None


def _make_http_handler():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            logger.debug("HTTP %s", fmt % args)

        def do_GET(self):
            parsed = urlparse(self.path)

            if parsed.path == "/health":
                self._respond(200, {"status": "ok"})
                return

            if parsed.path == "/query":
                params = parse_qs(parsed.query)
                intent = params.get("intent", ["full_status"])[0]
                msg = {"intent": intent, "params": {}}
                future = asyncio.run_coroutine_threadsafe(
                    _handler.handle(msg), _loop
                )
                try:
                    result = future.result(timeout=15)
                    self._respond(200, {"text": result})
                except Exception as e:
                    self._respond(500, {"error": str(e)})
                return

            self._respond(404, {"error": "not found"})

        def _respond(self, code: int, body: dict):
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def _start_http_server(port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), _make_http_handler())
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Local HTTP API listening on http://127.0.0.1:%d", port)
    return server


async def run(config_path: str = "config.yaml") -> None:
    global _handler, _loop
    _loop = asyncio.get_running_loop()

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
    _handler = SkillHandler(mqtt=mqtt, rest=rest)

    mqtt.connect()
    http_server = _start_http_server(config.openclaw.http_port)

    stop_event = asyncio.Event()

    def _handle_signal():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    logger.info("Connector ready. Query with: curl http://127.0.0.1:%d/query?intent=full_status", config.openclaw.http_port)

    try:
        await stop_event.wait()
    finally:
        http_server.shutdown()
        mqtt.disconnect()
        await rest.aclose()
        logger.info("Connector stopped.")


def main() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    asyncio.run(run(config_path))


if __name__ == "__main__":
    main()
