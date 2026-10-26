# Flowline — Run-Frequency Scope Gate (v1)

**Goal:** Decide ETL migration frequency eligibility from incomplete run history. **Policy:** reliably **≥60 min = In scope**; **<60 min or uncertain = Engineer review**. Frequency eligibility is separate from operational health and migration readiness.

**Input:** CSV with `workflow_name`, `start_time`, `end_time`, `status`. Classify using start times only. Accept blank end times, keep failed/aborted/stopped records, and ignore names as schedule evidence. No scheduler, timezone, or holiday calendar is available.

**Output:** For each workflow, show inferred cadence, decision (`In scope`, `Too frequent`, `Unknown`), run count, date range, pattern evidence, and separate warnings (retries, failures, gaps, potential inactivity).

## Rules

1. **Prepare:** Validate/sort starts per workflow; warn about bad rows. If excluded rows could change eligibility, classify `Unknown`. Evaluate within-day patterns separately so overnight gaps do not hide 15/30-minute schedules.
2. **Evidence:** Sub-hourly: ≥6 consecutive starts on **each of 2 days** with one fitted period (±3 min). Near-hourly (55–60 min): ≥10 starts per day on 2 days, then use rule 3. Hourly: ≥12 starts across 2 days, including ≥6 consecutive hourly slots per day. Daily/weekday: ≥5 dates; weekly/fortnightly: ≥4 dates; twice monthly: ≥5 occurrences across 3 months; monthly: 3 consecutive months; quarterly: 3 consecutive quarters. For daily/weekly patterns require ≥80% of expected dates between first and last observed scheduled start; for hourly require ≥90% expected slots inside a repeated daily operating window (e.g., 07:00–18:00). Clock alignment tolerance: ±10 min.
3. **Boundary:** Two day sequences fitted at **55–59.5 min**, with deviations ≤3 min → `Too frequent`. Combined period **59.8–60.2 min**, stable hourly clock anchor (±10 min), no independent faster pattern → `Hourly`. Otherwise near the boundary → `Unknown`. A sustained 59-minute drift differs from isolated 52–67-minute gaps around an hourly clock.
4. **Calendar:** Accept matching fixed dates, month-end, first/last weekday, nth weekday, or a fixed date moved to the previous weekday for weekends. Require same approximate time (±10 min). No loose “about monthly” rule or assumed holidays.
5. **Retries:** Label a run a *likely retry* only when it follows a failed/aborted/stopped run, is off a well-supported schedule, occurs before the next expected scheduled start and within 24 hours, and fits no separate recurring pattern. Preserve it. **If treating a questionable run as a retry is necessary to approve a workflow, classify `Unknown`.** Never automatically remove a real scheduled run following failure.
6. **Decide:** Proven repeated cadence <60 min → engineer (`Too frequent`). Supported ≥60 min without unexplained conflicting starts → `In scope`. Otherwise engineer (`Unknown`). Failures and long inactivity are separate warnings, not frequency failures.

**Manual corrections:** Reviewer enters corrected frequency, required reason and supporting source (free text: scheduler reference, ticket, URL). Reapply the same 60-minute rule. Keep original system result and append all corrections with timestamp, source, and reviewer if supplied. Mark results *reviewer-supplied*, not machine-verified. Sub-hourly exceptions never silently become standard in-scope.

## Done when

All 40 CSV workflows appear; blank end times work; every result includes evidence and warnings; corrections survive restart without overwriting originals; deterministic tests pass:

| Input | Good | Bad |
|---|---|---|
| Daily 03:00; failure, then likely retry 03:49 | Daily/in scope + retry warning | 49-minute schedule |
| Regular 30-minute mornings | Too frequent | Daily/in scope |
| Hourly clock; individual 52–67-minute gaps | Hourly/in scope | Too frequent from shortest gap |
| Jun 30, Jul 31, Aug 28 | Unknown | Invent month-end rule |
| Weekly; all runs failed | Weekly/in scope + health warning | Unknown due only to failures |

**Limit:** History cannot prove the configured schedule or retry ancestry. Unclear cases go to engineers.
