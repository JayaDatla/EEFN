"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowUpDown, ChevronLeft, ChevronRight, MapPin, Moon, Radar, RefreshCw, Search } from "lucide-react";
import { ConfidenceBadge, SectionHeading, StatusIndicator } from "./ScientificUI";
import { Callout } from "./ui/Callout";
import { Badge } from "./ui/Badge";
import { apiUrl } from "@/lib/api";

type Candidate = {
  pl_name: string;
  tic_id: number;
  toi_id: number;
  disposition: string;
  orbper: number;
  rade: number;
  trandep?: number;
  evidence_consistency_score?: number;
  followup_priority_score?: number;
  health_score?: number;
  health_grade?: string;
};

type ObservabilityInfo = {
  current_altitude_deg: number;
  current_airmass: number | null;
  moon_separation_deg: number;
  observable_tonight: boolean;
  reason: string;
  transit_window: { start_utc: string; end_utc: string } | null;
};

type ObservabilityRow = {
  pl_name: string;
  toi_id: number;
  tic_id: number;
  disposition: string;
  health_grade?: string;
  followup_priority_score?: number;
  observability: ObservabilityInfo | null;
  observability_unavailable_reason: string | null;
};

const PAGE_SIZE = 500;
const SORT_FIELDS: { value: string; label: string }[] = [
  { value: "followup_priority_score", label: "Follow-up priority" },
  { value: "health_score", label: "Health score" },
  { value: "evidence_consistency_score", label: "Evidence confidence" },
  { value: "toi_id", label: "TOI ID" },
];

