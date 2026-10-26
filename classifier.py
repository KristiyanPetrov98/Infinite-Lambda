"""Deterministic start-time frequency inference. No UI or third-party dependencies."""
from __future__ import annotations

import argparse
import calendar
import csv
import io
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from itertools import combinations
from statistics import mean, median

ENGINE_VERSION = "1.1"
BAD_STATUSES = {"failed", "aborted", "stopped"}
KNOWN_STATUSES = BAD_STATUSES | {"succeeded"}


@dataclass(frozen=True)
class EvidencePolicy:
    """Evidence gates are tunable heuristics, never the eligibility boundary."""
    fast_per_day: int = 4
    fast_single_day: int = 6
    hourly_per_day: int = 6
    hourly_single_day: int = 12
    daily_dates: int = 3
    weekly_dates: int = 3
    near_hourly_per_day: int = 6


DEFAULT_POLICY = EvidencePolicy()
SPEC_POLICY = EvidencePolicy(fast_per_day=6, fast_single_day=10**9,
                             hourly_single_day=10**9, daily_dates=5, weekly_dates=4,
                             near_hourly_per_day=10)


@dataclass(frozen=True)
class Run:
    start: datetime
    status: str
    row: int


@dataclass
class History:
    workflows: dict[str, list[Run]]
    row_counts: dict[str, int]
    issues: dict[str, list[str]]
    global_issues: list[str]


@dataclass
class Result:
    workflow: str
    cadence: str
    decision: str
    run_count: int
    valid_start_count: int
    first_start: str | None
    last_start: str | None
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    likely_retry_rows: list[int] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION

    @property
    def routing(self) -> str:
        return "Standard migration" if self.decision == "In scope" else "Engineer review"

    def to_dict(self) -> dict:
        return {**asdict(self), "routing": self.routing}


def eligibility(minutes: float | Decimal | None, supported: bool = True) -> str:
    """Shared policy: no rounding, epsilon, or sub-hourly exceptions."""
    if not supported or minutes is None:
        return "Unknown"
    try:
        value = Decimal(str(minutes))
    except InvalidOperation:
        return "Unknown"
    if not value.is_finite() or value <= 0:
        return "Unknown"
    return "In scope" if value >= Decimal(60) else "Too frequent"


def read_history(text: str) -> History:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    required = {"workflow_name", "start_time", "end_time", "status"}
    if len(reader.fieldnames or []) != len(set(reader.fieldnames or [])):
        raise ValueError("CSV headers must be unique; duplicate columns are ambiguous.")
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("CSV must include workflow_name, start_time, end_time, status.")
    workflows, counts, issues = defaultdict(list), Counter(), defaultdict(list)
    global_issues = []
    for row_number, row in enumerate(reader, 2):
        name = (row.get("workflow_name") or "").strip()
        if not name:
            global_issues.append(f"Row {row_number}: missing workflow name; cannot attribute this run.")
            continue
        counts[name] += 1
        workflows[name]  # Retain workflows whose every start is invalid.
        if None in row or any(value is None for value in row.values()):
            issues[name].append(f"Row {row_number}: wrong number of CSV fields; eligibility may be affected.")
            continue
        try:
            start = datetime.fromisoformat((row.get("start_time") or "").strip())
            if start.tzinfo is not None:
                raise ValueError("offset timestamps require an explicit calendar/timezone policy")
            if len((row.get("start_time") or "").strip()) < 16:
                raise ValueError("time of day is required")
        except ValueError as exc:
            issues[name].append(f"Row {row_number}: invalid start ({exc}); eligibility may be affected.")
            continue
        workflows[name].append(Run(start, (row.get("status") or "").strip().lower(), row_number))
    if not counts:
        raise ValueError("CSV contains no named workflows.")
    return History(dict(workflows), dict(counts), dict(issues), global_issues)


def minute(t: datetime) -> float:
    return t.hour * 60 + t.minute + t.second / 60 + t.microsecond / 60_000_000


def clock_distance(a: float, b: float, period: float = 1440) -> float:
    return abs((a - b + period / 2) % period - period / 2)


