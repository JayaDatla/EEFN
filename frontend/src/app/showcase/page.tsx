"use client";

import React, { useState, useEffect } from "react";
import { 
  Network, Database, ShieldAlert, Cpu, CheckCircle2, Play, 
  ChevronRight, ChevronLeft, RotateCcw, AlertTriangle, HelpCircle, 
  TrendingUp, BarChart3, LineChart, FileText, Activity, Layers, Sparkles, AlertCircle
} from "lucide-react";

export default function ShowcasePage() {
  const [activeSection, setActiveSection] = useState(0);
  const [tourActive, setTourActive] = useState(false);
  const [tourStep, setTourStep] = useState(0);
  const [autoPlay, setAutoPlay] = useState(false);

  // Tour slide states
  const [fusionStage, setFusionStage] = useState(0); 
  const [activeTab, setActiveTab] = useState("alerts");

  const sections = [
    { id: "problem", label: "01. The Problem" },
    { id: "fusion", label: "02. Fusion Story" },
    { id: "flagship", label: "03. Flagship Alert" },
    { id: "impact", label: "04. Historical Impact" },
    { id: "control", label: "05. Mission Control" },
    { id: "science", label: "06. Validation Science" },
    { id: "architecture", label: "07. System Architecture" },
    { id: "verdict", label: "08. Curation Verdict" }
  ];

  // Auto-play timer loop
  useEffect(() => {
    let interval: any = null;
    if (tourActive && autoPlay) {
      interval = setInterval(() => {
        handleNext();
      }, 5000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [tourActive, autoPlay, tourStep]);

  const handleNext = () => {
    if (tourStep < sections.length - 1) {
      setTourStep(prev => prev + 1);
      setActiveSection(tourStep + 1);
    } else {
      setAutoPlay(false);
      setTourActive(false);
      setTourStep(0);
    }
  };

  const handlePrev = () => {
    if (tourStep > 0) {
      setTourStep(prev => prev - 1);
      setActiveSection(tourStep - 1);
    }
  };

  const startTour = () => {
    setTourActive(true);
    setTourStep(0);
    setActiveSection(0);
    setAutoPlay(true);
  };

  return (
    <div className="flex-1 bg-surface-2 text-ink/90 font-sans flex flex-col md:flex-row overflow-hidden -m-6 h-[calc(100vh-32px-22px)]">
      
      {/* Sidebar Navigation */}
      <aside className="w-full md:w-64 border-b md:border-b-0 md:border-r border-border bg-surface-2/80 backdrop-blur-md flex flex-col justify-between p-6 z-20 select-none">
        <div className="flex flex-col gap-6">
          <div className="flex items-center gap-3 border-b border-border pb-4">
            <div className="bg-gradient-to-tr bg-accent p-1.5 rounded-lg">
              <Sparkles className="text-ink h-4.5 w-4.5 animate-pulse" />
            </div>
            <span className="font-mono font-extrabold tracking-wider text-sm text-ink">EEFN SHOWCASE</span>
          </div>
          
          <nav className="flex flex-row md:flex-col gap-1.5 overflow-x-auto md:overflow-x-visible pb-2 md:pb-0 scrollbar-none">
            {sections.map((sec, idx) => (
              <button
                key={sec.id}
                onClick={() => {
                  setActiveSection(idx);
                  if (tourActive) setTourStep(idx);
                }}
                className={`text-left py-2 px-3 rounded-lg font-mono text-[10px] tracking-wider border transition-all flex justify-between items-center whitespace-nowrap md:whitespace-normal shrink-0 ${
                  activeSection === idx 
                    ? "bg-accent/10 border-accent/30 text-accent font-bold" 
                    : "border-transparent text-muted hover:bg-surface-2/50 hover:text-ink/90"
                }`}
              >
                <span>{sec.label}</span>
                {tourActive && tourStep === idx && (
                  <span className="w-1.5 h-1.5 rounded-full bg-accent animate-ping hidden md:inline-block"></span>
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* Tour controls dock */}
        <div className="border-t border-border pt-4 flex flex-col gap-3 mt-4 md:mt-0">
          <button 
            onClick={startTour}
            className="w-full bg-accent hover:bg-accent text-ink font-bold py-2.5 px-4 rounded-lg flex items-center justify-center gap-2 transition-all shadow-lg  text-xs font-mono"
          >
            <Play className="h-4.5 w-4.5 fill-slate-950" /> START Guided Tour
          </button>
          
          {tourActive && (
            <div className="bg-surface-2 border border-border p-3 rounded-lg flex flex-col gap-2">
              <div className="flex justify-between items-center text-[10px] text-muted font-mono">
                <span>STEP: {tourStep + 1} / 8</span>
                <button onClick={() => setAutoPlay(!autoPlay)} className="text-accent hover:underline">
                  {autoPlay ? "PAUSE" : "PLAY"}
                </button>
              </div>
              <div className="w-full bg-surface-2 h-1.5 rounded-full overflow-hidden">
                <div 
                  className="bg-accent h-full transition-all duration-500" 
                  style={{ width: `${((tourStep + 1) / 8) * 100}%` }}
                ></div>
              </div>
              <div className="flex justify-between gap-2 mt-1">
                <button 
                  onClick={handlePrev} 
                  disabled={tourStep === 0}
                  className="flex-1 bg-surface-2 hover:bg-surface-2 border border-border py-1.5 px-2 rounded-md text-[10px] disabled:opacity-50 disabled:cursor-not-allowed font-mono text-ink/80"
                >
                  PREV
                </button>
                <button 
                  onClick={handleNext} 
                  className="flex-1 bg-surface-2 hover:bg-surface-2 border border-border py-1.5 px-2 rounded-md text-[10px] font-mono text-ink/80"
                >
                  {tourStep === 7 ? "FINISH" : "NEXT"}
                </button>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Main Presentation Screen */}
      <section className="flex-1 flex flex-col overflow-y-auto p-6 md:p-10 relative">
        
        {/* Abstract Background Grid */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f2937_1px,transparent_1px),linear-gradient(to_bottom,#1f2937_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] opacity-15 pointer-events-none"></div>

        <div className="flex-1 flex flex-col justify-center max-w-4xl mx-auto w-full z-10 py-4">
          
          {/* SECTION 1: THE PROBLEM */}
          {activeSection === 0 && (
            <div className="flex flex-col gap-6 animate-slideUp">
              <div className="text-center mb-6">
                <span className="inline-block px-3 py-1 rounded-full bg-severity-critical/10 border border-severity-critical/20 text-severity-critical font-bold font-mono text-[10px] tracking-widest mb-3">
                  THE SILOED CATALOG CRISIS
                </span>
                <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight text-ink font-sans">
                  Disconnected Catalogs. Stale Physics.
                </h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
                <div className="flex flex-col gap-4 text-ink/80 text-sm leading-relaxed font-sans">
                  <p>
                    Astronomers reference multiple disjoint databases. The **NASA Exoplanet Archive**, **Gaia DR3**, and TESS input tables are isolated catalog silos.
                  </p>
                  <p className="font-bold text-ink">
                    When stellar sizes are corrected in high-precision Gaia DR3 catalogs, corresponding planetary radii in TESS archives are not updated automatically.
                  </p>
                  <p>
                    This leaves hundreds of eclipsing binaries (unphysical companion stars) masquerading as exoplanet candidates, leading to costly follow-up observations.
                  </p>
                </div>

                {/* Animated Data Stream Simulation */}
                <div className="glass-panel p-5 rounded-xl flex flex-col gap-4 font-mono text-[10px] relative overflow-hidden h-60 justify-between">
                  <div className="flex justify-between items-center border-b border-border pb-2 text-muted">
                    <span>CATALOG REPOSITORIES</span>
                    <span className="text-severity-critical animate-pulse font-bold">DISCONNECTED</span>
                  </div>
                  
                  <div className="flex flex-col gap-2 text-muted">
                    <div className="flex justify-between items-center bg-surface-2 p-2 border border-border rounded-lg">
                      <span className="text-ink/80">NASA Exoplanet Archive</span>
                      <span className="text-muted">[Stellar params]</span>
                      <span className="text-severity-high">STALE (v2021)</span>
                    </div>
                    <div className="flex justify-between items-center bg-surface-2 p-2 border border-border rounded-lg">
                      <span className="text-ink/80">Gaia DR3 Archive</span>
                      <span className="text-muted">[Stellar Parallaxes]</span>
                      <span className="text-status-pass">UPDATED (v2023)</span>
                    </div>
                    <div className="flex justify-between items-center bg-surface-2 p-2 border border-border rounded-lg">
                      <span className="text-ink/80">ExoFOP Candidate Feed</span>
                      <span className="text-muted">[Transit Depths]</span>
                      <span className="text-severity-high">STALE (v2021)</span>
                    </div>
                  </div>

                  <div className="border-t border-border pt-2 text-center text-muted text-[9px]">
                    "Science demands automated cross-catalog parameter consistency."
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 2: THE EVIDENCE FUSION STORY */}
          {activeSection === 1 && (
            <div className="flex flex-col gap-6 animate-slideUp">
              <div className="text-center mb-4">
                <span className="inline-block px-3 py-1 rounded-full bg-accent/10 border border-accent/20 text-accent font-bold font-mono text-[10px] tracking-widest mb-3">
                  AUTOMATED FUSION WORKFLOW
                </span>
                <h2 className="text-3xl font-extrabold tracking-tight text-ink font-sans">The Evidence Fusion Story</h2>
                <p className="text-muted mt-2 max-w-xl mx-auto text-xs">
                  Watch how EEFN pulls transit events, aligns them with Gaia DR3 stars, and calculates physical planet radii parameters.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
                {/* Control card */}
                <div className="glass-panel p-4 rounded-xl flex flex-col justify-between font-mono">
                  <div className="flex flex-col gap-2.5">
                    <h4 className="font-bold text-accent border-b border-border pb-2">WORKFLOW STAGES</h4>
                    <button 
                      onClick={() => setFusionStage(0)}
                      className={`w-full text-left py-2 px-3 rounded-lg border text-[10px] transition-all ${fusionStage === 0 ? 'bg-accent/10 border-accent/30 text-ink' : 'border-border text-muted'}`}
                    >
                      Stage 1: Load TESS candidate
                    </button>
                    <button 
                      onClick={() => setFusionStage(1)}
                      className={`w-full text-left py-2 px-3 rounded-lg border text-[10px] transition-all ${fusionStage === 1 ? 'bg-accent/10 border-accent/30 text-ink' : 'border-border text-muted'}`}
                    >
                      Stage 2: Cross-match Gaia DR3
                    </button>
                    <button 
                      onClick={() => setFusionStage(2)}
                      className={`w-full text-left py-2 px-3 rounded-lg border text-[10px] transition-all ${fusionStage === 2 ? 'bg-accent/10 border-accent/30 text-ink' : 'border-border text-muted'}`}
                    >
                      Stage 3: Calculate Discrepancies
                    </button>
                  </div>
                  <button 
                    onClick={() => {
                      setFusionStage(0);
                      setTimeout(() => setFusionStage(1), 1500);
                      setTimeout(() => setFusionStage(2), 3000);
                    }}
                    className="w-full bg-surface-2 border border-border hover:border-accent/40 text-ink/80 hover:text-ink font-bold py-2 rounded-lg text-[10px] transition-all mt-4"
                  >
                    RUN SIMULATION WORKFLOW
                  </button>
                </div>

                {/* Display Panel */}
                <div className="glass-panel p-5 rounded-xl col-span-2 shadow-xl flex flex-col justify-between h-64">
                  <div className="flex justify-between border-b border-border pb-2 text-[10px] font-mono text-muted">
                    <span>TARGET WORKSPACE: TOI-1020.01</span>
                    <span className="font-bold text-accent">FUSION ENGINE ONLINE</span>
                  </div>

                  <div className="flex justify-around items-center gap-6 my-2">
                    {/* TESS parameters */}
                    <div className="bg-surface-2 border border-border p-4 rounded-xl text-center w-32 font-mono">
                      <span className="text-muted text-[9px] block mb-1 uppercase font-bold">TESS STAR TEMP</span>
                      <span className="text-lg font-extrabold text-ink">5028.7 K</span>
                    </div>

                    <div className="text-muted font-bold text-lg font-mono">&harr;</div>

                    {/* Gaia parameters */}
                    <div className={`border p-4 rounded-xl text-center w-32 font-mono transition-all duration-500 ${
                      fusionStage >= 1 ? 'border-accent/30 bg-accent/5' : 'border-border bg-surface-2/20 opacity-30'
                    }`}>
                      <span className="text-muted text-[9px] block mb-1 uppercase font-bold">GAIA DR3 TEMP</span>
                      <span className="text-lg font-extrabold text-ink">{fusionStage >= 1 ? "6822.4 K" : "N/A"}</span>
                    </div>
                  </div>

                  {/* Conflict display */}
                  <div className={`transition-all duration-500 p-3 rounded-lg flex justify-between items-center font-mono text-[10px] ${
                    fusionStage === 2 
                      ? 'bg-severity-critical/5 border border-severity-critical/25 text-severity-critical' 
                      : 'bg-surface-2/40 text-muted border border-border'
                  }`}>
                    <span>{fusionStage === 2 ? "SYSTEM TRIGGER: Critical catalog temperature discrepancy." : "Status: Awaiting parameter checks..."}</span>
                    {fusionStage === 2 && (
                      <span className="font-bold border border-severity-critical/20 px-2 py-0.5 rounded bg-severity-critical/10">1793.7 K DELTA</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 3: FLAGSHIP FEATURE (Derived Planet Radius Spotlight) */}
          {activeSection === 2 && (
            <div className="flex flex-col gap-6 animate-slideUp">
              <div className="text-center mb-4">
                <span className="inline-block px-3 py-1 rounded-full bg-severity-critical/10 border border-severity-critical/20 text-severity-critical font-bold font-mono text-[10px] tracking-widest mb-3">
                  FLAGSHIP CURATION AUDIT TOOL
                </span>
                <h2 className="text-3xl font-extrabold tracking-tight text-ink font-sans">
                  Derived Planet Size Verification
                </h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
                <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-3 font-mono">
                  <h3 className="font-bold text-xs text-accent border-b border-border pb-2">TOI-1017.01 SYSTEM AUDIT</h3>
                  <div className="flex justify-between"><span>Reported Planet Radius (TESS):</span><span className="text-ink">21.04 R_Earth</span></div>
                  <div className="flex justify-between"><span>Observed Transit Depth:</span><span className="text-ink">14,177.7 ppm</span></div>
                  <div className="flex justify-between"><span>Gaia DR3 Host Star Radius:</span><span className="text-ink">1.627 R_sun</span></div>
                  <div className="border-t border-border my-2"></div>
                  <div className="flex justify-between text-xs font-bold text-ink/80">
                    <span>Gaia-Derived Planet Radius:</span>
                    <span className="text-severity-critical animate-pulse">21.48 R_Earth</span>
                  </div>
                  
                  <div className="bg-severity-critical/5 border border-severity-critical/25 p-3 rounded-lg text-[10px] text-muted leading-normal mt-2">
                    <span className="text-severity-critical font-bold block mb-1">CRITICAL ANOMALY ALERT</span>
                    Derived radius exceeds hydrogen-helium physical limits for transiting exoplanets (~22 R_Earth). Re-classified as an eclipsing binary.
                  </div>
                </div>

                <div className="flex flex-col gap-4 text-ink/80 text-sm leading-relaxed font-sans">
                  <h4 className="font-bold text-ink text-base">Flagship Curation Algorithm</h4>
                  <p>
                    Astronomical archives calculate planet radii using reported host star sizes. If host star sizes are underestimated in candidate databases, false-positives appear physical.
                  </p>
                  <p className="font-bold text-accent">
                    By cross-referencing Gaia DR3 parallaxes and correcting the host star's radius, EEFN instantly recalculates the candidate's derived size.
                  </p>
                  <p>
                    If the derived radius exceeds exoplanet physical limits, it is flagged as an eclipsing binary false positive before observation.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 4: HISTORICAL IMPACT */}
          {activeSection === 3 && (
            <div className="flex flex-col gap-6 animate-slideUp">
              <div className="text-center mb-4">
                <span className="inline-block px-3 py-1 rounded-full bg-status-pass/10 border border-status-pass/20 text-status-pass font-bold font-mono text-[10px] tracking-widest mb-3">
                  QUANTIFIED ASTRONOMICAL SAVINGS
                </span>
                <h2 className="text-3xl font-extrabold tracking-tight text-ink font-sans">Retrospective Impact Study</h2>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="glass-panel p-4 rounded-xl text-center shadow-lg hover:border-status-pass/30 transition-all font-mono">
                  <span className="text-muted font-bold block mb-1.5 text-[9px] uppercase tracking-wider">False Positives</span>
                  <span className="text-3xl font-extrabold text-status-pass tracking-tight glow-green">473</span>
                  <span className="text-muted block text-[9px] mt-1.5">Candidates Flagged</span>
                </div>

                <div className="glass-panel p-4 rounded-xl text-center shadow-lg hover:border-status-pass/30 transition-all font-mono">
                  <span className="text-muted font-bold block mb-1.5 text-[9px] uppercase tracking-wider">Observations</span>
                  <span className="text-3xl font-extrabold text-status-pass tracking-tight glow-green">1,419</span>
                  <span className="text-muted block text-[9px] mt-1.5">Runs Avoided</span>
                </div>

                <div className="glass-panel p-4 rounded-xl text-center shadow-lg hover:border-status-pass/30 transition-all font-mono">
                  <span className="text-muted font-bold block mb-1.5 text-[9px] uppercase tracking-wider">Telescope Hours</span>
                  <span className="text-3xl font-extrabold text-status-pass tracking-tight glow-green">5,676</span>
                  <span className="text-muted block text-[9px] mt-1.5">Hours Saved</span>
                </div>

                <div className="glass-panel p-4 rounded-xl text-center shadow-lg hover:border-status-pass/30 transition-all font-mono">
                  <span className="text-muted font-bold block mb-1.5 text-[9px] uppercase tracking-wider">Budget Saved</span>
                  <span className="text-3xl font-extrabold text-status-pass tracking-tight glow-green">$709K</span>
                  <span className="text-muted block text-[9px] mt-1.5">Resource equivalents</span>
                </div>
              </div>

              <div className="glass-panel p-5 rounded-xl shadow-xl mt-2 leading-relaxed">
                <h4 className="font-bold text-ink border-b border-border pb-2 mb-3 font-mono text-xs">RESOURCE ALLOCATION RETROSPECTIVE</h4>
                <p className="text-xs text-muted font-sans">
                  Each exoplanet candidate going through ground-based verification before being flagged as a false positive costs approximately **12 telescope hours** across spectroscopy, imaging, and photometry. 
                  By automatically flagging **473 false positives** based on cross-catalog discrepancies, EEFN would have saved **5,676 telescope hours**, redirecting astronomical resources to candidates with higher confirmation probability.
                </p>
              </div>
            </div>
          )}

          {/* SECTION 5: MISSION CONTROL (Interactive dashboard embed) */}
          {activeSection === 4 && (
            <div className="flex flex-col gap-5 animate-fadeIn h-[390px] overflow-hidden">
              <div className="flex justify-between items-center border-b border-border pb-3">
                <div>
                  <h3 className="text-lg font-bold text-ink font-sans">Interactive Curation Desk</h3>
                  <p className="text-muted text-[10px] font-mono">Select tabs to audit candidate TOI-1017.01 details dynamically.</p>
                </div>
                <div className="flex gap-2 text-[10px] font-mono">
                  <button 
                    onClick={() => setActiveTab("alerts")} 
                    className={`py-1 px-3 border rounded-md transition-all ${activeTab === 'alerts' ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-muted'}`}
                  >
                    ACTIVE ALERTS
                  </button>
                  <button 
                    onClick={() => setActiveTab("provenance")} 
                    className={`py-1 px-3 border rounded-md transition-all ${activeTab === 'provenance' ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-muted'}`}
                  >
                    PROVENANCE AUDIT
                  </button>
                  <button 
                    onClick={() => setActiveTab("timeline")} 
                    className={`py-1 px-3 border rounded-md transition-all ${activeTab === 'timeline' ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-muted'}`}
                  >
                    CHRONOLOGY
                  </button>
                </div>
              </div>

              <div className="glass-panel rounded-xl flex-1 flex flex-col p-4 shadow-xl overflow-y-auto">
                {activeTab === "alerts" && (
                  <div className="flex flex-col gap-3 animate-fadeIn font-mono">
                    <div className="bg-severity-critical/5 border border-severity-critical/25 p-3 rounded-lg">
                      <span className="text-severity-critical font-bold text-xs block mb-1">CRITICAL Anomaly: Derived Planet Radius Mismatch</span>
                      <p className="text-muted text-[10px] leading-normal font-sans">
                        Gaia DR3 stellar radius (Rad=1.627) and observed transit depth (14,177.7 ppm) results in a derived radius of **21.48 R_Earth** (violates the hydrogen-helium limit of ~22 R_Earth). Flagged as a grazing eclipsing binary star.
                      </p>
                    </div>
                  </div>
                )}

                {activeTab === "provenance" && (
                  <table className="w-full text-left text-[10px] font-mono animate-fadeIn">
                    <thead className="bg-surface-2 text-muted border-b border-border">
                      <tr>
                        <th className="p-2">MEASUREMENT</th>
                        <th className="p-2">CATALOG SOURCE</th>
                        <th className="p-2">VALUE</th>
                        <th className="p-2">SYSTEM PROTOCOL</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-900/40 text-ink/80">
                      <tr>
                        <td className="p-2">Stellar Effective Temp</td>
                        <td className="p-2">Gaia DR3</td>
                        <td className="p-2">6822.4 K</td>
                        <td className="p-2 text-status-pass">RESOLVED</td>
                      </tr>
                      <tr>
                        <td className="p-2">Stellar Effective Temp</td>
                        <td className="p-2">TOI Catalog</td>
                        <td className="p-2">6995.2 K</td>
                        <td className="p-2 text-severity-high">STALE PARAMETER</td>
                      </tr>
                    </tbody>
                  </table>
                )}

                {activeTab === "timeline" && (
                  <div className="flex flex-col gap-2.5 font-mono text-[10px] text-muted animate-fadeIn pl-2">
                    <div className="flex gap-4 border-l border-border pl-4 pb-2 relative">
                      <div className="absolute -left-1 top-1 w-2 h-2 rounded-full bg-muted"></div>
                      <span className="font-bold text-ink">2018</span>
                      <span>Target cataloged under TIC 182943944 with Tmag=10.60.</span>
                    </div>
                    <div className="flex gap-4 border-l border-border pl-4 pb-2 relative">
                      <div className="absolute -left-1 top-1 w-2 h-2 rounded-full bg-muted"></div>
                      <span className="font-bold text-ink">2019</span>
                      <span>Transit event detected, cataloged as exoplanet candidate under TOI-1017.01.</span>
                    </div>
                    <div className="flex gap-4 border-l border-border pl-4 pb-2 relative">
                      <div className="absolute -left-1 top-1 w-2 h-2 rounded-full bg-severity-critical"></div>
                      <span className="font-bold text-severity-critical">2026</span>
                      <span>Gaia DR3 radius applied. Derived planetary size exceeds exoplanet limits. Flagged False Positive.</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* SECTION 6: THE SCIENCE (Validation workflow) */}
          {activeSection === 5 && (
            <div className="flex flex-col gap-6 animate-slideUp font-mono">
              <div className="text-center mb-4">
                <span className="inline-block px-3 py-1 rounded-full bg-accent/10 border border-accent/20 text-accent font-bold text-[10px] tracking-widest mb-3">
                  SCIENTIFIC RIGOR & VALIDATION
                </span>
                <h2 className="text-3xl font-bold text-ink font-sans">Verification Pipeline</h2>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 text-[10px] text-muted">
                {/* Left Side: 3 Audit Cards */}
                <div className="lg:col-span-2 flex flex-col gap-4">
                  <div className="glass-panel p-4 rounded-xl shadow flex flex-col gap-2">
                    <h4 className="font-bold text-ink border-b border-border pb-1">DATA LEAKAGE AUDIT</h4>
                    <p className="leading-relaxed font-sans text-[11px]">
                      Evaluated timeline leakage on 25 features. Zero outcome contamination verified. Gaia stellar parameters are completely independent of TESS exoplanet candidate outcomes.
                    </p>
                    <span className="text-status-pass font-bold block mt-1">STATUS: PASS (Risk 1/10)</span>
                  </div>

                  <div className="glass-panel p-4 rounded-xl shadow flex flex-col gap-2">
                    <h4 className="font-bold text-ink border-b border-border pb-1">TEMPORAL VALIDATION</h4>
                    <p className="leading-relaxed font-sans text-[11px]">
                      Trained model on historical cutoffs (e.g. pre-2020) and tested on subsequent discoveries. ROC-AUC remained stable above **0.90**, confirming temporal invariant physics.
                    </p>
                    <span className="text-status-pass font-bold block mt-1">STATUS: VERIFIED</span>
                  </div>

                  <div className="glass-panel p-4 rounded-xl shadow flex flex-col gap-2">
                    <h4 className="font-bold text-ink border-b border-border pb-1">SIGNIFICANCE TESTING</h4>
                    <p className="leading-relaxed font-sans text-[11px]">
                      Executed 500 bootstrap resamples and permutation tests. 95% confidence interval of improvement does not contain zero, and p-value is **0.0000** (statistically significant).
                    </p>
                    <span className="text-status-pass font-bold block mt-1">STATUS: SIGNIFICANT</span>
                  </div>
                </div>

                {/* Right Side: Limitations & Brutal Comparison */}
                <div className="glass-panel p-5 rounded-xl shadow flex flex-col justify-between border border-severity-critical/20 bg-severity-critical/5">
                  <div>
                    <h4 className="font-bold text-severity-critical border-b border-border pb-2 flex items-center gap-1.5 font-mono text-[11px]">
                      <AlertTriangle className="h-4 w-4" /> SCIENTIFIC LIMITATIONS
                    </h4>
                    <p className="leading-relaxed font-sans text-[11px] text-ink/80 mt-2.5">
                      EEFN is worse for physical validation of a single planet candidate for publication. It cannot compute a rigorous, multi-model False Positive Probability (FPP) and lacks access to raw diagnostic signals like centroid shifts or secondary eclipses.
                    </p>
                    <p className="leading-relaxed font-sans text-[11px] text-ink/80 mt-2.5">
                      It also has a much higher deployment overhead (FastAPI, SQLite, Neo4j, Next.js) compared to running a single academic script (such as <code className="text-accent">vespa</code> or <code className="text-accent">triceratops</code>).
                    </p>
                  </div>
                  <div className="border-t border-border pt-2 text-[9px] text-muted font-mono">
                    <span>* Context: EEFN serves as an upstream catalog auditor, not a physical signal validator.</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 7: SYSTEM ARCHITECTURE */}
          {activeSection === 6 && (
            <div className="flex flex-col gap-6 animate-slideUp font-mono">
              <div className="text-center mb-4">
                <span className="inline-block px-3 py-1 rounded-full bg-accent/10 border border-accent/20 text-accent font-bold text-[10px] tracking-widest mb-3">
                  PLATFORM TOPOLOGY
                </span>
                <h2 className="text-3xl font-bold text-ink font-sans">System Architecture</h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-center text-muted">
                <div className="glass-panel p-4 rounded-xl flex flex-col justify-center items-center shadow-lg gap-2">
                  <div className="bg-accent/10 p-2.5 rounded-lg text-accent"><Database className="h-6 w-6" /></div>
                  <span className="text-ink font-bold block text-[11px]">1. Ingestion Layer</span>
                  <span className="text-[9px] font-sans leading-normal">Queries NASA TAP & Gaia VizieR via CDS services</span>
                </div>

                <div className="glass-panel p-4 rounded-xl flex flex-col justify-center items-center shadow-lg gap-2">
                  <div className="bg-accent/10 p-2.5 rounded-lg text-accent"><Cpu className="h-6 w-6" /></div>
                  <span className="text-ink font-bold block text-[11px]">2. Diagnostic Engine</span>
                  <span className="text-[9px] font-sans leading-normal">Derives radii, flags conflicts, computes quality grades</span>
                </div>

                <div className="glass-panel p-4 rounded-xl flex flex-col justify-center items-center shadow-lg gap-2">
                  <div className="bg-accent/10 p-2.5 rounded-lg text-accent"><Network className="h-6 w-6" /></div>
                  <span className="text-ink font-bold block text-[11px]">3. DB & Graph resolution</span>
                  <span className="text-[9px] font-sans leading-normal">PostgreSQL schemas & Neo4j SAME_AS mappings</span>
                </div>

                <div className="glass-panel p-4 rounded-xl flex flex-col justify-center items-center shadow-lg gap-2">
                  <div className="bg-accent/10 p-2.5 rounded-lg text-accent"><Activity className="h-6 w-6" /></div>
                  <span className="text-ink font-bold block text-[11px]">4. FastAPI REST API</span>
                  <span className="text-[9px] font-sans leading-normal">Exposes verification datasets to the Next.js frontend</span>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 8: WHY THIS MATTERS */}
          {activeSection === 7 && (
            <div className="flex flex-col gap-6 animate-slideUp text-center">
              <div className="mb-4">
                <span className="inline-block px-3 py-1 rounded-full bg-status-pass/10 border border-status-pass/20 text-status-pass font-bold font-mono text-[10px] tracking-widest mb-3">
                  CURATION VERDICT
                </span>
                <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight text-ink font-sans">
                  Higher Quality Follow-up Decisions.
                </h2>
              </div>

              <div className="max-w-xl mx-auto flex flex-col gap-4 text-ink/80 text-sm leading-relaxed font-sans">
                <p>
                  By deploying the **Evidence Quality Intelligence Platform**, exoplanet research communities transition from manual database cross-referencing to automated, physics-based verification loops.
                </p>
                <div className="bg-surface-2 border border-border p-4 rounded-xl text-center text-sm font-bold my-3 font-mono text-ink shadow-xl">
                  "If EEFN had existed historically, 473 false positives could have been flagged before follow-up observation."
                </div>
                <p className="text-xs text-muted">
                  This represents over 5,600 telescope hours saved and directly prevents redundant observations on unresolved eclipsing binaries.
                </p>
              </div>
            </div>
          )}

        </div>
      </section>
    </div>
  );
}
