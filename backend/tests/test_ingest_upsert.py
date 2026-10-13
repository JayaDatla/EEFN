import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import HostStar, ExoplanetCandidate, AgreementMetrics, MeasurementHistory, DispositionChangeEvent
from app.pipeline import ingest as ingest_module


NASA_ROW_V1 = {
    "toi": "5001.01", "tid": 900001, "tfopwg_disp": "PC",
    "ra": 120.0, "dec": -10.0,
    "st_tmag": 10.0, "st_teff": 5500.0, "st_tefferr1": 50.0, "st_tefferr2": -50.0,
    "st_rad": 1.0, "st_raderr1": 0.05, "st_raderr2": -0.05,
    "st_logg": 4.4, "st_dist": 100.0, "st_disterr1": 5.0, "st_disterr2": -5.0,
    "pl_orbper": 4.0, "pl_trandurh": 2.5, "pl_trandep": 1200.0, "pl_trandeperr1": 60.0, "pl_trandeperr2": -60.0,
    "pl_rade": 1.8, "pl_radeerr1": 0.15, "pl_radeerr2": -0.15,
    "pl_insol": 200.0, "pl_eqt": 900.0,
}


def _gaia_source_csv():
    return (
        "toi,Source,Plx,e_Plx,RUWE,Gmag,BPmag,RPmag,PM,pmRA,pmDE,angDist\n"
        "5001.01,111111,10.0,0.1,1.05,10.2,10.5,9.9,5.0,1.0,1.0,0.5\n"
    )


def _gaia_param_csv():
    return (
        "toi,Source,Teff,b_Teff,B_Teff,logg,b_logg,B_logg,Dist,b_Dist,B_Dist,Rad,b_Rad,B_Rad,"
        "Rad-Flame,Mass-Flame,Lum-Flame,Age-Flame,angDist\n"
        "5001.01,111111,5480.0,5400.0,5560.0,4.4,4.3,4.5,98.0,95.0,101.0,1.02,0.97,1.07,1.02,1.0,1.0,5.0,0.5\n"
    )


@pytest.fixture()
def isolated_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _mock_endpoints(requests_mock, nasa_rows):
    requests_mock.get(ingest_module.NASA_TAP_URL, json=nasa_rows)
    requests_mock.post(
        ingest_module.CDS_XMATCH_URL,
        additional_matcher=lambda request: b"gaiadr3" in request.body,
        text=_gaia_source_csv(),
    )
    requests_mock.post(
        ingest_module.CDS_XMATCH_URL,
        additional_matcher=lambda request: b"paramp" in request.body,
        text=_gaia_param_csv(),
    )
    # UPGRADE_PLAN.md F.5: 2MASS/Pan-STARRS calls must be mocked too, or an unmocked
    # requests_mock URL makes post_with_retry's retry-with-sleep loop run for real
    # (3 attempts x several seconds each) on every test that ingests -- slow, not just
    # wrong. Empty results ("no match") since these fixtures don't need real photometry.
    requests_mock.post(
        ingest_module.CDS_XMATCH_URL,
        additional_matcher=lambda request: b"II/246/out" in request.body,
        text="toi,Jmag,e_Jmag,Hmag,e_Hmag,Kmag,e_Kmag,angDist\n",
    )
    requests_mock.post(
        ingest_module.CDS_XMATCH_URL,
        additional_matcher=lambda request: b"II/349/ps1" in request.body,
        text="toi,gmag,e_gmag,rmag,e_rmag,imag,e_imag,zmag,e_zmag,ymag,e_ymag,angDist\n",
    )