def fit(values: list[float]) -> tuple[float, float, float]:
    """OLS period, max residual, conservative 3-SE uncertainty band.

    This is a drift diagnostic, not a calibrated probability of a schedule.
    """
    n = len(values)
    xbar, ybar = (n - 1) / 2, mean(values)
    ssx = sum((i - xbar) ** 2 for i in range(n))
    slope = sum((i - xbar) * (y - ybar) for i, y in enumerate(values)) / ssx
    residuals = [y - (ybar + slope * (i - xbar)) for i, y in enumerate(values)]
    band = 3 * math.sqrt(sum(r * r for r in residuals) / max(1, n - 2) / ssx)
    return slope, max(map(abs, residuals)), band


def intraday(runs: list[Run], policy: EvidencePolicy) -> tuple[str, str, list[str]] | None:
    days = defaultdict(list)
    for r in runs:
        days[r.start.date()].append(minute(r.start))
    # Scan short windows too: a burst cannot be hidden by overnight or long gaps.
    bursts = []
    n = policy.fast_per_day
    for d, values in days.items():
        for size in {n, policy.fast_single_day}:
            if size > len(values):
                continue
            for i in range(len(values) - size + 1):
                period, residual, band = fit(values[i:i + size])
                if 0 < period < 55 and residual <= min(3, period * .1):
                    bursts.append((d, period, size))
    for d, period, size in bursts:
        support = {day for day, p, _ in bursts if abs(p - period) <= min(3, period * .1)}
        if len(support) >= 2 or size >= policy.fast_single_day:
            estimate = median(p for _, p, _ in bursts if abs(p - period) <= min(3, period * .1))
            return (f"Every {estimate:.2f} minutes", "Too frequent", [
                f"Recurring sub-hourly sequences on {len(support)} day(s); "
                f"at least {size} consecutive starts; median fitted period {estimate:.4f} min.",
                "Supporting dates: " + ", ".join(map(str, sorted(support))),
                "All execution statuses included; overnight gaps excluded from period fitting."])

    sequences = []
    suspicious = []
    for d, values in days.items():
        # Near-hourly analysis uses complete contiguous sequences, never cherry-picked windows.
        groups = [[]]
        for v in values:
            if groups[-1] and v - groups[-1][-1] > 90:
                groups.append([])
            groups[-1].append(v)
        for g in groups:
            if len(g) >= 4:
                p, residual, band = fit(g)
                if 0 < p and p + band < 60 - 1e-9 and residual <= min(3, p * .1):
                    suspicious.append((d, g, p, residual, band))
                if len(g) >= policy.hourly_per_day and 54 <= p <= 66:
                    sequences.append((d, g, p, residual, band))
    sufficient = len({s[0] for s in sequences}) >= 2 or any(
        len(s[1]) >= policy.hourly_single_day for s in sequences)
    evidence = [f"{d}: {len(g)} starts, fitted period {p:.4f} min, max residual "
                f"{res:.2f} min, drift band ±{band:.4f} min."
                for d, g, p, res, band in sequences]
    # Even 59.99 is faster when its drift is resolved. Never round it up to hourly.
    faster = [s for s in sequences if s[2] + s[4] < 60 - 1e-9 and s[3] <= 3
              and len(s[1]) >= policy.near_hourly_per_day]
    if len({s[0] for s in faster}) >= 2 or any(
        len(s[1]) >= policy.hourly_single_day for s in faster):
        p = median(s[2] for s in faster)
        return f"Every {p:.4f} minutes (sustained drift)", "Too frequent", evidence
    if suspicious:
        evidence += [f"{d}: shorter/conflicting sequence of {len(g)} starts fitted at {p:.4f} min; "
                     "insufficient evidence for automatic faster classification does not establish retries or hourly jitter."
                     for d, g, p, _, _ in suspicious]
        return "Possible faster recurrence; unresolved", "Unknown", evidence
    if not sufficient:
        return None
    if all(s[2] < 60 - 1e-9 for s in sequences):
        return "Near hourly; consistently negative but unresolved drift", "Unknown", evidence
    period = mean(s[2] for s in sequences)
    phases = [v % 60 for s in sequences for v in s[1]]
    anchor = min(phases, key=lambda a: max(clock_distance(a, v, 60) for v in phases))
    stable = max(clock_distance(anchor, v, 60) for v in phases) <= 10
    if not (59.8 <= period <= 60.2 and stable and
            all(abs(s[2] - 60) <= s[4] + 1e-9 for s in sequences)):
        return "Near hourly; unresolved period", "Unknown", evidence
    # Map every run to a clock slot, keeping duplicate/conflicting starts visible.
    assigned = []
    for r in runs:
        v = minute(r.start)
        slot = round((v - anchor) / 60)
        target = datetime.combine(r.start.date(), time()) + timedelta(minutes=anchor + slot * 60)
        if abs((r.start - target).total_seconds()) > 600:
            return "Hourly candidate with conflicting starts", "Unknown", evidence
        assigned.append(target)
    if len(set(assigned)) != len(assigned):
        return "Hourly candidate with multiple starts in a slot", "Unknown", evidence
    by_date = defaultdict(list)
    for t in assigned:
        by_date[t.date()].append(t.hour)
    lo = min(t.hour for t in assigned)
    hi = max(t.hour for t in assigned)
    first, last = min(by_date), max(by_date)
    dates = list(date_range(first, last))
    # An observed Mon–Fri pattern uses weekdays; no holiday assumptions.
    if (last - first).days >= 6 and all(d.weekday() < 5 for d in by_date):
        dates = [d for d in dates if d.weekday() < 5]
        calendar_label = "Mon–Fri"
    else:
        calendar_label = "calendar days"
    expected = len(dates) * (hi - lo + 1)
    coverage = len(assigned) / expected
    evidence.append(f"Hourly clock anchor :{anchor:.2f}; window {lo:02d}:00–{hi:02d}:00; "
                    f"{len(assigned)}/{expected} expected slots ({coverage:.1%}), {calendar_label}.")
    if coverage < .9:
        return "Hourly candidate; insufficient expected-slot coverage", "Unknown", evidence
    return "Hourly", "In scope", evidence


