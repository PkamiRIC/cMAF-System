#!/usr/bin/env python3
"""Compact control GUI for the alternate device sharing MainGUI_v5 aesthetics."""

import importlib.util
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple
import serial

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QSizePolicy,
    QPlainTextEdit,
    QCheckBox,
)

from rotary_valve import RotaryValve
from Sequence_1 import run_maf_sampling_sequence
from Sequence_2 import run_sequence2

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO.setwarnings(False)
except ImportError:  # pragma: no cover
    GPIO = None


# ===== Init timeouts =====
INIT_CONNECT_TIMEOUT = 6.0      # seconds per device connect probe
INIT_HOME_TIMEOUT = 10.0        # seconds per homing action
INIT_TOTAL_TIMEOUT = 25.0       # hard cap for full initialization
REQUIRE_SYRINGE_FOR_INIT = False # abort init if syringe doesn't ACK

def _run_with_timeout(func, timeout_s: float) -> bool:
    """Run func() in a thread; return True if it finishes before timeout."""
    done = threading.Event()
    def _wrap():
        try:
            func()
        finally:
            done.set()
    th = threading.Thread(target=_wrap, daemon=True)
    th.start()
    return done.wait(timeout_s)


from librpiplc import rpiplc as plc
from relay_board import RelayBoard06

try:
    from Syringe_Class import SyringePump as _SyringePump  # type: ignore
except ModuleNotFoundError:
    _SyringePump = None

if _SyringePump is None:
    _syringe_path = Path(__file__).with_name("Syringe_Class.py")
    if _syringe_path.exists():
        _spec = importlib.util.spec_from_file_location("syringe_module_alt", _syringe_path)
        if _spec and _spec.loader:
            _module = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_module)  # type: ignore[arg-type]
            _SyringePump = getattr(_module, "SyringePump", None)

SyringePump = _SyringePump

# IO / device configuration
RELAY_PORT = "/dev/ttySC3"
RELAY_ADDRESS = 0x02    #Check DIP switches for address
SYRINGE_PORT = "/dev/ttySC3"
SYRINGE_PUMP_ADDRESS = 0x4C
SYRINGE_STEPS_PER_ML = 8_000_000
SYRINGE_VELOCITY_CALIB = 8_000
DEFAULT_VERIFY_CONNECTIONS = False
CONNECTION_PROBE_TIMEOUT = 6.0

RELAY_OUTPUTS = [
    (1, "Relay 1"),
    (2, "Relay 2"),
    (3, "Relay 3"),
    (4, "Relay 4"),
]
RELAY_COMMAND_DELAY = 0.08  # seconds between batch commands

STEPPER_AXES = (
    {
        "name": "Vertical Axis",
        "address": 0x4E,
        "steps_per_ml": 2000.0,
        "velocity_calib": 1000.0,
        "positive_label": "Move",
        "negative_label": "Down",
        "home_enabled": True,
        "extra_buttons": ("Open", "Close"),
        "steps_per_mm": 2000.0,
        "min_mm": 0.0,
        "max_mm": 33.0,
    },
    {
        "name": "Horizontal Axis",
        "address": 0x4D,
        "steps_per_ml": 2000.0,
        "velocity_calib": 1000.0,
        "positive_label": "Move",
        "negative_label": "Left",
        "home_enabled": True,
        "steps_per_mm": 2000.0,
        "extra_buttons": (
            "Filtering",
            "Filter Out",
            "Filter In",
        ),
    },
)

# Hardcoded preset targets (label -> mm) for each axis' quick buttons.
AXIS_PRESET_POSITIONS = {
    "Vertical Axis": {
        "open": ("Open", 0.0),
        "close": ("Close", 33.0),
    },
    "Horizontal Axis": {
        "filtering": ("Filtering", 133.0),
        "filter out": ("Filter Out", 26.0),
        "filter in": ("Filter In", 0.0),
        "loading 0mm": ("Filter In", 0.0),
        "loadin 0mm": ("Filter In", 0.0),
    },
}

AXIS_JOG_STEPS_PER_MM = 2000   # jog distance conversion
AXIS_SPEED_STEPS_PER_RPM = 5  # steps/s per RPM for jog speed
SEQUENCE_AXIS_SPEED_RPM = 5.0  # enforced RPM for automated sequences
HORIZONTAL_AXIS_VERTICAL_LIMIT_MM = 10

PRIMARY_TOGGLE_STYLE = (
    "QPushButton {background-color: #1d4ed8; color: #f8fafc; font-weight: 600;"
    "border: none; border-radius: 8px; padding: 4px 8px;}"
    "QPushButton:checked {background-color: #22c55e; color: #0f172a;}"
)

PRIMARY_BUTTON_STYLE = (
    "QPushButton {background-color: #1d4ed8; color: #f8fafc; font-weight: 600;"
    "border: none; border-radius: 8px; padding: 4px 8px;}"
    "QPushButton:pressed {background-color: #1e40af;}"
)
COMMAND_ON_ACTIVE_STYLE = (
    "QPushButton {background-color: #22c55e; color: #0f172a; font-weight: 600;"
    "border: none; border-radius: 8px; padding: 4px 8px;}"
    "QPushButton:pressed {background-color: #16a34a;}"
)
COMMAND_OFF_ACTIVE_STYLE = (
    "QPushButton {background-color: #dc2626; color: #f8fafc; font-weight: 600;"
    "border: none; border-radius: 8px; padding: 4px 8px;}"
    "QPushButton:pressed {background-color: #b91c1c;}"
)
ROTARY_BUTTON_STYLE = (
    "QPushButton {background-color: #1d4ed8; color: #f8fafc; font-weight: 600;"
    "border: none; border-radius: 28px;}"
    "QPushButton:pressed {background-color: #1e40af;}"
)
ROTARY_BUTTON_ACTIVE_STYLE = (
    "QPushButton {background-color: #22c55e; color: #0f172a; font-weight: 700;"
    "border: none; border-radius: 28px;}"
    "QPushButton:pressed {background-color: #16a34a;}"
)

SPIN_STYLE = (
    "QSpinBox, QDoubleSpinBox {background-color: #0b1a3a; color: #f8fafc; font-weight: 600;"
    "border: 1px solid #1d4ed8; border-radius: 8px; padding: 6px 8px;}"
    "QSpinBox::up-button, QSpinBox::down-button,"
    "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {width: 0px; height: 0px; border: none;}"
)

_ui_log_callback: Optional[Callable[[str], None]] = None


def register_ui_logger(callback: Callable[[str], None]):
    global _ui_log_callback
    _ui_log_callback = callback


def emit_ui_log(message: str):
    if _ui_log_callback:
        try:
            _ui_log_callback(message)
        except Exception as exc:  # pragma: no cover
            print(f"[WARN] UI log callback failed: {exc}")


# --- Global safety and threading helpers (auto-injected) ---

_plc_lock = threading.RLock()


def safe_plc_call(op_name: str, func: Callable, *args, **kwargs):
    """Serialize PLC access and prevent hard crashes on I/O errors."""
    try:
        with _plc_lock:
            return func(*args, **kwargs)
    except Exception as exc:
        try:
            emit_ui_log(f"[PLC:{op_name}] error: {exc}")
        except Exception:
            # Last-resort logging if UI is not yet available
            print(f"[PLC:{op_name}] error: {exc}")


def _thread_excepthook(args):
    """Route unhandled thread exceptions to the UI log instead of only stderr."""
    try:
        thread_name = getattr(args, "thread", None)
        tname = getattr(thread_name, "name", "background")
        msg = f"[Thread:{tname}] unhandled exception: {args.exc_type.__name__}: {args.exc_value}"
    except Exception:
        msg = "[Thread] unhandled exception in background worker"
    try:
        emit_ui_log(msg)
    except Exception:
        print(msg)


# Install the thread excepthook if available (Python 3.8+)
if hasattr(threading, "excepthook"):
    threading.excepthook = _thread_excepthook  # type: ignore[attr-defined]


# Install a global sys.excepthook to keep the Qt event loop alive on errors.
def _global_excepthook(exc_type, exc_value, exc_traceback):
    try:
        emit_ui_log(f"[FATAL] Unhandled exception: {exc_type.__name__}: {exc_value}")
    except Exception:
        print(f"[FATAL] Unhandled exception: {exc_type.__name__}: {exc_value}")
    import traceback as _traceback
    _traceback.print_exception(exc_type, exc_value, exc_traceback)


sys.excepthook = _global_excepthook


class TaskManager:
    """Lightweight task orchestrator to serialize named background actions."""

    def __init__(self, logger: Callable[[str], None]):
        self._logger = logger
        self._lock = threading.Lock()
        self._active: Dict[str, threading.Thread] = {}

    def submit(self, name: str, func: Callable[[], None]) -> bool:
        with self._lock:
            if name in self._active:
                self._logger(f"[Task:{name}] already running")
                return False

            def runner():
                try:
                    func()
                except Exception as exc:
                    self._logger(f"[Task:{name}] error: {exc}")
                finally:
                    with self._lock:
                        self._active.pop(name, None)

            thread = threading.Thread(target=runner, daemon=True)
            self._active[name] = thread
            thread.start()
            return True


class MotionGate:
    """Global guard to serialize high-energy motion commands."""

    def __init__(self):
        self._state_lock = threading.Lock()
        self._owner: Optional[str] = None

    def try_claim(self, owner: str) -> bool:
        with self._state_lock:
            if self._owner is not None:
                return False
            self._owner = owner
            return True

    def release(self, owner: str):
        with self._state_lock:
            if self._owner == owner:
                self._owner = None

    def current_owner(self) -> Optional[str]:
        with self._state_lock:
            return self._owner


MOTION_GATE = MotionGate()


def wait_standstill(pump: Optional[SyringePump], timeout: float = 120.0, poll: float = 0.2) -> bool:
    """Return True when the drive reports standstill before the timeout."""
    if pump is None:
        return False
    start = time.time()
    while time.time() - start < timeout:
        try:
            status = pump.read_status()
        except Exception:
            status = None
        if status and status.get("standstill") == 1:
            return True
        time.sleep(poll)
    return False


