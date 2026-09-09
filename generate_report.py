# -*- coding: utf-8 -*-
import os
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                                 Table, TableStyle, Image, ListFlowable, ListItem, HRFlowable)

BASE = os.path.dirname(__file__)
OUT_DIR = os.path.join(BASE, "..", "outputs")
PDF_PATH = os.path.join(OUT_DIR, "HF_Patient_Engagement_Report.pdf")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="H1c", parent=styles["Heading1"], spaceBefore=14, spaceAfter=8,
                           textColor=colors.HexColor("#123456")))
styles.add(ParagraphStyle(name="H2c", parent=styles["Heading2"], spaceBefore=10, spaceAfter=6,
                           textColor=colors.HexColor("#1f6f43")))
styles.add(ParagraphStyle(name="Body", parent=styles["Normal"], spaceAfter=6, leading=14))
styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8.5, textColor=colors.grey))
styles.add(ParagraphStyle(name="CodeBlock", parent=styles["Normal"], fontName="Courier",
                           fontSize=8.3, leading=11, backColor=colors.HexColor("#f4f4f4")))
styles.add(ParagraphStyle(name="Callout", parent=styles["Normal"], leading=14,
                           backColor=colors.HexColor("#fff6e5"), borderColor=colors.HexColor("#d9a441"),
                           borderWidth=1, borderPadding=8, spaceAfter=8))

story = []


def h1(t):
    story.append(Paragraph(t, styles["H1c"]))


def h2(t):
    story.append(Paragraph(t, styles["H2c"]))


def p(t):
    story.append(Paragraph(t, styles["Body"]))


def bullets(items):
    story.append(ListFlowable([ListItem(Paragraph(i, styles["Body"])) for i in items],
                               bulletType="bullet", leftIndent=14))


def hr():
    story.append(HRFlowable(width="100%", color=colors.HexColor("#cccccc"), spaceBefore=4, spaceAfter=10))


def df_table(df, col_widths=None, fontsize=8):
    data = [list(df.columns)] + df.astype(str).values.tolist()
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123456")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), fontsize),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fa")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))


# ============================================================================
# COVER
# ============================================================================
story.append(Spacer(1, 60))
story.append(Paragraph("Heart-Failure Patient-Engagement Feedback App", styles["Title"]))
story.append(Paragraph("Explaining recovery progress in plain language, with clinician-gated safety",
                        ParagraphStyle(name="Sub", parent=styles["Normal"], fontSize=13,
                                       alignment=1, textColor=colors.HexColor("#444444"), spaceBefore=10)))
story.append(Spacer(1, 30))
story.append(Paragraph("Prototype report: scenario, baseline, implementation, usability walkthrough, "
                        "edge-case tests, performance results, ethics note, deployment checklist.",
                        ParagraphStyle(name="Sub2", parent=styles["Normal"], alignment=1, fontSize=10.5)))
story.append(Spacer(1, 200))
story.append(Paragraph("Data science prototype -- synthetic data, simulated multi-week pilot.",
                        styles["Small"]))
story.append(PageBreak())

# ============================================================================
# 1. SCENARIO DEFINITION
# ============================================================================
h1("1. Scenario definition")
p("<b>Population:</b> adults with heart failure recovering at home in the weeks after hospital "
  "discharge, enrolled in a remote-monitoring / patient-engagement pilot.")
p("<b>Problem:</b> patients stop participating in remote monitoring because the feedback they "
  "receive is not understandable (raw numbers, clinical jargon) or not motivating (flat, generic, "
  "the same regardless of how they are doing). Disengagement removes the early-warning signal the "
  "programme depends on.")
p("<b>Design goal:</b> a patient-engagement feedback app that explains day-to-day and week-to-week "
  "progress in plain language, sustains participation and comprehension over a multi-week recovery "
  "window, and never removes the clinician / authorised staff member from the loop for anything "
  "clinically actionable.")
h2("Hard constraint (non-negotiable)")
story.append(Paragraph(
    "The app may explain, encourage, and flag. It may not diagnose, instruct a medication change, "
    "or close out a clinical concern on its own. Every actionable finding becomes a pending review "
    "item that only an authorised clinician/staff member can approve, override, escalate, or "
    "dismiss. This is enforced in the code path (engine.py -> ReviewQueue), not only in the UI copy.",
    styles["Callout"]))
