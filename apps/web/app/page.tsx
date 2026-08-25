"use client";

import { FormEvent, startTransition, useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { categories, ScanRun, SystemStatus } from "@/lib/types";

const activeStatuses = new Set(["queued", "profiling", "running", "reporting"]);

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function label(value: string) {
  return value.replaceAll("_", " ");
}

export default function Dashboard() {
  const [runs, setRuns] = useState<ScanRun[]>([]);
  const [selected, setSelected] = useState<ScanRun | null>(null);
  const [targetType, setTargetType] = useState<"api" | "browser">("api");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [system, setSystem] = useState<SystemStatus | null>(null);

  const refresh = useCallback(async () => {
    try {
      const nextRuns = await api.listRuns();
      setRuns(nextRuns);
      setSelected((current) =>
        current ? nextRuns.find((run) => run.id === current.id) ?? current : nextRuns[0] ?? null,
      );
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to reach API");
    }
  }, []);

  useEffect(() => {
    refresh();
    api.getStatus().then(setSystem).catch(() => undefined);
    const timer = window.setInterval(refresh, 1500);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const url = String(data.get("url"));
    try {
      const run = await api.createRun({
        name: data.get("name"),
        target: {
          type: targetType,
          url,
          model: targetType === "api" ? String(data.get("model") || "demo") : undefined,
          authorization_confirmed: data.get("authorized") === "on",
          ...(targetType === "browser"
            ? {
                selectors: {
                  input: "#message-input",
                  submit: "#send-message",
                  messages: "#messages [data-role='assistant']",
                },
              }
            : {}),
        },
        categories,
        max_attempts: Number(data.get("max_attempts")),
      });
      startTransition(() => {
        setRuns((current) => [run, ...current]);
        setSelected(run);
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Run creation failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main>
      <header className="masthead">
        <div className="brand-mark">AP</div>
        <div>
          <p className="eyebrow">Prompt-injection observatory</p>
          <h1>AgentProbe</h1>
        </div>
        <div className="system-state"><span />
          {system?.groq_configured ? "GROQ ACTIVE" : "LOCAL FALLBACK"} / {system?.dataset.exists ? "CORPUS READY" : "BUILT-INS"}
        </div>
      </header>

      {error && <div className="error-banner">API ERROR / {error}</div>}

      <section className="command-grid">
        <form className="launch-panel" onSubmit={submit}>
          <div className="section-heading"><span>01</span><h2>Launch probe</h2></div>
          <label>Run designation<input name="name" defaultValue="Local baseline scan" required /></label>
          <div className="target-switch">
            <button type="button" className={targetType === "api" ? "active" : ""} onClick={() => setTargetType("api")}>API</button>
            <button type="button" className={targetType === "browser" ? "active" : ""} onClick={() => setTargetType("browser")}>BROWSER</button>
          </div>
          <label>Target URL<input name="url" key={targetType} defaultValue={targetType === "api" ? "http://localhost:8000/api/v1/demo/chat" : "http://localhost:8000/demo"} required /></label>
          {targetType === "api" && <label>Target model<input name="model" defaultValue="demo" placeholder="demo or demo-hardened" /></label>}
          <label>Attempt budget<input name="max_attempts" type="number" min="1" max="50" defaultValue="9" /></label>
          <label className="authorization"><input name="authorized" type="checkbox" required /><span>I confirm authorization to test this target.</span></label>
          <button className="launch-button" disabled={submitting}>{submitting ? "INITIALIZING..." : "START SCAN"}<b>↗</b></button>
        </form>

        <div className="run-index">
          <div className="section-heading"><span>02</span><h2>Run index</h2></div>
          <div className="run-list">
            {runs.length === 0 && <p className="empty">No telemetry yet. Launch the controlled baseline.</p>}
            {runs.map((run) => (
              <button key={run.id} className={`run-row ${selected?.id === run.id ? "selected" : ""}`} onClick={() => setSelected(run)}>
                <span className={`status-dot ${run.status}`} />
                <span><b>{run.name}</b><small>{run.target.type} / {run.attempts.length} attempts</small></span>
                <em>{run.status}</em>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="telemetry">
        <div className="section-heading"><span>03</span><h2>Finding telemetry</h2></div>
        {!selected ? <p className="empty">Select a run to inspect evidence.</p> : <RunDetail run={selected} />}
      </section>
    </main>
  );
}

function RunDetail({ run }: { run: ScanRun }) {
  const report = run.report;
  return <>
    <div className="metric-strip">
      <Metric title="Attack success" value={report ? percent(report.attack_success_rate) : "--"} accent />
      <Metric title="Avg. severity" value={report ? `${report.average_severity}/5` : "--"} />
      <Metric title="Executed" value={String(run.attempts.length).padStart(2, "0")} />
      <Metric title="Tokens used" value={report ? report.total_tokens.toLocaleString() : "--"} />
      <Metric title="Elapsed" value={report ? `${(report.duration_ms / 1000).toFixed(1)}s` : run.status.toUpperCase()} />
    </div>
    {run.error && <div className="error-banner">RUN FAILED / {run.error}</div>}
    <div className="detail-grid">
      <div className="findings">
        <h3>Attack evidence</h3>
        {run.attempts.length === 0 && <p className="empty">Profiler active. Awaiting first attack response.</p>}
        {run.attempts.map((attempt) => <article className="finding" key={attempt.id}>
          <div className="finding-top"><span className={attempt.evaluation.success ? "breach" : "resisted"}>{attempt.evaluation.success ? "BREACH" : "RESISTED"}</span><b>SEV {attempt.evaluation.severity}</b><small>{Object.values(attempt.token_usage).reduce((sum, usage) => sum + usage.total_tokens, 0).toLocaleString()} tokens / {attempt.duration_ms} ms</small></div>
          <h4>{label(attempt.category)} <small>/ {attempt.source}</small></h4>
          <p>{attempt.evaluation.rationale}</p>
          <details><summary>Inspect exchange</summary><label className="exchange-label">Attack prompt</label><code>{attempt.prompt}</code><label className="exchange-label">Target response</label><code>{attempt.response}</code></details>
        </article>)}
      </div>
      <aside className="coverage">
        <h3>Category exposure</h3>
        {report ? Object.entries(report.category_vulnerability).map(([category, rate]) => <div className="bar-row" key={category}><span>{label(category)}</span><div><i style={{ width: percent(rate) }} /></div><b>{percent(rate)}</b></div>) : <p className="empty">Available after report generation.</p>}
        {report && <div className="recommendations"><h3>Token breakdown</h3>{Object.entries(report.token_usage).map(([role, usage]) => <p key={role}><b>{role.toUpperCase()}</b> {usage.total_tokens.toLocaleString()} total ({usage.input_tokens.toLocaleString()} in / {usage.output_tokens.toLocaleString()} out)</p>)}<h3>Defensive actions</h3>{report.recommendations.map((item) => <p key={item}>{item}</p>)}</div>}
      </aside>
    </div>
  </>;
}

function Metric({ title, value, accent = false }: { title: string; value: string; accent?: boolean }) {
  return <div className={`metric ${accent ? "accent" : ""}`}><span>{title}</span><strong>{value}</strong></div>;
}