def wait_pos_done(
    pump: Optional[SyringePump],
    timeout: float = 300.0,
    poll: float = 0.2,
    tol_steps: int = 200,
    stable_cycles: int = 3,
) -> bool:
    """Wait until standstill & pos_ok stay stable for multiple polls."""
    if pump is None:
        return False
    start = time.time()
    last_position: Optional[int] = None
    stable_count = 0

    while time.time() - start < timeout:
        try:
            status = pump.read_status()
        except Exception:
            status = None
        if status and status.get("standstill") == 1 and status.get("pos_ok") == 1:
            current = status.get("actual_position")
            if last_position is None:
                last_position = current
                stable_count = 1
            elif current is not None and last_position is not None:
                if abs(current - last_position) <= tol_steps:
                    stable_count += 1
                    if stable_count >= stable_cycles:
                        return True
                else:
                    stable_count = 0
                last_position = current
        time.sleep(poll)
    return False


def _crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if (crc & 1) else (crc >> 1)
    return bytes((crc & 0xFF, (crc >> 8) & 0xFF))


def _int_be4(value: int) -> bytes:
    return int(value).to_bytes(4, "big", signed=True)


def _read_actual_position_safe(pump: SyringePump) -> int:
    try:
        status = pump.read_status()
        if status and "actual_position" in status:
            return int(status["actual_position"])
    except Exception:
        pass
    try:
        position = pump.read_feedback()
        if isinstance(position, int):
            return position
    except Exception:
        pass
    return 0


def _read_volume_ml(pump: SyringePump) -> Optional[float]:
    """Best-effort volume reading modeled after control_guiV15 architecture."""
    try:
        status = pump.read_status()
    except Exception:
        status = None
    if isinstance(status, dict):
        for key in ("volume_ml", "volume"):
            value = status.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
        actual = status.get("actual_position")
        if actual is not None:
            try:
                return float(actual) / float(pump.steps_per_ml)
            except Exception:
                pass

    try:
        feedback = pump.read_feedback()
    except Exception:
        feedback = None

    if isinstance(feedback, dict):
        for key in ("volume_ml", "volume"):
            value = feedback.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
    elif isinstance(feedback, (int, float)):
        try:
            return float(feedback) / float(pump.steps_per_ml)
        except Exception:
            pass
    return None


def quick_stop_device(pump: Optional[SyringePump], stop_flag: int = 0x01) -> bool:
    """Send a MODBUS quick-stop frame to the specified pump."""
    if pump is None:
        return False
    address = pump.address
    position = _read_actual_position_safe(pump)
    frame = bytearray(
        [
            address,
            0x10,
            0xA7,
            0x9E,
            0x00,
            0x07,
            0x0E,
            0x07,
            0x00,
            stop_flag,
            0x03,
            0x01,
            0xF4,
            0x00,
            0x00,
            0x00,
            0x00,
        ]
    )
    frame.extend(_int_be4(position))
    frame.extend(_crc16_modbus(frame))
    try:
        with serial.Serial(
            pump.port,
            pump.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.3,
        ) as handle:
            try:
                from serial.rs485 import RS485Settings

                handle.rs485_mode = RS485Settings(delay_before_tx=0, delay_before_rx=0)
            except Exception:
                pass
            handle.reset_input_buffer()
            handle.reset_output_buffer()
            handle.write(frame)
            time.sleep(0.01)
            ack = handle.read(8)
            return (
                len(ack) == 8
                and ack[0] == address
                and ack[1] == 0x10
                and _crc16_modbus(ack[:-2]) == ack[-2:]
            )
    except Exception:
        return False

def probe_pump_response(
    pump: Optional[SyringePump],
    timeout: float = CONNECTION_PROBE_TIMEOUT,
    poll: float = 0.2,
) -> bool:
    if pump is None:
        return False
    deadline = time.time() + max(timeout, 0.1)
    while time.time() < deadline:
        try:
            status = pump.read_status()
            if status:
                return True
        except Exception:
            pass
        time.sleep(poll)
    return False


class SyringeAxisDriver:
    """Axis controller modeled after the proven control_guiV15 pump workflow."""

    def __init__(
        self,
        name: str,
        port: str,
        address: int,
        steps_per_ml: float,
        velocity_calib: float,
        home_enabled: bool = True,
        steps_per_mm: Optional[float] = None,
        min_mm: Optional[float] = None,
        max_mm: Optional[float] = None,
    ):
        self.name = name
        self.port = port
        self.address = address
        self.steps_per_ml = steps_per_ml
        self.velocity_calib = velocity_calib
        self.home_enabled = home_enabled
        self.steps_per_mm = steps_per_mm or AXIS_JOG_STEPS_PER_MM
        self.min_mm = min_mm
        self.max_mm = max_mm
        self._pump: Optional[SyringePump] = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._pump is not None

    def is_busy(self) -> Optional[bool]:
        """Return True if the drive reports busy, False if idle, None if unknown."""
        pump = self._pump
        if pump is None:
            return None
        try:
            status = pump.read_status()
        except Exception:
            return None
        if not status:
            return None
        return bool(status.get("busy"))

    def connect(self, verify: bool = True, timeout: float = CONNECTION_PROBE_TIMEOUT) -> bool:
        if SyringePump is None:
            raise RuntimeError("SyringePump class unavailable")
        pump = SyringePump(
            port=self.port,
            address=self.address,
            steps_per_ml=self.steps_per_ml,
            velocity_calib=self.velocity_calib,
        )
        if verify and not probe_pump_response(pump, timeout=timeout):
            emit_ui_log(f"[{self.name}] no response on {self.port} @ {self.address:#04x}")
            return False
        with self._lock:
            self._pump = pump
        emit_ui_log(f"[{self.name}] Connected on {self.port} @ {self.address:#04x}")
        return True

    def disconnect(self):
        with self._lock:
            self._pump = None
        emit_ui_log(f"[{self.name}] Disconnected")

    def _require_pump(self) -> SyringePump:
        pump = self._pump
        if pump is None:
            raise RuntimeError(f"{self.name} axis unavailable")
        return pump

    def _mm_to_steps(self, mm: float) -> int:
        return int(round(mm * self.steps_per_mm))

    def _mm_to_ml(self, mm: float) -> float:
        if self.steps_per_ml <= 0:
            raise ValueError("steps_per_ml must be > 0")
        return (mm * self.steps_per_mm) / self.steps_per_ml

    def _ml_to_mm(self, volume_ml: float) -> Optional[float]:
        if not self.steps_per_mm:
            return None
        steps = volume_ml * self.steps_per_ml
        return steps / self.steps_per_mm

    def _clamp_mm(self, target_mm: float) -> float:
        if self.min_mm is not None:
            target_mm = max(self.min_mm, target_mm)
        if self.max_mm is not None:
            target_mm = min(self.max_mm, target_mm)
        return target_mm

    def _read_position_mm(self) -> Optional[float]:
        pump = self._pump
        if pump is None:
            return None
        if not self.steps_per_mm:
            return None
        try:
            status = pump.read_status()
            if status and "actual_position" in status:
                return float(status["actual_position"]) / float(self.steps_per_mm)
        except Exception:
            pass
        try:
            feedback = pump.read_feedback()
            if isinstance(feedback, int):
                return float(feedback) / float(self.steps_per_mm)
        except Exception:
            pass
        volume = _read_volume_ml(pump)
        if volume is not None:
            return self._ml_to_mm(volume)
        return None

    def _flow_from_rpm(self, rpm: float) -> float:
        speed_steps_per_s = max(rpm, 0.1) * AXIS_SPEED_STEPS_PER_RPM
        flow_ml_min = (speed_steps_per_s * 60.0) / max(self.steps_per_ml, 1.0)
        return min(max(flow_ml_min, 0.5), 15.0)

    def jog(self, forward: bool, steps: int, speed_steps_per_s: float):
        if not self.steps_per_mm:
            raise ValueError("steps_per_mm must be configured for jog")
        distance_mm = steps / float(self.steps_per_mm)
        current_mm = self._read_position_mm()
        if current_mm is None:
            emit_ui_log(f"[{self.name}] Jog: no feedback; assuming 0 reference")
            current_mm = 0.0
        target_mm = current_mm + (distance_mm if forward else -distance_mm)
        rpm = speed_steps_per_s / max(AXIS_SPEED_STEPS_PER_RPM, 1e-3)
        self.move_to_mm(target_mm, rpm, context="jog")

    def home(self):
        if not self.home_enabled:
            raise RuntimeError(f"{self.name} homing disabled")
        pump = self._require_pump()
        pump.home()
        emit_ui_log(f"[{self.name}] Waiting for homing standstill")
        if not wait_standstill(pump, timeout=60, poll=0.2):
            raise RuntimeError(f"{self.name} homing did not reach standstill")
        emit_ui_log(f"[{self.name}] Homing complete")

    def quick_stop(self) -> bool:
        pump = self._pump
        if pump is None:
            return False
        return quick_stop_device(pump)

    def get_position_steps(self) -> Optional[int]:
        pump = self._pump
        if pump is None:
            return None
        try:
            status = pump.read_status()
            if status and "actual_position" in status:
                return int(status["actual_position"])
        except Exception:
            pass
        try:
            feedback = pump.read_feedback()
            if isinstance(feedback, int):
                return feedback
        except Exception:
            pass
        volume = _read_volume_ml(pump)
        if volume is not None:
            try:
                return int(volume * pump.steps_per_ml)
            except Exception:
                return None
        return None

    def get_position_mm(self) -> Optional[float]:
        return self._read_position_mm()

    def move_to_mm(self, target_mm: float, rpm: float, context: str = "move"):
        pump = self._require_pump()
        target_mm = self._clamp_mm(float(target_mm))
        target_ml = self._mm_to_ml(target_mm)
        emit_ui_log(f"[{self.name}] {context}: ensuring standstill")
        if not wait_standstill(pump, timeout=30, poll=0.2):
            raise RuntimeError(f"{self.name} axis busy (no standstill)")
        current_volume = _read_volume_ml(pump)
        current_mm = self._read_position_mm()
        delta_mm = None
        if current_mm is not None:
            delta_mm = target_mm - current_mm
            if abs(delta_mm) < 0.01:
                emit_ui_log(f"[{self.name}] {context}: already at target ({target_mm:.3f} mm)")
                return
        flow = self._flow_from_rpm(rpm)
        if current_volume is not None:
            delta_ml = target_ml - current_volume
            flow = flow if delta_ml >= 0 else -flow
        else:
            flow = flow if target_mm >= 0 else -flow
        if delta_mm is not None:
            emit_ui_log(
                f"[{self.name}] {context}: target {target_mm:.3f} mm "
                f"(Δ {delta_mm:+.3f} mm)"
            )
        else:
            emit_ui_log(f"[{self.name}] {context}: target {target_mm:.3f} mm (no feedback)")
        pump.move(target_ml, flow)
        emit_ui_log(f"[{self.name}] {context}: waiting for completion")
        if not wait_pos_done(pump, timeout=600, poll=0.2):
            raise RuntimeError(f"{self.name} move incomplete (no standstill/pos_ok)")
        emit_ui_log(f"[{self.name}] {context}: move complete")



