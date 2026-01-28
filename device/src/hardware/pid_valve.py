import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from simple_pid import PID

from infra.config import PidValveConfig
from hardware.plc_utils import plc, safe_plc_call, ensure_plc_init


@dataclass
class PidValveState:
    enabled: bool = False
    setpoint: float = 1.0
    hall_state: Optional[int] = None


class PidValveController:
    def __init__(self, config: PidValveConfig, get_flow_func: Callable[[], float]) -> None:
        self.config = config
        self._get_flow = get_flow_func
        self.state = PidValveState(enabled=False, setpoint=float(config.setpoint_default))
        self.pid = PID(config.pid_kp, config.pid_ki, config.pid_kd, setpoint=self.state.setpoint)
        self.pid.sample_time = config.sample_time
        self.pid.output_limits = (config.output_min, config.output_max)

        ensure_plc_init()
        if plc:
            for pin in (config.step_pin, config.dir_pin, config.en_pin):
                safe_plc_call("pin_mode", plc.pin_mode, pin, plc.OUTPUT)
            safe_plc_call("pin_mode", plc.pin_mode, config.hall_pin, plc.INPUT)

        self._loop_interval = max(config.sample_time, 0.05)
        self._start_hall_monitor()
        threading.Thread(target=self._control_loop, daemon=True).start()

    def set_enabled(self, enabled: bool) -> None:
        self.state.enabled = bool(enabled)
        # EN pin is active-low in legacy wiring.
        if plc:
            safe_plc_call("digital_write", plc.digital_write, self.config.en_pin, not enabled)

    def set_setpoint(self, value: float) -> None:
        self.state.setpoint = float(value)
        self.pid.setpoint = self.state.setpoint

    def _step_valve(self, direction: bool, steps: int = 20) -> None:
        if not plc:
            return
        safe_plc_call("digital_write", plc.digital_write, self.config.dir_pin, direction)
        time.sleep(0.001)
        for _ in range(steps):
            safe_plc_call("digital_write", plc.digital_write, self.config.step_pin, True)
            time.sleep(0.00002)
            safe_plc_call("digital_write", plc.digital_write, self.config.step_pin, False)
            time.sleep(0.00002)

    def _control_loop(self) -> None:
        while True:
            if self.state.enabled:
                flow = float(self._get_flow() or 0.0)
                output = self.pid(flow)
                steps = int(abs(output) * 8)
                if steps:
                    self._step_valve(direction=(output > 0), steps=steps)
            time.sleep(self._loop_interval)

    def _start_hall_monitor(self) -> None:
        def monitor():
            while True:
                val = safe_plc_call("digital_read", plc.digital_read, self.config.hall_pin)
                if isinstance(val, int):
                    self.state.hall_state = val
                time.sleep(1.0)

        threading.Thread(target=monitor, daemon=True).start()

    def homing_routine(self) -> None:
        if not plc:
            return
        safe_plc_call("digital_write", plc.digital_write, self.config.en_pin, False)
        safe_plc_call("digital_write", plc.digital_write, self.config.dir_pin, False)
        # Match legacy GUI behavior: step while hall reads 1, stop when it drops to 0.
        while True:
            val = safe_plc_call("digital_read", plc.digital_read, self.config.hall_pin)
            if not isinstance(val, int):
                val = 0
            if val == 0:
                break
            safe_plc_call("digital_write", plc.digital_write, self.config.step_pin, True)
            time.sleep(0.001)
            safe_plc_call("digital_write", plc.digital_write, self.config.step_pin, False)
            time.sleep(0.001)
        safe_plc_call("digital_write", plc.digital_write, self.config.en_pin, True)

    def force_close(self, timeout: float = 8.0) -> None:
        if not plc:
            return
        safe_plc_call("digital_write", plc.digital_write, self.config.en_pin, False)
        deadline = time.time() + max(timeout, 1.0)
        while True:
            val = safe_plc_call("digital_read", plc.digital_read, self.config.hall_pin)
            if isinstance(val, int) and val == 1:
                break
            self._step_valve(direction=True, steps=1500)
            if time.time() > deadline:
                safe_plc_call("digital_write", plc.digital_write, self.config.en_pin, True)
                raise RuntimeError("PID valve close timed out")
        safe_plc_call("digital_write", plc.digital_write, self.config.en_pin, True)
