# SYSTEMD – Auto-Start Services for WARP Devices

This document explains how to run each device backend as a **systemd service** on the PLC so that it:

- Starts automatically on boot  
- Restarts on failure  
- Runs in the background (no manual `python -m main`)

Command prefixes:

- **[PC]** – Run in Windows PowerShell  
- **[PLC]** – Run in the PLC terminal (via SSH)

---

## 1. Service Naming Convention

Each device has its own service:

- `device1.service`
- `device2.service`
- `device3.service`

Each service runs the FastAPI backend of that specific device folder.

---

## 2. Prerequisites (per device)

Before creating a service for a device, the following must already work on the PLC:

```bash
# [PLC] Example for device3
cd ~/projects/WARP-Devices/devices/device3/src
source ../.venv/bin/activate
python -m main --config ../config/device3.yaml
```
You should see:
"Uvicorn running on http://0.0.0.0:8003"

If this does not work, fix the backend first before using systemd.