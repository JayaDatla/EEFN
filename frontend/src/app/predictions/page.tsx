"use client";

import React, { useState, useEffect } from 'react';
import { ShieldAlert, Cpu, BarChart3, LineChart, CheckCircle2, Info, RefreshCw } from 'lucide-react';
import { apiUrl } from '@/lib/api';
import { Callout } from '../components/ui/Callout';

export default function PredictionsPage() {
  const [metrics, setMetrics] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMetrics();
  }, []);

  const fetchMetrics = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(apiUrl('/api/v1/predictions/metrics'));
      // UPGRADE_PLAN.md C.8: a 503 here means the real model_metrics.json
      // artifact is missing -- checking res.ok (this used to be skipped, so a
      // 503's JSON error body would have been treated as real metrics and
      // crashed the render below). Also removed the fabricated fallback
      // (hardcoded 84.48% accuracy + 7 invented "feature weights" -- A.14).
      if (!res.ok) throw new Error(res.status === 503 ? "No trained model metrics artifact exists yet" : `Backend returned ${res.status}`);
      setMetrics(await res.json());
      setError(null);
    } catch (e) {
      setMetrics(null);
      setError(e instanceof Error ? e.message : "Unable to reach the EEFN backend.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-6 max-w-7xl mx-auto w-full py-4 animate-fadeIn font-mono text-xs">
      
      {/* Title */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-border pb-5">
        <div>
          <h2 className="text-3xl font-extrabold text-ink tracking-tight font-sans">
            Quality Classifier Calibration
          </h2>
          <p className="text-sm text-muted mt-1">
            Validation metrics and predictive weight analysis for exoplanet validation classifiers.
          </p>
        </div>
        <button
          onClick={fetchMetrics}
          className="bg-surface-2 hover:bg-surface-2 border border-border text-ink/80 font-semibold px-4 py-2 rounded-lg text-xs transition-all flex items-center gap-1.5"
        >
          <RefreshCw className="h-3.5 w-3.5" /> REFRESH
        </button>
      </div>

      {error && <Callout tone="critical" title="Backend unavailable">{error}. No metrics are shown -- this is not a fallback, it is an empty result.</Callout>}

      {/* Primary Calibration Stats Cards -- UPGRADE_PLAN.md A.14: these used to
          fall back to hardcoded "84.48%"/"0.9154"/"0.8460" placeholders (plus a
          static "2,667 exoplanet candidates" caption) whenever `metrics` was
          null, indistinguishable from a real fetched value. Now: real value or
          an explicit "--". */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

        {/* CV ACCURACY */}
        <div className="surface-card p-5 flex flex-col gap-2">
          <span className="text-muted text-[10px] font-bold uppercase tracking-wider">HELD-OUT ACCURACY</span>
          <span className="text-3xl font-extrabold text-ink tracking-tight">
            {metrics ? `${(metrics.metrics.accuracy * 100).toFixed(2)}%` : "--"}
          </span>
          <span className="text-muted text-[9px] mt-1">{metrics ? `Evaluated on ${metrics.test_size} held-out candidates.` : "Awaiting data."}</span>
        </div>

        {/* ROC AUC */}
        <div className="surface-card p-5 flex flex-col gap-2">
          <span className="text-muted text-[10px] font-bold uppercase tracking-wider">VALIDATION ROC-AUC</span>
          <span className="text-3xl font-extrabold text-status-pass tracking-tight">
            {metrics ? metrics.metrics.roc_auc.toFixed(4) : "--"}
          </span>
          <span className="text-muted text-[9px] mt-1">True positive vs false positive separation.</span>
        </div>

        {/* F1 SCORE */}
        <div className="surface-card p-5 flex flex-col gap-2">
          <span className="text-muted text-[10px] font-bold uppercase tracking-wider">F1 SCORE</span>
          <span className="text-3xl font-extrabold text-ink tracking-tight">
            {metrics ? metrics.metrics.f1_score.toFixed(4) : "--"}
          </span>
          <span className="text-muted text-[9px] mt-1">Balanced precision and recall.</span>
        </div>

      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Card: ROC Curve Visualization */}
        <div className="glass-panel p-5 rounded-xl lg:col-span-2 shadow-xl flex flex-col gap-4">
          <h3 className="font-bold text-sm text-accent border-b border-border pb-2.5 flex items-center gap-2 font-mono">
            <LineChart className="h-4.5 w-4.5" /> MODEL PERFORMANCE CURVES
          </h3>
          
          <div className="flex flex-col sm:flex-row items-center gap-6">
            
            {/* SVG ROC Curve */}
            <div className="w-full sm:w-80 h-64 bg-surface-2/60 rounded-xl border border-border p-4 flex flex-col justify-between relative">
              <div className="absolute top-2 left-2 text-[8px] text-muted uppercase tracking-wider">ROC Validation Curve</div>
              
              <div className="flex-1 w-full mt-2 relative border-l border-b border-border">
                {/* Illustrative curve shape only -- not plotted from real
                    per-threshold TPR/FPR pairs (that data isn't exposed by the
                    metrics endpoint). Labeled as such below, not presented as a
                    real measured curve. */}
                <svg className="w-full h-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none">
                  <line x1="25" y1="0" x2="25" y2="100" stroke="var(--color-border)" strokeWidth="0.5" strokeDasharray="2" />
                  <line x1="50" y1="0" x2="50" y2="100" stroke="var(--color-border)" strokeWidth="0.5" strokeDasharray="2" />
                  <line x1="75" y1="0" x2="75" y2="100" stroke="var(--color-border)" strokeWidth="0.5" strokeDasharray="2" />
                  <line x1="0" y1="25" x2="100" y2="25" stroke="var(--color-border)" strokeWidth="0.5" strokeDasharray="2" />
                  <line x1="0" y1="50" x2="100" y2="50" stroke="var(--color-border)" strokeWidth="0.5" strokeDasharray="2" />
                  <line x1="0" y1="75" x2="100" y2="75" stroke="var(--color-border)" strokeWidth="0.5" strokeDasharray="2" />
                  <line x1="0" y1="100" x2="100" y2="0" stroke="var(--color-text-muted)" strokeWidth="1" strokeDasharray="3" />
                  <path
                    d="M 0,100 Q 10,20 40,8 T 100,0"
                    fill="none"
                    stroke="var(--status-pass)"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute bottom-1 right-2 text-[8px] text-muted">False Positive Rate</div>
                <div className="absolute top-1 left-2 text-[8px] text-muted rotate-90 origin-top-left translate-x-2">True Positive Rate</div>
              </div>

              <div className="flex justify-between text-[8px] text-muted font-mono mt-1">
                <span>Real AUC = {metrics ? metrics.metrics.roc_auc.toFixed(4) : "--"} (curve shape above is illustrative)</span>
              </div>
            </div>

            {/* Description -- UPGRADE_PLAN.md A.14: this used to assert a
                specific "Permutation tests (p=0.0000)" statistical claim that no
                script in this repo ever actually ran, alongside a hardcoded
                "ROC-AUC of 0.9154" regardless of the real fetched value. Removed
                the fabricated claim entirely; the real number is used above. */}
            <div className="flex-1 flex flex-col gap-3 font-sans text-xs text-muted leading-relaxed">
              <h4 className="text-ink font-bold font-sans text-sm">Model summary</h4>
              <p>
                EEFN&apos;s Random Forest classifier is trained on cross-catalog disagreement metrics
                (derived planet size deltas, Teff mismatch, RUWE, distance mismatch, and related fields).
              </p>
              {metrics && (
                <div className="bg-surface-2 p-2.5 border border-border rounded-lg flex items-start gap-2">
                  <Info className="h-4.5 w-4.5 text-accent shrink-0 mt-0.5" />
                  <span className="text-[10px] font-mono leading-normal">
                    Evaluated {new Date(metrics.evaluated_at).toLocaleDateString()} on {metrics.test_size} held-out
                    candidates ({metrics.dataset_size} total dataset rows). See <code>LIMITATIONS.md</code> §1.1
                    for the label-leakage ablation results before treating this accuracy as unqualified.
                  </span>
                </div>
              )}
            </div>

          </div>
        </div>

        {/* Right Card: Features used in training */}
        <div className="surface-card p-5 flex flex-col gap-4">
          <h3 className="font-bold text-sm text-accent border-b border-border pb-2.5 flex items-center gap-2 font-mono">
            <BarChart3 className="h-4.5 w-4.5" /> FEATURES USED IN TRAINING
          </h3>
          {/* UPGRADE_PLAN.md A.14: per-feature "importance" weights here used to be
              fabricated -- undefined for every real feature and silently defaulted
              to a uniform 5.0% / 40%-width bar, implying equal importance that was
              never actually computed. The real /predictions/metrics artifact only
              lists which features were used, not a global importance ranking, so
              this panel now shows exactly that and nothing invented. */}
          <div className="flex flex-col gap-1.5">
            {metrics?.features?.length ? (
              metrics.features.map((f: any, idx: number) => (
                <div key={idx} className="flex justify-between font-mono text-[10px] text-ink/80 border-b border-border/40 py-1">
                  <span>{idx + 1}. {typeof f === "string" ? f : f.name}</span>
                </div>
              ))
            ) : (
              <span className="text-muted text-xs">{metrics ? "No feature list in this artifact." : "Querying model artifact..."}</span>
            )}
          </div>
        </div>

      </div>

    </div>
  );
}
