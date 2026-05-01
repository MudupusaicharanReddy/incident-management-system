from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ComponentType(str, Enum):
    API = "API"
    MCP_HOST = "MCP_HOST"
    CACHE = "CACHE"
    QUEUE = "QUEUE"
    RDBMS = "RDBMS"
    NOSQL = "NOSQL"


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class SignalIn(BaseModel):
    component_id: str = Field(..., min_length=2)
    component_type: ComponentType
    message: str = Field(..., min_length=3)
    observed_at: datetime | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    error_code: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Signal(SignalIn):
    id: str = Field(default_factory=lambda: str(uuid4()))
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    incident_id: str | None = None


class RCA(BaseModel):
    incident_start: datetime
    incident_end: datetime
    root_cause_category: str = Field(..., min_length=3)
    fix_applied: str = Field(..., min_length=5)
    prevention_steps: str = Field(..., min_length=5)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    component_id: str
    component_type: ComponentType
    severity: Severity
    status: IncidentStatus = IncidentStatus.OPEN
    title: str
    signal_count: int = 0
    first_signal_at: datetime
    last_signal_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rca: RCA | None = None
    mttr_seconds: float | None = None
    alert_channel: str


class StatusUpdate(BaseModel):
    status: IncidentStatus


class IngestResponse(BaseModel):
    accepted: int
    queue_depth: int
    rejected: int = 0


class DashboardState(BaseModel):
    active_incidents: list[Incident]
    signals_per_second: float
    queue_depth: int
    total_signals: int
