"""FastAPI app: health, KB/readiness status, and WebRTC signaling for the kiosk.

Health and status run with zero heavy dependencies (no Pipecat, no provider
keys) so readiness is always inspectable. The ``/offer`` endpoint wires a live
WebRTC peer to the Pipecat bot; its dependencies (Pipecat WebRTC extra + provider
keys) are imported lazily and missing pieces return a clear 503 rather than
crashing the app.
"""

from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from server import __version__
from server.cache import AnswerCache
from server.config import index_path, load_tenant
from server.fallbacks import can_run_audio_only, readiness_report

app = FastAPI(title="AI Product Specialist Engine", version=__version__)

# Active WebRTC connections, keyed by peer-connection id, for renegotiation.
_connections: dict[str, object] = {}


def _kb_status(tenant_id: str) -> dict:
    """Read the persisted KB index for chunk count + embedder (no embedding deps)."""
    path = index_path(tenant_id)
    if not path.exists():
        return {"kb_chunks": 0, "embedder": None, "index_built": False}
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "kb_chunks": len(data.get("items", [])),
        "embedder": data.get("embedder"),
        "index_built": True,
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/tenants/{tenant_id}/status")
async def tenant_status(tenant_id: str) -> dict:
    """Readiness for a tenant: KB index, missing provider keys, live readiness."""
    try:
        tenant = load_tenant(tenant_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    kb = _kb_status(tenant_id)
    live_ready = kb["kb_chunks"] > 0 and not tenant.missing_keys
    return {
        "tenant": tenant.id,
        "name": tenant.name,
        "languages": tenant.languages,
        "kb_chunks": kb["kb_chunks"],
        "kb_embedder": kb["embedder"],
        "index_built": kb["index_built"],
        "missing_keys": tenant.missing_keys,
        "live_ready": live_ready,
        # Fallback posture: per-provider readiness, whether a voice-only answer
        # is possible (avatar optional), and how many answers are pre-rendered.
        "providers": readiness_report(tenant),
        "audio_only_capable": kb["kb_chunks"] > 0 and can_run_audio_only(tenant),
        "cached_answers": len(AnswerCache.for_tenant(tenant_id)),
    }


@app.post("/tenants/{tenant_id}/offer")
async def offer(tenant_id: str, request: dict, background_tasks: BackgroundTasks):
    """WebRTC signaling: accept an SDP offer, start the bot, return the answer.

    Requires the Pipecat WebRTC extra (`pip install 'pipecat-ai[webrtc]'`) plus
    all provider keys. This is the live loop — validate it with keys and a real
    browser/mic; it cannot run in a sandbox.
    """
    try:
        tenant = load_tenant(tenant_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if tenant.missing_keys:
        return JSONResponse(
            status_code=503,
            content={"error": "missing provider keys", "missing_keys": tenant.missing_keys},
        )

    try:
        from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
        from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

        from server.bot import run_bot, transport_params
    except ImportError as e:
        return JSONResponse(
            status_code=503,
            content={"error": "WebRTC/Pipecat extras not installed", "detail": str(e)},
        )

    pc_id = request.get("pc_id")
    if pc_id and pc_id in _connections:
        connection = _connections[pc_id]
        await connection.renegotiate(
            sdp=request["sdp"], type=request["type"], restart_pc=request.get("restart_pc", False)
        )
    else:
        connection = SmallWebRTCConnection(ice_servers=["stun:stun.l.google.com:19302"])
        await connection.initialize(sdp=request["sdp"], type=request["type"])

        @connection.event_handler("closed")
        async def _on_closed(conn):
            _connections.pop(conn.pc_id, None)

        transport = SmallWebRTCTransport(webrtc_connection=connection, params=transport_params())
        background_tasks.add_task(run_bot, transport, tenant)
        _connections[connection.pc_id] = connection

    return connection.get_answer()
