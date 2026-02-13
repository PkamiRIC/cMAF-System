# cMAF System

Control software for the cMAF hardware on Raspberry Pi PLC:
- `device/`: FastAPI backend + hardware drivers + sequence logic
- `ui/warp-console/`: Next.js UI used by operators

This repository is intentionally trimmed to active code paths only.

## What This Repo Does
- Runs sequences for MAF sampling/cleaning with relay, axis, syringe, pump, PID, flow, and TEC coordination.
- Exposes a REST API (`:8002`) for control/status.
- Serves a web UI (`:3002`) for operators.
- Supports Sensirion SLF3S flow meter and Meerstetter TEC (pyMeCom).

## Runtime Structure
- `device/src/main.py`: backend entrypoint (`python -m src.main --config config/device2.yaml`)
- `device/src/interfaces/api.py`: HTTP endpoints
- `device/src/domain/controller.py`: orchestration, state, sequence execution
- `device/src/domain/sequence1.py`: MAF sequence 1
- `device/src/domain/sequence2.py`: MAF sequence 2
- `device/src/domain/cleaning_sequence.py`: cleaning sequence
- `device/src/hardware/*`: hardware drivers
- `device/src/infra/config.py`: typed YAML config loader
- `device/config/device2.yaml`: active device configuration
- `ui/warp-console/app` + `ui/warp-console/components`: UI

## Hardware Notes
- Flow meter: Sensirion SLF3S over SCC1 USB (`device/Old_Codes/slf3s_usb_sensor.py` remains in use by active flow wrapper).
- TEC: Meerstetter via pyMeCom on serial (recommended by-id path in YAML).
- PLC I/O pins are configured through `device2.yaml`.

### USB/Serial Naming (Flow + TEC)
Use stable names so device order changes (`ttyUSB0/1`) do not break startup.

Check current USB serial devices:
```bash
ls -l /dev/serial/by-id/
```

Current expected IDs in this setup:
- Flow: `usb-Sensirion_AG_Sensirion_RS485-USB_Cable_FT7TV0U4-if00-port0`
- TEC: `usb-FTDI_FT230X_Basic_UART_DP05MXL4-if00-port0`

Use them directly in `device/config/device2.yaml`:
```yaml
flow_sensor:
  port: "/dev/serial/by-id/usb-Sensirion_AG_Sensirion_RS485-USB_Cable_FT7TV0U4-if00-port0"
temperature:
  tec_port: "/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DP05MXL4-if00-port0"
```

Optional: create custom symlinks (`/dev/ttyFLOW`, `/dev/ttyTEC`) with udev:
```bash
sudo tee /etc/udev/rules.d/99-cmaf-serial.rules > /dev/null <<'EOF'
SUBSYSTEM=="tty", ENV{ID_SERIAL_SHORT}=="FT7TV0U4", SYMLINK+="ttyFLOW"
SUBSYSTEM=="tty", ENV{ID_SERIAL_SHORT}=="DP05MXL4", SYMLINK+="ttyTEC"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
ls -l /dev/ttyFLOW /dev/ttyTEC
```

### LAM Driver Pin + RS485 Direction Command
In this setup, peristaltic direction uses both:
- PLC digital pin `Q0.2` (`peristaltic.dir_reverse_pin`)
- RS485 write to the external direction driver (`peristaltic.dir_driver_*`)

Active mapping in code:
- CW/forward: `Q0.2 = HIGH`, RS485 value `0x0081` (DO1 OFF)
- CCW/reverse: `Q0.2 = LOW`, RS485 value `0x0001` (DO1 ON)

RS485 command format used by backend (`device/src/hardware/peristaltic_pump.py`):
- Modbus function `0x06`, register `0xA4F7`, value `0x0081` or `0x0001`, address from `dir_driver_address` (default `76` / `0x4C`).

Operational example (preferred through API):
```bash
# CW
curl -X POST http://127.0.0.1:8002/peristaltic/direction \
  -H "Content-Type: application/json" -d '{"forward": true}'

# CCW
curl -X POST http://127.0.0.1:8002/peristaltic/direction \
  -H "Content-Type: application/json" -d '{"forward": false}'
```

## Pi Setup (Step by Step)
### 1. Base packages
```bash
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip curl ca-certificates gnupg
```

