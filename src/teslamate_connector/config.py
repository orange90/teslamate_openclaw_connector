import yaml
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TeslaMateConfig:
    tailscale_ip: str
    mqtt_port: int = 1883
    api_port: int = 8080
    car_id: int = 1

    @property
    def mqtt_host(self) -> str:
        return self.tailscale_ip

    @property
    def api_base_url(self) -> str:
        return f"http://{self.tailscale_ip}:{self.api_port}"


@dataclass
class OpenClawConfig:
    gateway_url: str
    skill_id: str = "teslamate"


@dataclass
class Config:
    teslamate: TeslaMateConfig
    openclaw: OpenClawConfig


def load_config(path: str | Path = "config.yaml") -> Config:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            "Copy config.yaml.example to config.yaml and fill in your settings."
        )
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    tm = raw["teslamate"]
    oc = raw["openclaw"]
    return Config(
        teslamate=TeslaMateConfig(
            tailscale_ip=tm["tailscale_ip"],
            mqtt_port=tm.get("mqtt_port", 1883),
            api_port=tm.get("api_port", 8080),
            car_id=tm.get("car_id", 1),
        ),
        openclaw=OpenClawConfig(
            gateway_url=oc["gateway_url"],
            skill_id=oc.get("skill_id", "teslamate"),
        ),
    )
