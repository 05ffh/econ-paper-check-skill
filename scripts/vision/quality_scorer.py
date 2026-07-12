#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""quality_scorer.py · M3 v1.6.0 · Phase 2

**由系统结构校验产生 extraction_quality_score，禁止模型自报 confidence 填充。**

设计原则（v0.2 §9 + BUILD_GATE_ADDENDUM 修订 3）：
- 检查项按 artifact_type 分组
- 每项检查 → 通过/失败 → 计分
- **hard_gates_passed** = 所有 hard gate 通过（决定是否可作红色 issue 依据的前置条件）
- **critical_field_score** = 关键字段完整度（如回归表的系数/标准误/星号列都必须齐全）
- **extraction_quality_score** = 综合分（0.0-1.0）
- **recognition_coverage** = 有效识别文本占预期区域的比例（Phase 2.5+ 精细化）

判级门槛（Phase 4 落到 §9ter）：
- 红色：extraction ≥ 0.90 + critical=1.0 + hard_gates_passed + 两处独立可读
- 黄色：extraction ≥ 0.75 + critical ≥ 0.7
- 灰色：其他 / 单模型未验证 / 两处全 Vision（M3.1 硬约束）

Phase 2 骨架：先实现 table / formula / ocr_page 的基础校验。
"""
from __future__ import annotations

import re
from typing import Any


# ============================================================================
# 数据结构
# ============================================================================

def _empty_profile() -> dict:
    return {
        "extraction_quality_score": 0.0,
        "critical_field_score": 0.0,
        "hard_gates_passed": False,
        "structural_issues": [],
        "recognition_coverage": 0.0,
    }


# ============================================================================
# 主入口
# ============================================================================

def score(unified: dict) -> dict:
    """
    对一个 normalize 后的统一结构做质量评分。

    Args:
        unified: normalize() 的输出。

    Returns:
        quality_profile dict（同时写回到 unified['quality_profile']）
    """
    artifact_type = unified.get("artifact_type", "unknown")

    if artifact_type == "table":
        profile = _score_table(unified.get("cells", []))
    elif artifact_type == "formula":
        profile = _score_formula(unified.get("formula", {}))
    elif artifact_type == "ocr_page":
        profile = _score_ocr_page(unified.get("ocr_blocks", []))
    elif artifact_type == "reference_block":
        profile = _score_reference_block(unified.get("references", []))
    elif artifact_type == "layout":
        profile = _score_layout(unified.get("layout_regions", []))
    else:
        profile = _empty_profile()
        profile["structural_issues"].append(f"unknown artifact_type: {artifact_type}")

    unified["quality_profile"] = profile
    return profile


# ============================================================================
# 表格评分
# ============================================================================

# 数字/星号提取正则
_NUM_STAR_RE = re.compile(r"^\s*-?\d+(\.\d+)?(\s*\**)?\s*$")
_STAR_RE = re.compile(r"\*+")


def _score_table(cells: list) -> dict:
    profile = _empty_profile()

    if not cells:
        profile["structural_issues"].append("cells 为空")
        return profile

    n_cells = len(cells)
    issues = profile["structural_issues"]

    # ---------- Gate 1: 行列索引连续（无空洞）
    rows = {c["row"] for c in cells}
    cols = {c["col"] for c in cells}
    max_row = max(rows)
    max_col = max(cols)
    expected = (max_row + 1) * (max_col + 1)
    # 忽略 span 导致的合法空洞，简化：只要求 ≥ 60% 填充
    fill_ratio = min(1.0, n_cells / max(1, expected))
    if fill_ratio < 0.6:
        issues.append(f"表格填充率过低 {fill_ratio:.2f}")

    # ---------- Gate 2: 至少 1 行 header + 1 行数据
    has_header = any(c["row"] == 0 and c["text"] for c in cells)
    has_data = any(c["row"] > 0 and c["text"] for c in cells)
    if not has_header:
        issues.append("缺少表头行")
    if not has_data:
        issues.append("缺少数据行")

    # ---------- Gate 3: 每列都有非空 header
    header_cells = [c for c in cells if c["row"] == 0]
    non_empty_headers = sum(1 for c in header_cells if c["text"].strip())
    header_completeness = (
        non_empty_headers / len(header_cells) if header_cells else 0.0
    )
    if header_completeness < 0.8:
        issues.append(f"表头完整度 {header_completeness:.2f} < 0.8")

    # ---------- Gate 4: 若为回归表（有 variable_column_flag=True 的列）
    #   → 系数列/标准误列/星号列 都必须存在
    is_regression = any(c.get("variable_column_flag") for c in cells)
    critical_field_score = 1.0
    if is_regression:
        roles = {c.get("semantic_role") for c in cells if c.get("semantic_role")}
        required_roles = {"coefficient", "std_error"}
        missing = required_roles - roles
        if missing:
            issues.append(f"回归表缺少 semantic_role: {missing}")
            critical_field_score = max(
                0.0,
                1.0 - 0.4 * len(missing) / len(required_roles)
            )
        # 星号可选（Phase 2.5+ 增强）
        has_stars_anywhere = any(c.get("stars") is not None for c in cells)
        if has_stars_anywhere:
            # 至少 30% 系数单元格应标注了 stars
            coef_cells = [c for c in cells if c.get("semantic_role") == "coefficient"]
            if coef_cells:
                labeled = sum(1 for c in coef_cells if c.get("stars") is not None)
                stars_coverage = labeled / len(coef_cells)
                if stars_coverage < 0.3:
                    issues.append(f"星号标注覆盖 {stars_coverage:.2f} < 0.3")
                    critical_field_score *= 0.9

    # ---------- Gate 5: bbox 存在率（可选校验，供 KB 门禁用）
    bbox_ok = sum(1 for c in cells if c.get("bbox")) / n_cells if n_cells else 0.0
    if bbox_ok < 0.5:
        issues.append(f"bbox 覆盖率 {bbox_ok:.2f} < 0.5")

    # ---------- 综合评分
    hard_gates_passed = (
        has_header
        and has_data
        and header_completeness >= 0.8
        and fill_ratio >= 0.6
    )
    extraction = (
        0.3 * fill_ratio
        + 0.3 * header_completeness
        + 0.2 * bbox_ok
        + 0.2 * critical_field_score
    )
    coverage = fill_ratio

    profile.update({
        "extraction_quality_score": round(extraction, 3),
        "critical_field_score": round(critical_field_score, 3),
        "hard_gates_passed": hard_gates_passed,
        "recognition_coverage": round(coverage, 3),
    })
    return profile


# ============================================================================
# 公式评分
# ============================================================================

def _score_formula(formula: dict) -> dict:
    profile = _empty_profile()
    issues = profile["structural_issues"]

    latex = formula.get("latex", "") or ""
    symbols = formula.get("symbols", []) or []
    bbox = formula.get("bbox") or []
    image_hash = formula.get("image_hash", "")

    # Gate 1: latex 非空
    if not latex.strip():
        issues.append("latex 为空")
    # Gate 2: bbox 存在
    if not bbox or len(bbox) != 4:
        issues.append("bbox 缺失或非法")
    # Gate 3: 大括号平衡
    balanced = latex.count("{") == latex.count("}")
    if not balanced:
        issues.append("latex 大括号不平衡")

    # 综合
    has_content = bool(latex.strip())
    has_bbox = bool(bbox and len(bbox) == 4)
    has_hash = bool(image_hash)

    extraction = (
        0.5 * (1.0 if has_content else 0.0)
        + 0.3 * (1.0 if balanced else 0.0)
        + 0.1 * (1.0 if has_bbox else 0.0)
        + 0.1 * (1.0 if has_hash else 0.0)
    )
    critical = 1.0 if has_content and balanced else 0.5 if has_content else 0.0
    hard_gates = has_content and has_bbox and balanced

    profile.update({
        "extraction_quality_score": round(extraction, 3),
        "critical_field_score": round(critical, 3),
        "hard_gates_passed": hard_gates,
        "recognition_coverage": 1.0 if has_content else 0.0,
    })
    return profile


# ============================================================================
# OCR page 评分
# ============================================================================

def _score_ocr_page(blocks: list) -> dict:
    profile = _empty_profile()
    issues = profile["structural_issues"]

    if not blocks:
        issues.append("ocr_blocks 为空")
        return profile

    n = len(blocks)
    non_empty = sum(1 for b in blocks if (b.get("text") or "").strip())
    non_empty_ratio = non_empty / n if n else 0.0

    with_bbox = sum(1 for b in blocks if b.get("bbox")) / n if n else 0.0

    total_chars = sum(len((b.get("text") or "")) for b in blocks)

    if non_empty_ratio < 0.5:
        issues.append(f"非空文本块比例 {non_empty_ratio:.2f} < 0.5")

    if total_chars < 20:
        issues.append(f"总字符 {total_chars} 过少")

    extraction = 0.6 * non_empty_ratio + 0.4 * with_bbox
    critical = non_empty_ratio
    hard_gates = non_empty_ratio >= 0.7 and total_chars >= 30

    profile.update({
        "extraction_quality_score": round(extraction, 3),
        "critical_field_score": round(critical, 3),
        "hard_gates_passed": hard_gates,
        "recognition_coverage": round(non_empty_ratio, 3),
    })
    return profile


# ============================================================================
# Reference block 评分
# ============================================================================

def _score_reference_block(refs: list) -> dict:
    profile = _empty_profile()
    issues = profile["structural_issues"]

    if not refs:
        issues.append("references 为空")
        return profile

    n = len(refs)
    with_raw = sum(1 for r in refs if (r.get("raw_text") or "").strip()) / n

    # 简单 parse quality 分布
    quality_scores = {
        "high": 1.0, "medium": 0.7, "low": 0.4, "failed": 0.0,
    }
    avg_pq = sum(
        quality_scores.get(r.get("parse_quality", "medium"), 0.5) for r in refs
    ) / n

    extraction = 0.5 * with_raw + 0.5 * avg_pq
    critical = with_raw
    hard_gates = with_raw >= 0.9 and avg_pq >= 0.5

    profile.update({
        "extraction_quality_score": round(extraction, 3),
        "critical_field_score": round(critical, 3),
        "hard_gates_passed": hard_gates,
        "recognition_coverage": round(with_raw, 3),
    })
    return profile


# ============================================================================
# Layout 评分
# ============================================================================

def _score_layout(regions: list) -> dict:
    profile = _empty_profile()
    if not regions:
        profile["structural_issues"].append("layout_regions 为空")
        return profile
    n = len(regions)
    with_bbox = sum(1 for r in regions if r.get("bbox") and len(r["bbox"]) == 4) / n
    known_kind = sum(
        1 for r in regions
        if r.get("kind") not in (None, "", "unknown")
    ) / n

    extraction = 0.5 * with_bbox + 0.5 * known_kind
    profile.update({
        "extraction_quality_score": round(extraction, 3),
        "critical_field_score": round(known_kind, 3),
        "hard_gates_passed": with_bbox >= 0.9 and known_kind >= 0.7,
        "recognition_coverage": round(with_bbox, 3),
    })
    return profile


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    # 自测
    import json, sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent / "providers"))
    from mock_provider import MockProvider
    from base import VisionRequest, TaskKind
    from normalizer import normalize

    p = MockProvider()
    for kind in [TaskKind.TABLE_STRUCTURE, TaskKind.OCR_FULL_PAGE, TaskKind.FORMULA, TaskKind.REFERENCE_BLOCK]:
        req = VisionRequest(artifact_ref="/tmp/x.png", task_kind=kind, page_number=1)
        resp = p.recognize(req)
        unified = normalize(resp, runtime_mode="core")
        profile = score(unified)
        print(f"=== {kind.value} ===")
        print(json.dumps(profile, ensure_ascii=False, indent=2))
        print()
