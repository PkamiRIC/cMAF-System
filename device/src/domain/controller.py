import threading
import time
import asyncio
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

from hardware.relay_board import RelayBoard
from hardware.syringe_pump import SyringePump
from hardware.axis_driver import AxisDriver
from hardware.peristaltic_pump import PeristalticPump
from hardware.pid_valve import PidValveController
from hardware.rotary_valve import RotaryValve
from hardware.flow_sensor import FlowSensor
from hardware.temperature_control import TemperatureController
from infra.config import DeviceConfig

from domain.sequence1 import run_maf_sampling_sequence
from domain.sequence2 import run_sequence2
from domain.cleaning_sequence import run_maf_cleaning_sequence


@dataclass
class DeviceState:
    state: str = "IDLE"  # IDLE, RUNNING, ERROR
    current_sequence: Optional[str] = None
    sequence_step: Optional[str] = None
    last_error: Optional[str] = None
    stop_requested: bool = False
    relay_states: dict = field(default_factory=dict)
    logs: list = field(default_factory=list)
    syringe_busy: bool = False
    syringe_volume_ml: Optional[float] = None
    syringe_target_ml: Optional[float] = None
    x_target_mm: Optional[float] = None
    z_target_mm: Optional[float] = None
    x_homed: bool = False
    z_homed: bool = False
    syringe_homed: bool = False
    peristaltic_enabled: bool = False
    peristaltic_direction_cw: bool = True
    peristaltic_low_speed: bool = False
    pid_enabled: bool = False
    pid_setpoint: float = 1.0
    pid_hall: Optional[int] = None
    flow_ml_min: float = 0.0
    total_ml: float = 0.0
    flow_running: bool = False
    flow_error: Optional[str] = None
    temp_enabled: bool = False
    temp_ready: Optional[bool] = None
    temp_target_c: float = 58.0
    temp_current_c: Optional[float] = None
    temp_error: Optional[str] = None
    target_volume_ml: Optional[float] = None


