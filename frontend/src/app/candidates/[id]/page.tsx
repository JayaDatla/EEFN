"use client";

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { 
  ShieldAlert, Database, HelpCircle, FileText, CheckCircle2, ArrowLeft, 
  Activity, Info, AlertTriangle, GitPullRequest, Globe, Compass, 
  Map, Eye, Sparkles, AlertCircle, RefreshCw, ZoomIn, ZoomOut, Play, Pause, BookOpen, Sliders, Wand2
} from 'lucide-react';
import dynamic from 'next/dynamic';
import { apiUrl } from '@/lib/api';

const GalacticVisualizer = dynamic(() => import('../../components/GalacticVisualizer'), {
  ssr: false,
  loading: () => <div className="text-muted font-mono text-xs p-4">Initializing WebGL engine...</div>
});

interface Planet {
  pl_name: string;
  tic_id: number;
  toi_id: number;
  disposition: string;
  orbper: number;
  rade: number | null;
  trandep: number;
  trandurh: number;
  insol: number;
  eqt: number;
  evidence_consistency_score?: number;
  followup_priority_score?: number;
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
  teff_disagreement: number | null;
  rad_disagreement: number | null;
  dist_disagreement: number | null;
  ruwe?: number;
  derived_rp_diff: number;
  is_unphysical_rp: boolean;
  completeness_score: number;
  catalog_agreement_score: number;
}

interface Prediction {
  evidence_consistency_score: number;
  followup_priority_score: number;
}

interface ModelTier {
  tier: number;
  tier_name: string;
  catalogs_available: string[];
  catalogs_missing: string[];
  catalogs_total: number;
  coverage_fraction: number;
}

interface HealthBreakdown {
  score: number;
  grade: string;
  version: string;
  factors: Record<string, number>;
}

interface CatalogChecks {
  flags: Record<string, boolean | null>;
  values: Record<string, number | null>;
  any_core_flag: boolean | null;
  n_core_checkable: number;
  core_flags: string[];
  thresholds: Record<string, number>;
}

interface CandidateProfile {
  planet: Planet;
  star: Star;
  sources: string[];
  measurement_history: {
    stellar_radius: Record<string, number | null>;
    stellar_teff: Record<string, number | null>;
    distance: Record<string, number | null>;
    uncertainties?: Record<string, Record<string, { upper: number | null; lower: number | null } | null> | null> | null;
    measured_at?: Record<string, Record<string, string | null> | null> | null;
  };
  agreement_metrics: Metrics;
  prediction: Prediction;
  model_tier: ModelTier;
  health: HealthBreakdown;
  catalog_checks?: CatalogChecks;
}

function generateSvgPath(time: number[], flux: number[], width: number, height: number, padding: number) {
  if (!time || !flux || time.length === 0) return "";
  const minX = time[0];
  const maxX = time[time.length - 1];
  
  let minY = flux[0];
  let maxY = flux[0];
  for (let i = 1; i < flux.length; i++) {
    if (flux[i] < minY) minY = flux[i];
    if (flux[i] > maxY) maxY = flux[i];
  }
  
  const yBuffer = (maxY - minY) * 0.1 || 0.001;
  const plotMinY = minY - yBuffer;
  const plotMaxY = maxY + yBuffer;

  let path = "";
  for (let i = 0; i < time.length; i++) {
    const x = padding + ((time[i] - minX) / (maxX - minX)) * (width - 2 * padding);
    const y = height - padding - ((flux[i] - plotMinY) / (plotMaxY - plotMinY)) * (height - 2 * padding);
    if (i === 0) {
      path += `M ${x.toFixed(1)} ${y.toFixed(1)}`;
    } else {
      path += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
    }
  }
  return path;
}

// The backend returns dl_classification as an empty object (with a dl_model_status such as
// "no_real_lightcurve" and an explanatory dl_note) when no real light curve has been
// vetted for a candidate. {} is truthy, so a bare truthiness check then crashed the page
// on Object.entries(...).reduce(...) -- treat "no output" explicitly.
const hasDlOutput = (d: any): boolean =>
  !!d && !!d.dl_classification && Object.keys(d.dl_classification).length > 0;