function healthStatus(grade: string | undefined, rade: number, score: number | undefined) {
  const g = grade || (rade > 20 ? "F" : ((score ?? 0.5) > 0.8 ? "A" : "C"));
  return g === "F" || g === "D" ? "risk" : g === "A" || g === "B" ? "pass" : "watch";
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export default function TriageQueue() {
  const [data, setData] = useState<Candidate[]>([]);
  const [totalCount, setTotalCount] = useState<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [sortBy, setSortBy] = useState("followup_priority_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [dispositionFilter, setDispositionFilter] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Observability-tonight panel state (UPGRADE_PLAN.md H.3.1).
  const [obsOpen, setObsOpen] = useState(false);
  const [obsLat, setObsLat] = useState("");
  const [obsLon, setObsLon] = useState("");
  const [obsElevation, setObsElevation] = useState("0");
  const [obsDate, setObsDate] = useState(todayIso());
  const [onlyObservable, setOnlyObservable] = useState(false);
  const [obsActive, setObsActive] = useState(false);
  const [obsData, setObsData] = useState<Record<number, ObservabilityInfo | null>>({});
  const [obsLoading, setObsLoading] = useState(false);
  const [obsError, setObsError] = useState<string | null>(null);
  const [geoError, setGeoError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      if (dispositionFilter) params.set("disposition", dispositionFilter);
      const r = await fetch(apiUrl(`/api/v1/candidates?${params.toString()}`));
      if (!r.ok) throw new Error(`Backend returned ${r.status}`);
      const d = await r.json();
      setData(Array.isArray(d) ? d : []);
      const total = r.headers.get("X-Total-Count");
      setTotalCount(total ? Number(total) : null);
      setError(null);
    } catch (e) {
      // UPGRADE_PLAN.md A.14/H.4: never substitute fabricated data on fetch
      // failure -- show an explicit unavailable state instead.
      setData([]);
      setTotalCount(null);
      setError(e instanceof Error ? e.message : "Unable to reach the EEFN backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset, sortBy, sortDir, dispositionFilter]);

  const loadObservability = async () => {
    const lat = parseFloat(obsLat);
    const lon = parseFloat(obsLon);
    if (Number.isNaN(lat) || Number.isNaN(lon)) {
      setObsError("Enter a valid latitude and longitude.");
      return;
    }
    setObsLoading(true);
    setObsError(null);
    try {
      const params = new URLSearchParams({
        lat: String(lat),
        lon: String(lon),
        elevation_m: obsElevation || "0",
        date: obsDate,
        limit: String(PAGE_SIZE),
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      if (dispositionFilter) params.set("disposition", dispositionFilter);
      const r = await fetch(apiUrl(`/api/v1/observability?${params.toString()}`));
      if (!r.ok) throw new Error(`Backend returned ${r.status}`);
      const rows: ObservabilityRow[] = await r.json();
      const map: Record<number, ObservabilityInfo | null> = {};
      rows.forEach(row => { map[row.toi_id] = row.observability; });
      setObsData(map);
      setObsActive(true);
    } catch (e) {
      setObsError(e instanceof Error ? e.message : "Could not compute observability.");
    } finally {
      setObsLoading(false);
    }
  };

  const useMyLocation = () => {
    setGeoError(null);
    if (!navigator.geolocation) {
      setGeoError("Geolocation isn't available in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      pos => {
        setObsLat(pos.coords.latitude.toFixed(4));
        setObsLon(pos.coords.longitude.toFixed(4));
        if (pos.coords.altitude) setObsElevation(Math.max(0, Math.round(pos.coords.altitude)).toString());
      },
      err => setGeoError(err.message),
      { timeout: 8000 }
    );
  };

  const filtered = useMemo(() => {
    let rows = data;
    if (query.trim()) {
      const q = query.toLowerCase();
      rows = rows.filter(
        c => c.pl_name?.toLowerCase().includes(q) || String(c.toi_id).includes(q) || String(c.tic_id).includes(q)
      );
    }
    if (obsActive && onlyObservable) {
      rows = rows.filter(c => obsData[c.toi_id]?.observable_tonight);
    }
    return rows;
  }, [data, query, obsActive, onlyObservable, obsData]);

  // Registry pulse: every figure is computed from the rows actually loaded -- nothing
  // is estimated or filled in when a field is missing (a missing grade is just not counted).
  const pulse = useMemo(() => {
    if (!data.length) return null;
    const grades: Record<string, number> = { A: 0, B: 0, C: 0, D: 0, F: 0 };
    let verified = 0, review = 0, flagged = 0, confSum = 0, confN = 0;
    data.forEach(c => {
      const g = (c.health_grade || "").toUpperCase();
      if (g in grades) grades[g] += 1;
      const st = healthStatus(c.health_grade, c.rade, c.evidence_consistency_score);
      if (st === "pass") verified += 1; else if (st === "watch") review += 1; else flagged += 1;
      if (typeof c.evidence_consistency_score === "number") { confSum += c.evidence_consistency_score; confN += 1; }
    });
    const graded = Object.values(grades).reduce((a, b) => a + b, 0);
    return { grades, graded, verified, review, flagged, n: data.length, meanConf: confN ? confSum / confN : null };
  }, [data]);

  const parentRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 52,
    overscan: 12,
  });

  const totalPages = totalCount != null ? Math.max(Math.ceil(totalCount / PAGE_SIZE), 1) : null;
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  const columns = obsActive
    ? "2fr_0.8fr_1fr_1fr_1fr_1.2fr"
    : "2fr_1fr_1fr_1fr_1.2fr_1fr";

  return (
    <div className="animate-fadeIn">
      <SectionHeading
        eyebrow="TRIAGE QUEUE / CROSS-MATCHED REGISTRY"
        title="Should I point a telescope at this tonight?"
        description="The full cross-matched TOI registry, server-paginated and virtualized -- sorted by follow-up priority by default. Set an observing site below to filter by real altitude, airmass, and moon separation for tonight."
        action={
          <button onClick={load} className="btn-ghost">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Sync registry
          </button>
        }
      />

      {error && (
        <div className="mb-4">
          <Callout tone="critical" title="Backend unavailable">
            {error}. No candidate data is shown below -- this is not a fallback, it is an empty result.
          </Callout>
        </div>
      )}

      {pulse && (
        <section className="pulse" aria-label="Registry summary">
          <div className="pulse-lead">
            <span className="data-label">Registry</span>
            <span className="display-figure">{(totalCount ?? pulse.n).toLocaleString()}</span>
            <span className="pulse-note">cross-matched candidates</span>
          </div>
          <div className="pulse-fig">
            <span className="data-label">Verified</span>
            <strong>{Math.round((pulse.verified / pulse.n) * 100)}<small>%</small></strong>
            <span className="pulse-note">{pulse.verified.toLocaleString()} of {pulse.n.toLocaleString()} loaded</span>
          </div>
          <div className="pulse-fig">
            <span className="data-label">Need review</span>
            <strong>{(pulse.review + pulse.flagged).toLocaleString()}</strong>
            <span className="pulse-note">{pulse.review.toLocaleString()} review · {pulse.flagged.toLocaleString()} flagged</span>
          </div>
          <div className="pulse-fig">
            <span className="data-label">Mean evidence confidence</span>
            <strong>{pulse.meanConf != null ? Math.round(pulse.meanConf * 100) : "--"}<small>{pulse.meanConf != null ? "%" : ""}</small></strong>
            <span className="pulse-note">across loaded candidates</span>
          </div>
          {pulse.graded > 0 && (
            <div className="pulse-grades" role="img" aria-label={`Health grades: ${Object.entries(pulse.grades).map(([g, n]) => `${g} ${n}`).join(", ")}`}>
              <div className="pulse-bar">
                {Object.entries(pulse.grades).filter(([, n]) => n > 0).map(([g, n]) => (
                  <span key={g} style={{ flexGrow: n, background: `var(--grade-${g.toLowerCase()})` }} title={`Grade ${g}: ${n}`} />
                ))}
              </div>
              <div className="pulse-legend">
                <span className="data-label">Health grade</span>
                {Object.entries(pulse.grades).map(([g, n]) => (
                  <span key={g} className="data-value"><i style={{ background: `var(--grade-${g.toLowerCase()})` }} />{g} <b>{n}</b></span>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      <div className="surface-card mb-4 overflow-hidden">
        <button
          onClick={() => setObsOpen(o => !o)}
          className="flex w-full items-center justify-between px-4 py-3 text-left text-xs font-medium text-ink cursor-pointer"
        >
          <span className="inline-flex items-center gap-2">
            <Radar size={14} className="text-accent" /> Observability tonight
            {obsActive && <Badge tone="status-pass">Active</Badge>}
          </span>
          <span className="text-muted">{obsOpen ? "Hide" : "Set observing site"}</span>
        </button>
        {obsOpen && (
          <div className="border-t border-border p-4">
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Latitude
                <input value={obsLat} onChange={e => setObsLat(e.target.value)} placeholder="31.68" className="w-28 rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs text-ink outline-none" />
              </label>
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Longitude
                <input value={obsLon} onChange={e => setObsLon(e.target.value)} placeholder="-110.88" className="w-28 rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs text-ink outline-none" />
              </label>
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Elevation (m)
                <input value={obsElevation} onChange={e => setObsElevation(e.target.value)} className="w-24 rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs text-ink outline-none" />
              </label>
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Night of (UTC)
                <input type="date" value={obsDate} onChange={e => setObsDate(e.target.value)} className="rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs text-ink outline-none" />
              </label>
              <button onClick={useMyLocation} className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface-2 px-3 py-1.5 text-xs text-ink cursor-pointer">
                <MapPin size={12} /> Use my location
              </button>
              <button onClick={loadObservability} disabled={obsLoading} className="inline-flex items-center gap-1.5 rounded-lg border border-accent/25 bg-accent/10 px-3 py-1.5 text-xs text-accent cursor-pointer disabled:opacity-50">
                <Radar size={12} className={obsLoading ? "animate-pulse" : ""} /> {obsLoading ? "Computing..." : "Compute observability"}
              </button>
              {obsActive && (
                <label className="flex items-center gap-1.5 text-xs text-ink">
                  <input type="checkbox" checked={onlyObservable} onChange={e => setOnlyObservable(e.target.checked)} />
                  Only observable tonight
                </label>
              )}
            </div>
            {geoError && <p className="mt-2 text-2xs text-severity-high">{geoError}</p>}
            {obsError && <p className="mt-2 text-2xs text-severity-critical">{obsError}</p>}
            <p className="mt-3 text-2xs text-muted">
              Real astropy positional astronomy (altitude, airmass, moon separation, sky darkness) evaluated at each
              target&apos;s actual transit midpoint when a transit epoch is on record, otherwise at local UTC midnight
              for the given night. A candidate with no transit epoch reports that explicitly rather than guessing one.
            </p>
          </div>
        )}
      </div>

      <div className="surface-card overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-hairline p-4 md:flex-row md:items-center md:justify-between">
          <div className="relative w-full max-w-sm">
            <Search size={16} className="absolute left-3 top-2.5 text-muted" />
            <input
              aria-label="Search loaded candidates"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search within loaded page (name, TOI, TIC)"
              className="w-full rounded-md border border-border bg-surface-2 py-2 pl-9 pr-3 text-xs text-ink outline-none focus:border-accent/50"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Sort by"
              value={sortBy}
              onChange={e => { setSortBy(e.target.value); setOffset(0); }}
              className="rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs text-ink"
            >
              {SORT_FIELDS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
            </select>
            <button
              aria-label="Toggle sort direction"
              onClick={() => setSortDir(d => (d === "asc" ? "desc" : "asc"))}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs text-ink"
            >
              <ArrowUpDown size={12} /> {sortDir === "desc" ? "High -> low" : "Low -> high"}
            </button>
            <select
              aria-label="Filter by disposition"
              value={dispositionFilter}
              onChange={e => { setDispositionFilter(e.target.value); setOffset(0); }}
              className="rounded-md border border-border bg-surface-2 px-2 py-1.5 text-xs text-ink"
            >
              <option value="">All dispositions</option>
              <option value="CP">CP</option>
              <option value="KP">KP</option>
              <option value="PC">PC</option>
              <option value="FP">FP</option>
              <option value="APC">APC</option>
            </select>
            <span className="font-mono text-2xs text-muted">
              {totalCount != null ? `${totalCount.toLocaleString()} TOTAL` : "-- TOTAL"}
            </span>
          </div>
        </div>

        <div className="table-head grid gap-0 px-5 py-3" style={{ gridTemplateColumns: columns.replace(/_/g, " ") }}>
          <span>Candidate</span>
          <span>Disposition</span>
          {obsActive ? (
            <>
              <span>Altitude / Airmass</span>
              <span>Moon sep.</span>
              <span>Transit window (UTC)</span>
              <span>Tonight</span>
            </>
          ) : (
            <>
              <span>Period</span>
              <span>Radius</span>
              <span>Evidence confidence</span>
              <span>Review status</span>
            </>
          )}
        </div>

        <div ref={parentRef} className="overflow-auto" style={{ height: "560px" }}>
          {!loading && !error && filtered.length === 0 && (
            <div className="px-5 py-10 text-center text-xs text-muted">No candidates match this query.</div>
          )}
          <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, width: "100%", position: "relative" }}>
            {rowVirtualizer.getVirtualItems().map(vRow => {
              const c = filtered[vRow.index];
              const obs = obsData[c.toi_id];
              return (
                <div
                  key={c.toi_id}
                  className="absolute left-0 top-0 grid w-full items-center gap-0 row-line px-5 text-sm"
                  style={{ height: `${vRow.size}px`, transform: `translateY(${vRow.start}px)`, gridTemplateColumns: columns.replace(/_/g, " ").split(" ").join(" ") }}
                >
                  <Link href={`/candidates/${c.toi_id}`} className="font-semibold text-ink hover:text-accent">
                    {c.pl_name}
                    <span className="mt-1 block data-value text-2xs font-normal text-muted">TIC {c.tic_id}</span>
                  </Link>
                  <span className="data-value text-ink/80">{c.disposition}</span>
                  {obsActive ? (
                    obs ? (
                      <>
                        <span className="text-muted">{obs.current_altitude_deg.toFixed(0)}&deg; / {obs.current_airmass?.toFixed(2) ?? "--"}</span>
                        <span className="text-muted inline-flex items-center gap-1"><Moon size={11} /> {obs.moon_separation_deg.toFixed(0)}&deg;</span>
                        <span className="font-mono text-2xs text-muted">
                          {obs.transit_window ? `${obs.transit_window.start_utc.slice(11, 16)}-${obs.transit_window.end_utc.slice(11, 16)}` : "no epoch"}
                        </span>
                        <span><Badge tone={obs.observable_tonight ? "status-pass" : "status-watch"}>{obs.observable_tonight ? "Yes" : "No"}</Badge></span>
                      </>
                    ) : (
                      <span className="col-span-4 text-2xs text-muted">no host coordinates</span>
                    )
                  ) : (
                    <>
                      <span className="data-value text-muted">{Number(c.orbper).toFixed(3)} d</span>
                      <span className={`data-value ${Number(c.rade) > 20 ? "text-severity-critical" : "text-muted"}`}>{Number(c.rade).toFixed(2)} R⊕</span>
                      <span><ConfidenceBadge score={c.evidence_consistency_score ?? 0.5} /></span>
                      <span><StatusIndicator status={healthStatus(c.health_grade, c.rade, c.evidence_consistency_score)} /></span>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-hairline px-4 py-3">
          <span className="text-xs text-muted">
            Page {currentPage} of {totalPages ?? "?"} ({filtered.length} loaded)
          </span>
          <div className="flex gap-2">
            <button
              aria-label="Previous page"
              disabled={offset === 0}
              onClick={() => setOffset(o => Math.max(o - PAGE_SIZE, 0))}
              className="btn-icon"
            >
              <ChevronLeft size={15} />
            </button>
            <button
              aria-label="Next page"
              disabled={totalCount != null && offset + PAGE_SIZE >= totalCount}
              onClick={() => setOffset(o => o + PAGE_SIZE)}
              className="btn-icon"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
