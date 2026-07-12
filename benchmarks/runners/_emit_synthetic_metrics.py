"""
Emit a synthetic metrics.json for wiring test (M4 v0.2 Phase A).

Purpose: exercise schema + release_gate_check + promote_baseline + compare_run
end-to-end without touching production Skill code or samples.

NOTE: this is a wiring test only. The metrics values are hand-crafted defaults
that pass all hard gates. Do NOT use for real Benchmark judgment.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.lib import repro_hashes

REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def build_sample(sample_id: str, run_id: str, skill_version: str, commit_sha: str,
                 dataset_version: str) -> dict:
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
            "paper_type": "rule_fixture",
            "page_count": 1,
            "word_count": 200,
        },
        "judgment_counts": {
            "red": 1,
            "yellow": 0,
            "gray": 0,
            "total": 1,
            "by_issue_type": {"citation": 1},
        },
        "passed_checks": {"count": 0},
        "judgment_ids": ["R-01"],
        "judgment_fingerprints": [
            "gb7714_2015_journal_completeness|citation|reference_12|missing_volume_pages",
        ],
        "judgment_quality": {
            "anchor_recall": 1.0,
            "forbidden_issue_count": 0,
            "false_red_count": 0,
            "severity_match_rate": 1.0,
            "location_hit_rate": 1.0,
            "evidence_completeness_rate": 1.0,
            "duplicate_issue_rate": 0.0,
            "repeatability_rate": 1.0,
        },
        "kb_a_hits": {
            "count": 1,
            "distinct_norms": ["gb7714_2015_journal_completeness"],
            "by_fingerprint": {
                "gb7714_2015_journal_completeness|citation|reference_12|missing_volume_pages": [
                    "gb7714_2015_journal_completeness"
                ]
            },
        },
        "kb_a_quality": {
            "norm_precision": 1.0,
            "norm_recall": 1.0,
            "irrelevant_norm_rate": 0.0,
            "unsupported_red_count": 0,
        },
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
            "repeat_count": 3,
            "total_seconds_p50": 0.05,
            "total_seconds_p95": 0.08,
        },
        "artifacts": {
            "input_sha256": _sha256_of(f"synthetic-input:{sample_id}"),
            "canonical_result_json_sha256": _sha256_of(f"synthetic-canonical:{sample_id}"),
            "output_docx_sha256": None,
            "output_html_sha256": None,
            "semantic_report_hash": None,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--sample-id", default="R001_synthetic")
    ap.add_argument("--skill-version", default="1.6.2")
    ap.add_argument("--commit-sha", default="20abcca7")
    ap.add_argument("--dataset-version", default="benchmark-dataset-v0.1")
    args = ap.parse_args()

    out_dir = REPO_ROOT / "benchmarks" / "runs" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    m = build_sample(args.sample_id, args.run_id, args.skill_version,
                     args.commit_sha, args.dataset_version)
    out = out_dir / f"{args.sample_id}.metrics.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    print(f"wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