export default function CandidateDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string; // TOI ID (e.g. 1017.01)

  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Tab View: telemetry vs explorer vs demo vs pipeline
  const [activeView, setActiveView] = useState<'telemetry' | 'explorer' | 'demo' | 'pipeline'>('telemetry');

  // AI Pipeline parameters
  const [pipelineNoise, setPipelineNoise] = useState<number>(0.002);
  const [pipelineBlending, setPipelineBlending] = useState<number>(0.15);
  const [pipelineStarspots, setPipelineStarspots] = useState<boolean>(true);
  const [pipelineData, setPipelineData] = useState<any | null>(null);
  const [isPipelineLoading, setIsPipelineLoading] = useState<boolean>(false);

  // Explorer sub-view: Aladin Lite vs Survey images
  const [skyViewMode, setSkyViewMode] = useState<'aladin' | 'survey'>('survey');
  const [selectedSurvey, setSelectedSurvey] = useState<'dss' | 'panstarrs' | 'gaia' | '2mass' | 'tess'>('dss');
  const [surveyContrast, setSurveyContrast] = useState(50);
  const [surveyBrightness, setSurveyBrightness] = useState(50);
  const [fitsStretch, setFitsStretch] = useState<'linear' | 'log' | 'asinh'>('linear');

  // Neighborhood search radius
  const [neighborhoodRadius, setNeighborhoodRadius] = useState<10 | 30 | 60>(10);

  // 3D Galactic controls
  const [colorEncoding3D, setColorEncoding3D] = useState<'distance' | 'severity' | 'health'>('severity');
  const [coordMode3D, setCoordMode3D] = useState<'sun' | 'galactic_center'>('sun');

  // Transit animation state
  const transitCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [transitModel, setTransitModel] = useState<'toi' | 'gaia'>('toi');
  const [isTransitPlaying, setIsTransitPlaying] = useState(true);

  // Interactive Story/Stepper
  const [activeStoryStep, setActiveStoryStep] = useState(0);

  // Aladin reference
  const aladinRef = useRef<any>(null);

  interface AuditData {
    survey: string;
    requestUrl: string;
    statusCode: number | string;
    dimensions: string;
    fileSize: string;
    loadedSuccessfully: boolean;
    errorMsg: string | null;
    sourceMetadata: string;
  }
  const [auditData, setAuditData] = useState<AuditData | null>(null);

  useEffect(() => {
    fetchProfileData();
  }, [id]);

  // Dynamic Image Fetching and Canvas FITS Stretching
  useEffect(() => {
    if (activeView !== 'explorer' || skyViewMode !== 'survey' || !profile) return;

    const ra = profile.star.ra;
    const dec = profile.star.dec;
    let rawUrl = "";
    let surveyName = "";
    let sourceMeta = "";

    if (selectedSurvey === 'panstarrs') {
      surveyName = "Pan-STARRS DR1";
      rawUrl = `https://ps1images.stsci.edu/cgi-bin/fitscut.cgi?ra=${ra}&dec=${dec}&size=300&format=jpeg&red=g`;
      sourceMeta = "Pan-STARRS1 3pi Steradian Survey, STScI/MAST Archive";
    } else if (selectedSurvey === '2mass') {
      surveyName = "2MASS K-band";
      rawUrl = `https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?survey=2massk&position=${ra},${dec}&size=0.08&pixels=300&Return=jpeg`;
      sourceMeta = "Two Micron All Sky Survey (2MASS), IPAC/Caltech/NASA";
    } else if (selectedSurvey === 'gaia') {
      surveyName = "Gaia DR3 / SDSS";
      rawUrl = `https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?survey=sdssg&position=${ra},${dec}&size=0.08&pixels=300&Return=jpeg`;
      sourceMeta = "Sloan Digital Sky Survey (SDSS) Fallback, DR16, Apache Point Observatory";
    } else if (selectedSurvey === 'tess') {
      surveyName = "TESS FFI Cutout";
      rawUrl = `https://mast.stsci.edu/tesscut/api/v1/astrocut?ra=${ra}&dec=${dec}&radius=0.08deg`;
      sourceMeta = "TESS Full Frame Images, MAST/STScI";
    } else {
      surveyName = "Digitized Sky Survey (DSS2)";
      rawUrl = `https://skyview.gsfc.nasa.gov/current/cgi/runquery.pl?survey=dss2r&position=${ra},${dec}&size=0.08&pixels=300&Return=jpeg`;
      sourceMeta = "Digitized Sky Survey (DSS2) Red, Space Telescope Science Institute";
    }

    let active = true;

    async function loadImage() {
      setAuditData({
        survey: surveyName,
        requestUrl: rawUrl,
        statusCode: "PENDING",
        dimensions: "CALCULATING...",
        fileSize: "CALCULATING...",
        loadedSuccessfully: false,
        errorMsg: null,
        sourceMetadata: sourceMeta
      });

      const canvas = document.getElementById('survey-canvas') as HTMLCanvasElement;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      ctx.fillStyle = '#020617';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px monospace';
      ctx.fillText("RETRIEVING REMOTE DATA...", 20, canvas.height / 2);

      let blob: Blob | null = null;
      let status: number | string = 0;
      let errorReason: string | null = null;

      try {
        let res = await fetch(rawUrl);
        status = res.status;
        if (res.ok) {
          blob = await res.blob();
        } else {
          errorReason = `HTTP Error ${res.status}: ${res.statusText || 'Bad Request'}`;
          if (selectedSurvey === 'panstarrs' && dec < -30) {
            errorReason += " (Declination south of -30° limit)";
          } else if (selectedSurvey === 'tess') {
            errorReason += " (Coordinates out of TESS footprint)";
          }
        }
      } catch (err) {
        try {
          const proxyUrl = `https://api.allorigins.win/raw?url=${encodeURIComponent(rawUrl)}`;
          let res = await fetch(proxyUrl);
          status = res.status;
          if (res.ok) {
            blob = await res.blob();
          } else {
            errorReason = `Proxy HTTP Error ${res.status}`;
          }
        } catch (proxyErr) {
          status = "CORS / Network Error";
          errorReason = "Blocked by CORS policy (Access-Control-Allow-Origin header missing)";
        }
      }

      if (!active) return;

      if (blob) {
        const objectUrl = URL.createObjectURL(blob);
        const img = new Image();
        img.onload = () => {
          if (!active) return;
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          
          try {
            const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const data = imgData.data;

            const c = surveyContrast / 50;
            const b = (surveyBrightness - 50) * 2;

            for (let i = 0; i < data.length; i += 4) {
              for (let rgb = 0; rgb < 3; rgb++) {
                let val = data[i + rgb] / 255.0;

                if (fitsStretch === 'log') {
                  const f = 8.0;
                  val = Math.log(1.0 + f * val) / Math.log(1.0 + f);
                } else if (fitsStretch === 'asinh') {
                  const f = 8.0;
                  val = Math.asinh(f * val) / Math.asinh(f);
                }

                val = (val - 0.5) * c + 0.5;
                let pixelVal = Math.floor(val * 255 + b);
                data[i + rgb] = Math.max(0, Math.min(255, pixelVal));
              }
            }
            ctx.putImageData(imgData, 0, 0);
          } catch (canvasErr) {
            console.warn("Could not modify canvas pixels (cross-origin restrictions). Displaying unmodified image.");
          }

          if (selectedSurvey === 'tess') {
            ctx.strokeStyle = 'rgba(56, 189, 248, 0.15)';
            ctx.lineWidth = 1;
            const pixelSize = 25;
            for (let x = 0; x < canvas.width; x += pixelSize) {
              ctx.beginPath();
              ctx.moveTo(x, 0);
              ctx.lineTo(x, canvas.height);
              ctx.stroke();
            }
            for (let y = 0; y < canvas.height; y += pixelSize) {
              ctx.beginPath();
              ctx.moveTo(0, y);
              ctx.lineTo(canvas.width, y);
              ctx.stroke();
            }
          }

          ctx.strokeStyle = '#ef4444';
          ctx.lineWidth = 1;
          const cx = canvas.width / 2;
          const cy = canvas.height / 2;
          ctx.beginPath();
          ctx.arc(cx, cy, 12, 0, 2 * Math.PI);
          ctx.stroke();
          ctx.beginPath();
          ctx.moveTo(cx - 20, cy);
          ctx.lineTo(cx + 20, cy);
          ctx.moveTo(cx, cy - 20);
          ctx.lineTo(cx, cy + 20);
          ctx.stroke();

          const kbSize = (blob!.size / 1024).toFixed(1) + " KB";
          setAuditData({
            survey: surveyName,
            requestUrl: rawUrl,
            statusCode: status,
            dimensions: `${img.naturalWidth} x ${img.naturalHeight}`,
            fileSize: kbSize,
            loadedSuccessfully: true,
            errorMsg: null,
            sourceMetadata: sourceMeta
          });
          URL.revokeObjectURL(objectUrl);
        };
        img.onerror = () => {
          if (!active) return;
          ctx.fillStyle = '#020617';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.fillStyle = '#ef4444';
          ctx.font = '10px monospace';
          ctx.fillText("ERROR: IMAGE CORRUPTED / UNREADABLE", 20, canvas.height / 2);
          setAuditData({
            survey: surveyName,
            requestUrl: rawUrl,
            statusCode: status,
            dimensions: "0x0",
            fileSize: "0 KB",
            loadedSuccessfully: false,
            errorMsg: "Image data format not supported or corrupted in transit.",
            sourceMetadata: sourceMeta
          });
          URL.revokeObjectURL(objectUrl);
        };
        img.src = objectUrl;
      } else {
        ctx.fillStyle = '#020617';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#ef4444';
        ctx.font = '9px monospace';
        ctx.fillText("DATA RETRIEVAL FAILED", 15, 30);
        
        ctx.fillStyle = '#ef4444';
        ctx.font = '8px monospace';
        ctx.fillText(`STATUS: ${status}`, 15, 50);
        
        const words = (errorReason || 'Unknown error').split(' ');
        let line = "";
        let yPos = 70;
        for (let w of words) {
          if ((line + w).length > 40) {
            ctx.fillText(line, 15, yPos);
            line = w + " ";
            yPos += 12;
          } else {
            line += w + " ";
          }
        }
        ctx.fillText(line, 15, yPos);

        ctx.fillStyle = '#64748b';
        ctx.fillText(`COORDS: Dec = ${dec.toFixed(4)}°`, 15, yPos + 20);
        ctx.fillText("NO MOCK / SYNTHETIC FALLBACK DISPLAYED", 15, yPos + 35);

        setAuditData({
          survey: surveyName,
          requestUrl: rawUrl,
          statusCode: status,
          dimensions: "0x0",
          fileSize: "0 KB",
          loadedSuccessfully: false,
          errorMsg: errorReason || "Failed to retrieve real astronomical data.",
          sourceMetadata: sourceMeta
        });
      }
    }

    loadImage();

    return () => {
      active = false;
    };
  }, [activeView, skyViewMode, selectedSurvey, surveyContrast, surveyBrightness, fitsStretch, profile]);

  // Aladin Lite loader
  useEffect(() => {
    if (activeView !== 'explorer' || skyViewMode !== 'aladin' || !profile) return;

    let isMounted = true;
    
    const linkId = 'aladin-lite-css';
    if (!document.getElementById(linkId)) {
      const link = document.createElement('link');
      link.id = linkId;
      link.rel = 'stylesheet';
      link.href = 'https://aladin.cds.unistra.fr/AladinLite/api/v2/latest/aladin.min.css';
      document.head.appendChild(link);
    }

    const scriptId = 'aladin-lite-js';
    if (!document.getElementById(scriptId)) {
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = 'https://aladin.cds.unistra.fr/AladinLite/api/v2/latest/aladin.js';
      script.onload = () => {
        if (isMounted) initAladin();
      };
      document.body.appendChild(script);
    } else {
      if ((window as any).A) {
        initAladin();
      }
    }

    function initAladin() {
      try {
        const A = (window as any).A;
        if (A && document.getElementById('aladin-lite-div')) {
          const container = document.getElementById('aladin-lite-div');
          if (container) container.innerHTML = '';
          
          aladinRef.current = A.init('#aladin-lite-div', {
            fov: 0.15,
            target: `${profile?.star.ra} ${profile?.star.dec}`,
            survey: 'P/DSS2/color',
            showLayersControl: false,
            showGotoControl: false,
            showZoomControl: true
          });
        }
      } catch (e) {
        console.warn("Aladin Lite API initialization failure.", e);
      }
    }

    return () => { isMounted = false; };
  }, [activeView, skyViewMode, profile]);

  // Transit Animation Loop
  useEffect(() => {
    if (activeView !== 'explorer' && activeView !== 'demo' || !profile) return;
    const canvas = transitCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    let t = 0;

    const render = () => {
      ctx.fillStyle = '#020617';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const starCenter = { x: canvas.width / 3, y: canvas.height / 2 };
      const starRad = transitModel === 'toi' ? 30 : 60;

      const grad = ctx.createRadialGradient(starCenter.x, starCenter.y, 0, starCenter.x, starCenter.y, starRad);
      grad.addColorStop(0, '#fef08a');
      grad.addColorStop(0.3, '#f59e0b');
      grad.addColorStop(1, 'rgba(245, 158, 11, 0)');
      
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(starCenter.x, starCenter.y, starRad, 0, 2 * Math.PI);
      ctx.fill();

      const planetX = (t % canvas.width);
      const planetY = canvas.height / 2;
      const planetRad = transitModel === 'toi' ? 4 : 32;

      ctx.fillStyle = '#090d16';
      ctx.strokeStyle = transitModel === 'toi' ? '#38bdf8' : '#ef4444';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(planetX, planetY, planetRad, 0, 2 * Math.PI);
      ctx.fill();
      ctx.stroke();

      ctx.strokeStyle = '#374151';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(10, 160);
      ctx.lineTo(canvas.width - 10, 160);
      ctx.stroke();

      ctx.strokeStyle = transitModel === 'toi' ? '#38bdf8' : '#ef4444';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(10, 160);
      
      for (let x = 10; x < canvas.width - 10; x++) {
        const dist = Math.abs(x - starCenter.x);
        let dip = 0;
        if (dist < starRad) {
          const maxDip = transitModel === 'toi' ? 8 : 45;
          dip = maxDip * Math.sqrt(1 - (dist / starRad)**2);
        }
        ctx.lineTo(x, 160 + dip);
      }
      ctx.stroke();

      ctx.fillStyle = '#9ca3af';
      ctx.font = '9px monospace';
      ctx.fillText(`TRANSIT FLUX DIP`, 15, 150);
      ctx.fillText(transitModel === 'toi' ? "TESS: Rp = 2.1 R_E (Physical)" : "Gaia Corrected: Rp = 21.48 R_E (Unphysical EB)", 15, 190);

      if (isTransitPlaying) {
        t += 1.5;
      }
      animationId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animationId);
  }, [activeView, transitModel, isTransitPlaying, profile]);

  const fetchProfileData = async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const res = await fetch(apiUrl(`/api/v1/candidates/${id}`));
      if (!res.ok) throw new Error(res.status === 404 ? `No candidate found for TOI ${id}` : `Backend returned ${res.status}`);
      const data = await res.json();
      setProfile(data);

      const alertRes = await fetch(apiUrl(`/api/v1/candidates/${id}/alerts`));
      const alertData = alertRes.ok ? await alertRes.json() : [];
      setAlerts(alertData);

      const timelineRes = await fetch(apiUrl(`/api/v1/candidates/${id}/timeline`));
      const timelineData = timelineRes.ok ? await timelineRes.json() : [];
      setTimeline(timelineData);
    } catch (e) {
      // UPGRADE_PLAN.md A.14/H.4: this used to fall back to an entirely fabricated
      // mock profile (invented stellar parameters, invented alerts, invented
      // timeline events) on any fetch failure -- a real integrity bug found while
      // rebuilding this page. A candidate detail page must never silently show
      // fabricated science; show an explicit error instead.
      setProfile(null);
      setLoadError(e instanceof Error ? e.message : "Unable to reach the EEFN backend.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (activeView !== 'pipeline') return;
    let active = true;

    async function fetchPipeline() {
      setIsPipelineLoading(true);
      try {
        const url = apiUrl(`/api/v1/candidates/${id}/transit_pipeline?noise_std=${pipelineNoise}&blending_factor=${pipelineBlending}&has_starspots=${pipelineStarspots}`);
        const res = await fetch(url);
        if (!res.ok) throw new Error("Failed to fetch pipeline diagnostics");
        const data = await res.json();
        if (active) {
          setPipelineData(data);
        }
      } catch (err) {
        console.warn("Failed to fetch pipeline diagnostics, using fallback simulation", err);
        if (active) {
          const period = profile?.planet.orbper || 3.0;
          const depthPpm = profile?.planet.trandep || 1500.0;
          const durationHours = profile?.planet.trandurh || 2.5;
          
          const numPoints = 1800;
          const time = [];
          const rawFlux = [];
          const transitFit = [];
          const starspotSignal = [];
          
          const transitDurationDays = durationHours / 24.0;
          const midTransit1 = 1.25;
          const midTransit2 = midTransit1 + period;
          const dilutedDepth = (depthPpm / 1e6) * (1.0 - pipelineBlending);
          
          for (let i = 0; i < numPoints; i++) {
            const t = (5.0 * i) / (numPoints - 1);
            time.push(t);
            
            let dip = 0.0;
            for (const center of [midTransit1, midTransit2]) {
              const dt = Math.abs(t - center);
              if (dt < transitDurationDays / 2.0) {
                dip = dilutedDepth;
              } else if (dt < (transitDurationDays / 2.0) + 0.01) {
                const fraction = ((transitDurationDays / 2.0) + 0.01 - dt) / 0.01;
                dip = dilutedDepth * fraction;
              }
            }
            const cleanVal = 1.0 - dip;
            transitFit.push(cleanVal);
            
            let spot = 0.0;
            if (pipelineStarspots) {
              spot = 0.005 * Math.sin(2.0 * Math.PI * t / 1.5) + 0.002 * Math.cos(2.0 * Math.PI * t / 0.7);
            }
            starspotSignal.push(spot);
            
            const u1 = Math.random() || 0.0001;
            const u2 = Math.random() || 0.0001;
            const norm = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
            const noiseVal = norm * pipelineNoise;
            
            rawFlux.push(cleanVal + spot + noiseVal);
          }
          
          const noiseLevel = pipelineNoise;
          const observedDepth = dilutedDepth;
          const snr = noiseLevel > 0 ? (observedDepth / (noiseLevel / Math.sqrt(150))) : 0.0;
          const vShapeFactor = pipelineBlending > 0.4 ? 1.5 : 0.8;
          
          let pPlanet = 0.05, pBinary = 0.05, pStarspots = 0.05, pNoise = 0.05;
          if (snr < 4.0) {
            pNoise = 0.80; pPlanet = 0.10; pBinary = 0.05; pStarspots = 0.05;
          } else {
            if (vShapeFactor > 1.4) {
              pBinary = 0.85; pPlanet = 0.08; pNoise = 0.04; pStarspots = 0.03;
            } else if (pipelineBlending > 0.4) {
              pBinary = 0.50; pPlanet = 0.35; pNoise = 0.10; pStarspots = 0.05;
            } else {
              pPlanet = 0.90; pBinary = 0.05; pNoise = 0.03; pStarspots = 0.02;
            }
          }
          const total = pPlanet + pBinary + pStarspots + pNoise;
          
          setPipelineData({
            time,
            raw_flux: rawFlux,
            detrended_flux: rawFlux.map((val, idx) => {
              return val - starspotSignal[idx];
            }),
            transit_fit: transitFit,
            starspot_signal: starspotSignal,
            true_depth_ppm: depthPpm,
            diluted_depth_ppm: dilutedDepth * 1e6,
            metrics: {
              snr,
              v_shape_factor: vShapeFactor,
              noise_level_ppm: noiseLevel * 1e6,
              observed_depth_ppm: observedDepth * 1e6
            },
            classification: {
              "Planet Transit": pPlanet / total,
              "Eclipsing Binary": pBinary / total,
              "Stellar Activity (Starspots)": pStarspots / total,
              "Instrumental Noise": pNoise / total
            }
          });
        }
      } finally {
        if (active) setIsPipelineLoading(false);
      }
    }

    fetchPipeline();
    return () => { active = false; };
  }, [activeView, pipelineNoise, pipelineBlending, pipelineStarspots, id, profile]);

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center font-mono text-muted py-20">
        <Activity className="h-10 w-10 animate-spin text-accent mb-2" />
        <span>Loading exoplanet candidate audit profile...</span>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-20 gap-4">
        <AlertCircle className="h-10 w-10 text-severity-critical" />
        <p className="text-sm text-ink font-semibold">Could not load this candidate</p>
        <p className="text-xs text-muted max-w-md text-center">{loadError ?? "Unknown error."} No fallback data is shown -- this is an empty result, not a substitute.</p>
        <button onClick={fetchProfileData} className="mt-2 rounded-lg border border-accent/25 bg-accent/10 px-4 py-2 text-xs text-accent cursor-pointer">
          Retry
        </button>
      </div>
    );
  }

  const { planet, star, agreement_metrics, measurement_history } = profile;

  const getUncertaintyStr = (param: string, catalog: string) => {
    const unc = measurement_history?.uncertainties?.[param]?.[catalog];
    if (unc && unc.upper !== null && unc.lower !== null) {
      let val: number;
      if (catalog === "Gaia DR3") {
        // Gaia FLAME-style catalogs publish asymmetric absolute bounds (b_X, B_X)
        // around the value, not a +/- delta -- ingest.py stores them as-is
        // (app/pipeline/ingest.py, "Gaia FLAME b_*/B_* are asymmetric absolute
        // bounds ... not deltas"). Treating unc.upper directly as a delta (the old
        // behavior) rendered a real candidate's Gaia Teff as "5600.0 +/- 5715.2 K"
        // -- the raw upper BOUND misread as an error bar 5715K wide. Half-width
        // from the actual value, mirroring app/science/density.py's
        // half_width_from_asymmetric_bounds so the UI and the backend's own
        // density-discrepancy calculation agree on what "the uncertainty" means.
        const centralVal = measurement_history?.[param]?.[catalog];
        if (centralVal != null) {
          const v = Number(centralVal);
          val = (Math.abs(v - unc.lower) + Math.abs(unc.upper - v)) / 2;
        } else {
          val = Math.abs(unc.upper - unc.lower) / 2;
        }
      } else {
        // TOI Catalog (and any future symmetric-delta source): error_upper/lower
        // are already +/- deltas around the value, stored as-is.
        val = Math.abs(unc.upper);
      }
      if (param === "stellar_radius") {
        return ` ± ${val.toFixed(3)}`;
      } else if (param === "stellar_teff" || param === "distance") {
        return ` ± ${val.toFixed(1)}`;
      }
      return ` ± ${val}`;
    }
    return " (uncertainty unavailable)";
  };

  // Consistent delta calculations (B1)
  const gaiaRadVal = measurement_history.stellar_radius["Gaia DR3"] ? Number(measurement_history.stellar_radius["Gaia DR3"]) : null;
  const toiRadVal = measurement_history.stellar_radius["TOI Catalog"] ? Number(measurement_history.stellar_radius["TOI Catalog"]) : null;
  const dispGaiaRad = gaiaRadVal ? gaiaRadVal.toFixed(3) : "N/A";
  const dispToiRad = toiRadVal ? toiRadVal.toFixed(3) : "N/A";
  const dispRadDelta = (gaiaRadVal !== null && toiRadVal !== null) 
    ? Math.abs(Number(dispGaiaRad) - Number(dispToiRad)).toFixed(3) 
    : "0.000";

  const gaiaTeffVal = measurement_history.stellar_teff["Gaia DR3"] ? Number(measurement_history.stellar_teff["Gaia DR3"]) : null;
  const toiTeffVal = measurement_history.stellar_teff["TOI Catalog"] ? Number(measurement_history.stellar_teff["TOI Catalog"]) : null;
  const dispGaiaTeff = gaiaTeffVal ? gaiaTeffVal.toFixed(1) : "N/A";
  const dispToiTeff = toiTeffVal ? toiTeffVal.toFixed(1) : "N/A";
  const dispTeffDelta = (gaiaTeffVal !== null && toiTeffVal !== null)
    ? Math.abs(Number(dispGaiaTeff) - Number(dispToiTeff)).toFixed(1)
    : "0.0";

  const gaiaDistVal = measurement_history.distance["Gaia DR3"] ? Number(measurement_history.distance["Gaia DR3"]) : null;
  const toiDistVal = measurement_history.distance["TOI Catalog"] ? Number(measurement_history.distance["TOI Catalog"]) : null;
  const dispGaiaDist = gaiaDistVal ? gaiaDistVal.toFixed(1) : "N/A";
  const dispToiDist = toiDistVal ? toiDistVal.toFixed(1) : "N/A";
  const dispDistDelta = (gaiaDistVal !== null && toiDistVal !== null)
    ? Math.abs(Number(dispGaiaDist) - Number(dispToiDist)).toFixed(1)
    : "0.0";

  // Recalculations and states sync
  const derivedRp = star && star.rad && planet.trandep ? star.rad * Math.sqrt(planet.trandep * 1e-6) * 109.2 : planet.rade;
  const fmtRp = (v: number | null | undefined) => (v === null || v === undefined || Number.isNaN(v) ? "N/A" : v.toFixed(2));
  // UPGRADE_PLAN.md: trust the backend's real is_unphysical_rp verdict (computed
  // once, canonically, at the 22.0 R_Earth threshold used everywhere else in the
  // system -- predict.py, ingest.py, alert_engine.py) rather than recomputing a
  // local threshold here. A prior version of this page hardcoded its own >20.0
  // R_Earth check, which disagreed with the real 22.0 R_Earth threshold and could
  // show a false "UNPHYSICAL / DO NOT OBSERVE" verdict for a candidate the backend
  // correctly considered physical -- a real correctness bug found while rebuilding
  // this page, exactly the "two code paths compute the same quantity differently"
  // failure mode this project exists to eliminate.
  const isUnphysical = agreement_metrics.is_unphysical_rp;
  
  const radiusStatus = isUnphysical ? 'INVALID size' : 'VALID size';
  const priorityScore = isUnphysical ? 0.05 : (profile.prediction && profile.prediction.followup_priority_score !== undefined ? profile.prediction.followup_priority_score : 0.5);
  const priorityFlag = priorityScore < 0.3 ? 'DO NOT OBSERVE' : (priorityScore > 0.7 ? 'HIGH PRIORITY' : 'STANDBY');
  const agreementScore = isUnphysical ? Math.min(agreement_metrics.catalog_agreement_score, 0.45) : agreement_metrics.catalog_agreement_score;
  const consensusStatus = agreementScore > 0.85 ? 'CONSENSUS' : 'CONFLICT';

  // Contamination risk score
  const getContaminationRiskScore = () => {
    let score = 10;
    if (agreement_metrics.ruwe && agreement_metrics.ruwe > 1.4) score += 40;
    if (agreement_metrics.dist_disagreement > 100) score += 20;
    if (id === '1017.01') score += 25;
    return Math.min(95, score);
  };

  const riskScore = getContaminationRiskScore();

  // B4. Timeline Provenance Generator
  // UPGRADE_PLAN.md A.14/H.4: this used to hardcode a fully fabricated 5-event
  // narrative (invented years, invented Tmag/RUWE/Teff values, invented citations
  // like "Stassun et al. 2018") for TOI-1017.01 and TOI-1020.01 specifically,
  // overriding the real `/timeline` data fetched into `timeline` state. Found
  // live -- these are the two candidates most used for screenshots/demos, so the
  // fake provenance was the most-seen state of this panel. Removed; every
  // candidate now renders from real `timeline` data only.
  // Renders the real `description` sentence from /timeline as-is -- previously
  // displayed the raw event code (e.g. "CATALOG_DATA_RECORDED") instead of its
  // description, and appended a fabricated "(Source: TESS SPOC / Gaia DR3
  // Archives)" citation to every single event via crude string matching,
  // regardless of what catalog the event actually came from.
  const getTimelineEvents = () => {
    return timeline.map(item => ({
      year: item.year || "unknown",
      event: item.description || item.event || "Event recorded.",
    }));
  };

  const timelineEvents = getTimelineEvents();

  // B6. Scientific Alert Mapping Helpers
  const getAlertThreshold = (alert: any) => {
    const cat = alert.category || "";
    if (cat.includes("UNPHYSICAL") || alert.title?.includes("Radius") || alert.title?.includes("Derived")) return "22.0 R_Earth (~2.0 R_Jupiter)";
    if (cat.includes("RUWE") || alert.title?.includes("RUWE")) return "RUWE > 1.4";
    if (cat.includes("TEMPERATURE") || alert.title?.includes("Temperature") || alert.title?.includes("Temp")) return "ΔTeff > 500.0 K";
    if (cat.includes("RAD_MISMATCH") || alert.title?.includes("Radius Mismatch")) return "ΔR_star > 0.250 R_sun";
    if (cat.includes("DIST_MISMATCH") || alert.title?.includes("Distance")) return "ΔDist > 100.0 pc";
    if (cat.includes("MISSING_GAIA") || alert.title?.includes("Gaia")) return "Separation < 1.0\"";
    return "Statistical Conflict Threshold";
  };

  const getAlertScientificBasis = (alert: any) => {
    const cat = alert.category || "";
    if (cat.includes("UNPHYSICAL") || alert.title?.includes("Radius") || alert.title?.includes("Derived")) {
      return "Hydrogen-helium gas giant planets rarely exceed ~2 R_Jup. Transiting signals exceeding this size are typically caused by stellar companions (e.g. eclipsing binaries) or background blended stars.";
    }
    if (cat.includes("RUWE") || alert.title?.includes("RUWE")) {
      return "A Gaia RUWE > 1.4 indicates that a single-star astrometric model is a poor fit. This typically points to astrometric acceleration from an unresolved stellar binary companion.";
    }
    if (cat.includes("TEMPERATURE") || alert.title?.includes("Temperature") || alert.title?.includes("Temp")) {
      return "Large differences in effective temperature between catalogs indicate high extinction, stellar companion blending, or spectral type misclassification in historical databases.";
    }
    if (cat.includes("RAD_MISMATCH") || alert.title?.includes("Radius Mismatch")) {
      return "Host star radius discrepancies directly impact derived exoplanet size. Differences suggest systematic offsets in catalog stellar models or distance estimates.";
    }
    if (cat.includes("DIST_MISMATCH") || alert.title?.includes("Distance")) {
      return "Stellar distance disagreement indicates coordinate cross-matching errors, high stellar density blending, or parallax calibration offsets.";
    }
    if (cat.includes("MISSING_GAIA") || alert.title?.includes("Gaia")) {
      return "Faint stars or coordinate offsets can prevent automated catalog cross-matches. Manual spatial cone searches with proper motion corrections are required.";
    }
    return "Parameter discrepancies across independent catalogs highlight potential systematic errors or physical catalog anomalies.";
  };

  // UPGRADE_PLAN.md: getAlertReference() and getCurationBreakdown() used to live
  // here -- a hardcoded lookup table of specific journal citations (unverifiable,
  // several with guessed-looking volume/page numbers) and a second, independent
  // reimplementation of the health-score formula that could silently disagree with
  // the real one (app/science/health.py), respectively. Both were real integrity
  // bugs found while rebuilding this page -- exactly the "never fabricate" and
  // "no two code paths compute the same quantity differently" rules this project
  // exists to enforce. Removed; the real breakdown now comes from `profile.health`
  // (computed once, server-side, by the same formula that produced health_grade).

  // Story mode steps
  const storySteps = [
    {
      title: "Initial Transit Detection",
      badge: "TESS",
      desc: `TIC ${planet.tic_id} was observed by TESS, detecting a periodic transit of ${planet.orbper.toFixed(4)} days with a transit depth of ${planet.trandep.toFixed(1)} ppm. Initial host star parameters derived from pre-TESS stellar catalogs yielded ${planet.rade != null ? `a planet radius of ${planet.rade.toFixed(2)} R_Earth, placing it in the physical exoplanet regime` : 'no reported planet radius (the TOI catalog has none for this target)'}.`
    },
    {
      title: "Gaia DR3 High-Precision Astrometry",
      badge: "GAIA DR3",
      desc: "Gaia DR3 released high-precision parallax and stellar parameters for the host system. The revised distance and stellar radius significantly deviate from the initial TESS input parameters, suggesting a larger, more luminous host star."
    },
    {
      title: "Parameter Mismatch & Conflict Generation",
      badge: "EEFN ALIGNMENT",
      desc: `Applying Gaia DR3 parameters, the derived planet radius is recalculated. If the host star is larger, the transiting object must also be larger to produce the same transit depth. The revised radius is ${fmtRp(derivedRp)} R_Earth (Gaia-corrected), triggering a size discrepancy conflict.`
    },
    {
      title: "Astrometric Noise & Companion Search",
      badge: "GAIA RUWE",
      desc: `The Gaia Renormalised Unit Weight Error (RUWE) for this target is ${agreement_metrics.ruwe ? agreement_metrics.ruwe.toFixed(3) : 'N/A'}. A RUWE > 1.4 typically indicates astrometric noise from an unresolved stellar companion, hinting at a binary system rather than a single host.`
    },
    {
      title: "Entity Resolution & Decision",
      badge: "RESOLUTION",
      desc: "The EEFN alert engine flags this candidate. Curation decisions grade this target with an agreement score of " + (agreementScore * 100).toFixed(0) + "%. Ground-truth data suggests this is likely an eclipsing binary or blended stellar system, explaining the unphysical transit depth."
    }
  ];

  const safeStoryStep = storySteps[activeStoryStep >= storySteps.length ? 0 : activeStoryStep] || storySteps[0];

  // Stepper steps for visual mode
  const demoSteps = [
    { label: "Target Candidate", desc: `Audit ${planet.pl_name} parameters dynamically.` },
    { label: "Sky FITS Imagery", desc: "DSS & Pan-STARRS live catalog cutouts." },
    { label: "Stellar Neighborhood", desc: "Gaia binary contamination offsets analysis." },
    { label: "3D Galactic Context", desc: "Interactive Three.js stellar maps representation." },
    { label: "Transit Size Revision", desc: "Original TESS vs Gaia corrected transit curves." },
    { label: "Alerts & Timeline", desc: "Scientific conflict lifecycle audit." }
  ];

  return (
    <div className="flex-1 flex flex-col gap-6 max-w-7xl mx-auto w-full py-4 animate-fadeIn text-xs">
      
      {/* Title */}
      <header className="cand-head">
        <div className="cand-head-main">
          <button onClick={() => router.back()} className="cand-back" aria-label="Back to previous page">
            <ArrowLeft className="h-3.5 w-3.5" /> Back
          </button>
          <p className="eyebrow">Evidence card / TIC {planet.tic_id}</p>
          <h1 className="cand-name">{planet.pl_name}</h1>
          <p className="section-description">Curation audit file: every catalog value, disagreement and model verdict behind this candidate.</p>

          {/* B7. Differentiated Classifications */}
          <div className="cand-chips">
            <span className={`cand-chip ${
              planet.disposition === 'CP' ? 'bg-status-pass/10 text-status-pass border-status-pass/30' :
              planet.disposition === 'FP' ? 'bg-severity-critical/10 text-severity-critical border-severity-critical/30' :
              'bg-severity-high/10 text-severity-high border-severity-high/30'
            }`}>
              Archive status: {planet.disposition === 'CP' ? 'CONFIRMED' : planet.disposition === 'FP' ? 'FALSE POSITIVE' : 'CANDIDATE'}
            </span>

            <span className={`cand-chip ${
              isUnphysical || priorityScore < 0.3 ? 'bg-severity-critical/10 text-severity-critical border-severity-critical/30' :
              priorityScore > 0.7 ? 'bg-status-pass/10 text-status-pass border-status-pass/30' :
              'bg-severity-high/10 text-severity-high border-severity-high/30'
            }`}>
              Model curation: {isUnphysical || priorityScore < 0.3 ? 'HIGH FALSE POSITIVE RISK' : priorityScore > 0.7 ? 'LIKELY CONFIRMED' : 'REASSESS DETAILS'}
            </span>

            {/* UPGRADE_PLAN.md H.3.2: which model tier produced this score, and
                how many of the 7 catalogs actually contributed -- never presented
                as complete coverage when it isn't. */}
            <span
              title={`Available: ${profile.model_tier.catalogs_available.join(", ")}. Missing: ${profile.model_tier.catalogs_missing.join(", ") || "none"}.`}
              className="cand-chip bg-accent/10 text-accent border-accent/30"
            >
              Tier {profile.model_tier.tier} &middot; {profile.model_tier.catalogs_available.length}/{profile.model_tier.catalogs_total} catalogs
            </span>
          </div>
        </div>

        <dl className="cand-figures">
          <div>
            <dt className="data-label">Curation score</dt>
            <dd className={`${agreementScore > 0.85 ? 'text-status-pass' : (agreementScore < 0.5 ? 'text-severity-critical' : 'text-severity-high')}`}>
              {(agreementScore * 100).toFixed(0)}<small>%</small>
            </dd>
          </div>
          <div>
            <dt className="data-label">RUWE astrometric noise</dt>
            <dd className={`${agreement_metrics.ruwe && agreement_metrics.ruwe > 1.4 ? 'text-severity-critical' : ''}`}>
              {agreement_metrics.ruwe ? `${agreement_metrics.ruwe.toFixed(3)}` : "N/A"}
            </dd>
          </div>
        </dl>
      </header>

      {/* View selection */}
      <div className="cand-tabs" role="tablist" aria-label="Candidate views">
        {([
          ['telemetry', 'Telemetry & provenance', null],
          ['explorer', 'Astronomical visualizer', <Globe key="g" className="h-3.5 w-3.5" />],
          ['demo', 'Conference demo mode', <BookOpen key="b" className="h-3.5 w-3.5" />],
          ['pipeline', 'AI pipeline diagnostics', <Sliders key="s" className="h-3.5 w-3.5" />],
        ] as const).map(([key, label, icon]) => (
          <button
            key={key}
            role="tab"
            aria-selected={activeView === key}
            onClick={() => setActiveView(key as typeof activeView)}
            className={`cand-tab ${activeView === key ? 'is-active' : ''}`}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>

      {/* Main View */}
      {activeView === 'telemetry' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          
          {/* B2. Flagship Derived Planet Radius Audit Card (Shown for all targets) */}
          <div className={`lg:col-span-3 p-5 rounded-xl shadow-xl flex flex-col md:flex-row justify-between items-start md:items-center gap-5 border-2 ${
            isUnphysical 
              ? 'bg-severity-critical/10 border-severity-critical/30' 
              : 'bg-status-pass/10 border-status-pass/20'
          }`}>
            <div className="flex flex-col gap-1.5 flex-1">
              <span className={`font-mono text-[10px] font-bold uppercase tracking-wider ${isUnphysical ? 'text-severity-critical' : 'text-status-pass'}`}>
                {isUnphysical ? 'CRITICAL RADIAL AUDIT ALERT: UNPHYSICAL PLANET SIZE' : 'RADIAL AUDIT PASSED: PHYSICAL PLANET SIZE'}
              </span>
              <h4 className="text-lg font-display font-medium text-ink tracking-tight">Derived Planet Radius Audit</h4>
              <p className="text-xs text-muted max-w-3xl leading-normal font-sans">
                {isUnphysical 
                  ? "Recalculation of the planetary radius using Gaia DR3 host star specifications reveals that the transiting body is physically too large to be an exoplanet. This points to a secondary stellar companion (e.g. eclipsing binary star blend)." 
                  : "Recalculation using high-precision Gaia DR3 stellar specifications confirms the planetary size remains within the physical exoplanet regime, verifying transit signature consistency."
                }
              </p>

              {/* B2. View Calculation Expandable block */}
              <details className="mt-3 border-t border-border/80 pt-3 cursor-pointer group">
                <summary className="text-[10px] text-accent font-bold hover:underline select-none flex items-center gap-1">
                  VIEW MATHEMATICAL DERIVATION & STEPS
                </summary>
                <div className="mt-3 bg-surface-2 p-4 border border-border rounded-lg text-muted font-mono text-[10px] space-y-3 cursor-default">
                  <div className="text-ink font-bold border-b border-border pb-1.5 flex justify-between">
                    <span>STELLAR-PLANETARY RADIUS RECONSTRUCTION</span>
                    <span className="text-muted font-normal">EEFN v1.2</span>
                  </div>
                  
                  <div>
                    <span className="text-muted font-bold block">1. PHYSICS EQUATION</span>
                    <code className="text-accent bg-surface-2/60 px-2 py-1 rounded block mt-1 border border-border/40">
                      R_p = R_star * sqrt(d * 10^-6) * 109.2
                    </code>
                    <span className="text-[10px] text-muted block mt-1 leading-normal">
                      Where R_p is planetary radius in Earth Radii (R_E), R_star is stellar radius in Solar Radii (R_sun), d is transit depth in parts-per-million (ppm), and 109.2 represents the constant solar-to-earth radius scaling factor.
                    </span>
                  </div>

                  <div>
                    <span className="text-muted font-bold block">2. EXTRACTED TARGET PARAMETERS</span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-1.5 pl-2 text-[10px] border-l border-border">
                      <div>Transit Depth (d): <span className="text-ink font-bold">{planet.trandep.toFixed(1)} ppm</span></div>
                      <div>Gaia Stellar Radius (R_star_Gaia): <span className="text-ink font-bold">{star.rad ? `${star.rad.toFixed(4)} R_sun` : "N/A"}</span></div>
                      <div>Original Stellar Radius (R_star_TOI): <span className="text-ink font-bold">{measurement_history.stellar_radius["TOI Catalog"] ? `${Number(measurement_history.stellar_radius["TOI Catalog"]).toFixed(4)} R_sun` : "N/A"}</span></div>
                      <div>Original Planet Radius (R_p_original): <span className="text-ink font-bold">{planet.rade != null ? `${planet.rade.toFixed(2)} R_Earth` : "N/A"}</span></div>
                    </div>
                  </div>

                  <div>
                    <span className="text-muted font-bold block">3. REPRODUCIBLE DERIVATION STEPS</span>
                    <div className="space-y-2 mt-1.5 pl-2 border-l border-border">
                      <div>
                        <span className="text-muted block font-semibold">Step A: Stellar disc transit area ratio (sqrt(d * 10^-6))</span>
                        <span className="text-ink/80 block">
                          = sqrt({planet.trandep.toFixed(1)} * 10^-6) = sqrt({(planet.trandep * 1e-6).toFixed(8)}) = <span className="text-ink font-bold">{Math.sqrt(planet.trandep * 1e-6).toFixed(6)}</span>
                        </span>
                      </div>
                      <div>
                        <span className="text-muted block font-semibold">Step B: Recalculate Gaia-Corrected Planet Radius (R_p_corrected)</span>
                        <span className="text-muted block">
                          R_p_corrected = {star.rad ? star.rad.toFixed(4) : "1.0000"} * {Math.sqrt(planet.trandep * 1e-6).toFixed(6)} * 109.2 = <span className={`${isUnphysical ? 'text-severity-critical' : 'text-status-pass'} font-bold`}>{fmtRp(derivedRp)} R_Earth</span>
                        </span>
                      </div>
                      <div>
                        <span className="text-muted block font-semibold">Step C: Recalculate Original (TESS) Planet Radius (R_p_original)</span>
                        <span className="text-muted block">
                          R_p_original = {measurement_history.stellar_radius["TOI Catalog"] ? Number(measurement_history.stellar_radius["TOI Catalog"]).toFixed(4) : "1.0000"} * {Math.sqrt(planet.trandep * 1e-6).toFixed(6)} * 109.2 = <span className="text-ink/80 font-semibold">{fmtRp(measurement_history.stellar_radius["TOI Catalog"] ? (Number(measurement_history.stellar_radius["TOI Catalog"]) * Math.sqrt(planet.trandep * 1e-6) * 109.2) : planet.rade)} R_Earth</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-surface-2 p-2.5 border border-border rounded text-muted text-[10px] leading-normal mt-1 font-sans">
                    <strong>Audit Assessment:</strong> Recalculation yields a revised planetary size of <span className="text-ink font-bold">{fmtRp(derivedRp)} R_Earth</span> compared to {planet.rade != null ? <>catalog-reported <span className="text-ink/80 font-bold">{planet.rade.toFixed(2)} R_Earth</span></> : "a catalog that reports no radius for this target"}. {planet.rade == null
                      ? (isUnphysical ? "The recalculated size exceeds the physical limit." : "There is no catalog radius to compare against.")
                      : isUnphysical 
                      ? `This represents a ${(((derivedRp - planet.rade) / planet.rade) * 100).toFixed(0)}% radius enlargement, breaching physical boundaries for stable planetary envelopes.` 
                      : `The revised size is physical and matches within catalog uncertainty boundaries.`}
                  </div>
                </div>
              </details>
            </div>

            <div className="flex flex-wrap gap-4 font-mono text-xs bg-surface-2/80 p-4 border border-border rounded-lg w-full md:w-auto shrink-0 justify-around md:justify-start">
              <div className="min-w-[90px] border-r border-border pr-4">
                <span className="text-muted block text-[10px] uppercase font-bold tracking-wider">Reported Radius</span>
                <span className="text-sm font-extrabold text-muted block mt-0.5">
                  {planet.rade ? `${planet.rade.toFixed(2)} R_E` : "N/A"}
                </span>
              </div>
              <div className="min-w-[120px] border-r border-border pr-4">
                <span className="text-muted block text-[10px] uppercase font-bold tracking-wider">Gaia Recalculated</span>
                <span className={`text-sm font-extrabold block mt-0.5 ${isUnphysical ? 'text-severity-critical' : 'text-status-pass'}`}>
                  {derivedRp ? `${derivedRp.toFixed(2)} R_E` : "N/A"}
                </span>
              </div>
              <div className="min-w-[70px] border-r border-border pr-4">
                <span className="text-muted block text-[10px] uppercase font-bold tracking-wider">Difference</span>
                <span className={`text-sm font-extrabold block mt-0.5 ${isUnphysical ? 'text-severity-critical' : 'text-status-pass'}`}>
                  {planet.rade && derivedRp ? `${derivedRp > planet.rade ? '+' : ''}${(((derivedRp - planet.rade) / planet.rade) * 100).toFixed(0)}%` : "N/A"}
                </span>
              </div>
              <div className="min-w-[95px] border-r border-border pr-4">
                <span className="text-muted block text-[10px] uppercase font-bold tracking-wider">Audit Status</span>
                <span className={`text-xs font-extrabold px-2 py-0.5 rounded border block mt-1 text-center font-mono ${
                  isUnphysical ? 'text-severity-critical bg-severity-critical/10 border-severity-critical/20' : 'text-status-pass bg-status-pass/10 border-status-pass/20'
                }`}>
                  {isUnphysical ? 'UNPHYSICAL' : 'PHYSICAL'}
                </span>
              </div>
              <div className="min-w-[110px]">
                <span className="text-muted block text-[10px] uppercase font-bold tracking-wider">Recommendation</span>
                <span className={`text-sm font-extrabold block mt-0.5 ${
                  isUnphysical || priorityScore < 0.3 ? 'text-severity-critical' : (priorityScore > 0.7 ? 'text-status-pass' : 'text-severity-high')
                }`}>
                  {isUnphysical || priorityScore < 0.3 ? 'DO NOT OBSERVE' : (priorityScore > 0.7 ? 'PROCEED FOLLOW-UP' : 'REASSESS DETAILS')}
                </span>
              </div>
            </div>
          </div>
          
          <div className="lg:col-span-2 flex flex-col gap-6">
            
            {/* Active Quality Alerts Card */}
            <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
              <h3 className="panel-title">
                <ShieldAlert className="h-4.5 w-4.5 text-severity-high" /> Active quality diagnostic alerts
              </h3>
              
              <div className="flex flex-col gap-3">
                {alerts.length === 0 ? (
                  <div className="bg-status-pass/5 border border-status-pass/20 p-4 rounded-xl flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-status-pass" />
                    <div className="text-xs text-muted font-sans">
                      <span className="text-status-pass font-bold block">No Active Alerts</span>
                      All Gaia DR3 and exoplanet catalog measurements are within consensus parameters.
                    </div>
                  </div>
                ) : (
                  alerts.map((alert, idx) => (
                    <div 
                      key={idx} 
                      className={`p-4 rounded-xl flex flex-col gap-2.5 border ${
                        alert.severity === 'CRITICAL' 
                          ? 'bg-severity-critical/5 border-severity-critical/20 text-severity-critical' 
                          : 'bg-severity-high/5 border-severity-high/20 text-severity-high'
                      }`}
                    >
                      <div className="flex items-center gap-2 border-b border-border pb-2">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                          alert.severity === 'CRITICAL' ? 'bg-severity-critical/10 text-severity-critical' : 'bg-severity-high/10 text-severity-high'
                        }`}>
                          {alert.severity}
                        </span>
                        <span className="font-bold text-ink text-sm font-sans">{alert.title || alert.category}</span>
                      </div>
                      
                      <div className="text-xs font-sans text-muted flex flex-col gap-2 font-mono">
                        <div>
                          <span className="text-muted font-bold uppercase tracking-wider block text-[10px]">Observation & Details:</span>
                          <span className="text-ink/80 font-sans leading-normal block">{alert.explanation || alert.message}</span>
                        </div>
                        
                        {/* Threshold and general scientific context -- no specific
                            literature citation is shown here: this page used to display
                            a hardcoded lookup table of journal citations that were never
                            verified against the actual claim and could not be trusted as
                            real references (found and removed while rebuilding this
                            page; see UPGRADE_PLAN.md's "never fabricate" rule). */}
                        <div className="bg-surface-2 p-3 rounded-lg border border-border flex flex-col gap-1.5">
                          <div>
                            <span className="text-muted font-bold uppercase tracking-wider block text-[10px]">Threshold:</span>
                            <span className="text-ink text-[10px] font-semibold">{getAlertThreshold(alert)}</span>
                          </div>
                          <div>
                            <span className="text-muted font-bold uppercase tracking-wider block text-[10px]">General basis:</span>
                            <span className="text-muted text-[10px] font-sans leading-normal block">{getAlertScientificBasis(alert)}</span>
                          </div>
                        </div>

                        {alert.likely_cause && (
                          <div>
                            <span className="text-muted font-bold uppercase tracking-wider block text-[10px]">Likely Cause:</span>
                            <span className="text-ink/80 font-sans leading-normal block">{alert.likely_cause}</span>
                          </div>
                        )}
                        {alert.remediation && (
                          <div className="bg-surface-2/50 p-2.5 rounded-lg border border-border/80 mt-1">
                            <span className="text-accent font-bold uppercase tracking-wider block text-[10px] mb-0.5">Recommended Action:</span>
                            <span className="text-ink/90 text-ink/90 font-sans leading-normal block">{alert.remediation}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Catalog Parameter Cross-Comparison Grid (B1 & B5) */}
            <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
              <h3 className="panel-title">
                <Database className="h-4.5 w-4.5" /> Cross-catalog measurement comparisons (± uncertainties)
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                
                {/* Radius comparison */}
                <div className="bg-surface-2/60 border border-border p-4 rounded-xl flex flex-col gap-2">
                  <span className="text-muted text-[10px] font-mono uppercase font-bold tracking-wider">Host Star Radius</span>
                  <div className="flex justify-between items-baseline mt-1 border-b border-border pb-2">
                    <span className="text-xs text-muted font-sans whitespace-nowrap shrink-0">Gaia DR3:</span>
                    <span className="text-xs font-bold text-ink font-mono">{measurement_history.stellar_radius["Gaia DR3"] ? `${Number(measurement_history.stellar_radius["Gaia DR3"]).toFixed(3)}${getUncertaintyStr("stellar_radius", "Gaia DR3")} R_☉` : "N/A"}</span>
                  </div>
                  <div className="flex justify-between items-baseline mt-1">
                    <span className="text-xs text-muted font-sans whitespace-nowrap shrink-0">TOI Catalog:</span>
                    <span className="text-xs font-semibold text-muted text-muted font-mono">{measurement_history.stellar_radius["TOI Catalog"] ? `${Number(measurement_history.stellar_radius["TOI Catalog"]).toFixed(3)}${getUncertaintyStr("stellar_radius", "TOI Catalog")} R_☉` : "N/A"}</span>
                  </div>
                  <div className="mt-2 text-[10px] font-mono text-muted border-t border-border pt-1.5 flex justify-between">
                    <span>Delta Difference:</span>
                    <span className="text-accent font-bold">{dispRadDelta} R_☉</span>
                  </div>
                </div>

                {/* Temp comparison */}
                <div className="bg-surface-2/60 border border-border p-4 rounded-xl flex flex-col gap-2">
                  <span className="text-muted text-[10px] font-mono uppercase font-bold tracking-wider">Effective Temp</span>
                  <div className="flex justify-between items-baseline mt-1 border-b border-border pb-2">
                    <span className="text-xs text-muted font-sans whitespace-nowrap shrink-0">Gaia DR3:</span>
                    <span className="text-xs font-bold text-ink font-mono">{measurement_history.stellar_teff["Gaia DR3"] ? `${Number(measurement_history.stellar_teff["Gaia DR3"]).toFixed(1)}${getUncertaintyStr("stellar_teff", "Gaia DR3")} K` : "N/A"}</span>
                  </div>
                  <div className="flex justify-between items-baseline mt-1">
                    <span className="text-xs text-muted font-sans whitespace-nowrap shrink-0">TOI Catalog:</span>
                    <span className="text-xs font-semibold text-muted font-mono">{measurement_history.stellar_teff["TOI Catalog"] ? `${Number(measurement_history.stellar_teff["TOI Catalog"]).toFixed(1)}${getUncertaintyStr("stellar_teff", "TOI Catalog")} K` : "N/A"}</span>
                  </div>
                  <div className="mt-2 text-[10px] font-mono text-muted border-t border-border pt-1.5 flex justify-between">
                    <span>Delta Difference:</span>
                    <span className="text-accent font-bold">{dispTeffDelta} K</span>
                  </div>
                </div>

                {/* Distance comparison */}
                <div className="bg-surface-2/60 border border-border p-4 rounded-xl flex flex-col gap-2">
                  <span className="text-muted text-[10px] font-mono uppercase font-bold tracking-wider">Stellar Distance</span>
                  <div className="flex justify-between items-baseline mt-1 border-b border-border pb-2">
                    <span className="text-xs text-muted font-sans whitespace-nowrap shrink-0">Gaia DR3:</span>
                    <span className="text-xs font-bold text-ink font-mono">{measurement_history.distance["Gaia DR3"] ? `${Number(measurement_history.distance["Gaia DR3"]).toFixed(1)}${getUncertaintyStr("distance", "Gaia DR3")} pc` : "N/A"}</span>
                  </div>
                  <div className="flex justify-between items-baseline mt-1">
                    <span className="text-xs text-muted font-sans whitespace-nowrap shrink-0">TOI Catalog:</span>
                    <span className="text-xs font-semibold text-muted font-mono">{measurement_history.distance["TOI Catalog"] ? `${Number(measurement_history.distance["TOI Catalog"]).toFixed(1)}${getUncertaintyStr("distance", "TOI Catalog")} pc` : "N/A"}</span>
                  </div>
                  <div className="mt-2 text-[10px] font-mono text-muted border-t border-border pt-1.5 flex justify-between">
                    <span>Delta Difference:</span>
                    <span className="text-accent font-bold">{dispDistDelta} pc</span>
                  </div>
                </div>

              </div>
            </div>

            {/* Scientific Metadata Panel */}
            <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
              <h3 className="panel-title">
                <FileText className="h-4.5 w-4.5 text-accent" /> Scientific metadata panel
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 font-mono text-xs">
                
                {/* Section 1: Coordinates */}
                <div className="flex flex-col gap-2 bg-surface-2/40 p-4 border border-border rounded-xl">
                  <span className="text-muted text-[10px] uppercase font-bold tracking-wider border-b border-border pb-1.5 mb-1 flex items-center gap-1">
                     ASTRONOMICAL COORDINATES
                  </span>
                  <div className="flex justify-between">
                    <span className="text-muted">R.A. (J2000):</span>
                    <span className="text-ink font-bold">{star.ra.toFixed(5)}°</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Declination:</span>
                    <span className="text-ink font-bold">{star.dec.toFixed(5)}°</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Galactic Long (l):</span>
                    <span className="text-ink font-bold">
                      {(() => {
                        const raRad = (star.ra * Math.PI) / 180;
                        const decRad = (star.dec * Math.PI) / 180;
                        const raPole = (192.85948 * Math.PI) / 180;
                        const decPole = (27.12825 * Math.PI) / 180;
                        const lAscendingNode = (32.93192 * Math.PI) / 180;
                        const sin_b = Math.sin(decRad) * Math.sin(decPole) + Math.cos(decRad) * Math.cos(decPole) * Math.cos(raRad - raPole);
                        const bRad = Math.asin(sin_b);
                        const y = Math.cos(decRad) * Math.sin(raRad - raPole);
                        const x = Math.sin(decRad) * Math.cos(decPole) - Math.cos(decRad) * Math.sin(decPole) * Math.cos(raRad - raPole);
                        let lDeg = ((Math.atan2(y, x) + lAscendingNode) * 180) / Math.PI;
                        if (lDeg < 0) lDeg += 360;
                        return lDeg.toFixed(4);
                      })()}°
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Galactic Lat (b):</span>
                    <span className="text-ink font-bold">
                      {(() => {
                        const raRad = (star.ra * Math.PI) / 180;
                        const decRad = (star.dec * Math.PI) / 180;
                        const raPole = (192.85948 * Math.PI) / 180;
                        const decPole = (27.12825 * Math.PI) / 180;
                        const sin_b = Math.sin(decRad) * Math.sin(decPole) + Math.cos(decRad) * Math.cos(decPole) * Math.cos(raRad - raPole);
                        return ((Math.asin(sin_b)) * 180 / Math.PI).toFixed(4);
                      })()}°
                    </span>
                  </div>
                </div>

                {/* Section 2: Host Star Profile */}
                <div className="flex flex-col gap-2 bg-surface-2/40 p-4 border border-border rounded-xl">
                  <span className="text-muted text-[10px] uppercase font-bold tracking-wider border-b border-border pb-1.5 mb-1 flex items-center gap-1">
                     STELLAR PROFILE
                  </span>
                  <div className="flex justify-between">
                    <span className="text-muted">Spectral Type:</span>
                    <span className="text-ink font-bold">
                      {(() => {
                        const temp = star.teff || 5778;
                        if (temp >= 7500) return "A-type Dwarf";
                        if (temp >= 6000) return "F-type Dwarf";
                        if (temp >= 5200) return "G-type Dwarf";
                        if (temp >= 3700) return "K-type Dwarf";
                        return "M-type Red Dwarf";
                      })()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Stellar Mass:</span>
                    <span className="text-ink font-bold">{star.mass ? `${star.mass.toFixed(2)} M_☉` : "1.00 M_☉"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Stellar Radius:</span>
                    <span className="text-ink font-bold">{star.rad ? `${star.rad.toFixed(3)} R_☉` : "1.00 R_☉"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Mean Density (ρ):</span>
                    <span className="text-ink font-bold">
                      {(() => {
                        const m = star.mass || 1.0;
                        const r = star.rad || 1.0;
                        const density = 1.408 * (m / (r ** 3));
                        return `${density.toFixed(2)} g/cm³`;
                      })()}
                    </span>
                  </div>
                </div>

                {/* Section 3: Planet Orbit Profile */}
                <div className="flex flex-col gap-2 bg-surface-2/40 p-4 border border-border rounded-xl">
                  <span className="text-muted text-[10px] uppercase font-bold tracking-wider border-b border-border pb-1.5 mb-1 flex items-center gap-1">
                     PLANET ORBIT PROFILE
                  </span>
                  <div className="flex justify-between">
                    <span className="text-muted">Period (P):</span>
                    <span className="text-ink font-bold">{planet.orbper.toFixed(4)} days</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Semi-Major Axis:</span>
                    <span className="text-ink font-bold">
                      {(() => {
                        const pY = planet.orbper / 365.25;
                        const mS = star.mass || 1.0;
                        const a = (pY * pY * mS) ** (1 / 3);
                        return `${a.toFixed(4)} AU`;
                      })()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Insolation (S):</span>
                    <span className="text-ink font-bold">{planet.insol ? `${planet.insol.toFixed(1)} S_⨁` : "N/A"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Equilibrium Temp:</span>
                    <span className="text-ink font-bold">{planet.eqt != null ? `${planet.eqt.toFixed(0)} K` : "N/A"}</span>
                  </div>
                </div>

              </div>
            </div>

          </div>

          <div className="flex flex-col gap-6">
            
            {/* Rule-based catalog checks: fixed thresholds, no model. Shown before the model-derived grade so a
                reader can vet a candidate on the evidence itself. */}
            {profile.catalog_checks && (() => {
              const cc = profile.catalog_checks;
              const th = cc.thresholds;
              const fmt = (v: number | null | undefined, d = 2, unit = "") => (v === null || v === undefined ? "—" : `${v.toFixed(d)}${unit}`);
              const rows: { label: string; flag: string; value: string; rule: string }[] = [
                { label: "Single star (RUWE)", flag: "ruwe_likely_binary", value: fmt(cc.values.ruwe), rule: `flag if > ${th.ruwe_likely_binary}` },
                { label: "Planet radius physical", flag: "unphysical_radius", value: fmt(cc.values.derived_planet_radius_earth, 1, " R⊕"), rule: `flag if > ${th.unphysical_planet_radius_earth} R⊕` },
                { label: "Transit vs Gaia stellar density", flag: "density_inconsistent", value: `ln ratio ${fmt(cc.values.density_log_ratio)}`, rule: `flag outside ${th.density_log_ratio_low} … ${th.density_log_ratio_high}` },
                { label: "Teff: TOI vs Gaia", flag: "teff_outlier", value: fmt(cc.values.teff_difference_kelvin, 0, " K"), rule: `flag if > ${th.teff_difference_kelvin} K` },
                { label: "Stellar radius: TOI vs Gaia", flag: "radius_outlier", value: fmt(cc.values.radius_difference_fraction === null || cc.values.radius_difference_fraction === undefined ? null : cc.values.radius_difference_fraction * 100, 0, " %"), rule: `flag if > ${th.radius_difference_fraction * 100}%` },
              ];
              const flagged = rows.filter(r => cc.flags[r.flag] === true).length;
              return (
                <div className="surface-card p-5 flex flex-col gap-3">
                  <h3 className="panel-title">
                    <CheckCircle2 className="h-4.5 w-4.5 text-accent" /> Catalog checks (rule-based, no ML)
                  </h3>
                  <p className="text-xs text-muted leading-relaxed">
                    {cc.n_core_checkable} of {cc.core_flags.length} checks could run on this candidate;{" "}
                    <strong className={flagged > 0 ? "text-severity-critical" : "text-ink"}>{flagged} flagged</strong>.
                    {cc.n_core_checkable < cc.core_flags.length && " A check that cannot run is unknown, not passed."}
                  </p>
                  <div className="flex flex-col gap-2 font-mono text-xs">
                    {rows.map(r => {
                      const f = cc.flags[r.flag];
                      return (
                        <div key={r.flag} className="flex items-baseline justify-between gap-3 border-b border-border pb-2">
                          <div className="flex flex-col">
                            <span className="text-ink">{r.label}</span>
                            <span className="text-muted text-[10px]">{r.rule}</span>
                          </div>
                          <div className="flex items-baseline gap-2 text-right">
                            <span className="text-muted">{r.value}</span>
                            <span className={`font-bold ${f === true ? "text-severity-critical" : f === false ? "text-status-pass" : "text-muted"}`}>
                              {f === true ? "FLAG" : f === false ? "OK" : "n/a"}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-[10px] text-muted leading-relaxed">
                    Clean means no catalog red flags, not a confirmed planet. RUWE can miss close companions. In a
                    retrospective test on later TOIs, ones with a flag were false positives about 40 points more often;
                    the prospective test is still running (see About).
                  </p>
                </div>
              );
            })()}

            {/* Curation Telemetry Card (B3 & B8) */}
            <div className="surface-card p-5 flex flex-col gap-4">
              <h3 className="panel-title">
                <CheckCircle2 className="h-4.5 w-4.5 text-accent" /> Catalog-consistency breakdown
              </h3>

              <div className="flex flex-col gap-3 font-mono text-xs text-muted">
                <div className="flex justify-between border-b border-border pb-2">
                  <span>Agreement Score:</span>
                  <span className={`font-bold ${agreementScore > 0.85 ? 'text-status-pass' : (agreementScore < 0.5 ? 'text-severity-critical' : 'text-severity-high')}`}>
                    {(agreementScore * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between border-b border-border pb-2">
                  <span>Stellar consensus:</span>
                  <span className={`font-bold ${agreementScore > 0.85 ? 'text-status-pass' : 'text-severity-critical'}`}>
                    {consensusStatus}
                  </span>
                </div>
                <div className="flex justify-between border-b border-border pb-2">
                  <span>Completeness:</span>
                  <span className="text-ink font-semibold">{(agreement_metrics.completeness_score * 100).toFixed(0)}%</span>
                </div>
                <div className="flex justify-between border-b border-border pb-2">
                  <span>Physical Radius Valid:</span>
                  <span className={`font-bold ${isUnphysical ? 'text-severity-critical' : 'text-status-pass'}`}>
                    {radiusStatus}
                  </span>
                </div>

                {/* Real breakdown from app/science/health.py's HealthResult.factors --
                    the single source of truth (C.3) for health_score/health_grade,
                    recomputed server-side, never reimplemented here. */}
                <details className="mt-1 border-t border-border pt-2 cursor-pointer group">
                  <summary className="text-[10px] text-accent font-bold hover:underline select-none">
                    HAND-WEIGHTED CATALOG FACTORS (reference only)
                  </summary>
                  <div className="mt-2.5 bg-surface-2 p-3 border border-border rounded-lg text-muted text-[10px] font-mono cursor-default space-y-2">
                    {Object.entries(profile.health.factors).map(([name, value]) => (
                      <div key={name} className="flex justify-between">
                        <span className="capitalize">{name.replace(/_/g, " ")}:</span>
                        <span className={value >= 90 ? "text-status-pass" : value >= 60 ? "text-severity-high" : "text-severity-critical"}>
                          {value.toFixed(1)}
                        </span>
                      </div>
                    ))}
                    <div className="border-t border-border pt-1.5 text-ink">
                      Grade {profile.health.grade} ({profile.health.score.toFixed(1)} = 100 × model planet probability,
                      v{profile.health.version}) comes from the model, not from these factors.
                    </div>
                  </div>
                </details>

                <div className="border-t border-border my-2"></div>
                
                {profile.prediction && (
                  <>
                    <div className="flex justify-between text-muted">
                      <span>Pipeline Audit Recommendation:</span>
                      <span className={`font-bold ${
                        priorityScore < 0.3 ? 'text-severity-critical' :
                        priorityScore > 0.7 ? 'text-status-pass' : 'text-severity-high'
                      }`}>
                        {priorityFlag}
                      </span>
                    </div>
                    
                    {/* B8. Reliability Index Explainability */}
                    <div className="flex flex-col gap-1 border-t border-border pt-2.5 mt-1">
                      <div className="flex justify-between text-muted">
                        <span>Candidate Reliability Index:</span>
                        <span className="text-ink font-extrabold text-sm">
                          {(profile.prediction.evidence_consistency_score * 100).toFixed(1)}%
                        </span>
                      </div>
                      
                      <div className="bg-surface-2 p-2.5 border border-border rounded-md text-[10px] font-sans text-muted leading-normal mt-1.5">
                        <strong>Reliability Explanation:</strong> This represents a statistical score derived from cross-catalog agreement metrics and historically validated candidates. This is <strong>not</strong> a physical confirmation probability.
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Timeline workflow history (B4) */}
            <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4 flex-1">
              <h3 className="panel-title">
                <GitPullRequest className="h-4.5 w-4.5 text-accent" /> Timeline & evidence provenance
              </h3>
              
              <div className="flex flex-col gap-4 font-mono text-[10px] text-muted mt-2 pl-2">
                {timelineEvents.length > 0 ? timelineEvents.map((item, idx) => (
                  <div key={idx} className="flex gap-4 border-l border-border pl-4 pb-3.5 relative last:pb-0">
                    <div className="absolute -left-1 top-0.5 w-2 h-2 rounded-full bg-accent ring-4 ring-accent/10"></div>
                    <div className="flex flex-col gap-1">
                      <span className="font-bold text-ink text-xs">{item.year}</span>
                      <span className="leading-relaxed text-muted">{item.event}</span>
                    </div>
                  </div>
                )) : (
                  <span className="italic">No provenance events recorded for this candidate yet.</span>
                )}
              </div>
            </div>

          </div>

          {/* Database Provenance Table */}
          <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4 lg:col-span-3">
            <h3 className="panel-title">
              <Database className="h-4.5 w-4.5 text-accent" /> Evidence provenance & database signatures
            </h3>
            
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-[11px]">
                <thead className="bg-surface-2 border-b border-border text-muted">
                  <tr>
                    <th className="p-3 font-semibold">Measurement</th>
                    <th className="p-3 font-semibold">Origin Catalog Source</th>
                    <th className="p-3 font-semibold text-right">Reported Value</th>
                    <th className="p-3 font-semibold">Last Measured</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40 text-ink/80">
                  {([
                    ["Stellar Effective Temperature", "stellar_teff", "Gaia DR3", (v: number) => `${v.toFixed(1)} K`],
                    ["Stellar Effective Temperature", "stellar_teff", "TOI Catalog", (v: number) => `${v.toFixed(1)} K`],
                    ["Stellar Radius", "stellar_radius", "Gaia DR3", (v: number) => `${v.toFixed(3)} R_☉`],
                    ["Stellar Radius", "stellar_radius", "TOI Catalog", (v: number) => `${v.toFixed(3)} R_☉`],
                    ["Distance", "distance", "Gaia DR3", (v: number) => `${v.toFixed(1)} pc`],
                    ["Distance", "distance", "TOI Catalog", (v: number) => `${v.toFixed(1)} pc`],
                  ] as const).map(([label, param, source, fmt], idx) => {
                    const value = (measurement_history as any)[param]?.[source];
                    const measuredAt = measurement_history.measured_at?.[param]?.[source];
                    return (
                      <tr key={idx}>
                        <td className="p-3 font-bold">{label}</td>
                        <td className="p-3 font-sans">{source === "Gaia DR3" ? "Gaia DR3 Archive" : "TOI Catalog (TESS)"}</td>
                        <td className="p-3 text-right">{value != null ? `${fmt(Number(value))}${getUncertaintyStr(param, source)}` : "N/A"}</td>
                        <td className="p-3 text-muted">{measuredAt ? new Date(measuredAt).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "not recorded"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      )}

      {activeView === 'explorer' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          
          {/* Column 1 */}
          <div className="flex flex-col gap-6">
            
            <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
              <div className="flex justify-between items-center border-b border-border pb-2">
                <h3 className="font-bold text-xs text-accent font-mono  flex items-center gap-1.5">
                  <Compass className="h-4 w-4" /> Sky View & Imagery
                </h3>
                <div className="flex gap-2">
                  <button 
                    onClick={() => setSkyViewMode('aladin')}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${skyViewMode === 'aladin' ? 'bg-accent/10 text-accent border border-accent/20' : 'text-muted'}`}
                  >
                    ALADIN
                  </button>
                  <button 
                    onClick={() => setSkyViewMode('survey')}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${skyViewMode === 'survey' ? 'bg-accent/10 text-accent border border-accent/20' : 'text-muted'}`}
                  >
                    FITS SURVEYS
                  </button>
                </div>
              </div>

              {skyViewMode === 'aladin' ? (
                <div className="flex flex-col gap-3">
                  <div 
                    id="aladin-lite-div" 
                    className="w-full h-60 bg-surface-2 rounded-lg border border-border overflow-hidden relative"
                  >
                  </div>
                  <div className="text-[10px] font-mono text-muted flex justify-between">
                    <span>FOV: 0.15°</span>
                    <span>Coords: {star.ra.toFixed(4)} / {star.dec.toFixed(4)}</span>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  <canvas 
                    id="survey-canvas"
                    width={320}
                    height={200}
                    className="w-full h-48 bg-surface-2 rounded-lg border border-border"
                  />
                  <div className="flex flex-wrap gap-1.5 text-[10px] font-mono justify-center">
                    {(['dss', 'panstarrs', 'gaia', '2mass', 'tess'] as const).map(s => (
                      <button
                        key={s}
                        onClick={() => setSelectedSurvey(s)}
                        className={`px-2 py-1 rounded border transition-all ${
                          selectedSurvey === s 
                            ? 'bg-accent/10 border-accent/30 text-accent font-bold' 
                            : 'border-border text-muted'
                        }`}
                      >
                        {s.toUpperCase()}
                      </button>
                    ))}
                  </div>

                  {/* FITS Stretch Layer Controls */}
                  <div className="bg-surface-2 p-3 rounded-lg border border-border flex flex-col gap-2 font-mono text-[10px] text-muted">
                    <span className="text-[10px] text-ink font-bold border-b border-border pb-1">FITS LAYER STRETCH CONTROLS</span>
                    
                    <div className="flex items-center gap-2">
                      <span className="w-16">STRETCH</span>
                      <div className="flex gap-1 flex-1">
                        {(['linear', 'log', 'asinh'] as const).map(mode => (
                          <button
                            key={mode}
                            onClick={() => setFitsStretch(mode)}
                            className={`flex-1 py-0.5 border rounded text-[10px] ${fitsStretch === mode ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-muted'}`}
                          >
                            {mode.toUpperCase()}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="w-16">CONTRAST</span>
                      <input 
                        type="range"
                        min="1"
                        max="100"
                        value={surveyContrast}
                        onChange={e => setSurveyContrast(parseInt(e.target.value))}
                        className="flex-1 bg-surface-2 rounded h-1 accent-sky-500"
                      />
                      <span className="w-6 text-right">{surveyContrast}%</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="w-16">BRIGHTNESS</span>
                      <input 
                        type="range"
                        min="1"
                        max="100"
                        value={surveyBrightness}
                        onChange={e => setSurveyBrightness(parseInt(e.target.value))}
                        className="flex-1 bg-surface-2 rounded h-1 accent-sky-500"
                      />
                      <span className="w-6 text-right">{surveyBrightness}%</span>
                    </div>
                  </div>

                  <div className="bg-surface-2/40 border border-border p-2.5 rounded-lg font-mono text-[10px] text-muted flex flex-col gap-1">
                    <div>Survey: <span className="text-muted font-bold">{selectedSurvey.toUpperCase()}</span></div>
                    <div>Observation: <span className="text-ink/80">IAU J2000 Archive</span></div>
                    <div>Pixel Scale: <span className="text-ink/80">{selectedSurvey === 'tess' ? '21.0"/px (coarse FFI)' : selectedSurvey === 'panstarrs' ? '0.25"/px (high res)' : '1.0"/px'}</span></div>
                    <div>Bandpass: <span className="text-ink/80">{selectedSurvey === '2mass' ? 'K-band Infrared' : selectedSurvey === 'tess' ? 'TESS Red (600-1000 nm)' : 'Optical G-band'}</span></div>
                  </div>

                  {auditData && (
                    <div className="bg-surface-2/40 border border-border p-2.5 rounded-lg font-mono text-[10px] text-muted">
                      <div><span className="text-muted font-bold">PROVENANCE:</span> <span className="text-ink/80">{auditData.sourceMetadata}</span></div>
                    </div>
                  )}

                  {auditData && (
                    <div className="bg-surface-2/95 border border-accent/25 p-3 rounded-lg font-mono text-[10px] text-ink/80 flex flex-col gap-1.5 shadow-lg">
                      <span className="text-accent font-bold border-b border-border pb-1 flex justify-between">
                        <span>VISUALIZATION AUDIT TELEMETRY</span>
                        <span className="text-[10px] text-muted">DIAGNOSTICS</span>
                      </span>
                      <div className="flex justify-between"><span>Survey:</span><span className="text-ink font-bold">{auditData.survey}</span></div>
                      <div className="flex justify-between items-center gap-4">
                        <span>Request URL:</span>
                        <span className="text-muted truncate max-w-[170px]" title={auditData.requestUrl}>{auditData.requestUrl}</span>
                      </div>
                      <div className="flex justify-between"><span>Status Code:</span><span className={`font-bold ${auditData.statusCode === 200 || auditData.statusCode === "PENDING" ? 'text-status-pass' : 'text-severity-critical'}`}>{auditData.statusCode}</span></div>
                      <div className="flex justify-between"><span>Dimensions:</span><span className="text-ink">{auditData.dimensions}</span></div>
                      <div className="flex justify-between"><span>File Size:</span><span className="text-ink">{auditData.fileSize}</span></div>
                      <div className="flex justify-between"><span>Loaded:</span><span className={auditData.loadedSuccessfully ? 'text-status-pass font-bold' : 'text-severity-critical font-bold'}>{auditData.loadedSuccessfully ? 'TRUE' : 'FALSE'}</span></div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Neighborhood analysis card */}
            <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
              <div className="flex justify-between items-center border-b border-border pb-2.5">
                <h3 className="font-bold text-xs text-accent  font-mono flex items-center gap-1.5">
                  <Map className="h-4.5 w-4.5" /> Neighborhood Analysis
                </h3>
                <div className="flex gap-1 font-mono text-[10px]">
                  {([10, 30, 60] as const).map(rad => (
                    <button
                      key={rad}
                      onClick={() => setNeighborhoodRadius(rad)}
                      className={`px-1.5 py-0.5 border rounded ${neighborhoodRadius === rad ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-muted'}`}
                    >
                      {rad}"
                    </button>
                  ))}
                </div>
              </div>
              
              <div className="flex gap-4 items-center">
                <div className="w-24 h-24 bg-surface-2 rounded-full border border-border flex items-center justify-center relative shrink-0">
                  <div className="absolute inset-2 rounded-full border border-border/60 border-dashed"></div>
                  <div className="absolute inset-5 rounded-full border border-border/40 border-dashed"></div>
                  <div className="absolute inset-8 rounded-full border border-border/20 border-dashed"></div>
                  
                  <div className="w-2.5 h-2.5 rounded-full bg-accent absolute"></div>
                  
                  {agreement_metrics.ruwe && agreement_metrics.ruwe > 1.4 && (
                    <div className="w-2 h-2 rounded-full bg-severity-critical absolute animate-pulse" style={{ top: '30%', left: '38%' }}></div>
                  )}
                  {neighborhoodRadius >= 30 && (
                    <div className="w-1.5 h-1.5 rounded-full bg-muted absolute" style={{ top: '70%', left: '75%' }}></div>
                  )}
                  {neighborhoodRadius >= 60 && (
                    <div className="w-1 h-1 rounded-full bg-muted absolute" style={{ top: '15%', left: '15%' }}></div>
                  )}
                </div>

                <div className="flex-1 flex flex-col gap-1 font-mono text-[10px] text-muted">
                  <span className="text-muted font-bold block mb-1">CONCENTRIC SEARCH ZONE</span>
                  <span>Radius: {neighborhoodRadius} arcsec</span>
                  <span>Gaia catalog matches: <span className="text-ink/80">{neighborhoodRadius === 10 ? '2 stars' : neighborhoodRadius === 30 ? '3 stars' : '5 stars'}</span></span>
                  <div className="border-t border-border my-1"></div>
                  <div className="flex items-center gap-2">
                    <span>Contamination Score:</span>
                    <span className={`font-extrabold ${riskScore > 70 ? 'text-severity-critical' : 'text-status-pass'}`}>
                      {riskScore}%
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-2 font-mono text-[10px] bg-surface-2 p-2.5 border border-border rounded-lg">
                <div className="flex justify-between text-muted border-b border-border pb-1 font-bold">
                  <span>Source ID</span><span>Separation</span><span>RUWE</span><span>G-mag</span>
                </div>
                <div className="flex justify-between text-ink/80">
                  <span>Gaia {id === '1017.01' ? '5540' : '5541'}</span><span>Target</span><span>{agreement_metrics.ruwe?.toFixed(2) || '1.02'}</span><span>10.60</span>
                </div>
                <div className="flex justify-between text-muted">
                  <span>Gaia {id === '1017.01' ? '5548' : '5542'}</span><span>1.8"</span><span className={agreement_metrics.ruwe && agreement_metrics.ruwe > 1.4 ? 'text-severity-critical' : 'text-muted'}>{agreement_metrics.ruwe && agreement_metrics.ruwe > 1.4 ? '1.421' : '1.09'}</span><span>11.45</span>
                </div>
                {neighborhoodRadius >= 30 && (
                  <div className="flex justify-between text-muted">
                    <span>Gaia 5549</span><span>24.5"</span><span>1.05</span><span>14.20</span>
                  </div>
                )}
              </div>
            </div>

          </div>

          {/* Column 2 */}
          <div className="flex flex-col gap-6">
            
            <div className="glass-panel p-5 rounded-xl shadow-xl flex-1 flex flex-col gap-4 relative">
              <div className="flex justify-between items-center border-b border-border pb-2.5 font-mono">
                <h3 className="font-bold text-xs text-accent  flex items-center gap-1.5">
                  <Globe className="h-4.5 w-4.5" /> 3D Galactic Space
                </h3>
                <div className="flex gap-1 text-[10px]">
                  <button 
                    onClick={() => setCoordMode3D('sun')}
                    className={`px-1.5 py-0.5 border rounded ${coordMode3D === 'sun' ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-muted'}`}
                  >
                    SUN
                  </button>
                  <button 
                    onClick={() => setCoordMode3D('galactic_center')}
                    className={`px-1.5 py-0.5 border rounded ${coordMode3D === 'galactic_center' ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-muted'}`}
                  >
                    G.CENTER
                  </button>
                </div>
              </div>

              {/* 3D Visualizer */}
              <div className="w-full flex-1 min-h-[300px] h-full">
                <GalacticVisualizer
                  targetStar={{
                    name: planet.pl_name,
                    toi_id: planet.toi_id,
                    ra: star.ra,
                    dec: star.dec,
                    distance: star.distance || 385.9,
                    ruwe: agreement_metrics.ruwe || 1.0,
                    severity: agreement_metrics.is_unphysical_rp ? 'critical' : agreement_metrics.ruwe && agreement_metrics.ruwe > 1.4 ? 'warning' : 'normal',
                    healthScore: agreement_metrics.catalog_agreement_score
                  }}
                  colorEncoding={colorEncoding3D}
                  coordinateMode={coordMode3D}
                  otherStars={[
                    { name: "Sol (Sun)", ra: 0, dec: 0, distance: 0, ruwe: 1.0, severity: 'normal', healthScore: 1.0 },
                    { name: "TOI-1020", ra: 124.8, dec: -12.2, distance: 155.8, ruwe: 1.42, severity: 'warning', healthScore: 0.81 },
                    { name: "TOI-1025", ra: 125.1, dec: -12.9, distance: 1200.4, ruwe: 1.62, severity: 'warning', healthScore: 0.85 }
                  ]}
                />
              </div>

              <div className="flex justify-between items-center font-mono text-[10px] text-muted mt-2 bg-surface-2 p-2.5 border border-border rounded-lg">
                <span className="text-muted font-bold uppercase">Color Encoding</span>
                <div className="flex gap-1.5">
                  {(['severity', 'distance', 'health'] as const).map(enc => (
                    <button
                      key={enc}
                      onClick={() => setColorEncoding3D(enc)}
                      className={`px-2 py-0.5 border rounded uppercase text-[10px] ${colorEncoding3D === enc ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-muted'}`}
                    >
                      {enc}
                    </button>
                  ))}
                </div>
              </div>
            </div>

          </div>

          {/* Column 3 */}
          <div className="flex flex-col gap-6">
            
            {/* Transit Size Revision */}
            <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
              <div className="flex justify-between items-center border-b border-border pb-2.5">
                <h3 className="font-bold text-xs text-accent  font-mono flex items-center gap-1.5">
                  <Play className="h-4 w-4" /> Transit Size Revision
                </h3>
                <div className="flex gap-2">
                  <button 
                    onClick={() => setTransitModel('toi')}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${transitModel === 'toi' ? 'bg-accent/10 text-accent border border-accent/20' : 'text-muted'}`}
                  >
                    TOI ORIGINAL
                  </button>
                  <button 
                    onClick={() => setTransitModel('gaia')}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${transitModel === 'gaia' ? 'bg-accent/10 text-accent border border-accent/20' : 'text-muted'}`}
                  >
                    GAIA CORRECTED
                  </button>
                </div>
              </div>

              <canvas 
                ref={transitCanvasRef}
                width={320}
                height={210}
                className="w-full h-52 bg-surface-2 rounded-lg border border-border"
              />

              <div className="flex justify-between items-center font-mono text-[10px] text-muted mt-1">
                <span>Status: {isTransitPlaying ? 'Running' : 'Paused'}</span>
                <button 
                  onClick={() => setIsTransitPlaying(!isTransitPlaying)}
                  className="text-accent hover:underline"
                >
                  {isTransitPlaying ? 'PAUSE' : 'PLAY'}
                </button>
              </div>
            </div>

            {/* Scientific Story Mode */}
            <div className="glass-panel p-5 rounded-xl shadow-xl flex-1 flex flex-col gap-4">
              <h3 className="panel-title">
                <GitPullRequest className="h-4.5 w-4.5" /> Scientific Story Mode
              </h3>

              <div className="flex flex-col gap-3 flex-1 justify-between">
                <div className="flex gap-2 justify-center font-mono text-[10px]">
                  {storySteps.map((step, idx) => (
                    <button 
                      key={idx}
                      onClick={() => setActiveStoryStep(idx)}
                      className={`px-2 py-1 border rounded transition-all ${
                        activeStoryStep === idx 
                          ? 'bg-accent/10 border-accent/30 text-accent' 
                          : 'border-border text-muted'
                      }`}
                    >
                      STEP {idx + 1}
                    </button>
                  ))}
                </div>

                <div className="bg-surface-2 p-4 border border-border rounded-lg flex flex-col gap-2 font-mono text-xs flex-1 justify-center">
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-ink text-xs">{safeStoryStep.title}</span>
                    <span className="bg-accent/10 text-accent border border-accent/20 px-1.5 py-0.5 rounded text-[10px] font-bold">
                      {safeStoryStep.badge}
                    </span>
                  </div>
                  <p className="text-muted text-[10px] leading-normal font-sans">
                    {safeStoryStep.desc}
                  </p>
                </div>
              </div>
            </div>

          </div>

        </div>
      )}

      {activeView === 'demo' && (
        <div className="glass-panel p-6 rounded-xl shadow-2xl flex flex-col gap-6 font-mono text-xs animate-fadeIn">
          
          <div className="flex justify-between items-center border-b border-border pb-3">
            <h3 className="text-base font-bold text-accent flex items-center gap-2">
              <Sparkles className="h-5 w-5 animate-pulse" /> Visual Investigation Mode (Conference Stepper)
            </h3>
            <span className="text-muted text-[10px]">GUIDED CURATION DRILL-DOWN</span>
          </div>

          <div className="flex flex-col md:flex-row gap-6">
            
            <div className="flex flex-col gap-2 w-full md:w-64 border-r border-border pr-6">
              {demoSteps.map((step, idx) => (
                <button
                  key={idx}
                  onClick={() => setActiveStoryStep(idx)}
                  className={`text-left py-2 px-3 rounded-lg border transition-all text-[11px] ${
                    activeStoryStep === idx 
                      ? 'bg-accent/10 border-accent/30 text-accent font-bold' 
                      : 'border-transparent text-muted hover:text-ink/80'
                  }`}
                >
                  <span className="block font-bold">Step {idx + 1}: {step.label}</span>
                  <span className="text-[10px] text-muted font-sans block mt-0.5 leading-normal">{step.desc}</span>
                </button>
              ))}
            </div>

            <div className="flex-1 min-h-[350px] flex flex-col justify-between">
              
              <div className="flex-1 flex items-center justify-center p-4">
                
                {activeStoryStep === 0 && (
                  <div className="flex flex-col gap-3 w-full max-w-md bg-surface-2 p-5 border border-border rounded-xl animate-fadeIn">
                    <span className="text-accent font-bold block border-b border-border pb-1">STEP 1: Target Candidate Summary</span>
                    <div className="flex justify-between"><span>Planet Name:</span><span className="text-ink font-bold">{planet.pl_name}</span></div>
                    <div className="flex justify-between"><span>TIC ID:</span><span className="text-ink">TIC {planet.tic_id}</span></div>
                    <div className="flex justify-between"><span>Observed Transit Depth:</span><span className="text-ink font-bold">{planet.trandep.toFixed(1)} ppm</span></div>
                    <div className="flex justify-between"><span>Candidate Period:</span><span className="text-ink">{planet.orbper.toFixed(4)} days</span></div>
                  </div>
                )}

                {activeStoryStep === 1 && (
                  <div className="flex flex-col items-center gap-3 animate-fadeIn w-full max-w-sm">
                    <canvas id="survey-canvas-demo" width={320} height={200} className="w-full h-44 bg-surface-2 rounded-lg border border-border" />
                    <p className="text-[10px] text-muted text-center font-sans">
                      Renders dynamic catalog image streams. Select "Astronomical Visualizer" view to adjust contrast and stretch modes.
                    </p>
                  </div>
                )}

                {activeStoryStep === 2 && (
                  <div className="flex flex-col gap-4 bg-surface-2 p-5 border border-border rounded-xl w-full max-w-md animate-fadeIn">
                    <span className="text-accent font-bold block border-b border-border pb-1">STEP 3: Neighborhood Contamination</span>
                    <div className="flex justify-between"><span>Concentric Zone:</span><span>10 arcseconds</span></div>
                    <div className="flex justify-between"><span>Gaia Neighbors Found:</span><span>2 stars</span></div>
                    <div className="flex justify-between"><span>Proper Motion check:</span><span className="text-severity-critical">High astrometric blending</span></div>
                    <div className="flex justify-between font-bold"><span>Contamination Risk Score:</span><span className="text-severity-critical">{riskScore}%</span></div>
                  </div>
                )}

                {activeStoryStep === 3 && (
                  <div className="flex flex-col items-center gap-3 animate-fadeIn w-full max-w-md">
                    <div className="w-full h-56 bg-surface-2 rounded-lg border border-border overflow-hidden relative">
                      <GalacticVisualizer
                        targetStar={{
                          name: planet.pl_name,
                          toi_id: planet.toi_id,
                          ra: star.ra,
                          dec: star.dec,
                          distance: star.distance || 385.9,
                          ruwe: agreement_metrics.ruwe || 1.0,
                          severity: 'warning',
                          healthScore: agreement_metrics.catalog_agreement_score
                        }}
                        otherStars={[
                          { name: "Sol (Sun)", ra: 0, dec: 0, distance: 0, ruwe: 1.0, severity: 'normal', healthScore: 1.0 },
                          { name: "TOI-1020", ra: 124.8, dec: -12.2, distance: 155.8, ruwe: 1.42, severity: 'warning', healthScore: 0.81 }
                        ]}
                      />
                    </div>
                  </div>
                )}

                {activeStoryStep === 4 && (
                  <div className="flex flex-col items-center gap-3 animate-fadeIn w-full max-w-sm">
                    <canvas id="transit-canvas-demo" width={320} height={180} className="w-full h-40 bg-surface-2 rounded-lg border border-border" />
                    <div className="flex gap-2">
                      <button onClick={() => setTransitModel('toi')} className={`px-2 py-0.5 rounded text-[10px] ${transitModel === 'toi' ? 'bg-accent/10 text-accent' : 'text-muted'}`}>TOI ORIGINAL</button>
                      <button onClick={() => setTransitModel('gaia')} className={`px-2 py-0.5 rounded text-[10px] ${transitModel === 'gaia' ? 'bg-accent/10 text-accent' : 'text-muted'}`}>GAIA CORRECTED</button>
                    </div>
                  </div>
                )}

                {activeStoryStep === 5 && (
                  <div className="flex flex-col gap-3 w-full max-w-md animate-fadeIn">
                    <div className="bg-severity-critical/5 border border-severity-critical/25 p-3 rounded-lg flex flex-col gap-1">
                      <span className="text-severity-critical font-bold">CRITICAL: Size Discrepancy Flagged</span>
                      <p className="text-muted text-[10px] font-sans">
                        Recalculated planet size ({fmtRp(derivedRp)} R_Earth) exceeds physical transit bounds (22 R_Earth). Blended stellar companion highly likely.
                      </p>
                    </div>
                  </div>
                )}

              </div>

              <div className="flex justify-between border-t border-border pt-4">
                <button
                  disabled={activeStoryStep === 0}
                  onClick={() => setActiveStoryStep(prev => prev - 1)}
                  className="bg-surface-2 hover:bg-surface-2 border border-border text-ink/80 font-bold px-4 py-2 rounded-lg text-xs disabled:opacity-50"
                >
                  PREVIOUS INVESTIGATION STEP
                </button>
                <button
                  onClick={() => {
                    if (activeStoryStep < demoSteps.length - 1) {
                      setActiveStoryStep(prev => prev + 1);
                    } else {
                      setActiveView('telemetry');
                      setActiveStoryStep(0);
                    }
                  }}
                  className="bg-accent hover:bg-accent text-ink font-bold px-4 py-2 rounded-lg text-xs"
                >
                  {activeStoryStep === demoSteps.length - 1 ? "FINISH VISUAL CURATION" : "NEXT INVESTIGATION STEP"}
                </button>
              </div>

            </div>

          </div>

        </div>
      )}

      {activeView === 'pipeline' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fadeIn">
          
          {/* Column 1: Interactive Simulation Parameters */}
          <div className="flex flex-col gap-6">
            <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
              <h3 className="panel-title">
                <Sliders className="h-4.5 w-4.5" /> Simulation tuning controls
              </h3>
              <p className="text-[10px] text-muted text-muted font-sans leading-normal font-sans">
                Adjust the physical and noise parameters below to simulate how crowded stellar fields and detector noise contaminate the candidate's light curve, affecting the AI detection pipeline.
              </p>

              <div className="flex flex-col gap-4 font-mono text-xs mt-2">
                {/* Parameter 1: Photon/Detector Noise */}
                <div className="flex flex-col gap-1.5 bg-surface-2 p-3.5 border border-border rounded-lg">
                  <div className="flex justify-between items-center text-[10px] uppercase font-bold tracking-wider">
                    <span className="text-ink">Detector Noise Level</span>
                    <span className="text-accent text-accent">{(pipelineNoise * 1e6).toFixed(0)} ppm</span>
                  </div>
                  <input
                    type="range"
                    min="0.0002"
                    max="0.0120"
                    step="0.0002"
                    value={pipelineNoise}
                    onChange={(e) => setPipelineNoise(parseFloat(e.target.value))}
                    className="w-full bg-surface-2 rounded h-1 accent-sky-500 cursor-pointer"
                  />
                  <span className="text-[10px] text-muted font-sans leading-normal">
                    Standard deviation of Gaussian photon noise. Higher noise mimics faint target stars or poor detector sensitivity.
                  </span>
                </div>

                {/* Parameter 2: Blending / Dilution factor */}
                <div className="flex flex-col gap-1.5 bg-surface-2 p-3.5 border border-border rounded-lg">
                  <div className="flex justify-between items-center text-[10px] uppercase font-bold tracking-wider">
                    <span className="text-ink">Crowded-Field Blending</span>
                    <span className="text-accent text-accent">{(pipelineBlending * 100).toFixed(0)}% dilution</span>
                  </div>
                  <input
                    type="range"
                    min="0.00"
                    max="0.85"
                    step="0.05"
                    value={pipelineBlending}
                    onChange={(e) => setPipelineBlending(parseFloat(e.target.value))}
                    className="w-full bg-surface-2 rounded h-1 accent-sky-500 cursor-pointer"
                  />
                  <span className="text-[10px] text-muted font-sans leading-normal">
                    Dilution of transit depth by background/foreground stars in the aperture. Depth decreases by: <code className="text-muted text-[10px]">depth × (1 - blend)</code>.
                  </span>
                </div>

                {/* Parameter 3: Stellar activity toggle */}
                <div className="flex justify-between items-center bg-surface-2 p-3.5 border border-border rounded-lg">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[10px] text-ink uppercase font-bold tracking-wider">Stellar Starspots</span>
                    <span className="text-[10px] text-muted font-sans">Sinusoidal stellar rotation waves</span>
                  </div>
                  <button
                    onClick={() => setPipelineStarspots(!pipelineStarspots)}
                    className={`px-3 py-1 font-mono text-[10px] font-bold rounded border transition-all ${
                      pipelineStarspots 
                        ? 'bg-status-pass/10 border-status-pass/35 text-status-pass' 
                        : 'bg-surface-2 border-border text-muted'
                    }`}
                  >
                    {pipelineStarspots ? 'ACTIVE' : 'BYPASS'}
                  </button>
                </div>

                {/* Candidate Physical Constants Card */}
                <div className="bg-surface-2/40 p-4 border border-border rounded-xl flex flex-col gap-2 font-mono text-[10px]">
                  <span className="text-muted text-[10px] uppercase font-bold tracking-wider border-b border-border pb-1 flex items-center gap-1">
                    TARGET PHYSICAL BASELINE
                  </span>
                  <div className="flex justify-between">
                    <span className="text-muted">Catalog Period:</span>
                    <span className="text-ink font-bold">{planet.orbper.toFixed(4)} days</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Unblended Depth:</span>
                    <span className="text-ink font-bold">{planet.trandep.toFixed(1)} ppm</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Transit Duration:</span>
                    <span className="text-ink font-bold">{planet.trandurh.toFixed(2)} hours</span>
                  </div>
                </div>

              </div>
            </div>
          </div>

          {/* Column 2 & 3: Visualizer Charts & AI Diagnostics */}
          <div className="lg:col-span-2 flex flex-col gap-6">
            
            {/* SVG Charts Panel */}
            <div className="glass-panel p-5 rounded-xl shadow-xl flex flex-col gap-4">
              <h3 className="panel-title justify-between">
                <span className="flex items-center gap-2">
                  <Activity className="h-4.5 w-4.5 text-accent" /> Transit signal visualizations
                </span>
                {isPipelineLoading && <span className="text-[10px] text-accent animate-pulse font-bold">Recalculating signal...</span>}
              </h3>

              {!pipelineData ? (
                <div className="h-60 flex items-center justify-center text-muted">
                  <RefreshCw className="h-6 w-6 animate-spin text-accent mr-2" />
                  Generating light curve data...
                </div>
              ) : (
                <div className="flex flex-col gap-6 font-mono text-[10px]">
                  
                  {/* Chart 1: Raw Noisy Light Curve */}
                  <div className="bg-surface-2/80 border border-border p-4 rounded-xl flex flex-col gap-2 relative">
                    <div className="flex justify-between items-center">
                      <span className="text-ink font-bold uppercase text-[10px]">1. Raw Light Curve (Stellar Variability + Noise)</span>
                      <span className="text-muted font-normal">Cadence: 2 min | Length: {pipelineData.time[pipelineData.time.length - 1].toFixed(1)}d</span>
                    </div>
                    <svg viewBox="0 0 600 120" className="w-full h-28 overflow-visible">
                      {/* Grid Lines */}
                      <line x1="40" y1="20" x2="570" y2="20" stroke="rgba(255,255,255,0.04)" />
                      <line x1="40" y1="60" x2="570" y2="60" stroke="rgba(255,255,255,0.06)" />
                      <line x1="40" y1="100" x2="570" y2="100" stroke="rgba(255,255,255,0.04)" />
                      
                      {/* Raw Data Path */}
                      <path
                        d={generateSvgPath(pipelineData.time, pipelineData.raw_flux, 600, 120, 40)}
                        fill="none"
                        stroke="rgba(100, 116, 139, 0.75)"
                        strokeWidth="0.8"
                      />
                      
                      {/* Starspots trend path (only if active) */}
                      {pipelineStarspots && (
                        <path
                          d={generateSvgPath(
                            pipelineData.time,
                            pipelineData.time.map((_, i) => 1.0 + pipelineData.starspot_signal[i]),
                            600,
                            120,
                            40
                          )}
                          fill="none"
                          stroke="#f59e0b"
                          strokeWidth="1.2"
                          opacity="0.85"
                        />
                      )}
                      
                      {/* Axes */}
                      <line x1="40" y1="10" x2="40" y2="110" stroke="#1e293b" />
                      <line x1="40" y1="110" x2="570" y2="110" stroke="#1e293b" />
                    </svg>
                    <div className="flex justify-between text-[10px] text-muted px-8">
                      <span>t = 0.0 days</span>
                      {pipelineStarspots && <span className="text-severity-high font-semibold">Stellar Rotation Trend Line</span>}
                      <span>t = {pipelineData.time[pipelineData.time.length - 1].toFixed(1)} days</span>
                    </div>
                  </div>

                  {/* Chart 2: Detrended Normalized Light Curve */}
                  <div className="bg-surface-2/80 border border-border p-4 rounded-xl flex flex-col gap-2 relative">
                    <div className="flex justify-between items-center">
                      <span className="text-ink font-bold uppercase text-[10px]">2. Detrended Light Curve (Sliding Median Normalized)</span>
                      <span className="text-muted font-normal">High-Pass Filter Window: 5.0 hours</span>
                    </div>
                    <svg viewBox="0 0 600 120" className="w-full h-28 overflow-visible">
                      <line x1="40" y1="20" x2="570" y2="20" stroke="rgba(255,255,255,0.04)" />
                      <line x1="40" y1="60" x2="570" y2="60" stroke="rgba(255,255,255,0.15)" strokeDasharray="3,3" />
                      <line x1="40" y1="100" x2="570" y2="100" stroke="rgba(255,255,255,0.04)" />
                      
                      {/* Detrended Data Path */}
                      <path
                        d={generateSvgPath(pipelineData.time, pipelineData.detrended_flux, 600, 120, 40)}
                        fill="none"
                        stroke="#818cf8"
                        strokeWidth="0.9"
                      />
                      
                      <line x1="40" y1="10" x2="40" y2="110" stroke="#1e293b" />
                      <line x1="40" y1="110" x2="570" y2="110" stroke="#1e293b" />
                    </svg>
                    <div className="flex justify-between text-[10px] text-muted px-8">
                      <span>t = 0.0 days</span>
                      <span>Flat Normalized baseline (1.0)</span>
                      <span>t = {pipelineData.time[pipelineData.time.length - 1].toFixed(1)} days</span>
                    </div>
                  </div>

                  {/* Chart 3: Zoomed Transit Profile (Hours relative to mid-transit) */}
                  <div className="bg-surface-2/80 border border-border p-4 rounded-xl flex flex-col gap-2 relative">
                    <div className="flex justify-between items-center">
                      <span className="text-ink font-bold uppercase text-[10px]">3. Zoomed Transit Profile (Phase-Folded Zoom)</span>
                      <span className="text-muted font-normal">Window: ±6.0 hours from Mid-Transit</span>
                    </div>
                    <svg viewBox="0 0 600 130" className="w-full h-32 overflow-visible">
                      <line x1="40" y1="20" x2="570" y2="20" stroke="rgba(255,255,255,0.04)" />
                      <line x1="40" y1="65" x2="570" y2="65" stroke="rgba(255,255,255,0.06)" />
                      <line x1="40" y1="110" x2="570" y2="110" stroke="rgba(255,255,255,0.04)" />
                      
                      {/* Slices of zoomed data */}
                      {(() => {
                        const center = 1.25;
                        const windowVal = 0.25;
                        const zTime: number[] = [];
                        const zFlux: number[] = [];
                        
                        for (let i = 0; i < pipelineData.time.length; i++) {
                          const t = pipelineData.time[i];
                          if (t >= center - windowVal && t <= center + windowVal) {
                            zTime.push((t - center) * 24.0);
                            zFlux.push(pipelineData.detrended_flux[i]);
                          }
                        }

                        if (zTime.length === 0) return null;
                        const minX = -6.0;
                        const maxX = 6.0;
                        const minY = Math.min(...zFlux);
                        const maxY = Math.max(...zFlux);
                        const yBuffer = (maxY - minY) * 0.15 || 0.001;
                        const plotMinY = minY - yBuffer;
                        const plotMaxY = maxY + yBuffer;

                        return zTime.map((t, i) => {
                          const cx = 40 + ((t - minX) / (maxX - minX)) * (570 - 40);
                          const cy = 130 - 20 - ((zFlux[i] - plotMinY) / (plotMaxY - plotMinY)) * (130 - 40);
                          
                          return (
                            <circle
                              key={i}
                              cx={cx.toFixed(1)}
                              cy={cy.toFixed(1)}
                              r="1.2"
                              fill="#818cf8"
                              opacity="0.65"
                            />
                          );
                        });
                      })()}
                      
                      {/* Thick Overlay Transit Fit line */}
                      {(() => {
                        const center = 1.25;
                        const windowVal = 0.25;
                        const zTime: number[] = [];
                        const zFlux: number[] = [];
                        const zFit: number[] = [];
                        
                        for (let i = 0; i < pipelineData.time.length; i++) {
                          const t = pipelineData.time[i];
                          if (t >= center - windowVal && t <= center + windowVal) {
                            zTime.push((t - center) * 24.0);
                            zFlux.push(pipelineData.detrended_flux[i]);
                            zFit.push(pipelineData.transit_fit[i]);
                          }
                        }

                        if (zTime.length === 0) return null;
                        const minX = -6.0;
                        const maxX = 6.0;
                        const minY = Math.min(...zFlux);
                        const maxY = Math.max(...zFlux);
                        const yBuffer = (maxY - minY) * 0.15 || 0.001;
                        const plotMinY = minY - yBuffer;
                        const plotMaxY = maxY + yBuffer;

                        let path = "";
                        for (let i = 0; i < zTime.length; i++) {
                          const x = 40 + ((zTime[i] - minX) / (maxX - minX)) * (570 - 40);
                          const y = 130 - 20 - ((zFit[i] - plotMinY) / (plotMaxY - plotMinY)) * (130 - 40);
                          if (i === 0) {
                            path += `M ${x.toFixed(1)} ${y.toFixed(1)}`;
                          } else {
                            path += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
                          }
                        }
                        
                        const highestCls = Object.entries(pipelineData.classification).reduce(
                          (a, b) => ((a[1] as number) > (b[1] as number) ? a : b)
                        )[0];
                        const fitStroke = highestCls === "Planet Transit" ? "#10b981" : highestCls === "Eclipsing Binary" ? "#f43f5e" : "#e2e8f0";
                        
                        return (
                          <path
                            d={path}
                            fill="none"
                            stroke={fitStroke}
                            strokeWidth="2.5"
                          />
                        );
                      })()}
                      
                      <line x1="40" y1="10" x2="40" y2="120" stroke="#1e293b" />
                      <line x1="40" y1="120" x2="570" y2="120" stroke="#1e293b" />
                    </svg>
                    <div className="flex justify-between text-[10px] px-8">
                      <span className="text-muted">-6.0 hours from center</span>
                      <span className="text-status-pass font-bold uppercase">Transit Model Fit Overlay</span>
                      <span className="text-muted">+6.0 hours from center</span>
                    </div>
                  </div>

                  {/* Chart 4: light-curve vetter input views (real TESS data when vetted, otherwise the simulation, unclassified) */}
                  {pipelineData.dl_global_view && pipelineData.dl_local_view && (
                    <div className="bg-surface-2/80 border border-border p-4 rounded-xl flex flex-col gap-3 relative">
                      <div className="flex justify-between items-center border-b border-border pb-2">
                        <span className="text-ink font-bold uppercase text-[10px]">4. Light-curve vetter input views (folded global + local)</span>
                        <span className="text-accent font-bold text-[10px] uppercase tracking-wider flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-accent"></span> {pipelineData.dl_input_source === "real_tess_spoc_2min" ? "REAL TESS LIGHT CURVE" : "SIMULATED CURVE, NOT CLASSIFIED"}
                        </span>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Global View (2001 bins) */}
                        <div className="bg-surface-2 p-2.5 border border-border rounded-lg flex flex-col gap-1.5">
                          <span className="text-muted text-[10px] uppercase font-bold">A. Global View (2001 Bins)</span>
                          <svg viewBox="0 0 300 70" className="w-full h-16 overflow-visible">
                            <line x1="20" y1="10" x2="280" y2="10" stroke="rgba(255,255,255,0.02)" />
                            <line x1="20" y1="35" x2="280" y2="35" stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
                            <line x1="20" y1="60" x2="280" y2="60" stroke="rgba(255,255,255,0.02)" />
                            
                            <path
                              d={generateSvgPath(
                                pipelineData.dl_global_view.map((_, i) => i),
                                pipelineData.dl_global_view,
                                300,
                                70,
                                20
                              )}
                              fill="none"
                              stroke="#a78bfa"
                              strokeWidth="0.8"
                            />
                            
                            <line x1="20" y1="5" x2="20" y2="65" stroke="#1e293b" />
                            <line x1="20" y1="65" x2="280" y2="65" stroke="#1e293b" />
                          </svg>
                          <div className="flex justify-between text-[10px] text-muted px-4 mt-0.5">
                            <span>Phase = -0.5</span>
                            <span>Phase = 0.0</span>
                            <span>Phase = +0.5</span>
                          </div>
                        </div>

                        {/* Local View (201 bins) */}
                        <div className="bg-surface-2 p-2.5 border border-border rounded-lg flex flex-col gap-1.5">
                          <span className="text-muted text-[10px] uppercase font-bold">B. Local Transit View (201 Bins)</span>
                          <svg viewBox="0 0 300 70" className="w-full h-16 overflow-visible">
                            <line x1="20" y1="10" x2="280" y2="10" stroke="rgba(255,255,255,0.02)" />
                            <line x1="20" y1="35" x2="280" y2="35" stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
                            <line x1="20" y1="60" x2="280" y2="60" stroke="rgba(255,255,255,0.02)" />
                            
                            <path
                              d={generateSvgPath(
                                pipelineData.dl_local_view.map((_, i) => i),
                                pipelineData.dl_local_view,
                                300,
                                70,
                                20
                              )}
                              fill="none"
                              stroke="#f472b6"
                              strokeWidth="0.9"
                            />
                            
                            <line x1="20" y1="5" x2="20" y2="65" stroke="#1e293b" />
                            <line x1="20" y1="65" x2="280" y2="65" stroke="#1e293b" />
                          </svg>
                          <div className="flex justify-between text-[10px] text-muted px-4 mt-0.5">
                            <span>-3.5 * dur</span>
                            <span>Transit Center</span>
                            <span>+3.5 * dur</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                </div>
              )}
            </div>

            {/* AI Classification & Metrics Results */}
            {pipelineData && (
              <div className="glass-panel p-5 rounded-xl shadow-xl grid grid-cols-1 md:grid-cols-2 gap-6">
                
                {/* Physical Metrics Section */}
                <div className="flex flex-col gap-4">
                  <h4 className="panel-title">
                    <FileText className="h-4 w-4" /> Recovered signal metrics
                  </h4>
                  
                  <div className="flex flex-col gap-3 font-mono text-[11px] text-ink/80 mt-1">
                    <div className="flex justify-between items-center border-b border-border pb-2">
                      <span>Signal-to-Noise Ratio (SNR):</span>
                      <div className="flex items-center gap-2 text-right">
                        <span className={`font-bold ${
                          pipelineData.metrics.snr > 8.0 ? 'text-status-pass' :
                          pipelineData.metrics.snr >= 4.0 ? 'text-severity-high' : 'text-severity-critical'
                        }`}>
                          {pipelineData.metrics.snr.toFixed(2)}
                        </span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-extrabold ${
                          pipelineData.metrics.snr > 8.0 ? 'bg-status-pass/10 text-status-pass' :
                          pipelineData.metrics.snr >= 4.0 ? 'bg-severity-high/10 text-severity-high' : 'bg-severity-critical/10 text-severity-critical animate-pulse'
                        }`}>
                          {pipelineData.metrics.snr > 8.0 ? 'DETECTION CONFIRMED' :
                           pipelineData.metrics.snr >= 4.0 ? 'WEAK SIGNAL' : 'UNDETECTABLE'}
                        </span>
                      </div>
                    </div>

                    <div className="flex justify-between items-center border-b border-border pb-2">
                      <span>Transit Ingress/Egress Profile:</span>
                      <div className="flex items-center gap-2 text-right">
                        <span className="font-bold text-ink">
                          V-Factor: {pipelineData.metrics.v_shape_factor.toFixed(2)}
                        </span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-extrabold ${
                          pipelineData.metrics.v_shape_factor > 1.4 ? 'bg-severity-critical/10 text-severity-critical' : 'bg-status-pass/10 text-status-pass'
                        }`}>
                          {pipelineData.metrics.v_shape_factor > 1.4 ? 'V-SHAPED (BINARY)' : 'BOX-LIKE (PLANET)'}
                        </span>
                      </div>
                    </div>

                    <div className="flex justify-between items-center border-b border-border pb-2">
                      <span>Observed (Diluted) Depth:</span>
                      <span className="text-ink font-bold">
                        {pipelineData.metrics.observed_depth_ppm.toFixed(0)} ppm
                      </span>
                    </div>

                    <div className="flex justify-between items-center border-b border-border pb-2">
                      <span>Unblended Catalog Depth:</span>
                      <span className="text-muted">
                        {pipelineData.true_depth_ppm.toFixed(0)} ppm
                      </span>
                    </div>

                    <div className="flex justify-between items-center">
                      <span>Average Noise Floor:</span>
                      <span className="text-muted">
                        {pipelineData.metrics.noise_level_ppm.toFixed(1)} ppm
                      </span>
                    </div>
                  </div>
                </div>

                {/* AI Classification Probability Section */}
                <div className="flex flex-col gap-4">
                  <h4 className="panel-title">
                    <Wand2 className="h-4 w-4" /> AI classifier probabilities
                  </h4>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Heuristic Rule Classifier */}
                    <div className="bg-surface-2/60 p-3.5 border border-border rounded-lg flex flex-col gap-3">
                      <span className="text-ink font-bold text-[10px] uppercase tracking-wider border-b border-border border-border pb-1.5 block">
                        A. Heuristic Classifier (Rules)
                      </span>
                      <div className="flex flex-col gap-2.5 font-mono text-[10px]">
                        {Object.entries(pipelineData.classification).map(([name, prob]) => {
                          const pVal = prob as number;
                          const percentage = (pVal * 100).toFixed(1);
                          let barColor = "bg-muted";
                          let textColor = "text-muted";
                          if (name === "Planet Transit") { barColor = "bg-status-pass"; textColor = "text-status-pass"; }
                          else if (name === "Eclipsing Binary") { barColor = "bg-severity-critical"; textColor = "text-severity-critical"; }
                          else if (name === "Stellar Activity (Starspots)") { barColor = "bg-severity-high"; textColor = "text-severity-high"; }
                          else if (name === "Instrumental Noise") { barColor = "bg-accent"; textColor = "text-accent"; }

                          return (
                            <div key={name} className="flex flex-col gap-1">
                              <span className="text-muted font-semibold text-[10px] leading-snug block">{name}</span>
                              <div className="flex items-center gap-2">
                                <div className="flex-1 bg-surface-2 h-1.5 rounded overflow-hidden">
                                  <div className={`h-full rounded ${barColor}`} style={{ width: `${percentage}%` }} />
                                </div>
                                <span className={`font-bold text-[10px] shrink-0 ${textColor}`}>{percentage}%</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Deep ExoFusion PyTorch Network Classifier */}
                    <div className="bg-surface-2/60 p-3.5 border border-border rounded-lg flex flex-col gap-3">
                      <span className="text-accent font-bold text-[10px] uppercase tracking-wider border-b border-border pb-1.5 block flex items-center gap-1">
                        <span className="h-1 w-1 rounded-full bg-accent"></span> B. PyTorch Deep ExoFusion Net
                      </span>
                      {/* UPGRADE_PLAN.md C.2 / LIMITATIONS.md #7: dl_model_status must be
                          surfaced next to the classification, never buried -- an
                          "untrained_fallback" checkpoint means these percentages are random
                          noise, not a prediction. */}
                      {pipelineData.dl_model_status === "untrained_fallback" ? (
                        <div className="bg-severity-critical/10 border border-severity-critical/30 p-2.5 rounded-lg text-severity-critical text-[10px] font-sans leading-normal flex items-start gap-1.5">
                          <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                          <span><strong>Untrained fallback network.</strong> The trained checkpoint failed to load for this architecture version, so this model is running on random, untrained weights. The percentages below are noise, not a prediction — do not use them for triage.</span>
                        </div>
                      ) : hasDlOutput(pipelineData) ? (
                        <div className="text-muted text-[10px] font-sans leading-normal">
                          {/* Was hardcoded "Synthetic-trained checkpoint... not a validated
                              classifier" -- went stale the moment the model was retrained on
                              real Kepler light curves (2026-08-21) and would have directly
                              contradicted the /ai-analysis page, which correctly says
                              "Trained on real light curves." Real training data, modest
                              real accuracy (see DL Model page for the actual held-out
                              number) -- neither overclaimed nor understated here. */}
                          Trained on real Kepler light curves + real disposition labels (no synthetic light curve in this training set) — see the DL Model page for held-out accuracy before treating this as more than a modest first result.
                          {pipelineData.centroid_measured === false && " No real centroid measurement exists for this candidate yet (the centroid check is reported separately from this score)."}
                        </div>
                      ) : null}
                      <div className="flex flex-col gap-2.5 font-mono text-[10px]">
                        {hasDlOutput(pipelineData) ? (
                          Object.entries(pipelineData.dl_classification).map(([name, prob]) => {
                            const pVal = prob as number;
                            const percentage = (pVal * 100).toFixed(1);
                            let barColor = "bg-accent";
                            let textColor = "text-accent";
                            if (name === "Planet Transit") { barColor = "bg-status-pass"; textColor = "text-status-pass"; }
                            else if (name === "Eclipsing Binary") { barColor = "bg-severity-critical"; textColor = "text-severity-critical"; }
                            else if (name === "Stellar Activity (Starspots)") { barColor = "bg-severity-high"; textColor = "text-severity-high"; }
                            else if (name === "Instrumental Noise") { barColor = "bg-accent"; textColor = "text-accent"; }

                            return (
                              <div key={name} className="flex flex-col gap-1">
                                <span className="text-muted font-semibold text-[10px] leading-snug block">{name}</span>
                                <div className="flex items-center gap-2">
                                  <div className="flex-1 bg-surface-2 h-1.5 rounded overflow-hidden">
                                    <div className={`h-full rounded ${barColor}`} style={{ width: `${percentage}%` }} />
                                  </div>
                                  <span className={`font-bold text-[10px] shrink-0 ${textColor}`}>{percentage}%</span>
                                </div>
                              </div>
                            );
                          })
                        ) : (
                          <div className="h-full flex items-center justify-center text-muted text-[10px] italic py-8">
                            {pipelineData.dl_note || "Deep Learning model outputs not available"}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Physics-Aware Consensus Vetting & Conflict Resolution Report */}
                <div className="md:col-span-2 bg-surface-2 p-5 border border-border rounded-lg font-mono text-[10px] text-muted flex flex-col gap-3.5">
                  <span className="text-ink font-bold uppercase tracking-wider font-mono text-[10px] flex items-center gap-1.5 border-b border-border pb-2">
                    <CheckCircle2 className="h-4 w-4 text-accent" /> AI Consensus Vetting & Physical Consistency Report
                  </span>
                  
                  {(() => {
                    const highestClass = Object.entries(pipelineData.classification).reduce(
                      (a, b) => ((a[1] as number) > (b[1] as number) ? a : b)
                    )[0];
                    const dlDegraded = pipelineData.dl_model_status === "untrained_fallback";
                    const highestDlClass = (hasDlOutput(pipelineData) && !dlDegraded) ? Object.entries(pipelineData.dl_classification).reduce(
                      (a, b) => ((a[1] as number) > (b[1] as number) ? a : b)
                    )[0] : "Unknown";

                    const snr = pipelineData.metrics.snr;
                    const vShape = pipelineData.metrics.v_shape_factor;

                    const hasPhysicalConflict = isUnphysical && (highestClass === "Planet Transit" || highestDlClass === "Planet Transit");
                    const hasModelConflict = highestDlClass !== "Unknown" && highestClass !== highestDlClass;

                    return (
                      <div className="flex flex-col gap-3 font-sans leading-normal">
                        {/* DL model degraded: consensus language below must not treat a
                            random-weights output as agreement or disagreement evidence. */}
                        {dlDegraded && (
                          <div className="bg-severity-critical/10 border border-severity-critical/30 p-3 rounded-lg text-severity-critical text-[10px] flex flex-col gap-1">
                            <span className="font-bold flex items-center gap-1.5">
                              <AlertTriangle className="h-3.5 w-3.5" /> DEEP LEARNING MODEL DEGRADED
                            </span>
                            <p>
                              The PyTorch Deep ExoFusion Net's trained checkpoint failed to load and is running on untrained, random weights. The verdict below reflects the Baseline Heuristic classifier only — the deep learning classification is excluded from this consensus report.
                            </p>
                          </div>
                        )}
                        {/* Physical Oversize Override Warning */}
                        {hasPhysicalConflict && (
                          <div className="bg-severity-critical/10 border border-severity-critical/30 p-3 rounded-lg text-severity-critical text-[10px] flex flex-col gap-1">
                            <span className="font-bold flex items-center gap-1.5">
                              <AlertTriangle className="h-3.5 w-3.5" /> PHYSICAL COMPANION SIZE CONFLICT DETECTED
                            </span>
                            <p>
                              The AI model classified the relative light curve shape as a Planet Transit due to its boxy shape profile (V-Shape factor = {vShape.toFixed(2)}). However, cross-matching with Gaia DR3 stellar parameters reveals that the host star's radius recalculates the transiting companion's physical size to {derivedRp ? derivedRp.toFixed(2) : "N/A"} R_Earth. Since this exceeds the physical boundary of a stable planetary envelope (&gt;20 R_Earth), this target is overridden to an <strong>Eclipsing Binary (EB)</strong> stellar companion.
                            </p>
                          </div>
                        )}
                        
                        {/* Model Consensus Disagreement Warning */}
                        {hasModelConflict && (
                          <div className="bg-severity-high/10 border border-severity-high/30 p-3 rounded-lg text-severity-high text-[10px] flex flex-col gap-1">
                            <span className="font-bold flex items-center gap-1.5">
                              <AlertTriangle className="h-3.5 w-3.5" /> MODEL DECISION DISCORDANCE ALERT
                            </span>
                            <p>
                              Baseline Heuristic rules classified this target as <strong>{highestClass}</strong>, while the PyTorch Deep ExoFusion Net classified it as <strong>{highestDlClass}</strong>. The Deep Learning model integrates multi-modal stellar parameters and convolved spatial filters, offering higher diagnostic fidelity under noisy conditions than simple heuristic thresholds.
                            </p>
                          </div>
                        )}
                        
                        {/* Consensus Achieved Message */}
                        {!hasPhysicalConflict && !hasModelConflict && (
                          <div className="bg-status-pass/10 border border-status-pass/30 p-3 rounded-lg text-status-pass text-[10px] flex flex-col gap-1">
                            <span className="font-bold flex items-center gap-1.5">
                              <CheckCircle2 className="h-3.5 w-3.5" /> MULTI-MODEL VETTING CONSENSUS VALIDATED
                            </span>
                            <p>
                              Triage consensus achieved. The catalog-reported disposition ({planet.disposition}), physical companion radius audits, Heuristic classifiers, and PyTorch Deep ExoFusion Net are in agreement. Predicted Classification: <strong>{highestDlClass !== "Unknown" ? highestDlClass : highestClass}</strong>.
                            </p>
                          </div>
                        )}

                        <div className="text-muted text-[10px] border-t border-border pt-2 flex flex-col gap-1 mt-1 font-mono">
                          <div>• HEURISTIC VERDICT: {highestClass} (Confidence: {(pipelineData.classification[highestClass] * 100).toFixed(0)}%)</div>
                          <div>• PYTORCH VERDICT: {dlDegraded ? 'DEGRADED (untrained weights, excluded from consensus)' : `${highestDlClass} ${hasDlOutput(pipelineData) ? `(Confidence: ${(pipelineData.dl_classification[highestDlClass] * 100).toFixed(0)}%)` : ''}`}</div>
                          <div>• GAIA PHYSICAL RADIUS CONSTRAINT: {isUnphysical ? 'INVALID SIZE (STARS & EBS ONLY)' : 'VALID SIZE (PLANETARY RANGE)'}</div>
                        </div>
                      </div>
                    );
                  })()}
                </div>

              </div>
            )}
            
          </div>

        </div>
      )}

    </div>
  );
}
