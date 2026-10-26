"""Small local review interface; inference and audit storage live in separate modules."""
import io
import json
import os
import sqlite3
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from classifier import classify, read_history
from corrections import CALENDAR_FREQUENCIES, CorrectionStore, dataset_id

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Flowline · Frequency review", layout="wide")
st.title("Flowline · Frequency review")
st.write("Hourly or less often can enter the standard migration path. Faster or unresolved schedules need engineer review.")
st.caption("Frequency eligibility is separate from execution health and migration readiness.")


@st.cache_data(show_spinner=False)
def analyze(data: bytes):
    text = data.decode("utf-8-sig")
    history = read_history(text)
    return classify(history), history


def main():
    uploaded = st.file_uploader("Run history CSV", type=["csv"], help="Leave empty to review the supplied 40-workflow dataset.")
    data = uploaded.getvalue() if uploaded else (ROOT / "data/run_history.csv").read_bytes()
    try:
        results, history = analyze(data)
    except (ValueError, UnicodeError) as exc:
        st.error(f"Cannot read CSV: {exc}")
        return
    digest = dataset_id(data)
    st.caption(f"Dataset: {uploaded.name if uploaded else 'supplied run_history.csv'} · "
               f"{sum(r.run_count for r in results):,} named runs · {len(results)} workflows · SHA-256 {digest[:12]}")
    for issue in history.global_issues:
        st.warning(issue)
    store = CorrectionStore(os.environ.get("FLOWLINE_DB", str(ROOT / ".local/corrections.sqlite3")))
    for r in results:
        store.register(digest, r)
    reviews = {r.workflow: store.review(digest, r) for r in results}
    rows = []
    for r in results:
        effective = reviews[r.workflow]["effective"]
        rows.append({"Workflow": r.workflow, "Frequency": effective["cadence"], "Decision": effective["decision"],
                     "Provenance": effective["provenance"], "Original decision": r.decision,
                     "Runs": r.run_count, "Warnings": len(r.warnings), "First start": r.first_start,
                     "Last start": r.last_start})
    table = pd.DataFrame(rows)
    for col, decision in zip(st.columns(3), ["In scope", "Too frequent", "Unknown"]):
        col.metric(decision, int((table["Decision"] == decision).sum()))
    st.caption("Counts and frequency below use the latest correction when present. Original results remain preserved.")
    queue = st.radio("Show workflows", ["All", "Engineer review", "In scope"], horizontal=True)
    shown = table if queue == "All" else table[table["Decision"].eq("In scope") if queue == "In scope"
                                              else table["Decision"].ne("In scope")]
    st.dataframe(shown, hide_index=True, width="stretch")
    st.download_button("Download results and correction history", json.dumps({"dataset_sha256": digest,
                       "workflows": reviews}, indent=2), file_name="flowline-review.json", mime="application/json")
    if shown.empty:
        st.info("No workflows in this queue.")
        return
    selected = st.selectbox("Review workflow", shown["Workflow"].tolist())
    original = next(r for r in results if r.workflow == selected)
    review = reviews[selected]
    effective = review["effective"]
    st.subheader(selected)
    route = "Standard migration" if effective["decision"] == "In scope" else "Engineer review"
    st.write(f"**{effective['cadence']} · {effective['decision']} · {route}**")
    st.caption(f"{effective['provenance']} · Original system result: {original.cadence} / {original.decision}")
    if review["corrections"]:
        st.info("Reviewer-supplied frequency; supporting source has not been machine-verified. "
                "The same strict 60-minute policy determines eligibility.")
    left, right = st.columns(2)
    with left:
        st.markdown("**Original classification evidence**")
        for item in original.evidence:
            st.write("• " + item)
    with right:
        st.markdown("**Warnings**")
        for warning in original.warnings:
            st.write("• " + warning)
    runs = sorted(history.workflows[selected], key=lambda r: r.start)
    if runs:
        chart_rows = [{"Start": r.start, "Hour of day": r.start.hour + r.start.minute / 60 + r.start.second / 3600,
                       "Status": r.status, "CSV row": r.row,
                       "Interpretation": "Likely retry" if r.row in original.likely_retry_rows else "Execution"}
                      for r in runs]
        chart = alt.Chart(pd.DataFrame(chart_rows)).mark_circle(size=55).encode(
            x=alt.X("Start:T", title="Observed start"),
            y=alt.Y("Hour of day:Q", scale=alt.Scale(domain=[0, 24])),
            color="Status:N", shape="Interpretation:N",
            tooltip=["Start:T", "Status:N", "Interpretation:N", "CSV row:Q"]).interactive()
        st.altair_chart(chart, width="stretch")
    with st.expander("All original CSV rows (including failed runs and possible retries)"):
        raw = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
        st.dataframe(raw[raw["workflow_name"].str.strip() == selected], hide_index=True, width="stretch")
    st.subheader("Correct inferred frequency")
    st.write("Record the schedule supported by your source. A correction adds an audit entry; it never replaces the original result.")
    # Dataset/workflow-specific form keys prevent accidentally applying another workflow's draft.
    with st.form(f"correction-{digest}-{selected}", clear_on_submit=True):
        frequency = st.selectbox("Correct frequency", ["Unknown", "Fixed interval (minutes)"] + sorted(CALENDAR_FREQUENCIES))
        minutes = st.text_input("Interval in minutes", help="Used only for fixed intervals. 59.9 stays too frequent; 60 is in scope.")
        reason = st.text_area("Reason (required)")
        source = st.text_input("Supporting source (required)", help="Scheduler reference, ticket, URL, or other supporting reference.")
        reviewer = st.text_input("Reviewer (optional)")
        submitted = st.form_submit_button("Save correction")
    if submitted:
        try:
            store.append(digest, original, frequency, minutes, reason, source, reviewer)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.rerun()
    with st.expander(f"Correction history ({len(review['corrections'])})"):
        if review["corrections"]:
            st.dataframe(pd.DataFrame(review["corrections"])[["id", "timestamp", "cadence", "decision", "reason",
                                                           "source", "reviewer", "provenance"]],
                         hide_index=True, width="stretch")
        else:
            st.write("No corrections yet.")
    st.caption("Corrections persist locally in SQLite. Back up the database or download the review history. "
               "Exact CSV content and engine version identify this review; a different export starts a new review.")


try:
    main()
except (sqlite3.Error, OSError, ValueError) as exc:
    st.error(f"Review could not be loaded or saved: {exc}. No successful save is claimed.")
