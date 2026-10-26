# Flowline — run-frequency review

A deterministic Python classifier and local Streamlit prototype for Infinite Lambda's Senior Technical Product Manager assignment. No runtime AI, external services, authentication or scheduler connection.

**Supplied data:** 1,152 runs / 40 workflows → **31 In scope, 3 Too frequent, 6 Unknown**. [All results and discrepancies](docs/results.md) · [JSON evidence](data/classification_results.json) · [CSV results](data/classification_results.csv). Totals are computed, not targets.

## Run locally

Use Python **3.12**, from the repository root. The locked dependencies are the versions used for validation. Linux was tested here; the candidate confirmed local Windows operation. PowerShell instructions use the virtual environment interpreter directly, so activation and execution-policy changes are unnecessary.

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --browser.gatherUsageStats false
```

**Linux / macOS**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m streamlit run app.py --server.headless true --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open the local address printed by Streamlit; stop with Ctrl+C. The supplied CSV loads by default; another CSV can be uploaded. Cloud onboarding does not provide a web preview. macOS commands follow the same environment layout as Linux; they were not separately executed here.

CLI / regenerate evidence (use `.\.venv\Scripts\python.exe` instead on Windows):

```bash
.venv/bin/python classifier.py data/run_history.csv --json
.venv/bin/python validate_dataset.py
```

**Validation:** 72 tests pass, no skips, including five Streamlit interaction tests. Engine and persistence need only the standard library; without Streamlit, the UI tests explicitly skip, which does not validate the interface. `requirements.txt` declares Streamlit; `requirements.lock.txt` pins its resolved dependencies.

## Review and correct

Select a workflow to inspect evidence, warnings, the run chart and original rows. Correct its frequency with a required reason and supporting source (scheduler reference, ticket, URL or free text), plus an optional reviewer. Sources are recorded without fetching/verifying them. **59.9 minutes stays Too frequent; 60 is In scope.** There is no scope toggle or sub-hourly exception.

Corrections persist in `.local/corrections.sqlite3`; back it up or download the JSON audit. Originals and every timestamped correction remain preserved; the latest correction is explicitly **reviewer-supplied**, not machine-verified. Exact CSV bytes, workflow and engine version identify a review. A changed export or engine starts a separate review; older corrections remain in SQLite and an upgrade warning explains they are not automatically applied. `FLOWLINE_DB` optionally selects another database. This local prototype is not an authenticated or tamper-proof audit service.

## Assumptions and limits

- Starts determine frequency; names, durations and execution health do not. Blank ends and failed/aborted/stopped starts are retained.
- The strict 60-minute policy distinguishes recurring drift from isolated jitter. Short conflicting sequences and questionable retry ancestry go to engineers.
- Weekdays mean Mon–Fri. Expected coverage uses the fitted calendar, with no invented holidays or timezone/DST policy. Offset timestamps, duplicate starts and invalid records cannot silently receive approval.
- Inactivity is an export-relative ≥21-day silence; supported calendars must also be overdue. It is not proof of retirement.
- Evidence thresholds and drift bands are heuristics, not calibrated confidence. Short histories can hide missing executions or another schedule; equivalent calendar fits cannot establish scheduler configuration.
- Generic intraday intervals outside the supported families, custom working weeks and holiday-dependent schedules remain Unknown. Migration readiness, retirement decisions, production deployment and large-export scaling are outside scope.

## Submission materials

[Final one-page spec and good/bad examples](SPEC.md) · [rationale / original-spec history](docs/spec-review.md) · [assignment](docs/assignment-body.txt) · [original feedback PDF](docs/feedback-original.pdf) / [extracted text](docs/feedback.txt) · [original CSV](data/run_history.csv) · [review fixes](docs/review-fixes.md) · [AI prompt record](docs/ai-assistance.md) · [development decisions and actual mistakes](docs/development-log.md).

The engine is `classifier.py`, audit storage `corrections.py`, interface `app.py`, and tests `tests/`. Raw test logs and local databases are excluded from Git; the classification reports are intentional submission evidence.

**TODO — candidate:** add your honest time spent (recorded duration or clearly labeled estimate) in `docs/ai-assistance.md`, including discovery, implementation/review and manual testing as appropriate. No timer or total human effort was supplied; test runtimes are not development time. Attach earlier discovery prompts if available, or explicitly mark them unavailable. Do not invent either.
