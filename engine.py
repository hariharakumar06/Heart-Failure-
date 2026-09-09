"""
Feedback engine: BASELINE (simple/static) vs PROTOTYPE (plain-language, adaptive,
clinician-gated) explanation of a heart-failure patient's daily/weekly progress.

Design contract (safety-critical):
  - Both engines may FLAG a concern.
  - Neither engine may finalize a clinical action (medication change, escalation
    closure, plan change). Every flagged item becomes a ReviewItem that sits in a
    queue until an authorised clinician/staff member calls `resolve_review_item()`.
  - The patient-facing message NEVER states a diagnosis or instructs a dose change;
    it explains, encourages, and (when needed) tells the patient a nurse will be in
    touch -- it does not promise or perform escalation itself.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import math

# ---------------------------------------------------------------------------
# Clinical thresholds (simplified, illustrative -- not a real clinical protocol)
# ---------------------------------------------------------------------------
RAPID_GAIN_KG_24H = 1.5      # >1.5kg overnight gain -> flag
GAIN_KG_3DAY = 2.0           # >2kg over rolling 3 days -> flag
IMPLAUSIBLE_WEIGHT_MIN = 30  # kg, below this is a sensor/data error not a patient
IMPLAUSIBLE_WEIGHT_MAX = 250
HIGH_SYMPTOM = 3.0           # 0-4 scale
SUSTAINED_GAIN_FROM_DRY_URGENT = 3.0   # kg above dry weight, regardless of daily rate -> urgent
SUSTAINED_GAIN_FROM_DRY_YELLOW = 2.0   # kg above dry weight -> caution


@dataclass
class ReviewItem:
    patient_id: str
    date: str
    severity: str            # 'info' | 'routine' | 'urgent'
    reason: str
    raw_values: dict
    status: str = "pending"       # pending -> approved | overridden | dismissed | escalated
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    resolved_at: Optional[str] = None


class ReviewQueue:
    """The single place clinical/authorised-staff control is exercised.
    Nothing here auto-resolves; every item requires a human action."""
    def __init__(self):
        self.items = []

    def add(self, item: ReviewItem):
        self.items.append(item)
        return item

    def pending(self):
        return [i for i in self.items if i.status == "pending"]

    def resolve(self, item: ReviewItem, action: str, staff_id: str, note: str = ""):
        assert action in ("approved", "overridden", "dismissed", "escalated")
        item.status = action
        item.resolved_by = staff_id
        item.resolution_note = note
        item.resolved_at = datetime.utcnow().isoformat()
        return item


# ---------------------------------------------------------------------------
# BASELINE engine: minimal, static, numbers-only (the thing patients disengage from)
# ---------------------------------------------------------------------------
def baseline_feedback(row, dry_weight, queue: ReviewQueue):
    """Baseline = raw numeric readout + a generic canned line. No adaptation,
    no plain-language explanation, no positive reinforcement, same message
    regardless of trend direction or history."""
    w = row.get("weight_kg")
    msgs = []
    if w is None or (isinstance(w, float) and math.isnan(w)):
        msgs.append("No data recorded today.")
    else:
        msgs.append(f"Weight: {w} kg. Dry weight: {dry_weight} kg.")
        msgs.append("HR: {} bpm. SBP: {} mmHg. Symptom score: {}.".format(
            row.get("resting_hr"), row.get("systolic_bp"), row.get("symptom_score_0_4")))
    msgs.append("Please continue to follow your care plan.")  # same line, every day

    flagged = _flag_if_needed(row, dry_weight)
    if flagged:
        queue.add(ReviewItem(row["patient_id"], str(row["date"]), flagged[0], flagged[1],
                              {"weight_kg": w}))
    return " ".join(msgs)


# ---------------------------------------------------------------------------
# PROTOTYPE engine: plain language, explains WHY, ties to a goal, adapts tone,
# still routes anything actionable through the ReviewQueue (never auto-acts).
# ---------------------------------------------------------------------------
def _flag_if_needed(row, dry_weight, history=None):
    w = row.get("weight_kg")
    if w is None or (isinstance(w, float) and math.isnan(w)):
        return None
    if w < IMPLAUSIBLE_WEIGHT_MIN or w > IMPLAUSIBLE_WEIGHT_MAX:
        return ("urgent", "implausible_reading")
    if history is not None and len(history) >= 1:
        prev = history[-1]
        if prev is not None and not (isinstance(prev, float) and math.isnan(prev)):
            if w - prev >= RAPID_GAIN_KG_24H:
                return ("urgent", "rapid_weight_gain")
    # cumulative/sustained gain vs. dry weight -- catches slow fluid accumulation that
    # no single day-over-day jump would trigger (a known failure mode of 24h-only rules)
    if dry_weight is not None:
        delta = w - dry_weight
        if delta >= SUSTAINED_GAIN_FROM_DRY_URGENT:
            return ("urgent", "sustained_gain_above_threshold")
    symptom = row.get("symptom_score_0_4")
    if symptom is not None and not (isinstance(symptom, float) and math.isnan(symptom)):
        if symptom >= HIGH_SYMPTOM:
            return ("urgent", "high_symptom_score")
    return None


def _status_light(delta_from_dry, symptom, reason=None):
    """Very simple traffic-light status used to anchor the plain-language message."""
    if reason == "implausible_reading":
        return "gray"
    if reason in ("rapid_weight_gain", "sustained_gain_above_threshold", "high_symptom_score"):
        return "red"
    if symptom is not None and symptom >= HIGH_SYMPTOM:
        return "red"
    if delta_from_dry is not None and delta_from_dry >= SUSTAINED_GAIN_FROM_DRY_YELLOW:
        return "yellow"
    return "green"


def prototype_feedback(row, dry_weight, history_weights, queue: ReviewQueue, active_goal=None):
    """Returns (patient_message, status_light, review_item_or_None)

    history_weights: list of prior weight_kg values (chronological, may contain None/NaN)
    """
    w = row.get("weight_kg")
    missing = w is None or (isinstance(w, float) and math.isnan(w))

    if missing:
        msg = ("We didn't get a weight reading from you today. That's okay -- "
               "just log it when you can. Missed a day here and there won't change your plan.")
        return msg, "gray", None

    delta = round(w - dry_weight, 1)
    symptom = row.get("symptom_score_0_4")

    flagged = _flag_if_needed(row, dry_weight, history_weights)
    review_item = None
    if flagged:
        severity, reason = flagged
        review_item = queue.add(ReviewItem(row["patient_id"], str(row["date"]), severity, reason,
                                            {"weight_kg": w, "delta_from_dry": delta,
                                             "symptom": symptom}))

    light = _status_light(delta, symptom, reason=(flagged[1] if flagged else None))

    # plain-language message, in 2 short sentences, explains the "why"
    if reason_is := (flagged[1] if flagged else None):
        if reason_is == "implausible_reading":
            msg = ("That weight reading looks off, so we're not counting it yet. "
                   "A member of your care team will check with you before anything changes.")
        elif reason_is == "rapid_weight_gain":
            msg = (f"Your weight went up quickly today ({delta:+} kg from your usual). "
                   "That can mean extra fluid, so your care team has been notified and will "
                   "review this -- no action is needed from you right now besides logging "
                   "how you feel.")
        elif reason_is == "sustained_gain_above_threshold":
            msg = (f"Your weight has been trending up and is now {delta:+} kg above your "
                   "dry weight. Your care team has been notified and will follow up -- "
                   "no action is needed from you right now besides logging how you feel.")
        elif reason_is == "high_symptom_score":
            msg = ("You reported feeling noticeably worse today. Your care team has been "
                   "notified and will follow up. If you feel like this is an emergency, "
                   "please seek urgent care.")
        else:
            msg = "We noticed something worth a closer look and your care team will review it."
    else:
        if light == "green":
            msg = (f"Nice work -- your weight today is {delta:+} kg from your dry weight, "
                   "right in your steady range. Keep doing what you're doing.")
        else:
            msg = (f"Your weight is {delta:+} kg from your dry weight -- a little higher than "
                   "usual. Keep logging daily; your care team is watching your trend.")

    if active_goal is not None:
        msg += f" Goal check-in: {active_goal}."

    return msg, light, review_item


# ---------------------------------------------------------------------------
# Comprehension proxy (used by the multi-week simulation)
# ---------------------------------------------------------------------------
def comprehension_score(education_rows):
    """Share of viewed lessons answered correctly on the 1-question check.
    Returns None if nothing was viewed."""
    viewed = education_rows[education_rows["viewed"] == True]  # noqa: E712
    if len(viewed) == 0:
        return None
    checked = viewed[viewed["comprehension_check_correct"].notna()]
    if len(checked) == 0:
        return None
    return checked["comprehension_check_correct"].mean()


def participation_rate(adherence_rows):
    """Share of days with at least one logged adherence event (weigh-in, med, symptom)."""
    if len(adherence_rows) == 0:
        return 0.0
    any_event = (
        adherence_rows["weighin_logged"].fillna(False)
        | adherence_rows["med_taken"].fillna(False)
        | adherence_rows["symptom_logged"].fillna(False)
    )
    return any_event.mean()
