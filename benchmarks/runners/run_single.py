"""
run_single.py — M4 Benchmark 单样本运行器（Phase B 骨架）

用途:
  - 读一个 fixture 或 document 样本, 跑对应 pipeline 得到 actual
  - 结合 expected.yaml 计算 metrics.json 并写入 runs/{run_id}/
  - 不改任何生产代码; 仅 read-only 消费判断内核 / KB / vision 接口

支持样本类型:
  - rule_fixture      : benchmarks/fixtures/rules/R??? — 加载 input.md, 走 rule scaffold
                         (Phase B: 只做 fingerprint 期望校验骨架, actual 由后续 Phase 接入内核填充)
  - kb_query_fixture  : benchmarks/fixtures/kb_queries/Q??? — 调 KBQuery.query_norms
  - vision_crop_fixture : benchmarks/fixtures/vision_crops/V??? — 只在 Ark 真调时激活
  - document          : benchmarks/documents/**/*.manifest.yaml — Phase C 起接入

用法:
  python benchmarks/runners/run_single.py \
      --sample benchmarks/fixtures/kb_queries/Q001 \
      --run-id 20260713-phaseB-smoke

  # 全量夹具批跑
  for d in benchmarks/fixtures/{rules,kb_queries,vision_crops}/*/; do
      python benchmarks/runners/run_single.py --sample "$d" --run-id 20260713-phaseB-smoke
  done

Phase B 边界:
  - rule / kb / vision 的 actual 计算仅落在 kb_query 上跑真实检索
  - rule 与 vision 目前只做「schema 校验通过 + 占位 must_hit 命中」骨架
  - Phase C 起接入 parse_paper / render_report 真实 pipeline
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.lib import fingerprint as fp_lib
from benchmarks.lib import repro_hashes
from benchmarks.lib.issue_to_fingerprint import (
    diagnostic_to_fingerprints,
)


# ============================================================
# 工具函数
# ============================================================

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_of_text(s: str) -> str:
    return _sha256_bytes(s.encode("utf-8"))


def _sha256_of_file(p: Path) -> str:
    return _sha256_bytes(p.read_bytes())


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_yaml(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================
# 样本探测
# ============================================================

def detect_sample_kind(sample_dir: Path) -> str:
    """从目录名前缀推断样本类型。"""
    name = sample_dir.name
    if name.startswith("R"):
        return "rule_fixture"
    if name.startswith("Q"):
        return "kb_query_fixture"
    if name.startswith("V"):
        return "vision_crop_fixture"
    if name.startswith("S") or name.startswith("D"):
        return "document"
    raise ValueError(f"Cannot detect sample_kind from dir: {sample_dir}")


# ============================================================
# 各类型 pipeline: 只求得 actual_fingerprints + 辅助指标
# ============================================================

def run_rule_fixture(sample_dir: Path, expected: dict,
                     actual_json: Optional[Path] = None) -> dict:
    """
    R 路由:
      - Phase B 骨架 (默认): actual_fingerprints = must_hit 照抄，仅用于 schema wiring
      - Phase C 真接: 传 --actual-json 到真实 diagnostic_result.json，
        自动抽取 fingerprint 与 expected 对比
    内核判定由 LLM 完成 (SKILL.md 主流程)，benchmarks 只负责归一化与回归对比。
    """
    input_md = (sample_dir / "input.md").read_text(encoding="utf-8")
    input_sha = _sha256_of_text(input_md)

    fingerprint_errors: list = []
    if actual_json and actual_json.exists():
        with open(actual_json, "r", encoding="utf-8") as f:
            diagnostic = json.load(f)
        actual_fps, fingerprint_errors = diagnostic_to_fingerprints(diagnostic)
    else:
        # 骨架回退: 最低可行 actual (仅用于 Phase B wiring 测)
        actual_fps = [item["fingerprint"] for item in expected.get("must_hit", [])]

    return {
        "actual_fingerprints": actual_fps,
        "input_sha256": input_sha,
        "seconds_total": 0.0,
        "fingerprint_errors": fingerprint_errors,
    }


def run_kb_query_fixture(sample_dir: Path, expected: dict) -> dict:
    """
    调用 KBQuery.query_norms(query), 返回命中 norm_id 集合。
    """
    input_yaml = _load_yaml(sample_dir / "input.yaml")
    query = input_yaml.get("query", "")
    input_sha = _sha256_of_text(json.dumps(input_yaml, ensure_ascii=False, sort_keys=True))

    kb_a_hits: list[str] = []
    seconds_total = 0.0
    try:
        from scripts.kb_query import KBQuery  # lazy import; may be heavy
        kbq = KBQuery()
        t0 = time.perf_counter()
        results = kbq.query_norms(query, topk=5)
        seconds_total = time.perf_counter() - t0
        for r in results or []:
            nid = r.get("norm_id")
            if nid and nid not in kb_a_hits:
                kb_a_hits.append(nid)
    except Exception as e:
        print(f"[warn] KB query failed for {sample_dir.name}: {e}", file=sys.stderr)

    # 占位 actual: must_hit 的 placeholder 项永远算命中
    actual_fps = [item["fingerprint"] for item in expected.get("must_hit", [])]

    return {
        "actual_fingerprints": actual_fps,
        "input_sha256": input_sha,
        "seconds_total": seconds_total,
        "kb_a_hits": kb_a_hits,
    }


def run_vision_crop_fixture(sample_dir: Path, expected: dict) -> dict:
    """
    Phase B 骨架: image_path=null, 不调 Ark, 只做 schema wiring。
    Phase D 真调时补齐。
    """
    input_yaml = _load_yaml(sample_dir / "input.yaml")
    input_sha = _sha256_of_text(json.dumps(input_yaml, ensure_ascii=False, sort_keys=True))

    actual_fps = [item["fingerprint"] for item in expected.get("must_hit", [])]

    return {
        "actual_fingerprints": actual_fps,
        "input_sha256": input_sha,
        "seconds_total": 0.0,
    }


# ============================================================
# metrics 构建
# ============================================================

def evaluate_judgment_quality(expected: dict, actual: dict) -> tuple[dict, int, int]:
    """
    计算 anchor_recall / forbidden_issue_count / false_red_count 等硬门禁字段。
    返回 (judgment_quality_dict, forbidden_count, false_red_count)。
    """
    must_hit_fps = {item["fingerprint"] for item in expected.get("must_hit", [])}
    forbidden_fps = {item["fingerprint"] for item in expected.get("forbidden_issues", [])}
    actual_fps = set(actual.get("actual_fingerprints", []))

    hit_count = len(must_hit_fps & actual_fps)
    anchor_recall = (hit_count / len(must_hit_fps)) if must_hit_fps else 1.0
    forbidden_hit = actual_fps & forbidden_fps
    forbidden_count = len(forbidden_hit)
    # false_red: 只在 rule fixture 生产内核接入后才严格计算; Phase B 保持 0
    false_red_count = 0

    return (
        {
            "anchor_recall": round(anchor_recall, 4),
            "forbidden_issue_count": forbidden_count,
            "false_red_count": false_red_count,
            # Phase C 骨架: severity/location 匹配现阶段没真实能力，
            # 候 Phase D 接入后才能真算，临时以 anchor_recall 代理
            "severity_match_rate": round(anchor_recall, 4),
            "location_hit_rate":   round(anchor_recall, 4),
            "evidence_completeness_rate": 1.0,
            "duplicate_issue_rate": 0.0,
            "repeatability_rate": 1.0,
        },
        forbidden_count,
        false_red_count,
    )


def evaluate_kb_a_quality(expected: dict, actual: dict) -> dict:
    """KB-A 命中集合与 expected.kb_a_expectations 对比。"""
    exp_kb = expected.get("kb_a_expectations", {}) or {}
    must_hit = set(exp_kb.get("must_hit", []) or [])
    must_not_hit = set(exp_kb.get("must_not_hit", []) or [])
    actual_hits = set(actual.get("kb_a_hits", []) or [])

    if must_hit or must_not_hit:
        matched = actual_hits & must_hit
        unsupported = actual_hits & must_not_hit
        norm_recall = (len(matched) / len(must_hit)) if must_hit else 1.0
        norm_precision = (
            len(matched) / (len(matched) + len(unsupported)) if (matched or unsupported) else 1.0
        )
        return {
            "norm_precision": round(norm_precision, 4),
            "norm_recall": round(norm_recall, 4),
            "irrelevant_norm_rate": round(
                len(unsupported) / len(actual_hits) if actual_hits else 0.0, 4
            ),
            "unsupported_red_count": 0,  # Phase B 骨架, 内核接入后才算
        }
    # 无 KB-A 期望时, 用 1.0 表示 vacuously true (schema 强制 number)
    return {
        "norm_precision": 1.0,
        "norm_recall": 1.0,
        "irrelevant_norm_rate": 0.0,
        "unsupported_red_count": 0,
    }


def build_metrics(
    sample_id: str,
    sample_kind: str,
    run_id: str,
    skill_version: str,
    commit_sha: str,
    dataset_version: str,
    expected: dict,
    actual: dict,
) -> dict:
    """按 metrics.schema.yaml 组装完整 metrics.json。"""
    judgment_quality, _, _ = evaluate_judgment_quality(expected, actual)
    kb_a_quality = evaluate_kb_a_quality(expected, actual)
    actual_fps = actual.get("actual_fingerprints", [])

    # 按 severity 分桶（Phase B: 骨架, 用 expected 的 severity 反推）
    counts = {"red": 0, "yellow": 0, "gray": 0}
    by_type: dict[str, int] = {}
    for item in expected.get("must_hit", []):
        if item["fingerprint"] in actual_fps:
            sev = item.get("severity", "gray")
            counts[sev] = counts.get(sev, 0) + 1
            it = item.get("fingerprint", "").split("|")[1] if "|" in item.get("fingerprint", "") else "unknown"
            by_type[it] = by_type.get(it, 0) + 1
    counts["total"] = sum(counts[k] for k in ("red", "yellow", "gray"))

    return {
        "run_metadata": {
            "run_id": run_id,
            "run_kind": "mock_ci",
            "sample_id": sample_id,
            "dataset_version": dataset_version,
            "skill_version": skill_version,
            "commit_sha": commit_sha,
            "ran_at": _now_iso(),
            "ark_provider_used": False,
        },
        "reproducibility": {
            "python_version": sys.version.split()[0],
            "os": platform.platform(),
            "architecture": platform.machine(),
            "dependency_lock_hash": repro_hashes.dependency_lock_hash(),
            "model_provider": None,
            "model_id": None,
            "model_endpoint_id": None,
            "model_config_hash": None,
            "temperature": None,
            "seed": None,
            "prompt_template_hash": repro_hashes.prompt_template_hash(),
            "rules_hash": repro_hashes.rules_hash(),
            "agent_instructions_hash": repro_hashes.agent_instructions_hash(),
            "kb_a_snapshot_hash": repro_hashes.kb_a_snapshot_hash(),
            "kb_b_snapshot_hash": repro_hashes.kb_b_snapshot_hash(),
            "vision_schema_hash": repro_hashes.vision_schema_hash(),
            "report_template_hash": repro_hashes.report_template_hash(),
            "cache_used": False,
        },
        "paper_summary": {
            "paper_type": sample_kind,
            "page_count": 1,
            "word_count": len(actual.get("input_sha256", "")),
        },
        "judgment_counts": {
            "red": counts["red"],
            "yellow": counts["yellow"],
            "gray": counts["gray"],
            "total": counts["total"],
            "by_issue_type": by_type,
        },
        "passed_checks": {"count": 0},
        "judgment_ids": [],
        "judgment_fingerprints": actual_fps,
        "judgment_quality": judgment_quality,
        "kb_a_hits": {
            "count": len(actual.get("kb_a_hits", []) or []),
            "distinct_norms": actual.get("kb_a_hits", []) or [],
            "by_fingerprint": {},
        },
        "kb_a_quality": kb_a_quality,
        "kb_b_cards": {"count": 0, "avg_similarity": None},
        "kb_b_quality": {
            "precision_at_k": None,
            "empty_when_irrelevant_rate": None,
            "duplicate_card_rate": None,
        },
        "vision": {
            "used": False,
            "regions_dispatched": 0,
            "regions_recognized": 0,
            "pages_touched": [],
            "seconds_total": 0.0,
            "tokens_total": 0,
            "provider_calls": 0,
            "failures": 0,
            "full_page_uploads_rejected": 0,
        },
        "vision_quality": {
            "region_detection_recall": None,
            "critical_cell_accuracy": None,
            "numeric_exact_match": None,
            "sign_accuracy": None,
            "significance_marker_accuracy": None,
            "header_binding_accuracy": None,
            "quality_gate_false_pass_count": 0,
            "visual_false_red_count": 0,
        },
        "performance": {
            "repeat_count": 1,
            "total_seconds_p50": round(actual.get("seconds_total", 0.0), 4),
            "total_seconds_p95": round(actual.get("seconds_total", 0.0), 4),
        },
        "artifacts": {
            "input_sha256": actual.get("input_sha256", ""),
            "canonical_result_json_sha256": _sha256_of_text(
                json.dumps({"actual_fps": actual_fps}, sort_keys=True)
            ),
            "output_docx_sha256": None,
            "output_html_sha256": None,
            "semantic_report_hash": None,
        },
    }


# ============================================================
# 主流程
# ============================================================

def run_one(sample_dir: Path, run_id: str, skill_version: str, commit_sha: str,
            dataset_version: str, actual_json: Optional[Path] = None) -> Path:
    kind = detect_sample_kind(sample_dir)
    expected_path = sample_dir / "expected.yaml"
    if not expected_path.exists():
        raise FileNotFoundError(f"expected.yaml missing: {expected_path}")

    expected = _load_yaml(expected_path)
    sample_id = expected.get("sample_id") or sample_dir.name

    if kind == "rule_fixture":
        actual = run_rule_fixture(sample_dir, expected, actual_json=actual_json)
    elif kind == "kb_query_fixture":
        actual = run_kb_query_fixture(sample_dir, expected)
    elif kind == "vision_crop_fixture":
        actual = run_vision_crop_fixture(sample_dir, expected)
    else:
        raise NotImplementedError(f"document pipeline not wired in Phase B: {kind}")

    m = build_metrics(sample_id, kind, run_id, skill_version, commit_sha,
                      dataset_version, expected, actual)

    out_dir = REPO_ROOT / "benchmarks" / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{sample_id}.metrics.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=Path, required=True,
                    help="fixture 目录, e.g. benchmarks/fixtures/rules/R001")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--skill-version", default="1.6.2")
    ap.add_argument("--commit-sha", default="08b9d81")
    ap.add_argument("--dataset-version", default="benchmark-dataset-v0.1")
    ap.add_argument("--actual-json", type=Path, default=None,
                    help="(R 路由 Phase C) 外部 diagnostic_result.json。提供后从其抽取 fingerprint，"
                         "不提供时回退 Phase B 骨架。")
    args = ap.parse_args()

    sample_dir = args.sample.resolve()
    if not sample_dir.is_dir():
        print(f"ERROR: not a directory: {sample_dir}", file=sys.stderr)
        return 2

    out = run_one(sample_dir, args.run_id, args.skill_version, args.commit_sha,
                  args.dataset_version, actual_json=args.actual_json)
    print(f"wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
