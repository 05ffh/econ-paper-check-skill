"""
Compare a candidate run against a baseline (M4 v0.2).

Outputs diff_report.json with categorized diffs:
  REGRESSION / INTENDED_IMPROVEMENT / EXPECTED_VARIANCE
  / DATASET_CHANGE / ENVIRONMENT_CHANGE / NEEDS_REVIEW
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from benchmarks.lib.fingerprint import diff_fingerprint_sets, is_valid

REPO_ROOT = Path(__file__).resolve().parents[2]

REGRESSION = "REGRESSION"
INTENDED_IMPROVEMENT = "INTENDED_IMPROVEMENT"
EXPECTED_VARIANCE = "EXPECTED_VARIANCE"
DATASET_CHANGE = "DATASET_CHANGE"
ENVIRONMENT_CHANGE = "ENVIRONMENT_CHANGE"
NEEDS_REVIEW = "NEEDS_REVIEW"


def _load_metrics(dir_: Path) -> dict[str, dict]:
    result = {}
    for p in dir_.glob("*.metrics.json"):
        with open(p, "r", encoding="utf-8") as f:
            m = json.load(f)
        sid = m.get("run_metadata", {}).get("sample_id") or p.stem.split(".")[0]
        result[sid] = m
    return result


def _perf_pct_change(baseline: float, candidate: float) -> float | None:
    if baseline is None or baseline == 0:
        return None
    return (candidate - baseline) / baseline


def compare_sample(base: dict, cand: dict) -> dict:
    """Compare one sample: fingerprints + quality + perf + env."""
    findings = []

    # ---- fingerprint set diff ----
    b_fps = set(base.get("judgment_fingerprints") or [])
    c_fps = set(cand.get("judgment_fingerprints") or [])
    fp_diff = diff_fingerprint_sets(b_fps, c_fps)

    for fp in fp_diff["only_in_baseline"]:
        findings.append({
            "category": REGRESSION,
            "kind": "fingerprint_lost",
            "fingerprint": fp,
            "note": "anchor lost in candidate",
        })
    for fp in fp_diff["only_in_candidate"]:
        findings.append({
            "category": NEEDS_REVIEW,
            "kind": "fingerprint_new",
            "fingerprint": fp,
            "note": "new issue in candidate; human to classify (INTENDED_IMPROVEMENT vs REGRESSION vs EXPECTED_VARIANCE)",
        })

    # ---- hard quality gates ----
    bq = base.get("judgment_quality", {})
    cq = cand.get("judgment_quality", {})
    for k in ["forbidden_issue_count", "false_red_count"]:
        b = bq.get(k, 0)
        c = cq.get(k, 0)
        if c > b:
            findings.append({
                "category": REGRESSION,
                "kind": k,
                "baseline": b,
                "candidate": c,
                "note": "hard-gate violation increased",
            })

    kbq_b = base.get("kb_a_quality", {}).get("unsupported_red_count", 0)
    kbq_c = cand.get("kb_a_quality", {}).get("unsupported_red_count", 0)
    if kbq_c > kbq_b:
        findings.append({
            "category": REGRESSION,
            "kind": "unsupported_red_count",
            "baseline": kbq_b, "candidate": kbq_c,
        })

    vq_b = base.get("vision_quality", {})
    vq_c = cand.get("vision_quality", {})
    for k in ["visual_false_red_count", "quality_gate_false_pass_count"]:
        if vq_c.get(k, 0) > vq_b.get(k, 0):
            findings.append({
                "category": REGRESSION,
                "kind": k,
                "baseline": vq_b.get(k, 0), "candidate": vq_c.get(k, 0),
            })

    # ---- performance ----
    bp = base.get("performance", {})
    cp = cand.get("performance", {})
    p95_change = _perf_pct_change(bp.get("total_seconds_p95"), cp.get("total_seconds_p95"))
    if p95_change is not None:
        if p95_change > 0.35:
            findings.append({
                "category": REGRESSION,
                "kind": "p95_regression",
                "delta_pct": round(p95_change * 100, 1),
                "note": "p95 slowdown > 35%",
            })
        elif p95_change > 0.20:
            findings.append({
                "category": NEEDS_REVIEW,
                "kind": "p95_yellow",
                "delta_pct": round(p95_change * 100, 1),
            })

    # ---- reproducibility ----
    br = base.get("reproducibility", {})
    cr = cand.get("reproducibility", {})
    env_keys = [
        "python_version", "os", "dependency_lock_hash",
        "model_id", "model_endpoint_id", "model_config_hash",
        "temperature",
    ]
    for k in env_keys:
        if br.get(k) != cr.get(k):
            findings.append({
                "category": ENVIRONMENT_CHANGE,
                "kind": f"env_diff:{k}",
                "baseline": br.get(k), "candidate": cr.get(k),
            })

    kb_keys = ["rules_hash", "agent_instructions_hash", "kb_a_snapshot_hash",
               "vision_schema_hash", "prompt_template_hash"]
    for k in kb_keys:
        if br.get(k) != cr.get(k):
            findings.append({
                "category": DATASET_CHANGE,   # rules/kb 变化视为数据集/规则集变化
                "kind": f"asset_diff:{k}",
                "baseline_hash": br.get(k), "candidate_hash": cr.get(k),
            })

    return {
        "fingerprint_diff": fp_diff,
        "findings": findings,
        "counts_by_category": _count_by_cat(findings),
    }


def _count_by_cat(findings: list[dict]) -> dict[str, int]:
    out = {}
    for f in findings:
        out[f["category"]] = out.get(f["category"], 0) + 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--out", type=Path,
                    help="Output diff_report.json; default: candidate/diff_report.json")
    args = ap.parse_args()

    if not args.candidate.is_dir() or not args.baseline.is_dir():
        print("ERROR: candidate/baseline must be directories", file=sys.stderr)
        return 1

    args.candidate = args.candidate.resolve()
    args.baseline = args.baseline.resolve()

    b_metrics = _load_metrics(args.baseline)
    c_metrics = _load_metrics(args.candidate)

    common = sorted(set(b_metrics) & set(c_metrics))
    only_baseline = sorted(set(b_metrics) - set(c_metrics))
    only_candidate = sorted(set(c_metrics) - set(b_metrics))

    per_sample = {}
    total_by_cat = {}
    for sid in common:
        r = compare_sample(b_metrics[sid], c_metrics[sid])
        per_sample[sid] = r
        for k, v in r["counts_by_category"].items():
            total_by_cat[k] = total_by_cat.get(k, 0) + v

    report = {
        "candidate": args.candidate.relative_to(REPO_ROOT).as_posix(),
        "baseline": args.baseline.relative_to(REPO_ROOT).as_posix(),
        "sample_coverage": {
            "in_both": common,
            "only_baseline": only_baseline,
            "only_candidate": only_candidate,
        },
        "totals_by_category": total_by_cat,
        "per_sample": per_sample,
    }

    out = args.out or (args.candidate / "diff_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"wrote {out.relative_to(REPO_ROOT)}")
    print(f"totals: {total_by_cat}")

    if total_by_cat.get(REGRESSION, 0) > 0:
        print("!!! REGRESSION detected — release gate should block")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
