from dataclasses import dataclass
from typing import Optional

from infra.config import DeviceConfig


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
        return {
            "device_id": self.config.device_id,
            "state": self.state.state,
            "current_sequence": self.state.current_sequence,
            "pressure_bar": self.state.pressure_bar,
            "flow_lpm": self.state.flow_lpm,
            "total_volume_l": self.state.total_volume_l,
            "last_error": self.state.last_error,
        }

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
