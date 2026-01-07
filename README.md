# WARP Devices Monorepo

Code for all WARP PLC devices and the dashboard.

Structure:
- `devices/device1`: Device 1 backend (placeholder - no code yet)
- `devices/device2`: Device 2 backend (placeholder - no code yet)
- `devices/device3`: Device 3 FastAPI backend (live)
- `dashboard`: Legacy React/Vite dashboard (simple status card)
- `ui/warp-console`: Next.js frontend for Device 3 (recommended UI)

## Prereqs
- Python 3.10+ (backend)
- Node.js 20+ (frontend)

## Quick start (Device 3 backend, local)
```
cd devices/device3
python -m venv .venv
# Linux/macOS:
#   source .venv/bin/activate
# Windows PowerShell:
#   .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.main --config config/device3.yaml
```
Backend: http://localhost:8003 (try `GET /status`)

Device 3 API highlights:
- `GET /status` (includes relay states, rotary port, current step, logs)
- `GET /events/sse` (server-sent events stream for realtime UI updates)
- `POST /command/start/{sequence_name}` (sequence1/sequence2), `stop`, `home`, `emergency_stop`
- `POST /relays/{ch}/{on|off}`, `POST /rotary/{port}`, `POST /syringe/move`

See the device-specific READMEs for PLC commands and service management.

## UI (Next.js, `ui/warp-console`)
```
cd ui/warp-console
npm install
```
Set `NEXT_PUBLIC_API_BASE` to your backend (PLC or localhost), then start dev server:
- Linux/macOS: `NEXT_PUBLIC_API_BASE=http://warp3plc.local:8003 npm run dev`
- Windows PowerShell:
  - `$env:NEXT_PUBLIC_API_BASE="http://warp3plc.local:8003"`
  - `npm run dev`

Alternatively create `ui/warp-console/.env.local`:
```
NEXT_PUBLIC_API_BASE=http://warp3plc.local:8003
```

### UI on the Pi (local vs remote)
- If you start the UI on the Pi, `http://localhost:3000` only works on the Pi itself.
- From another device, use the Pi hostname or IP, e.g. `http://WARP3PLC.local:3000` or `http://<pi-ip>:3000`.
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
WorkingDirectory=/home/pi/WARP-Devices/ui/warp-console
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

### Remote access (Tailscale)
Tailscale gives you a private IP and DNS name to reach the Pi remotely.
```
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh
```
Then access the UI via:
- Tailnet IP: `http://<tailscale-ip>:3000`
- Or MagicDNS (if enabled): `http://WARP3PLC.tailnet-xxxx.ts.net:3000`

## Legacy dashboard (Vite, `dashboard/`)
The `dashboard/` app is kept as a simple status card.
```
cd dashboard
npm install
npm run dev
```
Configure backend URL in `dashboard/.env` via `VITE_DEVICE3_URL=...`.
