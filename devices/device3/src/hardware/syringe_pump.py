import struct
import time
from typing import Optional, Callable
import threading
import serial

from infra.config import SyringeConfig, AxisConfig


class SyringePump:
    # One lock per serial port path (e.g. /dev/ttyUSB0)
    _port_locks: dict[str, threading.Lock] = {}
    _port_locks_guard = threading.Lock()

    def __init__(self, config: SyringeConfig | AxisConfig) -> None:
        self.config = config
        self.target_position = 0

    def _port_lock(self) -> threading.Lock:
        key = str(self.config.port)
        with self._port_locks_guard:
            lock = self._port_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._port_locks[key] = lock
            return lock

    def _open_serial(self, timeout: Optional[float] = None) -> serial.Serial:
        ser = serial.Serial(
            port=self.config.port,
            baudrate=self.config.baudrate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=self.config.timeout if timeout is None else timeout,
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
        return struct.pack("<H", crc)

    def _steps_from_volume(self, volume_ml: float) -> int:
        return int(volume_ml * self.config.steps_per_ml)

    @staticmethod
    def _int_to_4byte_big_endian(val: int) -> bytes:
        return val.to_bytes(4, byteorder="big", signed=True)

    def _build_command(self, volume_ml: float, flow_rate_ml_per_min: float) -> bytes:
        flow_rate_ml_per_min = max(min(flow_rate_ml_per_min, 15), -15)

        if abs(volume_ml) > 180:
            raise ValueError("Volume must not exceed 180 mL")

        velocity_decimal = int(self.config.velocity_calib * flow_rate_ml_per_min)
        steps = self._steps_from_volume(volume_ml)
        self.target_position = steps

        base_command = bytearray(
            [
                self.config.address,
                0x10,
                0xA7,
                0x9E,
                0x00,
                0x07,
                0x0E,
                0x01,
                0x00,
                0x00,
                0x03,
                0x03,
                0xE8,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
            ]
        )

        velocity_bytes = self._int_to_4byte_big_endian(velocity_decimal)
        steps_bytes = self._int_to_4byte_big_endian(steps)
        base_command[13:17] = velocity_bytes
        base_command[17:21] = steps_bytes

        crc = self._crc16(base_command)
        return base_command + crc

    def _send_command(self, command: bytes) -> bytes:
        # IMPORTANT: lock serial port access to prevent concurrent poll/write collisions
        with self._port_lock():
            with self._open_serial(timeout=0.5) as ser:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                ser.flush()
                ser.write(command)
                time.sleep(0.5)
                return ser.read(30)

    # Public API -------------------------------------------------
    def goto_absolute(self, volume_ml: float, flow_rate_ml_min: float) -> None:
        """Move plunger to absolute volume target."""
        command = self._build_command(volume_ml, flow_rate_ml_min)
        self._send_command(command)

    def stop_motion(self, volume_hint_ml: Optional[float] = None) -> bool:
        """
        Best-effort soft stop:
        - Try reading current position and re-command that same point with zero flow.
        - If a recent volume hint is provided, fall back to it when live read fails.
        """
        status = self.read_status(max_tries=3)
        current_ml: Optional[float] = None

        if status:
            try:
                current_ml = float(status.get("volume_ml", None))
            except Exception:
                current_ml = None

        if current_ml is None:
            current_ml = volume_hint_ml

        if current_ml is None:
            return False

        try:
            # Zero flow re-issues the position with no additional travel.
            self.goto_absolute(current_ml, 0.0)
            return True
        except Exception:
            return False

    def move(self, volume_ml: float, flow_rate_ml_min: float) -> None:
        """Alias kept for compatibility with the old GUI code."""
        self.goto_absolute(volume_ml, flow_rate_ml_min)

    def read_status(self, max_tries: int = 5) -> Optional[dict]:
        """
        Query DDS5 status & live data.
        Returns a dict or None if communication fails.
        """
        poll = bytearray([self.config.address, 0x03, 0xA7, 0x3A, 0x00, 0x07])
        poll += self._crc16(poll)

        tries = 0
        while tries < max_tries:
            tries += 1
            try:
                # IMPORTANT: lock serial port access to prevent concurrent poll/write collisions
                with self._port_lock():
                    with self._open_serial(timeout=2.0) as ser:
                        ser.reset_input_buffer()
                        ser.reset_output_buffer()
                        ser.flush()
                        ser.write(poll)
                        time.sleep(0.2)
                        resp = ser.read(19)
            except Exception:
                time.sleep(0.2)
                continue

            if len(resp) != 19:
                time.sleep(0.2)
                continue
            if resp[0] != self.config.address or resp[1] != 0x03 or resp[2] != 0x0E:
                time.sleep(0.2)
                continue
            if self._crc16(resp[:-2]) != resp[-2:]:
                time.sleep(0.2)
                continue

            sdw = int.from_bytes(resp[3:7], "big")
            busy = (sdw >> 8) & 1
            standstill = (sdw >> 12) & 1
            vel_ok = (sdw >> 14) & 1
            pos_ok = (sdw >> 15) & 1
            mode = (sdw >> 24) & 0b111

            actual_velocity = int.from_bytes(resp[9:13], "big", signed=True)
            actual_position = int.from_bytes(resp[13:17], "big", signed=True)

            volume_ml = actual_position / self.config.steps_per_ml
            flow_ml_min = round(actual_velocity / self.config.velocity_calib, 4)

            return {
                "sdw": sdw,
                "mode": mode,
                "busy": busy,
                "standstill": standstill,
                "vel_ok": vel_ok,
                "pos_ok": pos_ok,
                "actual_velocity": actual_velocity,
                "actual_position": actual_position,
                "volume_ml": volume_ml,
                "flow_ml_min": flow_ml_min,
            }

        return None

    def wait_until_idle(
        self,
        timeout: Optional[float] = None,
        stop_flag: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """
        Wait until the drive reports idle.
        Returns False on timeout or if stop_flag() becomes True.
        """
        start_time = time.time()
        while True:
            if stop_flag and stop_flag():
                return False
            status = self.read_status()
            if status is not None and status.get("busy") == 0:
                return True
            if timeout is not None and (time.time() - start_time) >= timeout:
                return False
            time.sleep(0.5)

    def home(self, stop_flag: Optional[Callable[[], bool]] = None) -> None:
        """Send homing frames and wait until the pump reports idle."""

        def _make_home_cmd(flag_byte: int) -> bytes:
            frame = bytearray(
                [
                    self.config.address,
                    0x10,
                    0xA7,
                    0x9E,
                    0x00,
                    0x07,
                    0x0E,
                    0x07,
                    0x00,
                    flag_byte,
                    0x03,
                    0x01,
                    0xF4,
                    0x00,
                    0x00,
                    0x03,
                    0xE8,
                    0x00,
                    0x00,
                    0x27,
                    0x10,
                ]
            )
            frame += self._crc16(frame)
            return frame

        cmd1 = _make_home_cmd(0x00)
        cmd2 = _make_home_cmd(0x02)

        try:
            # IMPORTANT: lock serial port access to prevent concurrent poll/write collisions
            with self._port_lock():
                with self._open_serial(timeout=1.0) as ser:
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()

                    ser.write(cmd1)
                    ser.flush()
                    time.sleep(0.2)
                    ser.read(8)

                    ser.write(cmd2)
                    ser.flush()
                    time.sleep(0.2)
                    ser.read(8)
        except Exception:
            return

        self.wait_until_idle(timeout=60, stop_flag=stop_flag)
