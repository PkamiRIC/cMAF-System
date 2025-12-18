# WARP Dashboard (React + Vite)

## Install & run
```
cd dashboard
npm install
npm run dev
# open the URL Vite prints (typically http://localhost:5173)
```

## API integration
- Backend URL is configured via `dashboard/.env`:
  - `VITE_DEVICE3_URL=http://warp3plc.local:8003` (or `http://localhost:8003`)
- The dashboard currently polls `GET /status` every ~2s.
- Device 3 also supports realtime updates via `GET /events/sse` (used by `ui/warp-console`).

If you change `dashboard/.env`, restart `npm run dev`.
