from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

from .alerting import strategy_for
from .models import DashboardState, Incident, IncidentStatus, RCA, Signal
from .workflow import IncidentStateMachine, WorkflowError


SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


class RawSignalLake:
    """NoSQL-style append-only audit log for every signal."""

    def __init__(self) -> None:
        self._signals: dict[str, Signal] = {}
        self._by_incident: dict[str, list[str]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def put(self, signal: Signal) -> None:
        async with self._lock:
            self._signals[signal.id] = signal
            if signal.incident_id:
                self._by_incident[signal.incident_id].append(signal.id)

    async def list_for_incident(self, incident_id: str) -> list[Signal]:
        async with self._lock:
            return [self._signals[sid] for sid in self._by_incident.get(incident_id, [])]

    async def count(self) -> int:
        async with self._lock:
            return len(self._signals)


class IncidentRepository:
    """Transactional source of truth for incidents and RCA records."""

    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}
        self._active_by_component: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_debounced(self, signal: Signal, window_seconds: int) -> Incident:
        async with self._lock:
            now = signal.observed_at or signal.received_at
            existing_id = self._active_by_component.get(signal.component_id)
            if existing_id:
                existing = self._incidents[existing_id]
                inside_window = now - existing.first_signal_at <= timedelta(seconds=window_seconds)
                if existing.status != IncidentStatus.CLOSED and inside_window:
                    existing.signal_count += 1
                    existing.last_signal_at = now
                    existing.updated_at = datetime.now(timezone.utc)
                    return existing

            strategy = strategy_for(signal.component_type)
            incident = Incident(
                component_id=signal.component_id,
                component_type=signal.component_type,
                severity=strategy.severity(signal),
                title=f"{signal.component_id}: {signal.message}",
                signal_count=1,
                first_signal_at=now,
                last_signal_at=now,
                alert_channel=strategy.channel(signal),
            )
            self._incidents[incident.id] = incident
            self._active_by_component[signal.component_id] = incident.id
            return incident

    async def list_active(self) -> list[Incident]:
        async with self._lock:
            active = [i for i in self._incidents.values() if i.status != IncidentStatus.CLOSED]
            return sorted(active, key=lambda i: (SEVERITY_ORDER[i.severity.value], i.created_at))

    async def list_all(self) -> list[Incident]:
        async with self._lock:
            return sorted(self._incidents.values(), key=lambda i: i.created_at, reverse=True)

    async def get(self, incident_id: str) -> Incident | None:
        async with self._lock:
            return self._incidents.get(incident_id)

    async def transition(self, incident_id: str, status: IncidentStatus, rca: RCA | None = None) -> Incident:
        async with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(incident_id)
            updated = IncidentStateMachine(incident).transition_to(status, rca)
            updated.updated_at = datetime.now(timezone.utc)
            if updated.status == IncidentStatus.CLOSED:
                self._active_by_component.pop(updated.component_id, None)
            return updated

    async def attach_rca(self, incident_id: str, rca: RCA) -> Incident:
        async with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                raise KeyError(incident_id)
            incident.rca = rca
            incident.mttr_seconds = (rca.incident_end - incident.first_signal_at).total_seconds()
            incident.updated_at = datetime.now(timezone.utc)
            return incident


class HotDashboardCache:
    def __init__(self) -> None:
        self._state: DashboardState | None = None
        self._lock = asyncio.Lock()

    async def set(self, state: DashboardState) -> None:
        async with self._lock:
            self._state = state

    async def get(self) -> DashboardState | None:
        async with self._lock:
            return self._state


class TimeSeriesAggregations:
    def __init__(self) -> None:
        self._buckets: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def add(self, signal: Signal) -> None:
        bucket = signal.received_at.strftime("%Y-%m-%dT%H:%M:00Z")
        async with self._lock:
            self._buckets[bucket] += 1

    async def list(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [{"minute": minute, "signals": count} for minute, count in sorted(self._buckets.items())]


class ThroughputMeter:
    def __init__(self) -> None:
        self._events: deque[datetime] = deque()
        self._lock = asyncio.Lock()

    async def mark(self, amount: int = 1) -> None:
        now = datetime.now(timezone.utc)
        async with self._lock:
            for _ in range(amount):
                self._events.append(now)
            self._trim(now)

    async def rate(self) -> float:
        now = datetime.now(timezone.utc)
        async with self._lock:
            self._trim(now)
            return round(len(self._events) / 5, 2)

    def _trim(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=5)
        while self._events and self._events[0] < cutoff:
            self._events.popleft()


async def retry_db_write(operation, attempts: int = 3, delay_seconds: float = 0.05):
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return await operation()
        except Exception as exc:  # pragma: no cover - defensive retry wrapper
            last_error = exc
            await asyncio.sleep(delay_seconds * (2**attempt))
    raise last_error or WorkflowError("Unknown persistence failure")
