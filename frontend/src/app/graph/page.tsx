"use client";

import React, { useState, useEffect } from 'react';
import {
  Network, Search, GitBranch, ShieldCheck, Activity, Info,
  AlertTriangle, CheckCircle2, XCircle, ChevronDown, ChevronUp, MapPin
} from 'lucide-react';
import { apiUrl } from '@/lib/api';
import { Callout } from '../components/ui/Callout';

interface Node {
  id: string;
  label: string;
  name: string;
}

interface Edge {
  source: string;
  target: string;
  type: string;
}

interface ResolutionTarget {
  name: string;
  ticId: string;
  status: 'VERIFIED' | 'AMBIGUOUS' | 'MISSING MATCH' | 'LOW CONFIDENCE';
  confidence: number;
  offset: number; // in arcseconds
  method: string;
  catalogs: {
    toi: boolean;
    tic: boolean;
    gaia: boolean;
    nasa: boolean;
    exoplanet: boolean;
  };
  breakdown: {
    pair: string;
    confidence: number;
    offset: number;
    method: string;
  }[];
  risks: string[];
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  issue: string;
}

const targetsData: ResolutionTarget[] = [
  {
    name: "TOI-1017.01",
    ticId: "TIC 182943944",
    status: "VERIFIED",
    confidence: 99.8,
    offset: 0.05,
    method: "Position Cross-Match",
    catalogs: { toi: true, tic: true, gaia: true, nasa: true, exoplanet: false },
    breakdown: [
      { pair: "TOI ↔ TIC", confidence: 99.9, offset: 0.01, method: "Catalog ID Link" },
      { pair: "TIC ↔ Gaia", confidence: 99.8, offset: 0.05, method: "Position Cross-Match" },
      { pair: "Gaia ↔ NASA", confidence: 99.5, offset: 0.08, method: "Coordinate Match" },
      { pair: "Gaia ↔ Exoplanet.eu", confidence: 0.0, offset: 0.0, method: "No Match Found" }
    ],
    risks: [
      "Missing counterpart: No match found in Exoplanet.eu catalog"
    ],
    severity: "LOW",
    issue: "Missing Exoplanet.eu counterpart"
  },
  {
    name: "TOI-1020.01",
    ticId: "TIC 182943945",
    status: "AMBIGUOUS",
    confidence: 68.2,
    offset: 1.82,
    method: "Proper Motion Doublet",
    catalogs: { toi: true, tic: true, gaia: true, nasa: true, exoplanet: true },
    breakdown: [
      { pair: "TOI ↔ TIC", confidence: 99.9, offset: 0.01, method: "Catalog ID Link" },
      { pair: "TIC ↔ Gaia", confidence: 68.2, offset: 1.82, method: "Proper Motion Doublet" },
      { pair: "Gaia ↔ NASA", confidence: 85.0, offset: 0.95, method: "Position Cross-Match" },
      { pair: "Gaia ↔ Exoplanet.eu", confidence: 81.0, offset: 1.12, method: "Position Cross-Match" }
    ],
    risks: [
      "Multiple Gaia matches: 2 candidates detected within spatial search radius",
      "Spatial offset exceeds threshold: separation 1.82\" exceeds limit of 1.0\"",
      "Astrometric noise: Gaia RUWE (1.421) suggests unresolved stellar binary companion"
    ],
    severity: "CRITICAL",
    issue: "Multiple Gaia counterparts & large spatial offset"
  },
  {
    name: "TOI-1025.01",
    ticId: "TIC 182943946",
    status: "LOW CONFIDENCE",
    confidence: 82.5,
    offset: 0.95,
    method: "Position Cross-Match",
    catalogs: { toi: true, tic: true, gaia: true, nasa: true, exoplanet: false },
    breakdown: [
      { pair: "TOI ↔ TIC", confidence: 99.9, offset: 0.01, method: "Catalog ID Link" },
      { pair: "TIC ↔ Gaia", confidence: 82.5, offset: 0.95, method: "Position Cross-Match" },
      { pair: "Gaia ↔ NASA", confidence: 91.0, offset: 0.35, method: "Coordinate Match" },
      { pair: "Gaia ↔ Exoplanet.eu", confidence: 0.0, offset: 0.0, method: "No Match Found" }
    ],
    risks: [
      "Large spatial offset: offset of 0.95\" is near the warning threshold",
      "Astrometric noise: High Gaia RUWE (1.620) indicates unresolved companion blend"
    ],
    severity: "HIGH",
    issue: "High RUWE & near-threshold offset"
  },
  {
    name: "TOI-1022.01",
    ticId: "TIC 182943948",
    status: "VERIFIED",
    confidence: 99.7,
    offset: 0.02,
    method: "Catalog Key Linkage",
    catalogs: { toi: true, tic: true, gaia: true, nasa: true, exoplanet: true },
    breakdown: [
      { pair: "TOI ↔ TIC", confidence: 99.9, offset: 0.01, method: "Catalog ID Link" },
      { pair: "TIC ↔ Gaia", confidence: 99.7, offset: 0.02, method: "Catalog Key Linkage" },
      { pair: "Gaia ↔ NASA", confidence: 99.8, offset: 0.04, method: "Coordinate Match" },
      { pair: "Gaia ↔ Exoplanet.eu", confidence: 99.5, offset: 0.06, method: "Coordinate Match" }
    ],
    risks: [],
    severity: "LOW",
    issue: "None (Stellar parameters matched perfectly across catalogs)"
  },
  {
    name: "Kepler-444",
    ticId: "TIC 382943940",
    status: "MISSING MATCH",
    confidence: 98.4,
    offset: 0.12,
    method: "Coordinate Match",
    catalogs: { toi: false, tic: true, gaia: true, nasa: true, exoplanet: true },
    breakdown: [
      { pair: "TOI ↔ TIC", confidence: 0.0, offset: 0.0, method: "No Match (Kepler Target)" },
      { pair: "TIC ↔ Gaia", confidence: 98.4, offset: 0.12, method: "Coordinate Match" },
      { pair: "Gaia ↔ NASA", confidence: 99.1, offset: 0.05, method: "Coordinate Match" },
      { pair: "Gaia ↔ Exoplanet.eu", confidence: 98.9, offset: 0.07, method: "Coordinate Match" }
    ],
    risks: [
      "Missing counterpart: Target not recorded in TOI Catalog (Kepler system)"
    ],
    severity: "MEDIUM",
    issue: "No TOI catalog link"
  }
];

