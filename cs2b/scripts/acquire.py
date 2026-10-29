"""Stage 1 (acquire): verify data/raw against data/manifest.json.

Never downloads and never writes to data/raw (DVC owns data/raw through
data/raw.dvc). To download a release from scratch, use tools/download_release.py.
The pipeline runs the real release only, so it stops if data.use_fixture is true.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import acquire, paths

P = paths.load_params(ROOT)
if P["data"].get("use_fixture"):
    sys.exit("acquire: data.use_fixture is true. The dvc.yaml pipeline runs the "
             "real release only; set data.use_fixture: false (use the notebooks "
             "or tools/smoke_real.py for the fixture).")

manifest = ROOT / "data" / "manifest.json"
entries = json.loads(manifest.read_text())
bad = acquire.verify_manifest(manifest, root=ROOT)

reports = ROOT / P["outputs"]["reports"]
reports.mkdir(parents=True, exist_ok=True)
(reports / "manifest_check.json").write_text(
    json.dumps({"files_checked": len(entries), "mismatches": bad},
               indent=2, default=str) + "\n")
print(f"manifest: {len(entries)} files checked, {len(bad)} mismatches")
if bad:
    sys.exit(1)