def test_ingestion_upserts_existing_candidate_instead_of_skipping(isolated_db, requests_mock):
    """UPGRADE_PLAN.md A.10/C.10: the old create-only guards meant a TOI whose
    disposition flipped (e.g. PC -> FP) never updated in the DB on re-ingestion."""
    _mock_endpoints(requests_mock, [NASA_ROW_V1])
    result = ingest_module.ingest_and_fuse_data(isolated_db, limit=10)
    assert result["status"] == "success"

    cand = isolated_db.query(ExoplanetCandidate).filter(ExoplanetCandidate.pl_name == "TOI-5001.01").first()
    assert cand is not None
    assert cand.disposition == "PC"
    first_id = cand.id

    star_count_after_first_run = isolated_db.query(HostStar).count()
    assert star_count_after_first_run == 1

    # Re-run with a flipped disposition and a changed transit depth, simulating an
    # updated catalog record for the same target on a later sync.
    nasa_row_v2 = dict(NASA_ROW_V1)
    nasa_row_v2["tfopwg_disp"] = "FP"
    nasa_row_v2["pl_trandep"] = 5000.0
    _mock_endpoints(requests_mock, [nasa_row_v2])

    result2 = ingest_module.ingest_and_fuse_data(isolated_db, limit=10)
    assert result2["status"] == "success"

    all_candidates = isolated_db.query(ExoplanetCandidate).filter(ExoplanetCandidate.pl_name == "TOI-5001.01").all()
    assert len(all_candidates) == 1, "re-ingestion must not create a duplicate row"
    assert all_candidates[0].id == first_id, "the same row must be updated in place"
    assert all_candidates[0].disposition == "FP", "disposition flip must actually reach the DB"
    assert all_candidates[0].trandep == 5000.0

    assert isolated_db.query(HostStar).count() == 1, "re-ingestion must not duplicate the host star either"

    metrics = isolated_db.query(AgreementMetrics).filter(AgreementMetrics.candidate_id == first_id).all()
    assert len(metrics) == 1, "re-ingestion must not create a duplicate AgreementMetrics row"

    # UPGRADE_PLAN.md H.3.5: the PC -> FP flip above must be logged as a real,
    # timestamped DispositionChangeEvent for the diff/"what changed" view.
    change_events = isolated_db.query(DispositionChangeEvent).filter(DispositionChangeEvent.candidate_id == first_id).all()
    disposition_events = [e for e in change_events if e.field_name == "disposition"]
    assert len(disposition_events) == 1, "the disposition flip must be logged exactly once"
    assert disposition_events[0].old_value == "PC"
    assert disposition_events[0].new_value == "FP"
    assert disposition_events[0].changed_at is not None


def test_ingestion_does_not_log_a_change_event_for_a_brand_new_candidate(isolated_db, requests_mock):
    """A candidate's first-ever ingestion must not be logged as a "change" -- there
    was no real prior value for it to have changed from."""
    _mock_endpoints(requests_mock, [NASA_ROW_V1])
    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)
    assert isolated_db.query(DispositionChangeEvent).count() == 0


def test_ingestion_logs_no_change_event_when_disposition_is_unchanged(isolated_db, requests_mock):
    _mock_endpoints(requests_mock, [NASA_ROW_V1])
    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)
    _mock_endpoints(requests_mock, [NASA_ROW_V1])  # identical row, re-ingested
    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)
    disposition_events = isolated_db.query(DispositionChangeEvent).filter(DispositionChangeEvent.field_name == "disposition").all()
    assert len(disposition_events) == 0


def test_ingestion_writes_measurement_history_provenance(isolated_db, requests_mock):
    """UPGRADE_PLAN.md D.1: MeasurementHistory is the product's core trust mechanism --
    the model existed but ingestion never wrote to it. Each source's value for
    teff/radius/distance must land as its own row, and re-ingesting unchanged upstream
    data must not duplicate rows (only a genuine value change gets a new one)."""
    _mock_endpoints(requests_mock, [NASA_ROW_V1])
    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)

    cand = isolated_db.query(ExoplanetCandidate).filter(ExoplanetCandidate.pl_name == "TOI-5001.01").first()
    rows = isolated_db.query(MeasurementHistory).filter(MeasurementHistory.candidate_id == cand.id).all()

    by_source_param = {(r.source.name, r.parameter_name): r for r in rows}
    assert by_source_param[("TOI Catalog", "stellar_teff")].value == NASA_ROW_V1["st_teff"]
    assert by_source_param[("TOI Catalog", "stellar_teff")].error_upper == NASA_ROW_V1["st_tefferr1"]
    assert by_source_param[("Gaia DR3", "stellar_teff")].value == 5480.0
    assert by_source_param[("TOI Catalog", "stellar_radius")].value == NASA_ROW_V1["st_rad"]
    assert by_source_param[("Gaia DR3", "stellar_radius")].value == 1.02
    assert by_source_param[("TOI Catalog", "distance")].value == NASA_ROW_V1["st_dist"]
    assert by_source_param[("Gaia DR3", "distance")].value == 98.0
    assert len(rows) == 6, "one row per (source, parameter) on first ingest"

    # Re-run with identical upstream data: no new rows should appear.
    _mock_endpoints(requests_mock, [NASA_ROW_V1])
    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)
    rows_after_replay = isolated_db.query(MeasurementHistory).filter(MeasurementHistory.candidate_id == cand.id).all()
    assert len(rows_after_replay) == 6, "re-ingesting unchanged values must not duplicate history rows"

    # Re-run with a genuinely changed TOI teff: exactly one new row should appear.
    nasa_row_v2 = dict(NASA_ROW_V1)
    nasa_row_v2["st_teff"] = 5600.0
    _mock_endpoints(requests_mock, [nasa_row_v2])
    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)
    rows_after_change = isolated_db.query(MeasurementHistory).filter(MeasurementHistory.candidate_id == cand.id).all()
    assert len(rows_after_change) == 7, "a genuine value change must append exactly one new provenance row"
    toi_teff_rows = [r for r in rows_after_change if r.parameter_name == "stellar_teff" and r.source.name == "TOI Catalog"]
    assert len(toi_teff_rows) == 2
    latest = max(toi_teff_rows, key=lambda r: r.measured_at)
    assert latest.value == 5600.0