class RelayToggleButton(QPushButton):
    def __init__(
        self,
        channel: int,
        label: str,
        toggle_callback: Callable[[int, bool], bool],
        on_color: str = "#f97316",
        off_color: str = "#3b82f6",
        size: int = 48,
    ):
        super().__init__(label)
        self.channel = channel
        self._callback = toggle_callback
        self.on_color = on_color
        self.off_color = off_color
        self._size = size
        self.setCheckable(True)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._apply_style(False)
        self.clicked.connect(self._toggle)

    def set_state(self, state: bool):
        self.blockSignals(True)
        self.setChecked(state)
        self._apply_style(state)
        self.blockSignals(False)

    def _apply_style(self, state: bool):
        color = self.on_color if state else self.off_color
        radius = max(4, int(self._size * 0.2))
        font_size = 11 if self._size <= 48 else 12
        self.setStyleSheet(
            f"border-radius: {radius}px; background-color: {color}; color: #f8fafc;"
            f"font-weight: 600; font-size: {font_size}px; border: none;"
        )

    def _toggle(self):
        desired = self.isChecked()
        ok = self._callback(self.channel, desired)
        if not ok:
            self.blockSignals(True)
            self.setChecked(not desired)
            self.blockSignals(False)
            desired = not desired
        self._apply_style(desired)


class RotaryValvePanel(QWidget):
    """Simple 6-port rotary valve control panel."""

    def __init__(
        self,
        valve: Optional[RotaryValve] = None,
        port_count: int = 6,
    ):
        super().__init__()
        self.valve = valve or RotaryValve()
        self.port_count = max(1, min(6, port_count))
        self._busy = threading.Lock()
        self._current_port: Optional[int] = None
        self._buttons: Dict[int, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel("Rotary Valve")
        header.setObjectName("panelTitle")
        layout.addWidget(header)

        self.status_label = QLabel("Active Port: --")
        self.status_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.status_label)

        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 4)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        self.setMinimumHeight(280)

        grid_size = 5
        for row in range(grid_size):
            grid.setRowStretch(row, 1)
        for col in range(grid_size):
            grid.setColumnStretch(col, 1)

        circle_positions = [
            (0, 2),  # top
            (1, 4),  # upper-right
            (3, 4),  # lower-right
            (4, 2),  # bottom
            (3, 0),  # lower-left
            (1, 0),  # upper-left
        ]

        for idx, port in enumerate(range(1, self.port_count + 1)):
            row, col = circle_positions[idx % len(circle_positions)]
            button = QPushButton(f"Port {port}")
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.NoFocus)
            button.setFixedSize(56, 56)
            button.setStyleSheet(ROTARY_BUTTON_STYLE)
            button.clicked.connect(lambda _, p=port: self._handle_port(p))
            grid.addWidget(button, row, col)
            self._buttons[port] = button

        layout.addLayout(grid)

    def _handle_port(self, port: int):
        if not (1 <= port <= self.port_count):
            return
        if not self._busy.acquire(blocking=False):
            emit_ui_log(f"[Rotary] Busy, ignoring port {port}")
            return
        self._set_status(f"Switching to Port {port}…")
        threading.Thread(target=self._run_switch, args=(port,), daemon=True).start()

    def _run_switch(self, port: int):
        ok = False
        try:
            ok = bool(self.valve.set_port(port))
            if ok:
                emit_ui_log(f"[Rotary] Port -> {port}")
            else:
                emit_ui_log(f"[Rotary] Port {port} not ACKed")
        except Exception as exc:
            emit_ui_log(f"[Rotary] Port {port} error: {exc}")
        finally:
            self._invoke_ui(lambda: self._apply_switch_result(port, ok))
            self._busy.release()

    def _apply_switch_result(self, port: int, success: bool):
        if success:
            self._current_port = port
            self._set_status(f"Active Port: {port}")
        else:
            status = f"Active Port: {self._current_port}" if self._current_port else "Active Port: --"
            self._set_status(status)
        self._update_button_styles()

    def _update_button_styles(self):
        for port, button in self._buttons.items():
            if self._current_port == port:
                button.setStyleSheet(ROTARY_BUTTON_ACTIVE_STYLE)
            else:
                button.setStyleSheet(ROTARY_BUTTON_STYLE)

    def _set_status(self, text: str):
        self.status_label.setText(text)

    def _invoke_ui(self, func: Callable[[], None]):
        QTimer.singleShot(0, func)


