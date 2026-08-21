"use client";

import React, { useState, useEffect } from "react";
import { apiUrl } from "@/lib/api";

interface TelemetryData {
  networkStatus: "ONLINE" | "OFFLINE" | "CHECKING";
  gaiaSync: string | null;
  nasaSync: string | null;
  resolvedConflicts: string | null;
  activeAlerts: string | null;
}

const UNKNOWN: TelemetryData = {
  networkStatus: "CHECKING",
  gaiaSync: null,
  nasaSync: null,
  resolvedConflicts: null,
  activeAlerts: null,
};

export default function TelemetryBar() {
  const [data, setData] = useState<TelemetryData>(UNKNOWN);

  const fetchTelemetry = async () => {
    try {
      const res = await fetch(apiUrl("/api/v1/catalog/health"));
      if (!res.ok) throw new Error("API health check failed");
      const health = await res.json();

      const formatTime = (isoString: string | null) => {
        if (!isoString) return null;
        try {
          const dt = new Date(isoString);
          const yyyy = dt.getFullYear();
          const mm = String(dt.getMonth() + 1).padStart(2, "0");
          const dd = String(dt.getDate()).padStart(2, "0");
          const hh = String(dt.getHours()).padStart(2, "0");
          const min = String(dt.getMinutes()).padStart(2, "0");
          return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
        } catch {
          return null;
        }
      };

      setData({
        networkStatus: "ONLINE",
        gaiaSync: formatTime(health.last_sync?.gaia),
        nasaSync: formatTime(health.last_sync?.nasa),
        resolvedConflicts: health.resolved_conflict_count != null ? Number(health.resolved_conflict_count).toLocaleString() : null,
        activeAlerts: health.unresolved_alert_count != null ? Number(health.unresolved_alert_count).toLocaleString() : null,
      });
    } catch {
      // UPGRADE_PLAN.md A.14/H.4: an unreachable backend must show as OFFLINE
      // with no data, never keep stale/fabricated numbers on screen.
      setData({ ...UNKNOWN, networkStatus: "OFFLINE" });
    }
  };

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 8000);
    return () => clearInterval(interval);
  }, []);

  const statusColor =
    data.networkStatus === "ONLINE" ? "bg-status-pass" : data.networkStatus === "OFFLINE" ? "bg-status-risk" : "bg-status-watch";

  return (
    <div className="telemetry">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span className={`h-1.5 w-1.5 rounded-full ${statusColor}`} />
          <span>
            API Status: <strong className="online">{data.networkStatus}</strong>
          </span>
        </div>
        <div className="hidden md:flex items-center gap-5 border-l border-border pl-5">
          <span>
            Gaia DR3 Sync: <strong>{data.gaiaSync ?? "unavailable"} UT</strong>
          </span>
          <span>
            NASA Archive Sync: <strong>{data.nasaSync ?? "unavailable"} UT</strong>
          </span>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="hidden lg:flex items-center gap-5">
          <span>
            Targets: <span className="font-bold text-ink">{data.resolvedConflicts ?? "—"}</span>
          </span>
          <span>
            Discrepancy Alerts: <span className="font-bold text-severity-high">{data.activeAlerts ?? "—"}</span>
          </span>
        </div>
        <span className="hidden sm:inline border-l border-border pl-5 text-muted">
          DATA CONTEXT: <span className="text-ink/70">CROSS-CATALOG AUDITING</span>
        </span>
      </div>
    </div>
  );
}
