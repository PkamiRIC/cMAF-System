# Device 3 – PLC Quick Guide (WARP3PLC)

This file contains only the essential commands to operate Device 3 **on the PLC**.

All commands run after SSH:

```
ssh pi@warp3plc.local
# or
ssh pi@<PLC_IP>
```

---

## 1. Project Paths (ON PLC)

```
/home/pi/projects/WARP-Devices/devices/device3
  ├── src/          # FastAPI backend
  ├── config/       # device3.yaml (API port & device_id)
  ├── .venv/        # Python virtual environment
  └── requirements.txt
```

---

## 2. Run Backend (Manual Mode)

Use for debugging.

```
cd ~/projects/WARP-Devices/devices/device3/src
source ../.venv/bin/activate
python -m main --config ../config/device3.yaml
```

Backend should say:

```
Uvicorn running on http://0.0.0.0:8003
```

Test from PC:

```
http://warp3plc.local:8003/status
```

---

## 3. Run Backend (Production Mode – systemd)

Service name: **device3.service**

### Start:
```
sudo systemctl start device3.service
```

### Stop:
```
sudo systemctl stop device3.service
```

### Restart (after pulling new code):
```
sudo systemctl restart device3.service
```

### Enable autostart:
```
sudo systemctl enable device3.service
```

### Status:
```
sudo systemctl status device3.service
```

### Logs:
```
journalctl -u device3.service -n 50 --no-pager
```

---

## 4. Update Code from GitHub

```
cd ~/projects/WARP-Devices
git pull
```

If requirements changed:

```
cd devices/device3
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart device3.service
```

---

## 5. Edit Configuration

Config file:

```
~/projects/WARP-Devices/devices/device3/config/device3.yaml
```

Example:

```yaml
device_id: "device3"
network:
  api_port: 8003
```

If port changes → update dashboard `.env` and restart service.

---

## 6. Health Check

From PLC:

```
curl http://localhost:8003/status
```

From PC:

```
http://warp3plc.local:8003/status
```

---

## 7. When to Update This File

Update this file anytime:

- API port changes  
- Device path changes  
- Service name/path changes  
- Additional operational commands are added  
