#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""knowledge_bridge.py · M3 v1.6.0 · Phase 2

**视觉证据与 M1 三层证据（KB-A/KB-B）之间的门禁层。**

设计原则（决策 8 · 视觉与 M1 三层证据）：
- **不改** `scripts/build_reference_card.py` / `scripts/kb_query.py`
- 仅提供 kb_eligibility 计算 + student_evidence 结构化打包
- 门禁规则：
  - kb_a_query_eligible：所有 vision 结果均可查询 KB-A（用于通用规范查找）
  - kb_a_evidence_eligible：**hard_gates_passed=True** 且 extraction_quality_score ≥ 0.75
  - kb_b_eligible：extraction_quality_score ≥ 0.85 + hard_gates_passed
- 低质量视觉：可查询但不作 issue 依据

关键约束（追加补齐清单）：
- 不在 evidence 正文硬编码警告语
- 用 review_notice 字段承载，报告渲染器显示"视觉解析结果，请核对原图"
- requires_visual_review=True 时报告展示原图缩略图

调用：
    from scripts.vision.knowledge_bridge import (
        compute_kb_eligibility,
        build_vision_student_evidence,
    )
"""
from __future__ import annotations

from typing import Optional


# ============================================================================
# 阈值（可通过 config/vision/kb_bridge.yaml 覆盖，Phase 4 接入）
# ============================================================================

KB_A_EVIDENCE_MIN_SCORE = 0.75
KB_B_MIN_SCORE = 0.85


# ============================================================================
# KB 资格判定
# ============================================================================

def compute_kb_eligibility(unified: dict) -> dict:
    """
    根据 quality_profile 计算三个 KB 门禁标志。

    unified: normalize + score 后的统一结构。
    """
    profile = unified.get("quality_profile") or {}
    extraction = float(profile.get("extraction_quality_score", 0.0) or 0.0)
    critical = float(profile.get("critical_field_score", 0.0) or 0.0)
    hard_gates = bool(profile.get("hard_gates_passed", False))

    kb_a_query = True   # 所有 vision 结果都能查询 KB-A
    kb_a_evidence = hard_gates and extraction >= KB_A_EVIDENCE_MIN_SCORE
    kb_b = hard_gates and extraction >= KB_B_MIN_SCORE

    eligibility = {
        "kb_a_query_eligible": kb_a_query,
        "kb_a_evidence_eligible": kb_a_evidence,
        "kb_b_eligible": kb_b,
        "reasons": _explain_eligibility(extraction, critical, hard_gates),
    }

    unified["kb_eligibility"] = {
        "kb_a_query_eligible": kb_a_query,
        "kb_a_evidence_eligible": kb_a_evidence,
        "kb_b_eligible": kb_b,
    }
    return eligibility


def _explain_eligibility(extraction: float, critical: float, hard_gates: bool) -> list:
    reasons = []
    if not hard_gates:
        reasons.append("hard_gates_passed=False → 禁用作 issue 依据")
    if extraction < KB_A_EVIDENCE_MIN_SCORE:
        reasons.append(
            f"extraction_quality_score={extraction:.2f} < {KB_A_EVIDENCE_MIN_SCORE} "
            f"→ kb_a_evidence_eligible=False"
        )
    if extraction < KB_B_MIN_SCORE:
        reasons.append(
            f"extraction_quality_score={extraction:.2f} < {KB_B_MIN_SCORE} "
            f"→ kb_b_eligible=False"
        )
    return reasons


# ============================================================================
# 打包视觉证据为 student_evidence
# ============================================================================

def build_vision_student_evidence(
    unified: dict,
    parsed_text: Optional[str] = None,
) -> dict:
    """
    将 unified 视觉结果打包成 student_evidence 对象。

    结构（决策 8）：
        {
          "source_type": "vision",
          "parsed_text": "...",
          "page_number": 12,
          "bbox": [...],
          "artifact_ref": "path or null",
          "provenance": {...},
          "quality_profile": {...},
          "requires_visual_review": true,
          "review_notice": "视觉解析结果，请核对原图"
        }

    **不硬编码警告语到 parsed_text**。
    """
    provenance = unified.get("provenance") or {}
    profile = unified.get("quality_profile") or {}
    eligibility = unified.get("kb_eligibility") or {}

    # 提取 parsed_text（如未提供，由 unified 派生）
    if parsed_text is None:
        parsed_text = _extract_parsed_text(unified)

    # 提取 bbox（取整体或 provenance 中的 input_bbox）
    bbox = provenance.get("input_bbox") or _derive_bbox(unified)

    requires_review = not bool(profile.get("hard_gates_passed", False))

    return {
        "source_type": "vision",
        "parsed_text": parsed_text,
        "page_number": provenance.get("page_number"),
        "bbox": bbox,
        "artifact_ref": provenance.get("input_artifact_ref") or None,
        "provenance": {
            "provider_name": provenance.get("provider_name"),
            "model_id": provenance.get("model_id"),
            "generated_at": provenance.get("generated_at"),
            "raw_response_hash": provenance.get("raw_response_hash"),
            "runtime_mode": provenance.get("runtime_mode"),
        },
        "quality_profile": profile,
        "kb_eligibility": eligibility,
        "requires_visual_review": requires_review,
        "review_notice": "视觉解析结果，请核对原图",
    }


def _extract_parsed_text(unified: dict) -> str:
    """从 unified 抽取用于报告展示的文本表示。"""
    artifact_type = unified.get("artifact_type")

    if artifact_type == "table":
        rows = unified.get("derived_views", {}).get("rows", [])
        headers = unified.get("derived_views", {}).get("headers", [])
        lines = []
        if headers:
            lines.append(" | ".join(str(h) for h in headers))
        for row in rows[:20]:
            lines.append(" | ".join(str(c) for c in row))
        return "\n".join(lines)

    if artifact_type == "ocr_page":
        blocks = unified.get("ocr_blocks", [])
        return "\n".join((b.get("text") or "") for b in blocks)

    if artifact_type == "formula":
        return unified.get("formula", {}).get("latex", "")

    if artifact_type == "reference_block":
        refs = unified.get("references", [])
        return "\n".join((r.get("raw_text") or "") for r in refs)

    return ""


def _derive_bbox(unified: dict) -> Optional[list]:
    """从 unified 派生一个总 bbox（取所有 bbox 的并集）。"""
    artifact_type = unified.get("artifact_type")

    bboxes = []
    if artifact_type == "table":
        for c in unified.get("cells", []):
            if c.get("bbox"):
                bboxes.append(c["bbox"])
    elif artifact_type == "ocr_page":
        for b in unified.get("ocr_blocks", []):
            if b.get("bbox"):
                bboxes.append(b["bbox"])
    elif artifact_type == "formula":
        b = unified.get("formula", {}).get("bbox")
        if b:
            bboxes.append(b)
    elif artifact_type == "reference_block":
        for r in unified.get("references", []):
            if r.get("bbox"):
                bboxes.append(r["bbox"])

    if not bboxes:
        return None

    xs0 = [b[0] for b in bboxes if len(b) == 4]
    ys0 = [b[1] for b in bboxes if len(b) == 4]
    xs1 = [b[2] for b in bboxes if len(b) == 4]
    ys1 = [b[3] for b in bboxes if len(b) == 4]
    if not xs0:
        return None
    return [min(xs0), min(ys0), max(xs1), max(ys1)]


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import json, sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent / "providers"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mock_provider import MockProvider
    from base import VisionRequest, TaskKind
    from normalizer import normalize
    from quality_scorer import score

    p = MockProvider()
    req = VisionRequest(artifact_ref="/tmp/x.png", task_kind=TaskKind.TABLE_STRUCTURE, page_number=1)
    resp = p.recognize(req)
    unified = normalize(resp, runtime_mode="core")
    profile = score(unified)
    eligibility = compute_kb_eligibility(unified)
    student_evidence = build_vision_student_evidence(unified)

    print("=== KB eligibility ===")
    print(json.dumps(eligibility, ensure_ascii=False, indent=2))
    print()
    print("=== student_evidence ===")
    print(json.dumps(student_evidence, ensure_ascii=False, indent=2))
