import threading
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

from hardware.plc_io import PlcIo
from hardware.relay_board import RelayBoard
from hardware.rotary_valve import RotaryValve
from hardware.syringe_pump import SyringePump
from hardware.axis_driver import AxisDriver
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
        self.vertical_axis = AxisDriver(config.vertical_axis, "Vertical Axis")
        self.horizontal_axis = AxisDriver(config.horizontal_axis, "Horizontal Axis")
        self.state = DeviceState()
        self._stop_event = threading.Event()
        self._sequence_thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()

        # Best-effort initial connections for axes
        try:
            self.vertical_axis.connect()
            self.horizontal_axis.connect()
        except Exception:
            # Leave drivers unready; homing will fail with a clear message
            pass

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

    def home_all(self) -> None:
        """
        Homing routine mirroring the old GUI's Initialize button:
        runs in a background thread so it can be stopped.
        """
        if self._sequence_thread and self._sequence_thread.is_alive():
            raise RuntimeError("Another operation is already running")

        with self._state_lock:
            self.state.state = "RUNNING"
            self.state.current_sequence = "homing"
            self.state.last_error = None
            self.state.stop_requested = False
            self.state.sequence_step = "Preparing outputs"

        self._stop_event.clear()
        self._sequence_thread = threading.Thread(target=self._run_homing, daemon=True)
        self._sequence_thread.start()

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

    def _prepare_outputs_for_homing(self) -> None:
        """Best-effort: switch off relays before moving axes."""
        try:
            for ch in range(1, 9):
                self.relays.off(ch)
        except Exception:
            # Keep going even if one relay write fails
            pass

    def _check_stop(self) -> None:
        if self._stop_event.is_set():
            raise RuntimeError("Operation stopped")

    def _run_homing(self) -> None:
        try:
            self._check_stop()
            self._prepare_outputs_for_homing()

            self._before_step("Homing vertical axis")
            self._check_stop()
            self._home_vertical_axis()

            self._before_step("Homing horizontal axis")
            self._check_stop()
            self._home_horizontal_axis()

            self._before_step("Homing syringe pump")
            self._check_stop()
            self.syringe.home()

            with self._state_lock:
                self.state.state = "IDLE"
                self.state.last_error = None
        except Exception as exc:
            with self._state_lock:
                self.state.state = "ERROR"
                self.state.last_error = str(exc)
        finally:
            with self._state_lock:
                self.state.current_sequence = None
                self.state.sequence_step = None
                self.state.stop_requested = False
            self._stop_event.clear()

    def _home_vertical_axis(self) -> None:
        """
        Placeholder to be wired to the real vertical axis driver.
        Replace this implementation with your motion controller call,
        e.g., vertical_driver.home_blocking().
        """
        if not self.vertical_axis.ready:
            try:
                self.vertical_axis.connect()
            except Exception as exc:
                raise RuntimeError(f"Vertical axis unavailable: {exc}")
        self.vertical_axis.home(stop_flag=self._stop_event.is_set)

    def _home_horizontal_axis(self) -> None:
        """
        Placeholder to be wired to the real horizontal axis driver.
        Replace this implementation with your motion controller call,
        e.g., horizontal_driver.home_blocking().
        """
        if not self.horizontal_axis.ready:
            try:
                self.horizontal_axis.connect()
            except Exception as exc:
                raise RuntimeError(f"Horizontal axis unavailable: {exc}")
        self.horizontal_axis.home(stop_flag=self._stop_event.is_set)