class DeviceController:
    def __init__(self, config: DeviceConfig):
        self.config = config
        self.relays = RelayBoard(config.relay)
        self.syringe = SyringePump(config.syringe)
        self.vertical_axis = AxisDriver(config.vertical_axis, "Vertical Axis")
        self.horizontal_axis = AxisDriver(config.horizontal_axis, "Horizontal Axis")
        self.peristaltic = PeristalticPump(config.peristaltic)
        self.rotary_valve = RotaryValve(config.rotary_valve)
        self.flow_sensor = FlowSensor(config.flow_sensor)
        self.temperature = TemperatureController(config.temperature)
        self.pid_valve = PidValveController(config.pid_valve, self._read_flow_for_pid)
        self.state = DeviceState()
        self.state.peristaltic_enabled = self.peristaltic.state.enabled
        self.state.peristaltic_direction_cw = self.peristaltic.state.direction_forward
        self.state.peristaltic_low_speed = self.peristaltic.state.low_speed
        self.state.pid_enabled = self.pid_valve.state.enabled
        self.state.pid_setpoint = self.pid_valve.state.setpoint
        self.state.temp_enabled = self.temperature.state.enabled
        self.state.temp_target_c = float(self.temperature.state.target_c)
        self._stop_event = threading.Event()
        self._sequence_thread: Optional[threading.Thread] = None
        self._sequence_target_volume_ml: Optional[float] = None
        self._sequence_temp_target_c: Optional[float] = None
        self._last_stop_request_at: Optional[float] = None
        self._sequence_stop_timeout_s = 5.0
        self._state_lock = threading.Lock()
        self._log_lock = threading.Lock()
        self._log_buffer: list[str] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._sse_subscribers: list[asyncio.Queue] = []
        # Serialize all physical motion (axes, syringe) across threads.
        self._motion_lock = threading.Lock()
        self._io_retry_attempts = 3
        self._io_retry_delay_s = 0.12

        # Hard caps (Position 3) for manual + sequence moves
        self._axis_max_limits = {
            "Z": self._resolve_axis_limit(config.vertical_axis.max_mm, 33.0),
            "X": self._resolve_axis_limit(config.horizontal_axis.max_mm, 133.0),
        }

        # Relay caches for UI feedback
        self.relay_states = {ch: False for ch in range(1, 9)}

        # --- Live syringe status polling ---
        self._syringe_poll_stop = threading.Event()
        self._syringe_poll_thread: Optional[threading.Thread] = None
        self._live_poll_stop = threading.Event()
        self._flow_poll_thread: Optional[threading.Thread] = None
        self._temp_poll_thread: Optional[threading.Thread] = None

        # Best-effort initial connections for axes
        try:
            self.vertical_axis.connect()
            self.horizontal_axis.connect()
        except Exception:
            # Leave drivers unready; homing will fail with a clear message
            pass

        # Start syringe live poller (busy + volume)
        self._start_syringe_poller(interval_s=0.25)
        self._start_flow_poller(interval_s=0.2)
        self._start_temp_poller(interval_s=0.5)

    # ---------------------------------------------------
    # STATUS
    # ---------------------------------------------------
    def get_status(self) -> dict:
        with self._state_lock:
            # Live flow/temperature are updated asynchronously by pollers.
            self.state.temp_enabled = self.temperature.state.enabled
            self.state.temp_target_c = float(self.temperature.state.target_c)
            self.state.temp_error = self.temperature.state.error
            self.state.peristaltic_enabled = self.peristaltic.state.enabled
            self.state.peristaltic_direction_cw = self.peristaltic.state.direction_forward
            self.state.peristaltic_low_speed = self.peristaltic.state.low_speed
            self.state.pid_enabled = self.pid_valve.state.enabled
            self.state.pid_setpoint = self.pid_valve.state.setpoint
            self.state.pid_hall = self.pid_valve.state.hall_state
            # update cached UI fields
            self.state.relay_states = dict(self.relay_states)
            self.state.logs = list(self._log_buffer)
            snapshot = self._snapshot_unlocked()
        return snapshot

    def attach_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    # ---------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------
    def start_sequence(
        self,
        sequence_name: str,
        target_volume_ml: Optional[float] = None,
        temp_target_c: Optional[float] = None,
    ) -> None:
        if self._sequence_thread and self._sequence_thread.is_alive():
            if self._maybe_force_detach_sequence():
                pass
            else:
                raise RuntimeError("A sequence is already running")
        self._ensure_motion_available("Sequence start")
        self._clear_last_error()

        with self._state_lock:
            self.state.state = "RUNNING"
            self.state.current_sequence = sequence_name
            self.state.last_error = None
            self.state.stop_requested = False
            self.state.sequence_step = None
            self.state.target_volume_ml = target_volume_ml
        self._sequence_target_volume_ml = target_volume_ml
        self._sequence_temp_target_c = temp_target_c
        self._broadcast_status()

        self._stop_event.clear()
        self._sequence_thread = threading.Thread(
            target=self._run_sequence, args=(sequence_name,), daemon=True
        )
        self._sequence_thread.start()

    def stop_sequence(self) -> None:
        self._stop_event.set()
        self._last_stop_request_at = time.time()
        with self._state_lock:
            self.state.stop_requested = True
            self.state.state = "ERROR"
            self.state.last_error = "Operation stopped"
            self.state.current_sequence = None
            self.state.sequence_step = None
        self._broadcast_status()
        # Best-effort: give the sequence thread a chance to exit.
        if self._sequence_thread and self._sequence_thread.is_alive():
            self._sequence_thread.join(timeout=self._sequence_stop_timeout_s)
            if self._sequence_thread.is_alive():
                self._log("[WARN] Sequence thread did not exit; forcing detach")
                self._sequence_thread = None

    def emergency_stop(self) -> None:
        self.stop_sequence()
        self._log("[E-STOP] Emergency stop triggered")
        try:
            self.peristaltic.force_stop()
        except Exception:
            pass
        try:
            self._log("[E-STOP] Stopping vertical axis")
            self.vertical_axis.stop_motion()
        except Exception:
            pass
        try:
            self._log("[E-STOP] Stopping horizontal axis")
            self.horizontal_axis.stop_motion()
        except Exception:
            pass
        try:
            self._log("[E-STOP] Stopping syringe")
            self._stop_syringe(force=True)
        except Exception:
            pass
        try:
            self.pid_valve.set_enabled(False)
        except Exception:
            pass
        try:
            self.temperature.force_off()
        except Exception:
            pass
        try:
            self.relays.all_off()
            for ch in range(1, 9):
                self.relay_states[ch] = False
        except Exception:
            pass
        with self._state_lock:
            self.state.state = "ERROR"
            self.state.current_sequence = None
            self.state.last_error = "Emergency stop activated"
        self._broadcast_status()

    def set_relay(self, channel: int, enabled: bool) -> bool:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self._log(f"[Relay] R{channel} {'ON' if enabled else 'OFF'}")
        return self._retry_bool(
            f"Relay R{channel} {'ON' if enabled else 'OFF'}",
            lambda: self._set_relay(channel, enabled, allow_when_running=False),
        )

    def set_all_relays(self, enabled: bool) -> bool:
        """
        Convenience for bulk relay control using the board's all-on/all-off command.
        """
        self._ensure_manual_allowed()
        self._clear_last_error()
        ok = self._retry_bool(
            f"Relays ALL {'ON' if enabled else 'OFF'}",
            lambda: self.relays.all_on() if enabled else self.relays.all_off(),
        )
        self._log(f"[Relay] ALL {'ON' if enabled else 'OFF'}")
        if ok:
            for ch in range(1, 9):
                self.relay_states[ch] = enabled
            with self._state_lock:
                self.state.relay_states = dict(self.relay_states)
            self._broadcast_status()
        return ok

    def set_peristaltic_enabled(self, enabled: bool) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self.peristaltic.set_enabled(enabled)
        with self._state_lock:
            self.state.peristaltic_enabled = self.peristaltic.state.enabled
        self._broadcast_status()

    def set_peristaltic_direction(self, forward: bool) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self.peristaltic.set_direction(forward)
        with self._state_lock:
            self.state.peristaltic_direction_cw = self.peristaltic.state.direction_forward
        self._broadcast_status()

    def set_peristaltic_speed(self, low_speed: bool) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self.peristaltic.set_speed_checked(low_speed)
        with self._state_lock:
            self.state.peristaltic_low_speed = self.peristaltic.state.low_speed
        self._broadcast_status()

    def set_pid_enabled(self, enabled: bool) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self._log(f"[PID] {'Enabled' if enabled else 'Disabled'}")
        self._retry_void(
            f"PID {'enable' if enabled else 'disable'}",
            lambda: self.pid_valve.set_enabled(enabled),
        )
        with self._state_lock:
            self.state.pid_enabled = self.pid_valve.state.enabled
        self._broadcast_status()

    def set_pid_setpoint(self, value: float) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self._log(f"[PID] Setpoint {value}")
        self._retry_void(
            f"PID setpoint {value}",
            lambda: self.pid_valve.set_setpoint(value),
        )
        with self._state_lock:
            self.state.pid_setpoint = self.pid_valve.state.setpoint
        self._broadcast_status()

    def pid_home(self) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self._log("[PID] Home")
        self._retry_void("PID home", self.pid_valve.homing_routine)
        self._broadcast_status()

    def pid_close(self) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self._log("[PID] Close")
        self._retry_void("PID close", self.pid_valve.force_close)
        self._broadcast_status()

    def set_temp_enabled(self, enabled: bool) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self._log(f"[Temp] {'Enabled' if enabled else 'Disabled'}")
        self._retry_void(
            f"Temp {'enable' if enabled else 'disable'}",
            lambda: self.temperature.set_enabled(enabled),
        )
        with self._state_lock:
            self.state.temp_enabled = self.temperature.state.enabled
            self.state.temp_target_c = float(self.temperature.state.target_c)
            self.state.temp_current_c = self.temperature.state.current_c
            self.state.temp_error = self.temperature.state.error
        self._broadcast_status()

    def set_temp_target(self, target_c: float) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self._log(f"[Temp] Target set to {target_c:.2f}C")
        self._retry_void(
            f"Temp set target {target_c:.2f}C",
            lambda: self.temperature.set_target_c(target_c),
        )
        with self._state_lock:
            self.state.temp_target_c = float(self.temperature.state.target_c)
            self.state.temp_current_c = self.temperature.state.current_c
            self.state.temp_error = self.temperature.state.error
        self._broadcast_status()

    def flow_start(self) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self.flow_sensor.start()
        with self._state_lock:
            self.state.flow_running = self.flow_sensor.is_running()
            self.state.flow_error = self.flow_sensor.get_last_error()
        self._broadcast_status()

    def flow_stop(self) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self.flow_sensor.stop()
        with self._state_lock:
            self.state.flow_running = self.flow_sensor.is_running()
            self.state.flow_error = self.flow_sensor.get_last_error()
        self._broadcast_status()

    def flow_reset(self) -> None:
        self._ensure_manual_allowed()
        self._clear_last_error()
        self.flow_sensor.reset_totals()
        with self._state_lock:
            self.state.flow_error = self.flow_sensor.get_last_error()
        self._broadcast_status()

    def move_syringe(self, volume_ml: float, flow_ml_min: float) -> None:
        """
        Manual syringe move. Do NOT force syringe_busy here; live poller drives it.
        We only record the target for UI display.
        """
        self._ensure_manual_allowed()
        self._ensure_motion_available("Syringe move")
        self._clear_last_error()
        # Clear stale stop flags from prior operations before manual moves.
        self._stop_event.clear()
        self._log(f"[Syringe] move to {volume_ml} mL @ {flow_ml_min} mL/min")
        with self._state_lock:
            self.state.syringe_target_ml = volume_ml
            # Any non-homing motion invalidates the homed flag
            self.state.syringe_homed = False
        self._broadcast_status()

        with self._motion_lock:
            for attempt in range(1, 3):
                if self._stop_event.is_set():
                    raise RuntimeError("Operation stopped")
                self.syringe.goto_absolute(volume_ml, flow_ml_min)
                ok = self.syringe.wait_until_at_target(
                    timeout=120, stop_flag=self._stop_event.is_set
                )
                if ok:
                    break
                if attempt >= 2:
                    raise RuntimeError("Syringe move timed out")
                time.sleep(0.2)

        # Do not overwrite syringe_volume_ml here; poller updates it continuously.
        self._broadcast_status()

    def _stop_syringe(self, force: bool = False) -> None:
        # Allow stopping even during homing sequence
        if not force and self.state.state == "RUNNING" and self.state.current_sequence != "homing":
            self._ensure_manual_allowed()
        self._clear_last_error()
        self._log("[Syringe] stop request")
        self._stop_event.set()
        with self._state_lock:
            vol_hint = self.state.syringe_volume_ml
        with self._motion_lock:
            self.syringe.quick_stop()
            ok = self.syringe.stop_motion(volume_hint_ml=vol_hint)
        if not ok:
            raise RuntimeError("Syringe stop failed")
        self._stop_event.clear()
        # Do not force syringe_busy; poller will update based on real status.
        self._broadcast_status()

    def stop_syringe(self) -> None:
        self._stop_syringe(force=False)

    def home_syringe(self) -> None:
        self._ensure_manual_allowed()
        self._ensure_motion_available("Syringe home")
        self._clear_last_error()
        self._log("[Syringe] homing")
        # Do not force syringe_busy; poller will reflect true motion.
        with self._motion_lock:
            last_exc: Optional[Exception] = None
            for attempt in range(1, 3):
                if self._stop_event.is_set():
                    raise RuntimeError("Operation stopped")
                try:
                    ok = self.syringe.home(stop_flag=self._stop_event.is_set)
                    last_exc = None
                except Exception as exc:
                    ok = False
                    last_exc = exc
                if ok:
                    break
                if attempt >= 2:
                    if last_exc:
                        raise RuntimeError(f"Syringe home failed: {last_exc}") from last_exc
                    raise RuntimeError("Syringe home timed out")
                time.sleep(0.2)
        with self._state_lock:
            self.state.syringe_target_ml = 0.0
            self.state.syringe_homed = True
        self._broadcast_status()

    # ---------------------------------------------------
    # AXIS MANUAL CONTROL
    # ---------------------------------------------------
    def move_axis(self, axis: str, position_mm: float, rpm: float) -> None:
        # Allow manual moves when not running a user sequence (idle or homing)
        # Manual moves allowed even if a sequence is running.
        # Clear stale stop flags from prior errors before a manual move.
        self._stop_event.clear()
        self._ensure_motion_available(f"Axis {axis} move")
        self._clear_last_error()
        axis_norm = axis.upper()
        if axis_norm == "Z":
            self._ensure_axis_ready(self.vertical_axis, "Vertical")
            target = self._clamp(
                position_mm, self.config.vertical_axis.min_mm, self._axis_max_limits["Z"]
            )
            driver = self.vertical_axis
            log_label = "Vertical"
            target_field = "z_target_mm"
        elif axis_norm == "X":
            self._ensure_axis_ready(self.horizontal_axis, "Horizontal")
            target = self._clamp(
                position_mm, self.config.horizontal_axis.min_mm, self._axis_max_limits["X"]
            )
            driver = self.horizontal_axis
            log_label = "Horizontal"
            target_field = "x_target_mm"
        else:
            raise ValueError("axis must be X or Z")
        self._log(f"[Axis {log_label}] move to {target:.2f} mm @ {rpm:.2f} rpm")
        with self._state_lock:
            setattr(self.state, target_field, target)
            # Any non-homing motion invalidates the homed flag
            if axis_norm == "Z":
                self.state.z_homed = False
            else:
                self.state.x_homed = False
        try:
            with self._motion_lock:
                # Re-check safety interlocks at execution time (after any prior motion completes).
                if axis_norm == "X":
                    self._assert_horizontal_allowed()
                driver.move_mm(target, rpm=rpm, stop_flag=self._stop_event.is_set)
        except Exception:
            # Drop the driver so the next attempt will reconnect cleanly.
            driver.mark_unready()
            raise

    def home_axis(self, axis: str) -> None:
        # Clear stale stop flags from earlier errors before homing.
        self._stop_event.clear()
        self._ensure_motion_available(f"Axis {axis} home")
        self._clear_last_error()
        axis_norm = axis.upper()
        self._log(f"[Axis {axis_norm}] homing (manual)")
        # Manual moves allowed even if a sequence is running.
        if axis_norm == "Z":
            self._home_vertical_axis()
        elif axis_norm == "X":
            self._home_horizontal_axis()
        else:
            raise ValueError("axis must be X or Z")

    @staticmethod
    def _clamp(value: float, min_v: Optional[float], max_v: Optional[float]) -> float:
        if min_v is not None:
            value = max(min_v, value)
        if max_v is not None:
            value = min(max_v, value)
        return value

    @staticmethod
    def _resolve_axis_limit(cfg_max: Optional[float], hard_cap: float) -> float:
        if cfg_max is None:
            return hard_cap
        return min(cfg_max, hard_cap)

    def home_all(self) -> None:
        """
        Homing routine mirroring the old GUI's Initialize button:
        runs in a background thread so it can be stopped.
        """
        if self._sequence_thread and self._sequence_thread.is_alive():
            if self._maybe_force_detach_sequence():
                pass
            else:
                raise RuntimeError("Another operation is already running")
        self._ensure_motion_available("Initialize / homing")
        self._clear_last_error()

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
    # Syringe Live Poller
    # ---------------------------------------------------
    def _start_syringe_poller(self, interval_s: float = 0.25) -> None:
        if self._syringe_poll_thread and self._syringe_poll_thread.is_alive():
            return
        self._syringe_poll_stop.clear()
        self._syringe_poll_thread = threading.Thread(
            target=self._syringe_poller_loop, args=(interval_s,), daemon=True
        )
        self._syringe_poll_thread.start()

    def _start_flow_poller(self, interval_s: float = 0.2) -> None:
        if self._flow_poll_thread and self._flow_poll_thread.is_alive():
            return
        self._flow_poll_thread = threading.Thread(
            target=self._flow_poller_loop, args=(interval_s,), daemon=True
        )
        self._flow_poll_thread.start()

    def _start_temp_poller(self, interval_s: float = 0.5) -> None:
        if self._temp_poll_thread and self._temp_poll_thread.is_alive():
            return
        self._temp_poll_thread = threading.Thread(
            target=self._temp_poller_loop, args=(interval_s,), daemon=True
        )
        self._temp_poll_thread.start()

    def _flow_poller_loop(self, interval_s: float) -> None:
        while not self._live_poll_stop.is_set():
            changed = False
            try:
                flow = self.flow_sensor.read()
                flow_ml_min = float(flow.get("flow_ml_min", 0.0))
                total_ml = float(flow.get("total_ml", 0.0))
                running = bool(self.flow_sensor.is_running())
                err = self.flow_sensor.get_last_error()

                with self._state_lock:
                    if self.state.flow_ml_min != flow_ml_min:
                        self.state.flow_ml_min = flow_ml_min
                        changed = True
                    if self.state.total_ml != total_ml:
                        self.state.total_ml = total_ml
                        changed = True
                    if self.state.flow_running != running:
                        self.state.flow_running = running
                        changed = True
                    if self.state.flow_error != err:
                        self.state.flow_error = err
                        changed = True
            except Exception as exc:
                with self._state_lock:
                    if self.state.flow_error != str(exc):
                        self.state.flow_error = str(exc)
                        changed = True
            if changed:
                self._broadcast_status()
            self._live_poll_stop.wait(max(0.05, interval_s))

    def _temp_poller_loop(self, interval_s: float) -> None:
        while not self._live_poll_stop.is_set():
            changed = False
            try:
                current = self.temperature.read_current_c()
                ready = self.temperature.read_ready()
                enabled = bool(self.temperature.state.enabled)
                target = float(self.temperature.state.target_c)
                err = self.temperature.state.error
                with self._state_lock:
                    if self.state.temp_current_c != current:
                        self.state.temp_current_c = current
                        changed = True
                    if self.state.temp_ready != ready:
                        self.state.temp_ready = ready
                        changed = True
                    if self.state.temp_enabled != enabled:
                        self.state.temp_enabled = enabled
                        changed = True
                    if self.state.temp_target_c != target:
                        self.state.temp_target_c = target
                        changed = True
                    if self.state.temp_error != err:
                        self.state.temp_error = err
                        changed = True
            except Exception as exc:
                with self._state_lock:
                    if self.state.temp_error != str(exc):
                        self.state.temp_error = str(exc)
                        changed = True
            if changed:
                self._broadcast_status()
            self._live_poll_stop.wait(max(0.1, interval_s))

    def _syringe_poller_loop(self, interval_s: float) -> None:
        """
        Continuously poll syringe status and derive ACTIVE/IDLE from motion evidence.

        Why not just "busy bit"?
        Many drives clear their "busy" flag once the command is latched, even while motion continues.
        Motion evidence is more robust: standstill bit + actual velocity + flow.
        """
        idle_streak = 0
        last_active: Optional[bool] = None
        last_vol: Optional[float] = None

        # thresholds: tune if needed
        vel_thresh_steps = 5
        flow_thresh_ml_min = 0.01
        idle_debounce_polls = 3  # e.g. 3 * 0.25s = 0.75s stable idle before declaring idle

        while not self._syringe_poll_stop.is_set():
            try:
                st = self.syringe.read_status()
                if st is None:
                    time.sleep(interval_s)
                    continue

                busy_bit = int(st.get("busy", 0))
                standstill_bit = int(st.get("standstill", 1))
                actual_velocity = int(st.get("actual_velocity", 0))
                flow_ml_min = float(st.get("flow_ml_min", 0.0))
                volume_ml = st.get("volume_ml", None)

                moving = (
                    busy_bit == 1
                    or standstill_bit == 0
                    or abs(actual_velocity) > vel_thresh_steps
                    or abs(flow_ml_min) > flow_thresh_ml_min
                )

                if moving:
                    idle_streak = 0
                else:
                    idle_streak += 1

                is_active = moving or idle_streak < idle_debounce_polls

                changed = False
                with self._state_lock:
                    if is_active != self.state.syringe_busy:
                        self.state.syringe_busy = is_active
                        changed = True

                    if volume_ml is not None:
                        try:
                            v = float(volume_ml)
                        except Exception:
                            v = None
                        if v is not None and self.state.syringe_volume_ml != v:
                            self.state.syringe_volume_ml = v
                            changed = True

                # Throttle SSE chatter: broadcast only when meaningful change occurs.
                # Also keep a small additional guard so we don’t rebroadcast identical states.
                if changed:
                    self._broadcast_status()

                last_active = is_active
                last_vol = self.state.syringe_volume_ml

            except Exception as exc:
                # Do not kill poller; just surface error.
                with self._state_lock:
                    self.state.last_error = f"Syringe status poll error: {exc}"
                self._broadcast_status()

            time.sleep(interval_s)

    # ---------------------------------------------------
    # Internals
    # ---------------------------------------------------
    def _run_sequence(self, sequence_name: str) -> None:
        try:
            relay_adapter = _RelayAdapter(self, self._stop_event)
            syringe_adapter = _SyringeAdapter(self, self._stop_event)
            seq = sequence_name.lower()
            if seq in {"sequence1", "seq1", "maf", "maf1"}:
                target_ml = (
                    self._sequence_target_volume_ml
                    if self._sequence_target_volume_ml is not None
                    else 50.0
                )
                self._execute_sequence(
                    lambda: run_maf_sampling_sequence(
                        stop_flag=self._stop_event.is_set,
                        reset_flow_totals=self._flow_reset,
                        start_flow_meter=self._flow_start,
                        stop_flow_meter=self._flow_stop,
                        get_total_volume_ml=self._flow_total_ml,
                        log=self._log,
                        relays=relay_adapter,
                        motor_pump=self.peristaltic,
                        pid_controller=self.pid_valve,
                        home_pid_valve=self._pid_home,
                        syringe=syringe_adapter,
                        enable_temp_controller=self._temp_enable,
                        disable_temp_controller=self._temp_disable,
                        wait_for_temp_ready=self._temp_wait_ready,
                        wait_for_maf_heating=self._maf_wait_for_heating,
                        move_horizontal_to_filtering=self._move_horizontal_preset("filtering"),
                        move_horizontal_to_waste=self._move_horizontal_preset("filter out"),
                        move_horizontal_to_home=self._move_horizontal_preset("home"),
                        move_vertical_close_plate=self._move_vertical_preset("close"),
                        move_vertical_open_plate=self._move_vertical_preset("open"),
                        target_volume_ml=target_ml,
                        post_volume_wait_s=self.config.sequence1.post_volume_wait_s,
                        early_complete_ratio=self.config.sequence1.early_complete_ratio,
                        early_complete_wait_s=self.config.sequence1.early_complete_wait_s,
                        stagnant_timeout_s=self.config.sequence1.stagnant_timeout_s,
                        stagnant_epsilon_ml=self.config.sequence1.stagnant_epsilon_ml,
                        before_step=self._before_step,
                    )
                )
            elif seq in {"sequence2", "seq2", "maf2"}:
                target_ml = (
                    self._sequence_target_volume_ml
                    if self._sequence_target_volume_ml is not None
                    else float(self.config.sequence2.target_volume_ml)
                )
                self._execute_sequence(
                    lambda: run_sequence2(
                        stop_flag=self._stop_event.is_set,
                        log=self._log,
                        relays=relay_adapter,
                        syringe=syringe_adapter,
                        move_horizontal_to_filtering=self._move_horizontal_preset("filtering"),
                        move_horizontal_home=self._move_horizontal_preset("home"),
                        move_vertical_close_plate=self._move_vertical_preset("close"),
                        move_vertical_open_plate=self._move_vertical_preset("open"),
                        select_rotary_port=self._select_rotary_port,
                        reset_flow_totals=self._flow_reset,
                        start_flow_meter=self._flow_start,
                        stop_flow_meter=self._flow_stop,
                        get_total_volume_ml=self._flow_total_ml,
                        target_volume_ml=target_ml,
                        early_complete_ratio=self.config.sequence2.early_complete_ratio,
                        early_complete_wait_s=self.config.sequence2.early_complete_wait_s,
                        stagnant_timeout_s=self.config.sequence2.stagnant_timeout_s,
                        stagnant_epsilon_ml=self.config.sequence2.stagnant_epsilon_ml,
                        before_step=self._before_step,
                    )
                )
            elif seq in {"cleaning", "clean", "cleaning_sequence"}:
                self._execute_sequence(
                    lambda: run_maf_cleaning_sequence(
                        stop_flag=self._stop_event.is_set,
                        log=self._log,
                        relays=relay_adapter,
                        motor_pump=self.peristaltic,
                        pid_controller=self.pid_valve,
                        home_pid_valve=self._pid_home,
                        move_horizontal_to_filtering=self._move_horizontal_preset("filtering"),
                        move_horizontal_to_home=self._move_horizontal_preset("home"),
                        move_vertical_close_plate=self._move_vertical_preset("close"),
                        move_vertical_open_plate=self._move_vertical_preset("open"),
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
                self.state.target_volume_ml = None
            self._sequence_target_volume_ml = None
            self._sequence_temp_target_c = None
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

    def clear_logs(self) -> None:
        with self._log_lock:
            self._log_buffer = []
        with self._state_lock:
            self.state.logs = []
        self._broadcast_status()

    def _not_wired(self, label: str) -> Callable[[], None]:
        def _fn():
            raise RuntimeError(f"Action '{label}' not wired to backend yet")

        return _fn

    def _read_flow_for_pid(self) -> float:
        try:
            return float(self.flow_sensor.read().get("flow_ml_min", 0.0))
        except Exception:
            return 0.0

    def _flow_start(self) -> None:
        self.flow_sensor.start()

    def _flow_stop(self) -> None:
        self.flow_sensor.stop()

    def _flow_reset(self) -> None:
        self.flow_sensor.reset_totals()

    def _flow_total_ml(self) -> float:
        return float(self.flow_sensor.read().get("total_ml", 0.0))

    def _temp_enable(self) -> None:
        with self._state_lock:
            current_target_c = float(self.state.temp_target_c)
        target_c = (
            float(self._sequence_temp_target_c)
            if self._sequence_temp_target_c is not None
            else current_target_c
        )
        try:
            self.temperature.set_target_c(target_c)
            with self._state_lock:
                self.state.temp_target_c = float(self.temperature.state.target_c)
            self._log(f"[Temp] Sequence target {target_c:.2f}C")
        except Exception as exc:
            self._log(f"[WARN] Temp target apply skipped: {exc}")
            with self._state_lock:
                self.state.temp_error = str(exc)
        try:
            self.temperature.set_enabled(True)
        except Exception as exc:
            self._log(f"[WARN] Temp enable skipped: {exc}")
            with self._state_lock:
                self.state.temp_error = str(exc)

    def _temp_disable(self) -> None:
        try:
            self.temperature.set_enabled(False)
        except Exception as exc:
            self._log(f"[WARN] Temp disable skipped: {exc}")
            with self._state_lock:
                self.state.temp_error = str(exc)

    def _temp_wait_ready(self, timeout: float = 120.0) -> None:
        if not self.temperature.state.enabled:
            self._log("[WARN] Temp wait bypassed: controller is OFF")
            return
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._stop_event.is_set():
                raise InterruptedError("Sequence canceled")
            try:
                state = self.temperature.read_ready()
            except Exception as exc:
                self._log(f"[WARN] Temp wait bypassed: {exc}")
                return
            if state:
                return
            time.sleep(0.5)
        self._log("[WARN] Temp ready timeout; continuing sequence")

    def _maf_wait_for_heating(self, duration: float = 10.0) -> None:
        end = time.time() + max(0.0, duration)
        while time.time() < end:
            if self._stop_event.is_set():
                raise InterruptedError("Sequence canceled")
            time.sleep(0.5)

    def _pid_home(self) -> None:
        self.pid_valve.homing_routine()

    def _prepare_outputs_for_homing(self) -> None:
        """Best-effort: switch off relays before moving axes."""
        try:
            if hasattr(self.relays, "all_off"):
                self.relays.all_off()
            else:
                for ch in range(1, 9):
                    self.relays.off(ch)
            for ch in range(1, 9):
                self.relay_states[ch] = False
            with self._state_lock:
                self.state.relay_states = dict(self.relay_states)
            self._log("[Relays] All OFF before homing")
            self._broadcast_status()
            time.sleep(0.5)  # Allow relays to settle
        except Exception:
            # Keep going even if one relay write fails
            pass
        try:
            self.peristaltic.force_stop()
            with self._state_lock:
                self.state.peristaltic_enabled = False
            self._log("[Peristaltic] Forced OFF before homing")
        except Exception:
            pass
        try:
            self.pid_valve.set_enabled(False)
            self.pid_valve.homing_routine()
            with self._state_lock:
                self.state.pid_enabled = False
            self._log("[PID] Disabled + homed before homing sequence")
        except Exception:
            pass
        try:
            self.temperature.force_off()
            with self._state_lock:
                self.state.temp_enabled = False
            self._log("[Temp] Forced OFF before homing")
        except Exception:
            pass

    def _check_stop(self) -> None:
        if self._stop_event.is_set():
            raise RuntimeError("Operation stopped")

    def _run_homing(self) -> None:
        try:
            self._log("[Init] Initialization begins")
            self._check_stop()
            self._run_initialize_relay_sequence()
            self._prepare_outputs_for_homing()

            self._before_step("Homing vertical axis")
            self._check_stop()
            self._home_vertical_axis()

            self._before_step("Homing horizontal axis")
            self._check_stop()
            self._home_horizontal_axis()

            self._before_step("Homing syringe pump")
            self._check_stop()
            try:
                self._set_relay(1, True, allow_when_running=True)
            except Exception:
                pass
            with self._motion_lock:
                last_exc: Optional[Exception] = None
                for attempt in range(1, 3):
                    try:
                        ok = self.syringe.home(stop_flag=self._stop_event.is_set)
                        last_exc = None
                    except Exception as exc:
                        ok = False
                        last_exc = exc
                    if ok:
                        break
                    if attempt >= 2:
                        if last_exc:
                            raise RuntimeError(
                                f"Syringe home failed during initialize: {last_exc}"
                            ) from last_exc
                        raise RuntimeError("Syringe home timed out during initialize")
                    time.sleep(0.2)
            self._append_log("Syringe homed")
            with self._state_lock:
                self.state.syringe_homed = True
                self.state.state = "IDLE"
                self.state.last_error = None
            try:
                self._set_relay(1, False, allow_when_running=True)
            except Exception:
                pass
            self._log("[Init] Initialization finished")
        except Exception as exc:
            with self._state_lock:
                self.state.state = "ERROR"
                self.state.last_error = str(exc)
        finally:
            with self._state_lock:
                self.state.current_sequence = None
                self.state.sequence_step = None
                self.state.stop_requested = False
            self._broadcast_status()
            self._stop_event.clear()

    def _run_initialize_relay_sequence(self) -> None:
        """
        Custom pre-initialize relay sequence requested for startup safety:
        1) Relay 6 OFF
        2) Relay 7 OFF
        3) Wait 4 seconds
        4) Relay 5 OFF
        """
        self._before_step("Initialize relays: R6 OFF, R7 OFF, wait 4s, then R5 OFF")

        relay_gap_s = 0.15

        for idx, ch in enumerate((6, 7)):
            self._check_stop()
            ok = self._retry_bool(
                f"Relay R{ch} OFF (init)",
                lambda ch=ch: self._set_relay(ch, False, allow_when_running=True),
            )
            if not ok:
                raise RuntimeError(f"Relay R{ch} OFF failed during initialize")
            # Small settle time between back-to-back relay writes on shared RS485.
            if idx < 1:
                end_gap = time.time() + relay_gap_s
                while time.time() < end_gap:
                    self._check_stop()
                    time.sleep(0.02)

        hold_s = 4.0
        self._append_log(f"[Init] Holding {hold_s:.1f}s before turning R5 OFF")
        end = time.time() + hold_s
        while time.time() < end:
            self._check_stop()
            time.sleep(0.1)

        self._check_stop()
        end_gap = time.time() + relay_gap_s
        while time.time() < end_gap:
            self._check_stop()
            time.sleep(0.02)

        self._check_stop()
        ok = self._retry_bool(
            "Relay R5 OFF (init)",
            lambda: self._set_relay(5, False, allow_when_running=True),
        )
        if not ok:
            raise RuntimeError("Relay R5 OFF failed during initialize")

    def _home_vertical_axis(self) -> None:
        if not self.vertical_axis.ready:
            try:
                self.vertical_axis.connect()
            except Exception as exc:
                raise RuntimeError(f"Vertical axis unavailable: {exc}")
        with self._motion_lock:
            self.vertical_axis.home(stop_flag=self._stop_event.is_set)
        with self._state_lock:
            self.state.z_homed = True
        self._append_log("Vertical axis homed")

    def _home_horizontal_axis(self) -> None:
        if not self.horizontal_axis.ready:
            try:
                self.horizontal_axis.connect()
            except Exception as exc:
                raise RuntimeError(f"Horizontal axis unavailable: {exc}")
        with self._motion_lock:
            # Re-check safety interlocks at execution time.
            self._assert_horizontal_allowed()
            self.horizontal_axis.home(stop_flag=self._stop_event.is_set)
        with self._state_lock:
            self.state.x_homed = True
        self._append_log("Horizontal axis homed")

    def _assert_horizontal_allowed(self) -> None:
        # Block horizontal motion if vertical is above safety threshold.
        guard = self.config.horizontal_axis.vertical_guard_mm
        if guard is None:
            guard = 10.0  # legacy default from WARP3_v6
        vpos = self._read_vertical_position_mm()
        if vpos is None:
            raise RuntimeError("Horizontal axis locked: vertical axis position unavailable")
        if vpos > guard:
            raise RuntimeError(
                f"Horizontal axis locked: vertical axis at {vpos:.2f} mm (> {guard:.1f} mm limit)"
            )

    def _read_vertical_position_mm(self) -> Optional[float]:
        try:
            self._ensure_axis_ready(self.vertical_axis, "Vertical")
            return self.vertical_axis.read_position_mm()
        except Exception:
            return None

    def _set_relay(self, channel: int, enabled: bool, allow_when_running: bool) -> bool:
        # Allow relay control even if a sequence is running.
        ok = self.relays.on(channel) if enabled else self.relays.off(channel)
        if ok:
            self.relay_states[channel] = enabled
            with self._state_lock:
                self.state.relay_states = dict(self.relay_states)
            self._broadcast_status()
        return ok

    def _ensure_manual_allowed(self) -> None:
        with self._state_lock:
            running = self.state.state == "RUNNING"
            current = self.state.current_sequence
        if running:
            op = current or "operation"
            raise RuntimeError(f"Manual command blocked while '{op}' is running")

    def _clear_last_error(self) -> None:
        with self._state_lock:
            if self.state.last_error is not None:
                self.state.last_error = None
                if self.state.state == "ERROR":
                    self.state.state = "IDLE"
        self._broadcast_status()

    def _ensure_motion_available(self, label: str) -> None:
        """
        Reject new motion commands if another motion is in progress.
        Allow a short grace period for transient lock holds to clear.
        """
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if self._motion_lock.acquire(blocking=False):
                self._motion_lock.release()
                return
            time.sleep(0.05)
        raise RuntimeError(f"{label} rejected: motion busy")

    def _retry_bool(self, label: str, fn: Callable[[], bool]) -> bool:
        last_ok = False
        for attempt in range(1, self._io_retry_attempts + 1):
            try:
                last_ok = bool(fn())
            except Exception as exc:
                last_ok = False
                self._log(f"[Retry] {label} failed ({exc})")
            if last_ok:
                return True
            if attempt < self._io_retry_attempts:
                self._log(f"[Retry] {label} attempt {attempt + 1}/{self._io_retry_attempts}")
                time.sleep(self._io_retry_delay_s)
        return False

    def _retry_void(self, label: str, fn: Callable[[], None]) -> None:
        for attempt in range(1, self._io_retry_attempts + 1):
            try:
                fn()
                return
            except Exception as exc:
                self._log(f"[Retry] {label} failed ({exc})")
                if attempt < self._io_retry_attempts:
                    self._log(f"[Retry] {label} attempt {attempt + 1}/{self._io_retry_attempts}")
                    time.sleep(self._io_retry_delay_s)
        raise RuntimeError(f"{label} failed after {self._io_retry_attempts} attempts")

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
            self._ensure_axis_ready(self.horizontal_axis, "Horizontal")
            clamped = self._clamp(target, self.config.horizontal_axis.min_mm, self._axis_max_limits["X"])
            with self._state_lock:
                self.state.x_homed = False
            with self._motion_lock:
                # Re-check safety interlocks at execution time.
                self._assert_horizontal_allowed()
                self.horizontal_axis.move_mm(clamped, rpm=0.25, stop_flag=self._stop_event.is_set)

        return _fn

    def _move_vertical_preset(self, key: str) -> Callable[[], None]:
        presets = {
            "open": 0.0,
            "close": 25.0,
            "home": 0.0,
        }
        target = presets.get(key.lower())
        if target is None:
            return self._noop(f"vertical preset {key}")

        def _fn():
            self._ensure_axis_ready(self.vertical_axis, "Vertical")
            clamped = self._clamp(target, self.config.vertical_axis.min_mm, self._axis_max_limits["Z"])
            with self._state_lock:
                self.state.z_homed = False
            with self._motion_lock:
                self.vertical_axis.move_mm(clamped, rpm=0.25, stop_flag=self._stop_event.is_set)

        return _fn

    def _select_rotary_port(self, port: int) -> None:
        ok = self.rotary_valve.set_port(int(port))
        if not ok:
            raise RuntimeError(f"Rotary valve failed to set port {port}")

    def _ensure_axis_ready(self, driver: AxisDriver, label: str) -> None:
        if driver.ready:
            return
        try:
            driver.connect()
        except Exception as exc:
            raise RuntimeError(f"{label} axis unavailable: {exc}")

    def _home_all_axes(self) -> None:
        self._home_vertical_axis()
        self._home_horizontal_axis()

    def _broadcast_status(self) -> None:
        if not self._loop or not self._sse_subscribers:
            return
        with self._state_lock:
            snapshot = self._snapshot_unlocked()
        payload = json.dumps(snapshot)
        for q in list(self._sse_subscribers):
            try:
                self._loop.call_soon_threadsafe(q.put_nowait, payload)
            except Exception:
                continue

    def _snapshot_unlocked(self) -> dict:
        return {"device_id": self.config.device_id, **asdict(self.state)}

    def _maybe_force_detach_sequence(self) -> bool:
        """
        If a stop was requested and the sequence thread did not exit,
        allow new operations after a timeout by detaching the thread handle.
        """
        if not self._sequence_thread or not self._sequence_thread.is_alive():
            return False
        if self._last_stop_request_at is None:
            return False
        if (time.time() - self._last_stop_request_at) < self._sequence_stop_timeout_s:
            return False
        self._log("[WARN] Forcing sequence detach after stop timeout")
        self._sequence_thread = None
        return True

class _RelayAdapter:
    """Adapter used by sequences to update relay cache while allowing runs."""

    def __init__(self, controller: DeviceController, stop_event: threading.Event):
        self.controller = controller
        self.stop_event = stop_event

    def on(self, channel: int) -> bool:
        if self.stop_event.is_set():
            raise RuntimeError("Operation stopped")
        ok = self.controller._retry_bool(
            f"Relay R{channel} ON (sequence)",
            lambda: self.controller._set_relay(channel, True, allow_when_running=True),
        )
        if not ok:
            raise RuntimeError(f"Relay R{channel} ON failed")
        return ok

    def off(self, channel: int) -> bool:
        if self.stop_event.is_set():
            raise RuntimeError("Operation stopped")
        ok = self.controller._retry_bool(
            f"Relay R{channel} OFF (sequence)",
            lambda: self.controller._set_relay(channel, False, allow_when_running=True),
        )
        if not ok:
            raise RuntimeError(f"Relay R{channel} OFF failed")
        return ok


class _SyringeAdapter:
    """Adapter used by sequences to serialize syringe motion and allow STOP checks."""

    def __init__(self, controller: DeviceController, stop_event: threading.Event):
        self.controller = controller
        self.stop_event = stop_event

    def goto_absolute(self, volume_ml: float, flow_ml_min: float) -> None:
        if self.stop_event.is_set():
            raise RuntimeError("Operation stopped")
        with self.controller._motion_lock:
            self.controller.syringe.goto_absolute(volume_ml, flow_ml_min)
            ok = self.controller.syringe.wait_until_at_target(
                timeout=120, stop_flag=self.stop_event.is_set
            )
        if not ok:
            raise RuntimeError("Syringe move timed out")
