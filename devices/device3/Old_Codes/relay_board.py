# relay_board06.py
import serial, struct, time

class RelayBoard06:
    """
    Modbus RTU relay board controlled with Function 0x06 (Write Single Register).
    - Slave address default: 0x01 (from your table)
    - Per-relay registers: 0x0001..0x0008
    - Open = 0x0100, Close = 0x0200
    - Open/Close all at register 0x0000 with 0x0700 / 0x0800
    """
    def __init__(self, port='/dev/ttySC2', address=0x02, baudrate=9600,
                 parity=serial.PARITY_NONE, timeout=0.3):
        self.port = port
        self.address = address
        self.baudrate = baudrate
        self.parity = parity
        self.timeout = timeout

    @staticmethod
    def _crc16_modbus(data: bytes) -> bytes:
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if (crc & 1) else crc >> 1
        return struct.pack('<H', crc)  # little-endian

    def _open(self):
        ser = serial.Serial(
            port=self.port, baudrate=self.baudrate, bytesize=serial.EIGHTBITS,
            parity=self.parity, stopbits=serial.STOPBITS_ONE, timeout=self.timeout
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
        pdu = bytes([self.address, 0x06, hi_reg, lo_reg, hi_val, lo_val])
        frame = pdu + self._crc16_modbus(pdu)
        with self._open() as s:
            s.reset_input_buffer(); s.reset_output_buffer()
            s.write(frame)
            # Expect 8-byte echo for 0x06
            resp = s.read(8)
            return len(resp) == 8 and resp[:6] == pdu

    # ---------- Public API ----------
    def on(self, relay_num: int) -> bool:
        if not (1 <= relay_num <= 8):
            raise ValueError("relay_num must be 1..8")
        return self._write_register(relay_num, 0x0100)

    def off(self, relay_num: int) -> bool:
        if not (1 <= relay_num <= 8):
            raise ValueError("relay_num must be 1..8")
        return self._write_register(relay_num, 0x0200)

    def all_on(self) -> bool:
        return self._write_register(0x0000, 0x0700)

    def all_off(self) -> bool:
        return self._write_register(0x0000, 0x0800)
