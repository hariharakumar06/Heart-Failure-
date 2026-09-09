"""
Heart-Failure Patient-Engagement Feedback App -- Streamlit prototype.

Run locally with:  streamlit run app.py
(Requires: pip install streamlit pandas numpy matplotlib)

Two views:
  - Patient view   : plain-language daily progress, goals, education, streaks
  - Clinician view : review queue with Approve / Override / Escalate / Dismiss
                      (nothing clinical is ever auto-finalized by the app)

Two demo journeys are preloaded (P001 low-urgency / P002 high-urgency), plus an
edge-case injector and a baseline-vs-prototype side-by-side comparison, and a
multi-week metrics tab.
"""
import os
import sys
import math
import pandas as pd
import numpy as np
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from data_gen import generate_all  # noqa: E402
from engine import (baseline_feedback, prototype_feedback, ReviewQueue,
                     ReviewItem, comprehension_score, participation_rate)  # noqa: E402

st.set_page_config(page_title="HF Patient Engagement", layout="wide")

DATA_DIR = os.path.join(os.path.dirname(__file__), "outputs")


@st.cache_data
def load_data():
    csvs = {}
    for name in ["monitoring", "goals", "education", "adherence", "edge_cases", "patients"]:
        path = os.path.join(DATA_DIR, f"dataset_{name}.csv")
        if os.path.exists(path):
            csvs[name] = pd.read_csv(path, parse_dates=["date"] if "date" in
                                      pd.read_csv(path, nrows=0).columns else None)
        else:
            csvs = None
            break
    if csvs is None:
        csvs = generate_all(weeks=8, n_background=18)
    return csvs


if "queue" not in st.session_state:
    st.session_state.queue = ReviewQueue()
if "audit_log" not in st.session_state:
    st.session_state.audit_log = []
if "injected_edge" not in st.session_state:
    st.session_state.injected_edge = None

data = load_data()
patients = data["patients"]

st.title("Heart-Failure Recovery: Patient-Engagement Feedback App")
st.caption("Prototype -- explains progress in plain language. All clinical actions "
           "require review by an authorised clinician or staff member (see Clinician tab).")

tab_patient, tab_clinician, tab_compare, tab_metrics, tab_about = st.tabs(
    ["Patient view", "Clinician / staff view", "Baseline vs Prototype", "Multi-week metrics", "About / architecture"]
)

# ---------------------------------------------------------------------------
# Shared sidebar controls
# ---------------------------------------------------------------------------
st.sidebar.header("Demo controls")
pid = st.sidebar.selectbox(
    "Patient (journey)", patients.patient_id,
    format_func=lambda p: f"{p} - {patients.set_index('patient_id').loc[p, 'journey']}"
)
p_mon = data["monitoring"][data["monitoring"].patient_id == pid].sort_values("day_index").reset_index(drop=True)
p_adh = data["adherence"][data["adherence"].patient_id == pid].sort_values("day_index").reset_index(drop=True)
p_edu = data["education"][data["education"].patient_id == pid]
p_goals = data["goals"][data["goals"].patient_id == pid]
dry_weight = p_mon["dry_weight_kg"].iloc[0]

day_idx = st.sidebar.slider("Simulated day", 0, len(p_mon) - 1, min(21, len(p_mon) - 1))
row = p_mon.loc[day_idx]
week_no = int(row.week)
history_weights = p_mon.loc[:day_idx - 1, "weight_kg"].tolist() if day_idx > 0 else []

st.sidebar.markdown("---")
st.sidebar.subheader("Inject an edge case (this day)")
edge_choice = st.sidebar.selectbox(
    "Failure state",
    ["None", "Missing data today", "Implausible sensor reading", "Rapid weight gain (fluid retention)"]
)
sim_row = row.copy()
if edge_choice == "Missing data today":
    sim_row["weight_kg"] = np.nan
elif edge_choice == "Implausible sensor reading":
    sim_row["weight_kg"] = 4.2
elif edge_choice == "Rapid weight gain (fluid retention)":
    sim_row["weight_kg"] = (row.weight_kg if not math.isnan(row.weight_kg) else dry_weight) + 2.1

