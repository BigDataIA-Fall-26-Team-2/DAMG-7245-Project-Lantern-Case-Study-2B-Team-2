# LANTERN app

A backend (FastAPI) and a frontend (Streamlit) laid out in pipeline order:
1 Source, 2 Read, 3 Clean, 4 Compare, 5 Final list, 6 Check by hand.
The user picks months, cleaning rules and tolerance, runs, and sees what changed
against the team default. Runs never write to outputs/ or reports/.

Run from inside cs2b, after `dvc pull`:

    pip install -r requirements.txt
    uvicorn app.api:app --port 8000
    streamlit run app/ui.py        (second terminal)

For the team's 3 months the backend starts from outputs/work (seconds). Other
month choices read the raw SEC files once (a few minutes), then run in seconds.

Review safeguards:
- Raw parsing applies the configured source evidence, just like the DVC parse stage.
- Saved triage is checked against each run's totals. Incomplete/stale notes remain
  visible as historical evidence but do not count as reviewed explanations.
- Panel and search exports retain source classification, fact IDs and snapshot hashes.
- Principal currency/units are not verified (some amounts are equity quantities).
  Prices, aggregated principal and the price-based watch list are withheld until
  that evidence is available. Fair values remain USD; raw principal is not labelled USD.
