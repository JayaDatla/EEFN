"use client";

import React, { useState, useEffect } from 'react';
import { Network, Database, ShieldAlert, Cpu, CheckCircle2, ArrowRight, Activity, Scale, Compass, HelpCircle } from 'lucide-react';
import dynamic from 'next/dynamic';
import { apiUrl } from '@/lib/api';

const GalacticVisualizer = dynamic(() => import('../components/GalacticVisualizer'), {
  ssr: false,
  loading: () => <div className="text-muted font-mono text-xs p-4">Initializing WebGL alignment space...</div>
});

interface Planet {
  pl_name: string;
  tic_id: number;
  toi_id: number;
  disposition: string;
  orbper: number;
  rade: number;
  trandep: number;
  trandurh: number;
  insol: number;
  eqt: number;
}

interface Star {
  hostname: string;
  ra: number;
  dec: number;
  parallax?: number;
  distance?: number;
  teff?: number;
  logg?: number;
  rad?: number;
  mass?: number;
}

interface Metrics {
  teff_disagreement: number;
  rad_disagreement: number;
  dist_disagreement: number;
  ruwe?: number;
  derived_rp_gaia?: number;
  derived_rp_diff: number;
  is_unphysical_rp: boolean;
  completeness_score: number;
  catalog_agreement_score: number;
}

interface CandidateProfile {
  planet: Planet;
  star: Star;
  sources: string[];
  measurement_history: {
    stellar_radius: Record<string, number | null>;
    stellar_teff: Record<string, number | null>;
    distance: Record<string, number | null>;
  };
  agreement_metrics: Metrics;
  prediction: {
    evidence_consistency_score: number;
    followup_priority_score: number;
  };
}

