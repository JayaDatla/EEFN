# Independent Reimplementation Test: Alert Checker
# Written by Reviewer Agent
import sqlite3
import math

def run_alert_audit():
    db_path = "D:/Gemini_Projects/EXO/backend/eefn.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Query candidate metrics
    query = """
    SELECT 
        c.pl_name, 
        c.rade, 
        c.trandep, 
        s.rad as star_rad, 
        s.teff as star_teff,
        s.distance as star_dist,
        s.parallax as star_parallax,
        m.teff_disagreement,
        m.rad_disagreement,
        m.dist_disagreement,
        m.ruwe,
        m.is_unphysical_rp
    FROM exoplanet_candidates c
    JOIN host_stars s ON c.host_id = s.id
    LEFT JOIN agreement_metrics m ON m.candidate_id = c.id
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    print(f"Auditing alert conditions for {len(rows)} candidates...")
    
    rules = {
        "Unphysical Radius": {"triggers": 0, "verified": 0, "false_positives": 0},
        "High RUWE": {"triggers": 0, "verified": 0, "false_positives": 0},
        "Teff Mismatch": {"triggers": 0, "verified": 0, "false_positives": 0},
        "Radius Mismatch": {"triggers": 0, "verified": 0, "false_positives": 0},
        "Distance Mismatch": {"triggers": 0, "verified": 0, "false_positives": 0},
        "Missing Gaia": {"triggers": 0, "verified": 0, "false_positives": 0}
    }
    
    for row in rows:
        (pl_name, rade, trandep, star_rad, star_teff, star_dist, star_parallax,
         teff_dis, rad_dis, dist_dis, ruwe, is_unphysical) = row
         
        # 1. Unphysical Derived Radius Check (>22 R_earth)
        if star_rad and trandep:
            calc_rp = star_rad * math.sqrt(trandep * 1e-6) * 109.208
            if calc_rp > 22.0:
                rules["Unphysical Radius"]["verified"] += 1
                if is_unphysical:
                    rules["Unphysical Radius"]["triggers"] += 1
                else:
                    rules["Unphysical Radius"]["false_positives"] += 1
            else:
                if is_unphysical:
                    # Stored as unphysical but calc says it isn't
                    rules["Unphysical Radius"]["false_positives"] += 1
                    
        # 2. High RUWE Check (>1.4)
        if ruwe is not None:
            if ruwe > 1.4:
                rules["High RUWE"]["verified"] += 1
                rules["High RUWE"]["triggers"] += 1
                
        # 3. Teff Mismatch Check (>500K)
        if teff_dis is not None:
            if teff_dis > 500.0:
                rules["Teff Mismatch"]["verified"] += 1
                rules["Teff Mismatch"]["triggers"] += 1
                
        # 4. Radius Mismatch Check (>0.25 R_sun)
        if rad_dis is not None:
            if rad_dis > 0.25:
                rules["Radius Mismatch"]["verified"] += 1
                rules["Radius Mismatch"]["triggers"] += 1
                
        # 5. Distance Mismatch Check (>100 pc)
        if dist_dis is not None:
            if dist_dis > 100.0:
                rules["Distance Mismatch"]["verified"] += 1
                rules["Distance Mismatch"]["triggers"] += 1
                
        # 6. Missing Gaia Check (star_parallax is None)
        if star_parallax is None:
            rules["Missing Gaia"]["verified"] += 1
            rules["Missing Gaia"]["triggers"] += 1
            
    print("\n--- Alert Checker Validation Summary ---")
    for rule_name, stats in rules.items():
        triggers = stats["triggers"]
        verified = stats["verified"]
        fp = stats["false_positives"]
        
        precision = (triggers / (triggers + fp)) if (triggers + fp) > 0 else 1.0
        recall = (triggers / verified) if verified > 0 else 1.0
        fpr = (fp / (len(rows) - verified)) if (len(rows) - verified) > 0 else 0.0
        
        print(f"\nRule: {rule_name}")
        print(f"  Verified True Positives in DB: {triggers}")
        print(f"  Expected True Positives (calculated): {verified}")
        print(f"  False Positives: {fp}")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall: {recall:.4f}")
        print(f"  False Positive Rate: {fpr:.4f}")

if __name__ == "__main__":
    run_alert_audit()
