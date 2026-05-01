from datetime import datetime, timedelta, timezone

import pytest

from app.models import ComponentType, Incident, IncidentStatus, RCA, Severity
from app.workflow import IncidentStateMachine, WorkflowError, validate_rca


def make_incident() -> Incident:
    now = datetime.now(timezone.utc)
    return Incident(
        component_id="RDBMS_PRIMARY",
        component_type=ComponentType.RDBMS,
        severity=Severity.P0,
        title="RDBMS_PRIMARY: connection failures",
        signal_count=100,
        first_signal_at=now,
        last_signal_at=now,
        alert_channel="pagerduty:database-oncall",
    )


def test_rejects_close_without_rca() -> None:
    incident = make_incident()
    incident.status = IncidentStatus.RESOLVED

    with pytest.raises(WorkflowError, match="RCA is required"):
        IncidentStateMachine(incident).transition_to(IncidentStatus.CLOSED)


def test_rejects_incomplete_rca() -> None:
    now = datetime.now(timezone.utc)
    rca = RCA(
        incident_start=now,
        incident_end=now + timedelta(minutes=10),
        root_cause_category="Database",
        fix_applied="     ",
        prevention_steps="Add failover automation",
    )

    with pytest.raises(WorkflowError, match="incomplete"):
        validate_rca(rca)


def test_close_calculates_mttr() -> None:
    incident = make_incident()
    incident.status = IncidentStatus.RESOLVED
    rca = RCA(
        incident_start=incident.first_signal_at,
        incident_end=incident.first_signal_at + timedelta(minutes=15),
        root_cause_category="Database saturation",
        fix_applied="Promoted read replica",
        prevention_steps="Add connection pool alerts",
    )

    closed = IncidentStateMachine(incident).transition_to(IncidentStatus.CLOSED, rca)

    assert closed.status == IncidentStatus.CLOSED
    assert closed.mttr_seconds == 900
