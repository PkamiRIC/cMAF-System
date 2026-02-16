from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class NetworkConfig:
    api_port: int = 8002


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
    # Optional guard: block horizontal motion if vertical exceeds this height
    vertical_guard_mm: Optional[float] = None


@dataclass
class PeristalticConfig:
    enable_pin: str = "Q0.0"
    dir_forward_pin: str = "Q0.1"
    dir_reverse_pin: str = "Q0.2"
    speed_pin: str = "Q0.7"
    dir_driver_port: str = "/dev/ttySC3"
    dir_driver_address: int = 76
    dir_driver_baudrate: int = 9600
    dir_driver_parity: str = "N"
    dir_driver_timeout: float = 0.3


@dataclass
class PidValveConfig:
    step_pin: str = "Q0.5"
    dir_pin: str = "Q0.4"
    en_pin: str = "Q0.3"
    hall_pin: str = "I0.12"
    pid_kp: float = 1.6
    pid_ki: float = 0.25
    pid_kd: float = 0.02
    sample_time: float = 0.08
    output_min: float = -1.5
    output_max: float = 1.5
    setpoint_default: float = 1.0


@dataclass
class FlowSensorConfig:
    port: str = "/dev/ttyUSB0"
    medium: str = "water"
    interval_ms: int = 20
    scale_factor: float = 500.0
    stale_restart_limit: int = 20
    stale_seconds: float = 2.0


@dataclass
class Sequence1Config:
    post_volume_wait_s: float = 2.0
    early_complete_ratio: float = 0.925
    early_complete_wait_s: float = 10.0
    stagnant_timeout_s: float = 20.0
    stagnant_epsilon_ml: float = 0.001


@dataclass
class Sequence2Config:
    target_volume_ml: float = 50.0
    early_complete_ratio: float = 0.925
    early_complete_wait_s: float = 10.0
    stagnant_timeout_s: float = 20.0
    stagnant_epsilon_ml: float = 0.001


@dataclass
class TemperatureConfig:
    command_pin: str = "Q0.6"
    ready_pin: str = "I0.11"
    ready_gpio_pin: int = 4
    tec_port: Optional[str] = None
    tec_address: Optional[int] = None
    tec_baudrate: int = 57600
    tec_timeout_s: float = 0.35
    tec_poll_interval_s: float = 0.5
    tec_channel: int = 1
    tec_default_target_c: float = 58.0
    tec_ready_tolerance_c: float = 0.5


@dataclass
class AuthConfig:
    advanced_controls_password: str = "admin123"


@dataclass
class DeviceConfig:
    device_id: str = "device2"
    network: NetworkConfig = field(default_factory=NetworkConfig)
    relay: RelayConfig = field(default_factory=RelayConfig)
    rotary_valve: RotaryValveConfig = field(default_factory=RotaryValveConfig)
    syringe: SyringeConfig = field(default_factory=SyringeConfig)
    vertical_axis: AxisConfig = field(default_factory=AxisConfig)
    horizontal_axis: AxisConfig = field(
        default_factory=lambda: AxisConfig(address=0x4D, min_mm=0.0, max_mm=None)
    )
    peristaltic: PeristalticConfig = field(default_factory=PeristalticConfig)
    pid_valve: PidValveConfig = field(default_factory=PidValveConfig)
    flow_sensor: FlowSensorConfig = field(default_factory=FlowSensorConfig)
    sequence1: Sequence1Config = field(default_factory=Sequence1Config)
    sequence2: Sequence2Config = field(default_factory=Sequence2Config)
    temperature: TemperatureConfig = field(default_factory=TemperatureConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)


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
        device_id=data.get("device_id", "device2"),
        network=NetworkConfig(**data.get("network", {})),
        relay=RelayConfig(**data.get("relay", {})),
        rotary_valve=RotaryValveConfig(**data.get("rotary_valve", {})),
        syringe=SyringeConfig(**data.get("syringe", {})),
        vertical_axis=AxisConfig(**data.get("vertical_axis", {})),
        horizontal_axis=AxisConfig(**data.get("horizontal_axis", {})),
        peristaltic=PeristalticConfig(**data.get("peristaltic", {})),
        pid_valve=PidValveConfig(**data.get("pid_valve", {})),
        flow_sensor=FlowSensorConfig(**data.get("flow_sensor", {})),
        sequence1=Sequence1Config(**data.get("sequence1", {})),
        sequence2=Sequence2Config(**data.get("sequence2", {})),
        temperature=TemperatureConfig(**data.get("temperature", {})),
        auth=AuthConfig(**data.get("auth", {})),
    )
