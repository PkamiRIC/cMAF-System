from dataclasses import dataclass
from typing import Optional
import threading

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
    def __init__(self, port: str, channel: int) -> None:
        if MeComSerial is None:
            raise RuntimeError("pyMeCom is not available in this environment")
        self.port = port
        self.channel = int(channel)
        self._session = None
        self._address = None
        self._lock = threading.Lock()

    def _connect(self) -> None:
        if self._session is not None and self._address is not None:
            return
        self._session = MeComSerial(serialport=self.port)
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
                value=v, parameter_name="Status", address=a, parameter_instance=self.channel
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
            return bool(int(v))
        except Exception:
            return None


class TemperatureController:
    def __init__(self, config: TemperatureConfig) -> None:
        self.config = config
        self.state = TemperatureState(
            enabled=False,
            ready=None,
            target_c=float(config.tec_default_target_c),
            current_c=None,
            error=None,
        )
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
                self._tec = _TecDriver(config.tec_port, config.tec_channel)
            except Exception as exc:
                self.state.error = f"TEC init failed: {exc}"

    def set_target_c(self, target_c: float) -> None:
        value = float(target_c)
        self.state.target_c = value
        if self._tec is None:
            return
        try:
            self._tec.set_target_c(value)
            self.state.error = None
        except Exception as exc:
            self.state.error = f"TEC set target failed: {exc}"
            raise RuntimeError(self.state.error)

    def set_enabled(self, enabled: bool) -> None:
        self.state.enabled = bool(enabled)
        if plc:
            safe_plc_call("digital_write", plc.digital_write, self.config.command_pin, enabled)
        if self._tec is not None:
            try:
                # Ensure target is pushed before enabling control loop.
                self._tec.set_target_c(self.state.target_c)
                self._tec.set_enabled(bool(enabled))
                self.state.error = None
            except Exception as exc:
                self.state.error = f"TEC enable failed: {exc}"
                raise RuntimeError(self.state.error)

    def force_off(self) -> None:
        self.set_enabled(False)

    def read_current_c(self) -> Optional[float]:
        if self._tec is None:
            self.state.current_c = None
            return None
        try:
            self.state.current_c = float(self._tec.read_current_c())
            self.state.error = None
            return self.state.current_c
        except Exception as exc:
            self.state.error = f"TEC read failed: {exc}"
            self.state.current_c = None
            return None

    def read_ready(self) -> Optional[bool]:
        if self._tec is not None:
            current = self.read_current_c()
            if current is not None:
                stable = self._tec.read_stable_flag()
                close_to_target = abs(current - self.state.target_c) <= float(
                    self.config.tec_ready_tolerance_c
                )
                self.state.ready = bool(stable) if stable is not None else close_to_target
                return self.state.ready

        # Prefer GPIO ready if configured/available (external sensor)
        if GPIO is not None:
            try:
                if not self._gpio_ready_ok:
                    if GPIO.getmode() is None:
                        GPIO.setmode(GPIO.BCM)
                    GPIO.setup(self.config.ready_gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                    self._gpio_ready_ok = True
                self.state.ready = bool(GPIO.input(self.config.ready_gpio_pin))
                return self.state.ready
            except Exception:
                self._gpio_ready_ok = False
        if plc:
            val = safe_plc_call("digital_read", plc.digital_read, self.config.ready_pin)
            if isinstance(val, int):
                self.state.ready = bool(val)
                return self.state.ready
        self.state.ready = None
        return None
