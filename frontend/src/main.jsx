import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Activity, AlertTriangle, CheckCircle2, Clock, Database, RefreshCw, Send } from "lucide-react";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const severityRank = { P0: 0, P1: 1, P2: 2, P3: 3 };

function formatDate(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

async function api(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || response.statusText);
  }
  return response.json();
}

function App() {
  const [dashboard, setDashboard] = useState({ active_incidents: [], signals_per_second: 0, queue_depth: 0, total_signals: 0 });
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const selected = detail?.incident || dashboard.active_incidents.find((incident) => incident.id === selectedId);
  const sortedIncidents = useMemo(
    () => [...dashboard.active_incidents].sort((a, b) => severityRank[a.severity] - severityRank[b.severity]),
    [dashboard.active_incidents],
  );

  async function loadDashboard() {
    try {
      const next = await api("/dashboard");
      setDashboard(next);
      if (!selectedId && next.active_incidents.length) setSelectedId(next.active_incidents[0].id);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadDetail(id) {
    if (!id) return;
    try {
      setDetail(await api(`/incidents/${id}`));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadDashboard();
    const handle = setInterval(loadDashboard, 1500);
    return () => clearInterval(handle);
  }, []);

  useEffect(() => {
    loadDetail(selectedId);
  }, [selectedId]);

  async function seedOutage() {
    setLoading(true);
    setError("");
    const now = new Date().toISOString();
    const signals = [
      ...Array.from({ length: 100 }, (_, index) => ({
        component_id: "RDBMS_PRIMARY",
        component_type: "RDBMS",
        message: "Connection pool exhausted",
        observed_at: now,
        latency_ms: 2500 + index,
        error_code: "DB_POOL_TIMEOUT",
        payload: { host: "db-primary-1", sample: index },
      })),
      ...Array.from({ length: 18 }, (_, index) => ({
        component_id: "MCP_HOST_02",
        component_type: "MCP_HOST",
        message: "Tool host heartbeat missed",
        observed_at: now,
        latency_ms: 900,
        error_code: "MCP_HEARTBEAT_MISSED",
        payload: { region: "us-east", sample: index },
      })),
    ];
    try {
      await api("/signals/batch", { method: "POST", body: JSON.stringify(signals) });
      await loadDashboard();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function moveStatus(status) {
    if (!selected) return;
    try {
      const updated = await api(`/incidents/${selected.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setDetail((current) => ({ ...(current || {}), incident: updated }));
      await loadDashboard();
    } catch (err) {
      setError(err.message);
    }
  }

  async function submitRca(event) {
    event.preventDefault();
    if (!selected) return;
    const form = new FormData(event.currentTarget);
    const rca = Object.fromEntries(form.entries());
    rca.incident_start = new Date(rca.incident_start).toISOString();
    rca.incident_end = new Date(rca.incident_end).toISOString();
    try {
      const updated = await api(`/incidents/${selected.id}/rca`, {
        method: "POST",
        body: JSON.stringify(rca),
      });
      setDetail((current) => ({ ...(current || {}), incident: updated }));
      await loadDashboard();
      event.currentTarget.reset();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark"><Activity size={22} /></div>
          <div>
            <h1>Incident Management System</h1>
            <p>Mission-critical signal triage</p>
          </div>
        </div>

        <div className="metrics">
          <Metric icon={<Send />} label="Signals/sec" value={dashboard.signals_per_second} />
          <Metric icon={<Clock />} label="Queue depth" value={dashboard.queue_depth} />
          <Metric icon={<Database />} label="Raw signals" value={dashboard.total_signals} />
        </div>

        <div className="actions">
          <button onClick={seedOutage} disabled={loading} title="Send sample RDBMS and MCP signals">
            <AlertTriangle size={18} /> Simulate outage
          </button>
          <button className="secondary" onClick={loadDashboard} title="Refresh dashboard state">
            <RefreshCw size={18} /> Refresh
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        <section className="feed">
          <h2>Live Feed</h2>
          {sortedIncidents.length === 0 && <p className="empty">No active incidents.</p>}
          {sortedIncidents.map((incident) => (
            <button
              key={incident.id}
              className={`incidentRow ${selectedId === incident.id ? "selected" : ""}`}
              onClick={() => setSelectedId(incident.id)}
            >
              <span className={`sev ${incident.severity}`}>{incident.severity}</span>
              <span>
                <strong>{incident.component_id}</strong>
                <small>{incident.status} · {incident.signal_count} signals</small>
              </span>
            </button>
          ))}
        </section>
      </aside>

      <section className="detailPane">
        {!selected && (
          <div className="blank">
            <AlertTriangle size={36} />
            <h2>No incident selected</h2>
            <p>Simulate an outage or ingest signals through the API to populate the workflow.</p>
          </div>
        )}

        {selected && (
          <>
            <header className="incidentHeader">
              <div>
                <span className={`sev ${selected.severity}`}>{selected.severity}</span>
                <h2>{selected.title}</h2>
                <p>{selected.component_type} · Alert via {selected.alert_channel}</p>
              </div>
              <div className="statusPill">{selected.status}</div>
            </header>

            <div className="workflow">
              {["OPEN", "INVESTIGATING", "RESOLVED", "CLOSED"].map((status) => (
                <button key={status} onClick={() => moveStatus(status)} disabled={selected.status === status}>
                  {status === "CLOSED" ? <CheckCircle2 size={16} /> : <Clock size={16} />} {status}
                </button>
              ))}
            </div>

            <div className="contentGrid">
              <section className="panel">
                <h3>Raw Signals</h3>
                <div className="signalList">
                  {(detail?.signals || []).slice(0, 30).map((signal) => (
                    <article key={signal.id} className="signal">
                      <strong>{signal.error_code || "SIGNAL"}</strong>
                      <span>{signal.message}</span>
                      <small>{formatDate(signal.received_at)} · {signal.latency_ms ?? "-"} ms</small>
                    </article>
                  ))}
                </div>
              </section>

              <section className="panel">
                <h3>RCA Form</h3>
                <form onSubmit={submitRca} className="rcaForm">
                  <label>
                    Incident Start
                    <input name="incident_start" type="datetime-local" required />
                  </label>
                  <label>
                    Incident End
                    <input name="incident_end" type="datetime-local" required />
                  </label>
                  <label>
                    Root Cause Category
                    <select name="root_cause_category" required>
                      <option value="">Select category</option>
                      <option>Database saturation</option>
                      <option>Cache instability</option>
                      <option>Queue backlog</option>
                      <option>Deployment regression</option>
                      <option>Network partition</option>
                    </select>
                  </label>
                  <label>
                    Fix Applied
                    <textarea name="fix_applied" rows="4" required />
                  </label>
                  <label>
                    Prevention Steps
                    <textarea name="prevention_steps" rows="4" required />
                  </label>
                  <button type="submit"><CheckCircle2 size={18} /> Submit RCA</button>
                  {selected.mttr_seconds !== null && <p className="mttr">MTTR: {Math.round(selected.mttr_seconds / 60)} minutes</p>}
                </form>
              </section>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

function Metric({ icon, label, value }) {
  return (
    <div className="metric">
      {React.cloneElement(icon, { size: 18 })}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
