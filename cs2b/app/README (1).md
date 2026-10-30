# LANTERN app

A backend (FastAPI) and a frontend (Streamlit) laid out in pipeline order:
1 Source, 2 Read, 3 Clean, 4 Compare, 5 Final list, 6 Check by hand.
The user picks months, cleaning rules and tolerance, runs, and sees what changed
against the team default. Runs never write to outputs/ or reports/.

Run from inside cs2b, after `dvc pull`:

    pip install fastapi uvicorn "streamlit>=1.40" requests python-multipart
    uvicorn app.api:app --port 8000
    streamlit run app/ui.py        (second terminal)

For the team's 3 months the backend starts from outputs/work (seconds). Other
month choices read the raw SEC files once (a few minutes), then run in seconds.
