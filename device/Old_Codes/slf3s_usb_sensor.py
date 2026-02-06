#!/usr/bin/env python3
"""Sensirion SLF3S USB driver (SCC1-USB SHDLC transport).

This module reimplements the USB bridge protocol exactly as described in the
"SLF3x Liquid Flow Sensors – I²C and SCC1-USB" datasheet.  The SCC1 speaks the
Sensirion SHDLC framing protocol: every command is wrapped in 0x7E flags,
escaped with 0x7D and guarded with an 8‑bit inverted checksum.  The command set
exposes the same measurement opcodes as the I²C sensor.  This driver keeps the
interface focused on flow reads while hiding the low level framing/transport
quirks so that it can be embedded inside any GUI.

Key datasheet facts used here:
* Water calibration measurement command → 0x3608 (Table 12)
* IPA command → 0x3615
* Scale factor reported via command 0x53; falls back to datasheet value
  (500 ticks per mL/min for SLF3S‑1300F) when the cable refuses the query.
* Continuous measurement is controlled with commands 0x33 (start) / 0x34 (stop).
* Last sample is returned by 0x35 as a signed 16‑bit integer in big‑endian
  format; a zero-length reply means "no measurement available".

Compared to the earlier revision this version adds:
* A watchdog that restarts the SCC1 stream whenever the returned ticks stay
  constant for too long – this prevents the notorious "stuck at 2.910 mL/min"
  situation caused by truncated frames.
* Automatic retries for transient SHDLC framing issues.
* Better logging hooks so that GUIs can surface transport errors.
* A richer `read()` helper that mirrors the legacy total/flow dictionary.
"""

from __future__ import annotations

import logging
import struct
import time
from typing import Dict, Optional, Tuple

import serial

__all__ = [
    "DeviceStateError",
    "ShdlcError",
    "ShdlcTimeout",
    "SLF3SUSBFlowSensor",
]


LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ShdlcError(Exception):
    """Base class for SHDLC / transport level errors."""


class ShdlcTimeout(ShdlcError):
    """Raised when the cable fails to stream a full frame before the timeout."""


class DeviceStateError(ShdlcError):
    """Raised when the SCC1 device_state field is non-zero."""


# ---------------------------------------------------------------------------
# Datasheet constants
# ---------------------------------------------------------------------------


_MEASUREMENT_COMMANDS: Dict[str, int] = {
    "water": 0x3608,
    "ipa": 0x3615,
}

_DEFAULT_SCALE_FACTOR = 500.0  # ticks per mL/min (Table 15)
_VALID_SCALE_MIN = 50
_VALID_SCALE_MAX = 5000
_FLOW_SIGNAL = 0x0001

_CMD_START_CONTINUOUS = 0x33
_CMD_STOP_CONTINUOUS = 0x34
_CMD_LAST_MEASUREMENT = 0x35
_CMD_GET_SCALE_FACTOR = 0x53
_CMD_GET_DEVICE_INFO = 0xD0

_FLAG = 0x7E
_ESC = 0x7D
_XON = 0x11
_XOFF = 0x13
_ESC_XOR = 0x20

_DEVICE_STATE_MESSAGES = {
    0x01: "Invalid parameter / wrong payload size",
    0x20: "Sensor busy",
    0x21: "Sensor gives no I²C acknowledge",
    0x22: "CRC error while communicating with sensor",
    0x23: "Measurement timeout inside sensor",
    0x24: "No measurement started",
    0x25: "Measurement buffer empty",
    0x26: "Unknown measurement command",
    0x33: "Sensor gives no I²C acknowledge",
    0x34: "CRC error while communicating with sensor",
    0x35: "Measurement timeout inside sensor",
    0x36: "No measurement started",
}


# ---------------------------------------------------------------------------
# Core driver
# ---------------------------------------------------------------------------


