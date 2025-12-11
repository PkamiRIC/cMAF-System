"""
Axis driver reusing the syringe pump Modbus protocol.
Addresses and calibrations mirror the legacy WARP3_v6 GUI.
"""

import threading
from typing import Optional

from infra.config import AxisConfig
from hardware.syringe_pump import SyringePump


class AxisDriver:
    def __init__(self, config: AxisConfig, name: str):
        self.config = config
        self.name = name
        self._pump: Optional[SyringePump] = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._pump is not None

    def connect(self) -> None:
        pump = SyringePump(self.config)
        with self._lock:
            self._pump = pump

    def home(self, timeout: float = 5.0, stop_flag: Optional[callable] = None) -> None:
        pump = self._require_pump()
        pump.home()
        ok = pump.wait_until_idle(timeout=timeout, stop_flag=stop_flag)
        if not ok:
            raise RuntimeError(f"{self.name} homing timed out")

    def move_mm(self, target_mm: float, rpm: float, stop_flag: Optional[callable] = None) -> None:
        pump = self._require_pump()
        # Convert mm -> mL using calibration
        steps_per_ml = self.config.steps_per_ml
        steps_per_mm = self.config.steps_per_mm
        if steps_per_mm <= 0:
            raise ValueError("steps_per_mm must be > 0")
        volume_ml = (target_mm * steps_per_mm) / steps_per_ml
        flow_ml_min = max(rpm, 0.1) * 5  # AXIS_SPEED_STEPS_PER_RPM=5 in legacy
        pump.goto_absolute(volume_ml, flow_ml_min)
        pump.wait_until_idle(timeout=30.0, stop_flag=stop_flag)

    def _require_pump(self) -> SyringePump:
        pump = self._pump
        if pump is None:
            raise RuntimeError(f"{self.name} axis unavailable (not connected)")
        return pump
