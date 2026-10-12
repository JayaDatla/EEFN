import { SectionHeading } from "../components/ScientificUI";
import { Callout } from "../components/ui/Callout";
import { Table, TableHead, TableBody, Th, Td, Tr } from "../components/ui/Table";

export const metadata = {
  title: "Catalogs and Data Flow | EEFN",
};

const CATALOG_ROWS = [
  {
    name: "NASA Exoplanet Archive (TOI table)",
    gives: "The candidate itself: orbital period, transit depth/duration, TESS-reported planet radius, and the TESS pipeline's own stellar temperature/radius/distance estimate.",
    example: "TOI-1111.01: period 11.48 d, transit depth 8,341 ppm, reported planet radius 14.11 R⊕, host teff 7,262 K",
    coverage: "546 / 546 candidates (100%)",
    usedBy: "Both models",
  },
  {
    name: "Gaia DR3 Source + AstroParams",
    gives: "An independent, higher-precision stellar temperature, radius, distance, and RUWE (a single number that flags an unresolved binary star from its astrometric wobble).",
    example: "Same star, from Gaia: teff 7,464 K, radius 2.221 R☉, RUWE 0.992",
    coverage: "409 / 509 host stars (80.4%)",
    usedBy: "Both models — this is the other half of every disagreement calculation",
  },
  {
    name: "2MASS Photometry",
    gives: "Near-infrared brightness (J/H/K bands) — a temperature-sensitive measurement largely unaffected by interstellar dust, useful for cross-checking a star's temperature independent of Gaia's optical measurement.",
    example: "TOI-1111.01's host: J 9.055, H 8.953, K 8.892",
    coverage: "492 / 546 candidates (90.1%)",
    usedBy: "DL model only (3 of its 28 metadata inputs)",
  },
  {
    name: "Pan-STARRS",
    gives: "Optical brightness across g/r/i/z/y bands — a second independent photometric fingerprint of the star, used the same way as 2MASS.",
    example: "TOI-1000.01's host: i 10.644, z 9.969, y 9.892",
    coverage: "320 / 546 candidates (58.6%)",
    usedBy: "DL model only (2 of its 28 metadata inputs — g and r)",
  },
  {
    name: "APOGEE-2 Spectroscopy",
    gives: "A direct spectroscopic metallicity (Fe/H) and, where matched, a spectroscopic temperature/radius — measured from the star's actual spectrum rather than inferred from photometry.",
    example: "Real for 2 of 509 host stars today",
    coverage: "2 / 509 host stars (0.4%)",
    usedBy: "Both models, when present — real but rarely populated (see callout below)",
  },
  {
    name: "MAST TESS Target Pixel Files (centroid)",
    gives: "Whether the photocenter of the star shifts during the transit — a direct pixel-level check for whether the signal is actually happening on the target star or on a nearby contaminating source.",
    example: "Real for 5 of 546 candidates today",
    coverage: "5 / 546 candidates (0.9%)",
    usedBy: "DL model only — the model's third input channel, when present",
  },
];

const RF_FEATURES = [
  "pl_orbper, pl_trandurh, pl_trandep, pl_rade, pl_insol, pl_eqt — the transit's own geometry, from TOI",
  "st_teff, st_rad, st_logg, st_dist — TOI's stellar parameters",
  "teff_diff, teff_diff_rel, rad_diff, rad_diff_rel, dist_diff, dist_diff_rel — TOI vs. Gaia disagreement, raw and relative",
  "derived_rp_gaia, derived_rp_diff, derived_rp_diff_rel — the Gaia-corrected planet radius and how far it sits from TESS's reported radius",
  "is_unphysical_rp_gaia — 1 if the Gaia-corrected radius exceeds the 22 R⊕ physical limit for a transiting planet",
  "RUWE, high_ruwe — Gaia's astrometric-binarity signal, raw and thresholded (>1.4)",
  "completeness — how many of the 7 core stellar values above were actually measured for this star",
  "j_k, h_k, abs_K, ps_g_r — 2MASS and Pan-STARRS colours, plus absolute K magnitude from the Gaia parallax (a giant-vs-dwarf check on the catalog radius)",
];

