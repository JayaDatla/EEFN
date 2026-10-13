import uuid
import math
from datetime import datetime
from app.db.session import SessionLocal, Base, engine
from app.db.models import HostStar, ExoplanetCandidate, CatalogSource, MeasurementHistory, AgreementMetrics, MLPrediction

SEED_WARNING = """
THIS SCRIPT ERASES THE ENTIRE DATABASE and fills it with RANDOMLY GENERATED, FABRICATED candidates
(random periods, temperatures, scores, grades). None of it is real data. It exists only to make
a throwaway demo database. Refusing to run unless you pass --erase-and-fabricate, and refusing
even then if the target database already holds real ingested data (pass --force to override).
"""


def _refuse_if_real_data_present() -> None:
    """Real ingestion writes MeasurementHistory provenance rows and TOI-side host values; seed data
    writes neither. Their presence means this is not a throwaway database."""
    from app.db.models import HostStar, MeasurementHistory
    db = SessionLocal()
    try:
        real_rows = db.query(MeasurementHistory).count() + db.query(HostStar).filter(HostStar.toi_teff.isnot(None)).count()
    except Exception:
        real_rows = 0          # tables don't exist yet: nothing to protect
    finally:
        db.close()
    if real_rows:
        raise SystemExit(f"Refusing to erase: this database holds {real_rows} real ingested rows "
                         "(provenance history / TOI host values). Use a different DATABASE_URL, or --force.")


