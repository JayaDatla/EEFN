# EEFN feedback pack

For observers, TFOP members and citizen-science groups who choose TESS candidates (TOIs) for follow-up.
Nothing here has been posted anywhere; this is the material to use when asking.

## What EEFN is (and is not)

EEFN puts the cross-catalog evidence for a TOI on one page, with the source and time of every number, so
you do not have to assemble it by hand. It does **not** predict or confirm planets and does not rank
candidates by a hidden score.

For each TOI it shows five fixed, rule-based checks (no model):

| Check | Flags when |
|---|---|
| Gaia RUWE | above 1.4 |
| Planet radius recomputed from depth and the Gaia stellar radius | above 22 Earth radii |
| Transit-derived stellar density vs Gaia density | outside a band calibrated on confirmed planets |
| Effective temperature, TOI vs Gaia | differs by more than 400 K |
| Stellar radius, TOI vs Gaia | differs by more than 30 percent |

A check that cannot run is shown as unknown, never as passed. It also shows, separately and clearly
labelled as optional: a model grade, and a light-curve vetter result for a few candidates. An informational
note marks radii above about 8 Earth radii (giant planet or brown dwarf cannot be told apart by radius).
Catalog value changes between ingestions are listed on the Changes page, and a link goes to each TOI's
ExoFOP-TESS page (EEFN links to notes; it does not copy them).

Open source (BSD-3-Clause): https://github.com/JayaDatla/EEFN. There is no hosted demo yet; it runs locally
(see `README.md`), and `GET /api/v1/candidates/export?format=csv` (or `votable`) gives the whole table
with the check values, so you can apply your own cuts in Python.

## Known limits (please read before judging it)

- The rule-based flags are associated with later false-positive dispositions on past data, but those
  dispositions were partly based on the same indicators, so this is **not** independent validation. A
  frozen test on 108 unresolved TOIs (registered 2026-10-13) will give a cleaner answer around April 2027.
- The density band is calibrated on confirmed planets, which are shaped by detection and follow-up
  biases. A flag means "unusual", not "wrong".
- RUWE misses close companions. A clean result means "no catalog red flags", not "planet".
- The light-curve vetter was trained on Kepler (29.4-minute cadence). Only 18 of its 205 training
  examples have transits under 2 hours, while 143 of 560 live candidates are that short. Its accuracy
  there is unmeasured.
- No astronomer has used it on a real target list yet. That is what this request is about.

## What we would like to learn

1. Which of the five checks do you already run, and which would you never bother with?
2. Which are missing? (Name the one thing you most often look up by hand.)
3. Is any check misleading, or does it flag things you would not worry about?
4. How long does assembling this evidence for one TOI take you today?
5. Would a table or API export fit your workflow better than a web page? Which columns?
6. Would "what changed in the catalogs for this TOI since last time" be useful, and how often?

You do not need to try the tool to answer. If it would be useful, we can send a short, optional task (see
`docs/time_saved_study.md`) that takes under an hour.

## Draft post (not posted)

> **Feedback wanted: a free, open-source evidence page for TESS candidates**
>
> We are a small student team building EEFN, which puts the cross-catalog checks for a TOI (Gaia RUWE,
> planet radius from the Gaia stellar radius, transit vs Gaia stellar density, TOI vs Gaia Teff and
> radius) on one page with the source of every value, plus a CSV/VOTable export. It does not predict or
> confirm planets. We are not trying to replace your workflow and we have no endorsement from any
> project. We want to know whether it would save you time when choosing TOIs, which checks are missing or
> misleading, and what it would need to be useful. Repository and limitations: https://github.com/JayaDatla/EEFN
> Questions: which checks do you already run, what takes the most time, and what would you want exported?
> Happy to credit anyone who helps and to report back what changed.

## Etiquette (from the research notes; check each group's own rules)

- Ask in one place at a time, and read the group's rules first. Do not cross-post the same message.
- Do not cold-email TFOP chairs about a project. Join through the application process or an introduction.
- Never present the tool as endorsed by TFOP, TESS, NASA or any team.
- ExoFOP: observation notes and files belong to the uploader. Link to them; do not mirror them. Follow
  the ExoFOP conduct policy (contact the uploader before using their data in an analysis, cite it, use
  the standard acknowledgement). Do not use proprietary TFOP data.
- Do not scrape ExoFOP aggressively. Its download URLs are unofficial patterns and may change.
- Offer credit, and report back what you changed because of the feedback.

## Where to ask (ranked, from the research; some channels unverified)

1. Exoplanet Watch (NASA citizen science): Slack and project contact via https://science.nasa.gov/citizen-science/exoplanet-watch/
2. AAVSO Exoplanet Section: https://www.aavso.org/exoplanet-section (also the amateur route into TFOP SG1)
3. TFOP: https://tess.mit.edu/followup/apply-join-tfop/ , or an introduction from an advising researcher
4. BAA/AAVSO EXPLORE: https://britastro.org/?p=613839
5. Unistellar UNITE: https://science.unistellar.com/exoplanets/unite/

Thanks to Biel Escolà-Rodrigo for the suggestions that shaped this.
