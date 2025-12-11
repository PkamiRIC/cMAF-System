import threading
import asyncio
import json
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

from hardware.plc_io import PlcIo
from hardware.relay_board import RelayBoard
from hardware.rotary_valve import RotaryValve
from hardware.syringe_pump import SyringePump
from hardware.axis_driver import AxisDriver
from infra.config import DeviceConfig
from domain.sequence1 import run_maf_sampling_sequence
from domain.sequence2 import run_sequence2


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
    relay_states: dict = field(default_factory=dict)
    rotary_port: Optional[int] = None
    logs: list = field(default_factory=list)


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
        self._log_lock = threading.Lock()
        self._log_buffer: list[str] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._sse_subscribers: list[asyncio.Queue] = []

        # Relay/rotary caches for UI feedback
        self.relay_states = {ch: False for ch in range(1, 9)}
        self.rotary_port: Optional[int] = None

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
            # update cached UI fields
            self.state.relay_states = dict(self.relay_states)
            self.state.rotary_port = self.rotary_port
            self.state.logs = list(self._log_buffer)
            snapshot = {"device_id": self.config.device_id, **asdict(self.state)}
        return snapshot

    def attach_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

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
            self.state.sequence_step = None
        self._broadcast_status()

        self._stop_event.clear()
        self._sequence_thread = threading.Thread(
            target=self._run_sequence, args=(sequence_name,), daemon=True
        )
        self._sequence_thread.start()

    def stop_sequence(self) -> None:
        self._stop_event.set()
        with self._state_lock:
            self.state.stop_requested = True
            self.state.state = "ERROR"
            self.state.last_error = "Operation stopped"
            self.state.current_sequence = None
            self.state.sequence_step = None
        self._broadcast_status()

    def emergency_stop(self) -> None:
        self.stop_sequence()
        self.io.emergency_stop()
        with self._state_lock:
            self.state.state = "ERROR"
            self.state.current_sequence = None
            self.state.last_error = "Emergency stop activated"
        self._broadcast_status()

    def set_relay(self, channel: int, enabled: bool) -> bool:
        self._ensure_manual_allowed()
        return self._set_relay(channel, enabled, allow_when_running=False)

    def set_rotary_port(self, port: int) -> bool:
        self._ensure_manual_allowed()
        return self._set_rotary_port(port, allow_when_running=False)

    def move_syringe(self, volume_ml: float, flow_ml_min: float) -> None:
        self._ensure_manual_allowed()
        self._log(f"[Syringe] move to {volume_ml} mL @ {flow_ml_min} mL/min")
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
        self._broadcast_status()

        self._stop_event.clear()
        self._sequence_thread = threading.Thread(target=self._run_homing, daemon=True)
        self._sequence_thread.start()

    # ---------------------------------------------------
    # Internals
    # ---------------------------------------------------
    def _run_sequence(self, sequence_name: str) -> None:
        try:
            relay_adapter = _RelayAdapter(self, self._stop_event)
            if sequence_name.lower() in {"sequence1", "maf_sampling", "maf"}:
                self._execute_sequence(
                    lambda: run_maf_sampling_sequence(
                        stop_flag=self._stop_event.is_set,
                        log=self._log,
                        relays=relay_adapter,
                        syringe=self.syringe,
                        move_horizontal_to_filtering=self._move_horizontal_preset("filtering"),
                        move_vertical_close_plate=self._move_vertical_preset("close"),
                        select_rotary_port=lambda p: self._set_rotary_port(p, allow_when_running=True),
                        before_step=self._before_step,
                        init=self._home_all_axes,
                    )
                )
            elif sequence_name.lower() in {"sequence2", "seq2"}:
                self._execute_sequence(
                    lambda: run_sequence2(
                        stop_flag=self._stop_event.is_set,
                        log=self._log,
                        relays=relay_adapter,
                        syringe=self.syringe,
                        move_horizontal_to_filtering=self._move_horizontal_preset("filtering"),
                        move_horizontal_home=self._move_horizontal_preset("home"),
                        move_vertical_close_plate=self._move_vertical_preset("close"),
                        move_vertical_open_plate=self._move_vertical_preset("open"),
                        select_rotary_port=lambda p: self._set_rotary_port(p, allow_when_running=True),
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
            self._broadcast_status()
            self._stop_event.clear()

    def _execute_sequence(self, func: Callable[[], None]) -> None:
        func()

    def _before_step(self, step_label: str) -> None:
        with self._state_lock:
            self.state.sequence_step = step_label
        self._append_log(step_label)
        self._broadcast_status()

    def _log(self, message: str) -> None:
        self._append_log(message)
        print(message)

    def _append_log(self, message: str) -> None:
        with self._log_lock:
            self._log_buffer.append(message)
            if len(self._log_buffer) > 100:
                self._log_buffer = self._log_buffer[-100:]
        self._broadcast_status()

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
            self.syringe.home(stop_flag=self._stop_event.is_set)

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
        self._assert_horizontal_allowed()
        if not self.horizontal_axis.ready:
            try:
                self.horizontal_axis.connect()
            except Exception as exc:
                raise RuntimeError(f"Horizontal axis unavailable: {exc}")
        self.horizontal_axis.home(stop_flag=self._stop_event.is_set)

    def _assert_horizontal_allowed(self) -> None:
        guard = self.config.horizontal_axis.vertical_guard_mm
        if guard is None:
            return
        vpos = self._read_vertical_position_mm()
        if vpos is None:
            raise RuntimeError("Horizontal axis locked: vertical axis position unavailable")
        if vpos > guard:
            raise RuntimeError(
                f"Horizontal axis locked: vertical axis at {vpos:.2f} mm (> {guard:.1f} mm limit)"
            )

    def _read_vertical_position_mm(self) -> Optional[float]:
        try:
            return self.vertical_axis.read_position_mm()
        except Exception:
            return None

    def _set_relay(self, channel: int, enabled: bool, allow_when_running: bool) -> bool:
        if self.state.state == "RUNNING" and not allow_when_running:
            raise RuntimeError("Relays locked while a sequence is running")
        ok = self.relays.on(channel) if enabled else self.relays.off(channel)
        if ok:
            self.relay_states[channel] = enabled
            with self._state_lock:
                self.state.relay_states = dict(self.relay_states)
            self._broadcast_status()
        return ok

    def _set_rotary_port(self, port: int, allow_when_running: bool) -> bool:
        if self.state.state == "RUNNING" and not allow_when_running:
            raise RuntimeError("Rotary valve locked while a sequence is running")
        ok = self.rotary.set_port(port)
        if ok:
            self.rotary_port = port
            with self._state_lock:
                self.state.rotary_port = port
            self._broadcast_status()
        return ok

    def _ensure_manual_allowed(self) -> None:
        if self.state.state == "RUNNING":
            raise RuntimeError("Manual control locked while a sequence is running")

    def _noop(self, label: str) -> Callable[[], None]:
        def _fn():
            self._log(f"[NOOP] {label} (not wired)")

        return _fn

    def _move_horizontal_preset(self, key: str) -> Callable[[], None]:
        presets = {
            "filtering": 133.0,
            "filter out": 26.0,
            "filter in": 0.0,
            "home": 0.0,
        }
        target = presets.get(key.lower())
        if target is None:
            return self._noop(f"horizontal preset {key}")

        def _fn():
            self._assert_horizontal_allowed()
            self.horizontal_axis.move_mm(target, rpm=5.0, stop_flag=self._stop_event.is_set)

        return _fn

    def _move_vertical_preset(self, key: str) -> Callable[[], None]:
        presets = {
            "open": 0.0,
            "close": 33.0,
            "home": 0.0,
        }
        target = presets.get(key.lower())
        if target is None:
            return self._noop(f"vertical preset {key}")

        def _fn():
            self.vertical_axis.move_mm(target, rpm=5.0, stop_flag=self._stop_event.is_set)

        return _fn

    def _home_all_axes(self) -> None:
        self._home_vertical_axis()
        self._home_horizontal_axis()

    def _broadcast_status(self) -> None:
        if not self._loop or not self._sse_subscribers:
            return
        snapshot = self.get_status()
        payload = json.dumps(snapshot)
        for q in list(self._sse_subscribers):
            try:
                self._loop.call_soon_threadsafe(q.put_nowait, payload)
            except Exception:
                continue


class _RelayAdapter:
    """Adapter used by sequences to update relay cache while allowing runs."""

    def __init__(self, controller: DeviceController, stop_event: threading.Event):
        self.controller = controller
        self.stop_event = stop_event

    def on(self, channel: int) -> bool:
        if self.stop_event.is_set():
            raise RuntimeError("Operation stopped")
        return self.controller._set_relay(channel, True, allow_when_running=True)

    def off(self, channel: int) -> bool:
        if self.stop_event.is_set():
            raise RuntimeError("Operation stopped")
        return self.controller._set_relay(channel, False, allow_when_running=True)
