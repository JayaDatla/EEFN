"use client";

import { useState } from "react";
import Link from "next/link";
import { Upload, Download, ListChecks } from "lucide-react";
import { SectionHeading } from "../components/ScientificUI";
import { Callout } from "../components/ui/Callout";
import { Badge, healthGradeTone } from "../components/ui/Badge";
import { apiUrl } from "@/lib/api";

interface BatchResultItem {
  toi_id: number;
  found: boolean;
  pl_name?: string;
  disposition?: string;
  health_score?: number;
  health_grade?: string;
  evidence_consistency_score?: number;
  followup_priority_score?: number;
  model_tier?: number;
  catalogs_available_count?: number;
}

interface BatchResponse {
  requested_count: number;
  found_count: number;
  not_found: number[];
  results: BatchResultItem[];
}

function parseToiIds(raw: string): number[] {
  // Accepts one ID per line, comma-separated, or a CSV with a toi_id/TOI column
  // (the header row and any non-numeric-looking first token are skipped).
  const tokens = raw.split(/[\n,]+/).map(t => t.trim()).filter(Boolean);
  const ids: number[] = [];
  for (const tok of tokens) {
    const cleaned = tok.replace(/^TOI-?/i, "").split(/\s+/)[0];
    const n = parseFloat(cleaned);
    if (!Number.isNaN(n)) ids.push(n);
  }
  return Array.from(new Set(ids));
}

export default function BatchWorkflowPage() {
  const [input, setInput] = useState("1017.01\n1020.01\n1025.01");
  const [result, setResult] = useState<BatchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toiIds = parseToiIds(input);

  const runBatch = async () => {
    if (toiIds.length === 0) {
      setError("No valid TOI IDs found in the input.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(apiUrl("/api/v1/batch/audit"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ toi_ids: toiIds }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Backend returned ${res.status}`);
      }
      setResult(await res.json());
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : "Unable to reach the EEFN backend.");
    } finally {
      setLoading(false);
    }
  };

  const exportVotable = async () => {
    if (!result) return;
    const found = result.results.filter(r => r.found).map(r => r.toi_id);
    if (found.length === 0) return;
    const res = await fetch(apiUrl("/api/v1/batch/export"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ toi_ids: found }),
    });
    if (!res.ok) {
      setError(`Export failed: backend returned ${res.status}`);
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "eefn_batch_audit.vot";
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportCsv = () => {
    if (!result) return;
    const header = "toi_id,found,pl_name,disposition,health_score,health_grade,evidence_consistency_score,followup_priority_score,model_tier,catalogs_available_count";
    const rows = result.results.map(r =>
      [r.toi_id, r.found, r.pl_name ?? "", r.disposition ?? "", r.health_score ?? "", r.health_grade ?? "",
       r.evidence_consistency_score ?? "", r.followup_priority_score ?? "", r.model_tier ?? "", r.catalogs_available_count ?? ""].join(",")
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "eefn_batch_audit.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="animate-fadeIn">
      <SectionHeading
        eyebrow="BATCH WORKFLOW"
        title="Upload a target list, get a ranked audit"
        description="Paste TOI IDs (one per line, comma-separated, or a CSV with a toi_id column) to get a real, ranked audit across all of them at once -- matches how observers actually triage a night's target list."
      />

      <div className="surface-card p-5 flex flex-col gap-4">
        <label className="text-xs font-semibold text-ink flex items-center gap-2">
          <Upload size={14} /> Target list
        </label>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          rows={6}
          className="w-full rounded-lg border border-border bg-surface-2 p-3 font-mono text-xs text-ink outline-none focus:border-accent/50"
          placeholder="1017.01&#10;1020.01&#10;TOI-1025.01"
        />
        <div className="flex items-center gap-3">
          <button
            onClick={runBatch}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-accent/25 bg-accent/10 px-4 py-2 text-xs font-bold text-accent cursor-pointer disabled:opacity-50"
          >
            <ListChecks size={14} className={loading ? "animate-pulse" : ""} />
            {loading ? "Auditing..." : `Audit ${toiIds.length} target${toiIds.length === 1 ? "" : "s"}`}
          </button>
          {result && (
            <>
              <button onClick={exportCsv} className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-ink cursor-pointer">
                <Download size={12} /> Export CSV
              </button>
              <button onClick={exportVotable} className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-ink cursor-pointer">
                <Download size={12} /> Export VOTable
              </button>
            </>
          )}
        </div>
      </div>

      {error && <div className="mt-4"><Callout tone="critical" title="Batch audit failed">{error}</Callout></div>}

      {result && (
        <div className="surface-card mt-4 overflow-hidden">
          <div className="flex items-center justify-between border-b border-border p-4 text-xs">
            <span className="text-ink font-semibold">
              {result.found_count} of {result.requested_count} matched real candidates
            </span>
            {result.not_found.length > 0 && (
              <span className="text-severity-high">
                Not found: {result.not_found.map(id => `TOI-${id}`).join(", ")}
              </span>
            )}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-2 text-2xs uppercase tracking-wider text-muted border-b border-border">
                <tr>
                  <th className="px-4 py-2">Candidate</th>
                  <th className="px-4 py-2">Disposition</th>
                  <th className="px-4 py-2">Health</th>
                  <th className="px-4 py-2">Evidence confidence</th>
                  <th className="px-4 py-2">Follow-up priority</th>
                  <th className="px-4 py-2">Tier / coverage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {result.results.map(r => (
                  <tr key={r.toi_id} className={!r.found ? "opacity-50" : "hover:bg-accent/5"}>
                    <td className="px-4 py-3">
                      {r.found ? (
                        <Link href={`/candidates/${r.toi_id}`} className="font-semibold text-ink hover:text-accent">
                          {r.pl_name}
                        </Link>
                      ) : (
                        <span className="text-muted">TOI-{r.toi_id} (not found)</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-ink/80">{r.disposition ?? "--"}</td>
                    <td className="px-4 py-3">{r.health_grade ? <Badge tone={healthGradeTone(r.health_grade)}>{r.health_grade}</Badge> : "--"}</td>
                    <td className="px-4 py-3">{r.evidence_consistency_score != null ? `${(r.evidence_consistency_score * 100).toFixed(0)}%` : "--"}</td>
                    <td className="px-4 py-3">{r.followup_priority_score != null ? `${(r.followup_priority_score * 100).toFixed(0)}%` : "--"}</td>
                    <td className="px-4 py-3 text-muted">{r.model_tier != null ? `Tier ${r.model_tier} (${r.catalogs_available_count}/7)` : "--"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
