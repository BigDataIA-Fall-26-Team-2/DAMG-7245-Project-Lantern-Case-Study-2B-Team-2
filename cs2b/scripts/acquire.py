"""Stage 1 (acquire): verify data/raw against data/manifest.json.

Never downloads and never writes to data/raw (DVC owns data/raw through
data/raw.dvc). To download a release from scratch, use tools/download_release.py.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import acquire

manifest = ROOT / "data" / "manifest.json"
entries = json.loads(manifest.read_text())
bad = acquire.verify_manifest(manifest, root=ROOT)

out = ROOT / "reports" / "manifest_check.json"
out.write_text(json.dumps({"files_checked": len(entries), "mismatches": bad},
                          indent=2, default=str) + "\n")
print(f"manifest: {len(entries)} files checked, {len(bad)} mismatches")
if bad:
    sys.exit(1)