def seed_database():
    print("Dropping old database tables and creating ExoFusion-Net v2 schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    print("Clearing existing data...")
    db.query(MLPrediction).delete()
    db.query(AgreementMetrics).delete()
    db.query(MeasurementHistory).delete()
    db.query(ExoplanetCandidate).delete()
    db.query(HostStar).delete()
    db.query(CatalogSource).delete()
    db.commit()

    print("Adding catalog sources...")
    src_nasa = CatalogSource(id=uuid.uuid4(), name="NASA Exoplanet Archive", version="1.0", last_sync=datetime.utcnow())
    src_gaia = CatalogSource(id=uuid.uuid4(), name="Gaia DR3", version="1.2", last_sync=datetime.utcnow())
    src_toi = CatalogSource(id=uuid.uuid4(), name="TOI Catalog", version="2026-05-22", last_sync=datetime.utcnow())
    db.add_all([src_nasa, src_gaia, src_toi])
    db.commit()

    print("Seeding 50 exoplanet candidates...")
    import random
    random.seed(42)

    # We will specifically create a few flagship targets with distinct conflicts
    flagships = [
        {
            "toi": 1017.01,
            "tic": 182943944,
            "disp": "FP",
            "orbper": 9.22,
            "rade": 22.24, # Genuinely unphysical Rp
            "trandep": 16000.0,
            "trandurh": 2.1,
            "insol": 420.5,
            "eqt": 220.0, # Will be recalculated
            "st_teff": 6995.2,
            "gaia_teff": 6822.4,
            "st_rad": 1.61,
            "gaia_rad": 1.627,
            "st_dist": 406.9,
            "gaia_dist": 385.9,
            "ruwe": 0.858,
            "is_unphysical": True,
            "conf_prob": 0.045,
            "priority": 0.12
        },
        {
            "toi": 1020.01,
            "tic": 182943945,
            "disp": "CP",
            "orbper": 14.85,
            "rade": 3.62,
            "trandep": 1420.2,
            "trandurh": 3.4,
            "insol": 21.5,
            "eqt": 5028.7,
            "st_teff": 5028.7,
            "gaia_teff": 6822.4, # severe temp mismatch
            "st_rad": 0.88,
            "gaia_rad": 1.420, # severe rad mismatch
            "st_dist": 154.2,
            "gaia_dist": 155.8,
            "ruwe": 1.421, # High RUWE
            "is_unphysical": False,
            "conf_prob": 0.885,
            "priority": 0.95
        },
        {
            "toi": 1025.01,
            "tic": 182943946,
            "disp": "PC",
            "orbper": 3.52,
            "rade": 5.74,
            "trandep": 2200.4,
            "trandurh": 1.8,
            "insol": 850.3,
            "eqt": 5800.0,
            "st_teff": 5767.8,
            "gaia_teff": 5800.2,
            "st_rad": 1.12,
            "gaia_rad": 1.150,
            "st_dist": 850.3,
            "gaia_dist": 1200.4, # Distance conflict
            "ruwe": 1.620, # High RUWE
            "is_unphysical": False,
            "conf_prob": 0.540,
            "priority": 0.65
        },
        {
            "toi": 1022.01,
            "tic": 182943948,
            "disp": "FP",
            "orbper": 22.41,
            "rade": 23.77, # Genuinely unphysical Rp
            "trandep": 84200.2,
            "trandurh": 5.6,
            "insol": 2.4,
            "eqt": 150.0, # Will be recalculated
            "st_teff": 4750.0,
            "gaia_teff": 4800.0,
            "st_rad": 0.75,
            "gaia_rad": 0.76,
            "st_dist": 95.0,
            "gaia_dist": 95.2,
            "ruwe": 1.012,
            "is_unphysical": True,
            "conf_prob": 0.012,
            "priority": 0.05
        }
    ]

    flagship_tois = [f["toi"] for f in flagships]

    # Generate the remaining 46 targets randomly but realistically
    targets = []
    targets.extend(flagships)
    
    for i in range(1, 47):
        toi_val = round(1000.0 + i, 2)
        if toi_val in flagship_tois:
            continue
            
        disp = random.choice(["CP", "PC", "FP"])
        orbper = round(random.uniform(0.5, 50.0), 4)
        st_teff = round(random.uniform(3000.0, 7000.0), 1)
        gaia_teff = round(st_teff + random.uniform(-100.0, 100.0), 1)
        st_rad = round(random.uniform(0.5, 2.0), 3)
        gaia_rad = round(st_rad + random.uniform(-0.05, 0.05), 3)
        st_dist = round(random.uniform(50.0, 1500.0), 1)
        gaia_dist = round(st_dist + random.uniform(-15.0, 15.0), 1)
        ruwe = round(random.uniform(0.8, 1.3), 3)
        
        # Sometime force high RUWE
        if random.random() < 0.08:
            ruwe = round(random.uniform(1.45, 1.9), 3)
            
        # Transit depth in ppm
        trandep = round(random.uniform(100.0, 15000.0), 1)
        
        # Calculate derived planet radius in R_Earth using Gaia properties
        derived_rp_gaia = gaia_rad * (trandep * 1e-6)**0.5 * 109.2
        is_unphysical = derived_rp_gaia > 22.0
        
        # Original reported radius in R_Earth
        original_rp = st_rad * (trandep * 1e-6)**0.5 * 109.2
        
        if is_unphysical:
            disp = "FP"
            conf_prob = round(random.uniform(0.01, 0.09), 3)
            priority = round(random.uniform(0.02, 0.15), 3)
        else:
            conf_prob = round(random.uniform(0.2, 0.98), 3)
            priority = round(random.uniform(0.2, 0.98), 3)
            
        targets.append({
            "toi": toi_val,
            "tic": 182943948 + i,
            "disp": disp,
            "orbper": orbper,
            "rade": round(original_rp, 2),
            "trandep": trandep,
            "trandurh": round(random.uniform(1.0, 8.0), 2),
            "insol": round(random.uniform(1.0, 2000.0), 1),
            "eqt": 0.0, # Will be recalculated
            "st_teff": st_teff,
            "gaia_teff": gaia_teff,
            "st_rad": st_rad,
            "gaia_rad": gaia_rad,
            "st_dist": st_dist,
            "gaia_dist": gaia_dist,
            "ruwe": ruwe,
            "is_unphysical": is_unphysical,
            "conf_prob": conf_prob,
            "priority": priority
        })

    # Slice to ensure exactly 50
    targets = targets[:50]

    for t in targets:
        hostname = f"TIC {t['tic']}"
        star_mass = random.uniform(0.7, 1.3)
        
        # Calculate physically correct planet equilibrium temperature
        # using star's properties (Teff, Rad, Mass) and planet period
        calc_a = ((t["orbper"] / 365.25)**2 * star_mass)**(1/3)
        calc_eqt = t["gaia_teff"] * math.sqrt((t["gaia_rad"] * 0.0046524726) / (2.0 * calc_a))
        t["eqt"] = round(calc_eqt, 1)

        star = HostStar(
            id=uuid.uuid4(),
            hostname=hostname,
            ra=random.uniform(0.0, 360.0),
            dec=random.uniform(-90.0, 90.0),
            parallax=1000.0 / t["gaia_dist"] if t["gaia_dist"] > 0 else 1.0,
            distance=t["gaia_dist"],
            teff=t["gaia_teff"],
            logg=random.uniform(4.0, 4.5),
            rad=t["gaia_rad"],
            mass=star_mass,
            pm_ra=round(random.uniform(-50.0, 50.0), 2),
            pm_dec=round(random.uniform(-50.0, 50.0), 2),
            ruwe=t["ruwe"],
            j_mag=round(random.uniform(8.0, 14.0), 2),
            h_mag=round(random.uniform(7.5, 13.5), 2),
            k_mag=round(random.uniform(7.0, 13.0), 2),
            g_mag=round(random.uniform(9.0, 15.0), 2),
            r_mag=round(random.uniform(8.5, 14.5), 2),
            i_mag=round(random.uniform(8.0, 14.0), 2),
            z_mag=round(random.uniform(7.8, 13.8), 2),
            y_mag=round(random.uniform(7.5, 13.5), 2),
            teff_spec=round(t["gaia_teff"] + random.uniform(-40.0, 40.0), 1),
            rad_spec=round(t["gaia_rad"] + random.uniform(-0.02, 0.02), 3),
            fe_h=round(random.uniform(-0.3, 0.3), 2),
            alpha_fe=round(random.uniform(-0.05, 0.15), 2)
        )
        db.add(star)
        db.commit()

        pl_name = f"TOI-{t['toi']}"
        
        # Calculate ExoFusion-Net v2 Health Score & Density Invariants
        calc_rp_gaia = t["gaia_rad"] * (t["trandep"] * 1e-6)**0.5 * 109.2
        derived_rp_diff = abs(t["rade"] - calc_rp_gaia)
        
        # Transit density calculation (g/cm^3)
        density_transit = round(32.0 / (6.674e-8 * math.pi) * ((t["trandurh"]*3600)**(-3)) / ((t["trandep"]*1e-6)**0.75), 3) if t["trandurh"] > 0 and t["trandep"] > 0 else 1.4
        density_gaia = round(star_mass / (t["gaia_rad"]**3) * 1.408, 3)
        density_sigma = round(abs(density_transit - density_gaia) / 0.3, 2)
        
        # Health Score (0-100)
        h_score = 100.0
        h_score -= min(25.0, abs(t["st_teff"] - t["gaia_teff"]) / 20.0)
        h_score -= min(25.0, abs(t["st_rad"] - t["gaia_rad"]) / 0.05)
        if t["ruwe"] > 1.4: h_score -= 20.0
        if t["is_unphysical"]: h_score -= 30.0
        h_score = max(0.0, round(h_score, 1))
        
        h_grade = "A" if h_score >= 90 else ("B" if h_score >= 80 else ("C" if h_score >= 70 else ("D" if h_score >= 50 else "F")))

        cand = ExoplanetCandidate(
            id=uuid.uuid4(),
            host_id=star.id,
            tic_id=t["tic"],
            toi_id=t["toi"],
            pl_name=pl_name,
            disposition=t["disp"],
            orbper=t["orbper"],
            rade=t["rade"],
            trandep=t["trandep"],
            trandurh=t["trandurh"],
            insol=t["insol"],
            eqt=t["eqt"],
            density_transit=density_transit,
            density_gaia=density_gaia,
            density_discrepancy_sigma=density_sigma,
            centroid_shift_max=round(random.uniform(0.0, 0.25), 3),
            has_centroid_dip=(t["disp"] == "FP" and not t["is_unphysical"]),
            health_score=h_score,
            health_grade=h_grade,
            query_failed=False
        )
        db.add(cand)
        db.commit()

        # Add history
        db.add(MeasurementHistory(candidate_id=cand.id, source_id=src_toi.id, parameter_name="stellar_teff", value=t["st_teff"], error_upper=None, error_lower=None))
        db.add(MeasurementHistory(candidate_id=cand.id, source_id=src_gaia.id, parameter_name="stellar_teff", value=t["gaia_teff"], error_upper=None, error_lower=None))
        db.add(MeasurementHistory(candidate_id=cand.id, source_id=src_toi.id, parameter_name="stellar_radius", value=t["st_rad"], error_upper=None, error_lower=None))
        db.add(MeasurementHistory(candidate_id=cand.id, source_id=src_gaia.id, parameter_name="stellar_radius", value=t["gaia_rad"], error_upper=None, error_lower=None))
        db.add(MeasurementHistory(candidate_id=cand.id, source_id=src_toi.id, parameter_name="distance", value=t["st_dist"], error_upper=None, error_lower=None))
        db.add(MeasurementHistory(candidate_id=cand.id, source_id=src_gaia.id, parameter_name="distance", value=t["gaia_dist"], error_upper=None, error_lower=None))
        db.commit()

        # Agreement Metrics
        teff_diff = abs(t["st_teff"] - t["gaia_teff"])
        rad_diff = abs(t["st_rad"] - t["gaia_rad"])
        dist_diff = abs(t["st_dist"] - t["gaia_dist"])
        
        teff_rel = teff_diff / t["gaia_teff"]
        rad_rel = rad_diff / t["gaia_rad"]
        agreement_score = max(0.0, 1.0 - (teff_rel + rad_rel) / 2.0)

        metrics = AgreementMetrics(
            id=uuid.uuid4(),
            candidate_id=cand.id,
            teff_disagreement=teff_diff,
            rad_disagreement=rad_diff,
            dist_disagreement=dist_diff,
            ruwe=t["ruwe"],
            derived_rp_diff=derived_rp_diff,
            is_unphysical_rp=t["is_unphysical"],
            completeness_score=1.0,
            catalog_agreement_score=agreement_score
        )
        db.add(metrics)

        # ML Prediction 4-Class Probabilities
        if t["disp"] == "CP":
            p_planet, p_eb, p_act, p_noise = 0.94, 0.03, 0.02, 0.01
        elif t["is_unphysical"]:
            p_planet, p_eb, p_act, p_noise = 0.02, 0.95, 0.02, 0.01
        else:
            p_planet, p_eb, p_act, p_noise = round(t["conf_prob"], 2), round((1-t["conf_prob"])*0.6, 2), round((1-t["conf_prob"])*0.3, 2), 0.02

        pred = MLPrediction(
            id=uuid.uuid4(),
            candidate_id=cand.id,
            evidence_consistency_score=p_planet,
            followup_priority_score=t["priority"],
            prob_planet=p_planet,
            prob_eb=p_eb,
            prob_activity=p_act,
            prob_noise=p_noise,
            integrated_gradients={
                "global_lc": 0.28,
                "local_lc": 0.34,
                "centroid_drift": 0.18,
                "gaia_ruwe": 0.12,
                "teff_discrepancy": 0.08
            },
            feature_importance={
                "st_teff": 0.05,
                "Rad": 0.12,
                "pl_trandep": 0.22,
                "RUWE": 0.15,
                "pl_insol": 0.11,
                "derived_rp_diff": 0.35
            },
            calculated_at=datetime.utcnow()
        )
        db.add(pred)
        db.commit()

    total_cands = db.query(ExoplanetCandidate).count()
    conflict_count = db.query(AgreementMetrics).filter(AgreementMetrics.is_unphysical_rp == True).count()
    high_ruwe_count = db.query(AgreementMetrics).filter(AgreementMetrics.ruwe > 1.4).count()

    print("\nDatabase seeded successfully!")
    print(f"Total Candidates: {total_cands}")
    print(f"Unphysical Rad Candidates (Conflicts): {conflict_count}")
    print(f"High RUWE Candidates: {high_ruwe_count}")
    db.close()


if __name__ == "__main__":
    import sys

    print(SEED_WARNING)
    if "--erase-and-fabricate" not in sys.argv:
        raise SystemExit("Not running. Pass --erase-and-fabricate to proceed.")
    if "--force" not in sys.argv:
        _refuse_if_real_data_present()
    seed_database()
