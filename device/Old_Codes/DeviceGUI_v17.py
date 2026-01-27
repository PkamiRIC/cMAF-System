#!/usr/bin/env python3
"""Compact control GUI for the alternate device sharing MainGUI_v5 aesthetics."""
import faulthandler; faulthandler.enable()
import importlib.util
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple
import serial

from simple_pid import PID
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QDoubleValidator
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
    QMessageBox,
)

from MAF_Sequence_v1 import run_maf_sequence
from MAF_Sequence_2 import run_maf_sequence as run_maf_sequence_v2
from Cleaning_Sequence import run_maf_cleaning_sequence

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
from slf3s_usb_sensor import SLF3SUSBFlowSensor

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
RELAY_ADDRESS = 0x01
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
    (5, "Relay 5"),
    (6, "Relay 6"),
    (7, "Relay 7"),
    (8, "Relay 8"),
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
        "max_mm": 25.0,
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
        "close": ("Close", 25.0),
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

PERISTALTIC_PINS = {
    "enable": "Q0.0",
    "dir_forward": "Q0.1",
    "dir_reverse": "Q0.2",
    "speed": "Q0.7",
}

FLOW_SENSOR_PORT = "/dev/ttyUSB0"
FLOW_SENSOR_MEDIUM = "water"
FLOW_SENSOR_INTERVAL_MS = 20  # match stable CLI test settings
FLOW_SENSOR_SCALE_FACTOR = 500.0  # datasheet value for SLF3S-1300F
FLOW_SENSOR_STALE_RESTART_LIMIT = 20  # polls before watchdog restart

TEMP_COMMAND_PIN = "Q0.6"
TEMP_READY_PIN = "I0.11"       # PLC fallback
TEMP_READY_GPIO_PIN = 8        # BCM numbering for Pi GPIO

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


class PIDValveController:
    """Stepper-driven PID valve control."""

    def __init__(self, get_flow_func: Callable[[], float]):
        self._get_flow = get_flow_func
        self.enabled = False
        self.setpoint = 1.0
        self.pid = PID(1.6, 0.25, 0.02, setpoint=self.setpoint)
        self.pid.sample_time = 0.08
        self.pid.output_limits = (-1.5, 1.5)

        self.STEP = "Q0.5"
        self.DIR = "Q0.4"
        self.EN = "Q0.3"
        self.HALL = "I0.12"

        for pin in (self.STEP, self.DIR, self.EN):
            safe_plc_call("pin_mode", plc.pin_mode,pin, plc.OUTPUT)
        safe_plc_call("pin_mode", plc.pin_mode,self.HALL, plc.INPUT)

        self.hall_led_callback: Optional[Callable[[int], None]] = None
        self._start_hall_monitor()
        self._loop_interval = 0.08
        threading.Thread(target=self._control_loop, daemon=True).start()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        safe_plc_call("digital_write", plc.digital_write,self.EN, not enabled)
        emit_ui_log(f"PID valve {'ENABLED' if enabled else 'DISABLED'}")

    def set_setpoint(self, value: float):
        self.setpoint = value
        self.pid.setpoint = value
        emit_ui_log(f"PID setpoint -> {value:.1f} mL/min")

    def _step_valve(self, direction: bool, steps: int = 20):
        safe_plc_call("digital_write", plc.digital_write,self.DIR, direction)
        time.sleep(0.001)
        for _ in range(steps):
            safe_plc_call("digital_write", plc.digital_write,self.STEP, True)
            time.sleep(0.00002)
            safe_plc_call("digital_write", plc.digital_write,self.STEP, False)
            time.sleep(0.00002)

    def _control_loop(self):
        while True:
            if self.enabled:
                flow = self._get_flow()
                output = self.pid(flow)
                steps = int(abs(output) * 8)
                if steps:
                    self._step_valve(direction=(output > 0), steps=steps)
            time.sleep(self._loop_interval)

    def _start_hall_monitor(self):
        def monitor():
            while True:
                # Always treat non-integer reads as logical low (0)
                val = safe_plc_call("digital_read", plc.digital_read, self.HALL)
                if not isinstance(val, int):
                    val = 0
                if self.hall_led_callback:
                    try:
                        self.hall_led_callback(val)
                    except Exception as exc:
                        emit_ui_log(f"[PIDValve] hall LED callback error: {exc}")
                time.sleep(1)

        threading.Thread(target=monitor, daemon=True).start()

    def homing_routine(self):
        emit_ui_log("Starting PID valve homing")
        safe_plc_call("digital_write", plc.digital_write,self.EN, False)
        safe_plc_call("digital_write", plc.digital_write,self.DIR, False)
        while safe_plc_call("digital_read", plc.digital_read,self.HALL) == 1:
            safe_plc_call("digital_write", plc.digital_write,self.STEP, True)
            time.sleep(0.001)
            safe_plc_call("digital_write", plc.digital_write,self.STEP, False)
            time.sleep(0.001)
        safe_plc_call("digital_write", plc.digital_write,self.EN, True)
        emit_ui_log("PID valve homed")

    def force_close(self, timeout: float = 8.0):
        """Drive the valve fully closed without relying on the PID loop."""
        emit_ui_log("PID valve closing to hard stop")
        safe_plc_call("digital_write", plc.digital_write,self.EN, False)
        deadline = time.time() + max(timeout, 1.0)
        while True:
            val = safe_plc_call("digital_read", plc.digital_read,self.HALL)
            if isinstance(val, int) and val == 1:
                break
            self._step_valve(direction=True, steps=1500)
            if time.time() > deadline:
                safe_plc_call("digital_write", plc.digital_write,self.EN, True)
                raise RuntimeError("PID valve close timed out")
        safe_plc_call("digital_write", plc.digital_write,self.EN, True)
        emit_ui_log("PID valve closed")


