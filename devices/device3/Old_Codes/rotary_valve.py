# rotary_valve.py
import serial, struct, time

class RotaryValve:
    """
    Rotary valve on Modbus RTU (addr default 0x01).
    Protocol from your table:
      - Set position: 0x06 (Write Single Register)
        reg = 0x0000, value = 0x08NN (NN = 1..12), 8-byte echo as ACK
      - (Optional) Read position: via 0x04; not required for this step.
    """
    def __init__(self, port="/dev/ttySC3", address=0x01, baudrate=9600,
                 parity=serial.PARITY_NONE, timeout=0.3):
        self.port = port
        self.address = address
        self.baudrate = baudrate
        self.parity = parity
        self.timeout = timeout

    @staticmethod
    def _crc16(data: bytes) -> bytes:
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if (crc & 1) else crc >> 1
        # little-endian
        return struct.pack('<H', crc)

    def _open(self):
        ser = serial.Serial(self.port, self.baudrate, bytesize=serial.EIGHTBITS,
                            parity=self.parity, stopbits=serial.STOPBITS_ONE,
                            timeout=self.timeout)
        try:
            from serial.rs485 import RS485Settings
            ser.rs485_mode = RS485Settings(delay_before_tx=0, delay_before_rx=0)
        except Exception:
            pass
        return ser

    def _write_reg(self, reg: int, value: int) -> bool:
        hi_r, lo_r = (reg >> 8) & 0xFF, reg & 0xFF
        hi_v, lo_v = (value >> 8) & 0xFF, value & 0xFF
        pdu = bytes([self.address, 0x06, hi_r, lo_r, hi_v, lo_v])
        frame = pdu + self._crc16(pdu)
        with self._open() as s:
            s.reset_input_buffer(); s.reset_output_buffer()
            s.write(frame)
            ack = s.read(8)  # echo for 0x06
            return len(ack) == 8 and ack[:6] == pdu

    def set_port(self, port_num: int) -> bool:
        """
        Move valve to port 1..12.
        Per table: write reg 0x0000 with value 0x08NN (NN = port).
        """
        if not (1 <= port_num <= 12):
            raise ValueError("port_num must be 1..12")
        value = (0x08 << 8) | port_num       # 0x08NN
        ok = self._write_reg(0x0000, value)
        if not ok:
            print(f"[!] Valve set_port({port_num}) not ACKed")
        return ok