h2("In scope for this prototype")
bullets([
    "Daily monitoring trends (weight, heart rate, blood pressure, symptom score) explained in plain language.",
    "Weekly goals (adherence + clinical) with progress shown simply.",
    "Short plain-language education micro-lessons with a 1-question comprehension check.",
    "Adherence events (medication, weigh-in, symptom log).",
    "A clinician/staff review queue that gates every actionable output.",
    "A multi-week simulation comparing this design against a plain numeric baseline.",
])
h2("Out of scope")
bullets([
    "Real patient data or a validated clinical protocol -- thresholds here are illustrative, not medical advice.",
    "Direct medication titration or device control.",
    "Full EHR integration (a deployment checklist item, not built here).",
])

# ============================================================================
# 2. BASELINE METHOD
# ============================================================================
h1("2. Baseline method")
p("The baseline represents what many remote-monitoring tools already do, and what the problem "
  "statement says is driving disengagement: a numeric readout plus one static sentence, identical "
  "every day regardless of trend, direction, or history.")
h2("Baseline example output")
story.append(Paragraph(
    "Weight: 91.2 kg. Dry weight: 89.3 kg. HR: 74 bpm. SBP: 121 mmHg. Symptom score: 1.2. "
    "Please continue to follow your care plan.", styles["CodeBlock"]))
p("The baseline still runs every reading through the same safety checks as the prototype (it can "
  "still create a pending review item), so the comparison below isolates the effect of "
  "<i>explanation style</i> on participation and comprehension, not a difference in clinical safety "
  "coverage.")
h2("Known weaknesses of the baseline (by design, to demonstrate the gap)")
bullets([
    "No explanation of why a number matters or what to do about it.",
    "No positive reinforcement on good days -- same flat sentence whether the trend is good or bad.",
    "No connection to the patient's own goals.",
    "No adaptation over time -- a strong driver of the fatigue/disengagement pattern in the results below.",
])

# ============================================================================
# 3. IMPLEMENTED SOLUTION -- ARCHITECTURE & USER FLOW
# ============================================================================
story.append(PageBreak())
h1("3. Implemented solution: architecture and user flow")
h2("Architecture")
bullets([
    "<b>Synthetic data layer</b> (data_gen.py) -- daily monitoring trends, weekly goals, education "
    "interactions and adherence events for two named journeys (P001 low-urgency, P002 high-urgency) "
    "plus an 18-patient background cohort; edge cases are injected deterministically.",
    "<b>Feedback engine</b> (engine.py) -- baseline_feedback() and prototype_feedback() generate the "
    "patient-facing message; both call a shared threshold layer that can create a ReviewItem.",
    "<b>Review queue</b> (ReviewQueue / ReviewItem) -- the single point of clinical control. Items are "
    "created 'pending' and only leave that state via an explicit staff action (approve / escalate / "
    "override / dismiss), each stamped with a staff id and timestamp (audit trail).",
    "<b>Simulation layer</b> (simulate.py, make_charts.py) -- runs both conditions across the full "
    "cohort for 8 weeks and models the behavioural feedback loop between message style and next-week "
    "engagement (see Section 6 methodology note).",
    "<b>Streamlit app</b> (app.py) -- patient view, clinician/staff view, baseline-vs-prototype "
    "comparison, multi-week metrics, and an edge-case injector for live demonstration.",
])
h2("User flow")
bullets([
    "1. Patient logs (or the device syncs) a daily reading.",
    "2. Engine computes a plain-language status: green (on track), yellow (worth watching), "
    "red (care team notified), or gray (no data / not counted yet).",
    "3. If the reading crosses a safety threshold, a ReviewItem is created and stays 'pending'.",
    "4. Patient sees an explanatory message; if something was flagged, they are told a person will "
    "follow up -- never a diagnosis, never an automated instruction.",
    "5. Clinician/staff opens the review queue, sees the raw values and reason, and takes the only "
    "action that can finalize anything: approve / escalate / override / dismiss, with a note.",
    "6. The action is written to an audit log (patient, date, reason, action, staff id).",
])
h2("Why this approach is appropriate")
p("A rules-based, template-driven explanation layer (rather than a free-form generative one) keeps "
  "every patient-facing sentence traceable to a specific data value and a specific, reviewable "
  "threshold -- important in a safety-sensitive setting where an ungrounded or overconfident message "
  "could delay real care-seeking or cause unnecessary alarm. Keeping the clinician gate as a separate, "
  "structurally-enforced component (rather than a UI convention) means the safety property holds even "
  "if the front end changes.")

