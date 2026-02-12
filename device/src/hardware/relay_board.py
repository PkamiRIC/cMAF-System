import struct
import serial

from infra.config import RelayConfig
from hardware.serial_port_lock import get_port_lock


class RelayBoard:
    """
    Modbus RTU relay board controlled with Function 0x06 (Write Single Register).
    - Registers 0x0001..0x0008 control channels 1..8
    - Open = 0x0100, Close = 0x0200
    - 0x0000 with 0x0700 / 0x0800 toggles all
    """

    def __init__(self, config: RelayConfig) -> None:
        self.config = config

    @staticmethod
    def _crc16_modbus(data: bytes) -> bytes:
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if (crc & 1) else crc >> 1
        return struct.pack("<H", crc)

    def _open(self) -> serial.Serial:
        ser = serial.Serial(
            port=self.config.port,
            baudrate=self.config.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE if self.config.parity.upper() == "N" else self.config.parity,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.config.timeout,
        )
        try:
            from serial.rs485 import RS485Settings
            ser.rs485_mode = RS485Settings(delay_before_tx=0, delay_before_rx=0)
        except Exception:
            pass
        return ser

    def _write_register(self, reg: int, value: int) -> bool:
        hi_reg, lo_reg = (reg >> 8) & 0xFF, reg & 0xFF
        hi_val, lo_val = (value >> 8) & 0xFF, value & 0xFF
        pdu = bytes([self.config.address, 0x06, hi_reg, lo_reg, hi_val, lo_val])
        return self._write_frame(pdu)

    def _write_frame(self, pdu: bytes, expected_len: int = 8) -> bool:
        """Send a pre-built PDU with CRC and validate the echo."""
        frame = pdu + self._crc16_modbus(pdu)
        with get_port_lock(self.config.port):
            with self._open() as serial_port:
                serial_port.reset_input_buffer()
                serial_port.reset_output_buffer()
                serial_port.write(frame)
                resp = serial_port.read(expected_len)
                return len(resp) == expected_len and resp[: len(pdu)] == pdu

    def on(self, relay_num: int) -> bool:
        if not (1 <= relay_num <= 8):
            raise ValueError("relay_num must be 1..8")
        return self._write_register(relay_num, 0x0100)

    def off(self, relay_num: int) -> bool:
        if not (1 <= relay_num <= 8):
            raise ValueError("relay_num must be 1..8")
        return self._write_register(relay_num, 0x0200)

    def all_on(self) -> bool:
        """
        All ON command frame (addressed): addr 0x??, 06, 00, 00, 07, 00, CRC16.
        For addr=0x02 this is: 02 06 00 00 07 00 8B C9
        """
        pdu = bytes([self.config.address, 0x06, 0x00, 0x00, 0x07, 0x00])
        return self._write_frame(pdu)

    def all_off(self) -> bool:
        """
        All OFF command frame (addressed): addr 0x??, 06, 00, 00, 08, 00, CRC16.
        For addr=0x02 this is: 02 06 00 00 08 00 8E 39
        """
        pdu = bytes([self.config.address, 0x06, 0x00, 0x00, 0x08, 0x00])
        return self._write_frame(pdu)
