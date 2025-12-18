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
pnpm install   # or npm install
```
Set `NEXT_PUBLIC_API_BASE` to your backend (PLC or localhost), then start dev server:
- Linux/macOS: `NEXT_PUBLIC_API_BASE=http://warp3plc.local:8003 pnpm dev`
- Windows PowerShell:
  - `$env:NEXT_PUBLIC_API_BASE="http://warp3plc.local:8003"`
  - `pnpm dev`

Alternatively create `ui/warp-console/.env.local`:
```
NEXT_PUBLIC_API_BASE=http://warp3plc.local:8003
```

## Legacy dashboard (Vite, `dashboard/`)
The `dashboard/` app is kept as a simple status card.
```
cd dashboard
npm install
npm run dev
```
Configure backend URL in `dashboard/.env` via `VITE_DEVICE3_URL=...`.
