"""Download a release, record its provenance, verify it later."""
import datetime as dt
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import requests

BASE_URL = ("https://www.sec.gov/files/datastandardsinnovation/data/"
            "business-development-company-bdc-data-sets/")


def release_url(release: str, base_url: str = BASE_URL) -> str:
    """'2026_08' -> .../2026_08_bdc.zip ('2025q4' likewise)"""
    return f"{base_url}{release}_bdc.zip"


def download_release(release, dest_dir, user_agent,
                     base_url=BASE_URL) -> Path:
    if "@" not in user_agent or "Your Name" in user_agent:
        raise ValueError("set sec.user_agent: your name and email")
    dest = Path(dest_dir) / f"{release}_bdc.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = release_url(release, base_url)
    headers = {"User-Agent": user_agent}
    with requests.get(url, headers=headers, stream=True,
                      timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    return dest


def unzip_release(zip_path, raw_dir, release) -> Path:
    """Unpack into raw_dir/<release>_bdc, whatever the ZIP layout."""
    target = Path(raw_dir) / f"{release}_bdc"
    tmp = Path(raw_dir) / f".unzip_{release}"
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp)
    hits = [p for p in tmp.rglob("soi.tsv")
            if "__MACOSX" not in p.parts]
    if len(hits) != 1:
        raise FileNotFoundError(f"{len(hits)} soi.tsv files in ZIP")
    if not (hits[0].parent / "datasets" / "sub.tsv").exists():
        raise FileNotFoundError("datasets/sub.tsv not beside soi.tsv")
    shutil.rmtree(target, ignore_errors=True)
    shutil.move(str(hits[0].parent), str(target))
    shutil.rmtree(tmp, ignore_errors=True)
    return target


def sha256_file(path, block=1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(block), b""):
            h.update(b)
    return h.hexdigest()


def write_manifest(files, out_path, url=None, root=None) -> list:
    """Record size and SHA-256; paths relative to root if given."""
    today = dt.date.today().isoformat()
    rel = (lambda f: Path(f).resolve().relative_to(
        Path(root).resolve()).as_posix()) if root else (lambda f: Path(f).as_posix())
    rows = [{"path": rel(f), "url": url,
             "bytes": Path(f).stat().st_size,
             "sha256": sha256_file(f), "recorded": today}
            for f in files]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(rows, indent=2))
    return rows


def verify_manifest(manifest_path, root=None) -> list:
    """Entries whose file is missing or changed ([] = verified)."""
    bad = []
    for e in json.loads(Path(manifest_path).read_text()):
        p = Path(e["path"])
        if root and not p.is_absolute():
            p = Path(root) / p
        if not p.exists() or sha256_file(p) != e["sha256"]:
            bad.append(e["path"])
    return bad
