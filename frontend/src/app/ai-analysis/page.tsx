"use client";

import React, { useState, useEffect } from 'react';
import { Cpu, Database, RefreshCw, Eye, Sparkles, AlertCircle, HelpCircle, Check } from 'lucide-react';
import { apiUrl } from '@/lib/api';
import { Callout } from '../components/ui/Callout';

interface Candidate {
  pl_name: string;
  tic_id: number;
  toi_id: number;
  disposition: string;
  orbper: number | null;
  rade: number | null;
  trandep: number | null;
  trandurh: number | null;
  insol: number | null;
  eqt: number | null;
  evidence_consistency_score: number | null;
  followup_priority_score: number | null;
}

const MODEL_LABELS: Record<string, { name: string; note: string }> = {
  baseline_cnn: { name: "DeepExoFusionNet (previous production model)", note: "3.9M-parameter 4-branch CNN" },
  compact_cnn: { name: "Compact dual-view CNN", note: "~60k parameters, global pooling, augmentation, 3-seed ensemble" },
  features_gbm: { name: "Gradient boosting on physics features (shipped)", note: "odd/even depth, secondary eclipse, shape, implied radius, ..." },
  hybrid: { name: "CNN embedding + physics features", note: "matched the simple model, with more complexity" },
};

const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? "--" : `${(v * 100).toFixed(digits)}%`;

