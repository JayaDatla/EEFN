import os
import sys
import numpy as np

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.db.models import ExoplanetCandidate
from app.ml.transit_pipeline import transit_pipeline

def test_window_sizes():
    db = SessionLocal()
    try:
        c = db.query(ExoplanetCandidate).filter(ExoplanetCandidate.pl_name == "TOI-1020.01").first()
        if not c:
            return
            
        rstar_solar = c.host.rad if c.host and c.host.rad else 1.0
        period = c.orbper or 3.0
        duration_hours = c.trandurh or 2.5
        transit_duration_days = duration_hours / 24.0
        
        for window in [51, 75, 101, 151, 301]:
            print(f"\n--- WINDOW SIZE: {window} points ---")
            for spots in [True, False]:
                sim = transit_pipeline.generate_simulated_lightcurve(
                    period=period,
                    depth_ppm=c.trandep or 1500.0,
                    duration_hours=duration_hours,
                    noise_std=0.002,
                    blending_factor=0.15,
                    has_starspots=spots
                )
                
                time_arr = np.array(sim["time"])
                raw_flux_arr = np.array(sim["raw_flux"])
                n = len(raw_flux_arr)
                
                in_transit = np.zeros(n, dtype=bool)
                mid_transit_1 = 1.25
                for i, t in enumerate(time_arr):
                    phase = ((t - mid_transit_1 + period/2.0) % period) - period/2.0
                    if abs(phase) < (transit_duration_days / 2.0 + 0.01):
                        in_transit[i] = True
                
                medians = np.zeros(n)
                half_w = window // 2
                for i in range(n):
                    start = max(0, i - half_w)
                    end = min(n, i + half_w + 1)
                    
                    w_flux = raw_flux_arr[start:end]
                    w_mask = in_transit[start:end]
                    oot_flux = w_flux[~w_mask]
                    
                    if len(oot_flux) > 0:
                        medians[i] = np.median(oot_flux)
                    else:
                        medians[i] = np.median(w_flux)
                        
                detrended = raw_flux_arr / medians
                
                results = transit_pipeline.run_ai_classification(
                    time=time_arr,
                    detrended_flux=detrended,
                    period=period,
                    duration_hours=duration_hours,
                    blending_factor=0.15,
                    rstar_solar=rstar_solar
                )
                print(f"Spots: {spots:<5} | Depth: {results['observed_depth_ppm']:.1f} ppm | SNR: {results['snr']:.2f}")
                
    finally:
        db.close()

if __name__ == "__main__":
    test_window_sizes()
