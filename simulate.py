"""
Multi-week simulation: runs every synthetic patient's daily stream through the
BASELINE and PROTOTYPE feedback engines and models the behavioural feedback loop
(does today's message style change the odds the patient engages tomorrow?).

IMPORTANT / TRANSPARENCY NOTE:
The synthetic monitoring/adherence/education data itself (data_gen.py) is generated
independent of feedback condition -- it represents "what happened physiologically
and behaviourally at the source". The engagement-decay / comprehension-lift effect
of *message style* (baseline vs prototype) is a documented MODELING ASSUMPTION
(see ASSUMPTIONS below), calibrated to the qualitative pattern described in the
problem statement ("patients stop participating because feedback is not
understandable or motivating"), not to a real clinical trial. This is stated
explicitly in the report's Methods / Ethics sections -- results are a simulated
plausibility demonstration, not a clinical efficacy claim.

ASSUMPTIONS (tunable constants below):
  A1. Each day a patient's probability of logging an event is their "base" rate
      (from data_gen) MODULATED by an engagement multiplier that drifts based on
      the cumulative style of messages they've received.
  A2. Baseline messages (flat, numeric, same every day) push the multiplier down
      a little each week (fatigue). Prototype messages (plain language, explains
      why, positive reinforcement on green days) push it up a little, with a floor
      and ceiling so effects don't diverge unrealistically.
  A3. Comprehension-check correctness probability gets a fixed uplift under the
      prototype condition (simpler language, tied explicitly to the day's data)
      versus baseline (numbers only, no explanation) -- again an assumption, not
      a measured effect.
"""
import os
import numpy as np
import pandas as pd

from data_gen import generate_all
from engine import (baseline_feedback, prototype_feedback, ReviewQueue,
                     comprehension_score, participation_rate)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")

# --- tunable assumption constants (A2/A3 above) ---
BASELINE_FATIGUE_PER_WEEK = -0.015
PROTOTYPE_REINFORCE_PER_WEEK = 0.012
MULTIPLIER_FLOOR, MULTIPLIER_CEIL = 0.55, 1.15
PROTOTYPE_COMPREHENSION_UPLIFT = 0.18  # added to correctness probability


def run_condition(data, condition):
    """condition: 'baseline' or 'prototype'. Returns per-patient-per-week metrics df
    plus the review queue log."""
    monitoring = data["monitoring"]
    adherence = data["adherence"]
    education = data["education"].copy()
    goals = data["goals"]
    patients = data["patients"]

    queue = ReviewQueue()
    weekly_rows = []
    rng = np.random.default_rng(7 if condition == "baseline" else 11)

    for _, prow in patients.iterrows():
        pid = prow["patient_id"]
        dry_weight = monitoring.loc[monitoring.patient_id == pid, "dry_weight_kg"].iloc[0]
        p_mon = monitoring[monitoring.patient_id == pid].sort_values("day_index")
        p_adh = adherence[adherence.patient_id == pid].sort_values("day_index").copy()
        p_edu = education[education.patient_id == pid].copy()
        p_goals = goals[goals.patient_id == pid]

        multiplier = 1.0
        weight_hist = []
        weeks = sorted(p_mon.week.unique())
        # simulate day-by-day, adjusting participation via the engagement multiplier,
        # and recompute weekly participation from the (possibly re-drawn) events
        adjusted_events = []
        for _, row in p_mon.iterrows():
            wk = row.week
            base_p = 0.85  # nominal daily engagement draw before multiplier, re-derived
            # tie the redraw to the original synthetic adherence signal for realism:
            orig = p_adh[p_adh.day_index == row.day_index]
            orig_any = False
            if len(orig):
                o = orig.iloc[0]
                orig_any = bool(o.weighin_logged) or bool(o.med_taken) or bool(o.symptom_logged)
            # blend: original behavioural propensity * condition multiplier
            p_event = min(0.98, max(0.02, (0.75 if orig_any else 0.25) * multiplier))
            participated = rng.random() < p_event
            adjusted_events.append({"day_index": row.day_index, "week": wk,
                                     "participated": participated})

            # generate message + review item using the ACTUAL (unmodified) monitoring row
            if condition == "baseline":
                baseline_feedback(row, dry_weight, queue)
            else:
                hist_for_flag = weight_hist[-1:] if weight_hist else []
                prototype_feedback(row, dry_weight, hist_for_flag, queue)
            weight_hist.append(row.get("weight_kg"))

            # end of each week: drift the multiplier for next week
            if row.day_index % 7 == 6:
                if condition == "baseline":
                    multiplier += BASELINE_FATIGUE_PER_WEEK
                else:
                    multiplier += PROTOTYPE_REINFORCE_PER_WEEK
                multiplier = min(MULTIPLIER_CEIL, max(MULTIPLIER_FLOOR, multiplier))

        adj_df = pd.DataFrame(adjusted_events)

        for wk in weeks:
            wk_adj = adj_df[adj_df.week == wk]
            participation = wk_adj["participated"].mean() if len(wk_adj) else np.nan

            wk_edu = p_edu[p_edu.week == wk].copy()
            if condition == "prototype" and len(wk_edu):
                # apply comprehension uplift by re-drawing correctness for viewed lessons
                mask = wk_edu["viewed"] & wk_edu["comprehension_check_correct"].notna()
                wk_edu.loc[mask, "comprehension_check_correct"] = [
                    bool(rng.random() < min(0.98, 0.55 + PROTOTYPE_COMPREHENSION_UPLIFT
                                             + 0.35 * wk_adj["participated"].mean()))
                    for _ in range(mask.sum())
                ]
            comp = comprehension_score(wk_edu) if len(wk_edu) else None

            weekly_rows.append({
                "patient_id": pid, "journey": prow["journey"], "condition": condition,
                "week": wk, "participation_rate": participation,
                "comprehension_rate": comp,
            })

    weekly_df = pd.DataFrame(weekly_rows)
    return weekly_df, queue