class StepperAxisControl(QWidget):
    def __init__(
        self,
        driver: SyringeAxisDriver,
        positive_label: str,
        negative_label: str,
        task_runner: TaskManager,
        extra_buttons: Optional[Sequence[str]] = None,
    ):
        super().__init__()
        self.driver = driver
        self.name = driver.name
        self._steps_per_mm = getattr(driver, "steps_per_mm", AXIS_JOG_STEPS_PER_MM) or AXIS_JOG_STEPS_PER_MM
        self._move_lock = threading.Lock()
        self._stop_flag = threading.Event()
        self._tasks = task_runner

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel(self.name)
        header.setObjectName("panelTitle")
        layout.addWidget(header)

        button_height = 28

        self.position_spin = QDoubleSpinBox()
        self.position_spin.setDecimals(3)
        min_mm = 0.0
        max_mm = 133.0
        if getattr(self.driver, "min_steps", None) is not None:
            min_mm = max(0.0, self.driver.min_steps / self._steps_per_mm)
        if getattr(self.driver, "max_steps", None) is not None:
            max_mm = max(min_mm + 0.001, self.driver.max_steps / self._steps_per_mm)
        self.position_spin.setRange(min_mm, max_mm)
        self.position_spin.setSingleStep(0.05)
        self.position_spin.setValue(min_mm)
        self.position_spin.setSuffix(" mm")
        self.position_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.position_spin.setStyleSheet(SPIN_STYLE)

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setDecimals(1)
        self.speed_spin.setRange(1.0, 15.0)  # RPM
        default_rpm = 5.0 if self.name in {"Vertical Axis", "Horizontal Axis"} else 10.0
        self.speed_spin.setValue(default_rpm)
        self.speed_spin.setSuffix(" RPM")
        self.speed_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.speed_spin.setStyleSheet(SPIN_STYLE)

        spin_row = QGridLayout()
        spin_row.setContentsMargins(0, 0, 0, 0)
        spin_row.setHorizontalSpacing(8)
        spin_row.setVerticalSpacing(2)
        spin_row.addWidget(QLabel("Position"), 0, 0)
        spin_row.addWidget(self.position_spin, 0, 1)
        spin_row.addWidget(QLabel("Speed"), 1, 0)
        spin_row.addWidget(self.speed_spin, 1, 1)
        layout.addLayout(spin_row)

        inline_home_axes = {"Vertical Axis", "Horizontal Axis"}
        home_inline = self.driver.home_enabled and self.name in inline_home_axes

        self.home_button = None
        if self.driver.home_enabled:
            self.home_button = QPushButton("Home")
            self.home_button.setCursor(Qt.PointingHandCursor)
            self.home_button.setFocusPolicy(Qt.NoFocus)
            self.home_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
            self.home_button.setFixedHeight(button_height)
            self.home_button.clicked.connect(self._home)

        jog_row = QHBoxLayout()
        jog_row.setContentsMargins(0, 0, 0, 0)
        jog_row.setSpacing(10)

        self.neg_button = None
        if not home_inline:
            self.neg_button = QPushButton(negative_label)
            self.neg_button.setCursor(Qt.PointingHandCursor)
            self.neg_button.setFocusPolicy(Qt.NoFocus)
            self.neg_button.setMinimumHeight(button_height)
            self.neg_button.setFixedHeight(button_height)
            self.neg_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
            self.neg_button.clicked.connect(lambda: self._jog(False))

        self.pos_button = QPushButton(positive_label)
        self.pos_button.setCursor(Qt.PointingHandCursor)
        self.pos_button.setFocusPolicy(Qt.NoFocus)
        self.pos_button.setMinimumHeight(button_height)
        self.pos_button.setFixedHeight(button_height)
        self.pos_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.pos_button.clicked.connect(self._move_to_position)

        if home_inline and self.home_button is not None:
            jog_row.addWidget(self.home_button)
        elif self.neg_button is not None:
            jog_row.addWidget(self.neg_button)

        jog_row.addWidget(self.pos_button)
        layout.addLayout(jog_row)

        if self.home_button is not None and not home_inline:
            layout.addWidget(self.home_button)

        self._extra_buttons: List[QPushButton] = []

        if extra_buttons:
            extra_row = QHBoxLayout()
            extra_row.setContentsMargins(0, 0, 0, 0)
            extra_row.setSpacing(8)
            compact_buttons = len(extra_buttons) > 2
            for label in extra_buttons:
                btn = QPushButton(str(label))
                btn.setCursor(Qt.PointingHandCursor)
                btn.setFocusPolicy(Qt.NoFocus)
                btn.setMinimumHeight(button_height)
                btn.setFixedHeight(button_height)
                if compact_buttons:
                    btn.setMaximumWidth(90)
                    btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    btn.setStyleSheet(PRIMARY_BUTTON_STYLE + " QPushButton {padding: 2px 6px; font-size: 12px;}")
                else:
                    btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
                btn.clicked.connect(lambda _, text=label: self._handle_extra_button(text))
                extra_row.addWidget(btn)
                self._extra_buttons.append(btn)
            layout.addLayout(extra_row)

        self._control_widgets: List[QWidget] = [
            self.position_spin,
            self.speed_spin,
            self.pos_button,
        ]
        if self.neg_button:
            self._control_widgets.append(self.neg_button)
        if self.home_button:
            self._control_widgets.append(self.home_button)
        if self._extra_buttons:
            self._control_widgets.extend(self._extra_buttons)

        self._warn_default = "Axis unavailable (Initialize to connect)"
        self._warn_label = QLabel(self._warn_default)
        self._warn_label.setStyleSheet("color: #f43f5e; font-style: italic;")
        layout.addWidget(self._warn_label)

        self._safety_lock = False
        self._safety_message = ""
        self._pre_move_check: Optional[Callable[[], bool]] = None
        self._motion_callbacks: List[Callable[[], None]] = []

        self._last_position_mm: Optional[float] = None

        self.refresh_ready_state()

    def _jog(self, forward: bool):
        if not self.driver.ready:
            emit_ui_log(f"IGNORED jog on {self.name}: axis unavailable")
            return
        if not self._check_pre_move():
            return
        self._stop_flag.clear()
        mm_distance = self.position_spin.value()
        rpm = self.speed_spin.value()
        threading.Thread(
            target=self._run_steps, args=(forward, mm_distance, rpm), daemon=True
        ).start()

    def _move_to_position(self):
        if not self.driver.ready:
            emit_ui_log(f"IGNORED move on {self.name}: axis unavailable")
            return
        if not self._check_pre_move():
            return

        target_mm = self.position_spin.value()
        rpm = self.speed_spin.value()

        threading.Thread(
            target=self._run_position_move,
            args=(target_mm, rpm),
            daemon=True,
        ).start()

    def _run_steps(self, forward: bool, mm_distance: float, rpm: float):
        if not self._move_lock.acquire(blocking=False):
            return
        try:
            if self._stop_flag.is_set():
                return
            steps = int(round(mm_distance * self._steps_per_mm))
            if steps <= 0:
                raise ValueError("Jog distance must be > 0 mm")
            steps_per_sec = rpm * AXIS_SPEED_STEPS_PER_RPM
            direction = '+' if forward else '-'
            emit_ui_log(
                f"{self.name} jog {direction}{mm_distance:.3f} mm (~{steps} steps) "
                f"@ {rpm:.1f} RPM"
            )
            self.driver.jog(forward, steps, steps_per_sec)
            delta_mm = mm_distance if forward else -mm_distance
            self._update_cached_position(delta_mm=delta_mm, fallback_read=True)
            self._emit_motion_callbacks()
        except Exception as exc:
            emit_ui_log(f"[{self.name}] jog error: {exc}")
        finally:
            self._move_lock.release()

    def _run_position_move(self, target_mm: float, rpm: float):
        if not self._move_lock.acquire(blocking=False):
            emit_ui_log(f"[{self.name}] move skipped: another command in progress")
            return
        try:
            emit_ui_log(f"[{self.name}] Move -> {target_mm:.3f} mm request")
            self.driver.move_to_mm(target_mm, rpm, context="position")
            self._update_cached_position(target_mm=target_mm)
            self._emit_motion_callbacks()
        except Exception as exc:
            emit_ui_log(f"[{self.name}] move error: {exc}")
        finally:
            self._move_lock.release()

    def _home(self):
        if not self.driver.ready:
            emit_ui_log(f"IGNORED home on {self.name}: axis unavailable")
            return
        if not self._check_pre_move():
            return

        def _run_home():
            emit_ui_log(f"Homing {self.name}")
            try:
                self.driver.home()
                emit_ui_log(f"{self.name} homed")
                self._update_cached_position(target_mm=self.position_spin.minimum())
                self._emit_motion_callbacks()
            except Exception as exc:
                emit_ui_log(f"[{self.name}] home error: {exc}")

        threading.Thread(target=_run_home, daemon=True).start()

    def force_stop(self, quiet: bool = False):
        self._stop_flag.set()
        try:
            ok = self.driver.quick_stop()
            if not quiet:
                emit_ui_log(f"[{self.name}] Quick stop {'ACK' if ok else 'no ACK'}")
        except Exception as exc:
            if not quiet:
                emit_ui_log(f"[{self.name}] quick stop error: {exc}")
        finally:
            self._stop_flag.clear()

    def home_blocking(self):
        if not self.driver.ready:
            raise RuntimeError(f"{self.name} unavailable")
        self._check_pre_move(raise_on_block=True)
        self.driver.home()
        self._update_cached_position(target_mm=self.position_spin.minimum())
        self._emit_motion_callbacks()

    def refresh_ready_state(self):
        hw_ready = self.driver.ready
        enabled = hw_ready and not self._safety_lock
        for widget in self._control_widgets:
            widget.setEnabled(enabled)
        warning = None
        if not hw_ready:
            warning = self._warn_default
        elif self._safety_lock:
            warning = self._safety_message or "Axis locked by safety interlock"
        if warning:
            self._warn_label.setText(warning)
            self._warn_label.setVisible(True)
        else:
            self._warn_label.setVisible(False)
        if not hw_ready:
            self._last_position_mm = None

    def _handle_extra_button(self, label: str):
        if not self.driver.ready:
            emit_ui_log(f"IGNORED extra button '{label}' on {self.name}: axis unavailable")
            return
        if not self._check_pre_move():
            return

        axis_targets = AXIS_PRESET_POSITIONS.get(self.name)
        if not axis_targets:
            emit_ui_log(f"[{self.name}] extra button '{label}' pressed (no presets configured)")
            return

        normalized = label.strip().lower()
        target_info = axis_targets.get(normalized)
        if target_info is None:
            emit_ui_log(f"[{self.name}] extra button '{label}' pressed (no action assigned)")
            return

        display_label, target_mm = target_info
        current_mm = self.driver.get_position_mm()
        if current_mm is not None:
            if abs(target_mm - current_mm) < 0.01:
                emit_ui_log(f"[{self.name}] already near {display_label} ({target_mm:.3f} mm)")
                return
        else:
            emit_ui_log(f"[{self.name}] {display_label}: no position feedback, moving anyway")

        rpm = self.speed_spin.value()
        emit_ui_log(f"[{self.name}] {display_label} -> {target_mm:.3f} mm command requested")
        threading.Thread(
            target=self._run_position_move,
            args=(target_mm, rpm),
            daemon=True,
        ).start()

    def set_safety_lock(self, active: bool, message: str = ""):
        if active == self._safety_lock and (not active or message == self._safety_message):
            return
        self._safety_lock = active
        self._safety_message = message
        self.refresh_ready_state()

    def set_pre_move_check(self, callback: Optional[Callable[[], bool]]):
        self._pre_move_check = callback

    def add_motion_callback(self, callback: Callable[[], None]):
        if callback not in self._motion_callbacks:
            self._motion_callbacks.append(callback)

    def get_cached_position_mm(self) -> Optional[float]:
        return self._last_position_mm

    def set_cached_position_mm(self, value: Optional[float]):
        self._last_position_mm = value

    def _update_cached_position(
        self,
        *,
        target_mm: Optional[float] = None,
        delta_mm: Optional[float] = None,
        fallback_read: bool = False,
    ):
        if target_mm is not None:
            self._last_position_mm = target_mm
            return
        if delta_mm is not None and self._last_position_mm is not None:
            self._last_position_mm += delta_mm
            return
        if fallback_read:
            self._last_position_mm = self._read_position_mm()

    def _read_position_mm(self) -> Optional[float]:
        try:
            steps = self.driver.get_position_steps()
        except Exception:
            return None
        if steps is None or not self._steps_per_mm:
            return None
        return steps / self._steps_per_mm

    def _emit_motion_callbacks(self):
        if not self._motion_callbacks:
            return
        callbacks = list(self._motion_callbacks)

        def _dispatch():
            for cb in callbacks:
                try:
                    cb()
                except Exception as exc:
                    emit_ui_log(f"[{self.name}] motion callback error: {exc}")

        QTimer.singleShot(0, _dispatch)

    def _check_pre_move(self, raise_on_block: bool = False) -> bool:
        if not self._pre_move_check:
            return True
        try:
            allowed = bool(self._pre_move_check())
        except Exception as exc:
            if raise_on_block:
                raise
            emit_ui_log(f"[{self.name}] safety interlock blocked motion: {exc}")
            return False
        if not allowed:
            message = self._safety_message or "Axis locked by safety interlock"
            if raise_on_block:
                raise RuntimeError(message)
            emit_ui_log(f"[{self.name}] {message}")
            return False
        return True


class _RelayValveAdapter:
    """Maps relay channels to open/close valves for the MAF sequence."""

    def __init__(
        self,
        relays_getter: Callable[[], Optional[RelayBoard06]],
        channel: int,
        label: str,
    ):
        self._relays_getter = relays_getter
        self.channel = channel
        self.label = label

    def _require_relays(self) -> RelayBoard06:
        relays = self._relays_getter()
        if not relays:
            raise RuntimeError(f"{self.label}: relay board unavailable")
        return relays

    def open(self):
        relays = self._require_relays()
        relays.on(self.channel)
        emit_ui_log(f"[MAF] {self.label} -> OPEN (relay {self.channel} ON)")

    def close(self):
        relays = self._require_relays()
        relays.off(self.channel)
        emit_ui_log(f"[MAF] {self.label} -> CLOSED (relay {self.channel} OFF)")


