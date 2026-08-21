# Independent Reimplementation Test: Planet Radius Checker
# Written by Reviewer Agent to verify database consistency of derived exoplanet radii and agreement metrics.
import sqlite3
import math

def calculate_derived_radius(st_rad, trandep_ppm):
    """
    Independently calculates planetary radius (in Earth radii)
    from stellar radius (in Solar radii) and transit depth (in ppm).
    Formula: Rp = Rs * sqrt(depth_ppm * 1e-6) * (R_sun / R_earth)
    Using R_sun / R_earth = 109.2
    """
    if st_rad is None or trandep_ppm is None:
        return None
    depth_fraction = trandep_ppm * 1e-6
    r_ratio = math.sqrt(depth_fraction)
    rp_earth = st_rad * r_ratio * 109.2
    return rp_earth

def run_radius_audit():
    db_path = "D:/Gemini_Projects/EXO/backend/eefn.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Query details including agreement metrics
    query = """
    SELECT 
        c.pl_name, 
        c.rade as original_rade, 
        c.trandep, 
        s.rad as star_rad, 
        s.hostname,
        m.derived_rp_diff
    FROM exoplanet_candidates c
    JOIN host_stars s ON c.host_id = s.id
    JOIN agreement_metrics m ON m.candidate_id = c.id
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    print(f"Auditing {len(rows)} candidates for physical radius consistency...")
    
    diff_errors = []
    
    for row in rows:
        pl_name, original_rade, trandep, star_rad, hostname, db_rp_diff = row
        if original_rade is None or trandep is None or star_rad is None or db_rp_diff is None:
            continue
            
        # 1. Verify Gaia-derived planetary radius
        calc_rp_gaia = calculate_derived_radius(star_rad, trandep)
        
        # 2. Verify database's derived_rp_diff calculation
        calc_rp_diff = abs(calc_rp_gaia - original_rade)
        diff_error = abs(db_rp_diff - calc_rp_diff)
        diff_errors.append(diff_error)
        
    if not diff_errors:
        print("No complete records found to audit.")
        return
        
    diff_errors.sort()
    max_diff_error = max(diff_errors)
    mean_diff_error = sum(diff_errors) / len(diff_errors)
    median_diff_error = diff_errors[len(diff_errors) // 2]
    
    print("\n--- Radius Checker Audit Results ---")
    print(f"Processed: {len(diff_errors)} targets")
    print(f"Max Difference Error (Stored vs Calculated derived_rp_diff): {max_diff_error:.6f} R_earth")
    print(f"Mean Difference Error: {mean_diff_error:.6f} R_earth")
    print(f"Median Difference Error: {median_diff_error:.6f} R_earth")
    
    # Check if discrepancies exist
    threshold = 0.05
    failures = sum(1 for e in diff_errors if e > threshold)
    print(f"Discrepancies exceeding {threshold} R_earth: {failures}")
    if failures == 0:
        print("STATUS: PASS")
    else:
        print("STATUS: FAIL")

if __name__ == "__main__":
    run_radius_audit()
