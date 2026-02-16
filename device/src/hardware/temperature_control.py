from dataclasses import dataclass
from typing import Optional
import threading
import time

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO.setwarnings(False)
except Exception:
    GPIO = None

from infra.config import TemperatureConfig
from hardware.plc_utils import plc, safe_plc_call, ensure_plc_init

try:
    from mecom import MeComSerial, ResponseException, WrongChecksum  # type: ignore
    from serial import SerialException  # type: ignore
    from serial.serialutil import PortNotOpenError  # type: ignore
except Exception:
    MeComSerial = None
    ResponseException = Exception
    WrongChecksum = Exception
    SerialException = Exception
    PortNotOpenError = Exception


@dataclass
class TemperatureState:
    enabled: bool = False
    ready: Optional[bool] = None
    target_c: float = 58.0
    current_c: Optional[float] = None
    error: Optional[str] = None


class _TecDriver:
    def __init__(
        self,
        port: str,
        channel: int,
        address: Optional[int] = None,
        baudrate: int = 57600,
        timeout_s: float = 0.35,
    ) -> None:
        if MeComSerial is None:
            raise RuntimeError("pyMeCom is not available in this environment")
        self.port = port
        self.channel = int(channel)
        self.address = None if address is None else int(address)
        self.baudrate = int(baudrate)
        self.timeout_s = float(timeout_s)
        self._session = None
        self._address = None
        self._lock = threading.Lock()

    def _connect(self) -> None:
        if self._session is not None and self._address is not None:
            return
        kwargs = {
            "serialport": self.port,
            "baudrate": self.baudrate,
        }
        try:
            kwargs["timeout"] = self.timeout_s
            self._session = MeComSerial(**kwargs)
        except TypeError:
            kwargs.pop("timeout", None)
            self._session = MeComSerial(**kwargs)
        if self.address is not None:
            self._address = int(self.address)
        else:
            self._address = self._session.identify()

    def _reset(self) -> None:
        if self._session is not None:
            try:
                self._session.stop()
            except Exception:
                pass
        self._session = None
        self._address = None

    def _with_retry(self, func):
        with self._lock:
            for attempt in range(2):
                try:
                    self._connect()
                    return func(self._session, self._address)
                except (ResponseException, WrongChecksum, SerialException, PortNotOpenError):
                    self._reset()
                    if attempt >= 1:
                        raise

    def set_target_c(self, value: float) -> None:
        v = float(value)
        self._with_retry(
            lambda s, a: s.set_parameter(
                parameter_id=3000, value=v, address=a, parameter_instance=self.channel
            )
        )

    def set_enabled(self, enabled: bool) -> None:
        v = 1 if enabled else 0
        self._with_retry(
            lambda s, a: s.set_parameter(
                value=v, parameter_id=2010, address=a, parameter_instance=self.channel
            )
        )

    def read_current_c(self) -> float:
        return float(
            self._with_retry(
                lambda s, a: s.get_parameter(
                    parameter_id=1000, address=a, parameter_instance=self.channel
                )
            )
        )

    def read_stable_flag(self) -> Optional[bool]:
        try:
            v = self._with_retry(
                lambda s, a: s.get_parameter(
                    parameter_id=1200, address=a, parameter_instance=self.channel
                )
            )
            # MeCom 1200 semantics:
            # 0 = regulation not active, 1 = not stable, 2 = stable
            iv = int(v)
            if iv == 2:
                return True
            if iv in (0, 1):
                return False
            return None
        except Exception:
            return None


