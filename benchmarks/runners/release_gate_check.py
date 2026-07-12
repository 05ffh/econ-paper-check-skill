"""
Release Gate Check (M4 v0.2).

Iterates through candidate run metrics.json files and applies red/yellow/green
gates from plans/M4_RELEASE_GATE.md.

Exit codes:
  0 = all green
  1 = red gate hit (release blocked)
  2 = yellow gate hit only, non-strict mode

Usage:
  python benchmarks/runners/release_gate_check.py \
      --run benchmarks/runs/20260713-rc1 \
      [--baseline benchmarks/baselines/v1.7.0-rc.1] \
      [--strict] \
      [--allow-baseline-none]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

RED_MSG_TEMPLATE = "🟥 RED  {sample}: {reason}"
YEL_MSG_TEMPLATE = "🟨 YEL  {sample}: {reason}"
GRN_MSG_TEMPLATE = "🟩 OK   {sample}"


def _load_metrics(dir_: Path) -> dict[str, dict]:
    out = {}
    for p in dir_.glob("*.metrics.json"):
        with open(p, "r", encoding="utf-8") as f:
            out[p.stem.split(".")[0]] = json.load(f)
    return out


def check_sample(sample_id: str, m: dict) -> tuple[list[str], list[str]]:
    """Return (red_reasons, yellow_reasons)."""
    red: list[str] = []
    yellow: list[str] = []

    jq = m.get("judgment_quality", {})
    ka = m.get("kb_a_quality", {})
    vq = m.get("vision_quality", {})

    # 1.1 judgment red lines
    if jq.get("forbidden_issue_count", 0) > 0:
        red.append(f"forbidden_issue_count={jq['forbidden_issue_count']} > 0")
    if jq.get("false_red_count", 0) > 0:
        red.append(f"false_red_count={jq['false_red_count']} > 0")
    # 1.1 evidence completeness (red issues)
    ecr = jq.get("evidence_completeness_rate")
    if ecr is not None and ecr < 1.0:
        red.append(f"evidence_completeness_rate={ecr} < 1.0")
    # KB-A red support
    if ka.get("unsupported_red_count", 0) > 0:
        red.append(f"unsupported_red_count={ka['unsupported_red_count']} > 0")

    # 1.2 vision red lines
    if vq.get("visual_false_red_count", 0) > 0:
        red.append(f"visual_false_red_count={vq['visual_false_red_count']} > 0")
    if vq.get("quality_gate_false_pass_count", 0) > 0:
        red.append(f"quality_gate_false_pass_count={vq['quality_gate_false_pass_count']} > 0")

    # 1.3 anchor recall red line
    ar = jq.get("anchor_recall")
    if ar is not None and ar < 1.0:
        # anchor_recall < 1 means a must_hit is missing
        # High confidence anchor lost is RED per §10.1 (须由 diff_report 判定)
        # 这里的粗糙判定: recall < 1 一律红灯
        red.append(f"anchor_recall={ar} < 1.0 (any anchor missing → red)")

    # 2 yellow soft gates (perf, kb-b variance, etc.)
    # 首版无 baseline，先只做单点软阈值:
    # 具体阈值需要在 compare_run 中做对比，这里保留字段位

    return red, yellow


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--baseline", type=Path)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--allow-baseline-none", action="store_true")
    ap.add_argument("--out", type=Path,
                    help="Output release_gate_report.md; default: run/release_gate_report.md")
    args = ap.parse_args()

    if not args.run.is_dir():
        print(f"ERROR: run dir not found: {args.run}", file=sys.stderr)
        return 1

    args.run = args.run.resolve()
    if args.baseline:
        args.baseline = args.baseline.resolve()

    if not args.baseline and not args.allow_baseline_none:
        print("ERROR: --baseline required unless --allow-baseline-none is set", file=sys.stderr)
        return 1

    metrics = _load_metrics(args.run)
    if not metrics:
        print(f"ERROR: no *.metrics.json under {args.run}", file=sys.stderr)
        return 1

    lines = [f"# Release Gate Report",
             f"",
             f"- Run:      `{args.run.relative_to(REPO_ROOT)}`",
             f"- Baseline: `{args.baseline.relative_to(REPO_ROOT) if args.baseline else '(none)'}`",
             f"- Strict:   {args.strict}",
             f"",
             f"## Per-sample checks",
             f""]

    total_red = 0
    total_yel = 0
    for sid, m in sorted(metrics.items()):
        red, yel = check_sample(sid, m)
        total_red += len(red)
        total_yel += len(yel)
        if not red and not yel:
            lines.append(GRN_MSG_TEMPLATE.format(sample=sid))
        else:
            for r in red:
                lines.append(RED_MSG_TEMPLATE.format(sample=sid, reason=r))
            for y in yel:
                lines.append(YEL_MSG_TEMPLATE.format(sample=sid, reason=y))

    lines.append("")
    lines.append(f"## Summary")
    lines.append(f"- red total:    {total_red}")
    lines.append(f"- yellow total: {total_yel}")

    out = args.out or (args.run / "release_gate_report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {out.relative_to(REPO_ROOT)}")

    if total_red > 0:
        return 1
    if total_yel > 0 and args.strict:
        return 1
    if total_yel > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
