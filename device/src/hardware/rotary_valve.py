import struct
import serial

from infra.config import RotaryValveConfig
from hardware.serial_port_lock import get_port_lock


class RotaryValve:
    """
    Rotary valve on Modbus RTU (addr default 0x01).
    Protocol:
      - Set position: 0x06 (Write Single Register)
        reg = 0x0000, value = 0x08NN (NN = 1..12)
    """

    def __init__(self, config: RotaryValveConfig) -> None:
        self.config = config

    @staticmethod
    def _crc16(data: bytes) -> bytes:
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

    def _write_reg(self, reg: int, value: int) -> bool:
        hi_r, lo_r = (reg >> 8) & 0xFF, reg & 0xFF
        hi_v, lo_v = (value >> 8) & 0xFF, value & 0xFF
        pdu = bytes([self.config.address, 0x06, hi_r, lo_r, hi_v, lo_v])
        frame = pdu + self._crc16(pdu)
        with get_port_lock(self.config.port):
            with self._open() as serial_port:
                serial_port.reset_input_buffer()
                serial_port.reset_output_buffer()
                serial_port.write(frame)
                ack = serial_port.read(8)  # echo for 0x06
                return len(ack) == 8 and ack[:6] == pdu

    def set_port(self, port_num: int) -> bool:
        """
        Move valve to port 1..12.
        """
        if not (1 <= port_num <= 12):
            raise ValueError("port_num must be 1..12")
        value = (0x08 << 8) | port_num  # 0x08NN
        ok = self._write_reg(0x0000, value)
        return ok
