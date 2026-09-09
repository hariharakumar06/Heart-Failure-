# Heart-Failure Patient-Engagement Feedback App -- Prototype

Synthetic-data prototype: explains recovery progress in plain language, keeps
clinicians/authorised staff in control of every actionable decision, and
demonstrates sustained participation/comprehension over an 8-week simulation.

## Run it
```bash
pip install streamlit pandas numpy matplotlib reportlab
cd src && python3 simulate.py        # regenerate dataset + 8-week metrics -> ../outputs
cd .. && python3 -m streamlit run app.py    # launch the patient/clinician app
```
Report is pre-built at `outputs/HF_Patient_Engagement_Report.pdf`
(regenerate with `python3 report/generate_report.py` after `simulate.py`).

## Structure
- `src/data_gen.py`      synthetic monitoring/goals/education/adherence data + edge cases
- `src/engine.py`        baseline vs prototype feedback engine + clinician ReviewQueue (the safety gate)
- `src/simulate.py`      8-week baseline-vs-prototype simulation
- `src/make_charts.py`   participation/comprehension charts
- `src/edge_case_tests.py`  5 automated failure-state tests (`python3 edge_case_tests.py`)
- `app.py`               Streamlit app (patient view, clinician view, comparison, metrics)
- `outputs/`             generated CSVs, charts, and the PDF report
- `report/generate_report.py`  builds `outputs/HF_Patient_Engagement_Report.pdf`
