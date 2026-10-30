"""Run teaching notebooks in an isolated copy; never overwrite submission evidence.

Usage: python tools/run_notebooks.py
The scratch directory is retained for inspection and printed before execution.
Use `dvc repro` to regenerate the real multi-release submission pipeline.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def scratch_copy(root):
    destination = Path(tempfile.mkdtemp(prefix="lantern-notebooks-")) / "cs2b"
    # Copy files, not symlinks/hard links to writable submission artifacts.
    shutil.copytree(root, destination, ignore=shutil.ignore_patterns(
        ".git", ".dvc", ".venv", "__pycache__", ".pytest_cache"))
    import yaml
    params_path = destination / "params.yaml"
    params = yaml.safe_load(params_path.read_text())
    # Teaching notebooks demonstrate the fallback release, not the full pipeline.
    params["releases"] = [params["release"]]
    params_path.write_text(yaml.safe_dump(params, sort_keys=False))
    (destination / ".notebook-scratch").write_text("Teaching outputs only; not submission evidence.\n")
    return destination


def main():
    scratch = scratch_copy(ROOT)
    print(f"Scratch copy: {scratch}\nSubmission files remain untouched.", flush=True)
    fails = 0
    notebooks = sorted((scratch / "notebooks").glob("*.ipynb"))
    for nb in notebooks:
        cells = [c for c in json.loads(nb.read_text())["cells"] if c["cell_type"] == "code"]
        src = "\n\n".join("".join(c["source"]) for c in cells)
        bad = [line for line in src.splitlines() if line.lstrip().startswith(("%", "!"))]
        result = subprocess.run([sys.executable, "-c", src], cwd=scratch / "notebooks",
                                capture_output=True, text=True,
                                env=dict(os.environ, MPLBACKEND="Agg"))
        ok = result.returncode == 0 and not bad
        fails += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {nb.name}", flush=True)
        if not ok:
            print(result.stderr[-2500:], bad)
    print(f"{len(notebooks) - fails}/{len(notebooks)} notebooks passed. Scratch outputs: {scratch}")
    return int(bool(fails))


if __name__ == "__main__":
    sys.exit(main())
