"""
Synthetic data generator for the Heart-Failure Patient-Engagement Feedback App.

Generates, for each synthetic patient over N weeks:
  - monitoring_trends: daily weight, resting HR, systolic BP, reported symptom score
  - goals: weekly goal definitions + progress
  - education_interactions: micro-lesson views + comprehension check answers
  - adherence_events: medication / weigh-in / symptom-log completion events

Two named journeys are always included:
  - P001 "low_urgency"  : stable, slowly improving, high adherence
  - P002 "high_urgency" : deteriorating (fluid retention pattern), inconsistent adherence

Additional background patients (P003.. ) are generated for statistical power in the
multi-week simulation. Edge/failure cases are injected as explicit flags so the
engine/tests can locate them deterministically.
"""
import numpy as np
import pandas as pd

RNG_SEED = 42


def _daterange(start, days):
    return pd.date_range(start=start, periods=days, freq="D")


def generate_patient(patient_id, journey, start="2026-01-05", weeks=8, seed=0):
    """Generate one patient's full synthetic dataset.

    journey: 'low_urgency' | 'high_urgency' | 'background_stable' | 'background_variable'
    Returns dict of DataFrames: monitoring, goals, education, adherence
    """
    rng = np.random.default_rng(RNG_SEED + seed)
    days = weeks * 7
    dates = _daterange(start, days)

    dry_weight = rng.uniform(70, 95)
    base_hr = rng.uniform(68, 78)
    base_sbp = rng.uniform(112, 128)

    rows_monitor, rows_adh, edge_flags = [], [], []

    # journey-specific drift parameters
    if journey == "low_urgency":
        weight_drift = -0.01     # slowly trending toward dry weight / stable
        symptom_base = 1.0       # 0-4 scale, low
        adherence_p = 0.93
        noise = 0.35
    elif journey == "high_urgency":
        weight_drift = 0.06      # steady fluid gain -> decompensation risk
        symptom_base = 1.6
        adherence_p = 0.72
        noise = 0.5
    elif journey == "background_variable":
        weight_drift = rng.uniform(-0.02, 0.03)
        symptom_base = rng.uniform(0.5, 2.0)
        adherence_p = rng.uniform(0.6, 0.9)
        noise = 0.45
    else:  # background_stable
        weight_drift = rng.uniform(-0.02, 0.01)
        symptom_base = rng.uniform(0.3, 1.2)
        adherence_p = rng.uniform(0.8, 0.97)
        noise = 0.3

    weight = dry_weight
    engagement_fatigue = 0.0  # rises for baseline-style flat feedback, used later by engine

    for i, d in enumerate(dates):
        week_no = i // 7

        # --- decompensation event for the high-urgency patient (edge case: rapid gain) ---
        rapid_gain_day = journey == "high_urgency" and i == 3 * 7 + 2  # week 4
        if rapid_gain_day:
            weight += rng.uniform(1.8, 2.4)  # >2lb/1kg-ish overnight jump -> should trigger alert
            edge_flags.append((patient_id, d, "rapid_weight_gain"))
        else:
            weight += weight_drift + rng.normal(0, noise)

        hr = base_hr + (5 if journey == "high_urgency" and week_no >= 4 else 0) + rng.normal(0, 3)
        sbp = base_sbp + (8 if journey == "high_urgency" and week_no >= 4 else 0) + rng.normal(0, 6)
        symptom = max(0, symptom_base + (1.5 if journey == "high_urgency" and week_no >= 4 else 0)
                      + rng.normal(0, 0.6))

        # --- edge case: missing monitoring day (device not synced) ---
        missing_day = (patient_id == "P002" and i == 5 * 7 + 1) or (rng.random() < 0.03)
        # --- edge case: implausible sensor reading (data quality) ---
        sensor_error = (patient_id == "P001" and i == 2 * 7 + 4)
        if sensor_error:
            weight_val = 9.9  # clearly implausible scale glitch
            edge_flags.append((patient_id, d, "implausible_reading"))
        elif missing_day:
            weight_val = np.nan
            hr = np.nan
            sbp = np.nan
            symptom = np.nan
            edge_flags.append((patient_id, d, "missing_data"))
        else:
            weight_val = round(weight, 1)

        rows_monitor.append({
            "patient_id": patient_id, "date": d, "day_index": i, "week": week_no + 1,
            "weight_kg": weight_val,
            "resting_hr": None if missing_day else round(hr, 0),
            "systolic_bp": None if missing_day else round(sbp, 0),
            "symptom_score_0_4": None if missing_day else round(max(0, min(4, symptom)), 1),
            "dry_weight_kg": round(dry_weight, 1),
        })

        # adherence events (med taken, weigh-in logged, symptom logged)
        # engagement fatigue nudges probability down over time under a flat/baseline-style app;
        # the *actual* participation difference is computed later in engine per condition.
        did_weighin = (not missing_day) and (rng.random() < adherence_p)
        did_med = rng.random() < (adherence_p - 0.03)
        # edge case: connectivity/sync failure -> event exists but fails to transmit
        sync_failure = (patient_id == "P002" and i == 6 * 7 + 3)
        if sync_failure:
            edge_flags.append((patient_id, d, "sync_failure"))

        rows_adh.append({
            "patient_id": patient_id, "date": d, "day_index": i, "week": week_no + 1,
            "med_taken": bool(did_med) if not sync_failure else None,
            "weighin_logged": bool(did_weighin) if not sync_failure else None,
            "symptom_logged": bool((not missing_day) and rng.random() < (adherence_p - 0.05)),
            "sync_failure": bool(sync_failure),
        })

    monitoring = pd.DataFrame(rows_monitor)
    adherence = pd.DataFrame(rows_adh)

    # --- weekly goals ---
    goal_rows = []
    for w in range(1, weeks + 1):
        wk_mon = monitoring[monitoring.week == w]
        weighins = adherence[adherence.week == w]["weighin_logged"].fillna(False).sum()
        target = 7
        goal_rows.append({
            "patient_id": patient_id, "week": w,
            "goal": "Log your weight every day",
            "target_value": target, "achieved_value": int(weighins),
            "goal_type": "adherence",
        })
        avg_symptom = wk_mon["symptom_score_0_4"].mean()
        goal_rows.append({
            "patient_id": patient_id, "week": w,
            "goal": "Keep symptom score below 2",
            "target_value": 2.0,
            "achieved_value": None if pd.isna(avg_symptom) else round(avg_symptom, 2),
            "goal_type": "clinical",
        })
        # edge case: conflicting/unachievable goal for high_urgency week 4 (weight-loss goal
        # set before the retention event became visible) -> tests engine's handling of a goal
        # that is now clinically inappropriate to praise progress on
        if journey == "high_urgency" and w == 4:
            goal_rows.append({
                "patient_id": patient_id, "week": w,
                "goal": "Reduce weight by 1kg this week",
                "target_value": -1.0, "achieved_value": None,
                "goal_type": "conflicting_stale_goal",
            })
    goals = pd.DataFrame(goal_rows)

    # --- education interactions (micro-lessons with a 1-question comprehension check) ---
    lessons = [
        ("Why we track your daily weight", "low_literacy"),
        ("What your symptom score means", "low_literacy"),
        ("Taking your heart medicines on schedule", "low_literacy"),
        ("When to call your care team", "low_literacy"),
    ]
    edu_rows = []
    for w in range(1, weeks + 1):
        lesson_title, level = lessons[(w - 1) % len(lessons)]
        # comprehension probability differs by whether patient is engaged that week
        wk_adh = adherence[adherence.week == w]
        engaged = wk_adh["weighin_logged"].fillna(False).mean() > 0.5
        viewed = rng.random() < (0.85 if engaged else 0.4)
        correct = None
        if viewed:
            base_p_correct = 0.9 if engaged else 0.55
            correct = bool(rng.random() < base_p_correct)
        edu_rows.append({
            "patient_id": patient_id, "week": w, "lesson": lesson_title,
            "viewed": bool(viewed), "comprehension_check_correct": correct,
        })
    education = pd.DataFrame(edu_rows)

    edge_df = pd.DataFrame(edge_flags, columns=["patient_id", "date", "edge_case_type"])
    return {
        "monitoring": monitoring, "goals": goals,
        "education": education, "adherence": adherence, "edge_cases": edge_df,
    }


def generate_all(weeks=8, n_background=6, start="2026-01-05"):
    patients = [("P001", "low_urgency"), ("P002", "high_urgency")]
    for k in range(n_background):
        j = "background_stable" if k % 2 == 0 else "background_variable"
        patients.append((f"P{3+k:03d}", j))

    all_frames = {"monitoring": [], "goals": [], "education": [], "adherence": [], "edge_cases": []}
    meta = []
    for i, (pid, journey) in enumerate(patients):
        data = generate_patient(pid, journey, start=start, weeks=weeks, seed=i)
        for k in all_frames:
            all_frames[k].append(data[k])
        meta.append({"patient_id": pid, "journey": journey})

    out = {k: pd.concat(v, ignore_index=True) for k, v in all_frames.items()}
    out["patients"] = pd.DataFrame(meta)
    return out


if __name__ == "__main__":
    import os
    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    data = generate_all()
    for name, df in data.items():
        df.to_csv(os.path.join(out_dir, f"{name}.csv"), index=False)
        print(name, df.shape)