### 2. Install Industrial Shields PLC libraries
```bash
sudo mkdir -p /etc/apt/keyrings
sudo curl -fsSL https://apps.industrialshields.com/main/DebRepo/PublicKey.gpg -o /etc/apt/keyrings/industrialshields.gpg
echo "deb [signed-by=/etc/apt/keyrings/industrialshields.gpg] https://apps.industrialshields.com/main/DebRepo/ ./" | sudo tee /etc/apt/sources.list.d/industrialshields.list
sudo apt-get install -y librpiplc python3-librpiplc
sudo ldconfig
```

### 3. Install Node.js 20
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 4. Clone repo
```bash
cd /home/pi
git clone https://github.com/PkamiRIC/cMAF-System.git
cd /home/pi/cMAF-System
```

### 5. Backend venv
```bash
cd /home/pi/cMAF-System/device
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt
```

### 6. Install pyMeCom (if TEC is used)
```bash
cd /home/pi
mkdir -p pyMeCom-1.1
unzip -o pyMeCom-1.1.zip -d pyMeCom-1.1
cd /home/pi/cMAF-System/device
source .venv/bin/activate
pip install /home/pi/pyMeCom-1.1/pyMeCom-1.1
```

### 7. Configure backend
Edit `/home/pi/cMAF-System/device/config/device2.yaml`.

Critical fields:
- `network.api_port: 8002`
- `flow_sensor.port: /dev/serial/by-id/...Sensirion...`
- `temperature.tec_port: /dev/serial/by-id/...FTDI...`
- `temperature.tec_address: 2`
- `temperature.tec_channel: 1`
- `temperature.tec_baudrate: 57600`

### 8. Install backend service
```bash
sudo tee /etc/systemd/system/device2.service > /dev/null <<'EOF'
[Unit]
Description=cMAF Device 2 Backend (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/cMAF-System/device
ExecStart=/home/pi/cMAF-System/device/.venv/bin/python -m src.main --config config/device2.yaml
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
```

### 9. Build and install UI
```bash
cd /home/pi/cMAF-System/ui/warp-console
npm ci
npm run build
```

### 10. Install UI service
```bash
sudo tee /etc/systemd/system/warp-ui.service > /dev/null <<'EOF'
[Unit]
Description=cMAF UI (Next.js)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pi/cMAF-System/ui/warp-console
Restart=on-failure
Environment=NODE_ENV=production
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/npm run start -- --hostname 0.0.0.0 --port 3002
User=pi
Group=pi

[Install]
WantedBy=multi-user.target
EOF
```

### 11. Enable/start services
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now device2.service
sudo systemctl enable --now warp-ui.service
```

## Daily Operations
### Check status
```bash
sudo systemctl status device2.service --no-pager -l
sudo systemctl status warp-ui.service --no-pager -l
curl -sS http://127.0.0.1:8002/status
```

### Restart
```bash
sudo systemctl restart device2.service
sudo systemctl restart warp-ui.service
```

### Pull updates safely (avoid YAML conflict loops)
```bash
cd /home/pi/cMAF-System
git stash -u
git pull --rebase origin main
# re-apply only specific changes manually; avoid blind "git stash pop"
```

## Common Failure Recovery
### UI stuck at "reconnecting"
Usually backend is down. Check:
```bash
sudo systemctl status device2.service --no-pager -l
journalctl -u device2.service -n 120 --no-pager
```

### YAML parse error with `<<<<<<< Updated upstream`
Fix immediately:
```bash
cd /home/pi/cMAF-System
git restore --source=HEAD --staged --worktree device/config/device2.yaml
```
Then restore required TEC path and restart backend.

### TEC behavior
- Setting target while Peltier OFF updates software target and defers hardware write.
- On Peltier ON, target is pushed to TEC and regulation begins.
- Sequence temperature steps are non-blocking: TEC timeouts log warnings and sequence continues.

## API/Ports
- Backend: `http://<pi-ip>:8002`
- UI: `http://<pi-ip>:3002`

Key endpoints:
- `GET /status`
- `POST /command/start/{sequence_name}`
- `POST /command/emergency_stop`
- `POST /temperature/enable`
- `POST /temperature/target`
- `POST /flow/start`, `POST /flow/stop`, `POST /flow/reset`
