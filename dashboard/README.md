# WARP Dashboard (React + Vite)

## Install & run
```
cd dashboard
npm install
npm run dev
# open the URL Vite prints (typically http://localhost:5173)
```

## API integration
- Backend: Device 3 FastAPI (default http://localhost:8003)
- Status stream: subscribe to `GET /events/sse` for realtime relay/rotary/step/log updates.
- Manual endpoints: `/relays/{channel}/{on|off}`, `/rotary/{port}`, `/syringe/move`
- Sequence controls: `/command/start/{sequence_name}`, `/command/stop`, `/command/home`, `/command/emergency_stop`, `/status`

Ensure your `.env` or config points the dashboard to the correct API host/port.
