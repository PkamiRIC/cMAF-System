from dataclasses import dataclass
from typing import Optional
import threading

import serial

from infra.config import PeristalticConfig
from hardware.plc_utils import plc, safe_plc_call, ensure_plc_init
from hardware.syringe_pump import SyringePump


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
            for pin in (config.enable_pin, config.dir_reverse_pin, config.speed_pin):
                safe_plc_call("pin_mode", plc.pin_mode, pin, plc.OUTPUT)
                safe_plc_call("digital_write", plc.digital_write, pin, False)

    def _port_lock(self) -> threading.Lock:
        key = str(self.config.dir_driver_port)
        with SyringePump._port_locks_guard:
            lock = SyringePump._port_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                SyringePump._port_locks[key] = lock
            return lock

    def _open_serial(self, timeout: Optional[float] = None) -> serial.Serial:
        parity = {
            "N": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
        }.get(self.config.dir_driver_parity.upper(), serial.PARITY_NONE)
        ser = serial.Serial(
            port=self.config.dir_driver_port,
            baudrate=self.config.dir_driver_baudrate,
            parity=parity,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=self.config.dir_driver_timeout if timeout is None else timeout,
        )
        try:
            from serial.rs485 import RS485Settings
            ser.rs485_mode = RS485Settings(delay_before_tx=0, delay_before_rx=0)
        except Exception:
            pass
        return ser

    @staticmethod
    def _crc16(command_bytes) -> bytes:
        crc = 0xFFFF
        for b in command_bytes:
            crc ^= b
            for _ in range(8):
                if crc & 0x01:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc.to_bytes(2, byteorder="little")

    def _send_dir_command(self, value: int) -> None:
        frame = bytearray(
            [
                int(self.config.dir_driver_address),
                0x06,
                0xA4,
                0xF7,
                (value >> 8) & 0xFF,
                value & 0xFF,
            ]
        )
        frame.extend(self._crc16(frame))
        with self._port_lock():
            with self._open_serial(timeout=0.5) as ser:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                ser.write(frame)
                ser.read(8)

    def set_enabled(self, enabled: bool) -> None:
        # Enable pin is active-high for current wiring.
        if plc:
            safe_plc_call("digital_write", plc.digital_write, self.config.enable_pin, enabled)
        self.state.enabled = bool(enabled)

    def set_direction(self, forward: bool) -> None:
        if plc:
            # Q0.2 follows direction state: LOW for CCW, HIGH for CW.
            safe_plc_call("digital_write", plc.digital_write, self.config.dir_reverse_pin, forward)
        try:
            # Forward (CW) => DO1 OFF (0x0081). Reverse (CCW) => DO1 ON (0x0001).
            self._send_dir_command(0x0081 if forward else 0x0001)
        except Exception:
            pass
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