export default function DataPipelinePage() {
  return (
    <div className="max-w-4xl animate-fadeIn">
      <SectionHeading
        eyebrow="HOW EEFN WORKS"
        title="From seven catalogs to one follow-up decision"
        description="What each catalog actually gives, how EEFN lines them up, and what it does with the disagreements it finds."
      />

      <div className="surface-card p-6 text-sm leading-relaxed text-ink/90">
        <p>
          A TESS Object of Interest (TOI) is a single measurement of a possible planet — one pipeline&apos;s
          read of the transit, at one point in time. It carries the transit&apos;s own geometry and one
          estimate of the host star. Nothing in the TOI record checks that estimate against an independent
          source. EEFN&apos;s job is to fetch the independent sources that do exist, line every candidate up
          against them by sky position, and compute — per candidate, with the full number trail kept — where
          they agree, where they don&apos;t, and whether the disagreement changes the physical picture enough
          that an astronomer should think twice before pointing a telescope at it.
        </p>
      </div>

      <section className="mt-8">
        <h2 className="mb-3 font-display text-lg font-medium text-ink">1. What each catalog gives</h2>
        <p className="mb-4 text-sm text-muted">
          Coverage numbers are counted directly from the live database (546 candidates / 509 distinct host
          stars) as of the current sync — not aspirational targets.
        </p>
        <div className="surface-card overflow-hidden p-0">
          <Table>
            <TableHead>
              <tr>
                <Th>Catalog</Th>
                <Th>What it gives</Th>
                <Th>Real example</Th>
                <Th>Live coverage</Th>
                <Th>Consumed by</Th>
              </tr>
            </TableHead>
            <TableBody>
              {CATALOG_ROWS.map((row) => (
                <Tr key={row.name}>
                  <Td><span className="font-medium text-ink">{row.name}</span></Td>
                  <Td>{row.gives}</Td>
                  <Td><span className="font-mono text-2xs">{row.example}</span></Td>
                  <Td>{row.coverage}</Td>
                  <Td>{row.usedBy}</Td>
                </Tr>
              ))}
            </TableBody>
          </Table>
        </div>
        <div className="mt-4">
          <Callout tone="info" title="Two of seven are real, but thin">
            Spectroscopy and MAST centroid extraction are genuinely wired into the pipeline and genuinely
            guarded against fabricated fallback data — but they only cover a handful of stars today, because
            real APOGEE-2 cross-matches and real target-pixel-file downloads only exist for a small
            verification subset so far, not the full candidate list. Every prediction reports which catalogs
            actually contributed, rather than presenting a score computed from silently zero-filled missing
            catalogs as if it were complete.
          </Callout>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 font-display text-lg font-medium text-ink">2. How they get lined up: cross-matching</h2>
        <div className="surface-card p-6 text-sm leading-relaxed text-ink/90 space-y-3">
          <p>
            TOI candidates and each catalog carry no shared ID — a TOI record doesn&apos;t know its own Gaia
            source ID. EEFN resolves this by sky position: it sends every candidate&apos;s RA/Dec to the CDS
            X-Match service (Strasbourg astronomical Data Centre) and asks for the nearest real object in each
            target catalog within <strong>5.0 arcseconds</strong>. Where a query returns more than one nearby
            candidate match, EEFN keeps only the closest (smallest angular separation) and discards the rest —
            a coordinate-based match, not a name-based one, which is what lets EEFN cross a TESS ID against a
            Gaia source ID that was never in the TOI record to begin with.
          </p>
          <p>
            Each star&apos;s TESS-catalog position is also proper-motion-corrected forward to the Gaia DR3
            reference epoch (2016.0) before the match runs, using the star&apos;s Gaia-measured proper motion —
            without that step, a fast-moving nearby star can drift far enough between catalog epochs to miss
            a naive fixed-radius match entirely.
          </p>
          <p>
            The result is stored keyed on <code className="text-accent">TIC &#123;id&#125;</code> as the host
            star&apos;s identity — so a later re-sync updates the same star record instead of creating a
            duplicate, and every individual measurement (this specific temperature, from this specific
            catalog, at this specific time) is kept in a separate provenance ledger rather than overwritten in
            place.
          </p>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 font-display text-lg font-medium text-ink">3. Merging and calculating disagreement</h2>
        <p className="mb-4 text-sm text-muted">
          A real walkthrough — TOI-1111.01 (TIC 412014494), a currently FP-dispositioned candidate — with the
          exact numbers as stored.
        </p>

        <div className="surface-card overflow-hidden p-0 mb-4">
          <Table>
            <TableHead>
              <tr>
                <Th>Measurement</Th>
                <Th>TOI Catalog</Th>
                <Th>Gaia DR3</Th>
                <Th>Disagreement</Th>
              </tr>
            </TableHead>
            <TableBody>
              <Tr>
                <Td><span className="font-medium text-ink">Host temperature</span></Td>
                <Td>7,262.0 K</Td>
                <Td>7,464.1 K</Td>
                <Td><span className="font-mono text-2xs">202.1 K</span></Td>
              </Tr>
              <Tr>
                <Td><span className="font-medium text-ink">Host radius</span></Td>
                <Td>2.130 R☉</Td>
                <Td>2.221 R☉</Td>
                <Td><span className="font-mono text-2xs">0.091 R☉</span></Td>
              </Tr>
              <Tr>
                <Td><span className="font-medium text-ink">Distance</span></Td>
                <Td>312.5 pc</Td>
                <Td>327.0 pc</Td>
                <Td><span className="font-mono text-2xs">14.5 pc</span></Td>
              </Tr>
            </TableBody>
          </Table>
        </div>

        <div className="surface-card p-6 text-sm leading-relaxed text-ink/90 space-y-3">
          <p>
            A ~200 K temperature disagreement alone isn&apos;t dramatic — real catalogs disagree by that much
            fairly often. What makes this candidate a real find is what happens when that Gaia radius is used
            to <em>recompute</em> the planet, instead of just trusting TESS&apos;s own number:
          </p>
          <div className="rounded-lg border border-border bg-surface-2/40 p-4 font-mono text-xs space-y-1">
            <div>TESS-reported planet radius: <strong className="text-ink">14.11 R⊕</strong></div>
            <div>Transit depth (measured): <strong className="text-ink">8,341 ppm</strong></div>
            <div>→ planet radius, recomputed from the <em>Gaia</em> host radius + this transit depth:</div>
            <div className="text-severity-critical font-bold">22.15 R⊕</div>
            <div className="pt-1 text-muted">Physical limit for any transiting planet (hydrogen/helium radius ceiling): ~22 R⊕</div>
          </div>
          <p>
            A single-catalog read of this candidate — TESS&apos;s own reported 14.11 R⊕ — looks like a plausible
            large sub-Neptune. Re-deriving the same planet&apos;s size from an independent stellar radius
            flips the verdict: at 22.15 R⊕ it is physically too large to be a planet at all. EEFN flags this
            as <code>is_unphysical_rp = true</code>. This candidate&apos;s real, human-assigned disposition in
            the archive is <strong>FP</strong> (false positive) — an eclipsing binary, not a planet. The
            catalog-fusion check reached the same conclusion the human vetting process did, from a completely
            different angle: not by looking at the light curve shape, but by noticing that two catalogs&apos;
            stellar measurements, taken together, describe an object too big to exist.
          </p>
          <p>
            A second, independent physics check runs in parallel: the planet&apos;s orbital period and transit
            duration alone imply a stellar density (Seager &amp; Mallén-Ornelas 2003) — for this system,{" "}
            <strong className="text-ink">183.5 g/cm³</strong>. Gaia&apos;s own stellar-evolutionary model for
            this star&apos;s measured mass and radius implies a density of{" "}
            <strong className="text-ink">0.224 g/cm³</strong> — a difference of roughly{" "}
            <strong className="text-severity-critical">8,000σ</strong>. Two unrelated derivations of the same
            physical quantity, from two different catalogs, landing nowhere near each other, is itself strong
            independent evidence this isn&apos;t a real planet transit.
          </p>
          <p className="text-muted text-xs">
            Result: health grade D (61.6/100), evidence-consistency score 0.29, follow-up priority 0.03 — this
            candidate is correctly pushed to the bottom of the queue rather than competing for scarce telescope
            time against candidates whose catalogs actually agree.
          </p>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 font-display text-lg font-medium text-ink">4. Feature extraction: what actually reaches each model</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="surface-card p-5">
            <h3 className="mb-2 text-sm font-semibold text-ink">Gradient-boosted trees (evidence-consistency score)</h3>
            <p className="mb-3 text-xs text-muted">
              27 engineered features, built once for training and reproduced feature-for-feature at inference
              so the model always sees the columns it was fit on. A missing input becomes a real, tracked
              missing value (imputed by the trained median imputer) — never a substituted default.
            </p>
            <ul className="space-y-1.5 text-xs text-ink/80 list-disc list-inside">
              {RF_FEATURES.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </div>
          <div className="surface-card p-5">
            <h3 className="mb-2 text-sm font-semibold text-ink">Light-curve vetter (real TESS light curves)</h3>
            <p className="mb-3 text-xs text-muted">
              Gradient-boosted trees over the numbers an astronomer checks by hand, computed from the
              detrended, phase-folded SPOC light curve and run nightly: transit depth and SNR, odd-vs-even
              depth difference, secondary-eclipse depth, flat-vs-V shape, duration against what the stellar
              density predicts, the implied planet radius, and the star&apos;s Teff / radius / colours.
            </p>
            <p className="mb-2 text-xs text-ink/80">
              It replaced a 3.9M-parameter CNN that scored 64% under the same cross-validation as the
              <strong> 83%</strong> of this model. A measurable missing value stays missing (NaN), never a
              substituted default. Centroid offsets from the real TESS pixels are reported alongside it, as
              separate evidence, rather than fused into the score.
            </p>
          </div>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 font-display text-lg font-medium text-ink">5. What an astronomer actually sees</h2>
        <div className="surface-card p-6 text-sm leading-relaxed text-ink/90">
          <p>
            Every candidate resolves to a health grade (A–F), an evidence-consistency score, and a follow-up
            priority score — each with the full measurement trail (which catalog, which value, when it was
            fetched) one click away. The point isn&apos;t to replace an astronomer&apos;s judgment; it&apos;s
            to do the cross-catalog arithmetic that&apos;s tedious to do by hand for hundreds of candidates, so
            a limited pool of follow-up telescope time gets pointed at candidates whose catalog record is
            actually self-consistent, instead of being spent re-discovering — one expensive observation at a
            time — that a candidate&apos;s own numbers already contradicted each other.
          </p>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 font-display text-lg font-medium text-ink">Why this doesn&apos;t already exist elsewhere</h2>
        <div className="surface-card p-6 text-sm leading-relaxed text-ink/90 space-y-3">
          <p>
            The published, actively-used vetting tools in this field check a different kind of evidence than
            EEFN does. TRICERATOPS derives a Bayesian false-positive probability from transit shape and
            pixel-level blend analysis. Robovetter runs rule-based diagnostic tests on the light curve
            (odd-even depth, secondary eclipse, centroid offset). AstroNet and ExoMiner are CNNs trained on
            real, human-vetted light-curve morphology. All four ask, in different ways: <em>does this transit
            signal look astrophysically real, and is it actually on the target star?</em>
          </p>
          <p>
            None of them ask whether the candidate&apos;s <em>catalog record itself</em> is internally
            consistent — whether the TESS pipeline&apos;s stellar parameters agree with Gaia&apos;s, whether
            Gaia flags the host as an unresolved binary, or whether the transit-implied stellar density matches
            the star&apos;s independently known evolutionary density. TOI-1111.01 above is exactly the case
            none of them would catch by their own primary method: a real, isolated star with a transit signal
            whose shape may look perfectly ordinary, where the false positive is only visible by putting two
            catalogs&apos; stellar measurements side by side.
          </p>
          <p className="font-medium text-ink">
            That makes EEFN a complement to those tools, not a replacement for them — the honest, defensible
            claim is narrower than &quot;better vetting&quot;: EEFN surfaces a specific, currently-unaddressed
            false-confidence mode (catalog disagreement) that the field&apos;s most-used vetting tools don&apos;t
            check, and a real pipeline gets the most value running both checks together.
          </p>
          <p className="text-xs text-muted border-t border-border pt-3">
            Full methodology-level comparison, including where this project&apos;s own light-curve vetter
            currently loses ground to AstroNet/ExoMiner (they train on tens of thousands of real light curves;
            this project&apos;s light-curve vetter is trained on 169 real Kepler stars: ~83% cross-validated, 76% agreement on 50 real TESS targets) — see{" "}
            <code>docs/TOOL_COMPARISON.md</code> and <code>LIMITATIONS.md</code> in the repository.
          </p>
        </div>
      </section>
    </div>
  );
}