class PIDValvePanel(QWidget):
    def __init__(self, controller: PIDValveController, read_sensor: Callable[[], float]):
        super().__init__()
        self.controller = controller
        self.read_sensor = read_sensor

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QLabel("PID Valve")
        header.setObjectName("panelTitle")
        layout.addWidget(header)

        self.enable_button = QPushButton("Enable PID")
        self.enable_button.setCheckable(True)
        self.enable_button.setCursor(Qt.PointingHandCursor)
        self.enable_button.setFocusPolicy(Qt.NoFocus)
        self.enable_button.setStyleSheet(PRIMARY_TOGGLE_STYLE)
        self.enable_button.setFixedHeight(26)
        self.enable_button.clicked.connect(self._toggle_pid)

        self.setpoint_input = QLineEdit(f"{self.controller.setpoint:.1f}")
        self.setpoint_input.setValidator(QDoubleValidator(1.0, 500.0, 1))
        self.setpoint_input.setAlignment(Qt.AlignCenter)
        self.setpoint_input.setPlaceholderText("Setpoint (mL/min)")
        self.setpoint_input.returnPressed.connect(self._apply_setpoint)

        self.feedback_label = QLabel("Feedback: -- mL/min")
        self.feedback_label.setStyleSheet("font-weight: 600; font-size: 16px;")

        self.home_button = QPushButton("Home Valve")
        self.home_button.setCursor(Qt.PointingHandCursor)
        self.home_button.setFocusPolicy(Qt.NoFocus)
        self.home_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.home_button.setFixedHeight(26)
        self.home_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.home_button.clicked.connect(self._home_valve)

        self.close_button = QPushButton("Close Valve")
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setFocusPolicy(Qt.NoFocus)
        self.close_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.close_button.setFixedHeight(26)
        self.close_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.close_button.clicked.connect(self._close_valve)

        form = QGridLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(4)
        form.setVerticalSpacing(3)
        form.addWidget(QLabel("Setpoint"), 0, 0)
        form.addWidget(self.setpoint_input, 0, 1)
        form.addWidget(QLabel("Status"), 1, 0)
        form.addWidget(self.feedback_label, 1, 1)

        layout.addLayout(form)
        layout.addWidget(self.enable_button)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(6)
        button_row.addWidget(self.home_button)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

        self._telemetry = QTimer(self)
        self._telemetry.setInterval(1000)
        self._telemetry.timeout.connect(self._update_feedback)
        self._telemetry.start()

    def _toggle_pid(self):
        state = self.enable_button.isChecked()
        self.controller.set_enabled(state)
        self._apply_enable_button_state(state)

    def _apply_setpoint(self):
        try:
            value = float(self.setpoint_input.text())
        except ValueError:
            return
        self.controller.set_setpoint(value)

    def _update_feedback(self):
        value = self.read_sensor()
        self.feedback_label.setText(f"Feedback: {value:.1f} mL/min")

    def force_stop(self):
        self.controller.set_enabled(False)
        self._apply_enable_button_state(False)
        emit_ui_log("PID valve forced OFF")

    def _home_valve(self):
        if self.controller.enabled:
            self.controller.set_enabled(False)
            self._apply_enable_button_state(False)

        def _run_home():
            time.sleep(0.5)
            self.controller.homing_routine()

        threading.Thread(target=_run_home, daemon=True).start()

    def _close_valve(self):
        if self.controller.enabled:
            self.controller.set_enabled(False)
            self._apply_enable_button_state(False)

        def _run_close():
            time.sleep(0.5)
            try:
                self.controller.force_close()
            except Exception as exc:
                emit_ui_log(f"[PIDValve] close error: {exc}")

        threading.Thread(target=_run_close, daemon=True).start()

    def _apply_enable_button_state(self, state: bool):
        self.enable_button.blockSignals(True)
        self.enable_button.setChecked(state)
        self.enable_button.blockSignals(False)
        self.enable_button.setText("PID ON" if state else "Enable PID")


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


class _PeristalticSequenceAdapter:
    """Bridge the peristaltic panel pins to the MAF sequence motor API."""

    def __init__(self, panel: Optional["PeristalticPumpPanel"]):
        self.panel = panel

    def _require_panel(self) -> "PeristalticPumpPanel":
        if not self.panel:
            raise RuntimeError("Peristaltic pump unavailable")
        return self.panel

    def set_enabled(self, enabled: bool):
        panel = self._require_panel()
        safe_plc_call("digital_write", plc.digital_write,panel.enable_pin, not enabled)
        emit_ui_log(f"[MAF] Peristaltic pump {'ENABLED' if enabled else 'DISABLED'}")

    def set_direction(self, forward: bool):
        panel = self._require_panel()
        safe_plc_call("digital_write", plc.digital_write,panel.dir_forward_pin, forward)
        safe_plc_call("digital_write", plc.digital_write,panel.dir_reverse_pin, not forward)
        emit_ui_log(f"[MAF] Pump direction -> {'CW' if forward else 'CCW'}")

    def set_speed_checked(self, checked: bool):
        panel = self._require_panel()
        safe_plc_call("digital_write", plc.digital_write,panel.speed_pin, checked)
        emit_ui_log(f"[MAF] Pump speed -> {'LOW' if checked else 'HIGH'}")


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


class _SyringeSequenceAdapter:
    """Placeholder syringe adapter that logs sequence actions."""

    def __init__(self, panel: Optional["SyringeControlPanel"]):
        self.panel = panel

    def _require_pump(self) -> SyringePump:
        panel = self.panel
        pump = getattr(panel, "_pump", None) if panel else None
        if pump is None:
            raise RuntimeError("Syringe pump unavailable for sequence")
        return pump

    def _log(self, action: str):
        emit_ui_log(f"[MAF] Syringe {action} (action not yet implemented)")

    def goto_absolute(self, target_ml: float, flow_ml_min: float):
        pump = self._require_pump()
        if not wait_standstill(pump, timeout=30, poll=0.2):
            raise RuntimeError("Syringe not at standstill before move")
        current_ml = _read_volume_ml(pump)
        delta = None
        if current_ml is not None:
            delta = float(target_ml) - current_ml
            if abs(delta) < 0.01:
                emit_ui_log(f"[MAF] Syringe already at {target_ml:.2f} mL")
                return
        flow = max(float(flow_ml_min), 0.1)
        signed_flow = flow if (delta is None or delta >= 0.0) else -flow
        emit_ui_log(f"[MAF] Syringe move -> {target_ml:.2f} mL @ {abs(signed_flow):.2f} mL/min")
        pump.move(float(target_ml), signed_flow)
        if not wait_pos_done(pump, timeout=600, poll=0.2):
            raise RuntimeError("Syringe move did not settle")
        emit_ui_log(f"[MAF] Syringe reached {target_ml:.2f} mL")

    def suck_air(self):
        self._log("SUCK AIR")

    def inject_air(self):
        self._log("INJECT AIR")

    def suck_buffer(self):
        self._log("SUCK BUFFER")

    def inject_buffer(self):
        self._log("INJECT BUFFER")


