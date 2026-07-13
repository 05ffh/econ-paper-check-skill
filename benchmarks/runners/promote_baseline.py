"""
promote_baseline.py — Phase F.4 rc.x → 正式版 baseline 升迁骨架

用法:
  python promote_baseline.py --from-run 20260713-phaseD-perf \
                             --target-version v1.7.0 \
                             [--source-tag v1.7.0-rc.1] \
                             [--dry-run]

行为:
  1. 找到 --from-run 目录下所有 *.metrics.json
  2. 逐一 schema 校验通过后, 拷到 benchmarks/baselines/<target-version>/
  3. 生成 baselines/<target-version>/README.md (记录来源 run/tag/sha/时间)
  4. 生成 baselines/<target-version>/BASELINE_MANIFEST.yaml
     (逐 sample 记录 sha256 + 关键 metric 值供后续同比)
  5. 触发 release_gate_check 对新 baseline 做最终校验

升迁前置守卫 (硬):
  - target-version 不能已存在
  - 所有 metrics 必须 schema 通过
  - 所有 metrics 必须 release_gate 通过
  - Ark 真调样本必须有 performance.repeat_count >= 3
  - dry-run 模式不写文件, 只报告能不能升
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINES_DIR = REPO_ROOT / "benchmarks" / "baselines"
LIB_DIR = REPO_ROOT / "benchmarks" / "lib"
RUNNERS_DIR = REPO_ROOT / "benchmarks" / "runners"

SEMVER_RE = re.compile(r"^v?\d+\.\d+\.\d+(-[\w.-]+)?$")


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-run", required=True, help="benchmarks/runs/<run_id> 的 run_id")
    ap.add_argument("--target-version", required=True, help="e.g. v1.7.0")
    ap.add_argument("--source-tag", help="e.g. v1.7.0-rc.1")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="覆盖已有 target-version")
    args = ap.parse_args()

    if not SEMVER_RE.match(args.target_version):
        print(f"ERROR: --target-version '{args.target_version}' 不是合法 semver", file=sys.stderr)
        return 2

    run_dir = REPO_ROOT / "benchmarks" / "runs" / args.from_run
    if not run_dir.is_dir():
        print(f"ERROR: run 目录不存在: {run_dir}", file=sys.stderr)
        return 2

    target_dir = BASELINES_DIR / args.target_version
    if target_dir.exists() and not args.force:
        print(f"ERROR: baseline 已存在: {target_dir}. 用 --force 覆盖.", file=sys.stderr)
        return 2

    metrics_files = sorted(run_dir.glob("*.metrics.json"))
    if not metrics_files:
        print(f"ERROR: {run_dir} 无 *.metrics.json", file=sys.stderr)
        return 2

    print(f"Promote source: {run_dir}")
    print(f"Target baseline: {target_dir}")
    print(f"Source tag:      {args.source_tag or '(none)'}")
    print(f"metrics count:   {len(metrics_files)}")
    print()

    # 前置守卫 1: schema
    print("[1/4] schema_validator ... ", end="")
    sv = subprocess.run(
        ["python3", str(LIB_DIR / "schema_validator.py"), "--all"],
        capture_output=True, text=True
    )
    if sv.returncode != 0:
        print("❌")
        print(sv.stdout[-400:])
        return 3
    print("✅")

    # 前置守卫 2: release_gate
    print("[2/4] release_gate_check ... ", end="")
    rg = subprocess.run(
        ["python3", str(RUNNERS_DIR / "release_gate_check.py"),
         "--run", str(run_dir), "--allow-baseline-none"],
        capture_output=True, text=True
    )
    if rg.returncode != 0:
        print("❌")
        print(rg.stdout[-400:])
        return 3
    print("✅")

    # 前置守卫 3: 真调样本 repeat_count 检查
    print("[3/4] performance.repeat_count check ... ", end="")
    perf_issues = []
    for mf in metrics_files:
        m = json.loads(mf.read_text(encoding="utf-8"))
        # 只对 real_manual run_kind 校验
        if m.get("run_metadata", {}).get("run_kind") == "real_manual":
            rc = m.get("performance", {}).get("repeat_count", 0)
            if rc < 3:
                perf_issues.append(f"{mf.name}: repeat_count={rc} < 3")
    if perf_issues:
        print("❌")
        for issue in perf_issues:
            print(f"  {issue}")
        return 3
    print("✅")

    # 生成 manifest
    print("[4/4] building baseline manifest ...")
    import yaml
    manifest = {
        "baseline_version": args.target_version,
        "source_run_id": args.from_run,
        "source_tag": args.source_tag,
        "promoted_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "promoted_from_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT)
        ).decode().strip(),
        "samples": [],
    }

    for mf in metrics_files:
        m = json.loads(mf.read_text(encoding="utf-8"))
        rm = m.get("run_metadata", {})
        sha = _sha256(mf)
        manifest["samples"].append({
            "sample_id": rm.get("sample_id"),
            "metrics_file": mf.name,
            "metrics_sha256": sha,
            "run_kind": rm.get("run_kind"),
            "skill_version": rm.get("skill_version"),
            "ark_used": rm.get("ark_provider_used", False),
            "p50_seconds": m.get("performance", {}).get("total_seconds_p50"),
            "p95_seconds": m.get("performance", {}).get("total_seconds_p95"),
            "repeat_count": m.get("performance", {}).get("repeat_count"),
            "vision_quality": m.get("vision_quality", {}).get("critical_cell_accuracy"),
        })

    if args.dry_run:
        print()
        print("=== DRY RUN · 不写文件 ===")
        print(f"would create {target_dir}")
        print(f"would copy {len(metrics_files)} metrics")
        print(json.dumps(manifest, ensure_ascii=False, indent=2)[:800])
        return 0

    # 执行升迁
    target_dir.mkdir(parents=True, exist_ok=True)
    for mf in metrics_files:
        shutil.copy2(mf, target_dir / mf.name)

    (target_dir / "BASELINE_MANIFEST.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    readme_lines = [
        f"# Baseline · {args.target_version}",
        "",
        f"- 升迁自 run: `{args.from_run}`",
        f"- 源 tag: `{args.source_tag or '(none)'}`",
        f"- 升迁时间: `{manifest['promoted_at']}`",
        f"- 升迁 commit: `{manifest['promoted_from_commit']}`",
        f"- Sample 数: {len(metrics_files)}",
        "",
        "## 关键性能",
        "",
        "| sample | run_kind | p50 (s) | p95 (s) | repeat | ark |",
        "|---|---|---|---|---|---|",
    ]
    for s in manifest["samples"]:
        readme_lines.append(
            f"| {s['sample_id']} | {s['run_kind']} | "
            f"{s['p50_seconds']} | {s['p95_seconds']} | "
            f"{s['repeat_count']} | {'✅' if s['ark_used'] else '⚪'} |"
        )
    (target_dir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

    print()
    print(f"✅ promoted → {target_dir.relative_to(REPO_ROOT)}")
    print(f"   samples: {len(metrics_files)}")
    print(f"   manifest: BASELINE_MANIFEST.yaml + README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
