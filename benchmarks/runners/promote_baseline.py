"""
Baseline promotion tool (M4 v0.2).

- Refuses to overwrite existing baseline unless --force-approved
- Requires --approved-by, --change-reason
- Copies candidate metrics.json/canonical_result_json_sha256 references
- Writes APPROVAL.yaml with six_questions template
- Sets files to read-only (chmod 444) after copy
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ts() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _lock_readonly(dir_: Path) -> None:
    for p in dir_.rglob("*"):
        if p.is_file():
            try:
                p.chmod(0o444)
            except PermissionError:
                pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", type=Path, required=True,
                    help="benchmarks/runs/{run_id}/ directory")
    ap.add_argument("--to", dest="baseline_id", type=str, required=True,
                    help="baseline id, e.g. v1.7.0-rc.1")
    ap.add_argument("--approved-by", type=str, required=True)
    ap.add_argument("--change-reason", type=str, required=True)
    ap.add_argument("--six-questions", type=Path,
                    help="Optional path to pre-filled six_questions.yaml")
    ap.add_argument("--force-approved", action="store_true",
                    help="Overwrite existing baseline (dangerous)")
    args = ap.parse_args()

    src = args.src.resolve()
    if not src.is_dir():
        print(f"ERROR: source dir not found: {src}", file=sys.stderr)
        return 1

    dst = REPO_ROOT / "benchmarks" / "baselines" / args.baseline_id
    if dst.exists() and not args.force_approved:
        print(f"ERROR: baseline exists: {dst}", file=sys.stderr)
        print("  Use --force-approved only after human review + CHANGELOG record.", file=sys.stderr)
        return 1

    if dst.exists() and args.force_approved:
        # unlock ro so we can overwrite
        for p in dst.rglob("*"):
            if p.is_file():
                try:
                    p.chmod(0o644)
                except PermissionError:
                    pass
        shutil.rmtree(dst)

    dst.mkdir(parents=True, exist_ok=False)

    # Copy metrics/canonical files (not full artifacts dir)
    kept = []
    for p in src.iterdir():
        if p.name.endswith(".metrics.json") or p.name.endswith(".canonical_result.json"):
            shutil.copy2(p, dst / p.name)
            kept.append(p.name)

    if not kept:
        print(f"ERROR: no *.metrics.json / *.canonical_result.json under {src}", file=sys.stderr)
        return 1

    # Collect dataset_version + skill_version + commit from first metrics.json
    first_metrics = next((p for p in dst.iterdir() if p.name.endswith(".metrics.json")), None)
    dataset_version = None
    skill_version = None
    commit_sha = None
    if first_metrics:
        with open(first_metrics, "r", encoding="utf-8") as f:
            m = json.load(f)
        rm = m.get("run_metadata", {})
        dataset_version = rm.get("dataset_version")
        skill_version = rm.get("skill_version")
        commit_sha = rm.get("commit_sha")

    six_q_defaults = {
        "q1_why_change": args.change_reason,
        "q2_is_it_correct": "TODO: fill by approver",
        "q3_who_approved": args.approved_by,
        "q4_what_changed": ["TODO: enumerate diffs"],
        "q5_impacts_changelog": True,
        "q6_impacts_version": False,
    }
    if args.six_questions:
        with open(args.six_questions, "r", encoding="utf-8") as f:
            six_q_defaults.update(yaml.safe_load(f) or {})

    approval = {
        "baseline_id": args.baseline_id,
        "approved_by": args.approved_by,
        "approved_at": _ts(),
        "change_reason": args.change_reason,
        "source_run_dir": src.relative_to(REPO_ROOT).as_posix(),
        "dataset_version": dataset_version,
        "skill_version": skill_version,
        "commit_sha": commit_sha,
        "kept_files": sorted(kept),
        "six_questions": six_q_defaults,
    }
    approval_path = dst / "APPROVAL.yaml"
    with open(approval_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(approval, f, sort_keys=False, allow_unicode=True)

    _lock_readonly(dst)

    print(f"promoted -> {dst.relative_to(REPO_ROOT)}")
    print(f"  files: {sorted(kept)}")
    print(f"  approval: {approval_path.relative_to(REPO_ROOT)}")
    print(f"  chmod 444 applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
