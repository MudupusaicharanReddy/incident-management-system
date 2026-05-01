# Implementation Plan

1. Build a FastAPI backend with async endpoints and a bounded `asyncio.Queue` to absorb ingestion bursts.
2. Process signals in background workers so slow persistence does not block request handling.
3. Separate data responsibilities into raw signal lake, incident repository, dashboard cache, and aggregation store.
4. Use an alerting strategy per component class and an incident state machine for lifecycle transitions.
5. Build a React dashboard that polls the hot dashboard state and drills into incident details.
6. Package the app with Docker Compose and include a replay script for a simulated RDBMS outage followed by MCP and cache failures.

Tradeoff for this assignment build:

The stores are in-memory to keep local review and tests fast. The boundaries mirror production storage choices: MongoDB or ClickHouse/S3 for the raw signal lake, PostgreSQL for incident/RCA transactions, Redis for hot dashboard state, and TimescaleDB/ClickHouse for aggregations.