active_goal_row = p_goals[(p_goals.week == week_no) & (p_goals.goal_type != "conflicting_stale_goal")]
active_goal_text = active_goal_row.iloc[0]["goal"] if len(active_goal_row) else None

# ---------------------------------------------------------------------------
# PATIENT VIEW
# ---------------------------------------------------------------------------
with tab_patient:
    st.subheader(f"Today's update -- {pid} (day {day_idx + 1}, week {week_no})")
    msg, light, review_item = prototype_feedback(
        sim_row, dry_weight, history_weights, st.session_state.queue, active_goal_text
    )
    color = {"green": "#1f6f43", "yellow": "#b8860b", "red": "#c0392b", "gray": "#555"}[light]
    st.markdown(
        f"<div style='padding:16px;border-radius:10px;background:{color}20;"
        f"border-left:6px solid {color};font-size:1.05rem'>{msg}</div>",
        unsafe_allow_html=True,
    )
    if review_item is not None:
        st.info("This has been sent to your care team for review. You'll hear from them "
                "if anything needs to change -- you don't need to do anything else right now.")

    c1, c2, c3 = st.columns(3)
    weighins_wk = p_adh[p_adh.week == week_no]["weighin_logged"].fillna(False).sum()
    c1.metric("Weigh-ins this week", f"{int(weighins_wk)} / 7")
    streak = 0
    for v in p_adh.sort_values("day_index", ascending=False)["weighin_logged"]:
        if v is True:
            streak += 1
        else:
            break
    c2.metric("Current logging streak", f"{streak} days")
    comp = comprehension_score(p_edu[p_edu.week <= week_no])
    c3.metric("Comprehension check score", f"{comp*100:.0f}%" if comp is not None else "n/a")

    st.markdown("#### Your goals")
    for _, g in p_goals[p_goals.week == week_no].iterrows():
        if g.goal_type == "conflicting_stale_goal":
            continue  # never surface a stale/conflicting goal as something to celebrate or fail
        if g.goal_type == "adherence":
            pct = min(1.0, (g.achieved_value or 0) / g.target_value)
            st.progress(pct, text=f"{g.goal}: {int(g.achieved_value or 0)}/{int(g.target_value)} days")
        else:
            st.write(f"- **{g.goal}** -- " + (
                f"this week's average: {g.achieved_value}" if pd.notna(g.achieved_value) else "not enough data yet"
            ))

    st.markdown("#### This week's short lesson")
    lesson = p_edu[p_edu.week == week_no]
    if len(lesson):
        l = lesson.iloc[0]
        st.write(f"**{l.lesson}**")
        st.write("Written in plain language, one short idea, one quick check to see it landed.")
        if pd.notna(l.comprehension_check_correct):
            st.write("Your check-in: " + ("correct ✅" if l.comprehension_check_correct else "let's review this together next time"))

# ---------------------------------------------------------------------------
# CLINICIAN VIEW
# ---------------------------------------------------------------------------
with tab_clinician:
    st.subheader("Review queue -- authorised staff only")
    st.caption("Every flagged item requires a human decision. Nothing here changes the "
               "patient's plan until a clinician acts.")
    pending = st.session_state.queue.pending()
    if not pending:
        st.success("No pending items. Try the edge-case injector in the sidebar, then "
                    "revisit the Patient view tab to generate a flagged event.")
    for i, item in enumerate(pending):
        with st.expander(f"[{item.severity.upper()}] {item.patient_id} - {item.date} - {item.reason}"):
            st.write(item.raw_values)
            note = st.text_input("Clinical note", key=f"note_{i}")
            colA, colB, colC, colD = st.columns(4)
            staff_id = "Demo_Clinician"
            if colA.button("Approve", key=f"appr_{i}"):
                st.session_state.queue.resolve(item, "approved", staff_id, note)
                st.session_state.audit_log.append((item.patient_id, item.date, item.reason, "approved", staff_id))
                st.rerun()
            if colB.button("Escalate", key=f"esc_{i}"):
                st.session_state.queue.resolve(item, "escalated", staff_id, note)
                st.session_state.audit_log.append((item.patient_id, item.date, item.reason, "escalated", staff_id))
                st.rerun()
            if colC.button("Override", key=f"ovr_{i}"):
                st.session_state.queue.resolve(item, "overridden", staff_id, note)
                st.session_state.audit_log.append((item.patient_id, item.date, item.reason, "overridden", staff_id))
                st.rerun()
            if colD.button("Dismiss", key=f"dis_{i}"):
                st.session_state.queue.resolve(item, "dismissed", staff_id, note)
                st.session_state.audit_log.append((item.patient_id, item.date, item.reason, "dismissed", staff_id))
                st.rerun()

    st.markdown("#### Audit log (human review points)")
    if st.session_state.audit_log:
        st.dataframe(pd.DataFrame(st.session_state.audit_log,
                                   columns=["patient_id", "date", "reason", "action", "staff_id"]))
    else:
        st.write("No actions taken yet.")

