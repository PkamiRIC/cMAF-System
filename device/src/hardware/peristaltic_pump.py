from dataclasses import dataclass
from typing import Optional

from infra.config import PeristalticConfig
from hardware.plc_utils import plc, safe_plc_call, ensure_plc_init


@dataclass
class PeristalticState:
    enabled: bool = False
    direction_forward: bool = True
    low_speed: bool = False


class PeristalticPump:
    def __init__(self, config: PeristalticConfig) -> None:
        self.config = config
        self.state = PeristalticState()
        ensure_plc_init()
        if plc:
            for pin in (
                config.enable_pin,
                config.dir_forward_pin,
                config.dir_reverse_pin,
                config.speed_pin,
            ):
                safe_plc_call("pin_mode", plc.pin_mode, pin, plc.OUTPUT)
                safe_plc_call("digital_write", plc.digital_write, pin, False)

    def set_enabled(self, enabled: bool) -> None:
        # Enable pin is active-low in legacy wiring.
        if plc:
            safe_plc_call("digital_write", plc.digital_write, self.config.enable_pin, not enabled)
        self.state.enabled = bool(enabled)

    def set_direction(self, forward: bool) -> None:
        if plc:
            safe_plc_call("digital_write", plc.digital_write, self.config.dir_forward_pin, forward)
            safe_plc_call("digital_write", plc.digital_write, self.config.dir_reverse_pin, not forward)
        self.state.direction_forward = bool(forward)

    def set_speed_checked(self, checked: bool) -> None:
        # Legacy UI: checked => LOW speed. unchecked => HIGH speed.
        if plc:
            safe_plc_call("digital_write", plc.digital_write, self.config.speed_pin, checked)
        self.state.low_speed = bool(checked)

    def force_stop(self) -> None:
        self.set_enabled(False)
        self.set_direction(True)
        self.set_speed_checked(False)

    def snapshot(self) -> PeristalticState:
        return self.state
