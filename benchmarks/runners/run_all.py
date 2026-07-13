"""
run_all.py — Phase F.3 批量跑 R/Q/V + 全量汇总

用法:
  python run_all.py --run-id RUN_ID [--only R|Q|V|R,Q]
                    [--out-dir benchmarks/runs/RUN_ID]
                    [--skip-existing]

行为:
  1. 遍历 fixtures/{rules,kb_queries,vision_crops}/*/ 每个夹具
  2. 依次调用 run_single.py 生成 metrics.json
  3. 收尾:
     a) 全部 metrics.json schema_validator 验证
     b) release_gate_check 全 run 汇总
     c) 生成 batch_summary.md (通过/失败清单)

出口码:
  0 = 全 fixture 全 schema 全 release_gate 全绿
  1 = 有 fixture 跑失败
  2 = schema/release_gate 有 fail
"""
from __future__ import annotations
import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNERS_DIR = REPO_ROOT / "benchmarks" / "runners"
FIXTURES_DIR = REPO_ROOT / "benchmarks" / "fixtures"
LIB_DIR = REPO_ROOT / "benchmarks" / "lib"


def _collect_fixtures(only: set[str] | None) -> list[Path]:
    dirs = []
    if not only or "R" in only:
        dirs.extend(sorted((FIXTURES_DIR / "rules").glob("R*/")))
    if not only or "Q" in only:
        dirs.extend(sorted((FIXTURES_DIR / "kb_queries").glob("Q*/")))
    if not only or "V" in only:
        dirs.extend(sorted((FIXTURES_DIR / "vision_crops").glob("V*/")))
    return dirs


def _sample_id_from(dir_path: Path) -> str:
    return dir_path.name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True, help="run id (e.g. 20260713-phaseF-batch)")
    ap.add_argument("--only", type=str, help="filter e.g. R or R,Q")
    ap.add_argument("--out-dir", type=str, help="override out dir")
    ap.add_argument("--skip-existing", action="store_true", help="skip fixture if metrics exists")
    ap.add_argument("--continue-on-error", action="store_true", help="don't stop on first failure")
    args = ap.parse_args()

    only = set(x.strip() for x in args.only.split(",")) if args.only else None
    out_dir = Path(args.out_dir) if args.out_dir else REPO_ROOT / "benchmarks" / "runs" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    fixtures = _collect_fixtures(only)
    print(f"Discovered {len(fixtures)} fixtures. Run ID: {args.run_id}")
    print(f"Output dir: {out_dir}")
    print()

    passed, failed = [], []
    start = time.time()

    for fx_dir in fixtures:
        sample_id = _sample_id_from(fx_dir)
        metrics_path = out_dir / f"{sample_id}.metrics.json"

        if args.skip_existing and metrics_path.exists():
            print(f"  ⏭️  {sample_id} (existing, skipped)")
            passed.append(sample_id)
            continue

        # 找 mock_diagnostic_pass.json 如果存在 (R 系列)
        actual_json = fx_dir / "mock_diagnostic_pass.json"
        cmd = [
            "python3", str(RUNNERS_DIR / "run_single.py"),
            "--sample", str(fx_dir),
            "--run-id", args.run_id,
        ]
        if actual_json.exists():
            cmd.extend(["--actual-json", str(actual_json)])

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                failed.append((sample_id, r.stderr[:200]))
                print(f"  ❌ {sample_id}: exit {r.returncode}")
                if not args.continue_on_error:
                    print(r.stderr[:500])
                    break
            else:
                passed.append(sample_id)
                print(f"  ✅ {sample_id}")
        except subprocess.TimeoutExpired:
            failed.append((sample_id, "timeout"))
            print(f"  ⏱️  {sample_id}: timeout")
            if not args.continue_on_error:
                break

    elapsed = time.time() - start
    print()
    print(f"=== Fixture pass: {len(passed)}/{len(fixtures)} ({elapsed:.1f}s) ===")

    # 汇总 metrics validator
    print()
    print("=== Schema validator ===")
    sv = subprocess.run(
        ["python3", str(LIB_DIR / "schema_validator.py"), "--all"],
        capture_output=True, text=True
    )
    print(sv.stdout[-400:])
    schema_ok = sv.returncode == 0

    # 汇总 release_gate
    print()
    print("=== Release Gate ===")
    rg = subprocess.run(
        ["python3", str(RUNNERS_DIR / "release_gate_check.py"),
         "--run", str(out_dir), "--allow-baseline-none"],
        capture_output=True, text=True
    )
    print(rg.stdout[-400:])
    gate_ok = rg.returncode == 0

    # 写 batch_summary.md
    summary = out_dir / "batch_summary.md"
    summary.write_text(
        f"# Batch Summary · {args.run_id}\n\n"
        f"- fixtures: {len(fixtures)}\n"
        f"- passed:   {len(passed)}\n"
        f"- failed:   {len(failed)}\n"
        f"- schema:   {'✅' if schema_ok else '❌'}\n"
        f"- release_gate: {'✅' if gate_ok else '❌'}\n"
        f"- elapsed:  {elapsed:.1f}s\n\n"
        "## Passed\n\n"
        + "\n".join(f"- {s}" for s in passed) + "\n\n"
        + ("## Failed\n\n" + "\n".join(f"- {s}: {msg}" for s, msg in failed) if failed else ""),
        encoding="utf-8"
    )
    print(f"\nsummary → {summary.relative_to(REPO_ROOT)}")

    if failed:
        return 1
    if not (schema_ok and gate_ok):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
