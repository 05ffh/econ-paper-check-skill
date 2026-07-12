"""
Schema validator for M4 benchmarks (v0.2).

Validates:
  - benchmarks/schema/*.schema.yaml themselves
  - metrics.json (runs/**)
  - expected.yaml (expected/**, fixtures/**)
  - sample_manifest.yaml (documents/**)

CLI:
    python benchmarks/lib/schema_validator.py --all
    python benchmarks/lib/schema_validator.py --metrics benchmarks/runs/xxx/metrics.json
    python benchmarks/lib/schema_validator.py --expected benchmarks/expected/S01.expected.yaml
    python benchmarks/lib/schema_validator.py --manifest benchmarks/documents/private_local_manifest/S01.manifest.yaml
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    from jsonschema import Draft202012Validator, ValidationError
except ImportError:
    print("ERROR: jsonschema not installed. Run:", file=sys.stderr)
    print("  pip install --break-system-packages jsonschema", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "benchmarks" / "schema"

_SCHEMA_MAP = {
    "metrics":  SCHEMA_DIR / "metrics.schema.yaml",
    "expected": SCHEMA_DIR / "expected.schema.yaml",
    "manifest": SCHEMA_DIR / "sample_manifest.schema.yaml",
}


def _load_yaml(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_json_or_yaml(p: Path) -> Any:
    if p.suffix in {".yaml", ".yml"}:
        return _load_yaml(p)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def load_schema(kind: str) -> dict:
    if kind not in _SCHEMA_MAP:
        raise ValueError(f"unknown schema kind: {kind}")
    return _load_yaml(_SCHEMA_MAP[kind])


def validate_file(kind: str, path: Path) -> list[str]:
    """Return list of error messages (empty = ok)."""
    schema = load_schema(kind)
    data = _load_json_or_yaml(path)
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for e in sorted(validator.iter_errors(data), key=lambda x: list(x.absolute_path)):
        loc = "/".join(str(x) for x in e.absolute_path) or "<root>"
        errors.append(f"{path}: {loc}: {e.message}")
    return errors


def discover_files() -> dict[str, list[Path]]:
    """Discover all files that should be validated."""
    root = REPO_ROOT / "benchmarks"
    result = {"metrics": [], "expected": [], "manifest": []}

    # metrics.json under runs/**
    for p in glob.glob(str(root / "runs" / "**" / "*.metrics.json"), recursive=True):
        result["metrics"].append(Path(p))
    # metrics.json under baselines/**
    for p in glob.glob(str(root / "baselines" / "**" / "*.metrics.json"), recursive=True):
        result["metrics"].append(Path(p))

    # expected.yaml
    for p in glob.glob(str(root / "expected" / "*.expected.yaml")):
        result["expected"].append(Path(p))
    for p in glob.glob(str(root / "fixtures" / "**" / "expected.yaml"), recursive=True):
        result["expected"].append(Path(p))

    # sample_manifest.yaml
    for p in glob.glob(str(root / "documents" / "**" / "*.manifest.yaml"), recursive=True):
        result["manifest"].append(Path(p))
    for p in glob.glob(str(root / "fixtures" / "**" / "manifest.yaml"), recursive=True):
        result["manifest"].append(Path(p))

    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="Validate all discovered files")
    ap.add_argument("--metrics", type=Path, help="Validate one metrics.json")
    ap.add_argument("--expected", type=Path, help="Validate one expected.yaml")
    ap.add_argument("--manifest", type=Path, help="Validate one sample_manifest.yaml")
    ap.add_argument("--schema-only", action="store_true", help="Sanity check schemas themselves")
    args = ap.parse_args()

    total_errors: list[str] = []

    # Schema sanity: load each schema file
    if args.schema_only or args.all:
        for kind, p in _SCHEMA_MAP.items():
            try:
                s = _load_yaml(p)
                Draft202012Validator.check_schema(s)
                print(f"[schema] {kind}: OK ({p.relative_to(REPO_ROOT)})")
            except Exception as e:
                total_errors.append(f"schema {kind}: {e}")

    if args.metrics:
        errs = validate_file("metrics", args.metrics)
        total_errors.extend(errs)
        print(f"[metrics] {args.metrics}: {'OK' if not errs else 'FAIL'}")

    if args.expected:
        errs = validate_file("expected", args.expected)
        total_errors.extend(errs)
        print(f"[expected] {args.expected}: {'OK' if not errs else 'FAIL'}")

    if args.manifest:
        errs = validate_file("manifest", args.manifest)
        total_errors.extend(errs)
        print(f"[manifest] {args.manifest}: {'OK' if not errs else 'FAIL'}")

    if args.all:
        found = discover_files()
        for kind, paths in found.items():
            for p in paths:
                errs = validate_file(kind, p)
                total_errors.extend(errs)
                status = "OK" if not errs else "FAIL"
                print(f"[{kind}] {p.relative_to(REPO_ROOT)}: {status}")
        counts = {k: len(v) for k, v in found.items()}
        print(f"\nDiscovered: {counts}")

    if total_errors:
        print("\n=== ERRORS ===")
        for e in total_errors:
            print(f"  - {e}")
        return 1
    print("\nAll validations passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
