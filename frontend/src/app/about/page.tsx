import { SectionHeading } from "../components/ScientificUI";
import { Callout } from "../components/ui/Callout";

export const metadata = {
  title: "What EEFN does and does not do | EEFN",
};

export default function AboutPage() {
  return (
    <div className="max-w-5xl animate-fadeIn">
      <SectionHeading
        eyebrow="SCOPE AND LIMITS"
        title="What EEFN does and does not do"
        description="Read this before trusting a single number this tool shows you."
      />

      <div className="surface-card space-y-6 p-6 text-sm leading-relaxed text-ink/90">
        <section>
          <h2 className="mb-2 text-sm font-semibold text-ink">What EEFN is</h2>
          <p>
            EEFN is a time-saving evidence view for transiting planet candidates. Given a TOI, it cross-matches
            NASA/TESS, Gaia DR3, 2MASS, and Pan-STARRS records and shows, in one place, where those catalogs
            disagree with each other, with a full audit trail (source, catalog version, query timestamp) behind
            every number. A model grade is included as an optional second opinion. Many of these checks are
            already part of standard vetting; the aim is to apply them quickly and consistently, for example to
            older unresolved candidates, so an observer can decide faster whether a candidate&apos;s record is
            consistent enough to be worth scarce follow-up telescope time. It is not a planet predictor.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold text-ink">What EEFN is not</h2>
          <p>
            EEFN does not independently confirm exoplanets. The disposition labels its gradient-boosted model was
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
            <Callout tone="warning" title="The score mostly reproduces the TOI table, and it gets worse on new candidates">
              Held-out AUC is 0.93 under star-grouped cross-validation, but the TOI table&apos;s own columns alone
              reach 0.92: the cross-catalog (Gaia, 2MASS, Pan-STARRS) features add about +0.007 AUC
              (95% CI +0.001 to +0.013). Scored the way it would really be used &mdash; train on older TOIs, score
              later ones &mdash; AUC falls to 0.84&ndash;0.88 and the cross-catalog features add nothing. Treat the score as a
              prior learned from catalog values, not as evidence that a planet is real. Details:{" "}
              <code>LIMITATIONS.md</code> §1.3.
            </Callout>
            <Callout tone="warning" title="The A–F grade is the model's planet probability, checked on stars it never saw">
              The grade bands the tabular model&apos;s planet probability (A &ge; 0.90, B &ge; 0.75, C &ge; 0.50,
              D &ge; 0.25, F below; cut points fixed in advance, not tuned). It replaced a hand-weighted
              catalog-consistency score whose grade A was a false positive 39% of the time. On held-out stars
              (star-grouped cross-validation) the new grade A is a false positive <strong>6.6%</strong> of the time
              (grade B 15%, C 39%, D 61%, F 94%); scored forward in time (train on older TOIs, grade newer ones)
              grade A is 4&ndash;15% false positives. That is a measured rate, not a promise: it inherits every
              limit of the score above, including that human labels are partly set from the same catalog evidence.
              Live numbers: <code>GET /api/v1/health/validation</code> (<code>out_of_sample</code> is the one to
              trust; the top-level figures are on rows the model trained on). Details:{" "}
              <code>validation/scripts/split_validation.py</code>.
            </Callout>
            <Callout tone="info" title="Catalog-hygiene flags: an association, not independent validation">
              Fitting the one data-calibrated threshold (the transit-vs-Gaia density band) on older TOIs only and
              applying it to newer stars, TOIs with at least one core flag were later marked false positive
              39&ndash;42 percentage points more often than unflagged ones. Dispositions are partly decided from
              the same Gaia evidence, so this can overstate the effect and does not show the flags add information
              beyond existing vetting. The density band is calibrated on confirmed planets, which are shaped by
              detection and follow-up biases: an unusual candidate may be real, so read a flag as &quot;unusual&quot;,
              not &quot;wrong&quot;. The frozen prospective snapshot has not resolved yet.
              (<code>GET /api/v1/predictions/flag_validation</code>)
            </Callout>
            <Callout tone="info" title="Giant planet or brown dwarf: radius alone cannot tell">
              Candidates with a radius above about 8 R&oplus; and no measured mass show an informational note. At
              that size planets and brown dwarfs overlap (empirical range ~0.7&ndash;1.4 Jupiter radii, Carmichael
              2023); a radial-velocity mass would settle it. The note does not make a brown dwarf more likely and
              does not affect any grade or check.
            </Callout>
            <Callout tone="warning" title="Short transits may be smeared by the 29.4-minute binning">
              The light-curve vetter works on 29.4-minute bins; 143 of 560 candidates have transits shorter than
              2 hours. Accuracy for short transits has not been measured separately.
            </Callout>
            <Callout tone="warning" title="Calibration is measured, and imperfect">
              Brier score 0.100 on held-out data (the previous Random Forest scored 0.113). The score is well
              calibrated at the extremes but mildly <em>under</em>-confident in the 0.2-0.5 range (predicted ~0.26,
              observed ~0.41) -- treat scores in that band as a modest underestimate.
            </Callout>
            <Callout tone="warning" title="Light-curve vetting: measured on Kepler, weaker on TESS">
              A gradient-boosted model over physics features (odd/even depth, secondary eclipse, transit shape,
              implied radius) vets each candidate&apos;s <strong>real</strong> TESS light curve. Star-grouped
              cross-validation on 169 real Kepler stars: <strong>83%</strong> (&plusmn;6). On 50 real TESS targets
              with known TFOP dispositions it agrees with the human label <strong>76%</strong> of the time
              (ROC-AUC 0.81; it finds 88% of planets but also calls 36% of false positives planets, so a "Planet"
              verdict is weaker evidence than "Not Transit-Like") -- a real drop from the Kepler number, and those labels were assigned by people who
              inspected the same light curves, so this measures reproduction of human vetting. It replaced a CNN
              that scored 64% under the same protocol. Probability calibration is checked on Kepler only, not on TESS. See{" "}
              <code>LIMITATIONS.md</code> §1.7 and the Light-Curve Vetting page.
            </Callout>
            <Callout tone="info" title="Only 5 of 7 planned catalogs feed every candidate">
              NASA/TOI, Gaia DR3 (source + astroparams), 2MASS, and Pan-STARRS are live with real provenance.
              Real TESS centroid offsets, APOGEE-2 spectroscopy and real light-curve vetting now run on a nightly
              schedule, a few candidates per night, so coverage grows incrementally rather than being complete
              today -- every response reports which model tier ran and how many catalogs actually contributed,
              and an unmeasured value is reported as unmeasured, never as a clean zero.
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
