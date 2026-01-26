# DNA Extraction System Console (Next.js, v0)

Next.js frontend generated via v0. Points to the Device 3 FastAPI backend.

## Local dev
```
cd ui/warp-console
npm install
```
By default the UI talks to the backend on the same host at port 8003.
Set `NEXT_PUBLIC_API_BASE` only if the backend is on a different host.

Examples:
- Linux/macOS: `NEXT_PUBLIC_API_BASE=http://<plc-hostname>:8003 npm run dev`
- Windows PowerShell:
  - `$env:NEXT_PUBLIC_API_BASE="http://<plc-hostname>:8003"`
  - `npm run dev`

Alternatively create `ui/warp-console/.env.local`:
```
NEXT_PUBLIC_API_BASE=http://<plc-hostname>:8003
```
To point the UI at a Tailscale IP (example):
```
echo "NEXT_PUBLIC_API_BASE=http://100.98.170.67:8003" > .env.local
```
If `.env.local` exists, it overrides the automatic same-host behavior. Remove it
and rebuild if you want the UI to work on both LAN (`<plc-hostname>`) and Tailscale IPs.

## Run on the Pi
If you start the UI on the Pi, `http://localhost:3000` only works on the Pi itself.
For LAN access, bind to all interfaces:
```
npm run dev -- --hostname 0.0.0.0 --port 3000
```
Then open `http://<plc-hostname>:3000` or `http://<pi-ip>:3000`.

## Start on boot (systemd)
Build once, then run as a service:
```
npm install
npm run build
```
Create `/etc/systemd/system/warp-ui.service`:
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

## Remote access (Tailscale)
Install Tailscale on the Pi:
```
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh
```
Access the UI via the tailnet IP or MagicDNS:
- `http://<tailscale-ip>:3000`
- `http://<plc-hostname>.tailnet-xxxx.ts.net:3000`

Backend check:
- `http://<tailscale-ip>:8003/status`

## Build
```
npm run build
npm run start    # serve production build
```

## Notes
- API endpoints expected: `/status`, `/events/sse`, `/command/*`, `/relays`, `/rotary`, `/syringe/move`.
- Backend must have CORS enabled if served from a different origin.
