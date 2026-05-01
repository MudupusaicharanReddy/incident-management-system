from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .models import DashboardState, IncidentStatus, IngestResponse, RCA, Signal, SignalIn, StatusUpdate
from .rate_limit import TokenBucket
from .stores import (
    HotDashboardCache,
    IncidentRepository,
    RawSignalLake,
    ThroughputMeter,
    TimeSeriesAggregations,
    retry_db_write,
)
from .workflow import WorkflowError

DEBOUNCE_SECONDS = 10
QUEUE_MAX_SIZE = 50_000

signal_queue: asyncio.Queue[Signal] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
raw_lake = RawSignalLake()
incident_repo = IncidentRepository()
dashboard_cache = HotDashboardCache()
aggregations = TimeSeriesAggregations()
throughput = ThroughputMeter()
rate_limiter = TokenBucket(rate_per_second=10_000, capacity=20_000)
workers: list[asyncio.Task] = []


async def process_signal(signal: Signal) -> None:
    incident = await retry_db_write(lambda: incident_repo.get_or_create_debounced(signal, DEBOUNCE_SECONDS))
    signal.incident_id = incident.id
    await retry_db_write(lambda: raw_lake.put(signal))
    await aggregations.add(signal)
    await throughput.mark()


async def signal_worker() -> None:
    while True:
        signal = await signal_queue.get()
        try:
            await process_signal(signal)
        finally:
            signal_queue.task_done()


async def refresh_dashboard_cache() -> None:
    while True:
        active = await incident_repo.list_active()
        state = DashboardState(
            active_incidents=active,
            signals_per_second=await throughput.rate(),
            queue_depth=signal_queue.qsize(),
            total_signals=await raw_lake.count(),
        )
        await dashboard_cache.set(state)
        await asyncio.sleep(1)


async def print_metrics() -> None:
    while True:
        await asyncio.sleep(5)
        print(
            f"metrics signals_per_sec={await throughput.rate()} "
            f"queue_depth={signal_queue.qsize()} total_signals={await raw_lake.count()}",
            flush=True,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    for _ in range(4):
        workers.append(asyncio.create_task(signal_worker()))
    workers.append(asyncio.create_task(refresh_dashboard_cache()))
    workers.append(asyncio.create_task(print_metrics()))
    yield
    for worker in workers:
        worker.cancel()


app = FastAPI(title="Incident Management System", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str | int]:
    return {"status": "ok", "queue_depth": signal_queue.qsize()}


@app.post("/signals", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_signal(signal_in: SignalIn) -> IngestResponse:
    if not await rate_limiter.allow():
        raise HTTPException(status_code=429, detail="Ingestion rate limit exceeded")
    signal = Signal(**signal_in.model_dump())
    try:
        signal_queue.put_nowait(signal)
    except asyncio.QueueFull:
        raise HTTPException(status_code=503, detail="Backpressure queue is full") from None
    return IngestResponse(accepted=1, queue_depth=signal_queue.qsize())


@app.post("/signals/batch", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_batch(signals: list[SignalIn]) -> IngestResponse:
    if not signals:
        return IngestResponse(accepted=0, queue_depth=signal_queue.qsize())
    if not await rate_limiter.allow(len(signals)):
        raise HTTPException(status_code=429, detail="Ingestion rate limit exceeded")

    accepted = 0
    for signal_in in signals:
        try:
            signal_queue.put_nowait(Signal(**signal_in.model_dump()))
            accepted += 1
        except asyncio.QueueFull:
            break
    rejected = len(signals) - accepted
    if accepted == 0 and rejected:
        raise HTTPException(status_code=503, detail="Backpressure queue is full")
    return IngestResponse(accepted=accepted, rejected=rejected, queue_depth=signal_queue.qsize())


@app.get("/dashboard", response_model=DashboardState)
async def dashboard() -> DashboardState:
    cached = await dashboard_cache.get()
    if cached:
        return cached
    return DashboardState(
        active_incidents=await incident_repo.list_active(),
        signals_per_second=await throughput.rate(),
        queue_depth=signal_queue.qsize(),
        total_signals=await raw_lake.count(),
    )


@app.get("/incidents")
async def list_incidents():
    return await incident_repo.list_all()


@app.get("/incidents/{incident_id}")
async def incident_detail(incident_id: str):
    incident = await incident_repo.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    signals = await raw_lake.list_for_incident(incident_id)
    return {"incident": incident, "signals": signals}


@app.patch("/incidents/{incident_id}/status")
async def update_status(incident_id: str, update: StatusUpdate):
    try:
        return await incident_repo.transition(incident_id, update.status)
    except KeyError:
        raise HTTPException(status_code=404, detail="Incident not found") from None
    except WorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@app.post("/incidents/{incident_id}/rca")
async def submit_rca(incident_id: str, rca: RCA, response: Response):
    try:
        incident = await incident_repo.attach_rca(incident_id, rca)
        if incident.status == IncidentStatus.RESOLVED:
            incident = await incident_repo.transition(incident_id, IncidentStatus.CLOSED, rca)
            response.status_code = status.HTTP_200_OK
        return incident
    except KeyError:
        raise HTTPException(status_code=404, detail="Incident not found") from None
    except WorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@app.get("/aggregations")
async def list_aggregations():
    return await aggregations.list()
