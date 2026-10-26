# Flowline — run-frequency review

A deterministic Python classifier and local Streamlit prototype for Infinite Lambda's Senior Technical Product Manager assignment. No runtime AI, external services, authentication, or scheduler connection.

**The supplied 1,152-run, 40-workflow export produces 31 in scope, 3 too frequent, and 6 unknown.** See [all 40 results](docs/results.md), [JSON evidence](data/classification_results.json), or [CSV results](data/classification_results.csv). Totals are computed, never targets.

## Run

Python 3.12 was tested. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open the local address printed by Streamlit on a machine with browser access. Cloud onboarding does not provide a web preview. The default dataset is bundled; upload another CSV to review it. The application shows effective decisions, original results, evidence, warnings, run charts, raw rows, and the engineer queue.

The classifier and persistence tests use only the Python standard library:

```bash
python3 classifier.py data/run_history.csv
python3 classifier.py data/run_history.csv --json
python3 -m unittest discover -s tests -p test_classifier.py -v
python3 -m unittest discover -s tests -p test_corrections.py -v
python3 validate_dataset.py  # regenerate the checked-in full-data reports
```

Without Streamlit, discovery explicitly skips the five UI tests; it does not establish UI readiness. The complete suite with dependencies installed has **72 passing tests, no skips**. Streamlit's health and root HTTP endpoints also returned 200; AppTest exercises actual review interactions rather than treating HTTP health as application validation.

## Review and correct

Select a workflow, inspect its evidence and chart, then enter a corrected frequency, reason, supporting source, and optional reviewer. A source can be a scheduler reference, ticket, or URL; it is recorded without fetching or verifying it. Fixed intervals accept decimals: **59.9 remains Too frequent; 60 becomes In scope**. Unknown remains engineer review. There is no separate scope toggle or sub-hourly exception.

Corrections append to `.local/corrections.sqlite3`, survive restarts, and preserve the original system result. The latest correction controls the effective result and is explicitly **reviewer-supplied**, not machine-verified. All corrections retain timestamps (UTC), sources, reasons, and optional reviewers. Original health/history warnings remain visible. Engine 1.1 creates a new version-scoped review: earlier originals and corrections remain stored, but are not automatically applied to the updated inference. The UI warns when earlier reviews exist. Keep the SQLite backup; do not delete it during an upgrade.

Review identity is SHA-256 of the exact CSV bytes plus workflow and engine version. A different export starts a new review; corrections are not transferred by workflow name. Back up the database or download the JSON audit history. `FLOWLINE_DB=/path/to/review.sqlite3` selects another local database. This is a local prototype; SQLite is not a tamper-proof audit service. Source/reviewer text is stored locally without authentication.

## Assumptions and limits

[SPEC.md](SPEC.md) is the supplied contract, kept intact. [Specification review](docs/spec-review.md) records the narrow amendments required by the user's implementation request, including threshold sensitivity and business calendars.

- Frequency uses **start times**, including failed/aborted/stopped runs. End times may be blank and never determine cadence. Names are labels, not schedule evidence.
- Complete within-day near-hourly sequences are fitted for period and drift. Clear recurring periods below 60, including 59.99, stay out of scope even inside the original tolerance band. Unresolved/contradictory drift goes to review. Isolated short gaps do not establish fast recurrence. Short regular faster sequences that do not meet the automatic exclusion gate still block approval and go to review; they are not automatically treated as jitter or retries.
- Coverage uses the fitted calendar's expected occurrences. Weekdays mean Monday–Friday, including ordinal business days of a month; holidays are not invented. Monthly patterns must fit explicit rules across consecutive months.
- Likely retries require off-schedule timing, a preceding failure/abort/stop, ≤24 hours, time before the next expected occurrence, and no supported separate recurrence. All runs remain preserved. Unexplained/repeating extras block approval.
- Invalid starts block approval of their workflow; missing workflow names conservatively block approval across the file. Duplicate CSV headers are rejected; rows with missing/extra fields are retained in counts, warned about, and block workflow approval. Duplicate timestamps remain unresolved. ISO timestamps require a time of day and no UTC offset; timezone-aware exports require an explicit calendar policy and go to review here.
- Potential inactivity means ≥21 days before the **latest start in the same export**, not today's date. For a supported calendar, a warning also requires the next inferred occurrence to be overdue; monthly jobs that are not yet due are not flagged. It is not proof of retirement. Missing expected occurrences and execution health remain separate from frequency eligibility.

The weakest inference is a short regular history that could hide another schedule, missing periods, or manual reruns. Evidence gates and drift bands are heuristics, not calibrated confidence. History alone cannot establish configured cadence or retry ancestry. Supply stronger scheduler evidence as a correction when available. Equivalent calendar fits are disclosed rather than claiming one configured rule is proven.

Unsupported/ambiguous patterns go to engineers: a single quarterly occurrence, irregular schedules, holiday-dependent calendars, unresolved schedule changes, or generic intraday intervals outside the supported near-hourly/sub-hourly families. Migration readiness, retirement decisions, DST, custom working weeks, large-export performance, and production deployment are outside scope.

## Development evidence

- [Results and discrepancies](docs/results.md): all workflows, unknowns, health/inactivity, original-versus-revised evidence counts.
- [Specification review](docs/spec-review.md): contradictions, resolutions, and short-history comparisons.
- [Review fixes and regression evidence](docs/review-fixes.md): pre-submission defects and their resolutions.
- [Development log](docs/development-log.md): actual decisions, mistakes, corrections, and validation.
- [AI assistance and supplied prompt](docs/ai-assistance.md): AI involvement and honest time-reporting limits.
- Original [assignment](docs/assignment-body.txt) and [feedback PDF](docs/feedback-original.pdf), with [extracted feedback](docs/feedback.txt). The uploaded `feedback.md` contained PDF bytes; it is retained with its actual format.

The engine is `classifier.py`, audit persistence is `corrections.py`, and the interface is `app.py`. `requirements.txt` names the single direct UI dependency; `requirements.lock.txt` pins the resolved versions used for validation. Tests cover strict boundaries, jitter, evidence sensitivity, retries, calendars, CSV quality, all source workflows, restart persistence, and UI corrections.

Time-spent submission requirement: no implementation timer was started, and human discovery/manual-testing effort is unknown. The candidate must supply an honest recorded duration or clearly labeled estimate; test execution time is not a substitute.
