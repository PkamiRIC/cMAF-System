from dataclasses import dataclass
from typing import Optional

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO.setwarnings(False)
except Exception:
    GPIO = None

from infra.config import TemperatureConfig
from hardware.plc_utils import plc, safe_plc_call, ensure_plc_init


@dataclass
class TemperatureState:
    enabled: bool = False
    ready: Optional[bool] = None


class TemperatureController:
    def __init__(self, config: TemperatureConfig) -> None:
        self.config = config
        self.state = TemperatureState(enabled=False, ready=None)
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

    def set_enabled(self, enabled: bool) -> None:
        self.state.enabled = bool(enabled)
        if plc:
            safe_plc_call("digital_write", plc.digital_write, self.config.command_pin, enabled)

    def force_off(self) -> None:
        self.set_enabled(False)

    def read_ready(self) -> Optional[bool]:
        if plc:
            val = safe_plc_call("digital_read", plc.digital_read, self.config.ready_pin)
            if isinstance(val, int):
                self.state.ready = bool(val)
                return self.state.ready
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
        self.state.ready = None
        return None
