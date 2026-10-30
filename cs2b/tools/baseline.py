"""Verify the selected raw inputs and record the configured cleaning baseline.

Run from cs2b: python tools/baseline.py
Use --write-outputs to generate preliminary panel and reports. No downloads or manual evidence edits.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import acquire, paths, pipeline, reconcile, report  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-outputs", action="store_true",
                        help="Also generate preliminary panel and coverage/triage reports")
    args = parser.parse_args()
    params = paths.load_params(ROOT)
    dirs = paths.release_dirs(params, ROOT)
    rules = pipeline.configured_rules(params)
    if not params["data"]["use_fixture"]:
        manifest = ROOT / "data" / "manifest.json"
        entries = json.loads(manifest.read_text())
        recorded = {str((ROOT / e["path"]).resolve()) for e in entries}
        missing = [str(d.with_suffix(".zip")) for d in dirs.values()
                   if str(d.with_suffix(".zip").resolve()) not in recorded]
        if missing:
            raise ValueError(f"Selected release ZIPs missing from manifest: {missing}")
        bad = acquire.verify_manifest(manifest, root=ROOT)
        if bad:
            raise ValueError(f"Manifest verification failed: {bad}")
        wrong_sizes = [e["path"] for e in entries
                       if (ROOT / e["path"]).stat().st_size != e["bytes"]]
        if wrong_sizes:
            raise ValueError(f"Manifest size mismatch: {wrong_sizes}")
        print(f"Manifest verified: {len(entries)} ZIP files (SHA-256 and size)", flush=True)
    result = pipeline.run_baseline(dirs, float(params["reconcile"]["tolerance"]), rules=rules,
                                   **paths.source_evidence_paths(params, ROOT))
    summary = {
        "releases": list(dirs),
        "use_fixture": params["data"]["use_fixture"],
        "tolerance": params["reconcile"]["tolerance"],
        "rules": result["log"]["rule"].tolist(),
        "filings_in_sub": len(result["sub"]),
        "soi_rows": len(result["soi"]),
        "current_holdings_before_cleaning": int(result["holdings"]["is_current"].sum()),
        **reconcile.coverage(result["rec"], result["sub"]),
    }
    output = ROOT / params["outputs"]["reports"]
    output.mkdir(parents=True, exist_ok=True)
    (output / "baseline.json").write_text(json.dumps(summary, indent=2) + "\n")
    result["rec"].to_csv(output / "baseline_reconciliation.csv", index=False)
    result["diag"].to_csv(output / "baseline_diagnostics.csv", index=False)
    print(json.dumps(summary, indent=2))
    if args.write_outputs:
        report.write_outputs(result["kept"], result["rec"], result["diag"],
                             result["log"], ROOT, params, sub=result["sub"])
        print("Preliminary panel and reports written; inspect coverage.json for triage completeness.")


if __name__ == "__main__":
    main()
