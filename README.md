# WARP Devices Monorepo

Code for all WARP PLC devices and the dashboard.

Structure:
- `devices/device1`: Device 1 backend (placeholder scaffold)
- `devices/device2`: Device 2 backend (placeholder scaffold)
- `devices/device3`: Device 3 FastAPI backend (live)
- `dashboard`: React/Vite dashboard

Quick start (Device 3):
```
cd devices/device3
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.main --config config/device3.yaml
```

Device 3 API highlights:
- `GET /status` (includes relay states, rotary port, current step, logs)
- `GET /events/sse` (server-sent events stream for realtime UI updates)
- `POST /command/start/{sequence_name}` (sequence1/sequence2), `stop`, `home`, `emergency_stop`
- `POST /relays/{ch}/{on|off}`, `POST /rotary/{port}`, `POST /syringe/move`

See the device-specific READMEs for PLC commands and service management.