def test_ingestion_propagates_derived_radius_uncertainty(isolated_db, requests_mock):
    """UPGRADE_PLAN.md E.3: a derived radius must carry a real, propagated uncertainty
    end to end -- not a bare point estimate, and not a fabricated constant."""
    _mock_endpoints(requests_mock, [NASA_ROW_V1])
    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)

    cand = isolated_db.query(ExoplanetCandidate).filter(ExoplanetCandidate.pl_name == "TOI-5001.01").first()
    assert cand.rade_err_upper == NASA_ROW_V1["pl_radeerr1"]
    assert cand.rade_err_lower == NASA_ROW_V1["pl_radeerr2"]

    metrics = cand.agreement_metrics
    assert metrics.derived_rp_gaia is not None
    assert metrics.derived_rp_gaia > 0
    assert metrics.derived_rp_gaia_err is not None
    assert metrics.derived_rp_gaia_err > 0

    # A target with a much less precisely measured Gaia radius must get a larger
    # propagated uncertainty on the derived radius, all else equal -- never a fixed
    # value regardless of actual measurement quality.
    loose_row = dict(NASA_ROW_V1)
    loose_row.update({"toi": "5002.01", "tid": 900002})

    def _mock_loose(requests_mock):
        requests_mock.get(ingest_module.NASA_TAP_URL, json=[loose_row])
        requests_mock.post(
            ingest_module.CDS_XMATCH_URL,
            additional_matcher=lambda request: b"gaiadr3" in request.body,
            text=_gaia_source_csv().replace("5001.01", "5002.01"),
        )
        loose_param_csv = (
            "toi,Source,Teff,b_Teff,B_Teff,logg,b_logg,B_logg,Dist,b_Dist,B_Dist,Rad,b_Rad,B_Rad,"
            "Rad-Flame,Mass-Flame,Lum-Flame,Age-Flame,angDist\n"
            "5002.01,111112,5480.0,5400.0,5560.0,4.4,4.3,4.5,98.0,95.0,101.0,1.02,0.7,1.3,1.02,1.0,1.0,5.0,0.5\n"
        )
        requests_mock.post(
            ingest_module.CDS_XMATCH_URL,
            additional_matcher=lambda request: b"paramp" in request.body,
            text=loose_param_csv,
        )

    _mock_loose(requests_mock)
    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)
    loose_cand = isolated_db.query(ExoplanetCandidate).filter(ExoplanetCandidate.pl_name == "TOI-5002.01").first()
    assert loose_cand.agreement_metrics.derived_rp_gaia_err > metrics.derived_rp_gaia_err