class _RelaySequenceAdapter:
    """Relay shim so sequences reuse MainWindow's ACK/error handling."""

    def __init__(self, setter: Callable[[int, bool], bool]):
        self._setter = setter

    def _set(self, channel: int, state: bool) -> bool:
        return self._setter(int(channel), state)

    def on(self, channel: int) -> bool:
        return self._set(channel, True)

    def off(self, channel: int) -> bool:
        return self._set(channel, False)


class _SyringeSequenceAdapter:
    """Provides the minimal syringe API expected by automated sequences."""

    def __init__(self, panel_getter: Callable[[], Optional["SyringeControlPanel"]]):
        self._panel_getter = panel_getter

    def _require_pump(self) -> SyringePump:
        panel = self._panel_getter()
        pump = getattr(panel, "_pump", None) if panel else None
        if pump is None:
            raise RuntimeError("Syringe pump unavailable for sequence")
        return pump

    def goto_absolute(self, target_ml: float, flow_ml_min: float):
        pump = self._require_pump()
        emit_ui_log(f"[Sequence1] Syringe ensure standstill before move")
        if not wait_standstill(pump, timeout=30, poll=0.2):
            raise RuntimeError("Syringe not at standstill")
        current_ml = _read_volume_ml(pump)
        if current_ml is not None:
            delta = float(target_ml) - current_ml
            if abs(delta) < 0.01:
                emit_ui_log(f"[Sequence1] Syringe already at {target_ml:.3f} mL")
                return
        flow = max(abs(float(flow_ml_min)), 0.1)
        signed_flow = flow if (current_ml is None or float(target_ml) >= current_ml) else -flow
        emit_ui_log(f"[Sequence1] Syringe -> {target_ml:.3f} mL @ {abs(signed_flow):.2f} mL/min")
        pump.move(float(target_ml), signed_flow)
        if not wait_pos_done(pump, timeout=600, poll=0.2):
            raise RuntimeError("Syringe move did not settle")
        emit_ui_log(f"[Sequence1] Syringe reached {target_ml:.3f} mL")


class SyringeControlPanel(QWidget):
    """Minimal syringe pump control with Home / Move actions."""

    def __init__(
        self,
        port: str = SYRINGE_PORT,
        address: int = SYRINGE_PUMP_ADDRESS,
        task_runner: Optional[TaskManager] = None,
    ):
        super().__init__()
        self.port = port
        self.address = address
        self._busy_flag = threading.Event()
        self._pump: Optional[SyringePump] = None
        self._tasks = task_runner

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel("Syringe Control")
        header.setObjectName("panelTitle")
        layout.addWidget(header)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.status_label)

        form = QGridLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)
        self.volume_spin = QDoubleSpinBox()
        self.volume_spin.setDecimals(2)
        self.volume_spin.setRange(0.00, 2.50)
        self.volume_spin.setValue(0.00)
        self.volume_spin.setSuffix("mL")
        self.volume_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.volume_spin.setStyleSheet(SPIN_STYLE)
        self.flow_spin = QDoubleSpinBox()
        self.flow_spin.setDecimals(2)
        self.flow_spin.setRange(0.10, 2.00)
        self.flow_spin.setValue(1.00)
        self.flow_spin.setSuffix(" mL/min")
        self.flow_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.flow_spin.setStyleSheet(SPIN_STYLE)
        form.addWidget(QLabel("Volume"), 0, 0)
        form.addWidget(self.volume_spin, 0, 1)
        form.addWidget(QLabel("Flow Rate"), 1, 0)
        form.addWidget(self.flow_spin, 1, 1)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(10)
        self.move_button = QPushButton("Move")
        self.home_button = QPushButton("Home")
        for btn in (self.move_button, self.home_button):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
            btn.setFixedHeight(28)
            button_row.addWidget(btn)
        layout.addLayout(button_row)

        self.move_button.clicked.connect(self._start_move)
        self.home_button.clicked.connect(self._start_home)

        self._apply_ready_state()

    def _start_move(self):
        volume = self.volume_spin.value()
        flow = self.flow_spin.value()
        self._run_async("Move", lambda: self._move(volume, flow))

    def _start_home(self):
        self._run_async("Home", self._home)

    def _run_async(self, name: str, func: Callable[[], None]):
        if self._busy_flag.is_set():
            emit_ui_log(f"Syringe {name} ignored: busy")
            return
        if self._pump is None:
            emit_ui_log(f"Syringe {name} ignored: unavailable")
            return

        def worker():
            self._busy_flag.set()
            self._set_status_safe(f"{name} running...")
            try:
                func()
                self._set_status_safe(f"{name} complete")
                emit_ui_log(f"Syringe {name} finished")
            except Exception as exc:
                self._set_status_safe(f"{name} failed")
                emit_ui_log(f"[Syringe] {name} error: {exc}")
            finally:
                self._busy_flag.clear()
                self._invoke_ui(lambda: QTimer.singleShot(1500, lambda: self._set_status("Status: Idle")))

        if self._tasks and not self._tasks.submit(f"Syringe-{name}", worker):
            return
        if not self._tasks:
            threading.Thread(target=worker, daemon=True).start()

    def _invoke_ui(self, func: Callable[[], None]):
        QTimer.singleShot(0, func)

    def _set_status(self, text: str):
        self.status_label.setText(text)

    def _set_status_safe(self, text: str):
        self._invoke_ui(lambda: self._set_status(text))

    def _move(self, volume: float, flow: float):
        self._perform_move(volume, flow)

    def _home(self):
        self._perform_home(update_status=True)

    def force_stop(self):
        if self._busy_flag.is_set():
            self._set_status_safe("Status: Interrupted")
        self._busy_flag.clear()
        ok = quick_stop_device(self._pump)
        emit_ui_log(f"[Syringe] Quick stop {'ACK' if ok else 'no ACK'}")

    @property
    def ready(self) -> bool:
        return self._pump is not None

    def home_blocking(self):
        self._perform_home(update_status=False)

    def _require_pump(self) -> SyringePump:
        if not self._pump:
            raise RuntimeError("Syringe pump unavailable")
        return self._pump

    def connect(
        self,
        verify: bool = True,
        timeout: float = CONNECTION_PROBE_TIMEOUT,
    ) -> bool:
        if SyringePump is None:
            raise RuntimeError("SyringePump class unavailable")
        pump = SyringePump(
            port=self.port,
            address=self.address,
            steps_per_ml=SYRINGE_STEPS_PER_ML,
            velocity_calib=SYRINGE_VELOCITY_CALIB,
        )
        if verify and not probe_pump_response(pump, timeout=timeout):
            emit_ui_log(f"[Syringe] no response on {self.port} @ {self.address:#04x}")
            self._pump = None
            self._apply_ready_state_safe()
            return False
        self._pump = pump
        self._apply_ready_state_safe()
        emit_ui_log(f"Syringe control ready on {self.port} @ {self.address:#04x}")
        return True

    def disconnect(self):
        if self._pump is not None:
            self._pump = None
            self._apply_ready_state_safe()
            emit_ui_log("Syringe control disconnected")

    def _apply_ready_state(self):
        enabled = self._pump is not None
        for widget in (self.move_button, self.home_button):
            widget.setEnabled(enabled)
        if enabled:
            if not self._busy_flag.is_set():
                self.status_label.setText("Status: Idle")
        else:
            self.status_label.setText("Status: Offline" if self._pump else "Status: Unavailable")

    def _apply_ready_state_safe(self):
        self._invoke_ui(self._apply_ready_state)

    def _perform_move(self, volume: float, flow: float):
        pump = self._require_pump()
        target_ml = float(volume)
        flow = max(abs(float(flow)), 0.1)
        self._set_status_safe("Ensuring standstill...")
        emit_ui_log("[Syringe] Ensuring standstill before move")
        if not wait_standstill(pump, timeout=30, poll=0.2):
            raise RuntimeError("Syringe not at standstill")
        current_ml = _read_volume_ml(pump)
        if current_ml is not None:
            delta = target_ml - current_ml
            if abs(delta) < 0.01:
                emit_ui_log(f"[Syringe] Already at {target_ml:.3f} mL (Δ {delta:+.4f} mL)")
                self._set_status_safe("Status: Idle")
                return
            flow = flow if delta >= 0 else -flow
        else:
            flow = flow if target_ml >= 0 else -flow
        emit_ui_log(f"[Syringe] Move to {target_ml:.3f} mL @ {abs(flow):.2f} mL/min")
        self._set_status_safe("Moving...")
        pump.move(target_ml, flow)
        emit_ui_log("[Syringe] Waiting for move to finish")
        self._set_status_safe("Waiting for completion...")
        if not wait_pos_done(pump, timeout=600, poll=0.2):
            raise RuntimeError("Syringe move did not settle")
        emit_ui_log("[Syringe] Move complete")

    def _perform_home(self, update_status: bool):
        pump = self._require_pump()
        if update_status:
            self._set_status_safe("Homing...")
        emit_ui_log("[Syringe] Homing sequence start")
        pump.home()
        emit_ui_log("[Syringe] Waiting for homing standstill")
        if not wait_standstill(pump, timeout=100, poll=0.2):
            raise RuntimeError("Syringe homing did not reach standstill")
        emit_ui_log("[Syringe] Homing complete")
        if update_status:
            self._set_status_safe("Home reached")


