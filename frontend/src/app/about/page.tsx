import { SectionHeading } from "../components/ScientificUI";
import { Callout } from "../components/ui/Callout";

export const metadata = {
  title: "What EEFN does and does not do | EEFN",
};

export default function AboutPage() {
  return (
    <div className="max-w-3xl animate-fadeIn">
      <SectionHeading
        eyebrow="SCOPE AND LIMITS"
        title="What EEFN does and does not do"
        description="Read this before trusting a single number this tool shows you."
      />

      <div className="surface-card space-y-6 p-6 text-sm leading-relaxed text-ink/90">
        <section>
          <h2 className="mb-2 text-sm font-semibold text-ink">What EEFN is</h2>
          <p>
            EEFN is an automated cross-catalog evidence auditor for transiting planet candidates. Given a TOI,
            it cross-matches NASA/TESS, Gaia DR3, 2MASS, and Pan-STARRS records, flags where those catalogs
            disagree with each other, and produces a health score, an evidence-consistency probability, and a
            follow-up priority ranking with a full audit trail (source, catalog version, query timestamp) behind
            every number. It exists to help an observer decide whether a candidate&apos;s catalog record is
            internally consistent enough to be worth scarce follow-up telescope time.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold text-ink">What EEFN is not</h2>
          <p>
            EEFN does not independently confirm exoplanets. The disposition labels its Random Forest model was
            trained on come from human astronomers who already used Gaia RUWE and distance to classify
            candidates -- so a model trained on those labels partly learns to reproduce that human
            categorization, not to detect planets from first principles. Treat every probability as
            &quot;how consistent is this record with records the curation process already called confirmed,&quot;
            not &quot;how likely is this to be a real planet&quot; in an absolute sense.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold text-ink">Measured, disclosed gaps</h2>
          <div className="space-y-3">
            <Callout tone="warning" title="Label leakage was tested, not assumed away">
              Two ablations (pre-Gaia-EDR3 subset comparison, RV-mass-confirmed clean holdout) found no strong
              evidence the model&apos;s accuracy is primarily circular reasoning -- but neither is a complete
              resolution. See <code>LIMITATIONS.md</code> §1.1 for the full methodology and caveats.
            </Callout>
            <Callout tone="warning" title="Calibration is measured, and imperfect">
              Brier score 0.1127 on held-out data. The model is well-calibrated at the extremes but measurably
              overconfident in the 0.2-0.4 predicted-probability range -- treat scores in that band as a modest
              overestimate.
            </Callout>
            <Callout tone="warning" title="The deep-learning model is real-trained, on a small sample">
              Retrained 2026-08-21 on 116 real Kepler stars (real light curves, real disposition + real
              false-positive-reason labels from the NASA Exoplanet Archive) -- no synthetic light curve
              remains in this training set. Held-out accuracy is <strong>60.9%</strong> on 92 real samples
              never trained on, against 100% training accuracy: a real, expected overfitting gap on a
              sample this small. It reliably separates a non-detection from a real signal (100% held-out on
              "Not Transit-Like") but cannot yet reliably tell a real planet transit from a real eclipsing
              binary (33-50% held-out on those two). Centroid data still has no real measurement for these
              Kepler stars. See <code>LIMITATIONS.md</code> §1.7 and the DL Model page for the full report.
            </Callout>
            <Callout tone="info" title="Only 5 of 7 planned catalogs are live">
              NASA/TOI, Gaia DR3 (source + astroparams), 2MASS, and Pan-STARRS are live with real provenance.
              Real MAST target-pixel-file centroid extraction and real spectroscopy cross-matching are limited
              to a small verification subset today, not full production coverage -- every response reports
              which model tier ran and how many catalogs actually contributed, rather than presenting a number
              computed from silently zero-filled missing catalogs as if it were complete.
            </Callout>
          </div>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold text-ink">If the backend is unreachable</h2>
          <p>
            Every page in this app shows an explicit, unmistakable error state on fetch failure. EEFN never
            substitutes fabricated or stale data for a real result -- if you see a number, it came from a real
            query that just ran.
          </p>
        </section>

        <p className="border-t border-border pt-4 text-xs text-muted">
          For the complete, itemized list of known limitations, mitigations, and future work, see{" "}
          <code>LIMITATIONS.md</code> and <code>docs/TOOL_COMPARISON.md</code> in the repository.
        </p>
      </div>
    </div>
  );
}
