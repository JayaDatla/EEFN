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
                  THE SILOED CATALOG PROBLEM
                </span>
                <h2 className="page-title">
                  Disconnected Catalogs. No One Checks Them Against Each Other.
                </h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
                <div className="flex flex-col gap-4 text-ink/80 text-sm leading-relaxed font-sans">
                  <p>
                    A TESS Object of Interest (TOI) carries one pipeline&apos;s read of the transit and one
                    estimate of the host star. Gaia DR3, 2MASS, and Pan-STARRS each independently measure that
                    same star. Nothing in the TOI record checks its own numbers against those independent
                    sources.
                  </p>
                  <p className="font-bold text-ink">
                    When a candidate&apos;s TESS-reported stellar temperature and Gaia&apos;s measured
                    temperature disagree by hundreds of kelvin, the planet radius derived from each catalog can
                    disagree enough to flip a candidate from &quot;plausible planet&quot; to &quot;physically
                    impossible, most likely an eclipsing binary.&quot;
                  </p>
                  <p>
                    Real example: TOI-1111.01&apos;s own reported radius (14.11 R⊕) looks like an ordinary large
                    sub-Neptune. Recomputed from Gaia&apos;s independent stellar radius, it comes out to 22.15
                    R⊕ — past the physical limit for any transiting planet. See the full walkthrough two steps
                    ahead.
                  </p>
                </div>

                {/* Real catalog identifiers, as actually queried by the pipeline */}
                <div className="glass-panel p-5 rounded-xl flex flex-col gap-4 font-mono text-[10px] relative overflow-hidden h-60 justify-between">
                  <div className="flex justify-between items-center border-b border-border pb-2 text-muted">
                    <span>CATALOGS QUERIED INDEPENDENTLY</span>
                    <span className="text-severity-critical font-bold">NO CROSS-CHECK</span>
                  </div>

                  <div className="flex flex-col gap-2 text-muted">
                    <div className="flex justify-between items-center bg-surface-2 p-2 border border-border rounded-lg">
                      <span className="text-ink/80">NASA Exoplanet Archive</span>
                      <span className="text-muted">[TOI table, TAP sync]</span>
                      <span className="text-ink/60">TAP-toi-1.0</span>
                    </div>
                    <div className="flex justify-between items-center bg-surface-2 p-2 border border-border rounded-lg">
                      <span className="text-ink/80">Gaia DR3 Source + AstroParams</span>
                      <span className="text-muted">[Teff, radius, RUWE]</span>
                      <span className="text-ink/60">I/355/gaiadr3</span>
                    </div>
                    <div className="flex justify-between items-center bg-surface-2 p-2 border border-border rounded-lg">
                      <span className="text-ink/80">2MASS / Pan-STARRS</span>
                      <span className="text-muted">[Photometry]</span>
                      <span className="text-ink/60">II/246, II/349</span>
                    </div>
                  </div>

                  <div className="border-t border-border pt-2 text-center text-muted text-[9px]">
                    Each queried independently by EEFN&apos;s ingestion pipeline; matched by sky position, not by name.
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
                <h2 className="page-title">The Evidence Fusion Story</h2>
                <p className="text-muted mt-2 max-w-xl mx-auto text-xs">
                  Watch how EEFN pulls transit events, aligns them with Gaia DR3 stars, and calculates physical planet radii parameters.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
                {/* Control card */}
                <div className="glass-panel p-4 rounded-xl flex flex-col justify-between font-mono">
                  <div className="flex flex-col gap-2.5">
                    <h4 className="panel-title">Workflow stages</h4>
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
                    <span>TARGET WORKSPACE: TOI-1111.01 (TIC 412014494)</span>
                    <span className="font-bold text-accent">FUSION ENGINE ONLINE</span>
                  </div>

                  <div className="flex justify-around items-center gap-6 my-2">
                    {/* TESS parameters */}
                    <div className="bg-surface-2 border border-border p-4 rounded-xl text-center w-32 font-mono">
                      <span className="text-muted text-[9px] block mb-1 uppercase font-bold">TOI CATALOG TEMP</span>
                      <span className="text-lg font-extrabold text-ink">7262.0 K</span>
                    </div>

                    <div className="text-muted font-bold text-lg font-mono">&harr;</div>

                    {/* Gaia parameters */}
                    <div className={`border p-4 rounded-xl text-center w-32 font-mono transition-all duration-500 ${
                      fusionStage >= 1 ? 'border-accent/30 bg-accent/5' : 'border-border bg-surface-2/20 opacity-30'
                    }`}>
                      <span className="text-muted text-[9px] block mb-1 uppercase font-bold">GAIA DR3 TEMP</span>
                      <span className="text-lg font-extrabold text-ink">{fusionStage >= 1 ? "7464.1 K" : "N/A"}</span>
                    </div>
                  </div>

                  {/* Conflict display */}
                  <div className={`transition-all duration-500 p-3 rounded-lg flex justify-between items-center font-mono text-[10px] ${
                    fusionStage === 2
                      ? 'bg-severity-critical/5 border border-severity-critical/25 text-severity-critical'
                      : 'bg-surface-2/40 text-muted border border-border'
                  }`}>
                    <span>{fusionStage === 2 ? "Catalog temperature disagreement recorded." : "Status: Awaiting parameter checks..."}</span>
                    {fusionStage === 2 && (
                      <span className="font-bold border border-severity-critical/20 px-2 py-0.5 rounded bg-severity-critical/10">202.1 K DELTA</span>
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
                <h2 className="page-title">
                  Derived Planet Size Verification
                </h2>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
                <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-3 font-mono">
                  <h3 className="panel-title">Toi-1111.01 system audit</h3>
                  <div className="flex justify-between"><span>Reported Planet Radius (TESS):</span><span className="text-ink">14.11 R_Earth</span></div>
                  <div className="flex justify-between"><span>Observed Transit Depth:</span><span className="text-ink">8,341.0 ppm</span></div>
                  <div className="flex justify-between"><span>Gaia DR3 Host Star Radius:</span><span className="text-ink">2.221 R_sun</span></div>
                  <div className="border-t border-border my-2"></div>
                  <div className="flex justify-between text-xs font-bold text-ink/80">
                    <span>Gaia-Derived Planet Radius:</span>
                    <span className="text-severity-critical animate-pulse">22.15 R_Earth</span>
                  </div>

                  <div className="bg-severity-critical/5 border border-severity-critical/25 p-3 rounded-lg text-[10px] text-muted leading-normal mt-2">
                    <span className="text-severity-critical font-bold block mb-1">UNPHYSICAL RADIUS FLAG</span>
                    Derived radius exceeds the ~22 R_Earth hydrogen-helium physical limit for transiting exoplanets. This candidate&apos;s real, human-assigned disposition in the archive is FP (false positive) — an eclipsing binary, not a planet.
                  </div>
                </div>

                <div className="flex flex-col gap-4 text-ink/80 text-sm leading-relaxed font-sans">
                  <h4 className="font-bold text-ink text-base">Cross-Catalog Radius Verification</h4>
                  <p>
                    A candidate&apos;s reported planet radius depends entirely on its own catalog&apos;s host
                    star size. If that size is wrong, an impossible planet can look ordinary.
                  </p>
                  <p className="font-bold text-accent">
                    By recomputing the planet&apos;s radius from Gaia&apos;s independently measured stellar
                    radius and the same observed transit depth, EEFN produces a second, independent estimate of
                    the same physical quantity.
                  </p>
                  <p>
                    When that second estimate exceeds the physical limit for a transiting planet, EEFN flags it
                    as unphysical — a check made from stellar physics alone, without ever looking at the light
                    curve shape.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* SECTION 4: WHAT EEFN FLAGS TODAY */}
          {activeSection === 3 && (
            <div className="flex flex-col gap-6 animate-slideUp">
              <div className="text-center mb-4">
                <span className="inline-block px-3 py-1 rounded-full bg-status-pass/10 border border-status-pass/20 text-status-pass font-bold font-mono text-[10px] tracking-widest mb-3">
                  LIVE, FROM THE CURRENT DATABASE
                </span>
                <h2 className="page-title">What EEFN Flags Today</h2>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="glass-panel p-4 rounded-xl text-center shadow-lg hover:border-status-pass/30 transition-all font-mono">
                  <span className="text-muted font-bold block mb-1.5 text-[9px] uppercase tracking-wider">Candidates Synced</span>
                  <span className="text-3xl font-extrabold text-status-pass tracking-tight glow-green">546</span>
                  <span className="text-muted block text-[9px] mt-1.5">Live database</span>
                </div>

                <div className="glass-panel p-4 rounded-xl text-center shadow-lg hover:border-status-pass/30 transition-all font-mono">
                  <span className="text-muted font-bold block mb-1.5 text-[9px] uppercase tracking-wider">Unphysical Radius</span>
                  <span className="text-3xl font-extrabold text-status-pass tracking-tight glow-green">35</span>
                  <span className="text-muted block text-[9px] mt-1.5">Flagged by fusion alone</span>
                </div>

                <div className="glass-panel p-4 rounded-xl text-center shadow-lg hover:border-status-pass/30 transition-all font-mono">
                  <span className="text-muted font-bold block mb-1.5 text-[9px] uppercase tracking-wider">Agree With Human Call</span>
                  <span className="text-3xl font-extrabold text-status-pass tracking-tight glow-green">26 / 35</span>
                  <span className="text-muted block text-[9px] mt-1.5">Already dispositioned FP</span>
                </div>

                <div className="glass-panel p-4 rounded-xl text-center shadow-lg hover:border-status-pass/30 transition-all font-mono">
                  <span className="text-muted font-bold block mb-1.5 text-[9px] uppercase tracking-wider">High RUWE (&gt;1.4)</span>
                  <span className="text-3xl font-extrabold text-status-pass tracking-tight glow-green">91</span>
                  <span className="text-muted block text-[9px] mt-1.5">Likely astrometric binaries</span>
                </div>
              </div>

              <div className="glass-panel p-5 rounded-xl shadow-xl mt-2 leading-relaxed">
                <h4 className="font-bold text-ink border-b border-border pb-2 mb-3 font-mono text-xs">READ AS: AGREEMENT, NOT A SAVINGS ESTIMATE</h4>
                <p className="text-xs text-muted font-sans">
                  35 candidates in the current sync have a Gaia-corrected planet radius that exceeds the
                  physical limit for a transiting planet — a check made purely from stellar physics, without
                  looking at the light curve. 26 of those 35 (74%) already carry a human-assigned FP
                  disposition in the archive: an independent, physics-only check landing on the same conclusion
                  the human vetting process reached, from a completely different angle. We deliberately do not
                  quote a telescope-hours-saved or dollar figure here — that would require assumptions about
                  what a real observatory&apos;s baseline scheduling process already filters out before EEFN
                  ever runs, which we haven&apos;t measured (see <code>LIMITATIONS.md</code> §3.3).
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
                  <p className="text-muted text-[10px] font-mono">Select tabs to audit candidate TOI-1111.01 details dynamically.</p>
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
                      <span className="text-severity-critical font-bold text-xs block mb-1">Unphysical Radius: Derived Planet Radius Mismatch</span>
                      <p className="text-muted text-[10px] leading-normal font-sans">
                        Gaia DR3 stellar radius (Rad=2.221 R☉) and observed transit depth (8,341.0 ppm) result in a derived radius of <strong>22.15 R_Earth</strong> — past the ~22 R_Earth hydrogen-helium limit. Real disposition: FP.
                      </p>
                    </div>
                    <div className="bg-severity-critical/5 border border-severity-critical/25 p-3 rounded-lg">
                      <span className="text-severity-critical font-bold text-xs block mb-1">Density Discrepancy: 8,032σ</span>
                      <p className="text-muted text-[10px] leading-normal font-sans">
                        Transit-implied stellar density (183.5 g/cm³) does not match Gaia&apos;s stellar-evolutionary
                        density for this star (0.224 g/cm³) — two independent derivations of the same physical
                        quantity landing nowhere near each other.
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
                        <th className="p-2">FETCHED</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-900/40 text-ink/80">
                      <tr>
                        <td className="p-2">Stellar Effective Temp</td>
                        <td className="p-2">TOI Catalog</td>
                        <td className="p-2">7262.0 K</td>
                        <td className="p-2 text-muted">2026-08-13</td>
                      </tr>
                      <tr>
                        <td className="p-2">Stellar Effective Temp</td>
                        <td className="p-2">Gaia DR3</td>
                        <td className="p-2">7464.1 K</td>
                        <td className="p-2 text-muted">2026-08-20</td>
                      </tr>
                      <tr>
                        <td className="p-2">2MASS J magnitude</td>
                        <td className="p-2">2MASS Photometry</td>
                        <td className="p-2">9.055</td>
                        <td className="p-2 text-muted">2026-08-20</td>
                      </tr>
                    </tbody>
                  </table>
                )}

                {activeTab === "timeline" && (
                  <div className="flex flex-col gap-2.5 font-mono text-[10px] text-muted animate-fadeIn pl-2">
                    <div className="flex gap-4 border-l border-border pl-4 pb-2 relative">
                      <div className="absolute -left-1 top-1 w-2 h-2 rounded-full bg-muted"></div>
                      <span className="font-bold text-ink">2026-08-13</span>
                      <span>Target synced under TIC 412014494 / TOI-1111.01, with its own TOI-catalog stellar parameters.</span>
                    </div>
                    <div className="flex gap-4 border-l border-border pl-4 pb-2 relative">
                      <div className="absolute -left-1 top-1 w-2 h-2 rounded-full bg-muted"></div>
                      <span className="font-bold text-ink">2026-08-20</span>
                      <span>Gaia DR3 and 2MASS cross-match landed for this star, providing an independent temperature and radius.</span>
                    </div>
                    <div className="flex gap-4 border-l border-border pl-4 pb-2 relative">
                      <div className="absolute -left-1 top-1 w-2 h-2 rounded-full bg-severity-critical"></div>
                      <span className="font-bold text-severity-critical">2026-08-20</span>
                      <span>Gaia-derived planet radius (22.15 R_Earth) exceeded the physical limit. Health grade downgraded C → D (recorded as a real disposition-change event).</span>
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
                <h2 className="page-title">Verification Pipeline</h2>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 text-[10px] text-muted">
                {/* Left Side: 3 Audit Cards */}
                <div className="lg:col-span-2 flex flex-col gap-4">
                  <div className="glass-panel p-4 rounded-xl shadow flex flex-col gap-2">
                    <h4 className="font-bold text-ink border-b border-border pb-1">HELD-OUT PERFORMANCE</h4>
                    <p className="leading-relaxed font-sans text-[11px]">
                      LightGBM evidence-consistency model, 27 real features, evaluated on a stratified
                      80/20 split (n=2,667; held out 534, never trained on): <strong>85.39% accuracy, 0.9267
                      ROC-AUC, 0.8561 F1</strong>. That is the easiest protocol: scored by star-grouped
                      cross-validation it is AUC 0.927 (95% CI 0.917&ndash;0.936), and scored time-forward
                      (train to 2020, test on later TOIs) it falls to about 0.84&ndash;0.88. The Gaia / 2MASS /
                      Pan-STARRS features add only about +0.008 AUC over the TOI table alone, and nothing
                      time-forward.
                    </p>
                    <span className="text-status-pass font-bold block mt-1">SOURCE: model_metrics.json</span>
                  </div>

                  <div className="glass-panel p-4 rounded-xl shadow flex flex-col gap-2">
                    <h4 className="font-bold text-ink border-b border-border pb-1">LABEL LEAKAGE ABLATION</h4>
                    <p className="leading-relaxed font-sans text-[11px]">
                      Compared candidates cataloged before vs. after Gaia EDR3&apos;s 2020-12-03 release (a
                      proxy for whether the model could be circularly re-deriving Gaia-informed labels):
                      pre-EDR3 (n=1,527) scored ROC-AUC <strong>0.9399</strong>, post-EDR3 (n=1,140) scored{" "}
                      <strong>0.9156</strong> — the pre-EDR3 subset performed slightly <em>better</em>, the
                      opposite of what the leakage hypothesis would predict.
                    </p>
                    <span className="text-status-pass font-bold block mt-1">NO LEAKAGE SIGNATURE FOUND</span>
                  </div>

                  <div className="glass-panel p-4 rounded-xl shadow flex flex-col gap-2">
                    <h4 className="font-bold text-ink border-b border-border pb-1">RV-CONFIRMED CLEAN HOLDOUT</h4>
                    <p className="leading-relaxed font-sans text-[11px]">
                      103 candidates independently confirmed by radial-velocity mass measurement (ground truth
                      outside the TESS/Gaia vetting loop) were held out entirely from training. The model
                      correctly flagged <strong>93.2%</strong> of them as positive on data it never saw,
                      versus 100% in-sample recall on the same rows when trained normally.
                    </p>
                    <span className="text-status-pass font-bold block mt-1">SOURCE: LIMITATIONS.md §1.1</span>
                  </div>
                </div>

                {/* Right Side: Limitations & Brutal Comparison */}
                <div className="glass-panel p-5 rounded-xl shadow flex flex-col justify-between border border-severity-critical/20 bg-severity-critical/5">
                  <div>
                    <h4 className="font-bold text-severity-critical border-b border-border pb-2 flex items-center gap-1.5 font-mono text-[11px]">
                      <AlertTriangle className="h-4 w-4" /> SCIENTIFIC LIMITATIONS
                    </h4>
                    <p className="leading-relaxed font-sans text-[11px] text-ink/80 mt-2.5">
                      EEFN is not a substitute for physical validation of a single planet candidate for
                      publication. It cannot compute a rigorous, multi-model False Positive Probability (FPP)
                      the way TRICERATOPS does, and its access to raw diagnostic signals like centroid shifts
                      is real but limited to a small verification subset today, not full coverage.
                    </p>
                    <p className="leading-relaxed font-sans text-[11px] text-ink/80 mt-2.5">
                      It also has more deployment overhead (FastAPI, SQLite, Next.js) than running a single
                      academic script (such as <code className="text-accent">vespa</code> or <code className="text-accent">triceratops</code>).
                    </p>
                  </div>
                  <div className="border-t border-border pt-2 text-[9px] text-muted font-mono">
                    <span>* Context: EEFN serves as an upstream catalog auditor, not a physical signal validator. Full comparison: docs/TOOL_COMPARISON.md</span>
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
                <h2 className="page-title">System Architecture</h2>
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
                  <span className="text-ink font-bold block text-[11px]">3. Database & Entity Graph</span>
                  <span className="text-[9px] font-sans leading-normal">SQLAlchemy/SQLite relational schema; the entity graph view is computed on read, not a separate graph database</span>
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
                <h2 className="page-title">
                  Higher Quality Follow-up Decisions.
                </h2>
              </div>

              <div className="max-w-xl mx-auto flex flex-col gap-4 text-ink/80 text-sm leading-relaxed font-sans">
                <p>
                  EEFN turns tedious, manual cross-catalog arithmetic — the kind that&apos;s realistic to do by
                  hand for one candidate, not hundreds — into an automated, physics-based check that runs on
                  every synced candidate.
                </p>
                <div className="bg-surface-2 border border-border p-4 rounded-xl text-center text-sm font-bold my-3 font-mono text-ink shadow-xl">
                  &quot;26 of the 35 candidates EEFN flags as physically impossible today already carry a
                  human-assigned false-positive disposition — reached by an entirely independent, physics-only
                  check.&quot;
                </div>
                <p className="text-xs text-muted">
                  None of the field&apos;s most-used vetting tools (TRICERATOPS, Robovetter, AstroNet,
                  ExoMiner) check whether a candidate&apos;s own catalog record is internally consistent — that
                  is EEFN&apos;s specific, currently-unaddressed angle, and a complement to those tools rather
                  than a replacement for them.
                </p>
              </div>
            </div>
          )}

        </div>
      </section>
    </div>
  );
}
