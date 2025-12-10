from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel


class NetworkConfig(BaseModel):
    api_port: int = 8003


class DeviceConfig(BaseModel):
    device_id: str = "device3"
    network: NetworkConfig = NetworkConfig()


def load_config(path: str | None) -> DeviceConfig:
    """
    Load device configuration from a YAML file.

    If `path` is None or file is missing/invalid, use defaults.
    """
    if not path:
        return DeviceConfig()

    cfg_path = Path(path)
    if not cfg_path.exists():
        # Fallback to defaults if file is missing
        return DeviceConfig()

    with cfg_path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    device_id = raw.get("device_id", "device3")
    net_raw = raw.get("network", {}) or {}
    network = NetworkConfig(api_port=net_raw.get("api_port", 8003))

    return DeviceConfig(device_id=device_id, network=network)