export default function ComparePage() {
  const [candidatesList, setCandidatesList] = useState<any[]>([]);
  const [selectedToiA, setSelectedToiA] = useState<string>('1017.01');
  const [selectedToiB, setSelectedToiB] = useState<string>('1020.01');

  const [profileA, setProfileA] = useState<CandidateProfile | null>(null);
  const [profileB, setProfileB] = useState<CandidateProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchCandidatesList();
  }, []);

  useEffect(() => {
    fetchProfiles();
  }, [selectedToiA, selectedToiB, candidatesList]);

  const [listError, setListError] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);

  const fetchCandidatesList = async () => {
    try {
      const res = await fetch(apiUrl('/api/v1/candidates?limit=100'));
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      setCandidatesList(await res.json());
      setListError(null);
    } catch (e) {
      // UPGRADE_PLAN.md A.14: no more fabricated fallback options/profiles.
      setCandidatesList([]);
      setListError(e instanceof Error ? e.message : "Unable to reach the EEFN backend.");
    }
  };

  const fetchProfiles = async () => {
    setIsLoading(true);
    try {
      const [resA, resB] = await Promise.all([
        fetch(apiUrl(`/api/v1/candidates/${selectedToiA}`)),
        fetch(apiUrl(`/api/v1/candidates/${selectedToiB}`)),
      ]);
      if (!resA.ok || !resB.ok) throw new Error(`Backend returned ${resA.status}/${resB.status}`);
      setProfileA(await resA.json());
      setProfileB(await resB.json());
      setProfileError(null);
    } catch (e) {
      setProfileA(null);
      setProfileB(null);
      setProfileError(e instanceof Error ? e.message : "Unable to reach the EEFN backend.");
    } finally {
      setIsLoading(false);
    }
  };

  if (listError || profileError) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-20 gap-3">
        <p className="text-sm text-severity-critical font-semibold">Could not load comparison data</p>
        <p className="text-xs text-muted">{listError || profileError}. No fallback data is shown.</p>
      </div>
    );
  }

  if (isLoading || !profileA || !profileB) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center font-mono text-muted py-20">
        <Activity className="h-10 w-10 animate-spin text-accent mb-2" />
        <span>Loading compare parameters desk...</span>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col gap-6 max-w-7xl mx-auto w-full py-4 animate-fadeIn font-mono text-xs">
      
      {/* Header & Target Selectors */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-border pb-5">
        <div>
          <h2 className="text-3xl font-display font-medium text-ink tracking-tight flex items-center gap-2">
            <Scale className="h-7 w-7 text-accent" /> Side-by-Side Comparison Workspace
          </h2>
          <p className="text-sm text-muted mt-1">
            Examine and align two candidates simultaneously to identify target blending.
          </p>
        </div>
        
        {/* Selector Inputs */}
        <div className="flex gap-3 bg-surface-2/40 p-3 border border-border rounded-xl">
          <div>
            <label className="block text-[8px] text-muted font-bold uppercase mb-1">Candidate A</label>
            <select
              value={selectedToiA}
              onChange={e => setSelectedToiA(e.target.value)}
              className="bg-surface-2 border border-border rounded px-2 py-1 text-ink text-[11px]"
            >
              {candidatesList.map(c => (
                <option key={c.toi_id} value={c.toi_id.toString()}>TOI-{c.toi_id.toFixed(2)}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center text-muted font-bold text-sm mt-3">VS</div>
          <div>
            <label className="block text-[8px] text-muted font-bold uppercase mb-1">Candidate B</label>
            <select
              value={selectedToiB}
              onChange={e => setSelectedToiB(e.target.value)}
              className="bg-surface-2 border border-border rounded px-2 py-1 text-ink text-[11px]"
            >
              {candidatesList.map(c => (
                <option key={c.toi_id} value={c.toi_id.toString()}>TOI-{c.toi_id.toFixed(2)}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* SECTION A: SUMMARY COMPARISON */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Candidate A Summary */}
        <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
          <span className="text-accent font-bold border-b border-border pb-2 text-sm">CANDIDATE A: {profileA.planet.pl_name}</span>
          <div className="flex flex-col gap-2.5">
            {(() => {
              const isUnphysical = profileA.agreement_metrics.is_unphysical_rp;
              const rawScore = profileA.agreement_metrics.catalog_agreement_score;
              const displayScore = isUnphysical ? Math.min(rawScore, 0.45) : rawScore;
              return (
                <div className="flex justify-between">
                  <span>Health Agreement Score:</span>
                  <span className={`${isUnphysical ? 'text-severity-critical' : 'text-status-pass'} font-bold`}>
                    {(displayScore * 100).toFixed(1)}%
                  </span>
                </div>
              );
            })()}
            <div className="flex justify-between"><span>Derived Planet size:</span><span className={profileA.agreement_metrics.is_unphysical_rp ? 'text-severity-critical font-bold' : 'text-ink/80'}>{profileA.agreement_metrics.derived_rp_gaia != null ? `${profileA.agreement_metrics.derived_rp_gaia.toFixed(2)} R_E` : 'N/A'}</span></div>
            <div className="flex justify-between"><span>Alert Severity:</span><span className={profileA.agreement_metrics.is_unphysical_rp ? 'text-severity-critical font-bold' : 'text-muted'}>{profileA.agreement_metrics.is_unphysical_rp ? 'CRITICAL' : 'NORMAL'}</span></div>
            <div className="flex justify-between"><span>Status:</span><span className="text-ink font-bold">{profileA.planet.disposition}</span></div>
          </div>
        </div>

        {/* Candidate B Summary */}
        <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
          <span className="text-severity-critical font-bold border-b border-border pb-2 text-sm">CANDIDATE B: {profileB.planet.pl_name}</span>
          <div className="flex flex-col gap-2.5">
            {(() => {
              const isUnphysical = profileB.agreement_metrics.is_unphysical_rp;
              const rawScore = profileB.agreement_metrics.catalog_agreement_score;
              const displayScore = isUnphysical ? Math.min(rawScore, 0.45) : rawScore;
              return (
                <div className="flex justify-between">
                  <span>Health Agreement Score:</span>
                  <span className={`${isUnphysical ? 'text-severity-critical' : 'text-status-pass'} font-bold`}>
                    {(displayScore * 100).toFixed(1)}%
                  </span>
                </div>
              );
            })()}
            <div className="flex justify-between"><span>Derived Planet size:</span><span className={profileB.agreement_metrics.is_unphysical_rp ? 'text-severity-critical font-bold' : 'text-ink/80'}>{profileB.agreement_metrics.derived_rp_gaia != null ? `${profileB.agreement_metrics.derived_rp_gaia.toFixed(2)} R_E` : 'N/A'}</span></div>
            <div className="flex justify-between"><span>Alert Severity:</span><span className={profileB.agreement_metrics.is_unphysical_rp ? 'text-severity-critical font-bold' : 'text-muted'}>{profileB.agreement_metrics.is_unphysical_rp ? 'CRITICAL' : 'NORMAL'}</span></div>
            <div className="flex justify-between"><span>Status:</span><span className="text-ink font-bold">{profileB.planet.disposition}</span></div>
          </div>
        </div>

      </div>

      {/* SECTION B: CATALOG AGREEMENT COMPARISON */}
      <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
        <h3 className="font-bold text-xs text-accent border-b border-border pb-2.5 uppercase tracking-wider">
          Catalog Parameter Comparisons
        </h3>
        
        <table className="w-full text-left font-mono">
          <thead className="bg-surface-2 text-muted border-b border-border">
            <tr>
              <th className="p-3">Measurement Metric</th>
              <th className="p-3">{profileA.planet.pl_name} (A)</th>
              <th className="p-3">{profileB.planet.pl_name} (B)</th>
              <th className="p-3 text-right">Delta difference</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-900/60 text-ink/80">
            <tr>
              <td className="p-3 font-bold">{"Effective Temperature ($T_{eff}$)"}</td>
              <td className="p-3">{profileA.star.teff ? `${profileA.star.teff.toFixed(0)} K` : 'N/A'}</td>
              <td className="p-3">{profileB.star.teff ? `${profileB.star.teff.toFixed(0)} K` : 'N/A'}</td>
              <td className="p-3 text-right font-bold text-accent">
                {profileA.star.teff && profileB.star.teff ? `${Math.abs(profileA.star.teff - profileB.star.teff).toFixed(0)} K` : 'N/A'}
              </td>
            </tr>
            <tr>
              <td className="p-3 font-bold">Host Star Radius ($R_\odot$)</td>
              <td className="p-3">{profileA.star.rad ? `${profileA.star.rad.toFixed(3)} R_☉` : 'N/A'}</td>
              <td className="p-3">{profileB.star.rad ? `${profileB.star.rad.toFixed(3)} R_☉` : 'N/A'}</td>
              <td className="p-3 text-right font-bold text-accent">
                {profileA.star.rad && profileB.star.rad ? `${Math.abs(profileA.star.rad - profileB.star.rad).toFixed(3)} R_☉` : 'N/A'}
              </td>
            </tr>
            <tr>
              <td className="p-3 font-bold">Stellar Distance (d)</td>
              <td className="p-3">{profileA.star.distance ? `${profileA.star.distance.toFixed(1)} pc` : 'N/A'}</td>
              <td className="p-3">{profileB.star.distance ? `${profileB.star.distance.toFixed(1)} pc` : 'N/A'}</td>
              <td className="p-3 text-right font-bold text-accent">
                {profileA.star.distance && profileB.star.distance ? `${Math.abs(profileA.star.distance - profileB.star.distance).toFixed(1)} pc` : 'N/A'}
              </td>
            </tr>
            <tr>
              <td className="p-3 font-bold">Gaia RUWE Score</td>
              <td className="p-3">{profileA.agreement_metrics.ruwe ? profileA.agreement_metrics.ruwe.toFixed(3) : 'N/A'}</td>
              <td className="p-3">{profileB.agreement_metrics.ruwe ? profileB.agreement_metrics.ruwe.toFixed(3) : 'N/A'}</td>
              <td className="p-3 text-right font-bold text-accent">
                {profileA.agreement_metrics.ruwe && profileB.agreement_metrics.ruwe ? Math.abs(profileA.agreement_metrics.ruwe - profileB.agreement_metrics.ruwe).toFixed(3) : 'N/A'}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* SECTION C: SKY IMAGERY COMPARISON */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Candidate A Sky */}
        <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-3">
          <span className="text-accent font-bold border-b border-border pb-1.5 uppercase tracking-wider text-[10px]">Candidate A Sky Cutout (DSS)</span>
          <img 
            src={`https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?survey=dss2r&position=${profileA.star.ra},${profileA.star.dec}&size=0.08&pixels=300&Return=jpeg`}
            alt={`${profileA.planet.pl_name} DSS cutout`}
            className="w-full h-48 bg-surface-2 rounded-lg border border-border object-cover"
          />
        </div>

        {/* Candidate B Sky */}
        <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-3">
          <span className="text-severity-critical font-bold border-b border-border pb-1.5 uppercase tracking-wider text-[10px]">Candidate B Sky Cutout (DSS)</span>
          <img 
            src={`https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?survey=dss2r&position=${profileB.star.ra},${profileB.star.dec}&size=0.08&pixels=300&Return=jpeg`}
            alt={`${profileB.planet.pl_name} DSS cutout`}
            className="w-full h-48 bg-surface-2 rounded-lg border border-border object-cover"
          />
        </div>

      </div>

      {/* SECTION D: 3D POSITION IN GALACTIC SPACE */}
      <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4 relative">
        <h3 className="font-bold text-xs text-accent border-b border-border pb-2.5 uppercase tracking-wider">
          3D Galactic Space Alignment
        </h3>
        
        <div className="h-80 w-full">
          <GalacticVisualizer
            targetStar={{
              name: profileA.planet.pl_name,
              toi_id: profileA.planet.toi_id,
              ra: profileA.star.ra,
              dec: profileA.star.dec,
              distance: profileA.star.distance || 385.9,
              ruwe: profileA.agreement_metrics.ruwe || 1.0,
              severity: 'warning',
              healthScore: profileA.agreement_metrics.catalog_agreement_score
            }}
            comparisonStar={{
              name: profileB.planet.pl_name,
              toi_id: profileB.planet.toi_id,
              ra: profileB.star.ra,
              dec: profileB.star.dec,
              distance: profileB.star.distance || 155.8,
              ruwe: profileB.agreement_metrics.ruwe || 1.0,
              severity: 'warning',
              healthScore: profileB.agreement_metrics.catalog_agreement_score
            }}
            otherStars={[
              { name: "Sol (Sun)", ra: 0, dec: 0, distance: 0, ruwe: 1.0, severity: 'normal', healthScore: 1.0 }
            ]}
          />
        </div>
      </div>

    </div>
  );
}
