# Device 3 PLC Guide (WARP3PLC)

SSH into the PLC:
```
ssh pi@warp3plc.local
# or
ssh pi@<PLC_IP>
```

## Project Paths (on PLC)
```
/home/pi/projects/WARP-Devices/devices/device3
  src/          # FastAPI backend
  config/       # device3.yaml
  .venv/        # Python virtual environment
  requirements.txt
```

## Run Backend (manual)
```
cd ~/projects/WARP-Devices/devices/device3/src
source ../.venv/bin/activate
python -m main --config ../config/device3.yaml
```
Backend: http://localhost:8003

## systemd (production)
Service: device3.service
```
sudo systemctl start|stop|restart device3.service
sudo systemctl enable device3.service
sudo systemctl status device3.service
journalctl -u device3.service -n 50 --no-pager
```

## Update code / deps
```
cd ~/projects/WARP-Devices && git pull
cd devices/device3 && source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart device3.service
```

## API (manual + sequences)
- GET  `/status`            → state, step, relay/rotary, logs
- GET  `/events/sse`        → realtime status stream (use in UI)
- POST `/command/start/{sequence_name}` (sequence1, sequence2)
- POST `/command/stop`      → stop current sequence
- POST `/command/home`      → home axes + syringe
- POST `/command/emergency_stop`
- POST `/relays/{channel}/{on|off}`
- POST `/rotary/{port}`
- POST `/syringe/move` body `{"volume_ml":..., "flow_ml_min":...}`

Manual controls are locked while a sequence runs; status/SSE still reflect live relay/rotary changes.

## Config (device3/config/device3.yaml)
Key fields:
```
network.api_port: 8003
relay.port: /dev/ttySC3 , address: 0x02
rotary.port: /dev/ttySC3 , address: 0x01
syringe.port: /dev/ttySC3 , address: 0x4C
vertical_axis.port: /dev/ttySC3 , address: 0x4E , limits 0–33 mm
horizontal_axis.port: /dev/ttySC3 , address: 0x4D , vertical_guard_mm: 10
```
Update config if wiring/ports/addresses change, then restart the service.