# ---------------------------------------------------------------------------
# BASELINE VS PROTOTYPE COMPARISON
# ---------------------------------------------------------------------------
with tab_compare:
    st.subheader("Same data point, two feedback styles")
    dummy_q = ReviewQueue()
    b_msg = baseline_feedback(sim_row, dry_weight, dummy_q)
    p_msg, p_light, _ = prototype_feedback(sim_row, dry_weight, history_weights, dummy_q, active_goal_text)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Baseline (numbers-only, static)**")
        st.code(b_msg, language=None)
    with col2:
        st.markdown("**Prototype (plain language, adaptive, goal-linked)**")
        st.write(p_msg)
    st.caption("Baseline repeats the same generic sentence every day regardless of trend; "
               "the prototype explains what changed, why it matters, and what (if anything) "
               "the patient needs to do -- while routing anything actionable to a clinician.")

# ---------------------------------------------------------------------------
# MULTI-WEEK METRICS
# ---------------------------------------------------------------------------
with tab_metrics:
    st.subheader("8-week simulation: baseline vs prototype")
    summary_path = os.path.join(DATA_DIR, "weekly_summary.csv")
    if os.path.exists(summary_path):
        merged = pd.read_csv(summary_path)
        c1, c2 = st.columns(2)
        with c1:
            st.line_chart(merged.set_index("week")[["participation_rate_baseline", "participation_rate_prototype"]])
            st.caption("Participation rate by week")
        with c2:
            st.line_chart(merged.set_index("week")[["comprehension_rate_baseline", "comprehension_rate_prototype"]])
            st.caption("Comprehension-check accuracy by week")
        err_path = os.path.join(DATA_DIR, "error_analysis.csv")
        if os.path.exists(err_path):
            st.markdown("#### Target vs measured (final week)")
            st.dataframe(pd.read_csv(err_path))
    else:
        st.warning("Run `python3 src/simulate.py` first to generate the multi-week metrics files.")

# ---------------------------------------------------------------------------
# ABOUT
# ---------------------------------------------------------------------------
with tab_about:
    st.markdown("""
### Architecture (this prototype)
1. **Synthetic data layer** (`src/data_gen.py`) -- daily monitoring trends, weekly goals,
   education interactions, adherence events, for two named journeys plus a background
   cohort, with edge cases deterministically injected.
2. **Feedback engine** (`src/engine.py`) -- baseline (static/numeric) and prototype
   (plain-language, traffic-light, goal-linked) explanation generators. Both route any
   actionable finding to a `ReviewQueue`; only the prototype adapts tone/content.
3. **Review queue / human-in-the-loop gate** -- the *only* place a clinical action becomes
   final. Every item starts `pending`; a clinician must Approve / Escalate / Override /
   Dismiss it. This is enforced in code, not just in the UI.
4. **Simulation & metrics** (`src/simulate.py`, `src/make_charts.py`) -- multi-week
   behavioural simulation and comparison metrics.
5. **This Streamlit app** -- patient view, clinician view, comparison view, metrics view.

### User flow
Patient logs a reading -> engine classifies status (green/yellow/red/gray) -> plain-language
message generated -> if flagged, a `ReviewItem` is created -> clinician reviews in their
queue -> clinician action is the only thing that finalizes any change -> patient is told a
person is involved, never told a diagnosis or an automated decision.
""")
