"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { GitCompare, RefreshCw } from "lucide-react";
import { SectionHeading } from "../components/ScientificUI";
import { Callout } from "../components/ui/Callout";
import { apiUrl } from "@/lib/api";

interface ChangeEvent {
  toi_id: number | null;
  pl_name: string;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_at: string;
}

const LAST_VISIT_KEY = "eefn-changes-last-visit";

export default function ChangesPage() {
  const [events, setEvents] = useState<ChangeEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [since, setSince] = useState<string | null>(null);

  const load = async (sinceIso: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (sinceIso) params.set("since", sinceIso);
      const res = await fetch(apiUrl(`/api/v1/changes?${params.toString()}`));
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      setEvents(await res.json());
    } catch (e) {
      setEvents([]);
      setError(e instanceof Error ? e.message : "Unable to reach the EEFN backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const stored = window.localStorage.getItem(LAST_VISIT_KEY);
    setSince(stored);
    load(stored);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const markSeen = () => {
    const now = new Date().toISOString();
    window.localStorage.setItem(LAST_VISIT_KEY, now);
    setSince(now);
  };

  return (
    <div className="animate-fadeIn">
      <SectionHeading
        eyebrow="DIFF VIEW"
        title="What changed since your last visit"
        description={since
          ? `Real disposition/health-grade transitions recorded since ${new Date(since).toLocaleString()}.`
          : "Real disposition/health-grade transitions ever recorded (no prior visit on this browser) -- a real, timestamped ledger, never inferred after the fact."}
        action={
          <div className="flex gap-2">
            <button onClick={() => load(since)} className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-ink cursor-pointer">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
            </button>
            <button onClick={markSeen} className="inline-flex items-center gap-2 rounded-lg border border-accent/25 bg-accent/10 px-3 py-2 text-xs text-accent cursor-pointer">
              <GitCompare size={14} /> Mark all seen (reset baseline to now)
            </button>
          </div>
        }
      />

      {error && <Callout tone="critical" title="Backend unavailable">{error}. No change data is shown.</Callout>}

      <div className="surface-card overflow-hidden">
        {!loading && !error && events.length === 0 && (
          <div className="px-5 py-10 text-center text-xs text-muted">
            No real disposition or health-grade changes have been recorded {since ? "since your last visit" : "yet"}.
            This is the honest current state -- not every sync produces a change.
          </div>
        )}
        {events.length > 0 && (
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-2 text-2xs uppercase tracking-wider text-muted border-b border-border">
              <tr>
                <th className="px-5 py-3">Candidate</th>
                <th className="px-5 py-3">Field</th>
                <th className="px-5 py-3">Change</th>
                <th className="px-5 py-3">When</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {events.map((e, idx) => (
                <tr key={idx} className="hover:bg-accent/5">
                  <td className="px-5 py-3">
                    {e.toi_id != null ? (
                      <Link href={`/candidates/${e.toi_id}`} className="font-semibold text-ink hover:text-accent">{e.pl_name}</Link>
                    ) : (
                      <span className="text-ink">{e.pl_name}</span>
                    )}
                  </td>
                  <td className="px-5 py-3 font-mono text-muted">{e.field_name}</td>
                  <td className="px-5 py-3 font-mono">
                    <span className="text-severity-critical">{e.old_value ?? "--"}</span>
                    <span className="text-muted mx-2">&rarr;</span>
                    <span className="text-status-pass">{e.new_value ?? "--"}</span>
                  </td>
                  <td className="px-5 py-3 text-muted">{new Date(e.changed_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
