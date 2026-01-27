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

        if SLF3SUSBFlowSensor is None:
            return
        try:
            self._sensor = SLF3SUSBFlowSensor(
                port=config.port,
                medium=config.medium,
                interval_ms=config.interval_ms,
                scale_factor=config.scale_factor,
                stale_restart_limit=config.stale_restart_limit,
                auto_start=False,
            )
        except Exception:
            self._sensor = None

    def start(self) -> None:
        if self._sensor is None:
            return
        try:
            self._sensor.start()
            self._running = True
        except Exception:
            self._running = False

    def stop(self) -> None:
        if self._sensor is None:
            return
        try:
            self._sensor.stop()
        finally:
            self._running = False

    def reset_totals(self) -> None:
        if self._sensor is None:
            return
        try:
            self._sensor.reset_totals()
        except Exception:
            pass

    def read(self) -> dict:
        if self._sensor is None:
            return {
                "flow_ml_min": 0.0,
                "total_ml": 0.0,
                "total_l": 0.0,
            }
        try:
            data = self._sensor.read()
            return {
                "flow_ml_min": float(data.get("flow_ml_min", 0.0)),
                "total_ml": float(data.get("total_ml", 0.0)),
                "total_l": float(data.get("total_l", 0.0)),
            }
        except Exception:
            return {
                "flow_ml_min": 0.0,
                "total_ml": 0.0,
                "total_l": 0.0,
            }

    def is_running(self) -> bool:
        return bool(self._running)