class SLF3SUSBFlowSensor:
    """High-level SLF3S driver that talks to the SCC1-USB cable.

    Parameters mirror the datasheet terminology so that a GUI can pick the
    measurement command or configuration words on demand.
    """

    def __init__(
        self,
        *,
        port: str = "/dev/ttyUSB1",
        baudrate: int = 115200,
        address: int = 0x00,
        timeout: float = 0.5,
        interval_ms: int = 20,
        medium: str = "water",
        measurement_command: Optional[int] = None,
        configuration_word: Optional[int] = None,
        parameter: Optional[bytes] = None,
        scale_factor: Optional[float] = None,
        stale_restart_limit: int = 8,
        stale_seconds: float = 2.0,
        auto_start: bool = True,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.address = address & 0xFF
        self.timeout = float(timeout)
        self.interval_ms = self._clamp_interval(interval_ms)
        self.configuration_word = configuration_word
        self.parameter = parameter
        self.stale_restart_limit = max(1, stale_restart_limit)
        self.stale_seconds = max(0.2, float(stale_seconds))

        if measurement_command is None:
            self.measurement_command = self._command_for_medium(medium)
        else:
            self.measurement_command = measurement_command & 0xFFFF

        if configuration_word is not None and not 0 <= configuration_word <= 0xFFFF:
            raise ValueError("configuration_word must fit into 16 bits")
        if parameter is not None and len(parameter) != 3:
            raise ValueError("parameter must contain 3 bytes (2 data + CRC)")

        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
        )

        self.scale_factor_source = "user"
        self.unit_code: Optional[int] = None
        self.sanity_code: Optional[int] = None
        self.scale_factor = (
            float(scale_factor)
            if scale_factor is not None
            else self._discover_scale_factor()
        )

        self._running = False
        self._last_sample_time: Optional[float] = None
        self._total_liters: float = 0.0
        self._last_ticks: Optional[int] = None
        self._stale_count = 0
        self._last_ticks_change_time: Optional[float] = None

        if auto_start:
            self.start()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def start(self, interval_ms: Optional[int] = None) -> None:
        """Begin continuous measurement as per datasheet section 6.5."""
        if interval_ms is not None:
            self.interval_ms = self._clamp_interval(interval_ms)
        self._ensure_stopped()
        payload = struct.pack(">H", self.interval_ms)
        payload += struct.pack(">H", self.measurement_command)
        if self.parameter is not None:
            payload += self.parameter
        if self.configuration_word is not None:
            payload += struct.pack(">H", self.configuration_word)
        self._send_command(_CMD_START_CONTINUOUS, payload)
        self._running = True
        # Preserve integration timing across restarts.
        self._last_ticks = None
        self._stale_count = 0
        self._last_ticks_change_time = None

    def stop(self) -> None:
        """Stop continuous measurement if currently running."""
        if not self._running:
            return
        try:
            self._send_command(_CMD_STOP_CONTINUOUS, b"")
        finally:
            self._running = False

    def reset_totals(self) -> None:
        self._total_liters = 0.0
        self._last_sample_time = None

    def read_raw_ticks(self) -> Optional[int]:
        data = self._send_command(_CMD_LAST_MEASUREMENT, b"")
        if len(data) == 0:
            return None
        if len(data) != 2:
            raise ShdlcError(f"Unexpected payload size: {len(data)}")
        (u16,) = struct.unpack(">H", data)
        return u16 - 0x10000 if (u16 & 0x8000) else u16

    def read_flow_ml_min(self) -> Optional[float]:
        ticks = self._read_with_watchdog()
        if ticks is None:
            return None
        return ticks / self.scale_factor

    def read(self) -> Dict[str, float]:
        """Return a dict with flow+total fields expected by legacy panels."""
        flow_ml_min_opt = self.read_flow_ml_min()

        now = time.time()
        if self._last_sample_time is None:
            self._last_sample_time = now
        dt = max(0.0, now - self._last_sample_time)
        self._last_sample_time = now
        flow_ml_min = 0.0 if flow_ml_min_opt is None else float(flow_ml_min_opt)
        flow_l_min = flow_ml_min / 1000.0
        flow_ul_min = flow_ml_min * 1000.0

        if flow_ml_min_opt is not None:
            self._total_liters += ((float(flow_ml_min_opt) / 1000.0) / 60.0) * dt
        total_ul = self._total_liters * 1_000_000.0

        return {
            "flow_l_min": flow_l_min,
            "flow_ml_min": flow_ml_min,
            "flow_ul_min": flow_ul_min,
            "total_l": self._total_liters,
            "total_ml": self._total_liters * 1000.0,
            "total_ul": total_ul,
            "temp_c": None,
            "flags": None,
        }

    def close(self) -> None:
        try:
            self.stop()
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = None

    # ------------------------------------------------------------------ #
    # Context manager
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "SLF3SUSBFlowSensor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Datasheet helper methods
    # ------------------------------------------------------------------ #

    def get_scale_factor(
        self, signal: Optional[int] = _FLOW_SIGNAL
    ) -> Tuple[int, Optional[int], Optional[int]]:
        payload = b"" if signal is None else struct.pack(">H", signal & 0xFFFF)
        data = self._send_command(_CMD_GET_SCALE_FACTOR, payload)
        if len(data) == 2:
            (scale,) = struct.unpack(">H", data)
            return scale, None, None
        if len(data) == 6:
            scale, unit_code, sanity_code = struct.unpack(">HHH", data)
            return scale, unit_code, sanity_code
        raise ShdlcError(f"Unexpected scale factor payload length {len(data)}")

    def get_device_info_raw(self) -> bytes:
        return self._send_command(_CMD_GET_DEVICE_INFO, b"")

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _read_with_watchdog(self) -> Optional[int]:
        tries = 0
        while True:
            tries += 1
            try:
                ticks = self.read_raw_ticks()
            except (DeviceStateError, ShdlcError) as exc:
                LOGGER.warning("SHDLC read failed (%s); restarting stream", exc)
                self._restart_stream()
                continue

            if ticks is None:
                return None

            now = time.time()

            if ticks == self._last_ticks:
                self._stale_count += 1
                if self._last_ticks_change_time is None:
                    self._last_ticks_change_time = now

                if (now - self._last_ticks_change_time) >= self.stale_seconds:
                    LOGGER.warning(
                        "Flow stayed at %s ticks for %.3fs → restart",
                        ticks,
                        (now - self._last_ticks_change_time),
                    )
                    self._restart_stream()
                    continue
            else:
                self._stale_count = 0
                self._last_ticks = ticks
                self._last_ticks_change_time = now
            return ticks

    def _restart_stream(self) -> None:
        saved_last_sample_time = self._last_sample_time
        self._ensure_stopped()
        time.sleep(0.05)
        self.start()
        self._last_sample_time = saved_last_sample_time

    def _ensure_stopped(self) -> None:
        if not self._running:
            try:
                self._send_command(_CMD_STOP_CONTINUOUS, b"")
            except ShdlcError:
                pass
        else:
            self.stop()

    def _discover_scale_factor(self) -> float:
        try:
            scale, unit_code, sanity_code = self.get_scale_factor(signal=_FLOW_SIGNAL)
        except ShdlcError as exc:
            LOGGER.debug("Scale factor read failed: %s", exc)
            scale = None
            unit_code = None
            sanity_code = None

        if scale and _VALID_SCALE_MIN <= scale <= _VALID_SCALE_MAX:
            self.scale_factor_source = "sensor"
            self.unit_code = unit_code
            self.sanity_code = sanity_code
            return float(scale)
        if scale and not (_VALID_SCALE_MIN <= scale <= _VALID_SCALE_MAX):
            LOGGER.warning(
                "Ignoring out-of-range scale factor %s from sensor; using datasheet default",
                scale,
            )

        self.scale_factor_source = "datasheet"
        return _DEFAULT_SCALE_FACTOR

    @staticmethod
    def _command_for_medium(medium: str) -> int:
        cmd = _MEASUREMENT_COMMANDS.get(medium.lower())
        if cmd is None:
            raise ValueError(
                f"Unsupported medium '{medium}'. Choose from: {', '.join(_MEASUREMENT_COMMANDS)}"
            )
        return cmd

    @staticmethod
    def _clamp_interval(value: int) -> int:
        return max(0, min(int(value), 0xFFFF))

    # ------------------------------------------------------------------ #
    # SHDLC plumbing
    # ------------------------------------------------------------------ #

    def _send_command(self, cmd: int, payload: bytes) -> bytes:
        frame = self._build_frame(cmd, payload)
        self.ser.write(frame)
        self.ser.flush()
        return self._read_frame(cmd)

    def _read_frame(self, expect_cmd: int) -> bytes:
        start_found = False
        payload = bytearray()
        start_time = time.time()

        while True:
            chunk = self.ser.read(1)
            if not chunk:
                if time.time() - start_time > self.timeout:
                    raise ShdlcTimeout("Timeout waiting for SHDLC frame start")
                continue
            byte = chunk[0]
            if not start_found:
                if byte == _FLAG:
                    start_found = True
                    payload.clear()
                continue
            if byte == _FLAG:
                break
            payload.append(byte)

        if not payload:
            raise ShdlcError("Empty SHDLC frame")

        data = self._unescape(bytes(payload))
        if len(data) < 5:
            raise ShdlcError("SHDLC frame too short")

        content = data[:-1]
        checksum = data[-1]
        if self._checksum(content) != checksum:
            raise ShdlcError("SHDLC checksum mismatch")

        addr = content[0]
        rcmd = content[1]
        state = content[2]
        length = content[3]
        rest = content[4:]

        if addr != self.address:
            raise ShdlcError(f"Unexpected address in reply: {addr}")
        if rcmd != expect_cmd:
            raise ShdlcError(f"Unexpected command in reply: 0x{rcmd:02X}")
        if state != 0:
            message = _DEVICE_STATE_MESSAGES.get(state, "Unknown device error")
            raise DeviceStateError(f"Device state 0x{state:02X}: {message}")
        if len(rest) != length:
            raise ShdlcError("SHDLC length mismatch")
        return rest

    @staticmethod
    def _checksum(content: bytes) -> int:
        return (~(sum(content) & 0xFF)) & 0xFF

    @staticmethod
    def _escape(data: bytes) -> bytes:
        out = bytearray()
        for byte in data:
            if byte in (_FLAG, _ESC, _XON, _XOFF):
                out.append(_ESC)
                out.append(byte ^ _ESC_XOR)
            else:
                out.append(byte)
        return bytes(out)

    @staticmethod
    def _unescape(data: bytes) -> bytes:
        out = bytearray()
        it = iter(range(len(data)))
        idx = 0
        while idx < len(data):
            byte = data[idx]
            if byte == _ESC:
                idx += 1
                if idx >= len(data):
                    raise ShdlcError("Truncated escape sequence")
                out.append(data[idx] ^ _ESC_XOR)
            else:
                out.append(byte)
            idx += 1
        return bytes(out)

    def _build_frame(self, cmd: int, payload: bytes) -> bytes:
        body = bytearray([self.address, cmd & 0xFF, len(payload) & 0xFF])
        body.extend(payload)
        body.append(self._checksum(body))
        stuffed = self._escape(bytes(body))
        return bytes([_FLAG]) + stuffed + bytes([_FLAG])
