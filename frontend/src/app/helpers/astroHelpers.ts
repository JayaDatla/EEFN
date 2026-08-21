export const decToHMS = (deg: number | undefined | null, isDec = false): string => {
  if (deg === undefined || deg === null) return "00:00:00.00";
  const sign = deg < 0 ? "-" : isDec ? "+" : "";
  const absDeg = Math.abs(deg);
  
  if (isDec) {
    const d = Math.floor(absDeg);
    const m = Math.floor((absDeg - d) * 60);
    const s = ((absDeg - d - m / 60) * 3600).toFixed(2);
    return `${sign}${String(d).padStart(2, '0')}°${String(m).padStart(2, '0')}'${String(s).padStart(5, '0')}"`;
  } else {
    const hoursDecimal = absDeg / 15.0;
    const h = Math.floor(hoursDecimal);
    const m = Math.floor((hoursDecimal - h) * 60);
    const s = ((hoursDecimal - h - m / 60) * 3600).toFixed(3);
    return `${String(h).padStart(2, '0')}h ${String(m).padStart(2, '0')}m ${String(s).padStart(6, '0')}s`;
  }
};

export const getProp = (obj: any, path: string, fallback: any = "N/A"): any => {
  if (!obj) return fallback;
  try {
    const parts = path.split('.');
    let current = obj;
    for (const p of parts) {
      current = current[p];
      if (current === undefined || current === null) return fallback;
    }
    return current;
  } catch {
    return fallback;
  }
};
