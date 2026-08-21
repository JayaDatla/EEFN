"use client";

import React, { useState, useEffect } from 'react';
import { BarChart3, Scale } from 'lucide-react';
import { apiUrl } from '@/lib/api';
import { Callout } from '../components/ui/Callout';

interface Candidate {
  pl_name: string;
  tic_id: number;
  toi_id: number;
}

interface Profile {
  planet: { pl_name: string; toi_id: number };
  measurement_history: {
    stellar_radius: Record<string, number | null>;
    distance: Record<string, number | null>;
  };
  agreement_metrics: {
    rad_disagreement: number | null;
    dist_disagreement: number | null;
    teff_disagreement: number | null;
  };
}

// Real alert thresholds from services/alert_engine.py -- the same numbers that
// actually gate an alert on the backend, not invented display-only cutoffs.
const RAD_THRESHOLD = 0.25; // R_sun
const DIST_THRESHOLD = 100; // pc
const TEFF_THRESHOLD = 500; // K

function severityFor(diff: number | null, threshold: number): "critical" | "warning" | "low" | "no-data" {
  if (diff == null) return "no-data";
  if (diff > threshold * 2) return "critical";
  if (diff > threshold) return "warning";
  return "low";
}

export default function FusionDashboard() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAndFuse();
  }, []);

  const fetchAndFuse = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(apiUrl('/api/v1/candidates?limit=15'));
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      const list: Candidate[] = await res.json();

      // UPGRADE_PLAN.md A.14/H.3: this page used to fabricate every disagreement
      // number shown here -- a hardcoded lookup table for 3 TOIs plus a formula
      // ("mockToi", "mockGaia") that invented plausible-looking numbers for every
      // other real candidate, and three "consensus %" dials (94.7%, 89.2%, 96.1%)
      // that were never computed from anything. A real, serious integrity bug for
      // the page whose entire purpose is showing catalog-disagreement evidence.
      // Fixed: fetch each candidate's real agreement_metrics/measurement_history.
      const profileResults = await Promise.all(
        list.slice(0, 15).map(async c => {
          const r = await fetch(apiUrl(`/api/v1/candidates/${c.toi_id}`));
          if (!r.ok) return null;
          return (await r.json()) as Profile;
        })
      );
      setProfiles(profileResults.filter((p): p is Profile => p !== null));
    } catch (e) {
      setProfiles([]);
      setError(e instanceof Error ? e.message : "Unable to reach the EEFN backend.");
    } finally {
      setIsLoading(false);
    }
  };

  // A candidate with no Gaia match at all has a null disagreement, not a 0.0 one --
  // it must be excluded from both the numerator and denominator here, or "no data"
  // silently counts as "perfect agreement" (the exact bug this page used to have,
  // see ingest.py's diff() helper for the backend half of this fix).
  const withRad = profiles.filter(p => p.agreement_metrics.rad_disagreement != null);
  const withTeff = profiles.filter(p => p.agreement_metrics.teff_disagreement != null);
  const withDist = profiles.filter(p => p.agreement_metrics.dist_disagreement != null);

  const radConsensus = withRad.length
    ? withRad.filter(p => (p.agreement_metrics.rad_disagreement as number) <= RAD_THRESHOLD).length / withRad.length
    : null;
  const teffConsensus = withTeff.length
    ? withTeff.filter(p => (p.agreement_metrics.teff_disagreement as number) <= TEFF_THRESHOLD).length / withTeff.length
    : null;
  const distConsensus = withDist.length
    ? withDist.filter(p => (p.agreement_metrics.dist_disagreement as number) <= DIST_THRESHOLD).length / withDist.length
    : null;

  const ConsensusDial = ({ label, value, measuredCount, detail }: { label: string; value: number | null; measuredCount: number; detail: string }) => (
    <div className="bg-surface-2/60 border border-border p-4 rounded-xl flex flex-col items-center gap-3">
      <span className="text-[10px] font-mono font-bold text-muted uppercase tracking-wider">{label}</span>
      <div className="relative w-28 h-28 flex items-center justify-center">
        <svg className="w-full h-full transform -rotate-90">
          <circle cx="56" cy="56" r="45" stroke="var(--color-border)" strokeWidth="6" fill="transparent" />
          {value != null && (
            <circle cx="56" cy="56" r="45" stroke="var(--status-pass)" strokeWidth="6" fill="transparent"
              strokeDasharray={2 * Math.PI * 45}
              strokeDashoffset={2 * Math.PI * 45 * (1 - value)}
              strokeLinecap="round"
            />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center font-mono">
          <span className="text-xl font-extrabold text-ink">{value != null ? `${(value * 100).toFixed(0)}%` : "--"}</span>
          <span className="text-[8px] text-muted uppercase text-center leading-tight">of {measuredCount} with<br/>a Gaia match</span>
        </div>
      </div>
      <p className="text-[10px] text-muted font-sans text-center">{detail}</p>
    </div>
  );

  return (
    <div className="flex-1 flex flex-col gap-6 max-w-7xl mx-auto w-full py-4 animate-fadeIn">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-border pb-5">
        <div>
          <h2 className="text-3xl font-extrabold text-ink tracking-tight font-sans">
            Catalog Metric Fusion Workspace
          </h2>
          <p className="text-sm text-muted mt-1">
            Real parameter alignment between Gaia DR3 and the TOI catalog, for the {profiles.length || "--"} candidates currently loaded.
          </p>
        </div>
      </div>

      {error && <Callout tone="critical" title="Backend unavailable">{error}. No fusion data is shown -- this is not a fallback, it is an empty result.</Callout>}

      <div className="surface-card p-5 flex flex-col gap-4">
        <h3 className="font-bold text-sm text-accent border-b border-border pb-2.5 flex items-center gap-2 font-mono">
          <BarChart3 className="h-4.5 w-4.5" /> CATALOG CONSENSUS (this page's loaded sample, not the full registry)
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <ConsensusDial label="Radius Consensus" value={radConsensus} measuredCount={withRad.length} detail={`Stellar radii agreeing within ${RAD_THRESHOLD} R_sun (the real alert threshold). Candidates with no Gaia match are excluded, not counted as agreeing.`} />
          <ConsensusDial label="Effective Temp Consensus" value={teffConsensus} measuredCount={withTeff.length} detail={`Agreeing within ${TEFF_THRESHOLD} K (the real alert threshold). Candidates with no Gaia match are excluded, not counted as agreeing.`} />
          <ConsensusDial label="Distance Consensus" value={distConsensus} measuredCount={withDist.length} detail={`Agreeing within ${DIST_THRESHOLD} pc (the real alert threshold). Candidates with no Gaia match are excluded, not counted as agreeing.`} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="surface-card p-5 flex flex-col gap-4">
          <h3 className="font-bold text-sm text-accent border-b border-border pb-2.5 flex items-center gap-2 font-mono">
            <Scale className="h-4 w-4" /> STELLAR RADIUS CROSS-CHECK (R_sun)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead className="bg-surface-2 text-muted border-b border-border">
                <tr>
                  <th className="p-3">Target ID</th>
                  <th className="p-3 text-right">TOI Catalog</th>
                  <th className="p-3 text-right">Gaia DR3</th>
                  <th className="p-3 text-center">Severity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 text-ink/80">
                {isLoading ? (
                  <tr><td colSpan={4} className="p-4 text-center text-muted">Querying database...</td></tr>
                ) : profiles.length === 0 ? (
                  <tr><td colSpan={4} className="p-4 text-center text-muted">No data.</td></tr>
                ) : (
                  profiles.map((p) => {
                    const toi = p.measurement_history.stellar_radius["TOI Catalog"];
                    const gaia = p.measurement_history.stellar_radius["Gaia DR3"];
                    const sev = severityFor(p.agreement_metrics.rad_disagreement, RAD_THRESHOLD);
                    return (
                      <tr key={p.planet.toi_id} className="hover:bg-surface-2/40 transition-all">
                        <td className="p-3 text-ink font-bold">{p.planet.pl_name}</td>
                        <td className="p-3 text-right text-muted">{toi != null ? toi.toFixed(3) : "N/A"}</td>
                        <td className="p-3 text-right text-ink/90 font-semibold">{gaia != null ? gaia.toFixed(3) : "N/A"}</td>
                        <td className="p-3 text-center">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            sev === 'critical' ? 'bg-severity-critical/10 text-severity-critical border border-severity-critical/20' :
                            sev === 'warning' ? 'bg-severity-high/10 text-severity-high border border-severity-high/20' :
                            sev === 'no-data' ? 'bg-surface-2 text-muted border border-border' :
                            'bg-status-pass/10 text-status-pass border border-status-pass/20'
                          }`}>
                            {sev === 'no-data' ? 'NO GAIA MATCH' : `${sev.toUpperCase()} (${p.agreement_metrics.rad_disagreement!.toFixed(3)})`}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="surface-card p-5 flex flex-col gap-4">
          <h3 className="font-bold text-sm text-accent border-b border-border pb-2.5 flex items-center gap-2 font-mono">
            <Scale className="h-4 w-4" /> STELLAR DISTANCE CROSS-CHECK (pc)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead className="bg-surface-2 text-muted border-b border-border">
                <tr>
                  <th className="p-3">Target ID</th>
                  <th className="p-3 text-right">TOI Catalog</th>
                  <th className="p-3 text-right">Gaia DR3</th>
                  <th className="p-3 text-center">Severity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 text-ink/80">
                {isLoading ? (
                  <tr><td colSpan={4} className="p-4 text-center text-muted">Querying database...</td></tr>
                ) : profiles.length === 0 ? (
                  <tr><td colSpan={4} className="p-4 text-center text-muted">No data.</td></tr>
                ) : (
                  profiles.map((p) => {
                    const toi = p.measurement_history.distance["TOI Catalog"];
                    const gaia = p.measurement_history.distance["Gaia DR3"];
                    const sev = severityFor(p.agreement_metrics.dist_disagreement, DIST_THRESHOLD);
                    return (
                      <tr key={p.planet.toi_id} className="hover:bg-surface-2/40 transition-all">
                        <td className="p-3 text-ink font-bold">{p.planet.pl_name}</td>
                        <td className="p-3 text-right text-muted">{toi != null ? toi.toFixed(0) : "N/A"}</td>
                        <td className="p-3 text-right text-ink/90 font-semibold">{gaia != null ? gaia.toFixed(0) : "N/A"}</td>
                        <td className="p-3 text-center">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            sev === 'critical' ? 'bg-severity-critical/10 text-severity-critical border border-severity-critical/20' :
                            sev === 'warning' ? 'bg-severity-high/10 text-severity-high border border-severity-high/20' :
                            sev === 'no-data' ? 'bg-surface-2 text-muted border border-border' :
                            'bg-status-pass/10 text-status-pass border border-status-pass/20'
                          }`}>
                            {sev === 'no-data' ? 'NO GAIA MATCH' : `${sev.toUpperCase()} (${p.agreement_metrics.dist_disagreement!.toFixed(0)} pc)`}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
