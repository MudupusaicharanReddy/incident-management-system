from datetime import datetime, timezone

import pytest

from app.models import ComponentType, Signal
from app.stores import IncidentRepository


@pytest.mark.anyio
async def test_debounces_many_signals_for_same_component() -> None:
    repo = IncidentRepository()
    observed_at = datetime.now(timezone.utc)
    incidents = []

    for index in range(100):
        signal = Signal(
            component_id="CACHE_CLUSTER_01",
            component_type=ComponentType.CACHE,
            message="Eviction rate spike",
            observed_at=observed_at,
            payload={"index": index},
        )
        incidents.append(await repo.get_or_create_debounced(signal, window_seconds=10))

    assert len({incident.id for incident in incidents}) == 1
    assert incidents[-1].signal_count == 100
    assert incidents[-1].severity == "P2"