export default function AIAnalysisPage() {
  const [activeTab, setActiveTab] = useState('comparison');
  const [candidates, setCandidates] = useState([] as Candidate[]);
  const [isLoadingCand, setIsLoadingCand] = useState(false);
  const [selectedCand, setSelectedCand] = useState(null as Candidate | null);
  const [profile, setProfile] = useState(null as any);
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [profileFailed, setProfileFailed] = useState(false);

  // Real evaluation of the shipped light-curve vetter, the architecture study that chose it,
  // and the TESS transfer check -- all served from committed artifacts via
  // /predictions/lightcurve_vetter. Never falls back to a literal: if the endpoint 503s the
  // page says so instead of showing a plausible-looking number.
  const [report, setReport] = useState(null as any);
  const [reportError, setReportError] = useState(null as string | null);

  useEffect(() => {
    fetchCandidates();
    fetchReport();
  }, []);

  const fetchReport = async () => {
    try {
      const res = await fetch(apiUrl('/api/v1/predictions/lightcurve_vetter'));
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Backend returned ${res.status}`);
      }
      setReport(await res.json());
      setReportError(null);
    } catch (e) {
      setReport(null);
      setReportError(e instanceof Error ? e.message : 'Unable to reach the EEFN backend.');
    }
  };

  const fetchCandidates = async () => {
    setIsLoadingCand(true);
    try {
      const res = await fetch(apiUrl('/api/v1/candidates?limit=150'));
      const data = await res.json();
      setCandidates(Array.isArray(data) ? data : data.items ?? []);
    } catch (e) {
      console.error("API error fetching candidates", e);
    } finally {
      setIsLoadingCand(false);
    }
  };

  // The stored result of the nightly real-light-curve vetting -- not a classification of a
  // simulated curve (see LIMITATIONS.md section 7).
  const loadProfile = async (cand: Candidate) => {
    setSelectedCand(cand);
    setIsLoadingProfile(true);
    setProfile(null);
    setProfileFailed(false);
    try {
      const res = await fetch(apiUrl(`/api/v1/candidates/${cand.toi_id}`));
      if (!res.ok) throw new Error(String(res.status));
      setProfile(await res.json());
    } catch (e) {
      console.error("Error loading candidate", e);
      setProfileFailed(true);
    } finally {
      setIsLoadingProfile(false);
    }
  };

  const totalCount = candidates.length;
  const potentialPlanets = candidates.filter(c => c.disposition !== "FP" && (c.rade || 5.0) < 20.0);
  const potentialEBs = candidates.filter(c => c.disposition === "FP" || (c.rade && c.rade >= 20.0));

  const vetting = profile?.real_observations?.lightcurve_vetting;
  const centroid = profile?.real_observations?.centroid;
  const classification: Record<string, number> = vetting?.classification ?? {};
  const bestClass: string | null = vetting?.best_class ?? null;
  const confidence = bestClass ? classification[bestClass] : null;

  const studyModels = report?.architecture_study?.models ?? {};
  const tess = report?.tess_transfer;
  const cm = report?.confusion_matrix_oof;

  // Full literal class names (Tailwind cannot see names assembled by interpolation).
  const classBadge = (cls: string) =>
    cls.includes('Planet')
      ? 'bg-status-pass/10 text-status-pass border border-status-pass/30'
      : cls.includes('Binary')
        ? 'bg-accent/10 text-accent border border-accent/30'
        : 'bg-severity-critical/10 text-severity-critical border border-severity-critical/30';

  return (
    <div className="flex-1 flex flex-col gap-6 max-w-7xl mx-auto w-full py-4 animate-fadeIn text-xs text-ink/80">

      {reportError ? (
        <Callout tone="warning" title="Model evaluation unavailable">
          {reportError} Nothing on this page should be read as a validated performance claim until
          the backend serves the evaluation artifact.
        </Callout>
      ) : report ? (
        <Callout tone="info" title="Measured on real data, with its limits">
          {report.data_source} Accuracy figures are star-grouped cross-validation, so every KOI of a
          star stays on one side of each split. {report.known_gaps?.[0]}
        </Callout>
      ) : null}

      <div className="section-heading">
        <div>
          <p className="eyebrow">Models / light-curve vetting</p>
          <h1>Light-Curve Vetting Diagnostics</h1>
          <p className="section-description">
            Which architecture was chosen and why, how well it performs on Kepler and on real TESS targets,
            and what it says about each candidate&apos;s real light curve.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { fetchCandidates(); fetchReport(); }}
            className="bg-surface-2 hover:bg-surface-2 border border-border text-ink/80 font-semibold px-4 py-2 rounded-lg text-xs transition-all flex items-center gap-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoadingCand ? 'animate-spin' : ''}`} /> REFRESH
          </button>
        </div>
      </div>

      <div className="flex border-b border-border gap-1 text-[11px] font-bold">
        {[
          { id: 'comparison', icon: <Cpu className="h-4 w-4" />, label: 'ARCHITECTURE COMPARISON' },
          { id: 'performance', icon: <Database className="h-4 w-4" />, label: 'PERFORMANCE & TESS TRANSFER' },
          { id: 'live', icon: <Sparkles className="h-4 w-4" />, label: 'LIVE CANDIDATE VETTING' },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-5 py-3 border-b-2 transition-all flex items-center gap-2 ${activeTab === t.id ? 'border-accent text-ink bg-accent/10' : 'border-transparent text-muted hover:text-ink'}`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* TAB: ARCHITECTURE COMPARISON */}
      {activeTab === 'comparison' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          <div className="glass-panel p-5 rounded-xl lg:col-span-2 shadow-xl flex flex-col gap-4 border border-border">
            <h3 className="panel-title"><Cpu className="h-4.5 w-4.5" /> Same data, same folds, four models</h3>
            {!report ? (
              <span className="text-muted italic">No comparison available -- the evaluation artifact could not be loaded.</span>
            ) : (
              <>
                <p className="text-muted font-sans leading-relaxed">
                  {report.architecture_study?.n_kois} KOIs from {report.architecture_study?.n_stars} real Kepler stars.
                  {" "}{report.architecture_study?.protocol}. A model that always answers with the most common class
                  scores {pct(report.majority_class_baseline)}.
                </p>
                <div className="flex flex-col gap-3">
                  {Object.entries(studyModels)
                    .sort((a: any, b: any) => b[1].accuracy_mean - a[1].accuracy_mean)
                    .map(([key, m]: any) => {
                      const meta = MODEL_LABELS[key] ?? { name: key, note: "" };
                      return (
                        <div key={key} className="flex flex-col gap-1">
                          <div className="flex justify-between text-ink/90">
                            <span className="font-semibold">{meta.name}</span>
                            <span className="font-mono font-bold">
                              {pct(m.accuracy_mean)} <span className="text-muted font-normal">&plusmn; {pct(m.accuracy_std)}</span>
                            </span>
                          </div>
                          <div className="w-full bg-surface-2 h-2 rounded overflow-hidden border border-border">
                            <div className={`h-full rounded ${key === 'features_gbm' ? 'bg-status-pass' : 'bg-accent'}`} style={{ width: `${m.accuracy_mean * 100}%` }} />
                          </div>
                          <span className="text-muted text-[9px]">
                            {meta.note} &middot; macro-F1 {m.macro_f1_mean.toFixed(2)} &middot; {m.n_folds} folds
                          </span>
                        </div>
                      );
                    })}
                </div>
              </>
            )}
          </div>
          <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-3 border border-border">
            <h3 className="panel-title"><Eye className="h-4.5 w-4.5" /> Why the simple model won</h3>
            <p className="text-muted font-sans leading-relaxed">
              With a couple of hundred labelled stars, a network with millions of parameters memorises the
              training set (the previous model scored 100% on its training stars) and the held-out score swings
              by more than ten points from fold to fold.
            </p>
            <p className="text-muted font-sans leading-relaxed">
              The checks an astronomer makes by hand &mdash; do odd and even transits have the same depth? is
              there a secondary eclipse? is the bottom flat or V-shaped? is the implied planet radius plausible?
              &mdash; can be computed directly, leaving ~20 inputs that boosted trees fit reliably.
            </p>
            <Callout tone="warning" title="Not a claim that deep learning can&apos;t work here">
              AstroNet and ExoMiner train on tens of thousands of light curves. This comparison is specific to a
              dataset this size.
            </Callout>
          </div>
        </div>
      )}

      {/* TAB: PERFORMANCE & TESS TRANSFER */}
      {activeTab === 'performance' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          <div className="glass-panel p-5 rounded-xl lg:col-span-2 shadow-xl flex flex-col gap-4 border border-border">
            <h3 className="panel-title"><Database className="h-4.5 w-4.5" /> Shipped vetter: {report?.model_version ?? '--'}</h3>
            {reportError && <Callout tone="critical" title="No evaluation report available">{reportError}</Callout>}
            {report && (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {[
                    { label: 'REAL STARS', value: report.n_stars, sub: `${report.n_kois} KOIs` },
                    { label: 'CV ACCURACY', value: pct(report.cv_accuracy_mean), sub: `± ${pct(report.cv_accuracy_std)} across folds` },
                    { label: 'MACRO-F1', value: report.cv_macro_f1_mean.toFixed(2), sub: 'class-balanced' },
                    { label: 'MAJORITY BASELINE', value: pct(report.majority_class_baseline), sub: 'always guess the common class' },
                  ].map(c => (
                    <div key={c.label} className="bg-surface-2/60 p-4 border border-border rounded-lg text-center">
                      <div className="text-muted text-[9px] uppercase tracking-wider">{c.label}</div>
                      <div className="text-2xl font-bold text-ink mt-1">{c.value}</div>
                      <div className="text-[8px] text-muted mt-1">{c.sub}</div>
                    </div>
                  ))}
                </div>

                {cm && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-[10px] font-mono">
                      <caption className="text-left text-muted text-[9px] pb-1.5">
                        Out-of-fold confusion (rows = true class, columns = predicted)
                      </caption>
                      <thead>
                        <tr className="text-muted border-b border-border">
                          <th className="p-2" />
                          {cm.labels.map((l: string) => <th key={l} className="p-2">{l}</th>)}
                          <th className="p-2">Recall</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cm.rows_true_cols_pred.map((row: number[], i: number) => (
                          <tr key={i} className="border-b border-border/40">
                            <td className="p-2 text-ink font-bold">{cm.labels[i]}</td>
                            {row.map((v, j) => (
                              <td key={j} className={`p-2 ${i === j ? 'text-status-pass font-bold' : 'text-muted'}`}>{v}</td>
                            ))}
                            <td className="p-2 text-ink">{pct(report.per_class_recall?.[cm.labels[i]], 0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {report.ablation && (
                  <Callout tone="info" title="Does it rely on catalog inputs?">
                    No. With every stellar and catalog-derived input removed, cross-validated accuracy is{" "}
                    {pct(report.ablation.ablation?.["light-curve features only (no stellar/catalog inputs)"]?.accuracy)}{" "}
                    against {pct(report.ablation.ablation?.["all features (shipped)"]?.accuracy)} with them
                    (95% CI {pct(report.ablation.ablation?.["all features (shipped)"]?.ci95_by_star?.[0], 0)}&ndash;
                    {pct(report.ablation.ablation?.["all features (shipped)"]?.ci95_by_star?.[1], 0)}). Recall on
                    binaries Kepler labelled by a centroid offset alone, which the model cannot see, is only{" "}
                    {pct(report.ablation.eclipsing_binary_recall_by_kepler_flag?.["centroid-offset flag only (invisible to this model)"]?.recall, 0)}.
                  </Callout>
                )}
                <Callout tone="warning" title="Calibration is measured on Kepler only">
                  Out-of-fold calibration error on Kepler is {report.ablation?.calibration?.ece_before?.toFixed(3) ?? "--"}
                  (and rescaling does not improve it). On TESS the probabilities are unchecked: 50 labelled
                  targets are too few. Use them to rank candidates, not as stated frequencies.
                </Callout>
              </>
            )}
          </div>

          <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4 border border-border">
            <h3 className="panel-title"><Sparkles className="h-4.5 w-4.5" /> Transfer to real TESS targets</h3>
            {!tess ? (
              <span className="text-muted italic">No TESS transfer check has been run.</span>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3 text-center">
                  <div className="bg-surface-2/60 p-3 border border-border rounded-lg">
                    <div className="text-muted text-[9px] uppercase tracking-wider">AGREEMENT</div>
                    <div className="text-xl font-bold text-ink mt-1">{pct(tess.accuracy, 0)}</div>
                    <div className="text-[8px] text-muted mt-1">with the TFOP label, n={tess.n_vetted}</div>
                  </div>
                  <div className="bg-surface-2/60 p-3 border border-border rounded-lg">
                    <div className="text-muted text-[9px] uppercase tracking-wider">ROC-AUC</div>
                    <div className="text-xl font-bold text-ink mt-1">{tess.roc_auc_planet_vs_not?.toFixed(2) ?? '--'}</div>
                    <div className="text-[8px] text-muted mt-1">planet vs not</div>
                  </div>
                </div>
                <div className="flex flex-col gap-1 font-mono text-[10px]">
                  <div className="flex justify-between"><span className="text-muted">Planets called planet</span><span className="text-ink">{tess.confusion.planet_called_planet} / {tess.n_planets}</span></div>
                  <div className="flex justify-between"><span className="text-muted">Non-planets called not</span><span className="text-ink">{tess.confusion.non_planet_called_not} / {tess.n_non_planets}</span></div>
                </div>
                {tess.model_version && report?.model_version && tess.model_version !== report.model_version && (
                  <Callout tone="warning" title="Measured on an earlier model version">
                    This transfer check ran on {tess.model_version}; the shipped model is {report.model_version}.
                    Treat the numbers as pre-fix until the check is re-run.
                  </Callout>
                )}
                <Callout tone="warning" title="Lower than on Kepler, by design of the test">
                  {tess.caveats?.[1]} {tess.caveats?.[0]}
                </Callout>
              </>
            )}
          </div>
        </div>
      )}

      {/* TAB: LIVE CANDIDATE VETTING */}
      {activeTab === 'live' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          <div className="glass-panel p-5 rounded-xl lg:col-span-2 shadow-xl flex flex-col gap-4 border border-border min-h-[480px]">
            <div className="flex justify-between items-center border-b border-border pb-3">
              <h3 className="font-bold text-sm text-accent flex items-center gap-2">
                <Database className="h-4.5 w-4.5" /> Target Candidates ({candidates.length})
              </h3>
              <span className="text-muted text-[9px]">Results come from each candidate&apos;s real SPOC TESS light curve</span>
            </div>

            {isLoadingCand ? (
              <div className="flex-1 flex items-center justify-center text-muted">
                <RefreshCw className="h-6 w-6 animate-spin text-accent mr-2" /> Fetching candidates...
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto max-h-[460px] border border-border/60 rounded-lg">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-surface-2 border-b border-border text-muted uppercase tracking-wider text-[8px]">
                      <th className="p-3">TOI ID</th>
                      <th className="p-3">Candidate</th>
                      <th className="p-3">Disposition</th>
                      <th className="p-3">Period</th>
                      <th className="p-3">Radius</th>
                      <th className="p-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((c) => (
                      <tr key={c.toi_id} className={`border-b border-border/40 hover:bg-surface-2/20 transition-all ${selectedCand?.toi_id === c.toi_id ? 'bg-accent/5' : ''}`}>
                        <td className="p-3 text-ink font-bold">{c.toi_id.toFixed(2)}</td>
                        <td className="p-3">{c.pl_name}</td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded font-bold text-[8px] ${c.disposition === 'CP' ? 'bg-status-pass/10 text-status-pass border border-status-pass/20' : c.disposition === 'FP' ? 'bg-severity-critical/10 text-severity-critical border border-severity-critical/20' : 'bg-accent/10 text-accent border border-accent/20'}`}>
                            {c.disposition === 'CP' ? 'CONFIRMED' : c.disposition === 'FP' ? 'FALSE POSITIVE' : 'CANDIDATE'}
                          </span>
                        </td>
                        <td className="p-3">{c.orbper ? `${c.orbper.toFixed(2)}d` : 'N/A'}</td>
                        <td className="p-3 text-muted">{c.rade ? `${c.rade.toFixed(2)} Re` : 'N/A'}</td>
                        <td className="p-3 text-right">
                          <button
                            onClick={() => loadProfile(c)}
                            className="bg-surface-2 border border-border hover:border-accent/50 hover:bg-accent/10 text-accent px-3 py-1 rounded transition-all flex items-center gap-1 inline-flex text-[9px] font-bold"
                          >
                            <Cpu className="h-3 w-3" /> VIEW VETTING
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4 border border-border">
            <h3 className="panel-title"><Eye className="h-4.5 w-4.5" /> Real-Observation Vetting</h3>

            {isLoadingProfile ? (
              <div className="flex-1 flex flex-col items-center justify-center text-muted gap-2">
                <RefreshCw className="h-8 w-8 animate-spin text-accent" />
                <span className="text-[10px]">Loading stored measurements...</span>
              </div>
            ) : selectedCand && profileFailed ? (
              <div className="flex-1 flex flex-col items-center justify-center text-muted text-center gap-1.5">
                <AlertCircle className="h-7 w-7 text-muted" />
                <span>Could not load this candidate</span>
              </div>
            ) : selectedCand && profile ? (
              <div className="flex-1 flex flex-col gap-4">
                <div className="bg-surface-2 border border-border rounded-lg p-3 flex flex-col gap-1.5">
                  <div className="flex justify-between text-ink">
                    <span className="font-bold text-xs">{selectedCand.pl_name} (TOI-{selectedCand.toi_id})</span>
                    <span className="text-muted text-[10px]">TIC {selectedCand.tic_id}</span>
                  </div>
                  <div className="flex justify-between border-t border-border/60 pt-1.5 text-muted text-[9px]">
                    <span>Period: {selectedCand.orbper?.toFixed(3)}d</span>
                    <span>Depth: {selectedCand.trandep?.toFixed(1)} ppm</span>
                    <span>Size: {selectedCand.rade?.toFixed(2)} Re</span>
                  </div>
                </div>

                {vetting?.status === 'vetted' && bestClass ? (
                  <>
                    <div className="bg-surface-2 p-4 border border-border rounded-lg flex flex-col gap-2">
                      <span className="text-muted text-[8px] uppercase tracking-wider">Light-curve verdict</span>
                      <div className="flex items-center justify-between">
                        <span className="text-ink font-extrabold text-sm font-sans tracking-wide">{bestClass.toUpperCase()}</span>
                        <span className={`px-2 py-0.5 rounded font-extrabold text-[9px] ${classBadge(bestClass)}`}>
                          {((confidence ?? 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <span className="text-muted text-[8px]">
                        Sectors {vetting.sectors?.join(', ')} &middot; {vetting.model_version} &middot; calibration unchecked on TESS
                      </span>
                    </div>
                    <div className="flex flex-col gap-3 font-mono text-[9px]">
                      {Object.entries(classification).map(([cls, prob]) => (
                        <div key={cls} className="flex flex-col gap-1">
                          <div className="flex justify-between text-ink/80">
                            <span>{cls}</span>
                            <span className="font-bold">{(prob * 100).toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-surface-2 h-2 rounded overflow-hidden border border-border/60">
                            <div className="h-full rounded bg-accent transition-all duration-500" style={{ width: `${prob * 100}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <Callout tone="info" title="Not vetted against a real light curve yet">
                    Status: {vetting?.status ?? 'not attempted'}. The nightly job processes a few candidates
                    per run; candidates with no 2-minute SPOC light curve stay unvetted. No classification is
                    shown rather than classifying a simulation.
                  </Callout>
                )}

                <div className="bg-surface-2/60 border border-border/60 rounded p-3 flex flex-col gap-1 text-[9px]">
                  <span className="text-muted uppercase tracking-wider text-[8px]">Centroid check (real TESS pixels)</span>
                  {centroid?.measured ? (
                    <>
                      <div className="flex justify-between"><span className="text-muted">Photocentre shift</span><span className="text-ink font-mono">{(centroid.photocentre_shift_arcsec * 1000).toFixed(1)} mas</span></div>
                      <div className="flex justify-between"><span className="text-muted">Implied source offset</span><span className="text-ink font-mono">{centroid.implied_source_offset_arcsec != null ? `${centroid.implied_source_offset_arcsec.toFixed(2)}″ ± ${centroid.implied_source_offset_err_arcsec?.toFixed(2)}` : '--'}</span></div>
                      {centroid.min_detectable_offset_arcsec != null && (
                        <div className="flex justify-between"><span className="text-muted">Detectable at 3&sigma;</span><span className="text-ink font-mono">&ge; {centroid.min_detectable_offset_arcsec.toFixed(1)}&Prime;</span></div>
                      )}
                      <div className="flex justify-between"><span className="text-muted">Verdict</span><span className={centroid.is_dip ? 'text-severity-critical font-bold' : 'text-status-pass font-bold'}>{centroid.is_dip ? 'OFF-TARGET SIGNAL' : 'No significant offset'}</span></div>
                    </>
                  ) : (
                    <span className="text-muted">Not measured yet ({centroid?.status ?? 'not attempted'}).</span>
                  )}
                </div>

                <div className="bg-surface-2/60 border border-border/60 rounded p-2 text-muted text-[8px] flex gap-1.5 mt-auto leading-normal">
                  <Check className="h-3 w-3 text-status-pass shrink-0 mt-0.5" />
                  <span>
                    Disposition label shown in the table is the human TFOP label; it is never an input to this score.
                  </span>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-muted text-center gap-1">
                <HelpCircle className="h-8 w-8 text-muted" />
                <span>No Target Selected</span>
                <span className="text-[9px] text-muted">Click &quot;View Vetting&quot; to load stored measurements</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-panel p-5 rounded-xl flex flex-col gap-1 border border-border shadow-lg">
          <span className="text-muted text-[9px] font-bold uppercase tracking-wider">DATABASE CANDIDATES</span>
          <span className="text-2xl font-extrabold text-ink tracking-tight">
            {isLoadingCand ? <span className="text-muted text-base">Loading&hellip;</span> : totalCount}
          </span>
          <span className="text-muted text-[8px] mt-1">Aggregated across TIC and catalog records.</span>
        </div>
        <div className="glass-panel p-5 rounded-xl flex flex-col gap-1 border border-border shadow-lg">
          <span className="text-muted text-[9px] font-bold uppercase tracking-wider">PHYSICALLY PLAUSIBLE SIZE</span>
          <span className="text-2xl font-extrabold text-status-pass tracking-tight">
            {isLoadingCand ? <span className="text-muted text-base">Loading&hellip;</span> : potentialPlanets.length}
          </span>
          <span className="text-muted text-[8px] mt-1">Not labelled FP and R<sub>p</sub> &lt; 20 R<sub>&oplus;</sub>. A size screen, not a classification.</span>
        </div>
        <div className="glass-panel p-5 rounded-xl flex flex-col gap-1 border border-border shadow-lg">
          <span className="text-muted text-[9px] font-bold uppercase tracking-wider">LABELLED FP OR OVERSIZED</span>
          <span className="text-2xl font-extrabold text-accent tracking-tight">
            {isLoadingCand ? <span className="text-muted text-base">Loading&hellip;</span> : potentialEBs.length}
          </span>
          <span className="text-muted text-[8px] mt-1">Marked false positive, or R<sub>p</sub> &ge; 20 R<sub>&oplus;</sub>.</span>
        </div>
      </div>

    </div>
  );
}
