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

### Step 3 - Install Node.js 20.x
Run on the Pi:
```
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
node -v
npm -v
```

### Step 4 - Clone the repo
Run on the Pi:
```
cd ~
git clone https://github.com/PkamiRIC/cMAF-System.git
```

### Step 5 - Fix SSH host key warning after reflash
If SSH says the host key changed (new SD card), run on your PC:
```
ssh-keygen -R 10.0.46.111
```
Then reconnect:
```
ssh pi@10.0.46.111
```

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
