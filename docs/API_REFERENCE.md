# API_REFERENCE.md – WARP Devices API Specification

This document provides a unified API reference for all device backends (device1, device2, device3, …).  
Each device exposes a **FastAPI HTTP service** with the same endpoints and JSON structures.

All commands are REST over HTTP.

---

# 1. Base URLs (per device)

Each device runs its backend on a unique port:

| Device | Hostname | Port | Base URL |
|--------|----------|-------|-----------|
| device1 | warp1plc.local | 8001 | http://warp1plc.local:8001 |
| device2 | warp2plc.local | 8002 | http://warp2plc.local:8002 |
| device3 | warp3plc.local | 8003 | http://warp3plc.local:8003 |

Equivalent IP-based URLs also work:

```
http://<PLC_IP>:<PORT>
```

---

# 2. Authentication

None (local network, trusted environment).  
Future extension: token-based auth.

---

# 3. Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Returns device state and telemetry |
| POST | `/command/start/{sequence_name}` | Starts a named sequence |
| POST | `/command/emergency_stop` | Immediately stops all operations |

All devices implement the same API.

---

# 4. GET /status

## URL:
```
GET http://<device_base_url>/status
```

Example:
```
GET http://warp3plc.local:8003/status
```

## Response JSON:
```json
{
  "device_id": "device3",
  "state": "IDLE",
  "current_sequence": null,
  "pressure_bar": 0.0,
  "flow_lpm": 0.0,
  "total_volume_l": 0.0,
  "last_error": null
}
```

## Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `device_id` | string | Identifier: device1, device2, device3 |
| `state` | string | One of: `IDLE`, `RUNNING`, `ERROR` |
| `current_sequence` | string/null | Active sequence, else null |
| `pressure_bar` | float | Live sensor reading |
| `flow_lpm` | float | Live sensor reading |
| `total_volume_l` | float | Accumulated from flowmeter |
| `last_error` | string/null | Human‑readable error info |

---

# 5. POST /command/start/{sequence_name}

## URL:
```
POST http://<device_base_url>/command/start/<sequence_name>
```

Example:
```
POST http://warp3plc.local:8003/command/start/clean_1
```

## Supported sequences (initial list)

| Sequence Name | Description |
|---------------|-------------|
| `clean_1` | Executes Clean 1 cycle |
| `clean_2` | Executes Clean 2 cycle |
| `concentration` | Runs concentration sequence |
| `deaeration` | Removes air from system |
| `elution` | Runs elution cycle |
| `custom` | Placeholder for future sequences |

## Request Body
None (may extend later).

## Response:
```json
{ "ok": true }
```

## Notes
- Backend will reject unknown sequences (validation to be added).
- The systemd service must be running for dashboard control.

---

# 6. POST /command/emergency_stop

## URL:
```
POST http://<device_base_url>/command/emergency_stop
```

Example:
```
POST http://warp2plc.local:8002/command/emergency_stop
```

## Function:
Immediately halts:

- pump  
- valves  
- motors  
- ongoing sequences  

This endpoint MUST always respond fast.

## Response:
```json
{ "ok": true }
```

---

# 7. Error Responses

All errors follow FastAPI standard format:

Example:
```json
{
  "detail": "Unknown sequence name: wash_banana"
}
```

HTTP codes used:

| Code | Meaning |
|------|----------|
| 200 | Success |
| 400 | Bad request (invalid sequence) |
| 500 | Internal backend error |

---

# 8. Future API Extensions

The design supports future expansion:

### Planned endpoints
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/config` | Expose config data |
| POST | `/config` | Runtime config update |
| GET | `/sensors` | Return all raw sensor values |
| POST | `/calibrate` | Calibration routines |
| POST | `/sequence/cancel` | Stop a running sequence gracefully |

---

# 9. When to Update API_REFERENCE.md

Update this file whenever:

- New endpoints are added  
- Sequences change  
- Status JSON gains new fields  
- Error handling changes  
- Dashboard features require new API calls  

This document must stay in sync with `domain/controller.py` and `interfaces/api.py`.

