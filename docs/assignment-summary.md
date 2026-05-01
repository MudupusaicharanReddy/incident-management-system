# Assignment Summary

The assignment asks for an Incident Management System that can ingest high-volume signals from distributed infrastructure, debounce repeated component failures, persist raw signals separately from structured work items, drive an incident workflow, and enforce mandatory RCA before closure.

Core requirements implemented here:

- Async signal ingestion through FastAPI and an internal bounded queue.
- Token-bucket rate limiting on ingestion endpoints.
- Debouncing by `component_id` within a 10-second incident window.
- Raw signal lake, incident source of truth, hot dashboard cache, and timeseries aggregation modules.
- Alerting Strategy pattern for component-specific severity and notification channel selection.
- State pattern style workflow for `OPEN -> INVESTIGATING -> RESOLVED -> CLOSED`.
- RCA validation and MTTR calculation.
- Responsive React dashboard with live incident feed, raw signal detail, status controls, and RCA form.
- `/health` endpoint and console throughput metrics every 5 seconds.
- Unit tests for mandatory RCA behavior.