def date_range(first: date, last: date):
    for i in range((last - first).days + 1):
        yield first + timedelta(days=i)


def month_index(d: date) -> int:
    return d.year * 12 + d.month - 1


def month_date(index: int, day: int) -> date | None:
    year, m = divmod(index, 12)
    if day <= calendar.monthrange(year, m + 1)[1]:
        return date(year, m + 1, day)
    return None


def monthly_rules(index: int) -> dict[str, date]:
    year, m = divmod(index, 12)
    days = list(date_range(date(year, m + 1, 1), date(year, m + 1, calendar.monthrange(year, m + 1)[1])))
    weekdays = [d for d in days if d.weekday() < 5]
    rules = {f"day {d.day}": d for d in days}
    rules.update({"month-end": days[-1], "first weekday": weekdays[0], "last weekday": weekdays[-1]})
    for n, d in enumerate(weekdays, 1):
        rules[f"business day {n} (Mon–Fri)"] = d
    for d in days:
        adjusted = d - timedelta(days=max(0, d.weekday() - 4))
        rules[f"day {d.day}, previous weekday on weekends"] = adjusted
    for weekday in range(7):
        matching = [d for d in days if d.weekday() == weekday]
        name = calendar.day_name[weekday]
        for n, d in enumerate(matching, 1):
            rules[f"{n} {name}"] = d
        rules[f"last {name}"] = matching[-1]
    return rules


@dataclass
class Candidate:
    label: str
    expected: list[datetime]
    matched: set[int]
    coverage: float


