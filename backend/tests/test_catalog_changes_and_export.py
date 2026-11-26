"""Catalog change tracking, the CSV/VOTable export with check columns, and the duration diagnostic artifact."""
import csv
import io
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.catalog_changes import classify_change
from main import app

client = TestClient(app)


def test_frozen_catalogs_are_crossmatch_changes_and_live_ones_are_updates():
    for frozen in ("Gaia DR3", "2MASS Photometry", "Pan-STARRS"):
        assert classify_change(frozen) == "crossmatch_change"
    assert classify_change("TOI Catalog") == "catalog_update"
    assert classify_change("NASA Exoplanet Archive") == "catalog_update"


def test_a_new_gaia_release_would_count_as_a_catalog_update():
    # DR4 arrives as a new source version; only a live/new source name is a revision, and the frozen
    # list is explicit, so adding DR4 later means it is NOT in FROZEN_SOURCES.
    assert classify_change("Gaia DR4") == "catalog_update"


def test_catalog_changes_endpoint_shape_and_caveat():
    r = client.get("/api/v1/catalog_changes", params={"limit": 20})
    assert r.status_code == 200
    d = r.json()
    assert {"count", "counts_by_kind", "events", "caveat"} <= set(d)
    assert "not the catalog release date" in d["caveat"]
    for e in d["events"]:
        assert e["kind"] in ("catalog_update", "crossmatch_change")
        assert e["old_value"] != e["new_value"]


def test_catalog_changes_kind_filter_and_validation():
    d = client.get("/api/v1/catalog_changes", params={"kind": "catalog_update", "limit": 50}).json()
    assert all(e["kind"] == "catalog_update" for e in d["events"])
    assert client.get("/api/v1/catalog_changes", params={"kind": "bogus"}).status_code == 422


def test_csv_export_has_check_columns_and_consistent_counts():
    r = client.get("/api/v1/candidates/export", params={"format": "csv", "limit": 40})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(r.text)))
    if not rows:
        pytest.skip("empty database")
    for col in ("ruwe", "derived_planet_radius_earth", "flag_ruwe_likely_binary", "checks_flagged",
                "checks_checkable", "info_giant_planet_ambiguity"):
        assert col in rows[0]
    for row in rows:
        flags = [int(row[c]) for c in row if c.startswith("flag_")]
        assert all(f in (-1, 0, 1) for f in flags)
        if int(row["checks_checkable"]) > 0:
            assert int(row["checks_flagged"]) == sum(1 for f in flags if f == 1)
            assert int(row["checks_checkable"]) == sum(1 for f in flags if f != -1)


def test_votable_export_still_works_and_rejects_unknown_format():
    assert client.get("/api/v1/candidates/export", params={"limit": 3}).status_code == 200
    assert client.get("/api/v1/candidates/export", params={"format": "xlsx"}).status_code == 422


def test_duration_diagnostic_reports_small_short_bin_honestly():
    r = client.get("/api/v1/predictions/duration_diagnostic")
    assert r.status_code == 200
    d = r.json()
    bins = {b["duration_bin"]: b for b in d["by_duration"]}
    assert set(bins) == {"< 2 h", "2-4 h", "> 4 h"}
    assert sum(b["n"] for b in bins.values()) <= d["n_kois"]
    # the short-transit bin is tiny; the report must carry an interval, not just a point value
    short = bins["< 2 h"]
    assert short["n"] < 30 and short["accuracy_ci95"][0] is not None
    assert "29.4" in d["cadence_note"]