class PeristalticPumpPanel(QWidget):
    def __init__(self):
        super().__init__()

        self.enable_pin = PERISTALTIC_PINS["enable"]
        self.dir_forward_pin = PERISTALTIC_PINS["dir_forward"]
        self.dir_reverse_pin = PERISTALTIC_PINS["dir_reverse"]
        self.speed_pin = PERISTALTIC_PINS["speed"]

        for pin in (self.enable_pin, self.dir_forward_pin, self.dir_reverse_pin, self.speed_pin):
            safe_plc_call("pin_mode", plc.pin_mode,pin, plc.OUTPUT)
            safe_plc_call("digital_write", plc.digital_write,pin, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel("Peristaltic Pump")
        header.setObjectName("panelTitle")
        layout.addWidget(header)

        self.enable_button = QPushButton("Pump OFF")
        self.enable_button.setCheckable(True)
        self.enable_button.setCursor(Qt.PointingHandCursor)
        self.enable_button.setStyleSheet(PRIMARY_TOGGLE_STYLE)
        self.enable_button.setFocusPolicy(Qt.NoFocus)
        self.enable_button.setFixedHeight(34)
        self.enable_button.clicked.connect(self._toggle_enable)

        self.direction_button = QPushButton("Dir: CW")
        self.direction_button.setCheckable(True)
        self.direction_button.setCursor(Qt.PointingHandCursor)
        self.direction_button.setStyleSheet(PRIMARY_TOGGLE_STYLE)
        self.direction_button.setFocusPolicy(Qt.NoFocus)
        self.direction_button.setFixedHeight(34)
        self.direction_button.clicked.connect(self._toggle_direction)

        self.speed_button = QPushButton("High Speed")
        self.speed_button.setCheckable(True)
        self.speed_button.setCursor(Qt.PointingHandCursor)
        self.speed_button.setStyleSheet(PRIMARY_TOGGLE_STYLE)
        self.speed_button.setFocusPolicy(Qt.NoFocus)
        self.speed_button.setFixedHeight(34)
        self.speed_button.clicked.connect(self._toggle_speed)

        layout.addWidget(self.enable_button)
        layout.addWidget(self.direction_button)
        layout.addWidget(self.speed_button)

    def _toggle_enable(self):
        state = self.enable_button.isChecked()
        safe_plc_call("digital_write", plc.digital_write,self.enable_pin, not state)
        self.enable_button.setText("Pump ON" if state else "Pump OFF")
        emit_ui_log(f"Peristaltic pump {'ENABLED' if state else 'DISABLED'}")

    def _toggle_direction(self):
        forward = self.direction_button.isChecked()
        safe_plc_call("digital_write", plc.digital_write,self.dir_forward_pin, forward)
        safe_plc_call("digital_write", plc.digital_write,self.dir_reverse_pin, not forward)
        self.direction_button.setText("Dir: CW" if forward else "Dir: CCW")
        emit_ui_log(f"Pump direction -> {'CW' if forward else 'CCW'}")

    def _toggle_speed(self):
        slow = self.speed_button.isChecked()
        safe_plc_call("digital_write", plc.digital_write,self.speed_pin, slow)
        self.speed_button.setText("Low Speed" if slow else "High Speed")
        emit_ui_log(f"Pump speed -> {'LOW' if slow else 'HIGH'}")

    def force_stop(self):
        safe_plc_call("digital_write", plc.digital_write,self.enable_pin, True)
        safe_plc_call("digital_write", plc.digital_write,self.dir_forward_pin, False)
        safe_plc_call("digital_write", plc.digital_write,self.dir_reverse_pin, False)
        self.enable_button.blockSignals(True)
        self.enable_button.setChecked(False)
        self.enable_button.blockSignals(False)
        self.enable_button.setText("Pump OFF")
        emit_ui_log("Peristaltic pump forced OFF")


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
        if threading.current_thread() is threading.main_thread():
            func()
        else:
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


class FlowMeterPanel(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self._last_flow_ml_min = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(4)

        header = QLabel("Flow Meter")
        header.setObjectName("panelTitle")
        layout.addWidget(header)

        self.flow_label = QLabel("Flow Rate: -- mL/min")
        self.total_label = QLabel("Total Volume: -- mL")
        for lbl in (self.flow_label, self.total_label):
            lbl.setStyleSheet("font-size: 14px; font-weight: 600;")
            layout.addWidget(lbl)

        target_container = QHBoxLayout()
        target_container.setContentsMargins(0, 0, 0, 0)
        target_container.setSpacing(6)
        target_label = QLabel("Target Vol.")
        target_label.setStyleSheet("font-weight: 600;")
        target_container.addWidget(target_label)

        self.target_volume_spin = QDoubleSpinBox()
        self.target_volume_spin.setDecimals(1)
        self.target_volume_spin.setRange(1.0, 2000.0)
        self.target_volume_spin.setValue(50.0)
        self.target_volume_spin.setSuffix(" mL")
        self.target_volume_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.target_volume_spin.setStyleSheet(SPIN_STYLE)
        self.target_volume_spin.setFixedWidth(110)
        target_container.addWidget(self.target_volume_spin)

        layout.addLayout(target_container)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.start_button = QPushButton("Start")
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.start_button.clicked.connect(self._handle_start)
        button_row.addWidget(self.start_button)

        self.reset_button = QPushButton("Reset")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.reset_button.clicked.connect(self._handle_reset)
        button_row.addWidget(self.reset_button)

        self.elapsed_label = QLabel("Elapsed: 00:00")
        self.elapsed_label.setStyleSheet("font-weight: 600;")
        button_row.addWidget(self.elapsed_label)

        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._started = False
        self._idle_labels()
        self._elapsed_seconds = 0.0
        self._elapsed_start_time: Optional[float] = None
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(500)
        self._elapsed_timer.timeout.connect(self._update_elapsed_label)
        self._elapsed_timer.start()
        self._update_elapsed_label()
        self._set_start_button_state(False)

        self._timer = QTimer(self)
        self._timer.setInterval(250)   # poll every 0.25s like the CLI test
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._refresh()

    def _idle_labels(self) -> None:
        self.flow_label.setText("Flow Rate: 0.0 mL/min")
        self.total_label.setText("Total Volume: 0.0 mL")
        self.flow_label.setToolTip("")
        self.total_label.setToolTip("")
        self._last_flow_ml_min = 0.0

    def target_volume_ml(self) -> float:
        return self.target_volume_spin.value()

    def _handle_start(self):
        if not self._started:
            try:
                self._start_client()
            except Exception as e:
                self._log(f"[FlowMeter] start error: {e}")
                return
            self._started = True
            self._reset_elapsed()
            self._begin_elapsed()
            self._set_start_button_state(True)
        else:
            self._stop_stream()
            self._started = False
            self._pause_elapsed()
            self._set_start_button_state(False)

    def _handle_reset(self):
        if self._started:
            self._stop_stream()
            self._started = False
        self._reset_elapsed()
        self._set_start_button_state(False)
        if hasattr(self.client, "stop"):
            try:
                self.client.stop()
            except Exception as e:
                self._log(f"[FlowMeter] stop error: {e}")
        if hasattr(self.client, "reset_totals"):
            try:
                self.client.reset_totals()
            except Exception as e:
                self._log(f"[FlowMeter] reset_totals error: {e}")
        self._idle_labels()

    def _start_client(self):
        if hasattr(self.client, "start"):
            try:
                self.client.start()
            except TypeError:
                self.client.start(medium="water")

    def _stop_stream(self):
        if hasattr(self.client, "stop"):
            try:
                self.client.stop()
            except Exception as e:
                self._log(f"[FlowMeter] stop error: {e}")

    def _refresh(self):
        """Read the flow meter and update labels. Works with dict or tuple returns."""
        if not self._started:
            self._idle_labels()
            return
        try:
            data = self.client.read()

            flow_value_ml_min = 0.0
            total_value_ml = 0.0
            temp_c = None
            flags = None

            if isinstance(data, dict):
                flow_l_min = self._as_float(data.get("flow_l_min", 0.0))
                total_l = self._as_float(data.get("total_l", 0.0))
                flow_ml_min = data.get("flow_ml_min")
                total_ml = data.get("total_ml")
                flow_ul_min = data.get("flow_ul_min")
                total_ul = data.get("total_ul")
                temp_c = data.get("temp_c", None)
                flags = data.get("flags", None)

                if flow_ul_min is not None:
                    flow_value_ml_min = self._as_float(flow_ul_min) / 1000.0
                elif flow_ml_min is not None:
                    flow_value_ml_min = self._as_float(flow_ml_min)
                else:
                    flow_value_ml_min = flow_l_min * 1000.0

                if total_ul is not None:
                    total_value_ml = self._as_float(total_ul) / 1000.0
                elif total_ml is not None:
                    total_value_ml = self._as_float(total_ml)
                else:
                    total_value_ml = total_l * 1000.0
            else:
                # Expect tuple: (flow_l_min, total_l, temp_c, flags) from I²C client
                flow_l_min = self._as_float(data[0])
                total_l = self._as_float(data[1])
                temp_c = data[2] if len(data) > 2 else None
                flags = data[3] if len(data) > 3 else None
                flow_value_ml_min = flow_l_min * 1000.0
                total_value_ml = total_l * 1000.0

            self.flow_label.setText(f"Flow Rate: {flow_value_ml_min:.1f} mL/min")
            self.total_label.setText(f"Total Volume: {total_value_ml:.1f} mL")
            self._last_flow_ml_min = float(flow_value_ml_min)

            # Put extra info (temp & flags) in a tooltip so we don't change your layout
            tip = []
            if temp_c is not None:
                try:
                    tip.append(f"Temp: {float(temp_c):.1f} °C")
                except Exception:
                    tip.append(f"Temp: {temp_c}")
            if flags is not None:
                try:
                    fval = int(flags)
                    air = "AIR!" if (fval & 0x0001) else "OK"
                    hi  = "HI "  if (fval & 0x0002) else ""
                    sm  = "SM "  if (fval & 0x0020) else ""
                    tip.append(f"Flags: 0x{fval:04X} {air} {hi}{sm}".strip())
                except Exception:
                    tip.append(f"Flags: {flags}")
            tooltip = " • ".join(tip) if tip else ""
            self.flow_label.setToolTip(tooltip)
            self.total_label.setToolTip(tooltip)

        except Exception as e:
            # Keep UI responsive; show last value and log the error once per tick
            self._log(f"[FlowMeter] read error: {e}")

    def _begin_elapsed(self):
        self._elapsed_start_time = time.time()

    def _pause_elapsed(self):
        if self._elapsed_start_time is not None:
            self._elapsed_seconds += max(0.0, time.time() - self._elapsed_start_time)
            self._elapsed_start_time = None
        self._update_elapsed_label()

    def _reset_elapsed(self):
        self._elapsed_seconds = 0.0
        self._elapsed_start_time = None
        self._update_elapsed_label()

    def _update_elapsed_label(self):
        total = self._elapsed_seconds
        if self._elapsed_start_time is not None:
            total += max(0.0, time.time() - self._elapsed_start_time)
        minutes = int(total // 60)
        seconds = int(total % 60)
        self.elapsed_label.setText(f"Elapsed: {minutes:02d}:{seconds:02d}")

    def _set_start_button_state(self, running: bool):
        if running:
            self.start_button.setText("Stop")
            self.start_button.setStyleSheet(COMMAND_ON_ACTIVE_STYLE)
        else:
            self.start_button.setText("Start")
            self.start_button.setStyleSheet(PRIMARY_BUTTON_STYLE)

    def closeEvent(self, event):
        """Cleanly stop streaming on exit if supported."""
        try:
            if hasattr(self.client, "stop"):
                self.client.stop()
            if hasattr(self.client, "close"):
                self.client.close()
        except Exception as e:
            self._log(f"[FlowMeter] stop error: {e}")
        super().closeEvent(event)

    def _log(self, msg: str):
        # Use your app logger if available; fall back to print
        try:
            emit_ui_log(msg)  # type: ignore  # your app's UI logger (if in scope)
        except Exception:
            print(msg)

    @staticmethod
    def _as_float(value, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def last_flow_ml_min(self) -> float:
        """Return the most recent flow measurement cached by the panel."""
        return float(self._last_flow_ml_min)


class TemperatureControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._command_pin_ok = True
        self._ready_gpio_ok = False
        self._ready_fallback_ok = True
        self._signal_state: Optional[bool] = None
        self._last_ready_state: Optional[bool] = None
        self._indicator_size = 32
        try:
            safe_plc_call("pin_mode", plc.pin_mode,TEMP_COMMAND_PIN, plc.OUTPUT)
            safe_plc_call("digital_write", plc.digital_write,TEMP_COMMAND_PIN, False)
        except Exception as exc:
            self._command_pin_ok = False
            emit_ui_log(f"[TempCtrl] command pin init failed: {exc}")

        try:
            safe_plc_call("pin_mode", plc.pin_mode,TEMP_READY_PIN, plc.INPUT)
        except Exception as exc:
            self._ready_fallback_ok = False
            emit_ui_log(f"[TempCtrl] ready pin fallback init failed: {exc}")

        if GPIO is not None:
            try:
                if GPIO.getmode() is None:
                    GPIO.setmode(GPIO.BCM)
                GPIO.setup(TEMP_READY_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                self._ready_gpio_ok = True
            except Exception as exc:
                self._ready_gpio_ok = False
                emit_ui_log(f"[TempCtrl] GPIO ready setup failed: {exc}")
        else:
            emit_ui_log("[TempCtrl] RPi.GPIO unavailable; using PLC ready fallback")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(6)

        header = QLabel("Temperature Control")
        header.setObjectName("panelTitle")
        layout.addWidget(header)

        self.status_label = QLabel("Ready Signal: --")
        self.status_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.status_label)

        signal_row = QHBoxLayout()
        signal_row.setContentsMargins(0, 0, 0, 0)
        signal_row.setSpacing(8)

        self.signal_on_button = QPushButton("Peltier ON")
        self.signal_on_button.setCursor(Qt.PointingHandCursor)
        self.signal_on_button.setFocusPolicy(Qt.NoFocus)
        self.signal_on_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.signal_on_button.setFixedHeight(30)
        self.signal_on_button.clicked.connect(self._handle_command_on)
        signal_row.addWidget(self.signal_on_button, 1)

        self.signal_off_button = QPushButton("Peltier OFF")
        self.signal_off_button.setCursor(Qt.PointingHandCursor)
        self.signal_off_button.setFocusPolicy(Qt.NoFocus)
        self.signal_off_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.signal_off_button.setFixedHeight(30)
        self.signal_off_button.clicked.connect(self._handle_command_off)
        signal_row.addWidget(self.signal_off_button, 1)

        self.signal_indicator = QFrame()
        self.signal_indicator.setFixedSize(self._indicator_size, self._indicator_size)
        self._set_signal_indicator(False)
        signal_row.addWidget(self.signal_indicator)

        layout.addLayout(signal_row)

        self._poll = QTimer(self)
        self._poll.setInterval(500)
        self._poll.timeout.connect(self._update_status)
        self._poll.start()
        self._update_status()
        self._command_state: Optional[bool] = None
        self._update_command_buttons()

    def _update_status(self):
        ready_state = self._read_ready_state()
        if ready_state is None:
            self.status_label.setText("Ready Signal: N/A")
            self.status_label.setStyleSheet("color: #f97316; font-weight: 600;")
        else:
            self.status_label.setText(f"Ready Signal: {'ON' if ready_state else 'OFF'}")
            color = "#22c55e" if ready_state else "#94a3b8"
            self.status_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        if ready_state and self._last_ready_state is not True:
            emit_ui_log("Target Temperature Reached")
        self._last_ready_state = ready_state
        self._set_signal_indicator(ready_state)

    def _handle_command_on(self):
        self._set_command_state(True)

    def _handle_command_off(self):
        self._set_command_state(False)

    def _set_command_state(self, state: bool):
        if not self._command_pin_ok:
            emit_ui_log("[TempCtrl] command pin unavailable")
            self._update_command_buttons()
            return
        if state == self._command_state:
            self._update_command_buttons()
            return
        try:
            safe_plc_call("digital_write", plc.digital_write,TEMP_COMMAND_PIN, state)
            self._command_state = state
            emit_ui_log(f"Temp control command -> {'ON' if state else 'OFF'}")
        except Exception as exc:
            emit_ui_log(f"[TempCtrl] command write failed: {exc}")
            return
        self._update_command_buttons()

    def _update_command_buttons(self):
        if hasattr(self, "signal_on_button") and hasattr(self, "signal_off_button"):
            if not self._command_pin_ok:
                self.signal_on_button.setEnabled(False)
                self.signal_off_button.setEnabled(False)
                self.signal_on_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
                self.signal_off_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
            else:
                self.signal_on_button.setEnabled(True)
                self.signal_off_button.setEnabled(True)
                if self._command_state is True:
                    self.signal_on_button.setStyleSheet(COMMAND_ON_ACTIVE_STYLE)
                    self.signal_off_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
                elif self._command_state is False:
                    self.signal_on_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
                    self.signal_off_button.setStyleSheet(COMMAND_OFF_ACTIVE_STYLE)
                else:
                    self.signal_on_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
                    self.signal_off_button.setStyleSheet(PRIMARY_BUTTON_STYLE)

    def force_stop(self):
        """Force the temperature command output low."""
        if self._command_pin_ok:
            self._set_command_state(False)
        else:
            self._command_state = False
            self._update_command_buttons()

    def _read_ready_state(self) -> Optional[bool]:
        if self._ready_gpio_ok and GPIO is not None:
            try:
                return bool(GPIO.input(TEMP_READY_GPIO_PIN))
            except Exception as exc:
                self._ready_gpio_ok = False
                emit_ui_log(f"[TempCtrl] GPIO ready read failed: {exc}")
        if self._ready_fallback_ok:
            try:
                return safe_plc_call("digital_read", plc.digital_read,TEMP_READY_PIN)
            except Exception as exc:
                self._ready_fallback_ok = False
                emit_ui_log(f"[TempCtrl] PLC ready read failed: {exc}")
        return None

    def _set_signal_indicator(self, state: Optional[bool]):
        self._signal_state = state
        if state is None:
            color = "#64748b"
            tooltip = "Temperature ready signal: unavailable"
        else:
            color = "#22c55e" if state else "#475569"
            tooltip = f"Temperature ready signal: {'ON' if state else 'OFF'}"
        self.signal_indicator.setStyleSheet(
            f"background-color: {color}; border: 1px solid #0f172a; border-radius: {self._indicator_size // 2}px;"
        )
        self.signal_indicator.setToolTip(tooltip)


class MainWindow(QWidget):
    log_signal = pyqtSignal(str)
    init_state_signal = pyqtSignal(bool)
    sequence_prompt_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Integrated Device Console")
        self.setMinimumSize(720, 520)
        self.resize(760, 600)

        plc.init("RPIPLC_V6", "RPIPLC_38AR")

        self.log_view: Optional[QPlainTextEdit] = None
        self.pid_panel: Optional[PIDValvePanel] = None
        self.peristaltic_panel: Optional[PeristalticPumpPanel] = None
        self.axis_controls: List[StepperAxisControl] = []
        self._peristaltic_sequence_adapter: Optional[_PeristalticSequenceAdapter] = None
        self._syringe_sequence_adapter: Optional[_SyringeSequenceAdapter] = None
        self._valve1_adapter: Optional[_RelayValveAdapter] = None
        self._valve2_adapter: Optional[_RelayValveAdapter] = None
        self._horizontal_lock_active = False
        self._horizontal_lock_message = ""
        self._horizontal_lock_timer = QTimer(self)
        self._horizontal_lock_timer.setInterval(1000)
        self._horizontal_lock_timer.timeout.connect(self._horizontal_lock_watchdog)
        self._horizontal_lock_timer.start()
        # SLF3S USB flow sensor on SCC1-USB cable
        self.flow_meter = SLF3SUSBFlowSensor(
            port=FLOW_SENSOR_PORT,
            medium=FLOW_SENSOR_MEDIUM,
            interval_ms=FLOW_SENSOR_INTERVAL_MS,
            scale_factor=FLOW_SENSOR_SCALE_FACTOR,
            stale_restart_limit=FLOW_SENSOR_STALE_RESTART_LIMIT,
            auto_start=False,
        )
        self.syringe_panel: Optional[SyringeControlPanel] = None
        self._init_running = False
        self._init_abort = threading.Event()
        self._stop_event = threading.Event()
        self._sequence_lock = threading.Lock()
        self._sequence_thread: Optional[threading.Thread] = None
        self._sequence_name: Optional[str] = None
        self._sequence_cancel: Optional[Callable[[], None]] = None
        self.sequence1_button: Optional[QPushButton] = None
        self.sequence2_button: Optional[QPushButton] = None
        self.cleaning_button: Optional[QPushButton] = None

        register_ui_logger(self._append_log)
        self.log_signal.connect(self._write_log_entry)
        self.init_state_signal.connect(self._apply_init_state)
        # self.sequence_prompt_signal.connect(self._show_sequence_prompt_dialog)
        self._tasks = TaskManager(self._append_log)
        self._sequence_prompt_event = threading.Event()
        self._sequence_prompt_title = "Sequence Step"
        self.sequence_prompt_signal.connect(self._show_sequence_prompt_dialog)

        self.pid_controller = PIDValveController(self._read_pid_feedback)
        self.relays: Optional[RelayBoard06] = None
        self.relay_states: Dict[int, bool] = {channel: False for channel, _ in RELAY_OUTPUTS}
        self.relay_buttons: Dict[int, RelayToggleButton] = {}

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
        self.pid_panel = PIDValvePanel(self.pid_controller, self._read_pid_feedback)
        left_layout.addWidget(self.pid_panel)
        left_layout.addSpacing(4)
        relays_label = QLabel("Relays")
        relays_label.setObjectName("panelTitle")
        left_layout.addWidget(relays_label)
        relay_panel, relay_controls = self._build_valve_section(None, RELAY_OUTPUTS, size=42)
        left_layout.addWidget(relay_panel)
        left_layout.addSpacing(6)
        left_layout.addLayout(relay_controls)
        left_layout.addSpacing(18)
        left_layout.addStretch()
        self.peristaltic_panel = PeristalticPumpPanel()
        self._peristaltic_sequence_adapter = _PeristalticSequenceAdapter(self.peristaltic_panel)
        left_layout.addWidget(self.peristaltic_panel)
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
        self._syringe_sequence_adapter = _SyringeSequenceAdapter(self.syringe_panel)
        motion_layout.addWidget(self.syringe_panel)
        content.addWidget(motion_panel, 1)
        self._configure_horizontal_axis_interlock()
        self._valve1_adapter = _RelayValveAdapter(lambda: self.relays, 1, "Valve 1")
        self._valve2_adapter = _RelayValveAdapter(lambda: self.relays, 2, "Valve 2")

        # Right panel (Flow, Temp, Log, Stop)
        right_panel, right_layout = self._build_panel()
        self.flow_panel = FlowMeterPanel(self.flow_meter)
        right_layout.addWidget(self.flow_panel)
        right_layout.addSpacing(8)
        self.temperature_panel = TemperatureControlPanel()
        right_layout.addWidget(self.temperature_panel)
        right_layout.addSpacing(12)

        sequence_row = QHBoxLayout()
        sequence_row.setContentsMargins(0, 0, 0, 0)
        sequence_row.setSpacing(8)
        self.sequence1_button = QPushButton("Sequence 1")
        self.sequence2_button = QPushButton("Sequence 2")
        for button, label in (
            (self.sequence1_button, "Sequence1"),
            (self.sequence2_button, "Sequence 2"),
        ):
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.NoFocus)
            button.setStyleSheet(PRIMARY_BUTTON_STYLE)
            button.setFixedHeight(32)
            button.clicked.connect(
                lambda _, name=label: self._handle_sequence_placeholder(name)
            )
            sequence_row.addWidget(button)
        right_layout.addLayout(sequence_row)
        self.cleaning_button = QPushButton("Cleaning Sequence")
        self.cleaning_button.setCursor(Qt.PointingHandCursor)
        self.cleaning_button.setFocusPolicy(Qt.NoFocus)
        self.cleaning_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.cleaning_button.setFixedHeight(32)
        self.cleaning_button.clicked.connect(self._start_cleaning_sequence)
        right_layout.addWidget(self.cleaning_button)

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
        if threading.current_thread() is threading.main_thread():
            func()
        else:
            QTimer.singleShot(0, func)

    def _emergency_stop(self):
        emit_ui_log("EMERGENCY STOP triggered")
        self._init_abort.set()
        self._stop_event.set()
        self._stop_active_sequence()
        if self.pid_panel:
            self._safe_stop("PID panel", self.pid_panel.force_stop)
        if self.peristaltic_panel:
            self._safe_stop("Peristaltic pump", self.peristaltic_panel.force_stop)
        if self.syringe_panel:
            self._safe_stop("Syringe", self.syringe_panel.force_stop)
        for axis in self.axis_controls:
            self._safe_stop(axis.name, lambda ax=axis: ax.force_stop(quiet=True))
        self._safe_stop("Relays", lambda: self._relays_all_off(auto=True))
        if self.temperature_panel:
            self._safe_stop("Temperature controller", self.temperature_panel.force_stop)
        if getattr(self, "pid_controller", None):
            self._home_pid_valve_async()
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
        """Sequence button handler with MAF integration on Sequence 1."""
        if label == "Sequence1":
            self._start_maf_sequence()
            return
        if label == "Sequence 2":
            self._start_maf_sequence_v2()
            return
        emit_ui_log(f"[{label}] sequence placeholder pressed (no action yet)")

    def _register_sequence_runner(
        self,
        name: str,
        thread: threading.Thread,
        cancel_callback: Optional[Callable[[], None]] = None,
    ):
        with self._sequence_lock:
            self._sequence_thread = thread
            self._sequence_name = name
            self._sequence_cancel = cancel_callback
        self._stop_event.clear()

    def _stop_active_sequence(self):
        with self._sequence_lock:
            thread = self._sequence_thread
            cancel_cb = self._sequence_cancel
            name = self._sequence_name
        if not thread:
            return
        emit_ui_log(f"[STOP] Canceling sequence {name or '(unnamed)'}")
        self._stop_event.set()
        if cancel_cb:
            try:
                cancel_cb()
            except Exception as exc:
                emit_ui_log(f"[STOP] Sequence cancel callback error: {exc}")

        def _join_sequence():
            try:
                thread.join(timeout=2.0)
            except Exception as exc:
                emit_ui_log(f"[STOP] Sequence join error: {exc}")
            finally:
                with self._sequence_lock:
                    self._sequence_thread = None
                    self._sequence_cancel = None
                    self._sequence_name = None

        threading.Thread(target=_join_sequence, daemon=True).start()

    # ----- Sequence 1 / MAF integration -----

    def _start_maf_sequence(self):
        with self._sequence_lock:
            if self._sequence_thread and self._sequence_thread.is_alive():
                emit_ui_log("[MAF] Sequence already running")
                return
        emit_ui_log("Sequence 1 begin")

        # <<< NEW: start flow meter from GUI thread >>>
        self._maf_start_flow_meter_ui()

        self._sequence_prompt_title = "Sequence 1 Step"
        thread = threading.Thread(target=self._run_maf_sequence, daemon=True)
        self._register_sequence_runner("MAF Sequence", thread, cancel_callback=self._cancel_maf_sequence)
        thread.start()

    def _cancel_maf_sequence(self):
        emit_ui_log("[MAF] Cancel requested")
        self._stop_event.set()

    def _run_maf_sequence(self):
        try:
            self._run_sequence_initialization("MAF")
            run_maf_sequence(
                stop_flag=lambda: self._stop_event.is_set(),
                reset_flow_totals=self._maf_reset_flow_totals,
                start_flow_meter=self._maf_start_flow_meter,
                stop_flow_meter=self._maf_stop_flow_meter,
                get_total_volume_ml=self._maf_get_total_volume_ml,
                log=emit_ui_log,
                relays=self.relays,
                motor_pump=self._peristaltic_sequence_adapter,
                pid_controller=self.pid_controller,
                home_pid_valve=self._home_pid_valve_blocking,
                valve1=self._valve1_adapter,
                valve2=self._valve2_adapter,
                syringe=self._syringe_sequence_adapter or _SyringeSequenceAdapter(self.syringe_panel),
                enable_temp_controller=self._maf_enable_temp_controller,
                disable_temp_controller=self._maf_disable_temp_controller,
                wait_for_temp_ready=self._maf_wait_for_temp_ready,
                wait_for_maf_heating=self._maf_wait_for_maf_heating,
                move_horizontal_to_filtering=lambda: self._maf_move_axis_to_preset(
                    "Horizontal Axis", "filtering"
                ),
                move_horizontal_to_waste=lambda: self._maf_move_axis_to_preset(
                    "Horizontal Axis", "filter out"
                ),
                move_horizontal_to_home=lambda: self._maf_move_axis_to_preset(
                    "Horizontal Axis", "filter in"
                ),
                move_vertical_close_plate=lambda: self._maf_move_axis_to_preset(
                    "Vertical Axis", "close"
                ),
                move_vertical_open_plate=lambda: self._maf_move_axis_to_preset(
                    "Vertical Axis", "open"
                ),
                target_volume_ml=self.flow_panel.target_volume_ml() if self.flow_panel else 50.0,
                post_volume_wait_s=2.0,
                # before_step=self._maf_prompt_user_before_step,
            )
            emit_ui_log("Sequence 1 complete")
        except Exception as exc:
            emit_ui_log(f"[MAF] Sequence error: {exc}")
        finally:
            self._stop_event.clear()
            with self._sequence_lock:
                self._sequence_thread = None
                self._sequence_cancel = None
                self._sequence_name = None
            self._sequence_prompt_title = "Sequence Step"

    # ----- Sequence 2 / Alternate MAF integration -----

    def _start_maf_sequence_v2(self):
        with self._sequence_lock:
            if self._sequence_thread and self._sequence_thread.is_alive():
                emit_ui_log("[MAF2] Sequence already running")
                return
        emit_ui_log("Sequence 2 begin")

        # <<< NEW: start flow meter from GUI thread >>>
        self._maf_start_flow_meter_ui()

        self._sequence_prompt_title = "Sequence 2 Step"
        thread = threading.Thread(target=self._run_maf_sequence_v2, daemon=True)
        self._register_sequence_runner(
            "MAF Sequence 2",
            thread,
            cancel_callback=self._cancel_maf_sequence_v2,
        )
        thread.start()

    def _cancel_maf_sequence_v2(self):
        emit_ui_log("[MAF2] Cancel requested")
        self._stop_event.set()

    def _maf_start_flow_meter_ui(self):
        """Reset + start the flow meter safely from the GUI thread."""
        if not self.flow_panel:
            return

        def _do():
            try:
                # Full reset of UI and underlying client
                self.flow_panel._handle_reset()
                # Only start if not already running
                if not self.flow_panel._started:
                    self.flow_panel._handle_start()
            except Exception as exc:
                emit_ui_log(f"[MAF] Flow meter UI start failed: {exc}")

        # We are usually on the GUI thread when sequences are started,
        # but be defensive:
        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            self._invoke_ui(_do)

    def _run_maf_sequence_v2(self):
        try:
            self._run_sequence_initialization("MAF2")
            run_maf_sequence_v2(
                stop_flag=lambda: self._stop_event.is_set(),
                reset_flow_and_timer=self._maf_reset_flow_readings,
                get_total_volume_ml=self._maf_get_total_volume_ml,
                log=emit_ui_log,
                relays=self.relays,
                motor_pump=self._peristaltic_sequence_adapter,
                pid_controller=self.pid_controller,
                valve1=self._valve1_adapter,
                valve2=self._valve2_adapter,
                syringe=self._syringe_sequence_adapter or _SyringeSequenceAdapter(self.syringe_panel),
                enable_temp_controller=self._maf_enable_temp_controller,
                disable_temp_controller=self._maf_disable_temp_controller,
                wait_for_temp_ready=self._maf_wait_for_temp_ready,
                wait_for_maf_heating=self._maf_wait_for_maf_heating,
                move_horizontal_to_filtering=lambda: self._maf_move_axis_to_preset(
                    "Horizontal Axis", "filtering"
                ),
                move_horizontal_to_waste=lambda: self._maf_move_axis_to_preset(
                    "Horizontal Axis", "filter out"
                ),
                move_horizontal_to_home=lambda: self._maf_move_axis_to_preset(
                    "Horizontal Axis", "filter in"
                ),
                move_vertical_close_plate=lambda: self._maf_move_axis_to_preset(
                    "Vertical Axis", "close"
                ),
                move_vertical_open_plate=lambda: self._maf_move_axis_to_preset(
                    "Vertical Axis", "open"
                ),
                target_volume_ml=self.flow_panel.target_volume_ml() if self.flow_panel else 50.0,
                post_volume_wait_s=2.0,
                # before_step=self._maf_prompt_user_before_step,
            )
            emit_ui_log("Sequence 2 complete")
        except Exception as exc:
            emit_ui_log(f"[MAF2] Sequence error: {exc}")
        finally:
            self._stop_event.clear()
            with self._sequence_lock:
                self._sequence_thread = None
            self._sequence_cancel = None
            self._sequence_name = None
        self._sequence_prompt_title = "Sequence Step"

    # ----- Cleaning sequence integration -----

    def _start_cleaning_sequence(self):
        with self._sequence_lock:
            if self._sequence_thread and self._sequence_thread.is_alive():
                emit_ui_log("[Cleaning] Sequence already running")
                return
        emit_ui_log("Cleaning sequence begin")
        # Keep elapsed timer in sync with sequences
        self._maf_start_flow_meter_ui()
        self._sequence_prompt_title = "Cleaning Step"
        thread = threading.Thread(target=self._run_cleaning_sequence, daemon=True)
        self._register_sequence_runner(
            "Cleaning Sequence",
            thread,
            cancel_callback=self._cancel_cleaning_sequence,
        )
        thread.start()

    def _cancel_cleaning_sequence(self):
        emit_ui_log("[Cleaning] Cancel requested")
        self._stop_event.set()

    def _run_cleaning_sequence(self):
        try:
            self._run_sequence_initialization("CLEAN")
            run_maf_cleaning_sequence(
                stop_flag=lambda: self._stop_event.is_set(),
                log=emit_ui_log,
                relays=self.relays,
                motor_pump=self._peristaltic_sequence_adapter,
                pid_controller=self.pid_controller,
                home_pid_valve=self._home_pid_valve_blocking,
                move_horizontal_to_filtering=lambda: self._maf_move_axis_to_preset(
                    "Horizontal Axis", "filtering"
                ),
                move_horizontal_to_home=lambda: self._maf_move_axis_to_preset(
                    "Horizontal Axis", "filter in"
                ),
                move_vertical_close_plate=lambda: self._maf_move_axis_to_preset(
                    "Vertical Axis", "close"
                ),
                move_vertical_open_plate=lambda: self._maf_move_axis_to_preset(
                    "Vertical Axis", "open"
                ),
                before_step=self._prompt_user_on_prompts,
            )
            emit_ui_log("Cleaning sequence complete")
        except Exception as exc:
            emit_ui_log(f"[Cleaning] Sequence error: {exc}")
        finally:
            self._stop_event.clear()
            with self._sequence_lock:
                self._sequence_thread = None
                self._sequence_cancel = None
                self._sequence_name = None
            self._sequence_prompt_title = "Sequence Step"

    def _run_sequence_initialization(self, tag: str):
        emit_ui_log(f"[{tag}] Pre-sequence initialization start")
        if self._init_running:
            raise RuntimeError("Initialization already in progress")
        self._init_abort.clear()
        try:
            self._init_devices()
        except Exception as exc:
            raise RuntimeError(f"{tag} initialization failed: {exc}") from exc
        emit_ui_log(f"[{tag}] Pre-sequence initialization complete")

    def _maf_reset_flow_totals(self):
        """Reset flow totals without starting the UI stream."""
        if self.flow_panel:
            def _reset_ui():
                try:
                    self.flow_panel._handle_reset()
                except Exception as exc:
                    emit_ui_log(f"[MAF] Flow panel reset failed: {exc}")
            if threading.current_thread() is threading.main_thread():
                _reset_ui()
            else:
                self._invoke_ui(_reset_ui)
        sensor = getattr(self, "flow_meter", None)
        if sensor and hasattr(sensor, "reset_totals"):
            try:
                sensor.reset_totals()
            except Exception as exc:
                emit_ui_log(f"[MAF] Flow sensor reset failed: {exc}")

    def _maf_start_flow_meter(self):
        """Reset totals and start the flow meter UI stream."""
        if self.flow_panel:
            def _reset_and_start():
                try:
                    self.flow_panel._handle_reset()
                    self.flow_panel._handle_start()
                except Exception as exc:
                    emit_ui_log(f"[MAF] Flow panel start failed: {exc}")
            if threading.current_thread() is threading.main_thread():
                _reset_and_start()
            else:
                self._invoke_ui(_reset_and_start)
        sensor = getattr(self, "flow_meter", None)
        if sensor and hasattr(sensor, "reset_totals"):
            try:
                sensor.reset_totals()
            except Exception as exc:
                emit_ui_log(f"[MAF] Flow sensor reset failed: {exc}")

    def _maf_stop_flow_meter(self):
        """Stop flow readings but leave the elapsed timer untouched."""
        if self.flow_panel:
            def _stop_only():
                try:
                    self.flow_panel._stop_stream()
                except Exception as exc:
                    emit_ui_log(f"[MAF] Flow panel stop failed: {exc}")
            if threading.current_thread() is threading.main_thread():
                _stop_only()
            else:
                self._invoke_ui(_stop_only)

    # Backward compatibility for MAF_Sequence_2 signature
    def _maf_reset_flow_readings(self):
        self._maf_reset_flow_totals()

    def _maf_get_total_volume_ml(self) -> float:
        sensor = getattr(self, "flow_meter", None)
        total_liters = getattr(sensor, "_total_liters", None)
        if total_liters is None:
            return 0.0
        try:
            return float(total_liters) * 1000.0
        except Exception:
            return 0.0

    def _maf_enable_temp_controller(self):
        if self.temperature_panel:
            self.temperature_panel._handle_command_on()

    def _maf_disable_temp_controller(self):
        if self.temperature_panel:
            self.temperature_panel._handle_command_off()

    def _maf_wait_for_temp_ready(self, timeout: float = 120.0):
        if not self.temperature_panel:
            return
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._stop_event.is_set():
                raise InterruptedError("Sequence canceled")
            state = self.temperature_panel._read_ready_state()
            if state:
                return
            time.sleep(0.5)
        raise RuntimeError("Temperature controller ready timeout")

    def _maf_wait_for_maf_heating(self, duration: float = 10.0):    # 14 mins total = 840 sec (4 mins for MAF to reach temperature plus 10 mins for lising)
        end = time.time() + duration
        while time.time() < end:
            if self._stop_event.is_set():
                raise InterruptedError("Sequence canceled")
            time.sleep(0.5)

    def _maf_move_axis_to_preset(self, axis_name: str, preset_key: str):
        ctrl = self._get_axis_control(axis_name)
        if ctrl is None:
            raise RuntimeError(f"{axis_name} control unavailable")
        ctrl._check_pre_move(raise_on_block=True)
        presets = AXIS_PRESET_POSITIONS.get(axis_name, {})
        target_info = presets.get(preset_key)
        if target_info is None:
            raise RuntimeError(f"No preset '{preset_key}' configured for {axis_name}")
        _, target_mm = target_info
        if not ctrl.driver.ready:
            raise RuntimeError(f"{axis_name} not connected")
        rpm = SEQUENCE_AXIS_SPEED_RPM
        ctrl.driver.move_to_mm(target_mm, rpm, context=f"sequence:{preset_key}")
        ctrl.set_cached_position_mm(target_mm)
        ctrl._emit_motion_callbacks()

    def _maf_prompt_user_before_step(self, label: str):
        # Prompt disabled: no dialog or wait.
        return

    def _prompt_user_on_prompts(self, label: str):
        """Block on user confirmation for prompt-only steps."""
        if "Prompt message" not in label:
            return
        self._sequence_prompt_event.clear()
        # Emit signal so the dialog runs on the UI thread
        self.sequence_prompt_signal.emit(label)
        # Wait until user clicks Continue or Cancel; cancel sets stop_event inside dialog.
        self._sequence_prompt_event.wait()

    def _show_sequence_prompt_dialog(self, label: str):
        msg = QMessageBox(self)
        msg.setWindowTitle(self._sequence_prompt_title or "Sequence Step")
        msg.setText(f"Next step:\n\n{label}\n\nPress Continue to execute this step.")
        msg.setStyleSheet(
            "QLabel {color: #f8fafc; font-size: 14px;}"
            "QPushButton {font-weight: 600; padding: 4px 12px; background-color: #e5e7eb; color: #111827; border-radius: 4px;}"
            "QPushButton:pressed {background-color: #cbd5f5;}"
            "QMessageBox {background-color: #0f172a; color: #f8fafc;}"
        )
        continue_btn = msg.addButton("Continue", QMessageBox.AcceptRole)
        cancel_btn = msg.addButton("Cancel Sequence", QMessageBox.RejectRole)
        msg.setIcon(QMessageBox.Information)
        msg.exec_()
        clicked = msg.clickedButton()
        if clicked == cancel_btn:
            self._stop_event.set()
        self._sequence_prompt_event.set()

    def _home_pid_valve_async(self):
        def _home():
            try:
                emit_ui_log("[PID] Homing valve after STOP")
                self.pid_controller.homing_routine()
                emit_ui_log("[PID] Valve homed")
            except Exception as exc:
                emit_ui_log(f"[PID] Homing error after STOP: {exc}")

        threading.Thread(target=_home, daemon=True).start()

    def _home_pid_valve_blocking(self):
        """Home the PID valve synchronously for sequence steps."""
        try:
            emit_ui_log("[PID] Starting PID valve homing")
            self.pid_controller.homing_routine()
            emit_ui_log("[PID] PID valve homed")
        except Exception as exc:
            emit_ui_log(f"[PID] Homing error: {exc}")
            raise

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
                # Ensure Valve 1 is open during syringe homing
                emit_ui_log("[Syringe] Opening Valve 1 (relay 1) for homing")
                relay_on = self._set_relay_state(1, True)
                if not relay_on:
                    emit_ui_log("[Syringe] Relay 1 failed to turn ON before homing; continuing homing anyway")
                time.sleep(0.2)
                self.syringe_panel.home_blocking()
                emit_ui_log("[Syringe] Homed and at standstill")
                # Close Valve 1 after homing completes
                self._set_relay_state(1, False)
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
        controller = getattr(self, "pid_controller", None)
        if controller:
            disable_wait = False
            if getattr(controller, "enabled", False):
                try:
                    controller.set_enabled(False)
                    disable_wait = True
                    emit_ui_log("[PID] Disabled before initialization homing")
                except Exception as exc:
                    emit_ui_log(f"[PID] Failed to disable before homing: {exc}")
                if self.pid_panel:
                    self._invoke_ui(self.pid_panel.force_stop)
            if disable_wait:
                time.sleep(0.5)
            try:
                controller.homing_routine()
                emit_ui_log("[PID] Valve homed for initialization")
            except Exception as exc:
                emit_ui_log(f"[PID] Homing during initialization failed: {exc}")
        self._force_peltier_off_for_init()

    def _force_peltier_off_for_init(self):
        panel = getattr(self, "temperature_panel", None)
        if panel:
            def _force_off():
                try:
                    panel.force_stop()
                    emit_ui_log("[TempCtrl] Peltier forced OFF for initialization")
                except Exception as exc:
                    emit_ui_log(f"[TempCtrl] Failed to force OFF for initialization: {exc}")
            self._invoke_ui(_force_off)
        else:
            try:
                safe_plc_call("digital_write", plc.digital_write,TEMP_COMMAND_PIN, False)
                emit_ui_log("[TempCtrl] Peltier command pin forced OFF (no panel)")
            except Exception as exc:
                emit_ui_log(f"[TempCtrl] Unable to force Peltier OFF: {exc}")

    def _ensure_relays_off_before_connect(self):
        if self.relays and any(self.relay_states.values()):
            emit_ui_log("[Relays] Forcing ALL OFF before initialization")
            self._relays_all_off(auto=False)

    def _get_axis_control(self, name: str) -> Optional["StepperAxisControl"]:
        return next((ctrl for ctrl in self.axis_controls if ctrl.name == name), None)

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
        grid.setHorizontalSpacing(10 if title is None else 6)
        grid.setVerticalSpacing(10 if title is None else 8)

        cols = 3 if title is None else max(1, int(len(mapping) ** 0.5))
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
