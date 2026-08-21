import numpy as np
import math
from typing import Dict, Any

class TransitDetectionPipeline:
    def __init__(self):
        pass

    def generate_simulated_lightcurve(
        self,
        period: float,
        depth_ppm: float,
        duration_hours: float,
        noise_std: float = 0.002,
        blending_factor: float = 0.15,
        has_starspots: bool = True,
        seed: int = None
    ) -> Dict[str, Any]:
        """
        Simulates an astronomical light curve of a transiting exoplanet candidate.
        Includes options for:
        - Transit dips (based on physical parameters)
        - Stellar variability (sinusoidal starspot patterns)
        - Crowded-field blending (dilution of the transit depth)
        - Intrinsinc detector/photon noise
        """
        # Dynamic window size: at least 5 days, or 3 times the orbital period, up to a maximum of 30 days
        window_days = max(5.0, min(30.0, period * 3.0))
        
        # Maintain a constant 4-minute cadence proportional to window size
        num_points = int(window_days * 360)
        time = np.linspace(0.0, window_days, num_points)
        
        # 1. Base flux
        flux = np.ones_like(time)
        
        # 2. Add transit dips
        transit_duration_days = duration_hours / 24.0
        
        # Dynamically generate transit centers across the entire simulated window
        mid_transits = []
        current_center = 1.25
        while current_center < window_days:
            mid_transits.append(current_center)
            current_center += period
            
        # Calculate diluted depth due to crowded field blending
        # Dilution formula: depth_diluted = depth_true * (1 - blending_factor)
        diluted_depth = (depth_ppm / 1e6) * (1.0 - blending_factor)
        
        for i, t in enumerate(time):
            # Check proximity to transit centers
            for center in mid_transits:
                dt = abs(t - center)
                if dt < (transit_duration_days / 2.0):
                    # Inside transit flat bottom
                    flux[i] -= diluted_depth
                elif dt < (transit_duration_days / 2.0) + 0.01:
                    # Ingress/egress ramp
                    fraction = (transit_duration_days / 2.0 + 0.01 - dt) / 0.01
                    flux[i] -= diluted_depth * fraction
                    
        # Save clean transit signal (without stellar variability or noise) for fitting visual
        clean_transit_fit = flux.copy()

        # 3. Add stellar variability (Starspots rotation)
        if has_starspots:
            # Combined sinusoidal stellar rotation waves (amplitude ~ 0.5%)
            starspot_signal = 0.005 * np.sin(2.0 * np.pi * time / 1.5) + 0.002 * np.cos(2.0 * np.pi * time / 0.7)
            flux += starspot_signal
        else:
            starspot_signal = np.zeros_like(time)
            
        # 4. Add Gaussian detector noise
        if seed is not None:
            rng = np.random.default_rng(seed)
            noise = rng.normal(0.0, noise_std, num_points)
        else:
            noise = np.random.normal(0.0, noise_std, num_points)
        raw_flux = flux + noise
        
        return {
            "time": time.tolist(),
            "raw_flux": raw_flux.tolist(),
            "clean_transit_fit": clean_transit_fit.tolist(),
            "starspot_signal": starspot_signal.tolist(),
            "true_depth_ppm": depth_ppm,
            "diluted_depth_ppm": float(diluted_depth * 1e6)
        }

    def detrend_lightcurve(
        self,
        time: np.ndarray,
        raw_flux: np.ndarray,
        period: float,
        duration_hours: float
    ) -> np.ndarray:
        """
        Detrends the light curve to filter out low-frequency stellar variability/starspots
        using a high-pass moving median filter with transit masking.
        Excluding in-transit points prevents the transit signal from diluting/distorting the baseline.
        """
        import scipy.ndimage as ndimage
        n = len(raw_flux)
        
        # Calculate dynamic window size in points corresponding to ~8 hours 
        # (small enough to track starspots of 16-36h period, but large enough to cover transit duration)
        duration_days = time[-1] - time[0]
        cadence_days = duration_days / n
        window_size = int(0.33 / cadence_days)
        if window_size % 2 == 0:
            window_size += 1
        window_size = max(75, min(181, window_size))
        
        # Vectorized transit mask generation
        transit_duration_days = duration_hours / 24.0
        mid_transit_1 = 1.25
        phases = ((time - mid_transit_1 + period/2.0) % period) - period/2.0
        in_transit = np.abs(phases) < (transit_duration_days / 2.0 + 0.015) # add a small buffer
        
        # If there are no out-of-transit points, default to standard median filter
        oot_mask = ~in_transit
        if not np.any(oot_mask):
            medians = ndimage.median_filter(raw_flux, size=window_size, mode='nearest')
            return raw_flux / medians
            
        # Get out-of-transit values
        oot_flux = raw_flux[oot_mask]
        oot_times = time[oot_mask]
        
        # Fast 1D median filter using scipy
        oot_medians = ndimage.median_filter(oot_flux, size=window_size, mode='nearest')
        
        # Interpolate medians back to all time points (including in-transit)
        medians = np.interp(time, oot_times, oot_medians)
        
        # Divide by median trend to normalize
        detrended_flux = raw_flux / medians
        return detrended_flux

    def run_ai_classification(
        self,
        time: np.ndarray,
        detrended_flux: np.ndarray,
        period: float,
        duration_hours: float,
        blending_factor: float,
        rstar_solar: float = 1.0
    ) -> Dict[str, Any]:
        """
        Runs an AI-based evaluation pipeline to detect transit signatures, calculate
        physical metrics, and classify the signal origin.
        """
        n = len(detrended_flux)
        # Calculate standard deviation of detrended flux out-of-transit to estimate noise
        transit_duration_days = duration_hours / 24.0
        
        # Simple fold to compute transit statistics
        folded_phase = []
        in_transit_mask = np.zeros(n, dtype=bool)
        
        mid_transit_1 = 1.25
        for i, t in enumerate(time):
            # Fold phase relative to mid_transit_1
            phase = ((t - mid_transit_1 + period/2.0) % period) - period/2.0
            folded_phase.append(phase)
            if abs(phase) < (transit_duration_days / 2.0):
                in_transit_mask[i] = True
                
        folded_phase = np.array(folded_phase)
        
        # Compute stats
        out_transit_flux = detrended_flux[~in_transit_mask]
        in_transit_flux = detrended_flux[in_transit_mask]
        
        noise_level = np.std(out_transit_flux) if len(out_transit_flux) > 0 else 0.001
        observed_depth = 1.0 - np.mean(in_transit_flux) if len(in_transit_flux) > 0 else 0.0
        
        # Calculate Signal-to-Noise Ratio (SNR) of transit detection
        # SNR = depth / (noise_level / sqrt(number_in_transit))
        num_in_transit = np.sum(in_transit_mask)
        snr = (observed_depth / (noise_level / np.sqrt(num_in_transit))) if (noise_level > 0 and num_in_transit > 0) else 0.0
        
        # Ingress/egress shape analysis: "V-shape" factor
        # Planet transits are boxy/U-shaped (flat bottom, steep ingress/egress, shape index ~1.0)
        # Eclipsing Binaries are V-shaped (continuous change in light, shape index ~2.0)
        # We calculate the ratio of the core transit depth (deepest 25% of in-transit data points) 
        # to the overall observed transit depth. For boxy transits this ratio is ~1.0-1.2. 
        # For sharp V-shaped eclipses, the core is much deeper than the average, yielding a ratio >1.4.
        v_shape_factor = 1.0
        if len(in_transit_flux) > 0:
            # Apply a moving average smoothing (window = 5 points) to suppress noise spikes
            # before sorting, preventing selection bias of noise outliers.
            smooth_window = min(5, len(in_transit_flux))
            if smooth_window > 1:
                smoothed_flux = np.convolve(in_transit_flux, np.ones(smooth_window)/smooth_window, mode='valid')
            else:
                smoothed_flux = in_transit_flux
                
            sorted_in_transit = np.sort(smoothed_flux)
            num_points_25 = max(1, len(sorted_in_transit) // 4)
            core_depth = 1.0 - np.mean(sorted_in_transit[:num_points_25])
            
            if observed_depth > 0:
                v_shape_factor = float(core_depth / (observed_depth + 1e-6))
            else:
                v_shape_factor = 1.0
                
            # Normalize and bound v_shape_factor for API compatibility (range 0.1 to 2.5)
            v_shape_factor = max(0.1, min(2.5, v_shape_factor))
        
        # Calculate derived physical planetary radius in Earth Radii
        # observed_depth is fractional depth (e.g. 0.015 for 15,000 ppm)
        # R_p = R_star * sqrt(observed_depth) * 109.2
        derived_rp_earth = 0.0
        if observed_depth > 0:
            derived_rp_earth = rstar_solar * math.sqrt(observed_depth) * 109.2

        # AI Classification scoring logic (simulating neural network outputs based on physical parameters)
        # Blending dilutes the transit depth. If blending is high, a planet might look like noise, or a binary EB looks like a planet.
        p_planet = 0.05
        p_binary = 0.05
        p_starspots = 0.05
        p_noise = 0.05
        
        if snr < 4.0:
            # Signal dominated by noise
            p_noise = 0.80
            p_planet = 0.10
            p_binary = 0.05
            p_starspots = 0.05
        else:
            # Detected signal is significant
            if derived_rp_earth > 20.0:
                # Physically too large for a planet candidate (brown dwarf/stellar range) -> flags as Eclipsing Binary
                p_binary = 0.92
                p_planet = 0.03
                p_noise = 0.03
                p_starspots = 0.02
            elif v_shape_factor > 1.4:
                # Highly likely Eclipsing Binary (V-shaped)
                p_binary = 0.85
                p_planet = 0.08
                p_noise = 0.04
                p_starspots = 0.03
            elif blending_factor > 0.4:
                # Large stellar blending dilutes EBs to look like planets
                p_binary = 0.50
                p_planet = 0.35
                p_noise = 0.10
                p_starspots = 0.05
            else:
                # Flat-bottomed U-shape transit, low blend, high SNR = planet candidate
                p_planet = 0.90
                p_binary = 0.05
                p_noise = 0.03
                p_starspots = 0.02
                
        # Normalize probabilities to sum to 1.0
        total = p_planet + p_binary + p_starspots + p_noise
        
        return {
            "snr": float(snr),
            "v_shape_factor": float(v_shape_factor),
            "noise_level_ppm": float(noise_level * 1e6),
            "observed_depth_ppm": float(observed_depth * 1e6),
            "derived_rp_earth": float(derived_rp_earth),
            "classification": {
                "Planet Transit": float(p_planet / total),
                "Eclipsing Binary": float(p_binary / total),
                "Stellar Activity (Starspots)": float(p_starspots / total),
                "Instrumental Noise": float(p_noise / total)
            }
        }

transit_pipeline = TransitDetectionPipeline()
