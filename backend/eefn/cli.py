"""
`eefn` command-line entry point (UPGRADE_PLAN.md D.4/G). Subcommands:

    eefn audit --toi 1017.01                  # print the full evidence report for one candidate
    eefn sync --limit 100                     # run ingestion synchronously against the local DB
    eefn export --format csv|json|votable     # dump the current candidate table

One thing intentionally NOT implemented here, to avoid claiming support the code
doesn't actually have: `--sector` filtering. The plan's example command was
`eefn sync --sector 31`, but the underlying NASA TOI query (app/pipeline/ingest.py)
has no TESS-sector predicate today -- adding one is real science-layer work, not a
packaging concern. `--limit` is what actually exists and works.
"""
import argparse
import csv
import json
import sys
from datetime import datetime, date

from eefn import audit_candidate, sync_candidates
from app.db.session import SessionLocal
from app.db.models import ExoplanetCandidate
from app.export import build_candidates_votable_bytes


def _json_default(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _cmd_audit(args: argparse.Namespace) -> int:
    try:
        report = audit_candidate(toi=args.toi)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, default=_json_default))
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    result = sync_candidates(limit=args.limit)
    print(json.dumps(result, indent=2, default=_json_default))
    return 0 if result.get("status") in ("success", "partial_failure") else 1


def _cmd_export(args: argparse.Namespace) -> int:
    if args.format == "votable":
        db = SessionLocal()
        try:
            vot_bytes = build_candidates_votable_bytes(db)
        finally:
            db.close()
        if args.output is None:
            sys.stdout.buffer.write(vot_bytes)
        else:
            with open(args.output, "wb") as f:
                f.write(vot_bytes)
        return 0

    db = SessionLocal()
    try:
        candidates = db.query(ExoplanetCandidate).order_by(ExoplanetCandidate.toi_id.asc()).all()
        rows = [
            {
                "pl_name": c.pl_name,
                "tic_id": c.tic_id,
                "toi_id": c.toi_id,
                "disposition": c.disposition,
                "orbper": c.orbper,
                "rade": c.rade,
                "rade_err_upper": c.rade_err_upper,
                "rade_err_lower": c.rade_err_lower,
                "trandep": c.trandep,
                "trandurh": c.trandurh,
                "health_score": c.health_score,
                "health_grade": c.health_grade,
            }
            for c in candidates
        ]
    finally:
        db.close()

    out = sys.stdout if args.output is None else open(args.output, "w", newline="")
    try:
        if args.format == "json":
            json.dump(rows, out, indent=2, default=_json_default)
            out.write("\n")
        else:
            writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()) if rows else [])
            writer.writeheader()
            writer.writerows(rows)
    finally:
        if out is not sys.stdout:
            out.close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="eefn", description="EEFN evidence-auditor CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_audit = subparsers.add_parser("audit", help="Print the full evidence report for one candidate")
    p_audit.add_argument("--toi", type=float, required=True, help="TOI ID, e.g. 1017.01")
    p_audit.set_defaults(func=_cmd_audit)

    p_sync = subparsers.add_parser("sync", help="Run ingestion synchronously against the local DB")
    p_sync.add_argument("--limit", type=int, default=100, help="Max targets to fetch from NASA TAP")
    p_sync.set_defaults(func=_cmd_sync)

    p_export = subparsers.add_parser("export", help="Export the candidate table")
    p_export.add_argument("--format", choices=["csv", "json", "votable"], default="csv")
    p_export.add_argument("--output", default=None, help="Output file path (default: stdout)")
    p_export.set_defaults(func=_cmd_export)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
