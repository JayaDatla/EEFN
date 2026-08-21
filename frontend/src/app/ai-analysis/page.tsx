"use client";

import React, { useState, useEffect } from 'react';
import { Cpu, Database, RefreshCw, Eye, Sparkles, AlertCircle, HelpCircle, Check, Info } from 'lucide-react';
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

export default function AIAnalysisPage() {
  const [activeTab, setActiveTab] = useState('architecture');
  const [candidates, setCandidates] = useState([] as Candidate[]);
  const [isLoadingCand, setIsLoadingCand] = useState(false);
  const [selectedCand, setSelectedCand] = useState(null as Candidate | null);
  const [dlResult, setDlResult] = useState(null as any);
  const [isLoadingDl, setIsLoadingDl] = useState(false);

  // Real training statistics from app/ml/dl_training_report.json, served via
  // /predictions/dl_training. These were previously hardcoded in this file and had
  // gone stale across a retrain, a metadata-vector expansion and a class-count
  // change while still being displayed as current fact. Never falls back to a
  // literal -- if the endpoint 503s (no artifact yet), the panel says so.
  const [trainingReport, setTrainingReport] = useState(null as any);
  const [trainingReportError, setTrainingReportError] = useState(null as string | null);

  // Custom interactive vetting parameters
  const [noiseStd, setNoiseStd] = useState(0.001);
  const [hasStarspots, setHasStarspots] = useState(true);

  useEffect(() => {
    fetchCandidates();
    fetchTrainingReport();
  }, []);

  const fetchTrainingReport = async () => {
    try {
      const res = await fetch(apiUrl('/api/v1/predictions/dl_training'));
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Backend returned ${res.status}`);
      }
      setTrainingReport(await res.json());
      setTrainingReportError(null);
    } catch (e) {
      setTrainingReport(null);
      setTrainingReportError(e instanceof Error ? e.message : 'Unable to reach the EEFN backend.');
    }
  };

  const fetchCandidates = async () => {
    setIsLoadingCand(true);
    try {
      const res = await fetch(apiUrl('/api/v1/candidates?limit=150'));
      const data = await res.json();
      setCandidates(data);
    } catch (e) {
      console.error("API error fetching candidates", e);
    } finally {
      setIsLoadingCand(false);
    }
  };

  const runVettingModel = async (cand: Candidate) => {
    setSelectedCand(cand);
    setIsLoadingDl(true);
    setDlResult(null);
    try {
      const url = apiUrl(`/api/v1/candidates/${cand.toi_id}/transit_pipeline?noise_std=${noiseStd}&has_starspots=${hasStarspots}`);
      const res = await fetch(url);
      const data = await res.json();
      setDlResult(data);
    } catch (e) {
      console.error("Error vetting candidate", e);
    } finally {
      setIsLoadingDl(false);
    }
  };

  // Compute summary stats from fetched database candidates
  const totalCount = candidates.length;
  const potentialPlanets = candidates.filter(c => {
    // Planets have moderate radius and CP/PC disposition
    if (c.disposition === "FP") return false;
    const rade = c.rade || 5.0;
    return 20.0 > rade;
  });
  const potentialEBs = candidates.filter(c => {
    // EBs are FP disposition or have unphysically large radius
    return c.disposition === "FP" || (c.rade && c.rade >= 20.0);
  });
  // Find key with the highest value in dlResult.dl_classification
  let bestClass = "Unknown";
  let confidence = 0.0;
  if (dlResult && dlResult.dl_classification) {
    let maxVal = -1;
    for (const [cls, val] of Object.entries(dlResult.dl_classification)) {
      if ((val as number) > maxVal) {
        maxVal = val as number;
        bestClass = cls;
      }
    }
    confidence = maxVal;
  }

  return (
    <div className="flex-1 flex flex-col gap-6 max-w-7xl mx-auto w-full py-4 animate-fadeIn font-mono text-xs text-ink/80">

      {/* Driven by the real training artifact, not a hardcoded claim -- this banner
          previously asserted "trained entirely on synthetic light curves" as a literal,
          which would have silently become FALSE the moment the model was retrained on
          real data (and was already stale in the other direction before that). */}
      {trainingReport?.data_source?.includes("real") ? (
        <Callout tone="info" title="Trained on real light curves">
          Training data: {trainingReport.data_source}
          {trainingReport.known_gaps ? ` Known gaps: ${trainingReport.known_gaps}` : null}
          {" "}The block diagram below does not yet depict the 4th (centroid) branch.
        </Callout>
      ) : (
        <Callout tone="warning" title="Model training provenance unverified">
          No real training report is currently available from the backend, so nothing on this
          page should be read as a validated performance claim. The block diagram below also
          does not yet depict the 4th (centroid) branch.
        </Callout>
      )}

      {/* Title */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-border pb-5">
        <div>
          <h2 className="text-3xl font-extrabold text-ink tracking-tight font-sans">
            Deep Learning AI Diagnostics
          </h2>
          <p className="text-sm text-muted mt-1">
            DeepExoFusionNet model parameters, scaled multi-modal training metrics, and live target classification diagnostics.
          </p>
        </div>
        <div className="flex gap-2">
          <button 
            onClick={fetchCandidates}
            className="bg-surface-2 hover:bg-surface-2 border border-border text-ink/80 font-semibold px-4 py-2 rounded-lg text-xs transition-all flex items-center gap-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoadingCand ? 'animate-spin' : ''}`} /> REFRESH DATABASE
          </button>
        </div>
      </div>

      {/* Tabs Menu */}
      <div className="flex border-b border-border gap-1 text-[11px] font-bold">
        <button 
          onClick={() => setActiveTab('architecture')}
          className={`px-5 py-3 border-b-2 transition-all flex items-center gap-2 ${activeTab === 'architecture' ? 'border-accent text-ink bg-accent/10' : 'border-transparent text-muted hover:text-ink'}`}
        >
          <Cpu className="h-4 w-4" /> MODEL ARCHITECTURE
        </button>
        <button 
          onClick={() => setActiveTab('training')}
          className={`px-5 py-3 border-b-2 transition-all flex items-center gap-2 ${activeTab === 'training' ? 'border-accent text-ink bg-accent/10' : 'border-transparent text-muted hover:text-ink'}`}
        >
          <Database className="h-4 w-4" /> TRAINING DATASET & SCALING
        </button>
        <button 
          onClick={() => setActiveTab('predictions')}
          className={`px-5 py-3 border-b-2 transition-all flex items-center gap-2 ${activeTab === 'predictions' ? 'border-accent text-ink bg-accent/10' : 'border-transparent text-muted hover:text-ink'}`}
        >
          <Sparkles className="h-4 w-4" /> LIVE VETTING DIAGNOSTICS
        </button>
      </div>

      {/* Tab CONTENT: MODEL ARCHITECTURE */}
      {activeTab === 'architecture' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          {/* Left Panel: Diagram / Visual blocks */}
          <div className="glass-panel p-5 rounded-xl lg:col-span-2 shadow-xl flex flex-col gap-5 border border-border">
            <h3 className="font-bold text-sm text-accent border-b border-border pb-2.5 flex items-center gap-2">
              <Cpu className="h-4.5 w-4.5" /> DeepExoFusionNet Structural Specification
            </h3>
            
            {/* Structural Flow Diagram */}
            <div className="bg-surface-2/80 border border-border rounded-xl p-6 flex flex-col gap-6 relative">
              <div className="absolute top-3 right-3 text-[9px] text-muted tracking-widest font-mono uppercase">Multi-Modal Fusion</div>
              
              <div className="grid grid-cols-3 gap-4 text-center">
                {/* Branch 1 */}
                <div className="bg-surface-2/60 p-4 border border-border/80 rounded-lg flex flex-col gap-2">
                  <span className="text-[10px] text-accent font-bold uppercase tracking-wider">Global View CNN</span>
                  <span className="text-[9px] text-muted">Inputs: Folded Global LC</span>
                  <span className="text-ink text-xs font-mono bg-surface-2 py-1 rounded">1 x 2001 bins</span>
                  <div className="text-[9px] text-muted text-left mt-2 flex flex-col gap-1">
                    <div>• 4x 1D Conv Blocks</div>
                    <div>• 1D Batch Normalization</div>
                    <div>• 1D MaxPool (down to 63)</div>
                    <div>• Dense 256 + Dropout(0.2)</div>
                  </div>
                  <div className="text-accent font-bold border-t border-border pt-2 mt-auto text-[10px]">
                    Output: 256 Features
                  </div>
                </div>

                {/* Branch 2 */}
                <div className="bg-surface-2/60 p-4 border border-border/80 rounded-lg flex flex-col gap-2">
                  <span className="text-[10px] text-accent font-bold uppercase tracking-wider">Local View CNN</span>
                  <span className="text-[9px] text-muted">Inputs: Folded Transit LC</span>
                  <span className="text-ink text-xs font-mono bg-surface-2 py-1 rounded">1 x 201 bins</span>
                  <div className="text-[9px] text-muted text-left mt-2 flex flex-col gap-1">
                    <div>• 3x 1D Conv Blocks</div>
                    <div>• 1D Batch Normalization</div>
                    <div>• 1D MaxPool (down to 100)</div>
                    <div>• Dense 128 + Dropout(0.2)</div>
                  </div>
                  <div className="text-accent font-bold border-t border-border pt-2 mt-auto text-[10px]">
                    Output: 128 Features
                  </div>
                </div>

                {/* Branch 3 */}
                <div className="bg-surface-2/60 p-4 border border-border/80 rounded-lg flex flex-col gap-2">
                  <span className="text-[10px] text-accent font-bold uppercase tracking-wider">Stellar MLP</span>
                  <span className="text-[9px] text-muted">Inputs: Scaled Parameters</span>
                  {/* UPGRADE_PLAN.md F.2: this was stale at "8 Features" from before
                      the metadata vector was expanded to 28 dims (h_mag/g_mag/r_mag +
                      10 presence bits) -- found during a final honesty sweep. */}
                  <span className="text-ink text-xs font-mono bg-surface-2 py-1 rounded">28 Features</span>
                  <div className="text-[9px] text-muted text-left mt-2 flex flex-col gap-1">
                    <div>• Dense 32 + BatchNorm</div>
                    <div>• Dense 64 + BatchNorm</div>
                    <div>• Dense 64 + ReLU</div>
                    <div>• Scaling factor centering</div>
                  </div>
                  <div className="text-accent font-bold border-t border-border pt-2 mt-auto text-[10px]">
                    Output: 64 Features
                  </div>
                </div>
              </div>

              {/* Fusion point */}
              <div className="flex flex-col items-center justify-center my-3 relative">
                <div className="h-6 w-0.5 bg-gradient-to-b bg-accent"></div>
                <div className="bg-accent/10 border border-accent text-accent font-bold px-6 py-2.5 rounded-lg shadow-lg  uppercase tracking-widest text-[10px]">
                  Late-Fusion Concatenation (448 features)
                </div>
                <div className="h-6 w-0.5 bg-gradient-to-b bg-accent"></div>
              </div>

              {/* Fully connected classifier */}
              <div className="bg-surface-2/40 border border-border rounded-lg p-3 text-center flex flex-col gap-1">
                <span className="text-[9px] text-muted uppercase tracking-widest">Late fully connected layers</span>
                <span className="text-ink text-xs">Linear(448 → 128) + ReLU + Dropout(0.3)</span>
                <span className="text-ink text-xs">Linear(128 → 64) + ReLU</span>
                <span className="text-ink text-xs">Linear(64 → 3 Classifier Logits)</span>
              </div>

              <div className="grid grid-cols-4 gap-2 mt-2 text-center text-[10px] font-bold text-muted">
                <div className="bg-accent/10 border border-accent/20 p-2 rounded">Planet Transit</div>
                <div className="bg-accent/10 border border-accent/20 p-2 rounded">Eclipsing Binary</div>
                <div className="bg-accent/10 border border-accent/20 p-2 rounded">Not Transit-Like</div>
              </div>

            </div>
          </div>

          {/* Right Panel: Architecture parameter values */}
          <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4 border border-border">
            <h3 className="font-bold text-sm text-accent border-b border-border pb-2.5 flex items-center gap-2">
              <Info className="h-4.5 w-4.5" /> Architecture Parameters
            </h3>
            
            <div className="flex flex-col gap-4 font-mono text-[10px]">
              <div className="flex justify-between border-b border-border pb-2">
                <span className="text-muted">MODEL TYPE</span>
                <span className="text-ink font-bold">Multi-Modal Late-Fusion 1D CNN</span>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <span className="text-muted">GLOBAL LC DIMENSION</span>
                <span className="text-ink font-bold">2001 bins (Folded phase [-0.5, 0.5])</span>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <span className="text-muted">LOCAL LC DIMENSION</span>
                <span className="text-ink font-bold">201 bins (Folded centered [-3.5dur, 3.5dur])</span>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <span className="text-muted">METADATA DIMENSION</span>
                <span className="text-ink font-bold">28 scaled astrophysical metrics + presence bits</span>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <span className="text-muted">TOTAL MODEL PARAMETERS</span>
                <span className="text-accent font-bold">3,863,844 (~3.86 M weights)</span>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <span className="text-muted">ACTIVATION FUNCTION</span>
                <span className="text-ink font-bold">Rectified Linear Unit (ReLU)</span>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <span className="text-muted">REGULARIZATION</span>
                <span className="text-ink font-bold">Spatial Dropout (0.2) + Fusion Dropout (0.3)</span>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <span className="text-muted">LOSS CRITERION</span>
                <span className="text-ink font-bold">Cross Entropy (Multi-Class Loss)</span>
              </div>
            </div>

            <div className="bg-surface-2 p-4 border border-border rounded-lg text-muted font-sans text-xs leading-relaxed mt-auto">
              <h4 className="font-bold text-ink mb-1.5 font-sans">Why Multi-View?</h4>
              The 1D convolutions on the global view recognize secondary eclipses and out-of-transit variations, while the local view convolves the transit shape to differentiate boxy profiles (planets) from deep V-shapes (binary star systems).
            </div>
          </div>
        </div>
      )}

      {/* Tab CONTENT: TRAINING DATASET & SCALING */}
      {activeTab === 'training' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          {/* Left Panel: Statistics & scaling details */}
          <div className="glass-panel p-5 rounded-xl lg:col-span-2 shadow-xl flex flex-col gap-4 border border-border">
            <h3 className="font-bold text-sm text-accent border-b border-border pb-2.5 flex items-center gap-2">
              <Database className="h-4.5 w-4.5" /> Model Training Dataset & Augmentation Summary
            </h3>
            
            {trainingReportError && (
              <Callout tone="critical" title="No training report available">
                {trainingReportError} No training statistics are shown -- this panel never
                displays fallback numbers.
              </Callout>
            )}

            {trainingReport && (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 my-2">
                  <div className="bg-surface-2/60 p-4 border border-border rounded-lg text-center">
                    <div className="text-muted text-[9px] uppercase tracking-wider">REAL STARS</div>
                    <div className="text-2xl font-bold text-ink mt-1">{trainingReport.num_real_stars}</div>
                    <div className="text-[8px] text-muted mt-1">{trainingReport.train_samples} train samples after augmentation</div>
                  </div>
                  <div className="bg-surface-2/60 p-4 border border-border rounded-lg text-center">
                    <div className="text-muted text-[9px] uppercase tracking-wider">EPOCHS TRAINED</div>
                    <div className="text-2xl font-bold text-accent mt-1">{trainingReport.num_epochs}</div>
                    <div className="text-[8px] text-muted mt-1">Adam Optimizer</div>
                  </div>
                  <div className="bg-surface-2/60 p-4 border border-border rounded-lg text-center">
                    <div className="text-muted text-[9px] uppercase tracking-wider">HELD-OUT ACCURACY</div>
                    <div className="text-2xl font-bold text-status-pass mt-1">
                      {trainingReport.held_out_test_metrics?.accuracy != null
                        ? `${(trainingReport.held_out_test_metrics.accuracy * 100).toFixed(2)}%`
                        : "--"}
                    </div>
                    <div className="text-[8px] text-muted mt-1">
                      On {trainingReport.held_out_test_stars} real stars never trained on
                    </div>
                  </div>
                  <div className="bg-surface-2/60 p-4 border border-border rounded-lg text-center">
                    <div className="text-muted text-[9px] uppercase tracking-wider">TRAIN ACCURACY</div>
                    <div className="text-2xl font-bold text-ink mt-1">
                      {trainingReport.final_train_accuracy != null
                        ? `${(trainingReport.final_train_accuracy * 100).toFixed(2)}%`
                        : "--"}
                    </div>
                    <div className="text-[8px] text-muted mt-1">Not a generalisation estimate</div>
                  </div>
                </div>

                <Callout tone="info" title="Read the held-out number, not the training number">
                  Training accuracy measures fit to data the model already saw. The held-out
                  figure is computed on real stars excluded from training entirely (split at the
                  star level, so augmented copies of a training star can never leak into the test
                  set). Data source: {trainingReport.data_source}
                </Callout>

                {trainingReport.known_gaps && (
                  <Callout tone="warning" title="Known gaps in this training run">
                    {trainingReport.known_gaps}
                  </Callout>
                )}
              </>
            )}

            <h4 className="text-ink font-bold text-xs mt-2 border-b border-border pb-1.5 font-sans">
              Feature Centering & Scaling Configuration
            </h4>
            
            <div className="bg-surface-2 p-4 border border-border rounded-lg flex flex-col gap-3 font-sans text-muted">
              <p>
                To resolve batch normalization instabilities during inference, input parameters are centered and scaled dynamically before being passed to the network layers:
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 font-mono text-[10px]">
                <div className="bg-surface-2/60 p-2.5 border border-border rounded">
                  <span className="text-accent font-bold">1. Light Curve Baseline-Centering</span>
                  <div className="text-muted mt-1">
                    Raw normalized flux values hover around 1.0. We subtract 1.0:
                    <code className="block bg-surface-2 p-1 mt-1 rounded text-ink text-[9px]">flux_centered = flux - 1.0</code>
                    This centers the out-of-transit data at exactly 0.0, stabilizing convolutions.
                  </div>
                </div>

                <div className="bg-surface-2/60 p-2.5 border border-border rounded">
                  <span className="text-accent font-bold">2. Dynamical Parameter Scaling</span>
                  <div className="text-muted mt-1 flex flex-col gap-1 text-[9px]">
                    <div>• Teff Temp Scaling: <code className="text-ink">st_teff / 5778.0</code></div>
                    <div>• Depth Scaling: <code className="text-ink">depth_ppm / 10000.0</code></div>
                    <div>• Radius Scaling: <code className="text-ink">derived_rp_earth / 10.0</code></div>
                    <div>• Parallax Scaling: <code className="text-ink">parallax / 10.0</code></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Panel: Class Distribution details */}
          <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4 border border-border">
            <h3 className="font-bold text-sm text-accent border-b border-border pb-2.5 flex items-center gap-2">
              <Database className="h-4.5 w-4.5" /> Dataset Class Balancer
            </h3>
            
            {trainingReportError && (
              <span className="text-muted font-sans text-xs italic">
                No class distribution shown -- training report unavailable.
              </span>
            )}

            {trainingReport && (
              <div className="flex flex-col gap-4 font-mono text-[10px] my-2">
                {Object.entries(trainingReport.real_star_class_distribution || {}).map(([name, count]) => {
                  const total = trainingReport.num_real_stars || 1;
                  const pct = ((count as number) / total) * 100;
                  const perClass = trainingReport.held_out_test_metrics?.per_class_accuracy?.[name];
                  return (
                    <div key={name} className="flex flex-col gap-1">
                      <div className="flex justify-between text-ink/80">
                        <span>{name}</span>
                        <span className="text-ink font-bold">{count as number} real stars ({pct.toFixed(1)}%)</span>
                      </div>
                      <div className="w-full bg-surface-2 h-2 rounded overflow-hidden border border-border">
                        <div className="bg-accent h-full rounded" style={{ width: `${pct}%` }}></div>
                      </div>
                      <span className="text-muted text-[8px]">
                        Held-out accuracy for this class:{" "}
                        {perClass != null ? `${(perClass * 100).toFixed(1)}%` : "not represented in held-out set"}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="bg-surface-2 p-4 border border-border rounded-lg text-muted font-sans text-xs leading-relaxed mt-auto">
              <h4 className="font-bold text-ink mb-1">What is Augmentation?</h4>
              Each real star&apos;s measured light curve is fixed &mdash; there is only one real
              observation of it. Augmentation therefore varies only the <em>metadata presence
              pattern</em>: optional catalog fields (RUWE, 2MASS/Pan-STARRS photometry, stellar
              parameters) are randomly withheld per sample, so the network learns to handle
              partial catalog coverage rather than assuming every field is always present. The
              light-curve measurement itself is never synthesised or perturbed.
            </div>
          </div>
        </div>
      )}

      {/* Tab CONTENT: LIVE VETTING DIAGNOSTICS */}
      {activeTab === 'predictions' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          {/* Left Panel: Candidates table */}
          <div className="glass-panel p-5 rounded-xl lg:col-span-2 shadow-xl flex flex-col gap-4 border border-border min-h-[480px]">
            <div className="flex justify-between items-center border-b border-border pb-3">
              <h3 className="font-bold text-sm text-accent flex items-center gap-2">
                <Database className="h-4.5 w-4.5" /> Target Candidates List ({candidates.length})
              </h3>
              
              {/* Interactive Telemetry Tuning Parameters */}
              <div className="flex items-center gap-4 text-[9px] border-l border-border pl-4">
                <div className="flex items-center gap-1">
                  <span className="text-muted">NOISE STANDARD:</span>
                  <select 
                    value={noiseStd} 
                    onChange={(e) => setNoiseStd(parseFloat(e.target.value))}
                    className="bg-surface-2 border border-border text-ink rounded p-0.5 focus:outline-none"
                  >
                    <option value="0.0001">100 ppm (Quiet)</option>
                    <option value="0.0005">500 ppm</option>
                    <option value="0.001">1000 ppm</option>
                    <option value="0.002">2000 ppm (TESS standard)</option>
                    <option value="0.004">4000 ppm (High)</option>
                  </select>
                </div>
                
                <div className="flex items-center gap-2">
                  <span className="text-muted">STARSPOTS ACTIVITY:</span>
                  <button 
                    onClick={() => setHasStarspots(!hasStarspots)}
                    className={`px-1.5 py-0.5 rounded font-bold border transition-all ${hasStarspots ? 'bg-accent/10 text-accent border-accent/30' : 'bg-surface-2 text-muted border-border'}`}
                  >
                    {hasStarspots ? "ACTIVE" : "BYPASSED"}
                  </button>
                </div>
              </div>
            </div>

            {isLoadingCand ? (
              <div className="flex-1 flex items-center justify-center text-muted">
                <RefreshCw className="h-6 w-6 animate-spin text-accent mr-2" /> Fetching exoplanet records from SQLite database...
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto max-h-[460px] border border-border/60 rounded-lg">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-surface-2 border-b border-border text-muted uppercase tracking-wider text-[8px]">
                      <th className="p-3">TOI ID</th>
                      <th className="p-3">Candidate Name</th>
                      <th className="p-3">Disposition</th>
                      <th className="p-3">Orbital Period</th>
                      <th className="p-3">Radius (Earth)</th>
                      <th className="p-3">Curation Score</th>
                      <th className="p-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((c, index) => (
                      <tr key={index} className={`border-b border-border/40 hover:bg-surface-2/20 transition-all ${selectedCand?.toi_id === c.toi_id ? 'bg-accent/5' : ''}`}>
                        <td className="p-3 text-ink font-bold">{c.toi_id.toFixed(2)}</td>
                        <td className="p-3">{c.pl_name}</td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded font-bold text-[8px] ${c.disposition === 'CP' ? 'bg-status-pass/10 text-status-pass border border-status-pass/20' : c.disposition === 'FP' ? 'bg-severity-critical/10 text-severity-critical border border-severity-critical/20' : 'bg-accent/10 text-accent border border-accent/20'}`}>
                            {c.disposition === 'CP' ? 'CONFIRMED' : c.disposition === 'FP' ? 'FALSE POSITIVE' : 'CANDIDATE'}
                          </span>
                        </td>
                        <td className="p-3">{c.orbper ? `${c.orbper.toFixed(2)}d` : 'N/A'}</td>
                        <td className="p-3 text-muted">{c.rade ? `${c.rade.toFixed(2)} Re` : 'N/A'}</td>
                        <td className="p-3">
                          <span className="text-muted">{(c.evidence_consistency_score ? c.evidence_consistency_score * 100 : 50).toFixed(0)}%</span>
                        </td>
                        <td className="p-3 text-right">
                          <button
                            onClick={() => runVettingModel(c)}
                            className="bg-surface-2 border border-border hover:border-accent/50 hover:bg-accent/10 text-accent px-3 py-1 rounded transition-all flex items-center gap-1 inline-flex text-[9px] font-bold"
                          >
                            <Cpu className="h-3 w-3" /> VET TARGET
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Right Panel: Diagnostic Results Card */}
          <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4 border border-border">
            <h3 className="font-bold text-sm text-accent border-b border-border pb-2.5 flex items-center gap-2">
              <Eye className="h-4.5 w-4.5" /> Neural Net Activation Output
            </h3>
            
            {isLoadingDl ? (
              <div className="flex-1 flex flex-col items-center justify-center text-muted gap-2">
                <RefreshCw className="h-8 w-8 animate-spin text-accent" />
                <span className="text-[10px]">Convolving folded views...</span>
                <span className="text-[8px] text-muted">Running DeepExoFusionNet on backend</span>
              </div>
            ) : selectedCand ? (
              dlResult ? (
                <div className="flex-1 flex flex-col gap-4">
                  {/* Selected Info */}
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

                  {/* UPGRADE_PLAN.md C.2 / LIMITATIONS.md #7: dl_model_status must be
                      surfaced next to the classification, never buried -- an
                      "untrained_fallback" checkpoint means the verdict below is random
                      noise, not a prediction. */}
                  {dlResult.dl_model_status === "untrained_fallback" && (
                    <div className="bg-severity-critical/10 border border-severity-critical/30 p-2.5 rounded-lg text-severity-critical text-[9px] font-sans leading-normal flex items-start gap-1.5">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                      <span><strong>Untrained fallback network.</strong> The trained checkpoint failed to load, so this run used random, untrained weights. The verdict and confidence below are noise, not a prediction.</span>
                    </div>
                  )}

                  {/* Vetting Verdict Badge */}
                  <div className="bg-surface-2 p-4 border border-border rounded-lg flex flex-col gap-2 relative">
                    <span className="text-muted text-[8px] uppercase tracking-wider">Classification Verdict</span>
                    <div className="flex items-center justify-between">
                      <span className="text-ink font-extrabold text-sm font-sans tracking-wide">
                        {bestClass.toUpperCase()}
                      </span>
                      <span className={`px-2 py-0.5 rounded font-extrabold text-[9px] ${
                        bestClass.includes('Planet') ? 'bg-status-pass/10 text-status-pass border border-status-pass/30' :
                        bestClass.includes('Binary') ? 'bg-accent/10 text-accent border border-accent/30' :
                        bestClass.includes('Activity') ? 'bg-accent/10 text-accent border border-accent/30' :
                        'bg-severity-critical/10 text-severity-critical border border-severity-critical/30'
                      }`}>
                        {(confidence * 100).toFixed(2)}% CONF
                      </span>
                    </div>
                  </div>

                  {/* Probability Chart */}
                  <div className="flex flex-col gap-3 font-mono text-[9px]">
                    <span className="text-muted uppercase tracking-widest text-[8px] font-bold">Probability Distribution</span>
                    {Object.entries(dlResult.dl_classification).map(([cls, prob]: any, idx) => (
                      <div key={idx} className="flex flex-col gap-1">
                        <div className="flex justify-between text-ink/80">
                          <span>{cls}</span>
                          <span className={`${
                            cls.includes('Planet') ? 'text-status-pass' : 
                            cls.includes('Binary') ? 'text-accent' : 
                            cls.includes('Activity') ? 'text-accent' : 
                            'text-severity-critical'
                          } font-bold`}>{(prob * 100).toFixed(2)}%</span>
                        </div>
                        <div className="w-full bg-surface-2 h-2 rounded overflow-hidden border border-border/60">
                          <div 
                            className={`h-full rounded transition-all duration-500 ${
                              cls.includes('Planet') ? 'bg-status-pass' : 
                              cls.includes('Binary') ? 'bg-accent' : 
                              cls.includes('Activity') ? 'bg-accent' : 
                              'bg-severity-critical'
                            }`}
                            style={{ width: `${prob * 100}%` }}
                          ></div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {(() => {
                    const isFP = selectedCand.disposition === "FP";
                    const isOversized = selectedCand.rade && selectedCand.rade > 20.0;
                    const hasConflict = (isFP || isOversized) && bestClass.includes("Planet");

                    if (hasConflict) {
                      return (
                        <div className="bg-severity-high/10 border border-severity-high/30 rounded p-2.5 text-severity-high text-[8.5px] flex gap-1.5 mt-auto leading-normal">
                          <AlertCircle className="h-3.5 w-3.5 text-severity-high shrink-0 mt-0.5" />
                          <span>
                            <strong>Physics Override:</strong> Heuristic parameters or physical size ({selectedCand.rade?.toFixed(1)} Re) classify this as a False Positive, overriding the CNN's shape-based "Planet Transit" verdict.
                          </span>
                        </div>
                      );
                    }
                    return (
                      <div className="bg-surface-2/60 border border-border/60 rounded p-2 text-muted text-[8px] flex gap-1.5 mt-auto leading-normal">
                        <Check className="h-3 w-3 text-status-pass shrink-0 mt-0.5" />
                        <span>
                          Verifying with Centered Convolution: The global baseline is centered at 0.0 and dynamic metadata features are scaled to stabilize batch norms.
                        </span>
                      </div>
                    );
                  })()}
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-muted text-center gap-1.5">
                  <AlertCircle className="h-7 w-7 text-muted" />
                  <span>Vetting Execution Failed</span>
                  <span className="text-[9px] text-muted">Model could not complete calculations</span>
                </div>
              )
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-muted text-center gap-1">
                <HelpCircle className="h-8 w-8 text-muted" />
                <span>No Target Selected</span>
                <span className="text-[9px] text-muted">Click "Vet Target" to execute late-fusion predictions</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Primary summary analytics card for overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        
        {/* TOTAL DB CANDIDATES */}
        <div className="glass-panel p-5 rounded-xl flex flex-col gap-1 border border-border shadow-lg">
          <span className="text-muted text-[9px] font-bold uppercase tracking-wider">DATABASE CANDIDATES</span>
          <span className="text-2xl font-extrabold text-ink tracking-tight">
            {isLoadingCand ? <span className="text-muted text-base">Loading&hellip;</span> : totalCount}
          </span>
          <span className="text-muted text-[8px] mt-1">Successfully aggregated across TIC and catalog records.</span>
        </div>

        {/* POTENTIAL PLANETS */}
        <div className="glass-panel p-5 rounded-xl flex flex-col gap-1 border border-border shadow-lg">
          <span className="text-muted text-[9px] font-bold uppercase tracking-wider">POTENTIAL PLANETS (SIZE VETTED)</span>
          <span className="text-2xl font-extrabold text-status-pass tracking-tight">
            {isLoadingCand ? <span className="text-muted text-base">Loading&hellip;</span> : potentialPlanets.length}
          </span>
          <span className="text-muted text-[8px] mt-1">Candidates with physically plausible sizes ($R_p &lt; 20 R_E$).</span>
        </div>

        {/* POTENTIAL ECLIPSING BINARIES */}
        <div className="glass-panel p-5 rounded-xl flex flex-col gap-1 border border-border shadow-lg">
          <span className="text-muted text-[9px] font-bold uppercase tracking-wider">POTENTIAL ECLIPSING BINARIES</span>
          <span className="text-2xl font-extrabold text-accent tracking-tight">
            {isLoadingCand ? <span className="text-muted text-base">Loading&hellip;</span> : potentialEBs.length}
          </span>
          <span className="text-muted text-[8px] mt-1">Candidates flagged as False Positive or too large ($R_p \ge 20 R_E$).</span>
        </div>

      </div>

    </div>
  );
}
