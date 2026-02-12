import threading
from typing import Optional
from pathlib import Path
import sys

from infra.config import FlowSensorConfig

_OLD_CODES = Path(__file__).resolve().parents[2] / "Old_Codes"
if str(_OLD_CODES) not in sys.path:
    sys.path.append(str(_OLD_CODES))

try:
    from slf3s_usb_sensor import SLF3SUSBFlowSensor  # type: ignore
except Exception:
    SLF3SUSBFlowSensor = None


class FlowSensor:
    def __init__(self, config: FlowSensorConfig) -> None:
        self.config = config
        self._sensor = None
        self._running = False
        self._lock = threading.Lock()
        self._last_error: Optional[str] = None
        self._last_data = {
            "flow_ml_min": 0.0,
            "total_ml": 0.0,
            "total_l": 0.0,
        }

    def _ensure_sensor(self):
        if SLF3SUSBFlowSensor is None:
            raise RuntimeError(
                "SLF3S driver is unavailable. Ensure 'device/Old_Codes/slf3s_usb_sensor.py' and pyserial are installed."
            )
        if self._sensor is not None:
            return self._sensor
        self._sensor = SLF3SUSBFlowSensor(
            port=self.config.port,
            medium=self.config.medium,
            interval_ms=self.config.interval_ms,
            scale_factor=self.config.scale_factor,
            stale_restart_limit=self.config.stale_restart_limit,
            stale_seconds=self.config.stale_seconds,
            auto_start=False,
        )
        return self._sensor

    def start(self) -> None:
        with self._lock:
            sensor = self._ensure_sensor()
            sensor.start(interval_ms=self.config.interval_ms)
            self._running = True
            self._last_error = None

    def stop(self) -> None:
        with self._lock:
            if self._sensor is None:
                self._running = False
                return
            try:
                self._sensor.stop()
            finally:
                self._running = False

    def reset_totals(self) -> None:
        with self._lock:
            sensor = self._ensure_sensor()
            sensor.reset_totals()
            self._last_data["total_ml"] = 0.0
            self._last_data["total_l"] = 0.0
            self._last_error = None

    def read(self) -> dict:
        with self._lock:
            if self._sensor is None:
                return dict(self._last_data)
            try:
                data = self._sensor.read()
                self._last_data = {
                    "flow_ml_min": float(data.get("flow_ml_min", 0.0)),
                    "total_ml": float(data.get("total_ml", 0.0)),
                    "total_l": float(data.get("total_l", 0.0)),
                }
                self._last_error = None
                return dict(self._last_data)
            except Exception as exc:
                # Keep last good values to avoid UI flapping on transient transport errors.
                self._last_error = str(exc)
                return dict(self._last_data)

    def is_running(self) -> bool:
        with self._lock:
            return bool(self._running)

    def get_last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    def close(self) -> None:
        with self._lock:
            if self._sensor is None:
                self._running = False
                return
            try:
                self._sensor.close()
            except Exception:
                pass
            self._sensor = None
            self._running = False
