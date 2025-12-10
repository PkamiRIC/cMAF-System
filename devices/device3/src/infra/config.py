from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class NetworkConfig:
    api_port: int = 8003


@dataclass
class RelayConfig:
    port: str = "/dev/ttySC2"
    address: int = 0x02
    baudrate: int = 9600
    parity: str = "N"
    timeout: float = 0.3


@dataclass
class RotaryValveConfig:
    port: str = "/dev/ttySC3"
    address: int = 0x01
    baudrate: int = 9600
    parity: str = "N"
    timeout: float = 0.3


@dataclass
class SyringeConfig:
    port: str = "/dev/ttySC2"
    address: int = 0x4C
    baudrate: int = 9600
    steps_per_ml: float = 304457.5314
    velocity_calib: float = 304.45753
    timeout: float = 1.0


@dataclass
class DeviceConfig:
    device_id: str = "device3"
    network: NetworkConfig = field(default_factory=NetworkConfig)
    relay: RelayConfig = field(default_factory=RelayConfig)
    rotary: RotaryValveConfig = field(default_factory=RotaryValveConfig)
    syringe: SyringeConfig = field(default_factory=SyringeConfig)


def _load_yaml(path: str) -> Dict[str, Any]:
    raw = Path(path).read_text()
    data = yaml.safe_load(raw) if raw else {}
    return data or {}


def load_config(path: str) -> DeviceConfig:
    """
    Read YAML config into a typed DeviceConfig with sensible defaults.
    Unknown keys are ignored to keep backward compatibility.
    """
    data = _load_yaml(path)

    return DeviceConfig(
        device_id=data.get("device_id", "device3"),
        network=NetworkConfig(**data.get("network", {})),
        relay=RelayConfig(**data.get("relay", {})),
        rotary=RotaryValveConfig(**data.get("rotary_valve", data.get("rotary", {}))),
        syringe=SyringeConfig(**data.get("syringe", {})),
    )
