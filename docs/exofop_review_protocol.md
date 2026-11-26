# ExoFOP review protocol (manual first, not yet run)

**Question.** When EEFN's rule-based flags fire on a TOI, was that issue already known to the community at
the time (visible in the public ExoFOP-TESS notes), and did the later disposition have independent
observational support? This separates "EEFN found something overlooked" from "EEFN automated something
people already knew". A reviewer advised doing this by hand on a small, representative sample before
attempting any automation, and warned that **no public note is not evidence that an issue was overlooked.**

## Rules that apply

- Public pages only. Do not use proprietary TFOP data.
- Read; do not copy. Record categories and counts, not the text of notes. Link, do not mirror.
- Follow the ExoFOP conduct policy: uploaded data belongs to the uploader; cite unpublished data by
  contributor and URL; use the standard ExoFOP acknowledgement in anything published; contact the uploader
  before relying on their data in an analysis. Counting how many TOIs have a note of a given kind is
  different from using the note, but check with ExoFOP (NExScI) before publishing anything built on it.
- Do not scrape. Reading 30-50 pages by hand is the intended scale.

## Sample

30-50 TOIs, chosen at random with a recorded seed, stratified so the sample is representative rather than
the most interesting cases:

- about 40% with at least one core flag that has since been resolved to FP, FA or CP/KP;
- about 30% with a core flag and still unresolved (PC or APC);
- about 30% with no core flag, as a control (the same review, so we can see how often unflagged TOIs also
  have notes about the same issues).

Record which flag(s) fired, with the value, and the date EEFN first computed the flag. For the 108
unresolved TOIs in the frozen snapshot, use the snapshot date (2026-10-13) as the reference time.

## Per-TOI record

| Field | Notes |
|---|---|
| TOI, TIC | |
| Flag(s) fired and values | from the EEFN candidate page |
| Public notes present? | yes / no (do not record content) |
| Does any note concern the same issue as the flag? | e.g. a companion, a blend, a stellar-parameter problem |
| Date of that note vs the flag date | before / after / undated |
| Current disposition and when it changed | from ExoFOP or the NASA Exoplanet Archive |
| Independent observation behind the disposition? | RV, high-resolution imaging, spectroscopy, ground photometry, none visible |

## Categories (set on the first 10 TOIs, then fixed)

The first 10 are reviewed together to settle the categories below, then frozen. Revisions are recorded.
Starting set:

1. **Known before** - a public note on the same issue predates the flag.
2. **Noted after** - a note on the same issue appears after the flag.
3. **Not visible** - no public note on this issue. This does **not** mean overlooked; many groups do not
   post notes, and some work is not public.
4. **Different issue** - notes exist but about something else.
5. **Unclear** - the notes cannot be read against the flag.

## Report

Counts per category, split by flag type and by flagged vs control. State the limits: public notes are an
incomplete record of what the community knew; the sample is small; categories are one reader's judgement
(a second reader on 10 TOIs, with agreement reported, is the minimum check). Only after this decide whether
any automation is justified.
