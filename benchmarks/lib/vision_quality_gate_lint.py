"""
vision_quality_gate_lint.py — Phase F.2: 视觉 quality_gate 离线 false-positive/negative 检测

不消耗 Ark quota. 对已有的 vision_result.json (来自 Phase C/D 真调) 做多维度 sanity check.
用作 v1.7.0 及后续 vision baseline 的必跑守卫.

检测项目 (每项都会引发 exit_code=1 若失败):

  L01 · hard_gates=True 但 quality_score < 0.5      → 门禁矛盾
  L02 · hard_gates=True 但 table_preview 为空       → 空壳通过
  L03 · hard_gates=True 但 n_rows/n_cols 全为 0      → 尺寸零通过
  L04 · hard_gates=False 但 critical_field_score=1.0 → 关键字段满分却降级
  L05 · latency_ms > 60000                          → 单页 60s+ 需排查
  L06 · kb_a_evidence_eligible=True 但 quality < 0.6 → 低质量却作证据
  L07 · quota_used > quota_limit                    → quota 越界
  L08 · 同一 run 内 quality_score 方差 > 0.3         → 内一致性异常
  L09 · usage.total_tokens 缺失                      → 计费无法核算
  L10 · runtime_mode 不在白名单                       → mode 污染

用法:
  python vision_quality_gate_lint.py <vision_result.json>[, ...]
  python vision_quality_gate_lint.py --all-in benchmarks/runs/
"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ALLOWED_RUNTIME_MODES = {"basic", "enhanced", "test_stub"}
LATENCY_ALERT_MS = 60000
LOW_QUALITY_THRESHOLD = 0.6
STRICT_QUALITY_MIN_WHEN_GATE_PASS = 0.5


class LintFailure(Exception):
    pass


def _lint_evidence(idx: int, e: dict[str, Any]) -> list[str]:
    fails = []
    q = e.get("quality_profile") or {}
    tp = e.get("table_preview") or {}
    ke = e.get("kb_eligibility") or {}
    usage = e.get("usage") or {}
    prov = e.get("provenance") or {}

    gate = q.get("hard_gates_passed")
    qs = q.get("extraction_quality_score", 0.0) or 0.0
    cfs = q.get("critical_field_score", 0.0) or 0.0

    if gate is True and qs < STRICT_QUALITY_MIN_WHEN_GATE_PASS:
        fails.append(f"[L01] page {e.get('page_number')}: gates=True but quality={qs:.2f}")

    if gate is True and not tp:
        fails.append(f"[L02] page {e.get('page_number')}: gates=True but table_preview empty")

    if gate is True and (tp.get("n_rows", 0) == 0 or tp.get("n_cols", 0) == 0):
        fails.append(f"[L03] page {e.get('page_number')}: gates=True but n_rows={tp.get('n_rows')} n_cols={tp.get('n_cols')}")

    if gate is False and cfs >= 1.0:
        fails.append(f"[L04] page {e.get('page_number')}: gates=False but critical_field_score={cfs}")

    lat = e.get("latency_ms", 0) or 0
    if lat > LATENCY_ALERT_MS:
        fails.append(f"[L05] page {e.get('page_number')}: latency {lat}ms > {LATENCY_ALERT_MS}ms")

    if ke.get("kb_a_evidence_eligible") is True and qs < LOW_QUALITY_THRESHOLD:
        fails.append(f"[L06] page {e.get('page_number')}: kb_a_evidence_eligible=True but quality={qs:.2f}")

    ql, qu = e.get("quota_limit"), e.get("quota_used")
    if isinstance(ql, int) and isinstance(qu, int) and qu > ql:
        fails.append(f"[L07] page {e.get('page_number')}: quota_used {qu} > quota_limit {ql}")

    if not usage.get("total_tokens"):
        fails.append(f"[L09] page {e.get('page_number')}: usage.total_tokens missing")

    rmode = prov.get("runtime_mode")
    if rmode is not None and rmode not in ALLOWED_RUNTIME_MODES:
        fails.append(f"[L10] page {e.get('page_number')}: runtime_mode='{rmode}' not in whitelist")

    return fails


def lint_file(path: Path) -> tuple[list[str], list[str]]:
    """返回 (all_fails, notes)."""
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as exc:
        return ([f"FILE_LOAD_ERROR: {path}: {exc}"], [])

    all_fails = []
    notes = [f"file: {path.name} · provider={d.get('provider')} · available={d.get('available')} · evidences={len(d.get('evidences', []))}"]

    if not d.get("available"):
        # 未启用/未真调的空壳, 只做基础断言, 不做深度 lint
        notes.append("skip lint (provider not available)")
        return (all_fails, notes)

    evidences = d.get("evidences", [])

    # 单条 lint
    for i, e in enumerate(evidences):
        all_fails.extend(_lint_evidence(i, e))

    # 内一致性: L08
    good_scores = [
        (e.get("quality_profile") or {}).get("extraction_quality_score", 0.0)
        for e in evidences
        if (e.get("quality_profile") or {}).get("hard_gates_passed")
    ]
    if len(good_scores) >= 2:
        try:
            variance = statistics.pstdev(good_scores)
            if variance > 0.3:
                all_fails.append(f"[L08] cross-page quality variance {variance:.3f} > 0.3 (unstable)")
        except statistics.StatisticsError:
            pass

    return (all_fails, notes)


def main() -> int:
    ap = argparse.ArgumentParser(description="Vision quality_gate lint")
    ap.add_argument("targets", nargs="*", help="vision_result*.json paths")
    ap.add_argument("--all-in", type=str, help="scan directory for vision_result*.json")
    args = ap.parse_args()

    paths: list[Path] = []
    if args.all_in:
        root = Path(args.all_in)
        paths.extend(sorted(root.rglob("vision_result*.json")))
    paths.extend(Path(t) for t in args.targets)

    if not paths:
        print("no vision_result*.json found", file=sys.stderr)
        return 2

    total_fails = 0
    print("=" * 70)
    print("Vision Quality Gate Lint · Phase F.2 (offline, no Ark)")
    print("=" * 70)

    for p in paths:
        fails, notes = lint_file(p)
        for n in notes:
            print(f"  ℹ️  {n}")
        for f in fails:
            print(f"  ❌  {f}")
        total_fails += len(fails)
        if not fails and any("provider not available" not in n for n in notes):
            print("  ✅ clean")
        print()

    print("=" * 70)
    print(f"Total FAILS: {total_fails}")
    print("=" * 70)
    return 0 if total_fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
