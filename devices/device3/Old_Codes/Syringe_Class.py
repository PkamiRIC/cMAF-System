# ------------------ SYRINGE PUMP CLASS ------------------ #
import serial
import time
import struct
 
class SyringePump:
    def __init__(self, port='/dev/ttySC2', address=0x4C, steps_per_ml=304457.5314, velocity_calib=304.45753):
        self.port = port
        self.address = address
        self.baudrate = 9600
        self.steps_per_ml = steps_per_ml
        self.velocity_calib = velocity_calib
        self.target_position = 0  # Store the target position in steps
 
    # === NEW: one place to open the port with RS-485 mode enabled ===
    def _open_serial(self, timeout=1.0):
        ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=timeout,
        )
        # Enable RS-485 driver enable/receive toggle if available
        try:
            from serial.rs485 import RS485Settings
            ser.rs485_mode = RS485Settings(delay_before_tx=0, delay_before_rx=0)
        except Exception:
            pass
        return ser
 
    def calculate_crc(self, command_bytes):
        crc = 0xFFFF
        for b in command_bytes:
            crc ^= b
            for _ in range(8):
                if crc & 0x01:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return struct.pack('<H', crc)  # little-endian
 
    def calculate_steps(self, volume_ml):
        return int(volume_ml * self.steps_per_ml)
 
    def int_to_4byte_big_endian(self, val):
        return val.to_bytes(4, byteorder='big', signed=True)
 
    def build_command(self, volume_ml, flow_rate_ml_per_min):
        # Limit flow rate to ±15 mL/min
        if flow_rate_ml_per_min > 15:
            flow_rate_ml_per_min = 15
        elif flow_rate_ml_per_min < -15:
            flow_rate_ml_per_min = -15
 
        # Limit volume to ±180 mL
        if abs(volume_ml) > 180:
            raise ValueError("Volume must not exceed 180 mL")
 
        velocity_decimal = int(self.velocity_calib * flow_rate_ml_per_min)
        steps = self.calculate_steps(volume_ml)
        self.target_position = steps
 
        base_command = bytearray([
            self.address, 0x10, 0xA7, 0x9E,
            0x00, 0x07,
            0x0E,
            0x01, 0x00, 0x00, 0x03,
            0x03, 0xE8,
            0x00, 0x00, 0x00, 0x00,  # velocity placeholder
            0x00, 0x00, 0x00, 0x00   # steps placeholder
        ])
 
        velocity_bytes = self.int_to_4byte_big_endian(velocity_decimal)
        steps_bytes = self.int_to_4byte_big_endian(steps)
        base_command[13:17] = velocity_bytes
        base_command[17:21] = steps_bytes
 
        crc = self.calculate_crc(base_command)
        return base_command + crc
 
    def send_command(self, command):
        # REPLACED: use _open_serial (RS-485 enabled)
        with self._open_serial(timeout=0.5) as ser:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.flush()
            ser.write(command)
            time.sleep(0.5)
            response = ser.read(30)
            print(f"Response: {response}")
 
    def move(self, volume_ml, flow_rate_ml_min):
        command = self.build_command(volume_ml, flow_rate_ml_min)
        self.send_command(command)
 
    # ---------- NEW: low-level status reader (no prints) ----------
    def read_status(self, max_tries=5):
        """
        Query DDS5 status & live data (no printing).
        Returns a dict with:
          sdw, mode, busy, standstill, vel_ok, pos_ok,
          actual_velocity, actual_position, volume_ml, flow_ml_min
        or None on failure.
        """
        poll = bytearray([self.address, 0x03, 0xA7, 0x3A, 0x00, 0x07])
        poll += self.calculate_crc(poll)

        tries = 0
        while tries < max_tries:
            tries += 1
            try:
                with self._open_serial(timeout=2.0) as ser:
                    ser.reset_input_buffer(); ser.reset_output_buffer(); ser.flush()
                    ser.write(poll)
                    time.sleep(0.2)
                    resp = ser.read(19)
            except Exception:
                time.sleep(0.2)
                continue

            # Validate frame
            if len(resp) != 19:
                time.sleep(0.2); continue
            if resp[0] != self.address or resp[1] != 0x03 or resp[2] != 0x0E:
                # wrong slave / function / byte-count
                time.sleep(0.2); continue
            if self.calculate_crc(resp[:-2]) != resp[-2:]:
                # CRC mismatch
                time.sleep(0.2); continue

            # Parse payload
            sdw = int.from_bytes(resp[3:7], 'big')                # 32-bit StatusDWord
            busy        = (sdw >> 8)  & 1
            standstill  = (sdw >> 12) & 1
            vel_ok      = (sdw >> 14) & 1
            pos_ok      = (sdw >> 15) & 1
            mode        = (sdw >> 24) & 0b111

            actual_velocity = int.from_bytes(resp[9:13],  'big', signed=True)
            actual_position = int.from_bytes(resp[13:17], 'big', signed=True)

            volume_ml   = actual_position / self.steps_per_ml
            flow_ml_min = round(actual_velocity / self.velocity_calib, 4)

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

        return None  # exhausted tries

    # ---------- NEW: convenience for sequences ----------
    def read_status_dword(self):
        """Return raw 32-bit StatusDWord (int) or None."""
        st = self.read_status()
        return None if st is None else st["sdw"]

    def print_status(self, show=("position",), label=None):
        """
        Print only selected fields. Available keys:
          'position', 'busy', 'standstill', 'pos_ok', 'vel_ok',
          'velocity', 'volume', 'flow', 'mode', 'sdw_hex'
        """
        st = self.read_status()
        if st is None:
            print("[!] No status")
            return None

        parts = []
        if label: parts.append(f"{label}:")
        keymap = {
            "position":   f"pos={st['actual_position']}",
            "busy":       f"busy={st['busy']}",
            "standstill": f"standstill={st['standstill']}",
            "pos_ok":     f"posOK={st['pos_ok']}",
            "vel_ok":     f"velOK={st['vel_ok']}",
            "velocity":   f"vel={st['actual_velocity']}",
            "volume":     f"vol_ml={st['volume_ml']:.4f}",
            "flow":       f"flow={st['flow_ml_min']:.4f} mL/min",
            "mode":       f"mode={st['mode']:03b}",
            "sdw_hex":    f"SDW=0x{st['sdw']:08X}",
        }
        for k in show:
            if k in keymap: parts.append(keymap[k])
        print(" ".join(parts))
        return st

    # ---------- REPLACED: keep old behavior but built on read_status ----------
    def read_feedback(self, return_busy_bit=False):
        """
        Back-compat:
          - if return_busy_bit=True: returns (None, busy)
          - else: prints the original full block and returns actual_position
        """
        st = self.read_status()
        if st is None:
            print("[!] Incomplete or unexpected response, skipping...")
            return None if not return_busy_bit else (None, None)

        if return_busy_bit:
            return (None, st["busy"])

        # Original verbose block
        av_hex = [(st["actual_velocity"] >> (8*i)) & 0xFF for i in (3,2,1,0)]
        ap = st["actual_position"]
        ap_hex = [(ap >> (8*i)) & 0xFF for i in (3,2,1,0)]

        print("\n--------- SYRINGE FEEDBACK (RAW HEX) ---------")
        print(f"Actual Velocity (Hex) : {[hex(b) for b in av_hex]}")
        print(f"Actual Position (Hex) : {[hex(b) for b in ap_hex]}")
        print(f"Actual Position        : {ap} steps")
        print(f"Sucked Volume          : {st['volume_ml']:.4f} mL")
        print(f"Flow Rate              : {st['flow_ml_min']:.4f} mL/min")
        print(f"Busy Bit               : {st['busy']}")
        print("--------------------------------------------\n")

        return ap

    def monitor_until_target(self, tolerance=10):
        while True:
            actual_position = self.read_feedback()
            if actual_position is not None and abs(actual_position - self.target_position) <= tolerance:
                print("[?] Target position reached.")
                return True
            time.sleep(5)
 
    def home(self):
   
        print(f"[Stage] Sending homing commands to pump at address {hex(self.address)}")

        def _make_home_cmd(flag_byte):
            frame = bytearray([
                self.address,     # dynamic node address
                0x10,             # Function: Write Multiple Registers
                0xA7, 0x9E,       # Starting Address = 0xA79E
                0x00, 0x07,       # Quantity of Registers = 7
                0x0E,             # Byte Count = 14
                0x07, 0x00,       # ControlDWord (high word)
                flag_byte, 0x03,  # ControlDWord low: flag + 0x03
                0x01, 0xF4,       # TargetTorque = 500 (0x01F4)
                0x00, 0x00, 0x03, 0xE8,  # TargetVelocity = 1000
                0x00, 0x00, 0x27, 0x10   # TargetPosition = 10000
            ])
            frame += self.calculate_crc(frame)
            return frame

        cmd1 = _make_home_cmd(0x00)  # first homing frame
        cmd2 = _make_home_cmd(0x02)  # second homing frame

        try:
            with self._open_serial(timeout=1.0) as ser:
                ser.reset_input_buffer()
                ser.reset_output_buffer()

                ser.write(cmd1)
                ser.flush()
                time.sleep(0.2)
                ack1 = ser.read(8)
                print(f"[home] CMD1 ack: {ack1.hex()}")

                ser.write(cmd2)
                ser.flush()
                time.sleep(0.2)
                ack2 = ser.read(8)
                print(f"[home] CMD2 ack: {ack2.hex()}")

                print("[?] Homing command(s) sent.")
        except Exception as e:
            print(f"[!] Homing failed: {e}")
            return

        # Wait for busy bit to clear
        ok = self.wait_until_idle(timeout=60)
        if ok:
            print("[?] Homing completed (idle).")
        else:
            print("[!] Homing timed out (still busy).")


 
    def wait_until_idle(self, timeout=None):
        start_time = time.time()
        while True:
            result = self.read_feedback(return_busy_bit=True)
            if result is None:
                time.sleep(0.5)
                continue
            _, busy_bit = result
            if busy_bit == 0:
                return True
            if timeout is not None and (time.time() - start_time) >= timeout:
                print("[!] Operation timeout expired")
                return False
            time.sleep(0.5)