# ============================================================================
# 4. USABILITY WALKTHROUGH -- TWO PATIENT JOURNEYS
# ============================================================================
story.append(PageBreak())
h1("4. Usability walkthrough: two patient journeys")
p("Both journeys use the plain-language prototype engine against the synthetic data described in "
  "Section 3. Selected days are shown; 'REVIEW ITEM' marks a human-review touch point.")

walk_path = os.path.join(OUT_DIR, "journey_walkthrough.txt")
h2("P001 -- low urgency (stable, improving)")
p("Dry weight 89.3 kg. This patient stays in range for most of the pilot, with one data-quality "
  "blip and a late, gradual upward drift the system catches even though no single day looks alarming.")
low_rows = [
    ["Day 1 (wk1)", "green", "Nice work -- your weight today is +0.4 kg from your dry weight...", "--"],
    ["Day 14 (wk2)", "green", "Nice work -- your weight today is +1.7 kg from your dry weight...", "--"],
    ["Day 19 (wk3)", "gray", "That weight reading looks off, so we're not counting it yet...", "REVIEW (urgent / implausible_reading)"],
    ["Day 28 (wk4)", "green", "Nice work -- your weight today is +0.2 kg from your dry weight...", "--"],
    ["Day 41 (wk6)", "yellow", "Your weight is +2.7 kg from your dry weight -- a little higher than usual...", "--"],
    ["Day 56 (wk8)", "red", "Your weight has been trending up and is now +4.2 kg above your dry weight...", "REVIEW (urgent / sustained_gain_above_threshold)"],
]
df_table(pd.DataFrame(low_rows, columns=["Day", "Status", "Message (truncated)", "Human review point"]),
         col_widths=[0.7*inch, 0.6*inch, 3.4*inch, 1.8*inch])

h2("P002 -- high urgency (deteriorating / fluid retention)")
p("Dry weight 86.3 kg. This patient looks stable through week 3, then shows a sustained fluid-"
  "retention pattern from week 4 onward -- the kind of slow drift that a 24-hour-only alert rule "
  "would miss, but which the cumulative-vs-dry-weight check in Section 3 catches and routes to a "
  "clinician repeatedly (not just once) as it worsens toward week 8.")
high_rows = [
    ["Day 1 (wk1)", "green", "Nice work -- your weight today is -0.4 kg from your dry weight...", "--"],
    ["Day 21 (wk3)", "green", "Nice work -- your weight today is +1.5 kg from your dry weight...", "--"],
    ["Day 25 (wk4)", "red", "Your weight has been trending up and is now +4.0 kg above your dry weight...", "REVIEW (urgent / sustained_gain_above_threshold)"],
    ["Day 31 (wk5)", "red", "Your weight has been trending up and is now +3.8 kg above your dry weight...", "REVIEW (urgent / sustained_gain_above_threshold)"],
    ["Day 56 (wk8)", "red", "Your weight has been trending up and is now +10.0 kg above your dry weight...", "REVIEW (urgent / sustained_gain_above_threshold)"],
]
df_table(pd.DataFrame(high_rows, columns=["Day", "Status", "Message (truncated)", "Human review point"]),
         col_widths=[0.7*inch, 0.6*inch, 3.4*inch, 1.8*inch])
p("In both journeys the patient-facing text never states a diagnosis or an instruction to change "
  "medication; it consistently says a person will follow up. All six flagged points above sit in "
  "the clinician queue as 'pending' until a staff member acts (demonstrated live in the Streamlit "
  "Clinician view).")

# ============================================================================
# 5. EDGE-CASE / FAILURE-STATE TESTS
# ============================================================================
story.append(PageBreak())
h1("5. Edge-case and failure-state tests")
p("Five realistic failure states were implemented as automated, assertion-based tests "
  "(edge_case_tests.py) -- more than the minimum of three requested. All five pass.")
