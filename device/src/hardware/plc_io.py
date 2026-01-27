"""
Lightweight PLC IO wrapper.
Falls back to an in-memory simulation when the rpiplc library is not present,
so the REST API can still answer status calls during development.
"""

from typing import Dict, Optional

try:
    from librpiplc import rpiplc as plc  # type: ignore
except Exception:  # pragma: no cover
    plc = None


class PlcIo:
    def __init__(
        self,
        valve_pin_map: Optional[Dict[int, str]] = None,
        pressure_channel: Optional[str] = None,
        flow_channel: Optional[str] = None,
        volume_counter_channel: Optional[str] = None,
    ) -> None:
        self.valve_pin_map = valve_pin_map or {}
        self.pressure_channel = pressure_channel
        self.flow_channel = flow_channel
        self.volume_counter_channel = volume_counter_channel
        self._sim_pressure_bar = 0.0
        self._sim_flow_lpm = 0.0
        self._sim_volume_l = 0.0

        if plc:
            try:
                plc.init("RPIPLC_V6", "RPIPLC_38AR")
            except Exception:
                # Keep going in simulated mode if init fails
                pass

    def read_pressure(self) -> float:
        if plc and self.pressure_channel is not None:
            try:
                return float(plc.analog_read(self.pressure_channel))
            except Exception:
                pass
        return self._sim_pressure_bar

    def read_flow(self) -> float:
        if plc and self.flow_channel is not None:
            try:
                return float(plc.analog_read(self.flow_channel))
            except Exception:
                pass
        return self._sim_flow_lpm

    def read_volume(self) -> float:
        if plc and self.volume_counter_channel is not None:
            try:
                return float(plc.analog_read(self.volume_counter_channel))
            except Exception:
                pass
        return self._sim_volume_l

    def set_valve(self, valve_id: int, open_: bool) -> None:
        pin = self.valve_pin_map.get(valve_id)
        if plc and pin is not None:
            try:
                plc.digital_write(pin, plc.HIGH if open_ else plc.LOW)
            except Exception:
                pass

    def set_pump_enable(self, enabled: bool) -> None:
        if plc:
            try:
                plc.digital_write("Q0.0", plc.HIGH if enabled else plc.LOW)
            except Exception:
                pass

    def set_pump_speed_mode(self, mode: str) -> None:
        if plc:
            try:
                if mode.upper() == "HIGH":
                    plc.digital_write("Q0.1", plc.HIGH)
                else:
                    plc.digital_write("Q0.1", plc.LOW)
            except Exception:
                pass

    def emergency_stop(self) -> None:
        # Best-effort safety: cut pump enable and close mapped valves
        self.set_pump_enable(False)
        for valve_id in self.valve_pin_map:
            self.set_valve(valve_id, False)
