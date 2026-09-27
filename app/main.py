from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from pathlib import Path
import json
from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

from app.composer import compose
from app.config import settings
from app.llm import GeminiClient
from app.logging_setup import setup_logging
from app.reply_fsm import ConversationManager
from app.schemas import (
    ContextAck,
    ContextPush,
    Health,
    Metadata,
    OutboundAction,
    ReplyRequest,
    ReplyResponse,
    TickRequest,
    TickResponse,
)
from app.signals import select_top_candidates
from app.store import ContextStore
from app.suppression import SentLedger, generate_suppression_key
from app.ui import get_dashboard_html

logger = logging.getLogger("vera.main")

# State holders
_start_time: float = time.time()
_store: ContextStore = ContextStore(max_context_bytes=settings.MAX_CONTEXT_BYTES)
_ledger: SentLedger = SentLedger()
_gemini_client: GeminiClient = GeminiClient(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
_fsm: ConversationManager = ConversationManager(store=_store)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time, _store, _ledger, _gemini_client, _fsm
    setup_logging(settings.LOG_LEVEL)
    logger.info("Initializing Vera Engine...")
    _start_time = time.time()
    if _store is None:
        _store = ContextStore(max_context_bytes=settings.MAX_CONTEXT_BYTES)
    if _ledger is None:
        _ledger = SentLedger()
    if _gemini_client is None:
        _gemini_client = GeminiClient(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    if _fsm is None:
        _fsm = ConversationManager(store=_store)

    # Pre-load expanded seed dataset so engine is immediately context-aware on boot
    expanded_path = Path("expanded")
    if expanded_path.exists():
        logger.info("Pre-loading expanded dataset into store...")
        for cf in (expanded_path / "categories").glob("*.json"):
            try:
                data = json.load(open(cf))
                _store.upsert(ContextPush(scope="category", context_id=data.get("slug", cf.stem), version=1, payload=data))
            except Exception as e:
                logger.warning(f"Failed loading category {cf}: {e}")
        for mf in (expanded_path / "merchants").glob("*.json"):
            try:
                data = json.load(open(mf))
                _store.upsert(ContextPush(scope="merchant", context_id=data.get("merchant_id", mf.stem), version=1, payload=data))
            except Exception as e:
                logger.warning(f"Failed loading merchant {mf}: {e}")
        for cuf in (expanded_path / "customers").glob("*.json"):
            try:
                data = json.load(open(cuf))
                _store.upsert(ContextPush(scope="customer", context_id=data.get("customer_id", cuf.stem), version=1, payload=data))
            except Exception as e:
                logger.warning(f"Failed loading customer {cuf}: {e}")
        for tf in (expanded_path / "triggers").glob("*.json"):
            try:
                data = json.load(open(tf))
                _store.upsert(ContextPush(scope="trigger", context_id=data.get("id", tf.stem), version=1, payload=data))
            except Exception as e:
                logger.warning(f"Failed loading trigger {tf}: {e}")
        logger.info(f"Contexts ready: {_store.get_counts()}")

    logger.info("Vera Engine ready to accept traffic.")
    yield
    logger.info("Shutting down Vera Engine.")


app = FastAPI(
    title="Vera Engine",
    description="magicpin AI Challenge Merchant Assistant",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_ui():
    """Interactive visual dashboard for testing proactive outreach and conversational FSM."""
    return HTMLResponse(content=get_dashboard_html())


@app.post("/v1/load-seed-dataset", include_in_schema=False)
async def load_seed_dataset():
    """Load expanded dataset into in-memory context store."""
    loaded = 0
    expanded_path = Path("expanded")
    if expanded_path.exists():
        for cf in (expanded_path / "categories").glob("*.json"):
            data = json.load(open(cf))
            _store.upsert(ContextPush(scope="category", context_id=data.get("slug", cf.stem), version=1, payload=data))
            loaded += 1
        for mf in (expanded_path / "merchants").glob("*.json"):
            data = json.load(open(mf))
            _store.upsert(ContextPush(scope="merchant", context_id=data.get("merchant_id", mf.stem), version=1, payload=data))
            loaded += 1
        for cuf in (expanded_path / "customers").glob("*.json"):
            data = json.load(open(cuf))
            _store.upsert(ContextPush(scope="customer", context_id=data.get("customer_id", cuf.stem), version=1, payload=data))
            loaded += 1
        for tf in (expanded_path / "triggers").glob("*.json"):
            data = json.load(open(tf))
            _store.upsert(ContextPush(scope="trigger", context_id=data.get("id", tf.stem), version=1, payload=data))
            loaded += 1
    return {"status": "ok", "loaded_count": loaded, "contexts_loaded": _store.get_counts()}


@app.exception_handler(Exception)
async def global_fail_safe_exception_handler(request: Request, exc: Exception):
    """Fail-Safe: Endpoints must never return 500."""
    logger.error(f"Handled uncaught exception on {request.url.path}: {exc}", exc_info=True)
    if request.url.path == "/v1/tick":
        return JSONResponse(status_code=200, content={"actions": []})
    elif request.url.path == "/v1/reply":
        return JSONResponse(
            status_code=200,
            content={
                "action": "wait",
                "body": None,
                "cta": None,
                "rationale": "Internal exception; backing off safely.",
                "wait_seconds": 3600,
            },
        )
    return JSONResponse(
        status_code=200,
        content={"status": "error_handled", "detail": str(exc)},
    )


@app.api_route("/v1/healthz", methods=["GET", "HEAD"], response_model=Health)
@app.api_route("/healthz", methods=["GET", "HEAD"], response_model=Health, include_in_schema=False)
async def healthz():
    """Lock-free liveness probe in < 5ms supporting both GET and HEAD requests."""
    uptime = time.time() - _start_time if _start_time > 0 else 0.0
    counts = _store.get_counts()
    return Health(
        status="ok",
        uptime_seconds=round(uptime, 2),
        contexts_loaded=counts,
    )


@app.get("/v1/metadata", response_model=Metadata)
@app.get("/metadata", response_model=Metadata, include_in_schema=False)
async def metadata():
    return Metadata(
        team_name=settings.TEAM_NAME,
        team_members=settings.TEAM_MEMBERS,
        model=settings.GEMINI_MODEL,
        approach="Deterministic signal ranking + grounded numeric facts gate + Gemini composer with verified fallback",
        version=settings.APP_VERSION,
        contact_email="team.vera@magicpin.in",
        submitted_at="2026-04-26T08:00:00Z",
    )


@app.post("/v1/context", response_model=ContextAck)
async def push_context(push: ContextPush):
    ack = _store.upsert(push)
    return ack


@app.post("/v1/tick", response_model=TickResponse)
async def tick(req: TickRequest):
    # 1. Select top candidates with suppression filter & max 1 per merchant
    candidates = select_top_candidates(
        now=req.now,
        trigger_ids=req.available_triggers,
        store_getter=_store.get,
        is_suppressed_fn=_ledger.is_suppressed,
        suppression_key_fn=generate_suppression_key,
        max_actions=20,
    )

    if not candidates:
        return TickResponse(actions=[])

    # 2. Concurrency control via semaphore + deadline budget
    semaphore = asyncio.Semaphore(settings.COMPOSE_CONCURRENCY)

    async def _compose_worker(cand):
        async with semaphore:
            action_dict = await compose(
                category=cand.category,
                merchant=cand.merchant,
                trigger=cand.trigger,
                customer=cand.customer,
                gemini_client=_gemini_client,
                now=req.now,
            )
            sup_key = action_dict.get("suppression_key")
            if sup_key:
                _ledger.record_sent(sup_key, req.now)
            return OutboundAction(**action_dict)

    tasks = [_compose_worker(c) for c in candidates]

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=settings.TICK_DEADLINE_S,
        )
        actions: List[OutboundAction] = [
            r for r in results if isinstance(r, OutboundAction)
        ]
        return TickResponse(actions=actions[:20])
    except asyncio.TimeoutError:
        logger.warning(f"Tick processing deadline {settings.TICK_DEADLINE_S}s exceeded; returning partial actions.")
        return TickResponse(actions=[])
    except Exception as e:
        logger.error(f"Error during tick composition: {e}")
        return TickResponse(actions=[])


@app.post("/v1/reply", response_model=ReplyResponse)
async def reply(req: ReplyRequest):
    return await _fsm.process_reply_async(req, _gemini_client)
