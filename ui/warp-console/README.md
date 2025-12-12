# Warp Console (Next.js, v0)

Next.js frontend generated via v0. Points to the Device 3 FastAPI backend.

## Local dev
```
cd ui/warp-console
pnpm install    # or npm install
NEXT_PUBLIC_API_BASE=http://warp3plc.local:8003 pnpm dev
```
Set `NEXT_PUBLIC_API_BASE` to your backend (PLC or localhost).

## Build
```
pnpm build
pnpm start    # serve production build
```

## Notes
- API endpoints expected: `/status`, `/events/sse`, `/command/*`, `/relays`, `/rotary`, `/syringe/move`.
- Backend must have CORS enabled if served from a different origin.
