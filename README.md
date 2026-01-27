# DNA Extraction System

Backend + UI for the DNA Extraction System PLC device.

Structure:
- `device`: FastAPI backend (live)
- `dashboard`: Legacy React/Vite dashboard (simple status card)
- `ui/warp-console`: Next.js frontend (recommended UI)

## SD Card Setup (Device 2)
### Step 1 - Set hostname to WARP2PLC
Run on the Pi:
```
sudo hostnamectl set-hostname WARP2PLC
sudo sed -i 's/127.0.1.1.*/127.0.1.1\tWARP2PLC/' /etc/hosts
sudo reboot
```
Verify after reboot:
```
hostname
```

### Step 2 - Install base packages
Run on the Pi:
```
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip
```

### Step 3 - Install Industrial Shields librpiplc
Run on the Pi:
```
sudo apt update
sudo apt install -y git cmake
cd ~
git clone https://github.com/Industrial-Shields/librpiplc.git
cd ~/librpiplc
cmake -B build/ -DPLC_VERSION=RPIPLC_V6 -DPLC_MODEL=RPIPLC_38AR
cmake --build build/ -- -j $(nproc)
sudo cmake --install build/
sudo chown -R $USER:$USER ~/test/
sudo ldconfig
```

### Step 4 - Install Node.js 20.x
Run on the Pi:
```
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
node -v
npm -v
```

### Step 5 - Clone the repo
Run on the Pi:
```
cd ~
git clone https://github.com/PkamiRIC/cMAF-System.git
```

### Step 6 - Fix SSH host key warning after reflash
If SSH says the host key changed (new SD card), run on your PC:
```
ssh-keygen -R 10.0.46.111
```
Then reconnect:
```
ssh pi@10.0.46.111
```

### Step 7 - Ensure Wi-Fi auto-connect (NetworkManager)
Run on the Pi:
```
nmcli connection show
nmcli connection modify "CyRIC-INT" connection.autoconnect yes
nmcli connection modify "CyRIC-INT" connection.autoconnect-priority 10
```
(Optional) remove duplicate old connections if needed:
```
nmcli connection delete "<UUID_OR_NAME_OF_OLD_DUPLICATE>"
```

### Step 8 - Create venv and install backend dependencies
Run on the Pi:
```
cd ~/cMAF-System/device
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 9 - Create device2 config
Run on the Pi:
```
cd ~/cMAF-System/device/config
cp device3.yaml device2.yaml
```
Edit `device2.yaml` and set:
- `device_id: "device2"`
- `network.api_port: 8002`
- `relay.address: 1`
- `syringe` port/address/steps_per_ml/velocity_calib
- `vertical_axis` min/max to 0..25
- `flow_sensor.port: /dev/ttyUSB0`
- `temperature` pins (Q0.6/I0.11/8)

### Step 10 - Create backend systemd service
Run on the Pi:
```
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

sudo systemctl daemon-reload
sudo systemctl enable --now device2.service
sudo systemctl status device2.service --no-pager
```

### Step 11 - Build Next.js UI on PC
Run on your PC:
```
cd C:\Users\p.kamintzis\OneDrive - Cy.R.I.C. Cyprus Research and Innovation Center Ltd\Work\WARP\cMAF-System\ui\warp-console
npm install
npm run build
```

### Step 12 - Copy UI build to the Pi
Run on your PC:
```
scp -r "C:\Users\p.kamintzis\OneDrive - Cy.R.I.C. Cyprus Research and Innovation Center Ltd\Work\WARP\cMAF-System\ui\warp-console\.next" pi@10.0.46.111:/home/pi/cMAF-System/ui/warp-console/
```
Verify on the Pi (must exist before starting the UI service):
```
ls -ld /home/pi/cMAF-System/ui/warp-console/.next
```
If `.next` is missing, re-run the `scp` command above.

### Step 13 - Install UI runtime deps on the Pi
Run on the Pi (required for `next start`):
```
cd /home/pi/cMAF-System/ui/warp-console
npm install --omit=dev
```
Tip (if install is slow): add `--no-audit --no-fund`.

### Step 14 - Create UI systemd service (port 3002)
Run on the Pi:
```
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

sudo systemctl daemon-reload
sudo systemctl enable --now warp-ui.service
sudo systemctl status warp-ui.service --no-pager
```
Note: If the service fails with status=127, make sure `npm` is in PATH or use the absolute path from `which npm`.

## Prereqs
- Python 3.10+ (backend)
- Node.js 20+ (frontend)

## Quick start (backend, local)
```
cd device
python -m venv .venv
# Linux/macOS:
#   source .venv/bin/activate
# Windows PowerShell:
#   .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.main --config config/device3.yaml
```
Backend: http://localhost:8003 (try `GET /status`)

API highlights:
- `GET /status` (includes relay states, rotary port, current step, logs)
- `GET /events/sse` (server-sent events stream for realtime UI updates)
- `POST /command/start/{sequence_name}` (sequence1/sequence2), `stop`, `home`, `emergency_stop`
- `POST /relays/{ch}/{on|off}`, `POST /rotary/{port}`, `POST /syringe/move`

## UI (Next.js, `ui/warp-console`)
```
cd ui/warp-console
npm install
```
By default the UI talks to the backend on the same host at port 8003.
Set `NEXT_PUBLIC_API_BASE` only if the backend is on a different host, then start dev server:
- Linux/macOS: `NEXT_PUBLIC_API_BASE=http://<plc-hostname>:8003 npm run dev`
- Windows PowerShell:
  - `$env:NEXT_PUBLIC_API_BASE="http://<plc-hostname>:8003"`
  - `npm run dev`

Alternatively create `ui/warp-console/.env.local`:
```
NEXT_PUBLIC_API_BASE=http://<plc-hostname>:8003
```
Note: If `.env.local` exists, it overrides the automatic same-host behavior.

### UI on the Pi (local vs remote)
- If you start the UI on the Pi, `http://localhost:3000` only works on the Pi itself.
- From another device, use the Pi hostname or IP, e.g. `http://<plc-hostname>:3000` or `http://<pi-ip>:3000`.
- For LAN access in dev mode, bind to all interfaces:
  - `npm run dev -- --hostname 0.0.0.0 --port 3000`

### Start on boot (recommended for deployments)
Build once, then run with systemd so it starts after reboot:
```
cd ui/warp-console
npm install
npm run build
```
Create `/etc/systemd/system/warp-ui.service` on the Pi:
```
[Unit]
Description=WARP UI (Next.js)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pi/DNA-Extraction-System/ui/warp-console
ExecStart=/usr/bin/npm run start
Restart=on-failure
Environment=NODE_ENV=production
User=pi
Group=pi

[Install]
WantedBy=multi-user.target
```
Enable and start:
```
sudo systemctl daemon-reload
sudo systemctl enable --now warp-ui.service
```

## Legacy dashboard (Vite, `dashboard/`)
The `dashboard/` app is kept as a simple status card.
```
cd dashboard
npm install
npm run dev
```
Configure backend URL in `dashboard/.env` via `VITE_DEVICE3_URL=...`.
