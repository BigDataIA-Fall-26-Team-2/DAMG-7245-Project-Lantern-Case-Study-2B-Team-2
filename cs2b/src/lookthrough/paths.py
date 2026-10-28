"""Find the repository root and read params.yaml."""
from pathlib import Path
import re
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


def release_dirs(params: dict, root=None) -> dict:
    """Resolve the baseline input scope; an explicit releases list takes precedence.

    List order is intentional: a filing repeated in several releases is taken
    from the last listed release. Fixture mode always selects only the fixture.
    This resolves local paths; it never downloads or discovers new releases.
    """
    root = Path(root) if root else repo_root()
    if params["data"]["use_fixture"]:
        return {FIXTURE_RELEASE: release_dir(params, root)}
    releases = params.get("releases", [params.get("release")])
    if not isinstance(releases, list) or not releases:
        raise ValueError("releases must be a non-empty list; omit it to use release")
    if any(not isinstance(r, str) or not re.fullmatch(
            r"\d{4}(?:_(?:0[1-9]|1[0-2])|q[1-4])", r) for r in releases):
        raise ValueError("release IDs must have form YYYY_MM or YYYYqN")
    if len(set(releases)) != len(releases):
        raise ValueError("releases must not contain duplicates")
    raw = root / params["data"]["raw_dir"]
    return {r: raw / f"{r}_bdc" for r in releases}
