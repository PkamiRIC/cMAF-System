# DNA Extraction System PLC Guide

SSH into the PLC:
```
ssh pi@warp3plc.local
# or
ssh pi@<PLC_IP>
```

## Project Paths (on PLC)
```
/home/pi/DNA-Extraction-System
  device/       # FastAPI backend package (entry: src/main.py)
  config/       # device3.yaml
  .venv/        # Python virtual environment
  requirements.txt
```

## Run Backend (manual)
```
cd ~/DNA-Extraction-System/device
source .venv/bin/activate
python -m src.main --config config/device3.yaml
```
Backend: http://localhost:8003 (port comes from `config/device3.yaml`)

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
cd ~/DNA-Extraction-System && git pull
cd device && source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart device3.service
```

## API (manual + sequences)
- GET  `/status`            state, step, relay/rotary, logs
- GET  `/events/sse`        realtime status stream (use in UI)
- POST `/command/start/{sequence_name}` (sequence1, sequence2)
- POST `/command/stop`      stop current sequence
- POST `/command/home`      home axes + syringe
- POST `/command/emergency_stop`
- POST `/relays/{channel}/{on|off}`
- POST `/rotary/{port}`
- POST `/syringe/move` body `{"volume_ml":..., "flow_ml_min":...}`

Manual controls are locked while a sequence runs; status/SSE still reflect live relay/rotary changes.

## Config (`config/device3.yaml`)
Key fields (ports/addresses depend on wiring):
```
network.api_port: 8003
relay.port: /dev/ttySC3, address: 2     # 0x02
rotary.port: /dev/ttySC3, address: 1    # 0x01
syringe.port: /dev/ttySC3, address: 76  # 0x4C
vertical_axis.port: /dev/ttySC3, address: 78  # 0x4E, min_mm: 0, max_mm: 33
horizontal_axis.port: /dev/ttySC3, address: 77 # 0x4D, vertical_guard_mm: 10
```
Update config if wiring/ports/addresses change, then restart the service.

## Axis presets (quick moves)
Horizontal Axis:
- Filtering: 133.0 mm
- Filter Out: 50.0 mm
- Filter In: 26.0 mm

Vertical Axis:
- Open: 0.0 mm
- Close: 33.0 mm
