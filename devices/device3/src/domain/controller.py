import threading
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

from hardware.plc_io import PlcIo
from hardware.relay_board import RelayBoard
from hardware.rotary_valve import RotaryValve
from hardware.syringe_pump import SyringePump
from infra.config import DeviceConfig
from domain.sequences import run_maf_sampling_sequence, run_sequence2


@dataclass
class DeviceState:
    state: str = "IDLE"  # IDLE, RUNNING, ERROR
    current_sequence: Optional[str] = None
    sequence_step: Optional[str] = None
    pressure_bar: float = 0.0
    flow_lpm: float = 0.0
    total_volume_l: float = 0.0
    last_error: Optional[str] = None
    stop_requested: bool = False


class DeviceController:
    def __init__(self, config: DeviceConfig):
        self.config = config
        self.io = PlcIo()
        self.relays = RelayBoard(config.relay)
        self.rotary = RotaryValve(config.rotary)
        self.syringe = SyringePump(config.syringe)
        self.state = DeviceState()
        self._stop_event = threading.Event()
        self._sequence_thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()

    # ---------------------------------------------------
    # STATUS
    # ---------------------------------------------------
    def get_status(self) -> dict:
        with self._state_lock:
            self.state.pressure_bar = self.io.read_pressure()
            self.state.flow_lpm = self.io.read_flow()
            self.state.total_volume_l = self.io.read_volume()
            return {"device_id": self.config.device_id, **asdict(self.state)}

    # ---------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------
    def start_sequence(self, sequence_name: str) -> None:
        if self._sequence_thread and self._sequence_thread.is_alive():
            raise RuntimeError("A sequence is already running")

        with self._state_lock:
            self.state.state = "RUNNING"
            self.state.current_sequence = sequence_name
            self.state.last_error = None
            self.state.stop_requested = False

        self._stop_event.clear()
        self._sequence_thread = threading.Thread(
            target=self._run_sequence, args=(sequence_name,), daemon=True
        )
        self._sequence_thread.start()

    def stop_sequence(self) -> None:
        self._stop_event.set()
        with self._state_lock:
            self.state.stop_requested = True

    def emergency_stop(self) -> None:
        self.stop_sequence()
        self.io.emergency_stop()
        with self._state_lock:
            self.state.state = "ERROR"
            self.state.current_sequence = None
            self.state.last_error = "Emergency stop activated"

    def set_relay(self, channel: int, enabled: bool) -> bool:
        return self.relays.on(channel) if enabled else self.relays.off(channel)

    def set_rotary_port(self, port: int) -> bool:
        return self.rotary.set_port(port)

    def move_syringe(self, volume_ml: float, flow_ml_min: float) -> None:
        self.syringe.goto_absolute(volume_ml, flow_ml_min)

    # ---------------------------------------------------
    # Internals
    # ---------------------------------------------------
    def _run_sequence(self, sequence_name: str) -> None:
        try:
            if sequence_name.lower() in {"sequence1", "maf_sampling", "maf"}:
                self._execute_sequence(
                    lambda: run_maf_sampling_sequence(
                        stop_flag=self._stop_event.is_set,
                        log=self._log,
                        relays=self.relays,
                        syringe=self.syringe,
                        move_horizontal_to_filtering=self._not_wired("move_horizontal_to_filtering"),
                        move_vertical_close_plate=self._not_wired("move_vertical_close_plate"),
                        select_rotary_port=self.rotary.set_port,
                        before_step=self._before_step,
                        init=self._not_wired("init_homing"),
                    )
                )
            elif sequence_name.lower() in {"sequence2", "seq2"}:
                self._execute_sequence(
                    lambda: run_sequence2(
                        stop_flag=self._stop_event.is_set,
                        log=self._log,
                        relays=self.relays,
                        syringe=self.syringe,
                        move_horizontal_to_filtering=self._not_wired("move_horizontal_to_filtering"),
                        move_horizontal_home=self._not_wired("move_horizontal_home"),
                        move_vertical_close_plate=self._not_wired("move_vertical_close_plate"),
                        move_vertical_open_plate=self._not_wired("move_vertical_open_plate"),
                        select_rotary_port=self.rotary.set_port,
                        before_step=self._before_step,
                    )
                )
            else:
                raise ValueError(f"Unknown sequence '{sequence_name}'")
        except Exception as exc:
            with self._state_lock:
                self.state.state = "ERROR"
                self.state.last_error = str(exc)
        else:
            with self._state_lock:
                self.state.state = "IDLE" if not self._stop_event.is_set() else "ERROR"
                self.state.last_error = "Sequence stopped" if self._stop_event.is_set() else None
        finally:
            with self._state_lock:
                self.state.current_sequence = None
                self.state.sequence_step = None
                self.state.stop_requested = False
            self._stop_event.clear()

    def _execute_sequence(self, func: Callable[[], None]) -> None:
        func()

    def _before_step(self, step_label: str) -> None:
        with self._state_lock:
            self.state.sequence_step = step_label

    def _log(self, message: str) -> None:
        # Placeholder logging hook for future persistence/log streaming
        print(message)

    def _not_wired(self, label: str) -> Callable[[], None]:
        def _fn():
            raise RuntimeError(f"Action '{label}' not wired to backend yet")

        return _fn
