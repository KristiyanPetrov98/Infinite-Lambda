# Pre-submission review fixes — engine 1.1

The critical review found real gaps despite all 59 original tests passing. These fixes implement the user's agreement with the findings; they do not add a new classification feature or change the strict eligibility boundary.

| Finding / reproduction | Previous behavior | Current behavior |
|---|---|---|
| Six hourly starts on each of two days, then five exact 59-minute starts | Hourly / In scope | Unknown; shorter conflicting sequence disclosed |
| Ten daily starts with a failed run followed by six exact 59-minute extras | Daily / In scope, all extras likely retries | Unknown; possible faster recurrence remains unresolved |
| Short failed recurring bursts at 30, 59, or 59.9 minutes | Could be explained away as retries | Unknown when below automatic exclusion gates; all starts preserved |
| Duplicate CSV headers | Last same-named column silently won | CSV rejected with an explicit error |
| Named row with missing or extra fields | Could be silently accepted | Row counted, excluded with a warning, workflow Unknown |
| July 31 / September 1 / October 1: nominal August–October day 1 moved to previous weekday | Unknown because observed months were not consecutive | Monthly / In scope based on consecutive nominal months |
| Quarterly weekend shifts into preceding months | Nominal quarter phase could be lost | Uses the nominal month/quarter, with missing occurrences still rejected |
| Month-end last observed August 31, export ends September 26 | Potential inactivity warning although September occurrence is not due | No inactivity warning until the inferred next occurrence is overdue |

Four-start complete intraday sequences are examined for resolved faster drift even if they fall below automatic Too frequent thresholds. Such a sequence can block approval without proving a configured schedule. Proven fast patterns retain precedence. Retry checks also examine the extras' intraday pattern, including their failed statuses, rather than only calendar recurrence.

The supplied CSV still has 31 In scope / 3 Too frequent / 6 Unknown across all 40 workflows and 1,152 runs. The changed results are warnings and engine provenance, not workflow decisions. Expected monthly jobs no longer appear potentially inactive just because 21 days have passed; unresolved histories still receive a qualified long-silence warning.

Engine version 1.1 preserves all engine-1.0 original records and corrections in the same SQLite database. They are separate reviews, not overwritten results or silently migrated reviewer assertions. The app warns when earlier-version records exist. Streamlit's analysis cache now includes the engine version, so cached version-1.0 inference cannot silently survive the upgrade.

Validation: all 59 existing tests plus 12 review-regression tests and one UI upgrade/preservation test pass: **72 tests, no failures or skips**. Cases include rejecting ambiguous inputs, preserving run counts, accepting valid blank end times, rejecting missing nominal months, retaining the strict decimal boundary, and retaining earlier correction history. The current complete runner output is in `docs/test-results.txt`.

Time-spent documentation remains deliberately honest: total human effort was not provided or measured. The candidate should supply their recorded duration or a clearly identified estimate before submission. No fabricated duration or new AI error story was added.
