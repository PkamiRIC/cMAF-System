"""
Axis driver reusing the syringe pump Modbus protocol.
Addresses and calibrations mirror the legacy WARP3_v6 GUI.
"""

import threading
import time
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
        pump.home(stop_flag=stop_flag)
        self._wait_until_idle(timeout=timeout, stop_flag=stop_flag)

    def move_mm(self, target_mm: float, rpm: float, stop_flag: Optional[callable] = None) -> None:
        pump = self._require_pump()
        # Convert mm -> mL using calibration
        steps_per_ml = self.config.steps_per_ml
        steps_per_mm = self.config.steps_per_mm
        if steps_per_mm <= 0:
            raise ValueError("steps_per_mm must be > 0")
        volume_ml = (target_mm * steps_per_mm) / steps_per_ml
        flow_ml_min = max(rpm, 0.1) * 5  # AXIS_SPEED_STEPS_PER_RPM=5 in legacy
        target_steps = int(round(target_mm * steps_per_mm))
        for attempt in range(1, 3):
            if stop_flag and stop_flag():
                raise RuntimeError("Operation stopped")
            pump.goto_absolute(volume_ml, flow_ml_min)
            try:
                self._wait_until_at_target(target_steps, timeout=30.0, stop_flag=stop_flag)
                return
            except Exception:
                if attempt >= 2:
                    raise
                time.sleep(0.2)

    def read_position_mm(self) -> Optional[float]:
        pump = self._pump
        if pump is None:
            return None
        status = pump.read_status()
        if not status:
            return None
        try:
            steps_per_mm = self.config.steps_per_mm
            if steps_per_mm <= 0:
                return None
            return float(status["actual_position"]) / float(steps_per_mm)
        except Exception:
            return None

    def _require_pump(self) -> SyringePump:
        pump = self._pump
        if pump is None:
            raise RuntimeError(f"{self.name} axis unavailable (not connected)")
        return pump

    def mark_unready(self) -> None:
        """Drop the cached driver so the next call forces a reconnect."""
        with self._lock:
            self._pump = None

    def _log(self, message: str) -> None:
        # Keep logging consistent with other hardware classes
        print(message)

    def stop_motion(self) -> bool:
        """
        Best-effort stop for an axis:
        try a quick-stop frame first, then re-command current position with zero flow.
        """
        pump = self._pump
        if pump is None:
            # Best-effort: try to reconnect so E-STOP can still act
            try:
                self.connect()
                pump = self._pump
            except Exception as exc:
                self._log(f"[AxisStop] {self.name} addr={self.config.address} error=no_pump:{exc}")
                return False
            if pump is None:
                self._log(f"[AxisStop] {self.name} addr={self.config.address} error=no_pump")
                return False
        try:
            ok = pump.quick_stop()
            self._log(f"[AxisStop] {self.name} addr={self.config.address} quick_stop={ok}")
            if ok:
                return True
            soft_ok = bool(pump.stop_motion())
            self._log(f"[AxisStop] {self.name} addr={self.config.address} soft_stop={soft_ok}")
            return soft_ok
        except Exception as exc:
            self._log(f"[AxisStop] {self.name} addr={self.config.address} error={exc}")
            return False

    def _wait_until_idle(self, timeout: float, stop_flag: Optional[callable] = None) -> None:
        """
        Wait until the drive is truly idle.
        The legacy busy bit can clear early; standstill/velocity are more reliable.
        """
        pump = self._require_pump()
        start = time.time()
        vel_thresh_steps = 5

        while True:
            if stop_flag and stop_flag():
                raise RuntimeError("Operation stopped")

            st = pump.read_status(max_tries=2)
            if st is not None:
                busy = int(st.get("busy", 0))
                standstill = int(st.get("standstill", 1))
                actual_velocity = int(st.get("actual_velocity", 0))
                if busy == 0 and standstill == 1 and abs(actual_velocity) <= vel_thresh_steps:
                    return

            if (time.time() - start) >= timeout:
                raise RuntimeError(f"{self.name} motion timed out")

            time.sleep(0.2)

    def _wait_until_at_target(
        self, target_steps: int, timeout: float, stop_flag: Optional[callable] = None
    ) -> None:
        """
        Wait until at target and standstill.
        Prevents returning early (which can let subsequent moves violate interlocks).
        """
        pump = self._require_pump()
        start = time.time()
        vel_thresh_steps = 5
        tol_steps = max(10, int(round(self.config.steps_per_mm * 0.05)))  # ~0.05mm or >=10 steps

        while True:
            if stop_flag and stop_flag():
                raise RuntimeError("Operation stopped")

            st = pump.read_status(max_tries=2)
            if st is not None:
                busy = int(st.get("busy", 0))
                standstill = int(st.get("standstill", 1))
                actual_velocity = int(st.get("actual_velocity", 0))
                actual_position = st.get("actual_position", None)
                try:
                    actual_position = int(actual_position)
                except Exception:
                    actual_position = None

                if (
                    actual_position is not None
                    and abs(actual_position - target_steps) <= tol_steps
                    and busy == 0
                    and standstill == 1
                    and abs(actual_velocity) <= vel_thresh_steps
                ):
                    return

            if (time.time() - start) >= timeout:
                raise RuntimeError(f"{self.name} move to target timed out")

            time.sleep(0.2)
