# The Hollow Hunt — revision plan

Status: **awaiting author sign-off on the decision points below.**
Working brief: `verdict-2026-07-04.md`. Baseline numbers: `metrics-v1.md`.
Source of truth for text: `../chapters/` (v1 split, one file per chapter).

## Ground rules

- v1 is frozen in `../source/`. All revision happens in `../chapters/`,
  committed per pass, so every draft stage is a dated, recoverable version.
- No pass touches sentences until the structure pass is agreed.
- Targets: **95–105k words**, key reveal by **30%**, active opposition by
  **45%**, convening arc ≥ **10%** of the book, scene breaks ≤ **75**.
- Tic budget (enforced by `lint-prose.py`): "specific" ≤ 60, "quality" ≤ 60,
  "register" ≤ 25, "the way" ≤ 90, "he looked at me" ≤ 30,
  "for a long moment" ≤ 6, "something" ≤ 250.

## Phases

### Phase 0 — Decisions (author)
See decision points at the bottom. Nothing else is blocked on them except
where noted, but Pass 1 is materially shaped by D1–D4.

### Phase 1 — Beat sheet + outline diff (Claude drafts, author approves)
- Reverse-outline v1: every scene, its load-bearing event (if any), word cost.
- Draft the new 5-act beat sheet per the brief, including: placement of the
  Claim reveal, Kira's public failure (D2), Aleksei's inexcusable choice (D3),
  the consent confrontation (D4), the convening reversal (D5).
- Output: `beat-sheet-v2.md` + a per-chapter cut/merge/move map.

### Phase 2 — Structural edit (per-chapter, committed chapter by chapter)
- Execute the cut map: Ch2 −50%, merge early Hall chapters, compress
  mark-acquisition loops, cut vote arithmetic, halve scene breaks.
- Write new/expanded scenes required by Phase 1 (failure beat, betrayal beat,
  consent beat, climax reversal) as drafts flagged `[NEW — author review]`.

### Phase 3 — Voice pass
- Kira chapters: concrete/tactical/economic diction, shorter deductions,
  street comparisons, appetite and irritation, Vreshka past as active force.
- Aleksei chapters: older time-scale, stranger sensory priorities, no
  management vocabulary, occasional mortal-assumption blindness.
- Tic deletion to budget, by strength not by synonym.

### Phase 4 — Continuity + copyedit
- Build `canon-bible.md` while line-editing (eye colors, timeline day-count,
  term capitalization, travel times, who-knows-what-when).
- Fix the six confirmed errors in `metrics-v1.md` plus whatever the pass finds.
- Rename Cael or Kael (D6).

### Phase 5 — Human loop + production (author-driven, Claude supports)
- Beta round (8–12 genre-native readers) → revise → professional or
  equivalently rigorous copyedit → title/brand lock (D1) → cover brief →
  separate print/ebook builds → proof → copyright registration → launch only
  with a stable Book Two draft.

## Decision points (author)

- **D1 — Title/series brand.** Keep *The Hollow Hunt* despite the Selena
  Winters collision, or rebrand (candidates: *Nochval*, *The Old Claim*,
  *The Veil Nights*)? Affects nothing until Phase 5, but decide before covers.
- **D2 — Kira's failure beat.** Preferred option (misreads an ally / early
  mark activation / damages the membrane proving control / treats a person as
  a problem and someone gets hurt)?
- **D3 — Aleksei's inexcusable choice.** How hard to push (withholds something
  that costs a third party / acts on the binding without consent / a
  protective act that removes her agency publicly)?
- **D4 — Consent reconciliation.** Which mechanism (genuine open door she
  returns through / symmetrical duty in the binding / she rewrites the law at
  the convening — this one doubles as climax material)?
- **D5 — Climax cost.** Defection, conditional recognition, or "win unleashes
  the sealed wing early"?
- **D6 — Cael vs. Kael.** Which one renames, and to what?
