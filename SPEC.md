# Flowline — Run-Frequency Scope Gate (engine 1.1)

**Policy:** Reliably hourly or less often → **In scope**; proven recurring **<60 minutes → Too frequent**; uncertain → **Unknown**. Both latter outcomes require engineer review; health/readiness are separate.

**Input/output:** CSV `workflow_name,start_time,end_time,status`. Use starts, never names/durations; retain failed/aborted/stopped runs and blank ends. Show cadence, decision, counts, range, evidence, warnings and provenance. No scheduler/timezone/holiday metadata exists.

## Rules

1. **Validate:** Sort starts. Reject duplicate headers. Invalid starts or malformed row widths warn and block workflow approval; unattributable rows block approval across the file. Duplicate starts remain Unknown. Starts require ISO date/time without offsets.
2. **Evidence (heuristics):** Sub-55-minute bursts: ≥4 consecutive starts on each of 2 days, or ≥6 on 1 day. Near-hourly faster drift: ≥6/day on 2 days or ≥12 on 1 day. Daily/weekday and weekly/fortnightly: ≥3 dates, ≥80% expected occurrences. Twice monthly: ≥5 starts across 3 consecutive months; monthly: 3 consecutive months; quarterly: 3 consecutive quarters. Monthly/quarterly patterns need full expected coverage; calendar clock tolerance: ±10 minutes.
3. **Strict boundary:** Separate within-day fits from overnight gaps. Resolved near-hourly drift below 60 is faster, including 59.9; never round it up. Short resolved faster sequences (≥4 starts) block approval even below exclusion gates. Hourly requires ≥6 slots/day on 2 days or ≥12 on 1 day, combined fit 59.8–60.2, individual drift bands including 60, stable clock anchor ±10 minutes, ≥90% operating-window coverage, and no faster/conflicting starts. Consistently negative unresolved slopes or other ambiguity → Unknown. Tolerance never exempts sub-hourly schedules. Residual/three-standard-error diagnostics: [rationale](docs/spec-review.md).
4. **Calendars:** Daily, Mon–Fri, weekly, fortnightly; monthly fixed dates, month-end, ordinal/first/last business day, nth/last named weekday, weekend dates moved to previous weekday; twice-monthly date pairs; quarterly rules. Coverage uses appropriate calendars and nominal months/quarters before weekend shifts. No assumed holidays or “about monthly” matching.
5. **Retries / warnings:** Likely retries must follow failure/abort/stop, be off a supported schedule, within 24 hours and before the next expected start, with no separate recurrence. Preserve every run. Questionable retries needed for approval → Unknown. Inactivity means ≥21-day export-relative silence; supported calendars must also be overdue. It is not proof of retirement.

**Corrections:** Require frequency, reason/source; reviewer optional. Reapply policy: 59.9 stays Too frequent; 60 is In scope. Append timestamped reviewer assertions; preserve originals/history. CSV bytes, workflow and engine version scope reviews; prior-version corrections remain stored, not automatically applied.

## Done when / examples

All 40 workflows have evidence/warnings; blank ends work; corrections survive restart without overwriting originals; the complete deterministic test suite passes.

| Input | Good | Bad |
|---|---|---|
| Supported daily 03:00; failure, likely retry 03:49 | Daily/in scope + retry warning | 49-minute schedule |
| Regular 30-minute mornings | Too frequent | Daily/in scope |
| Supported hourly clock; isolated 52–67-minute gaps | Hourly/in scope | Decide from shortest gap |
| Clear recurring 59.9-minute starts | Too frequent | Round up to hourly |
| Jun 30, Jul 31, Aug 28 | Unknown | Invent month-end rule |
| Supported weekly; all runs failed | In scope + health warning | Unknown solely from failures |

**Limit:** History cannot prove configured cadence or retry ancestry. Unsupported or unclear cases go to engineers.