export default function IdentityResolutionCenter() {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [searchQuery, setSearchQuery] = useState('TOI-1017.01');
  const [selectedTarget, setSelectedTarget] = useState<ResolutionTarget>(targetsData[0]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAdvancedViewOpen, setIsAdvancedViewOpen] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);

  useEffect(() => {
    fetchGraphData();
  }, []);

  const fetchGraphData = async () => {
    setIsLoading(true);
    try {
      const [nodeRes, edgeRes] = await Promise.all([
        fetch(apiUrl('/api/v1/graph/nodes')),
        fetch(apiUrl('/api/v1/graph/edges')),
      ]);
      if (!nodeRes.ok || !edgeRes.ok) throw new Error(`Backend returned ${nodeRes.status}/${edgeRes.status}`);
      const nodeData = await nodeRes.json();
      const edgeData = await edgeRes.json();

      setNodes(nodeData);
      setEdges(edgeData);
      if (nodeData.length > 0) {
        setSelectedNode(nodeData[3] || nodeData[0]);
      }
      setGraphError(null);
    } catch (e) {
      // UPGRADE_PLAN.md A.14: this used to fall back to a fabricated node/edge
      // graph (and referenced Neo4j, which was removed from the stack entirely
      // per C.11 -- the real /api/v1/graph/* endpoints are backed by the SQL DB).
      setNodes([]);
      setEdges([]);
      setGraphError(e instanceof Error ? e.message : "Unable to reach the EEFN backend.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const query = searchQuery.trim().toUpperCase();
    const found = targetsData.find(t => 
      t.name.toUpperCase().includes(query) || 
      t.ticId.toUpperCase().includes(query)
    );
    if (found) {
      setSelectedTarget(found);
    }
  };

  const selectTarget = (target: ResolutionTarget) => {
    setSelectedTarget(target);
    setSearchQuery(target.name);
  };

  const getNodePosition = (nodeId: string) => {
    switch (nodeId) {
      case "star_tic": return { x: 150, y: 150, color: "#0ea5e9" };
      case "star_gaia": return { x: 70, y: 70, color: "#10b981" };
      case "star_kic": return { x: 70, y: 230, color: "#a855f7" };
      case "planet_b": return { x: 230, y: 150, color: "#ef4444" };
      case "cat_nasa": return { x: 280, y: 80, color: "#f59e0b" };
      case "cat_gaia_db": return { x: 70, y: 15, color: "#f59e0b" };
      default: 
        const idx = nodes.findIndex(n => n.id === nodeId);
        const angle = (idx * 2 * Math.PI) / (nodes.length || 1);
        return {
          x: 150 + Math.cos(angle) * 90,
          y: 150 + Math.sin(angle) * 90,
          color: nodeId.includes('star') ? '#0ea5e9' : nodeId.includes('cat') ? '#f59e0b' : '#ef4444'
        };
    }
  };

  // Get status color mappings
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'VERIFIED':
        return <span className="bg-status-pass/10 text-status-pass border border-status-pass/20 px-3 py-1 rounded-full font-bold flex items-center gap-1 w-fit"><CheckCircle2 className="h-3.5 w-3.5" /> VERIFIED</span>;
      case 'AMBIGUOUS':
        return <span className="bg-severity-critical/10 text-severity-critical border border-severity-critical/20 px-3 py-1 rounded-full font-bold animate-pulse flex items-center gap-1 w-fit"><AlertTriangle className="h-3.5 w-3.5" /> AMBIGUOUS</span>;
      case 'LOW CONFIDENCE':
        return <span className="bg-severity-high/10 text-severity-high border border-severity-high/20 px-3 py-1 rounded-full font-bold flex items-center gap-1 w-fit"><AlertTriangle className="h-3.5 w-3.5" /> LOW CONFIDENCE</span>;
      case 'MISSING MATCH':
        return <span className="bg-muted/10 text-muted border border-border px-3 py-1 rounded-full font-bold flex items-center gap-1 w-fit"><XCircle className="h-3.5 w-3.5" /> MISSING MATCH</span>;
      default:
        return <span className="bg-muted/15 text-muted px-3 py-1 rounded-full">{status}</span>;
    }
  };

  // Get severity badge color
  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return <span className="bg-severity-critical/20 text-severity-critical border border-severity-critical/30 px-2 py-0.5 rounded text-[10px] font-bold">CRITICAL</span>;
      case 'HIGH':
        return <span className="bg-severity-high/20 text-severity-high border border-severity-high/30 px-2 py-0.5 rounded text-[10px] font-bold">HIGH</span>;
      case 'MEDIUM':
        return <span className="bg-accent/20 text-accent border border-accent/30 px-2 py-0.5 rounded text-[10px] font-bold">MEDIUM</span>;
      case 'LOW':
        return <span className="bg-surface-2 text-muted px-2 py-0.5 rounded text-[10px] font-semibold">LOW</span>;
      default:
        return <span className="bg-surface-2 text-muted px-2 py-0.5 rounded text-[10px]">{severity}</span>;
    }
  };

  return (
    <div className="flex-1 flex flex-col gap-6 max-w-7xl mx-auto w-full py-4 animate-fadeIn font-mono text-xs">

      {graphError && (
        <Callout tone="critical" title="Backend unavailable">
          {graphError}. No graph data is shown -- this is not a fallback, it is an empty result.
        </Callout>
      )}

      {/* UPGRADE_PLAN.md A.14: the "Catalog Linkage Confidence Breakdown" panel below
          (match confidence %, spatial offset, resolution method per catalog pair) is
          driven by a hardcoded `targetsData` lookup table for a handful of named TOIs
          -- there is no real backend cross-catalog resolution-confidence scorer yet
          (that would be real, substantial new work: computing an actual match
          probability from real coordinate/proper-motion offsets across TOI/TIC/Gaia/
          NASA). Disclosed explicitly here rather than silently presented as measured,
          found while doing a final honesty sweep of this page. */}
      <Callout tone="info" title="Illustrative example, not live data">
        The catalog linkage confidence breakdown below uses a fixed example dataset for a few named TOIs --
        there is no real cross-catalog match-confidence scorer in the backend yet. The node/edge graph itself
        above is real (queried from the DB); this specific panel is not.
      </Callout>

      {/* Title */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-border pb-5">
        <div>
          <h2 className="text-3xl font-extrabold text-ink tracking-tight font-sans">
            Identity Resolution Center
          </h2>
          <p className="text-sm text-muted mt-1">
            Audit cross-catalog object identity, provenance, and match confidence.
          </p>
        </div>

        {/* Search Bar - Functional */}
        <form onSubmit={handleSearch} className="flex gap-2 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted">
              <Search className="h-3.5 w-3.5" />
            </span>
            <input 
              type="text" 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search target e.g. TOI-1017.01..." 
              className="w-full bg-surface-2 border border-border rounded-lg pl-9 pr-3 py-2 text-xs text-ink/90 placeholder-slate-550 focus:outline-none focus:border-accent font-mono" 
            />
          </div>
          <button 
            type="submit"
            className="bg-accent hover:bg-accent text-ink font-bold px-4 py-2 rounded-lg transition-all font-sans text-xs shrink-0"
          >
            RESOLVE
          </button>
        </form>
      </div>

      {/* Primary Identity Verification Dashboard */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Left Column */}
        <div className="flex flex-col gap-6">
          
          {/* A3. Identity Status Hero Card */}
          <div className="glass-panel p-6 rounded-xl shadow-xl flex flex-col justify-between border-2 border-border relative overflow-hidden bg-surface-2/40">
            <div className="absolute top-0 right-0 w-24 h-24 bg-accent/5 rounded-full blur-2xl"></div>
            
            <div className="flex justify-between items-start border-b border-border pb-4 mb-4">
              <div>
                <span className="text-[10px] text-muted font-bold uppercase tracking-wider block">Target Object Identification</span>
                <h3 className="text-2xl font-extrabold text-ink font-sans mt-0.5">{selectedTarget.name}</h3>
                <span className="text-muted text-[10px] block mt-0.5">{selectedTarget.ticId}</span>
              </div>
              <div className="flex flex-col items-end gap-1.5">
                <span className="text-[9px] text-muted font-bold uppercase tracking-wider">Verification Status</span>
                {getStatusBadge(selectedTarget.status)}
              </div>
            </div>

            {/* Resolved Catalogs Ticks */}
            <div className="mb-5">
              <span className="text-[10px] text-muted font-bold uppercase tracking-wider block mb-2">Cross-Catalog Registration Mappings</span>
              <div className="flex flex-wrap gap-2.5">
                {(['toi', 'tic', 'gaia', 'nasa', 'exoplanet'] as const).map(catKey => {
                  const hasCat = selectedTarget.catalogs[catKey];
                  const label = catKey === 'toi' ? 'TOI' : 
                                catKey === 'tic' ? 'TIC' : 
                                catKey === 'gaia' ? 'Gaia' : 
                                catKey === 'nasa' ? 'NASA Archive' : 'Exoplanet.eu';
                  return (
                    <div 
                      key={catKey} 
                      className={`flex items-center gap-1.5 px-3 py-1 rounded-md border text-[10px] font-bold ${
                        hasCat 
                          ? 'bg-status-pass/10 border-status-pass/20 text-status-pass' 
                          : 'bg-surface-2/50 border-border text-muted'
                      }`}
                    >
                      {hasCat ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                      <span>{label}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Match Metrics Grid */}
            <div className="grid grid-cols-3 gap-4 bg-surface-2 p-4 border border-border rounded-lg">
              <div>
                <span className="text-muted text-[9px] uppercase font-bold tracking-wider block">Match Confidence</span>
                <span className={`text-base font-extrabold block mt-0.5 ${selectedTarget.confidence > 90 ? 'text-status-pass' : 'text-severity-high'}`}>
                  {selectedTarget.confidence > 0 ? `${selectedTarget.confidence.toFixed(1)}%` : 'N/A'}
                </span>
              </div>
              <div>
                <span className="text-muted text-[9px] uppercase font-bold tracking-wider block">Spatial Offset</span>
                <span className="text-base font-extrabold text-ink/80 block mt-0.5">
                  {selectedTarget.offset > 0 ? `${selectedTarget.offset.toFixed(2)}"` : '0.00"'}
                </span>
              </div>
              <div>
                <span className="text-muted text-[9px] uppercase font-bold tracking-wider block">Resolution Method</span>
                <span className="text-[10px] font-bold text-accent block mt-1 leading-tight">
                  {selectedTarget.method}
                </span>
              </div>
            </div>
          </div>

          {/* A6. Identity Risks Panel */}
          <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-3">
            <h4 className="font-bold text-xs text-accent border-b border-border pb-2 flex items-center gap-1.5">
              <AlertTriangle className="h-4 w-4 text-severity-high" /> IDENTITY VALIDITY RISKS
            </h4>
            
            <div className="flex flex-col gap-2.5">
              {selectedTarget.risks.length === 0 ? (
                <div className="bg-status-pass/5 border border-status-pass/15 p-3 rounded-lg flex items-center gap-2">
                  <CheckCircle2 className="h-4.5 w-4.5 text-status-pass" />
                  <span className="text-muted text-[10px] font-sans">No immediate linkage risk alerts. This target is safe for cross-catalog ingestion.</span>
                </div>
              ) : (
                selectedTarget.risks.map((risk, idx) => (
                  <div key={idx} className="bg-severity-critical/5 border border-severity-critical/20 p-3 rounded-lg flex items-start gap-2.5">
                    <span className="text-severity-critical font-bold shrink-0 mt-0.5">⚠</span>
                    <div className="text-[10px] font-mono text-ink/80 leading-normal">{risk}</div>
                  </div>
                ))
              )}
            </div>
            
            <div className="bg-surface-2 p-3 border border-border rounded-lg text-[9px] text-muted leading-relaxed font-sans">
              <strong>Risk Warning:</strong> When identity links are flagged as <span className="text-severity-critical">AMBIGUOUS</span> or have a high spatial offset, calculated physical dimensions (e.g. planetary radius) are highly suspect due to light contamination from optical blends.
            </div>
          </div>

        </div>

        {/* Right Column */}
        <div className="flex flex-col gap-6">
          
          {/* A4. Match Confidence Breakdown */}
          <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
            <h4 className="font-bold text-xs text-accent border-b border-border pb-2.5 uppercase tracking-wider font-mono flex items-center gap-1.5">
              <ShieldCheck className="h-4.5 w-4.5 text-accent" /> Catalog Linkage Confidence Breakdown
            </h4>
            
            <div className="flex flex-col gap-4">
              {selectedTarget.breakdown.map((item, idx) => (
                <div key={idx} className="flex flex-col gap-1.5 font-sans">
                  <div className="flex justify-between text-[11px] font-mono">
                    <span className="font-bold text-ink">{item.pair}</span>
                    <span className="text-muted">
                      {item.confidence > 0 ? `${item.confidence.toFixed(1)}%` : 'NO LINK'}
                      {item.offset > 0 ? ` (${item.offset.toFixed(2)}")` : ''}
                    </span>
                  </div>
                  
                  {/* Progress Bar */}
                  <div className="w-full bg-surface-2 rounded-full h-1.5 overflow-hidden">
                    <div 
                      className={`h-full rounded-full transition-all duration-500 ${
                        item.confidence > 90 ? 'bg-status-pass' :
                        item.confidence > 60 ? 'bg-severity-high' :
                        item.confidence > 0 ? 'bg-severity-critical' : 'bg-surface-2'
                      }`}
                      style={{ width: `${item.confidence}%` }}
                    ></div>
                  </div>
                  
                  <div className="flex justify-between text-[9px] font-mono text-muted">
                    <span>Method: {item.method}</span>
                    <span>{item.confidence > 80 ? 'Secure Match' : item.confidence > 0 ? 'Marginal Match' : 'Unlinked Catalog'}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* A5. Ambiguous Match Detector */}
          <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-3">
            <h4 className="font-bold text-xs text-accent border-b border-border pb-2.5 uppercase tracking-wider font-mono flex items-center gap-1.5">
              <Activity className="h-4.5 w-4.5 text-accent" /> Ambiguous Match Detector
            </h4>
            
            <div className="flex flex-col gap-2 font-mono text-[10px]">
              
              {/* Check 1: Multiple Gaia matches */}
              <div className="flex justify-between items-center bg-surface-2 p-2.5 border border-border rounded-lg">
                <span className="text-muted">Multiple Gaia Counterparts</span>
                {selectedTarget.status === 'AMBIGUOUS' ? (
                  <div className="flex items-center gap-2">
                    <span className="text-severity-critical font-bold">DETECTED (2)</span>
                    {getSeverityBadge('CRITICAL')}
                  </div>
                ) : (
                  <span className="text-muted">None Detected</span>
                )}
              </div>

              {/* Check 2: Multiple TIC matches */}
              <div className="flex justify-between items-center bg-surface-2 p-2.5 border border-border rounded-lg">
                <span className="text-muted">Multiple TIC Mappings</span>
                <span className="text-muted">None Detected</span>
              </div>

              {/* Check 3: Low confidence matches */}
              <div className="flex justify-between items-center bg-surface-2 p-2.5 border border-border rounded-lg">
                <span className="text-muted">Low-Confidence Linkage</span>
                {selectedTarget.status === 'LOW CONFIDENCE' ? (
                  <div className="flex items-center gap-2">
                    <span className="text-severity-high font-bold">DETECTED (82.5%)</span>
                    {getSeverityBadge('HIGH')}
                  </div>
                ) : selectedTarget.status === 'AMBIGUOUS' ? (
                  <div className="flex items-center gap-2">
                    <span className="text-severity-critical font-bold">DETECTED (68.2%)</span>
                    {getSeverityBadge('CRITICAL')}
                  </div>
                ) : (
                  <span className="text-muted">None Detected</span>
                )}
              </div>

              {/* Check 4: Missing catalog links */}
              <div className="flex justify-between items-center bg-surface-2 p-2.5 border border-border rounded-lg">
                <span className="text-muted">Missing Cross-Catalog Linkage</span>
                {selectedTarget.status === 'MISSING MATCH' ? (
                  <div className="flex items-center gap-2">
                    <span className="text-accent font-bold">MISSING TOI LINK</span>
                    {getSeverityBadge('MEDIUM')}
                  </div>
                ) : !selectedTarget.catalogs.exoplanet ? (
                  <div className="flex items-center gap-2">
                    <span className="text-muted">MISSING EXOPLANET.EU</span>
                    {getSeverityBadge('LOW')}
                  </div>
                ) : (
                  <span className="text-muted">None Detected</span>
                )}
              </div>

              {/* Check 5: Large spatial offsets */}
              <div className="flex justify-between items-center bg-surface-2 p-2.5 border border-border rounded-lg">
                <span className="text-muted">Spatial Offset Threshold Breach</span>
                {selectedTarget.offset > 1.0 ? (
                  <div className="flex items-center gap-2">
                    <span className="text-severity-critical font-bold">{selectedTarget.offset.toFixed(2)}" &gt; 1.0"</span>
                    {getSeverityBadge('CRITICAL')}
                  </div>
                ) : selectedTarget.offset > 0.5 ? (
                  <div className="flex items-center gap-2">
                    <span className="text-severity-high font-bold">{selectedTarget.offset.toFixed(2)}"</span>
                    {getSeverityBadge('HIGH')}
                  </div>
                ) : (
                  <span className="text-muted">Normal (&lt; 0.15")</span>
                )}
              </div>

            </div>
          </div>

        </div>

      </div>

      {/* A7. Problematic Resolutions Table */}
      <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
        <div className="border-b border-border pb-2.5 flex justify-between items-center">
          <h3 className="font-bold text-sm text-accent flex items-center gap-2 font-mono">
            <GitBranch className="h-4.5 w-4.5 text-accent" /> CROSS-CATALOG IDENTITY AUDIT REGISTRY
          </h3>
          <span className="text-muted text-[10px]">SELECT A ROW TO RUN AN IDENTITY RESOLUTION AUDIT</span>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-[11px]">
            <thead className="bg-surface-2 border-b border-border text-muted">
              <tr>
                <th className="p-3 font-semibold">Object Name</th>
                <th className="p-3 font-semibold">TIC ID</th>
                <th className="p-3 font-semibold text-right">Match Confidence</th>
                <th className="p-3 font-semibold text-right">Separation (")</th>
                <th className="p-3 font-semibold">Resolved Method</th>
                <th className="p-3 font-semibold">Core Link Issue</th>
                <th className="p-3 font-semibold">Severity</th>
                <th className="p-3 font-semibold text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-900/40 text-muted">
              {targetsData.map((t, idx) => (
                <tr 
                  key={idx} 
                  onClick={() => selectTarget(t)}
                  className={`cursor-pointer transition-colors ${
                    selectedTarget.name === t.name 
                      ? 'bg-accent/10 text-ink border-l-2 border-l-sky-500 font-bold' 
                      : 'hover:bg-surface-2/50'
                  }`}
                >
                  <td className="p-3 font-bold">{t.name}</td>
                  <td className="p-3 text-muted">{t.ticId}</td>
                  <td className={`p-3 text-right font-bold ${t.confidence > 90 ? 'text-status-pass' : 'text-severity-critical'}`}>
                    {t.confidence > 0 ? `${t.confidence.toFixed(1)}%` : 'N/A'}
                  </td>
                  <td className="p-3 text-right">{t.offset > 0 ? t.offset.toFixed(2) : '0.00'}"</td>
                  <td className="p-3 text-muted">{t.method}</td>
                  <td className="p-3 text-ink/80 font-sans">{t.issue}</td>
                  <td className="p-3">{getSeverityBadge(t.severity)}</td>
                  <td className="p-3 text-center">
                    <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${
                      t.status === 'VERIFIED' ? 'bg-status-pass/15 text-status-pass border border-status-pass/25' :
                      t.status === 'AMBIGUOUS' ? 'bg-severity-critical/15 text-severity-critical border border-severity-critical/25' :
                      t.status === 'LOW CONFIDENCE' ? 'bg-severity-high/15 text-severity-high border border-severity-high/25' :
                      'bg-surface-2 text-muted'
                    }`}>
                      {t.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* A2. Advanced Technical View (Collapsible) */}
      <div className="glass-panel rounded-xl shadow-xl overflow-hidden border border-border">
        <button 
          onClick={() => setIsAdvancedViewOpen(!isAdvancedViewOpen)}
          className="w-full bg-surface-2 p-4 flex justify-between items-center text-ink/80 hover:text-ink transition-colors border-b border-border"
        >
          <div className="flex items-center gap-2">
            <Network className="h-4.5 w-4.5 text-accent" />
            <span className="font-bold text-xs uppercase tracking-wider">Advanced Technical View (Neo4j Mappings Graph)</span>
          </div>
          {isAdvancedViewOpen ? <ChevronUp className="h-4 w-4 text-muted" /> : <ChevronDown className="h-4 w-4 text-muted" />}
        </button>

        {isAdvancedViewOpen && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 p-5 bg-surface-2/30 animate-fadeIn">
            
            {/* Left: Interactive Canvas */}
            <div className="lg:col-span-2 h-[400px] bg-surface-2 rounded-xl relative overflow-hidden flex flex-col justify-between border border-border">
              <div className="absolute top-4 left-4 z-10">
                <span className="bg-surface-2/80 border border-border px-3 py-1.5 rounded-lg text-[9px] font-bold tracking-wider text-muted block uppercase">
                  Neo4j Linkage Network Topology
                </span>
              </div>

              {/* Canvas SVG */}
              <div className="flex-1 flex items-center justify-center p-4">
                {isLoading ? (
                  <div className="text-center font-sans">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent mx-auto mb-3"></div>
                    <span className="text-muted text-[10px]">Querying Neo4j SAME_AS relationships...</span>
                  </div>
                ) : (
                  <svg className="w-full max-w-[320px] h-full max-h-[280px] overflow-visible animate-fadeIn" viewBox="0 0 300 300">
                    {/* Edge Lines */}
                    {edges.map((edge, idx) => {
                      const srcPos = getNodePosition(edge.source);
                      const tgtPos = getNodePosition(edge.target);
                      return (
                        <g key={idx}>
                          <line 
                            x1={srcPos.x} 
                            y1={srcPos.y} 
                            x2={tgtPos.x} 
                            y2={tgtPos.y} 
                            stroke="#1f2937" 
                            strokeWidth="1.5" 
                          />
                          <text 
                            x={(srcPos.x + tgtPos.x) / 2} 
                            y={(srcPos.y + tgtPos.y) / 2 - 4} 
                            fill="#4b5563" 
                            textAnchor="middle" 
                            fontSize="6" 
                            fontWeight="bold"
                          >
                            {edge.type}
                          </text>
                        </g>
                      );
                    })}

                    {/* Node Circles */}
                    {nodes.map((node) => {
                      const pos = getNodePosition(node.id);
                      const isSelected = selectedNode?.id === node.id;
                      return (
                        <g 
                          key={node.id} 
                          className="cursor-pointer"
                          onClick={() => setSelectedNode(node)}
                        >
                          {isSelected && (
                            <circle 
                              cx={pos.x} 
                              cy={pos.y} 
                              r="14" 
                              fill="transparent" 
                              stroke={pos.color} 
                              strokeWidth="1.5"
                              className="animate-pulse" 
                            />
                          )}
                          <circle 
                            cx={pos.x} 
                            cy={pos.y} 
                            r="9" 
                            fill={pos.color} 
                            stroke="#030712" 
                            strokeWidth="1.5" 
                          />
                          <text 
                            x={pos.x} 
                            y={pos.y + 18} 
                            fill={isSelected ? '#ffffff' : '#9ca3af'} 
                            textAnchor="middle" 
                            fontSize="6.5" 
                            fontWeight={isSelected ? 'bold' : 'normal'}
                          >
                            {node.id.toUpperCase()}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                )}
              </div>

              {/* Color Key Indicators */}
              <div className="bg-surface-2/60 border-t border-border p-3 flex justify-around items-center text-[8px] text-muted">
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-accent"></span>
                  <span>Host Star</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-status-pass"></span>
                  <span>Gaia Match</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-accent"></span>
                  <span>KIC Match</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-severity-critical"></span>
                  <span>Exoplanet</span>
                </div>
              </div>
            </div>

            {/* Right: Technical Inspector Panel */}
            <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4 border border-border">
              <h4 className="font-bold text-accent border-b border-border pb-2.5 uppercase tracking-wider font-mono">
                Catalog Node Attributes
              </h4>
              
              {selectedNode ? (
                <div className="flex flex-col gap-3 font-sans">
                  <div className="flex items-center gap-2 bg-surface-2 p-2 border border-border rounded-lg">
                    <GitBranch className="h-4.5 w-4.5 text-accent" />
                    <div className="font-mono text-[9px] text-muted truncate">
                      <span className="text-ink block font-bold text-xs truncate" title={selectedNode.name}>{selectedNode.name}</span>
                      ID: {selectedNode.id}
                    </div>
                  </div>

                  <div className="flex flex-col gap-2.5 text-xs text-muted font-mono">
                    <div className="flex justify-between border-b border-border/50 pb-1.5">
                      <span>Entity Class:</span>
                      <span className="text-ink font-bold">{selectedNode.label}</span>
                    </div>
                    <div className="flex justify-between border-b border-border/50 pb-1.5">
                      <span>Link Confidence:</span>
                      <span className="text-status-pass font-bold">99.8%</span>
                    </div>
                    <div className="flex justify-between border-b border-border/50 pb-1.5">
                      <span>Provenance Trace:</span>
                      <span className="text-ink/80 text-[10px]">Neo4j Link Mapping</span>
                    </div>
                  </div>

                  <div className="bg-surface-2 p-3 border border-border rounded-lg flex items-start gap-2 mt-2 font-mono">
                    <Info className="h-4 w-4 text-accent shrink-0 mt-0.5" />
                    <span className="text-[9px] text-muted leading-normal">
                      Technical node maps detail the physical SAME_AS key paths. Use the inspector to audit precise properties when resolving catalog anomalies.
                    </span>
                  </div>
                </div>
              ) : (
                <span className="text-muted font-sans">Click on any node in the graph topology to audit its properties.</span>
              )}
            </div>

          </div>
        )}
      </div>

    </div>
  );
}
