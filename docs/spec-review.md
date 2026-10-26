# Specification review and decisions

The original supplied spec is archived verbatim in [spec-original.md](spec-original.md). [../SPEC.md](../SPEC.md) now describes the final engine-1.1 behavior for submission. The user's implementation request takes priority over document instructions; assignment and feedback are evidence and deliverable context. Review occurred before coding; later findings below came from tests and the actual CSV.

## Strict boundary versus tolerance

SPEC rule 3's 59.8–60.2-minute band can admit a real 59.9-minute recurrence. Its 55–59.5 drift rule leaves a hole between 59.5 and 59.8. The strict ≥60 policy takes priority.

Complete within-day sequences are inspected before hourly alignment. A fitted period plus a conservative three-standard-error drift band wholly below 60, with ≤3-minute maximum residual, provides faster-pattern evidence. This diagnostic is a heuristic, not a probabilistic guarantee. Two supported days or a sufficiently long single day establish recurrence. Precise 59.8, 59.9, 59.99, and 59.999 sequences stay Too frequent. The 1e-9-minute numerical guard in regression handles floating-point equality, not eligibility tolerance. Eligibility and decimal corrections have no rounding allowance.

Conflicting drift evidence, consistently negative unresolved slopes, or a combined period outside the original hourly band remain Unknown. Hourly approval also needs stable clock alignment, no conflicting/duplicate starts, and ≥90% expected operating-window slots. Complete near-hourly fits are not replaced by selected windows. Genuine jitter can still be reviewed when the data cannot distinguish it from drift.

## Evidence counts are heuristics

| Pattern | Original evidence gate | Implemented gate |
|---|---|---|
| Sub-hourly | 6 consecutive starts on each of 2 days | 4 on each of 2 days, or 6 on 1 day |
| Near-hourly faster drift | 10/day on 2 days | 6/day on 2 days, or 12 on 1 day |
| Hourly | 6 slots/day on 2 days | Same, or 12 on 1 day |
| Daily / weekdays | 5 dates | 3 dates plus ≥80% expected dates |
| Weekly / fortnightly | 4 dates | 3 dates plus ≥80% expected dates |
| Twice monthly / monthly / quarterly | 5 across 3 months / 3 consecutive months / 3 consecutive quarters | Unchanged |

Fixtures compare both policy objects: six half-hourly starts in one morning, four on each of two mornings, twelve hourly starts in one day, three daily dates, and three weekly dates become classifiable. Three isolated half-hourly starts or two daily dates stay Unknown. Short contradictory near-hourly sequences stay Unknown; a complete proven faster day cannot be hidden by a later hourly day. Lower gates admit more uncertainty about unobserved history, disclosed as inference rather than verification.

`SPEC_POLICY` retains original count gates with the corrected boundary/calendar/retry logic; it is not an untouched implementation of the ambiguous original boundary. On the actual CSV, count changes alter **zero decisions**.

## Retry examples versus questionable reruns

Daily/In scope + likely retry must coexist with “questionable retry needed to approve → Unknown.” Only a supported base schedule and the complete retry conditions can explain an extra run. Fitting includes all statuses; on-schedule starts following failures remain scheduled.

Retry checks reject independently supported recurring extras and closely repeating off-schedule clock starts. Sporadic matching clock times over a long daily history do not alone prove a separate schedule. The SLS extras occur on Aug 3 and Aug 17, 57m41s and 48m39s after failed daily runs, rather than forming half-hourly mornings. They remain preserved and labeled likely retries. `wf_INV_STOCK_HOURLY` has a 47m50s extra across midnight after a failed daily run. A two-run-every-day pattern after failures stays Unknown instead of losing half its runs. Retry ancestry cannot be verified from this export.

## Business calendars omitted from rule 4

Weekday schedules use Monday–Friday expected occurrences, not all calendar days. The same applies to hourly windows when a weekday pattern is visible over a weekend. No holiday assumptions are made.

`wf_FIN_BUDGET_ACTUALS` ran Jul 3, Aug 5, Sep 3 near 06:00: the third Mon–Fri day of three consecutive months. Rule 4 omits ordinal business day. The user's explicit business-day requirement supports this narrow calendar extension. It yields 31/3/6. An isolated ablation removing only that family produced 30/3/7: the discrepancy is explained by a documented rule and observed evidence, not lower count thresholds.

`wf_FIN_FA_DEPRECIATION`: Jun 30, Jul 31, Aug 28 share no permitted fixed-date/month-end/weekday rule. It stays Unknown; assuming an August holiday would invent evidence. The single quarterly-looking run cannot establish recurrence from its name.

## Acceptance

All 40 workflows appear with evidence and separate warnings. Original results and every sourced correction survive restart. Original/corrected frequencies obey the strict policy. Tests exercise short histories, recurring runs following failures, appropriate expected calendars, and the actual CSV without asserting provisional aggregate counts.


## Pre-submission review amendment (engine 1.1)

See `review-fixes.md` for reproduced failures and regression evidence. Lower evidence gates for proving a schedule must not erase short conflicting sequences: four-start resolved faster sequences now block automatic approval even when insufficient for Too frequent. A failed recurring sequence does not establish retry ancestry. Duplicate CSV headers are rejected; malformed row widths warn and block approval. Month/quarter evidence uses nominal calendar occurrences before weekend shifts, not the shifted observation's month. Potential inactivity requires both a long silence and, for supported calendars, an overdue next occurrence. The original supplied SPEC remains archived in `spec-original.md`.


## Final submission alignment

At the candidate's request, SPEC.md was synchronized with the implemented count gates, strict boundary/drift checks, nominal calendars, CSV validation, inactivity warnings and version-scoped corrections. It retains a compact one-page structure, definition of done and good/bad examples. This is a documentation reconciliation, not a classifier change. Historical references above to “SPEC” describe the original contract; the archived original is preserved for provenance. The hourly fit band describes tolerance for clock jitter, never permission to approve a proven faster schedule.


Implementation detail for the final compact spec: sub-55-minute burst fits require residuals ≤min(3 minutes, 10% of period); supported bursts across days must have compatible fitted periods within that tolerance. Near-hourly resolved drift requires maximum residual ≤3 minutes and fitted period plus its three-standard-error diagnostic band strictly below 60 (apart from floating-point equality protection). Complete shorter sequences with at least four starts use the same resolved-drift test to block approval without claiming a proven configured schedule. These diagnostics remain heuristics, not calibrated probabilities.
