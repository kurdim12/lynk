# Kiosk

The portrait-totem front-end for the AI Product Specialist Engine. A visitor taps
to talk; the kiosk opens a WebRTC session to the engine's `/offer` endpoint,
streams the mic up, and renders the avatar's lip-synced video and voice back.

- **Portrait totem** layout, premium dark UI.
- **AR / EN** toggle with full RTL.
- **Attract loop** — an idle invitation that draws people in.
- **QR lead capture** — scan to get more info or book a test drive.
- **WebRTC client** matching the server's SmallWebRTC signaling (`lib/webrtc.ts`).

## Run

```bash
cd kiosk
npm install
cp .env.local.example .env.local     # point NEXT_PUBLIC_API_BASE at the engine
npm run dev                          # http://localhost:3000
```

The engine (FastAPI) must be running and `live_ready` for a tenant — see the
repo root README. `npm run build` / `npm run typecheck` validate the app without
a browser; the live WebRTC loop needs the engine, provider keys, and a mic.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | The engine's base URL |
| `NEXT_PUBLIC_TENANT` | `lynk-and-co` | Which brand this kiosk serves |
| `NEXT_PUBLIC_LEAD_URL` | `https://example.com/lead?...` | Target of the lead-capture QR |
