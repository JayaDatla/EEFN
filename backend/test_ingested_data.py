from app.db.session import SessionLocal
from app.db.models import HostStar, ExoplanetCandidate, AgreementMetrics, MLPrediction

db = SessionLocal()
stars = db.query(HostStar).count()
candidates = db.query(ExoplanetCandidate).count()
metrics = db.query(AgreementMetrics).count()
predictions = db.query(MLPrediction).count()

print("Database seeded report:")
print(f"  Host Stars: {stars}")
print(f"  Exoplanet Candidates: {candidates}")
print(f"  Agreement Metrics: {metrics}")
print(f"  ML Predictions: {predictions}")

if candidates > 0:
    cand = db.query(ExoplanetCandidate).first()
    print("\nFirst candidate details:")
    print(f"  Name: {cand.pl_name}")
    print(f"  TIC ID: {cand.tic_id}")
    print(f"  TOI ID: {cand.toi_id}")
    print(f"  Disposition: {cand.disposition}")
    print(f"  Period: {cand.orbper} days")
    print(f"  Radius: {cand.rade} R_earth")
    
    pred = db.query(MLPrediction).filter(MLPrediction.candidate_id == cand.id).first()
    if pred:
        print(f"  Evidence Consistency Score: {pred.evidence_consistency_score * 100:.2f}%")
        print(f"  Follow-up Priority: {pred.followup_priority_score * 100:.2f}%")
        print(f"  Top Feature Contributions: {pred.feature_importance}")
