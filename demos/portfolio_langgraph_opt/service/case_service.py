"""Case discovery and case-root path resolution."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml

_SERVICE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SERVICE_DIR.parent  # demos/portfolio_langgraph_opt
CASES_ROOT = (_PROJECT_ROOT / "src" / "cases").resolve()

_CASE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_case_id(case_id: str) -> bool:
    return bool(case_id and _CASE_ID_RE.match(case_id))


def case_root(case_id: str) -> Path:
    if not validate_case_id(case_id):
        raise ValueError(f"Invalid case_id format: {case_id}")
    return (CASES_ROOT / case_id).resolve()


def resolve_within_case(case_id: str, relpath: str) -> Path:
    """
    Resolve a relative path within a case root, preventing traversal.
    relpath must be a relative POSIX-like path such as "agents/foo.yaml".
    """
    if not validate_case_id(case_id):
        raise ValueError(f"Invalid case_id format: {case_id}")

    p = Path(relpath)
    if p.is_absolute():
        raise ValueError(f"Absolute paths not allowed: {relpath}")

    root = case_root(case_id)
    resolved = (root / p).resolve()

    try:
        resolved.relative_to(root)
    except ValueError as e:
        raise ValueError(f"Path traversal attempt: {relpath}") from e

    return resolved


def load_manifest(case_id: str) -> Optional[Dict]:
    """
    Load manifest.yaml for a given case_id.
    Returns None if not found.
    Raises ValueError if manifest is invalid.
    """
    if not validate_case_id(case_id):
        return None

    manifest_path = case_root(case_id) / "manifest.yaml"
    if not manifest_path.exists():
        return None

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Manifest must be a mapping/dict")

    required = ["case_id", "display_name", "description", "defaults"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Manifest missing required fields: {missing}")

    if data.get("case_id") != case_id:
        raise ValueError(f"Manifest case_id '{data.get('case_id')}' != directory '{case_id}'")

    if not isinstance(data.get("defaults"), dict):
        raise ValueError("Manifest.defaults must be a dict")

    return data


def discover_cases() -> List[str]:
    """Return sorted case_ids for directories under CASES_ROOT that contain a valid manifest.yaml."""
    if not CASES_ROOT.exists():
        return []

    case_ids: List[str] = []
    for d in CASES_ROOT.iterdir():
        if not d.is_dir():
            continue
        if d.name.startswith("_"):
            continue
        mp = d / "manifest.yaml"
        if not mp.exists():
            continue
        try:
            m = load_manifest(d.name)
            if m:
                case_ids.append(d.name)
        except Exception:
            continue

    return sorted(case_ids)


def list_cases() -> List[Dict]:
    """Return summaries for UI."""
    out: List[Dict] = []
    for cid in discover_cases():
        try:
            m = load_manifest(cid)
            if not m:
                continue
            out.append(
                {
                    "case_id": m["case_id"],
                    "display_name": m["display_name"],
                    "description": m.get("description", ""),
                    "version": m.get("version", "1.0.0"),
                }
            )
        except Exception:
            continue
    return out


def get_default_case_id() -> Optional[str]:
    """Read default from src/cases/_default.yaml."""
    dp = (CASES_ROOT / "_default.yaml").resolve()
    if not dp.exists():
        return None

    try:
        with open(dp, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None
        cid = data.get("default_case_id")
        if validate_case_id(cid):
            if (case_root(cid) / "manifest.yaml").exists():
                return cid
        return None
    except Exception:
        return None
