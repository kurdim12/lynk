"""The Pipecat pipeline — the live, real-time voice/video loop.

    WebRTC mic ─▶ Deepgram STT (AR/EN) ─▶ RAG grounding ─▶ Claude (brand-safe)
                ─▶ ElevenLabs TTS (Levantine) ─▶ Simli (lip-synced video) ─▶ kiosk

Wired against the real Pipecat 1.4 API (services, transport, universal
LLMContext, frame processors). It cannot run in a sandbox — it needs provider
keys and a real WebRTC peer (browser/mic). Validate the live loop on first run
with keys set; everything it depends on (config, KB, grounding) is verified
offline by the test suite.

Provider models, voice, and face IDs all come from the tenant config — no code
changes to onboard a new brand.
"""

from __future__ import annotations

from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.transports.base_transport import BaseTransport, TransportParams

from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.simli.video import SimliVideoService

from server.brain.rag import RAGGroundingProcessor, RAGGrounder
from server.config import TenantConfig, load_tenant
from server.fallbacks import first_ready, use_avatar
from server.kb.retriever import Retriever

DEFAULT_TENANT = "lynk-and-co"


def transport_params() -> TransportParams:
    """WebRTC transport params for a voice + avatar-video kiosk."""
    return TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        video_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
    )


def _greeting_system_prompt(tenant: TenantConfig) -> str:
    persona = tenant.persona
    return (
        f"You are {persona.get('name', 'the product specialist')}, a "
        f"{persona.get('role', 'digital product specialist')} for {tenant.name}. "
        "Greet the visitor warmly in one short sentence and ask how you can help. "
        "Speak naturally for voice — no markdown. Default to English, but switch "
        "to Arabic if the visitor speaks Arabic."
    )


def _require(tenant: TenantConfig, kind: str) -> dict:
    """The first ready provider config for a kind, or a clear error."""
    option = first_ready(tenant, kind)
    if option is None:
        raise RuntimeError(
            f"No ready '{kind}' provider for tenant '{tenant.id}'. "
            f"Set its credentials, or configure a fallback that has them."
        )
    return option.config


def create_services(tenant: TenantConfig):
    """Build the swappable provider services, honouring fallbacks.

    Each service uses the first provider in its chain whose credentials are set
    (primary, else fallback). The avatar is optional: if no avatar provider is
    ready, the bot runs audio-only and ``simli`` is ``None``.
    """
    from deepgram import LiveOptions

    stt_cfg = _require(tenant, "stt")
    llm_cfg = _require(tenant, "llm")
    tts_cfg = _require(tenant, "tts")

    stt = DeepgramSTTService(
        api_key=stt_cfg["api_key"],
        live_options=LiveOptions(
            model=stt_cfg.get("model", "nova-2-general"),
            language=stt_cfg.get("language", "multi"),
            smart_format=True,
        ),
    )
    # Pass only max_tokens — Opus 4.8 rejects sampling params (temperature/top_p/top_k).
    llm = AnthropicLLMService(
        api_key=llm_cfg["api_key"],
        model=llm_cfg.get("model", "claude-opus-4-8"),
        params=AnthropicLLMService.InputParams(max_tokens=int(llm_cfg.get("max_tokens", 1024))),
    )
    tts = ElevenLabsTTSService(
        api_key=tts_cfg["api_key"],
        voice_id=tts_cfg["voice_id"],
        model=tts_cfg.get("model", "eleven_turbo_v2_5"),
    )
    simli = None
    if use_avatar(tenant):
        avatar_cfg = _require(tenant, "avatar")
        simli = SimliVideoService(api_key=avatar_cfg["api_key"], face_id=avatar_cfg["face_id"])
    return stt, llm, tts, simli


def create_task(transport: BaseTransport, tenant: TenantConfig) -> PipelineTask:
    """Assemble the full pipeline and return a runnable task."""
    stt, llm, tts, simli = create_services(tenant)

    grounder = RAGGrounder(tenant, Retriever.from_tenant(tenant))
    rag = RAGGroundingProcessor(grounder)

    # Seed with a greeting prompt; the RAG processor swaps in the grounded,
    # brand-safe contract on every real user turn.
    context = LLMContext(messages=[{"role": "system", "content": _greeting_system_prompt(tenant)}])
    aggregator = LLMContextAggregatorPair(context)

    # Avatar is optional — drop Simli for an audio-only loop when it isn't ready.
    processors = [
        transport.input(),       # WebRTC mic in
        stt,                     # Deepgram STT (AR/EN)
        aggregator.user(),       # aggregate the user's turn into the context
        rag,                     # inject approved-knowledge grounding
        llm,                     # Claude, under the brand-safety contract
        tts,                     # ElevenLabs TTS
    ]
    if simli is not None:
        processors.append(simli)  # Simli lip-synced video
    else:
        logger.warning(f"[{tenant.id}] avatar not available — running audio-only")
    processors += [
        transport.output(),      # WebRTC audio (+ video) out
        aggregator.assistant(),  # record the assistant turn back into context
    ]
    pipeline = Pipeline(processors)

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True, enable_metrics=True),
    )

    @transport.event_handler("on_client_connected")
    async def _on_connected(_transport, _client):
        logger.info(f"[{tenant.id}] client connected — greeting")
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def _on_disconnected(_transport, _client):
        logger.info(f"[{tenant.id}] client disconnected")
        await task.cancel()

    return task


async def run_bot(transport: BaseTransport, tenant: TenantConfig | None = None) -> None:
    """Run the live pipeline for a connected transport."""
    tenant = tenant or load_tenant(DEFAULT_TENANT)
    task = create_task(transport, tenant)
    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