def summarize(weekly_baseline, weekly_prototype):
    def agg(df):
        return df.groupby("week").agg(
            participation_rate=("participation_rate", "mean"),
            comprehension_rate=("comprehension_rate", "mean"),
        ).reset_index()

    b = agg(weekly_baseline)
    p = agg(weekly_prototype)
    merged = b.merge(p, on="week", suffixes=("_baseline", "_prototype"))
    return merged


def error_analysis(merged, target_participation=0.75, target_comprehension=0.80):
    last_week = merged["week"].max()
    final = merged[merged.week == last_week].iloc[0]
    rows = []
    rows.append({
        "metric": "Participation rate (final week)",
        "baseline": round(final.participation_rate_baseline, 3),
        "target": target_participation,
        "prototype_measured": round(final.participation_rate_prototype, 3),
        "error_vs_target": round(final.participation_rate_prototype - target_participation, 3),
    })
    rows.append({
        "metric": "Comprehension rate (final week)",
        "baseline": round(final.comprehension_rate_baseline, 3)
        if pd.notna(final.comprehension_rate_baseline) else None,
        "target": target_comprehension,
        "prototype_measured": round(final.comprehension_rate_prototype, 3)
        if pd.notna(final.comprehension_rate_prototype) else None,
        "error_vs_target": round(final.comprehension_rate_prototype - target_comprehension, 3)
        if pd.notna(final.comprehension_rate_prototype) else None,
    })
    return pd.DataFrame(rows)


def review_queue_summary(queue: ReviewQueue, condition):
    rows = []
    for it in queue.items:
        rows.append({"condition": condition, "patient_id": it.patient_id, "date": it.date,
                      "severity": it.severity, "reason": it.reason, "status": it.status})
    return pd.DataFrame(rows)


def run_all(weeks=8, n_background=18):
    os.makedirs(OUT_DIR, exist_ok=True)
    data = generate_all(weeks=weeks, n_background=n_background)
    for name, df in data.items():
        df.to_csv(os.path.join(OUT_DIR, f"dataset_{name}.csv"), index=False)

    weekly_baseline, q_base = run_condition(data, "baseline")
    weekly_prototype, q_proto = run_condition(data, "prototype")
    weekly_baseline.to_csv(os.path.join(OUT_DIR, "weekly_baseline.csv"), index=False)
    weekly_prototype.to_csv(os.path.join(OUT_DIR, "weekly_prototype.csv"), index=False)

    merged = summarize(weekly_baseline, weekly_prototype)
    merged.to_csv(os.path.join(OUT_DIR, "weekly_summary.csv"), index=False)

    err = error_analysis(merged)
    err.to_csv(os.path.join(OUT_DIR, "error_analysis.csv"), index=False)

    rq = pd.concat([review_queue_summary(q_base, "baseline"),
                     review_queue_summary(q_proto, "prototype")], ignore_index=True)
    rq.to_csv(os.path.join(OUT_DIR, "review_queue_log.csv"), index=False)

    print("=== Weekly summary (participation / comprehension, baseline vs prototype) ===")
    print(merged.to_string(index=False))
    print("\n=== Error analysis vs target ===")
    print(err.to_string(index=False))
    print("\n=== Review queue item counts ===")
    print(rq.groupby(["condition", "severity"]).size())

    return data, merged, err, rq


if __name__ == "__main__":
    run_all()
