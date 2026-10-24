"""Find the repository root and read params.yaml."""
from pathlib import Path
import yaml

FIXTURE_RELEASE = "2026_08"   # the synthetic fixture mimics this release's layout


def repo_root(start=None) -> Path:
    here = Path(start or Path.cwd()).resolve()
    for p in [here, *here.parents]:
        if (p / "params.yaml").exists():
            return p
    raise FileNotFoundError("params.yaml not found: run from inside the lantern-lab2b repository")


def load_params(root=None) -> dict:
    root = Path(root) if root else repo_root()
    with open(root / "params.yaml") as fh:
        return yaml.safe_load(fh)


def release_dir(params: dict, root=None) -> Path:
    """Folder holding soi.tsv and datasets/ for the active release (fixture or real)."""
    root = Path(root) if root else repo_root()
    if params["data"]["use_fixture"]:
        return root / params["data"]["fixture_dir"] / f"{FIXTURE_RELEASE}_bdc"
    return root / params["data"]["raw_dir"] / f"{params['release']}_bdc"