def calendar_candidates(runs: list[Run], policy: EvidencePolicy) -> list[Candidate]:
    first, last = runs[0].start.date(), runs[-1].start.date()
    # Include future occurrences for retry checks after the last scheduled run.
    # Coverage remains bounded by the first/last actual matching starts below.
    horizon = last + timedelta(days=100)
    days = list(date_range(first, horizon))
    observed_dates = {r.start.date() for r in runs}
    nominal_months = {}
    patterns = [("Daily", days, policy.daily_dates),
                ("Weekdays (Mon–Fri)", [d for d in days if d.weekday() < 5], policy.daily_dates)]
    for w in sorted({d.weekday() for d in observed_dates}):
        patterns.append((f"Weekly ({calendar.day_name[w]})", [d for d in days if d.weekday() == w], policy.weekly_dates))
    for phase in sorted({d.toordinal() % 14 for d in observed_dates}):
        patterns.append(("Fortnightly", [d for d in days if d.toordinal() % 14 == phase], policy.weekly_dates))
    months = list(range(month_index(first), month_index(horizon) + 1))
    rules = {m: monthly_rules(m) for m in months}
    for rule in dict.fromkeys(rule for m in months for rule in rules[m]):
        nominal = {rules[m][rule]: m for m in months if rule in rules[m]}
        dates = list(nominal)
        if len(months) >= 3:
            label = f"Monthly ({rule})"
            patterns.append((label, dates, 3))
            nominal_months[label] = nominal
        for phase in range(3):
            qdates = [d for d in dates if nominal[d] % 3 == phase]
            if len(qdates) >= 3:
                label = f"Quarterly ({rule})"
                patterns.append((label, qdates, 3))
                nominal_months[label] = nominal
    doms = sorted({d.day for d in observed_dates})
    if len(months) >= 3:
        for a, b in combinations(doms, 2):
            dates = [d for m in months for n in (a, b) if (d := month_date(m, n))]
            patterns.append((f"Twice monthly (days {a}, {b})", dates, 5))
    # Cluster clock anchors before evaluating date patterns (midnight-safe).
    anchors = []
    for r in runs:
        v = minute(r.start)
        if not any(clock_distance(v, a) <= 10 for a in anchors):
            anchors.append(v)
    candidates = []
    for label, expected_dates, minimum in patterns:
        for anchor in anchors:
            expected = [datetime.combine(d, time()) + timedelta(minutes=anchor) for d in expected_dates]
            matched = set()
            used = set()
            for i, r in enumerate(runs):
                options = [(abs((r.start - t).total_seconds()), j) for j, t in enumerate(expected)
                           if j not in used and abs((r.start - t).total_seconds()) <= 600]
                if options:
                    _, j = min(options)
                    used.add(j)
                    matched.add(i)
            if len(matched) < minimum:
                continue
            matched_months = {nominal_months.get(label, {}).get(expected[j].date(),
                              month_index(expected[j].date())) for j in used}
            if label.startswith(("Monthly", "Twice monthly")) and (len(matched_months) < 3 or
                    max(matched_months) - min(matched_months) + 1 != len(matched_months)):
                continue
            if label.startswith("Quarterly"):
                qm = sorted(matched_months)
                if len(qm) < 3 or any(b - a != 3 for a, b in zip(qm, qm[1:])):
                    continue
            lower = min(runs[i].start for i in matched) - timedelta(minutes=10)
            upper = max(runs[i].start for i in matched) + timedelta(minutes=10)
            bounded = [t for t in expected if lower <= t <= upper]
            coverage = len(matched) / len(bounded)
            calendar_pattern = label.startswith(("Monthly", "Quarterly", "Twice monthly"))
            if coverage >= (1 if calendar_pattern else .8):
                candidates.append(Candidate(label, expected, matched, coverage))
    return sorted(candidates, key=lambda c: (-len(c.matched), -c.coverage))


def assess_extras(runs: list[Run], candidate: Candidate) -> tuple[list[int], list[int]]:
    extras = [i for i in range(len(runs)) if i not in candidate.matched]
    extra_runs = [runs[i] for i in extras]
    recurring_rows = set()
    if intraday(extra_runs, DEFAULT_POLICY) is not None:
        recurring_rows.update(r.row for r in extra_runs)
    if len(extra_runs) >= 3:
        for pattern in calendar_candidates(extra_runs, DEFAULT_POLICY):
            recurring_rows.update(extra_runs[j].row for j in pattern.matched)
    retries, conflicts = [], []
    for i in extras:
        r = runs[i]
        previous = runs[i - 1] if i else None
        # Repeated extra starts at a shared clock time may be another schedule.
        aligned = [runs[j] for j in extras if clock_distance(minute(r.start), minute(runs[j].start)) <= 10]
        span = [t for t in candidate.expected if min(x.start.date() for x in aligned) <= t.date()
                <= max(x.start.date() for x in aligned)]
        recurring = r.row in recurring_rows or (len(aligned) >= 2 and len(span) > 0 and
                                                len(aligned) / len(span) >= .8)
        # Get next expected occurrence even when this is an extra at the end of the export.
        future = [t for t in candidate.expected if t > (previous.start if previous else r.start) + timedelta(minutes=10)]
        before_next = bool(future) and r.start < min(future) - timedelta(minutes=10)
        if (previous and previous.status in BAD_STATUSES and
                0 < (r.start - previous.start).total_seconds() <= 86400 and
                before_next and not recurring):
            retries.append(r.row)
        else:
            conflicts.append(r.row)
    return retries, conflicts


