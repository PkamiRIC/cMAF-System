# IO_MAP_TEMPLATE.md – Hardware I/O Mapping Template for WARP Devices

This document defines the **template I/O map** for all WARP devices.  
Each device (device1, device2, device3, …) must define:

- Digital outputs (valves, pumps, relays, solenoids)
- Digital inputs (limit switches, sensors)
- Analog inputs (pressure sensors, flow sensors)
- Any actuators controlled via drivers (stepper motors, syringe pumps)

Use this template to create per-device maps:

```
devices/deviceX/IO_MAP_DEVICEX.md
```

Do NOT modify this template directly; instead copy it.

---

# 1. Device Overview

Fill in:

| Device Name | PLC Model | Board Revision | Notes |
|-------------|-----------|----------------|-------|
| deviceX | Raspberry PLC 38AR / 21R / etc. | v6 | e.g., Flowmeter installed, Pump uses Q0.x |

---

# 2. Digital Outputs (DO)

| DO # | PLC Pin Name | Physical Component | Active State | Notes |
|------|---------------|-------------------|--------------|-------|
| 0 | Q0.0 | Valve 1 | HIGH = open | 24V output |
| 1 | Q0.1 | Valve 2 | HIGH = open | 24V output |
| 2 | Q0.2 | Pump Enable | LOW = enable | Relay / driver |
| 3 | Q0.3 | Pump DIR | HIGH = forward | Stepper direction |
| 4 | Q0.4 | Pump STEP | Pulse | 20–40 µs timing |
| 5 | Q0.5 | Relay 5 | HIGH = on | for MAF filters |
| 6 | Q0.6 | Relay 6 | HIGH = on | for MAF filters |
| … | … | … | … | … |

_Replace with your actual wiring per device._

---

# 3. Digital Inputs (DI)

| DI # | PLC Pin Name | Signal | Active State | Notes |
|------|---------------|--------|--------------|--------|
| 0 | I0.0 | Emergency stop switch | LOW | NC/NO logic |
| 1 | I0.1 | Limit switch A | HIGH | Servo/axis |
| 2 | I0.2 | Limit switch B | HIGH | |
| … | … | … | … | |

---

# 4. Analog Inputs (AI)

| AI # | PLC Pin Name | Sensor Type | Units | Scaling/Formula | Notes |
|------|---------------|----------------|--------|----------------|--------|
| 0 | A0 | Pressure sensor | bar | e.g., `(volts - 0.5) * 50/3.5` | depends on sensor |
| 1 | A1 | Flow sensor (pulse-type) | L/min | handled in software | |
| … | … | … | … | … | |

---

# 5. Communication Buses (if any)

| Bus Type | Port | Purpose | Notes |
|----------|------|---------|--------|
| RS485 | /dev/ttyS0 | Stepper driver | Modbus (future) |
| I2C | SDA/SCL | Additional sensors | optional |
| UART | /dev/ttyAMA0 | Debugging | optional |

---

# 6. Software Mapping (Python)

Example mapping block stored in:

```
devices/deviceX/src/hardware/io_map.py
```

```python
VALVE_PINS = {
    1: "Q0.0",
    2: "Q0.1",
}

PUMP_PINS = {
    "ENABLE": "Q0.2",
    "DIR": "Q0.3",
    "STEP": "Q0.4",
}
```

Update `plc_io.py` to use this mapping.

---

# 7. Verification Checklist

After wiring:

- [ ] Verify every DO toggles correct physical output
- [ ] Verify DI reflect correct sensor states
- [ ] Verify AI read stable voltage values
- [ ] Document any electrical inversion (e.g. LOW = enable)
- [ ] Update this file and push to GitHub
- [ ] Update backend logic in `hardware/plc_io.py`

---

# 8. When to Update IO Maps

Update per-device IO map whenever:

- Wiring changes  
- New valves/pumps are added  
- Pressure/flow sensor model changes  
- Pins are reassigned  
- Additional IO modules installed  
- Firmware changes require new mappings  

Make sure to update:

- `README_DEVICEX.md`
- `API_REFERENCE.md` (if the status JSON changes)
- `domain/controller.py` (if sequence logic depends on new IO)
- `hardware/plc_io.py`