class MainWindow(QWidget):
    log_signal = pyqtSignal(str)
    init_state_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Integrated Device Console")
        self.setMinimumSize(720, 520)
        self.resize(760, 600)

        plc.init("RPIPLC_V6", "RPIPLC_38AR")

        self.log_view: Optional[QPlainTextEdit] = None
        self.rotary_panel: Optional[RotaryValvePanel] = None
        self.axis_controls: List[StepperAxisControl] = []
        self._horizontal_lock_active = False
        self._horizontal_lock_message = ""
        self._horizontal_lock_timer = QTimer(self)
        self._horizontal_lock_timer.setInterval(1000)
        self._horizontal_lock_timer.timeout.connect(self._horizontal_lock_watchdog)
        self._horizontal_lock_timer.start()
       
        self.syringe_panel: Optional[SyringeControlPanel] = None
        self._init_running = False
        self._init_abort = threading.Event()
        self._stop_event = threading.Event()
        self._sequence1_running = False
        self._sequence2_running = False
        self._syringe_sequence_adapter: Optional[_SyringeSequenceAdapter] = None

        register_ui_logger(self._append_log)
        self.log_signal.connect(self._write_log_entry)
        self.init_state_signal.connect(self._apply_init_state)
        self._tasks = TaskManager(self._append_log)

        self.relays: Optional[RelayBoard06] = None
        self.relay_states: Dict[int, bool] = {channel: False for channel, _ in RELAY_OUTPUTS}
        self.relay_buttons: Dict[int, RelayToggleButton] = {}
        self._relay_sequence_adapter = _RelaySequenceAdapter(
            lambda channel, state: self._set_relay_state(channel, state)
        )

        self.setStyleSheet(
            """
            QWidget {
                background-color: #0f172a;
                color: #e2e8f0;
                font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                font-size: 13px;
            }
            QLabel#panelTitle {
                font-size: 14px;
                font-weight: 600;
                color: #f8fafc;
                margin: 0;
                padding: 0 0 6px 0;
            }
            QFrame#panel {
                background-color: #1e293b;
                border-radius: 12px;
            }
            QLineEdit {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 4px 10px;
                color: #f8fafc;
                font-weight: 500;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
            }
            QPlainTextEdit {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 12px;
                padding: 10px;
                font-family: 'JetBrains Mono', 'SFMono', monospace;
                font-size: 12px;
            }
            """
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 12)
        main_layout.setSpacing(8)

        content = QHBoxLayout()
        content.setSpacing(8)
        main_layout.addLayout(content)

        # Left panel
        left_panel, left_layout = self._build_panel()
        self.rotary_panel = RotaryValvePanel()
        left_layout.addWidget(self.rotary_panel)
        left_layout.addStretch()
        left_layout.addSpacing(6)
        relays_label = QLabel("Relays")
        relays_label.setObjectName("panelTitle")
        left_layout.addWidget(relays_label)
        relay_panel, relay_controls = self._build_valve_section(None, RELAY_OUTPUTS, size=58)
        left_layout.addWidget(relay_panel)
        left_layout.addSpacing(6)
        left_layout.addLayout(relay_controls)
        content.addWidget(left_panel, 1)

        # Middle panel (Stepper axes)
        motion_panel, motion_layout = self._build_panel()
        self._axis_drivers: List[SyringeAxisDriver] = []
        for axis in STEPPER_AXES:
            driver = SyringeAxisDriver(
                name=axis["name"],
                port=axis.get("port", SYRINGE_PORT),
                address=axis["address"],
                steps_per_ml=axis["steps_per_ml"],
                velocity_calib=axis["velocity_calib"],
                home_enabled=axis.get("home_enabled", True),
                steps_per_mm=axis.get("steps_per_mm"),
                min_mm=axis.get("min_mm"),
                max_mm=axis.get("max_mm"),
            )
            self._axis_drivers.append(driver)
            widget = StepperAxisControl(
                driver,
                axis["positive_label"],
                axis["negative_label"],
                self._tasks,
                extra_buttons=axis.get("extra_buttons"),
            )
            self.axis_controls.append(widget)
            motion_layout.addWidget(widget)
        motion_layout.addStretch()
        self.syringe_panel = SyringeControlPanel(task_runner=self._tasks)
        self._syringe_sequence_adapter = _SyringeSequenceAdapter(lambda: self.syringe_panel)
        motion_layout.addWidget(self.syringe_panel)
        content.addWidget(motion_panel, 1)
        self._configure_horizontal_axis_interlock()
        self._valve1_adapter = _RelayValveAdapter(lambda: self.relays, 1, "Valve 1")
        self._valve2_adapter = _RelayValveAdapter(lambda: self.relays, 2, "Valve 2")

        # Right panel (Flow, Temp, Log, Stop)
        right_panel, right_layout = self._build_panel()
      
        sequence_row = QHBoxLayout()
        sequence_row.setContentsMargins(0, 0, 0, 0)
        sequence_row.setSpacing(8)
        self.sequence1_button = QPushButton("Sequence 1")
        self.sequence2_button = QPushButton("Sequence 2")
        for button in (self.sequence1_button, self.sequence2_button):
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.NoFocus)
            button.setStyleSheet(PRIMARY_BUTTON_STYLE)
            button.setFixedHeight(32)
            sequence_row.addWidget(button)
        if self.sequence1_button:
            self.sequence1_button.clicked.connect(lambda _=False: self._start_sequence1())
        if self.sequence2_button:
            self.sequence2_button.clicked.connect(self._start_sequence2)

        right_layout.addLayout(sequence_row)

        log_title = QLabel("Event Log")
        log_title.setObjectName("panelTitle")
        right_layout.addWidget(log_title)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(400)
        right_layout.addWidget(self.log_view, 1)

        right_layout.addSpacing(8)

        self.verify_checkbox = QCheckBox("Verify devices before homing")
        self.verify_checkbox.setChecked(DEFAULT_VERIFY_CONNECTIONS)
        self.verify_checkbox.setStyleSheet("font-weight: 600;")
        right_layout.addWidget(self.verify_checkbox)
        right_layout.addSpacing(4)

        self.stop_button = QPushButton("STOP ALL")
        self.stop_button.setCursor(Qt.PointingHandCursor)
        self.stop_button.setFocusPolicy(Qt.NoFocus)
        self.stop_button.setStyleSheet(
            "QPushButton {background-color: #dc2626; color: #f8fafc; font-weight: 700;"
            "border: none; border-radius: 10px; padding: 10px 20px;}"
            "QPushButton:pressed {background-color: #b91c1c;}"
        )
        self.stop_button.setFixedHeight(38)
        self.stop_button.clicked.connect(self._emergency_stop)

        self.init_button = QPushButton("Initialize")
        self.init_button.setCursor(Qt.PointingHandCursor)
        self.init_button.setFocusPolicy(Qt.NoFocus)
        self.init_button.setStyleSheet(
            "QPushButton {background-color: #22c55e; color: #0f172a; font-weight: 700;"
            "border: none; border-radius: 10px; padding: 10px 20px;}"
            "QPushButton:pressed {background-color: #16a34a;}"
        )
        self.init_button.setFixedHeight(38)
        init_min_width = self.init_button.fontMetrics().horizontalAdvance("Initializing...") + 34
        self.init_button.setMinimumWidth(init_min_width)
        self.init_button.clicked.connect(self._handle_initialize)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        button_row.addWidget(self.init_button)
        button_row.addWidget(self.stop_button)
        right_layout.addLayout(button_row)

        content.addWidget(right_panel, 1)

    def _build_panel(self):
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(9)
        return frame, layout

    def _safe_stop(self, label: str, action: Callable[[], None]):
        try:
            action()
        except Exception as exc:
            emit_ui_log(f"[STOP] {label} error: {exc}")

    def _invoke_ui(self, func: Callable[[], None]):
        QTimer.singleShot(0, func)

    def _emergency_stop(self):
        emit_ui_log("EMERGENCY STOP triggered")
        self._init_abort.set()
        self._stop_event.set()
        if self.syringe_panel:
            self._safe_stop("Syringe", self.syringe_panel.force_stop)
        for axis in self.axis_controls:
            self._safe_stop(axis.name, lambda ax=axis: ax.force_stop(quiet=True))
        self._safe_stop("Relays", lambda: self._relays_all_off(auto=True))
        if self._init_running:
            self._init_running = False
            self._set_init_enabled(True)
        self._append_log("Emergency stop activated")

    def _handle_initialize(self):
        if self._init_running:
            emit_ui_log("Initialize already running")
            return
        self._stop_event.clear()
        self._init_running = True
        self._set_init_enabled(False)
        self._init_abort.clear()
        if not self._tasks.submit("Initialize", self._initialize_sequence):
            self._init_running = False
            self._set_init_enabled(True)

    def _handle_sequence_placeholder(self, label: str):
        emit_ui_log(f"[{label}] sequence controls are disabled in this build")

    def _update_sequence_buttons(self):
        busy = self._sequence1_running or self._sequence2_running
        if self.sequence1_button:
            self.sequence1_button.setEnabled(not busy)
        if self.sequence2_button:
            self.sequence2_button.setEnabled(not busy)


    def _start_sequence1(self):
        if self._sequence1_running:
            emit_ui_log("[Sequence1] already running")
            return
        emit_ui_log("Sequence 1 begin")
        try:
            self._ensure_sequence1_ready()
        except Exception as exc:
            emit_ui_log(f"[Sequence1] unavailable: {exc}")
            return
        if not self._tasks.submit("Sequence1", self._run_sequence1):
            emit_ui_log("[Sequence1] worker already active")
            return
        emit_ui_log("[Sequence1] Starting background worker")
        self._stop_event.clear()
        self._sequence1_running = True
        self._update_sequence_buttons()

    def _run_sequence1(self):
        try:
            syringe_adapter = self._syringe_sequence_adapter
            relay_adapter = self._relay_sequence_adapter
            if syringe_adapter is None:
                raise RuntimeError("Syringe adapter unavailable")
            if relay_adapter is None:
                raise RuntimeError("Relay adapter unavailable")
            run_maf_sampling_sequence(
                stop_flag=lambda: self._stop_event.is_set(),
                log=emit_ui_log,
                relays=relay_adapter,
                syringe=syringe_adapter,
                move_horizontal_to_filtering=lambda: self._sequence_move_axis(
                    "Horizontal Axis", "filtering"
                ),
                move_vertical_close_plate=lambda: self._sequence_move_axis(
                    "Vertical Axis", "close"
                ),
                select_rotary_port=self._sequence_select_rotary_port,
                init=self._sequence_full_init,
            )
            emit_ui_log("Sequence 1 complete")
        except Exception as exc:
            emit_ui_log(f"[Sequence1] error: {exc}")
        finally:
            self._stop_event.clear()
            self._sequence1_running = False
            self._invoke_ui(self._update_sequence_buttons)
    
    def _start_sequence2(self):
        if self._sequence2_running:
            emit_ui_log("[Sequence2] already running")
            return
        if self._sequence1_running:
            emit_ui_log("[Sequence2] cannot start: Sequence 1 is running")
            return

        emit_ui_log("Sequence 2 begin")
        try:
            # Same prereqs as Sequence 1 are fine
            self._ensure_sequence1_ready()
        except Exception as exc:
            emit_ui_log(f"[Sequence2] unavailable: {exc}")
            return

        if not self._tasks.submit("Sequence2", self._run_sequence2):
            emit_ui_log("[Sequence2] worker already active")
            return

        emit_ui_log("[Sequence2] Starting background worker")
        self._stop_event.clear()
        self._sequence2_running = True
        self._update_sequence_buttons()

    def _run_sequence2(self):
        try:
            syringe_adapter = self._syringe_sequence_adapter
            relay_adapter = self._relay_sequence_adapter
            if syringe_adapter is None:
                raise RuntimeError("Syringe adapter unavailable")
            if relay_adapter is None:
                raise RuntimeError("Relay adapter unavailable")

            run_sequence2(
                stop_flag=lambda: self._stop_event.is_set(),
                log=emit_ui_log,
                relays=relay_adapter,
                syringe=syringe_adapter,
                move_horizontal_to_filtering=lambda: self._sequence_move_axis(
                    "Horizontal Axis", "filtering"
                ),
                # Home = back to 0 mm / "filter in"
                move_horizontal_home=lambda: self._sequence_move_axis(
                    "Horizontal Axis", "filter in"
                ),
                move_vertical_close_plate=lambda: self._sequence_move_axis(
                    "Vertical Axis", "close"
                ),
                move_vertical_open_plate=lambda: self._sequence_move_axis(
                    "Vertical Axis", "open"
                ),
                select_rotary_port=self._sequence_select_rotary_port,
            )
            emit_ui_log("Sequence 2 complete")
        except Exception as exc:
            emit_ui_log(f"[Sequence2] error: {exc}")
        finally:
            self._stop_event.clear()
            self._sequence2_running = False
            self._invoke_ui(self._update_sequence_buttons)

    def _sequence_full_init(self):
        emit_ui_log("[Sequence1] Full initialization start")
        self._sequence1_init()
        if self.relays:
            emit_ui_log("[Sequence1] Ensuring all relays are OFF")
            self._relays_all_off(auto=True)
        axis_order = ("Vertical Axis", "Horizontal Axis")
        for axis_name in axis_order:
            ctrl = self._get_axis_control(axis_name)
            if ctrl is None or not ctrl.driver.ready:
                raise RuntimeError(f"{axis_name} unavailable for homing")
            emit_ui_log(f"[Sequence1] Homing {axis_name}")
            try:
                busy = ctrl.driver.is_busy()
            except Exception:
                busy = None
            if busy:
                emit_ui_log(f"[Sequence1] {axis_name} busy before home -> quick stop")
                ctrl.force_stop(quiet=True)
                time.sleep(0.1)
            ctrl.home_blocking()
            emit_ui_log(f"[Sequence1] {axis_name} homed")
            if axis_name == "Vertical Axis":
                self._handle_vertical_motion_update()

        if not self.syringe_panel or not self.syringe_panel.ready:
            raise RuntimeError("Syringe pump unavailable for homing")
        emit_ui_log("[Sequence1] Homing Syringe")
        self.syringe_panel.home_blocking()
        emit_ui_log("[Sequence1] Syringe homed")
        emit_ui_log("[Sequence1] Full initialization complete")

    def _sequence1_init(self):
        emit_ui_log("[Sequence1] Pre-check: ensuring relays 1,5,6 are OFF")
        for channel in (1, 5, 6):
            self._set_relay_state(channel, False, quiet=True)
        emit_ui_log("[Sequence1] Pre-check complete")

    def _ensure_sequence1_ready(self):
        try:
            self._validate_sequence1_prereqs()
            emit_ui_log("[Sequence1] Hardware ready")
            return
        except Exception as exc:
            emit_ui_log(f"[Sequence1] Prereqs missing ({exc}); running Initialize first")
        self._auto_initialize_for_sequence()
        self._validate_sequence1_prereqs()
        emit_ui_log("[Sequence1] Hardware ready after initialization")

    def _validate_sequence1_prereqs(self):
        if not self.relays:
            raise RuntimeError("Relay board unavailable. Run Initialize first.")
        if not self.rotary_panel or not getattr(self.rotary_panel, "valve", None):
            raise RuntimeError("Rotary valve control unavailable")
        vertical = self._get_axis_control("Vertical Axis")
        if vertical is None or not vertical.driver.ready:
            raise RuntimeError("Vertical axis unavailable. Run Initialize first.")
        horizontal = self._get_axis_control("Horizontal Axis")
        if horizontal is None or not horizontal.driver.ready:
            raise RuntimeError("Horizontal axis unavailable. Run Initialize first.")
        if not self.syringe_panel or not self.syringe_panel.ready:
            raise RuntimeError("Syringe pump unavailable. Run Initialize first.")
        if self._syringe_sequence_adapter is None:
            raise RuntimeError("Syringe adapter not configured")

    def _auto_initialize_for_sequence(self):
        if self._init_running:
            emit_ui_log("[Sequence1] Waiting for ongoing initialization to finish")
            while self._init_running:
                if self._stop_event.is_set():
                    raise RuntimeError("Initialization interrupted")
                time.sleep(0.1)
            emit_ui_log("[Sequence1] Initialization ready")
            return
        emit_ui_log("[Sequence1] Pre-sequence initialization start")
        self._stop_event.clear()
        self._init_abort.clear()
        self._init_running = True
        self._set_init_enabled(False)
        self._initialize_sequence()
        emit_ui_log("[Sequence1] Pre-sequence initialization complete")

    def _sequence_move_axis(self, axis_name: str, preset_key: str):
        ctrl = self._get_axis_control(axis_name)
        if ctrl is None:
            raise RuntimeError(f"{axis_name} control unavailable")
        if not ctrl.driver.ready:
            raise RuntimeError(f"{axis_name} unavailable")
        preset_key = preset_key.strip().lower()
        preset_map = AXIS_PRESET_POSITIONS.get(axis_name)
        if not preset_map or preset_key not in preset_map:
            raise RuntimeError(f"{axis_name} preset '{preset_key}' undefined")
        if axis_name == "Horizontal Axis":
            allowed, message = self._evaluate_horizontal_axis_state()
            if not allowed:
                raise RuntimeError(message or "Horizontal axis locked")
        label, target_mm = preset_map[preset_key]
        ctrl.driver.move_to_mm(target_mm, SEQUENCE_AXIS_SPEED_RPM, context=f"[Sequence1] {label}")
        ctrl.set_cached_position_mm(target_mm)
        if axis_name == "Vertical Axis":
            self._handle_vertical_motion_update()

    def _sequence_select_rotary_port(self, port: int):
        panel = self.rotary_panel
        if panel is None or not getattr(panel, "valve", None):
            raise RuntimeError("Rotary valve unavailable")
        if not (1 <= int(port) <= panel.port_count):
            raise RuntimeError(f"Rotary port {port} out of range")
        emit_ui_log(f"[Sequence1] Rotary valve -> Port {port}")
        ok = panel.valve.set_port(int(port))
        if not ok:
            raise RuntimeError(f"Rotary valve port {port} not acknowledged")
        panel._invoke_ui(lambda: panel._apply_switch_result(int(port), True))

    def _set_init_enabled(self, enabled: bool):
        self.init_state_signal.emit(enabled)

    @pyqtSlot(bool)
    def _apply_init_state(self, enabled: bool):
        self.init_button.setEnabled(enabled)
        if hasattr(self, 'verify_checkbox') and self.verify_checkbox is not None:
            self.verify_checkbox.setEnabled(enabled)
        if enabled:
            self.init_button.setText('Initialize')
            self.unsetCursor()
        else:
            self.init_button.setText('Initializing...')
            self.setCursor(Qt.BusyCursor)

    def _initialize_sequence(self):
        emit_ui_log("Initialization sequence started")
        try:
            self._init_devices()
            emit_ui_log("Initialization complete")
        except Exception as exc:
            if self._init_abort.is_set():
                emit_ui_log("Initialization aborted by user")
            else:
                emit_ui_log(f"Initialization failed: {exc}")
        finally:
            self._set_init_enabled(True)
            self._init_running = False

    def _check_init_abort(self):
        if self._init_abort.is_set():
            raise RuntimeError("Initialization aborted by user")

    def _init_devices(self):
        self._check_init_abort()
        self._prepare_outputs_for_init()
        self._check_init_abort()
        if SyringePump is None:
            raise RuntimeError("SyringePump class unavailable")

        self._ensure_relays_off_before_connect()
        self._connect_relays()
        self._check_init_abort()
        verify_devices = True
        if hasattr(self, "verify_checkbox") and self.verify_checkbox is not None:
            verify_devices = self.verify_checkbox.isChecked()

        def _connect_axis(ctrl: StepperAxisControl):
            self._check_init_abort()
            driver = ctrl.driver
            emit_ui_log(f"[{driver.name}] Connecting on {driver.port} @ {driver.address:#04x}")
            try:
                ok = driver.connect(verify=verify_devices, timeout=CONNECTION_PROBE_TIMEOUT)
            except Exception as exc:
                ok = False
                emit_ui_log(f"[{driver.name}] init failed: {exc}")
            self._invoke_ui(ctrl.refresh_ready_state)
            if not ok:
                raise RuntimeError(f"{driver.name} unavailable (no response)")
            emit_ui_log(f"[{driver.name}] Ready")

        axis_sequence = ("Vertical Axis", "Horizontal Axis")
        connected_axes: List[StepperAxisControl] = []
        for axis_name in axis_sequence:
            self._check_init_abort()
            ctrl = self._get_axis_control(axis_name)
            if ctrl is None:
                raise RuntimeError(f"{axis_name} control unavailable")
            _connect_axis(ctrl)
            connected_axes.append(ctrl)

        # Connect syringe pump
        syringe_ready = False
        if self.syringe_panel:
            self._check_init_abort()
            emit_ui_log("[Syringe] Connecting")
            try:
                syringe_ready = self.syringe_panel.connect(
                    verify=verify_devices,
                    timeout=CONNECTION_PROBE_TIMEOUT,
                )
            except Exception as exc:
                syringe_ready = False
                emit_ui_log(f"[Syringe] init failed: {exc}")

            if not syringe_ready:
                emit_ui_log("[Syringe] unavailable (no response)")
                if REQUIRE_SYRINGE_FOR_INIT:
                    raise RuntimeError("Syringe connection required but unavailable")

        # Auto-home axes: Vertical → Horizontal → Syringe
        for ctrl in connected_axes:
            self._check_init_abort()
            emit_ui_log(f"[{ctrl.name}] Auto-homing…")
            try:
                busy = ctrl.driver.is_busy()
                if busy:
                    emit_ui_log(f"[{ctrl.name}] Busy before homing → issuing quick stop")
                    ctrl.force_stop(quiet=True)
                    time.sleep(0.1)
                ctrl.home_blocking()
                emit_ui_log(f"[{ctrl.name}] Homed and at standstill")
                if ctrl.name == "Vertical Axis":
                    self._handle_vertical_motion_update()
            except Exception as exc:
                raise RuntimeError(f"{ctrl.name} homing error: {exc}") from exc

        if self.syringe_panel and (self.syringe_panel.ready or syringe_ready):
            self._check_init_abort()
            emit_ui_log("[Syringe] Auto-homing…")
            try:
                self.syringe_panel.home_blocking()
                emit_ui_log("[Syringe] Homed and at standstill")
            except Exception as exc:
                raise RuntimeError(f"Syringe homing error: {exc}") from exc
        else:
            emit_ui_log("[Syringe] Skipped (unavailable)")

    def _configure_horizontal_axis_interlock(self):
        horizontal = self._get_axis_control("Horizontal Axis")
        vertical = self._get_axis_control("Vertical Axis")
        if horizontal:
            horizontal.set_pre_move_check(self._horizontal_axis_precheck)
        if vertical:
            vertical.add_motion_callback(self._handle_vertical_motion_update)
        self._refresh_horizontal_axis_lock()

    def _horizontal_lock_watchdog(self):
        if self._horizontal_lock_active:
            self._refresh_horizontal_axis_lock()

    def _handle_vertical_motion_update(self):
        if threading.current_thread() is threading.main_thread():
            self._refresh_horizontal_axis_lock()
        else:
            self._invoke_ui(self._refresh_horizontal_axis_lock)

    def _horizontal_axis_precheck(self) -> bool:
        allowed = self._refresh_horizontal_axis_lock()
        if not allowed:
            msg = self._horizontal_lock_message or "Horizontal axis locked by safety interlock"
            emit_ui_log(msg)
        return allowed

    def _refresh_horizontal_axis_lock(self) -> bool:
        horizontal = self._get_axis_control("Horizontal Axis")
        allowed, message = self._evaluate_horizontal_axis_state()
        state_changed = (self._horizontal_lock_active != (not allowed)) or (
            message != self._horizontal_lock_message
        )
        self._horizontal_lock_active = not allowed
        self._horizontal_lock_message = message
        if horizontal:
            horizontal.set_safety_lock(not allowed, message)
        if state_changed:
            if not allowed:
                emit_ui_log(message or "Horizontal axis locked by safety interlock")
            else:
                emit_ui_log("Horizontal axis safety lock cleared")
        return allowed

    def _evaluate_horizontal_axis_state(self) -> Tuple[bool, str]:
        vertical_ctrl = self._get_axis_control("Vertical Axis")
        if vertical_ctrl is None or not vertical_ctrl.driver.ready:
            return False, "Horizontal axis locked: vertical axis unavailable"
        position_mm = vertical_ctrl.get_cached_position_mm()
        if position_mm is None:
            return False, "Horizontal axis locked: waiting for vertical axis feedback"
        if position_mm > HORIZONTAL_AXIS_VERTICAL_LIMIT_MM:
            return (
                False,
                f"Horizontal axis locked: vertical axis at {position_mm:.2f} mm (> {HORIZONTAL_AXIS_VERTICAL_LIMIT_MM:.1f} mm limit)",
            )
        return True, ""

    def _prepare_outputs_for_init(self):
        self._relays_all_off(auto=True)

    def _ensure_relays_off_before_connect(self):
        if self.relays and any(self.relay_states.values()):
            emit_ui_log("[Relays] Forcing ALL OFF before initialization")
            self._relays_all_off(auto=False)

    def _get_axis_control(self, name: str) -> Optional["StepperAxisControl"]:
        return next((ctrl for ctrl in self.axis_controls if ctrl.name == name), None)

    def _require_relays(self) -> RelayBoard06:
        if not self.relays:
            raise RuntimeError("Relay board unavailable")
        return self.relays

    def _connect_relays(self):
        try:
            self.relays = RelayBoard06(port=RELAY_PORT, address=RELAY_ADDRESS)
            emit_ui_log(f"Relay board ready on {RELAY_PORT} @ {RELAY_ADDRESS:#04x}")
        except Exception as exc:
            self.relays = None
            emit_ui_log(f"[Relays] board init failed: {exc}")

        # Reset relay states to known board channels only
        self.relay_states = {ch: False for ch, _ in RELAY_OUTPUTS}
        def _reset_buttons():
            for ch in self.relay_states.keys():
                self._update_relay_button(ch, False)
        self._invoke_ui(_reset_buttons)
        self._relays_all_off(auto=True)

    def _handle_relay_toggle(self, channel: int, state: bool) -> bool:
        return self._set_relay_state(channel, state)

    def _set_relay_state(self, channel: int, state: bool, quiet: bool = False) -> bool:
        try:
            if not self.relays:
                raise RuntimeError("Relay board not initialized")
            cmd = self.relays.on if state else self.relays.off
            ok = bool(cmd(int(channel)))
            if not ok:
                raise RuntimeError("No ACK")
        except Exception as exc:
            if not quiet:
                emit_ui_log(f"[Relay {channel}] error: {exc}")
            fallback_state = self.relay_states.get(channel, False)
            self._invoke_ui(
                lambda ch=channel, st=fallback_state: self._update_relay_button(ch, st)
            )
            return False

        self.relay_states[channel] = state
        self._invoke_ui(lambda ch=channel, st=state: self._update_relay_button(ch, st))
        if not quiet:
            emit_ui_log(f"[Relay {channel}] -> {'ON' if state else 'OFF'}")
        return True

    def _update_relay_button(self, channel: int, state: bool):
        btn = self.relay_buttons.get(channel)
        if btn:
            btn.set_state(state)

    def _relays_all_on(self):
        ok = True
        channels = sorted(self.relay_states.keys())
        for idx, channel in enumerate(channels):
            if not self._set_relay_state(channel, True):
                ok = False
            if idx < len(channels) - 1:
                time.sleep(RELAY_COMMAND_DELAY)
        emit_ui_log(f"[Relays] ALL ON {'OK' if ok else 'incomplete'}")

    def _relays_all_off(self, auto: bool = False):
        ok = True
        channels = sorted(self.relay_states.keys())
        for idx, channel in enumerate(channels):
            if not self._set_relay_state(channel, False, quiet=auto):
                ok = False
            if idx < len(channels) - 1:
                time.sleep(RELAY_COMMAND_DELAY)
        if not auto:
            emit_ui_log(f"[Relays] ALL OFF {'OK' if ok else 'incomplete'}")

    def _build_valve_section(
        self,
        title: Optional[str],
        mapping: Sequence[tuple],
        size: int = 48,
    ) -> Tuple[QWidget, QHBoxLayout]:
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout = QVBoxLayout(container)
        padding = 4 if title is None else 0
        bottom_padding = padding if title is None else 8
        layout.setContentsMargins(0, padding, 0, bottom_padding)
        layout.setSpacing(8)

        if title:
            hdr = QLabel(title)
            hdr.setObjectName("panelTitle")
            layout.addWidget(hdr)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12 if title is None else 10)
        grid.setVerticalSpacing(12 if title is None else 10)

        cols = 2
        for idx, (channel, label) in enumerate(mapping):
            btn = RelayToggleButton(
                channel=channel,
                label=label,
                toggle_callback=self._handle_relay_toggle,
                size=size,
            )
            btn.set_state(self.relay_states.get(channel, False))
            self.relay_buttons[channel] = btn
            row, col = divmod(idx, cols)
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(8)
        all_on = QPushButton("All ON")
        all_off = QPushButton("All OFF")
        for btn in (all_on, all_off):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
            btn.setFixedHeight(28)
        all_on.clicked.connect(self._relays_all_on)
        all_off.clicked.connect(self._relays_all_off)
        ctrl_row.addWidget(all_on)
        ctrl_row.addWidget(all_off)
        return container, ctrl_row

    def _append_log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        if self.log_view is None:
            print(entry)
            return
        self.log_signal.emit(entry)

    @pyqtSlot(str)
    def _write_log_entry(self, entry: str):
        if self.log_view:
            self.log_view.appendPlainText(entry)

    def _read_pid_feedback(self) -> float:
        """Return latest flow feedback (mL/min) for PID control."""
        panel = getattr(self, "flow_panel", None)
        if panel is not None:
            try:
                return float(panel.last_flow_ml_min())
            except Exception:
                pass
        sensor = getattr(self, "flow_meter", None)
        if sensor is not None:
            try:
                value = sensor.read_flow_ml_min()
                if value is not None:
                    return float(value)
            except Exception:
                pass
        return 0.0


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
