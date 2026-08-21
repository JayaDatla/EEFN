"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { Activity, RefreshCw, Layers, Pause } from 'lucide-react';
import { apiUrl } from '@/lib/api';
import { Callout } from '../components/ui/Callout';
import { Badge } from '../components/ui/Badge';

interface CatalogHealth {
  conflict_rate: number;
  ingestion_success_rate: number;
  cross_match_success_rate: number;
  stale_record_rate: number;
  unresolved_alert_count: number;
  resolved_conflict_count: number;
  total_candidates: number;
  last_sync: { nasa: string | null; gaia: string | null; toi: string | null };
}

interface PipelineRun {
  id: string;
  status: string;
  limit_requested: number;
  targets_processed: number | null;
  error_detail: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
}

const RUN_STATUS_TONE: Record<string, "status-pass" | "status-watch" | "status-risk" | "neutral"> = {
  success: "status-pass",
  queued: "status-watch",
  running: "status-watch",
  error: "status-risk",
  cancelled: "neutral",
};

export default function AdminDashboard() {
  const [health, setHealth] = useState<CatalogHealth | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [healthRes, runsRes] = await Promise.all([
        fetch(apiUrl('/api/v1/catalog/health')),
        fetch(apiUrl('/api/v1/pipeline/runs')),
      ]);
      if (!healthRes.ok) throw new Error(`catalog/health returned ${healthRes.status}`);
      setHealth(await healthRes.json());
      setRuns(runsRes.ok ? await runsRes.json() : []);
      setError(null);
    } catch (e) {
      // UPGRADE_PLAN.md A.14/H.3.8: this page used to hardcode "CONNECTED"
      // statuses, fabricated target counts, a fake Neo4j node count (Neo4j was
      // removed from the stack entirely per C.11), and -- worst of all -- claimed
      // "Pipeline execution completed" via a fixed setTimeout regardless of
      // whether the real backend call even succeeded. All real integrity bugs
      // found while rebuilding this page. Now: real data, or an explicit error.
      setHealth(null);
      setError(e instanceof Error ? e.message : "Unable to reach the EEFN backend.");
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  const triggerPipelineSync = async () => {
    setIsTriggering(true);
    setTriggerError(null);
    try {
      const res = await fetch(apiUrl('/api/v1/pipeline/run?limit=50'), { method: 'POST' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Backend returned ${res.status}`);
      }
      await load();
    } catch (e) {
      // A real failure is shown as a real failure -- never a fabricated
      // "completed" message, the bug this page had before.
      setTriggerError(e instanceof Error ? e.message : "Failed to trigger pipeline run.");
    } finally {
      setIsTriggering(false);
    }
  };

  const formatTime = (iso: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "never");

  return (
    <div className="flex-1 flex flex-col gap-6 max-w-7xl mx-auto w-full py-4 animate-fadeIn font-mono text-xs">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-border pb-5">
        <div>
          <h2 className="text-3xl font-display font-medium text-ink tracking-tight">
            Pipeline Telemetry &amp; Admin
          </h2>
          <p className="text-sm text-muted mt-1">
            Real per-source catalog health and pipeline run history -- no simulated data.
          </p>
        </div>
        <button
          onClick={triggerPipelineSync}
          disabled={isTriggering}
          className="inline-flex items-center gap-2 rounded-lg border border-accent/25 bg-accent/10 px-4 py-2.5 text-xs font-bold text-accent cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isTriggering ? 'animate-spin' : ''}`} />
          {isTriggering ? "TRIGGERING..." : "FORCE PIPELINE SYNC"}
        </button>
      </div>

      {error && <Callout tone="critical" title="Backend unavailable">{error}. No catalog health data is shown.</Callout>}
      {triggerError && <Callout tone="critical" title="Pipeline trigger failed">{triggerError}</Callout>}

      {health && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="surface-card p-4 flex flex-col gap-2">
            <span className="text-muted text-[10px] font-bold uppercase tracking-wider">NASA Archive</span>
            <span className="text-sm font-extrabold text-ink">Last sync: {formatTime(health.last_sync.nasa)}</span>
          </div>
          <div className="surface-card p-4 flex flex-col gap-2">
            <span className="text-muted text-[10px] font-bold uppercase tracking-wider">Gaia DR3 TAP</span>
            <span className="text-sm font-extrabold text-ink">Last sync: {formatTime(health.last_sync.gaia)}</span>
          </div>
          <div className="surface-card p-4 flex flex-col gap-2">
            <span className="text-muted text-[10px] font-bold uppercase tracking-wider">Ingestion Success Rate</span>
            <span className="text-sm font-extrabold text-ink">{(health.ingestion_success_rate * 100).toFixed(1)}%</span>
          </div>
          <div className="surface-card p-4 flex flex-col gap-2">
            <span className="text-muted text-[10px] font-bold uppercase tracking-wider">Stale Records ({'>'}30d)</span>
            <span className="text-sm font-extrabold text-ink">{(health.stale_record_rate * 100).toFixed(1)}%</span>
          </div>
        </div>
      )}

      <div className="surface-card p-5 flex flex-col gap-4">
        <h3 className="font-bold text-sm text-accent border-b border-border pb-2.5 flex items-center gap-2 font-mono">
          <Layers className="h-4.5 w-4.5" /> PIPELINE RUN HISTORY
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs border-collapse">
            <thead className="bg-surface-2 text-muted border-b border-border">
              <tr>
                <th className="p-3">Requested</th>
                <th className="p-3">Status</th>
                <th className="p-3">Processed</th>
                <th className="p-3">Created</th>
                <th className="p-3">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60 text-ink/80">
              {runs.length === 0 && (
                <tr><td colSpan={5} className="p-4 text-center text-muted">No pipeline runs recorded yet.</td></tr>
              )}
              {runs.slice(0, 15).map(run => (
                <tr key={run.id} className="hover:bg-surface-2/30">
                  <td className="p-3">{run.limit_requested}</td>
                  <td className="p-3"><Badge tone={RUN_STATUS_TONE[run.status] ?? "neutral"}>{run.status}</Badge></td>
                  <td className="p-3">{run.targets_processed ?? "--"}</td>
                  <td className="p-3">{formatTime(run.created_at)}</td>
                  <td className="p-3">{run.duration_seconds != null ? `${run.duration_seconds.toFixed(1)}s` : "--"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex gap-3 border-t border-border pt-4 text-muted text-2xs">
          <Pause className="h-3.5 w-3.5" />
          Scheduled/paused ingestion controls are not built yet -- runs are currently manual-trigger only.
        </div>
      </div>
    </div>
  );
}
