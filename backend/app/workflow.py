from __future__ import annotations

from dataclasses import dataclass

from .models import Incident, IncidentStatus, RCA


class WorkflowError(ValueError):
    pass


ALLOWED_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.OPEN: {IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED},
    IncidentStatus.INVESTIGATING: {IncidentStatus.RESOLVED, IncidentStatus.OPEN},
    IncidentStatus.RESOLVED: {IncidentStatus.CLOSED, IncidentStatus.INVESTIGATING},
    IncidentStatus.CLOSED: set(),
}


@dataclass(frozen=True)
class IncidentStateMachine:
    incident: Incident

    def transition_to(self, next_status: IncidentStatus, rca: RCA | None = None) -> Incident:
        current = self.incident.status
        if next_status == current:
            return self.incident
        if next_status not in ALLOWED_TRANSITIONS[current]:
            raise WorkflowError(f"Cannot transition incident from {current} to {next_status}")
        if next_status == IncidentStatus.CLOSED:
            final_rca = rca or self.incident.rca
            validate_rca(final_rca)
            self.incident.rca = final_rca
            self.incident.mttr_seconds = (
                final_rca.incident_end - self.incident.first_signal_at
            ).total_seconds()
        self.incident.status = next_status
        return self.incident


def validate_rca(rca: RCA | None) -> None:
    if rca is None:
        raise WorkflowError("RCA is required before closing an incident")
    if rca.incident_end < rca.incident_start:
        raise WorkflowError("Incident end must be after incident start")
    required_text = [rca.root_cause_category, rca.fix_applied, rca.prevention_steps]
    if any(not value.strip() for value in required_text):
        raise WorkflowError("RCA is incomplete")