def classify(history: History, policy: EvidencePolicy = DEFAULT_POLICY) -> list[Result]:
    latest = max((r.start for rs in history.workflows.values() for r in rs), default=None)
    results = []
    for name in sorted(history.workflows):
        runs = sorted(history.workflows[name], key=lambda r: (r.start, r.row))
        result = Result(name, "Unresolved", "Unknown", history.row_counts[name], len(runs),
                        runs[0].start.isoformat(" ") if runs else None,
                        runs[-1].start.isoformat(" ") if runs else None)
        result.warnings.extend(history.issues.get(name, []))
        result.warnings.extend(history.global_issues)
        health = Counter(r.status for r in runs if r.status != "succeeded")
        if health:
            result.warnings.append("Execution health (does not determine frequency): " +
                                   ", ".join(f"{n} {s or 'blank status'}" for s, n in sorted(health.items())))
        if any(r.status not in KNOWN_STATUSES for r in runs):
            result.warnings.append("Unrecognized/blank statuses cannot establish retry ancestry.")
        next_expected = None
        if not runs:
            result.evidence.append("No valid start times.")
        elif len({r.start for r in runs}) != len(runs):
            result.evidence.append("Duplicate start timestamps: duplicate export or simultaneous schedules unresolved.")
        else:
            intra = intraday(runs, policy)
            if intra:
                result.cadence, result.decision, result.evidence = intra
            else:
                candidates = calendar_candidates(runs, policy)
                if candidates:
                    best = candidates[0]
                    future = [t for t in best.expected if t > runs[-1].start + timedelta(minutes=10)]
                    next_expected = min(future) if future else None
                    retries, conflicts = assess_extras(runs, best)
                    result.cadence = best.label
                    result.likely_retry_rows = retries
                    result.evidence = [f"{len(best.matched)} scheduled starts; {best.coverage:.1%} of expected "
                                       "occurrences between first and last matching start; clock tolerance ±10 min.",
                                       f"Pattern: {best.label}; observed clock anchor near "
                                       f"{runs[min(best.matched)].start:%H:%M}."]
                    alternatives = sorted({c.label for c in candidates if c.label != best.label and
                                           c.matched == best.matched and c.coverage == best.coverage})
                    if alternatives:
                        result.evidence.append("Equivalent observed fits (not distinguishable from this history): " +
                                               "; ".join(alternatives[:5]))
                    if best.coverage < 1:
                        result.warnings.append("Gaps in expected schedule; missing logs and missed executions cannot be distinguished.")
                    if retries:
                        result.warnings.append(f"Likely retries at CSV rows {retries}: off supported schedule, after "
                                               "failure/abort/stop, within 24h, before next expected start. Preserved; ancestry unverified.")
                    if conflicts:
                        result.evidence.append(f"Unexplained/conflicting starts at CSV rows {conflicts}; engineer review required.")
                    else:
                        result.decision = eligibility(1440)
                else:
                    result.evidence = ["No supported recurring pattern satisfies the evidence, coverage and clock-alignment gates.",
                                       f"{len(runs)} starts on {len({r.start.date() for r in runs})} distinct dates. "
                                       "Sparse or irregular history; names are not schedule evidence."]
        if latest and runs and (latest - runs[-1].start).days >= 21:
            if next_expected is None or latest > next_expected + timedelta(minutes=10):
                result.warnings.append(f"Potential inactivity: last run {(latest - runs[-1].start).days} days "
                                       "before export's latest start. " +
                                       (f"Next inferred occurrence {next_expected} is overdue. " if next_expected else
                                        "No supported next occurrence is available. ") + "Not proof of retirement.")
        if history.issues.get(name) or history.global_issues:
            result.decision = "Unknown"
            result.evidence.append("Invalid/unattributable rows could change eligibility; approval blocked.")
        result.warnings.append("History inference only; scheduler, timezone and holiday calendar are unavailable.")
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="?", default="data/run_history.csv")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--spec-thresholds", action="store_true")
    args = parser.parse_args()
    try:
        with open(args.csv, encoding="utf-8-sig") as f:
            results = classify(read_history(f.read()), SPEC_POLICY if args.spec_thresholds else DEFAULT_POLICY)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"{exc}\n")
    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        for r in results:
            print(f"{r.workflow:28} {r.decision:13} {r.cadence}")
        print(dict(Counter(r.decision for r in results)))


if __name__ == "__main__":
    main()