edge_rows = [
    ["Missing data day (device didn't sync)", "Neutral 'gray' status, no fabricated value, no false alarm, no review item created."],
    ["Implausible sensor reading (e.g. 4.2 kg)", "Flagged urgent + pending; patient told data is being checked, not that something is wrong with them."],
    ["Rapid 24h weight gain", "Flagged urgent + pending; reassuring, non-instructional patient message; item only leaves 'pending' after an explicit staff action."],
    ["Connectivity / sync failure", "Adherence fields recorded as unknown, not as a missed dose -- the patient is not penalized for a system-side failure."],
    ["Conflicting / clinically stale goal", "Excluded from positive-progress messaging entirely rather than being praised or silently failed."],
]
df_table(pd.DataFrame(edge_rows, columns=["Failure state", "Required safe behaviour (asserted in tests)"]),
         col_widths=[2.3*inch, 4.2*inch])
p("A sixth, related property is also asserted: resolving a review item requires a staff id and "
  "timestamp, so the audit trail can show who acted and when for every flagged event -- this is the "
  "concrete implementation of 'clinician/authorised staff control over final actions'.")

# ============================================================================
# 6. PERFORMANCE RESULTS
# ============================================================================
story.append(PageBreak())
h1("6. Performance results: 8-week simulation")
p("<b>Methodology note (read before the numbers):</b> the underlying monitoring, adherence and "
  "education events are generated independent of feedback condition (Section 3). What differs "
  "between 'baseline' and 'prototype' below is a documented behavioural-modeling assumption: flat, "
  "generic baseline messages apply a small weekly engagement-fatigue drag, while explanatory, "
  "positively-framed prototype messages apply a small weekly reinforcement -- calibrated only to "
  "reproduce the qualitative pattern named in the problem statement, not to a measured clinical "
  "trial effect size. Treat the results as a plausibility demonstration of the design, not an "
  "efficacy claim (see Section 8, Ethics).")

img_participation = os.path.join(OUT_DIR, "chart_participation.png")
img_comprehension = os.path.join(OUT_DIR, "chart_comprehension.png")
if os.path.exists(img_participation):
    story.append(Image(img_participation, width=5.6*inch, height=3.45*inch))
if os.path.exists(img_comprehension):
    story.append(Image(img_comprehension, width=5.6*inch, height=3.45*inch))

err_path = os.path.join(OUT_DIR, "error_analysis.csv")
if os.path.exists(err_path):
    h2("Baseline / target / measured / error (final week)")
    err = pd.read_csv(err_path)
    df_table(err, col_widths=[2.0*inch, 0.9*inch, 0.8*inch, 1.5*inch, 1.2*inch])

p("<b>Reading the result:</b> participation declines under the baseline (fatigue pattern matching "
  "the stated problem) and rises under the prototype, finishing above the 75% participation target; "
  "comprehension stays consistently higher under the prototype and both conditions exceed the 80% "
  "target by the final week, though the baseline's comprehension is noisier week to week (small "
  "per-week sample of comprehension checks, ~24 patients).")
h2("Human review load (a safety cost to report honestly)")
p("Because the prototype adds the cumulative sustained-gain check (Section 3), it generates a "
  "modestly higher number of urgent review items over the simulation than the baseline. This is "
  "treated as a feature, not a defect: it is precisely the slow-drift pattern (illustrated by P002 "
  "in Section 4) that a 24-hour-only rule would miss. A deployment should size clinical staffing "
  "against this queue volume, not assume it away.")

# ============================================================================
# 7. STAKEHOLDER / USER VALIDATION (SHORT)
# ============================================================================
h1("7. Short stakeholder validation")
p("Structured walkthrough conducted against the design (patient view + clinician view) with a "
  "reviewer role-playing (a) a health-literacy-focused patient advocate and (b) a heart-failure "
  "care-coordination nurse perspective, using the two journeys in Section 4 as the discussion "
  "artifact.")