class TemperatureController:
    def __init__(self, config: TemperatureConfig) -> None:
        self.config = config
        self._lock = threading.Lock()
        self.state = TemperatureState(
            enabled=False,
            ready=None,
            target_c=float(config.tec_default_target_c),
            current_c=None,
            error=None,
        )
        self._poll_stop = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None
        ensure_plc_init()
        if plc:
            safe_plc_call("pin_mode", plc.pin_mode, config.command_pin, plc.OUTPUT)
            safe_plc_call("digital_write", plc.digital_write, config.command_pin, False)
            safe_plc_call("pin_mode", plc.pin_mode, config.ready_pin, plc.INPUT)

        self._gpio_ready_ok = False
        if GPIO is not None:
            try:
                if GPIO.getmode() is None:
                    GPIO.setmode(GPIO.BCM)
                GPIO.setup(config.ready_gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                self._gpio_ready_ok = True
            except Exception:
                self._gpio_ready_ok = False

        self._tec = None
        if config.tec_port:
            try:
                self._tec = _TecDriver(
                    config.tec_port,
                    config.tec_channel,
                    address=config.tec_address,
                    baudrate=config.tec_baudrate,
                    timeout_s=config.tec_timeout_s,
                )
            except Exception as exc:
                with self._lock:
                    self.state.error = f"TEC init failed: {exc}"
        else:
            with self._lock:
                self.state.error = "TEC disabled: temperature.tec_port is not configured"

        if self._tec is not None:
            self._start_polling()

    def set_target_c(self, target_c: float) -> None:
        value = float(target_c)
        with self._lock:
            self.state.target_c = value
            enabled = bool(self.state.enabled)
        # Requested behavior:
        # - Apply should power the TEC controller so communication is available.
        # - Apply should send the target immediately.
        # - Heating must remain OFF until set_enabled(True) is called.
        if plc and not enabled:
            safe_plc_call("digital_write", plc.digital_write, self.config.command_pin, True)
            # Give TEC comms a brief warm-up after controller power is applied.
            time.sleep(0.25)
        if self._tec is None:
            msg = "TEC set target failed: controller unavailable"
            with self._lock:
                self.state.error = msg
            raise RuntimeError(msg)
        try:
            self._tec.set_target_c(value)
            # Keep heating loop disabled after target apply.
            self._tec.set_enabled(False)
            with self._lock:
                self.state.error = None
        except Exception as exc:
            with self._lock:
                self.state.error = f"TEC set target failed: {exc}"
                err = self.state.error
            raise RuntimeError(err)

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.state.enabled = bool(enabled)
        if plc:
            safe_plc_call("digital_write", plc.digital_write, self.config.command_pin, enabled)
        if self._tec is not None:
            if not enabled:
                # Turning OFF should be best-effort and quiet.
                try:
                    self._tec.set_enabled(False)
                except Exception:
                    pass
                with self._lock:
                    self.state.ready = False
                    self.state.error = None
                return
            try:
                # Ensure target is pushed before enabling control loop.
                with self._lock:
                    target_c = self.state.target_c
                self._tec.set_target_c(target_c)
                self._tec.set_enabled(bool(enabled))
                with self._lock:
                    self.state.error = None
            except Exception as exc:
                with self._lock:
                    self.state.error = f"TEC enable failed: {exc}"
                    err = self.state.error
                raise RuntimeError(err)

    def force_off(self) -> None:
        self.set_enabled(False)

    def read_current_c(self) -> Optional[float]:
        with self._lock:
            return self.state.current_c

    def read_ready(self) -> Optional[bool]:
        if self._tec is not None:
            with self._lock:
                return self.state.ready
        return self._read_ready_from_inputs()

    def _read_ready_from_inputs(self) -> Optional[bool]:
        ready: Optional[bool] = None

        # Prefer GPIO ready if configured/available (external sensor)
        if GPIO is not None:
            try:
                if not self._gpio_ready_ok:
                    if GPIO.getmode() is None:
                        GPIO.setmode(GPIO.BCM)
                    GPIO.setup(self.config.ready_gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                    self._gpio_ready_ok = True
                ready = bool(GPIO.input(self.config.ready_gpio_pin))
                with self._lock:
                    self.state.ready = ready
                return ready
            except Exception:
                self._gpio_ready_ok = False
        if plc:
            val = safe_plc_call("digital_read", plc.digital_read, self.config.ready_pin)
            if isinstance(val, int):
                ready = bool(val)
                with self._lock:
                    self.state.ready = ready
                return ready
        with self._lock:
            self.state.ready = None
        return ready

    def _sample_tec(self) -> None:
        if self._tec is None:
            return
        with self._lock:
            enabled = bool(self.state.enabled)
        if not enabled:
            # Requested behavior: no TEC read errors while controller is OFF.
            with self._lock:
                self.state.ready = False
                self.state.error = None
            return
        current: Optional[float] = None
        ready: Optional[bool] = None
        err: Optional[str] = None

        try:
            current = float(self._tec.read_current_c())
            stable = self._tec.read_stable_flag()
            with self._lock:
                target_c = self.state.target_c
            close_to_target = abs(current - target_c) <= float(self.config.tec_ready_tolerance_c)
            ready = bool(stable) if stable is not None else close_to_target
        except Exception as exc:
            err = f"TEC read failed: {exc}"

        with self._lock:
            self.state.current_c = current
            self.state.ready = ready
            self.state.error = err

    def _poll_loop(self, interval_s: float) -> None:
        while not self._poll_stop.is_set():
            self._sample_tec()
            self._poll_stop.wait(interval_s)

    def _start_polling(self) -> None:
        if self._poll_thread and self._poll_thread.is_alive():
            return
        interval_s = max(0.1, float(self.config.tec_poll_interval_s))
        self._poll_stop.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop, args=(interval_s,), daemon=True
        )
        self._poll_thread.start()
