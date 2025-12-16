from dataclasses import dataclass
from typing import Optional
from infra.config import DeviceConfig
import time

@dataclass
class DeviceState:
    state: str = "IDLE"  # IDLE, RUNNING, ERROR
    current_sequence: Optional[str] = None
    pressure_bar: float = 0.0
    flow_lpm: float = 0.0
    total_volume_l: float = 0.0
    last_error: Optional[str] = None


class DeviceController:
    """
    High-level device controller.

    Later this will call into hardware/plc_io.py to control
    valves, pump, etc. For now it is a minimal stub so that
    the FastAPI backend can run and the /status endpoint works.
    """

    def __init__(self, config: DeviceConfig) -> None:
        self.config = config
        self.state = DeviceState()

    # --------- Status ---------
    def get_status(self) -> dict:
        syringe_status = None
        try:
            syringe_status = self.syringe.read_status()
        except Exception:
            syringe_status = None

        with self._state_lock:
            self.state.pressure_bar = self.io.read_pressure()
            self.state.flow_lpm = self.io.read_flow()
            self.state.total_volume_l = self.io.read_volume()

            if syringe_status:
                try:
                    self.state.syringe_busy = bool(syringe_status.get("busy"))
                    vol = syringe_status.get("volume_ml")
                    if vol is not None:
                        self.state.syringe_volume_ml = float(vol)
                except Exception:
                    pass

            self.state.relay_states = dict(self.relay_states)
            self.state.rotary_port = self.rotary_port
            self.state.logs = list(self._log_buffer)
            snapshot = {"device_id": self.config.device_id, **asdict(self.state)}
        return snapshot

    # --------- Commands ---------
    def start_sequence(self, sequence_name: str) -> None:
        """
        Start a named sequence.

        For now, this just updates state; later we will
        implement real sequences mapped to your pump/valve logic.
        """
        self.state.state = "RUNNING"
        self.state.current_sequence = sequence_name
        self.state.last_error = None

    def emergency_stop(self) -> None:
        """
        Emergency stop: later we will add real IO calls here.
        """
        self.state.state = "ERROR"
        self.state.current_sequence = None
        self.state.last_error = "Emergency stop activated"

    def move_syringe(self, volume_ml: float, flow_ml_min: float) -> None:
        self._ensure_manual_allowed()
        self._log(f"[Syringe] move to {volume_ml} mL @ {flow_ml_min} mL/min")
        target_steps = self.syringe._steps_from_volume(volume_ml)
        tolerance_steps = 10

        with self._state_lock:
            self.state.syringe_busy = True
            self.state.syringe_target_ml = volume_ml
        self._broadcast_status()

        try:
            self.syringe.goto_absolute(volume_ml, flow_ml_min)
            deadline = time.time() + 120
            consecutive_idle = 0
            while time.time() < deadline:
                status = self.syringe.read_status()
                if status:
                    # update live volume for the widget
                    try:
                        with self._state_lock:
                            self.state.syringe_volume_ml = float(status.get("volume_ml", volume_ml))
                    except Exception:
                        pass
                    busy = bool(status.get("busy"))
                    pos = int(status.get("actual_position", 0))
                    at_target = abs(pos - target_steps) <= tolerance_steps
                    if not busy and at_target:
                        consecutive_idle += 1
                        if consecutive_idle >= 2:
                            break
                    else:
                        consecutive_idle = 0
                time.sleep(0.2)
            else:
                raise RuntimeError("Syringe move timed out")
        finally:
            with self._state_lock:
                self.state.syringe_busy = False
            self._broadcast_status()