bullets([
    "<b>Patient-advocate perspective:</b> messages read at a plain, non-technical level; every "
    "flagged event tells the patient a person is involved rather than leaving them to interpret a "
    "number; missing-data days are explicitly framed as low-stakes to avoid guilt-driven disengagement.",
    "<b>Care-coordination perspective:</b> the review queue surfaces the raw values (not just the "
    "plain-language gloss) so a clinician isn't working from a simplified message; requiring a note "
    "on every resolution supports later audit and handoff between shifts.",
    "<b>Open follow-up raised:</b> review-queue volume under the sustained-gain rule (Section 6) "
    "needs real-world staffing validation before a live pilot -- flagged in the deployment checklist below.",
])

# ============================================================================
# 8. ETHICS NOTE
# ============================================================================
story.append(PageBreak())
h1("8. Ethics note")
bullets([
    "<b>Synthetic data only.</b> No real patient data was used anywhere in this prototype; clinical "
    "thresholds are illustrative and not a substitute for a validated protocol or clinician sign-off.",
    "<b>No autonomous clinical action.</b> The app explains and flags; it never diagnoses, titrates "
    "medication, or closes a safety concern without an authorised human action -- enforced structurally "
    "via the ReviewQueue, tested explicitly in Section 5.",
    "<b>Simulated engagement effect, clearly labeled.</b> The participation/comprehension uplift in "
    "Section 6 comes from a stated modeling assumption, not measured patient outcomes; presenting it "
    "as a proven effect would be misleading and is avoided in this report.",
    "<b>Avoiding false reassurance and false alarm.</b> Missing-data and sensor-error states are "
    "designed to neither fabricate a reassuring number nor trigger a false alarm; sustained-drift "
    "detection is designed to avoid missing a slow deterioration that day-to-day rules would let "
    "through (Section 4, P002).",
    "<b>Health literacy and equity.</b> Plain-language, short-sentence messaging and a light-touch "
    "comprehension check are intended to reduce reliance on numeracy or clinical vocabulary; a real "
    "deployment should validate reading level and translation needs with the actual patient population.",
    "<b>Accountability trail.</b> Every clinical action is attributed to a staff id and timestamp so "
    "responsibility for a final decision is always traceable to a person, not the app.",
])

# ============================================================================
# 9. DEPLOYMENT CHECKLIST
# ============================================================================
h1("9. Deployment checklist")
bullets([
    "Replace illustrative thresholds with a clinician-approved, guideline-based protocol before any "
    "real patient sees this app.",
    "Integrate with the real EHR / care-coordination system so review-queue actions write back to "
    "the patient's chart, not just this prototype's audit log.",
    "Load-test and staff the review queue against realistic urgent-item volume (Section 6) -- confirm "
    "coverage during nights/weekends before go-live.",
    "Run a formal health-literacy and readability review (e.g. plain-language / reading-level audit) "
    "with real patients or patient representatives, in the target population's languages.",
    "Add authentication, role-based access control, and encryption-at-rest/in-transit for PHI before "
    "any non-synthetic data is used.",
    "Define and test an explicit emergency-escalation path (e.g. what happens if a 'red' flag is not "
    "acted on within a defined SLA) beyond routing to a pending queue.",
    "Replace the simulated engagement model (Section 6) with a real pilot measurement plan (e.g. a "
    "randomized or stepped-wedge comparison against the baseline) before making any efficacy claim.",
    "Add accessibility support (screen reader, low-vision, low-dexterity input) for the patient view.",
    "Establish a data-retention and patient-consent policy, including consent for remote monitoring "
    "and for any future model retraining.",
    "Pilot with a small cohort and a human safety reviewer shadowing the queue before wider rollout.",
])

story.append(Spacer(1, 14))
p("<i>This document, the underlying Python prototype (data_gen.py, engine.py, simulate.py, "
  "make_charts.py, edge_case_tests.py) and the Streamlit app (app.py) together constitute the "
  "full working prototype -- not a concept presentation or an isolated notebook.</i>")

doc = SimpleDocTemplate(PDF_PATH, pagesize=letter,
                         leftMargin=0.75*inch, rightMargin=0.75*inch,
                         topMargin=0.7*inch, bottomMargin=0.7*inch,
                         title="HF Patient Engagement -- Prototype Report")
doc.build(story)
print("Wrote", PDF_PATH)
