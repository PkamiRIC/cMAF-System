from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

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
class AxisConfig:
    port: str = "/dev/ttySC3"
    address: int = 0x4E
    baudrate: int = 9600
    steps_per_ml: float = 2000.0
    velocity_calib: float = 1000.0
    steps_per_mm: float = 2000.0
    min_mm: Optional[float] = 0.0
    max_mm: Optional[float] = 33.0
    timeout: float = 1.0


@dataclass
class DeviceConfig:
    device_id: str = "device3"
    network: NetworkConfig = field(default_factory=NetworkConfig)
    relay: RelayConfig = field(default_factory=RelayConfig)
    rotary: RotaryValveConfig = field(default_factory=RotaryValveConfig)
    syringe: SyringeConfig = field(default_factory=SyringeConfig)
    vertical_axis: AxisConfig = field(default_factory=AxisConfig)
    horizontal_axis: AxisConfig = field(
        default_factory=lambda: AxisConfig(address=0x4D, min_mm=0.0, max_mm=None)
    )


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
        vertical_axis=AxisConfig(**data.get("vertical_axis", {})),
        horizontal_axis=AxisConfig(**data.get("horizontal_axis", {})),
    )
