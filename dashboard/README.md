# WARP Dashboard (React + Vite)

## Install & run
```
cd dashboard
npm install
npm run dev
# open the URL Vite prints (typically http://localhost:5173)
```
Note: `localhost` only works on the same machine. For LAN access:
```
npm run dev -- --host 0.0.0.0 --port 5173
```
Then browse to `http://WARP3PLC.local:5173` or `http://<pi-ip>:5173`.

## API integration
- Backend URL is configured via `dashboard/.env`:
  - `VITE_DEVICE3_URL=http://warp3plc.local:8003` (or `http://localhost:8003`)
- The dashboard currently polls `GET /status` every ~2s.
- Device 3 also supports realtime updates via `GET /events/sse` (used by `ui/warp-console`).

If you change `dashboard/.env`, restart `npm run dev`.

## Remote access (Tailscale)
If the Pi is abroad, use Tailscale to reach it:
```
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh
```
Then open `http://<tailscale-ip>:5173`.
You can verify the backend from anywhere on the tailnet:
- `http://<tailscale-ip>:8003/status`
