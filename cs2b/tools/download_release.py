import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lookthrough import acquire, paths

P = paths.load_params(ROOT)
raw = ROOT / P["data"]["raw_dir"]
base = P["sec"]["base_url"]

rows = []
for rel in P["releases"]:
    z = raw / f"{rel}_bdc.zip"
    if not z.exists():
        z = acquire.download_release(rel, raw, P["sec"]["user_agent"], base)
    acquire.unzip_release(z, raw, rel)
    rows.append({
        "path": z.resolve().relative_to(ROOT.resolve()).as_posix(),
        "url": acquire.release_url(rel, base),
        "bytes": z.stat().st_size,
        "sha256": acquire.sha256_file(z),
        "recorded": dt.date.today().isoformat(),
    })

mpath = ROOT / "data" / "manifest.json"
mpath.write_text(json.dumps(rows, indent=2))
bad = acquire.verify_manifest(mpath, root=ROOT)

for r in rows:
    print(r["path"], r["bytes"], r["sha256"])
print("mismatches:", len(bad))