def test_ingestion_populates_2mass_and_panstarrs_photometry(isolated_db, requests_mock):
    """UPGRADE_PLAN.md F.5: 2MASS/Pan-STARRS must actually reach HostStar and
    MeasurementHistory, not just be queried and discarded."""
    _mock_endpoints(requests_mock, [NASA_ROW_V1])
    # Override the default empty-result 2MASS/Pan-STARRS mocks from _mock_endpoints
    # with real matches for this test.
    requests_mock.post(
        ingest_module.CDS_XMATCH_URL,
        additional_matcher=lambda request: b"II/246/out" in request.body,
        text="toi,Jmag,e_Jmag,Hmag,e_Hmag,Kmag,e_Kmag,angDist\n5001.01,9.5,0.02,9.1,0.03,9.0,0.02,0.4\n",
    )
    requests_mock.post(
        ingest_module.CDS_XMATCH_URL,
        additional_matcher=lambda request: b"II/349/ps1" in request.body,
        text="toi,gmag,e_gmag,rmag,e_rmag,imag,e_imag,zmag,e_zmag,ymag,e_ymag,angDist\n"
             "5001.01,12.1,0.01,11.8,0.01,11.6,0.01,11.5,0.01,11.4,0.02,0.4\n",
    )

    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)

    star = isolated_db.query(HostStar).filter(HostStar.hostname == "TIC 900001").first()
    assert star is not None
    assert star.j_mag == 9.5
    assert star.h_mag == 9.1
    assert star.k_mag == 9.0
    assert star.g_mag == 12.1
    assert star.r_mag == 11.8
    assert star.i_mag == 11.6
    assert star.z_mag == 11.5
    assert star.y_mag == 11.4

    cand = isolated_db.query(ExoplanetCandidate).filter(ExoplanetCandidate.pl_name == "TOI-5001.01").first()
    photometry_rows = (
        isolated_db.query(MeasurementHistory)
        .filter(MeasurementHistory.candidate_id == cand.id, MeasurementHistory.parameter_name.in_(
            ["j_mag", "h_mag", "k_mag", "g_mag", "r_mag", "i_mag", "z_mag", "y_mag"]))
        .all()
    )
    assert len(photometry_rows) == 8
    j_mag_row = next(r for r in photometry_rows if r.parameter_name == "j_mag")
    assert j_mag_row.source.name == "2MASS Photometry"
    assert j_mag_row.value == 9.5
    g_mag_row = next(r for r in photometry_rows if r.parameter_name == "g_mag")
    assert g_mag_row.source.name == "Pan-STARRS"


def test_ingestion_computes_real_completeness_score(isolated_db, requests_mock):
    """UPGRADE_PLAN.md A.10/C.10: completeness_score was previously hardcoded to 1.0
    regardless of actual field coverage."""
    _mock_endpoints(requests_mock, [NASA_ROW_V1])
    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)

    cand = isolated_db.query(ExoplanetCandidate).filter(ExoplanetCandidate.pl_name == "TOI-5001.01").first()
    metrics = cand.agreement_metrics
    assert metrics is not None
    # All 7 completeness fields (st_teff, gaia_teff, st_rad, gaia_rad, st_dist, gaia_dist,
    # ruwe) are populated in this fixture, so completeness should be a real 1.0 -- but
    # computed from actual coverage, not hardcoded regardless of what's present.
    assert metrics.completeness_score == pytest.approx(1.0)


def test_ingestion_stores_toi_side_host_values_next_to_the_gaia_ones(isolated_db, requests_mock):
    """The catalog-disagreement features compare the TOI table's host values with Gaia's, so both
    must survive ingestion; storing only Gaia's made the served features compare Gaia with itself."""
    _mock_endpoints(requests_mock, [NASA_ROW_V1])
    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)
    star = isolated_db.query(HostStar).first()
    assert (star.toi_teff, star.toi_rad, star.toi_dist, star.toi_logg) == (5500.0, 1.0, 100.0, 4.4)
    assert (star.teff, star.rad, star.distance) == (5480.0, 1.02, 98.0)      # Gaia values, distinct


def test_no_gaia_radius_means_no_derived_radius_not_an_invented_one(isolated_db, requests_mock):
    """`pl_rade or 1.0` used to stand in for a missing Gaia-derived radius, so a star Gaia never
    characterised read as 'perfect agreement' and could never trip the unphysical-radius check."""
    def no_astroparams_csv():
        return ("toi,Source,Teff,b_Teff,B_Teff,logg,b_logg,B_logg,Dist,b_Dist,B_Dist,Rad,b_Rad,B_Rad,"
                "Rad-Flame,Mass-Flame,Lum-Flame,Age-Flame,angDist\n")

    _mock_endpoints(requests_mock, [NASA_ROW_V1])
    requests_mock.post(
        ingest_module.CDS_XMATCH_URL,
        additional_matcher=lambda request: b"paramp" in request.body,
        text=no_astroparams_csv(),
    )
    ingest_module.ingest_and_fuse_data(isolated_db, limit=10)
    metrics = isolated_db.query(AgreementMetrics).first()
    assert metrics.derived_rp_gaia is None and metrics.derived_rp_diff is None
    assert metrics.is_unphysical_rp is False
