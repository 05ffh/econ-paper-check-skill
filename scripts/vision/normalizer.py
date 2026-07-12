#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""normalizer.py · M3 v1.6.0 · Phase 2

将 Provider 原生输出（VisionResponse.raw）转成统一 Schema（vision_output.schema.json）。

设计原则：
- **Phase 2 仅实现 Mock provider 的 normalize**（PaddleOCR / Ark 各自的 raw 结构 Phase 2.5/3 补）
- **derived_views 由 cells[] 推导**，禁止反向
- **禁止模型自报 confidence 填 quality_profile**（quality_scorer 系统校验后填）
- 未识别或识别失败的字段留 None / [] / null，不猜测

调用：
    from scripts.vision.normalizer import normalize
    unified = normalize(vision_response, runtime_mode="core")
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE / "providers") not in sys.path:
    sys.path.insert(0, str(_HERE / "providers"))

from base import TaskKind, VisionResponse


SCHEMA_VERSION = "vision.v1"


# ============================================================================
# 主入口
# ============================================================================

def normalize(resp: VisionResponse, runtime_mode: str = "core") -> dict:
    """
    根据 VisionResponse.task_kind 分派到具体 normalizer。
    """
    provenance = _build_provenance(resp, runtime_mode)

    if resp.task_kind == TaskKind.TABLE_STRUCTURE:
        return _normalize_table(resp, provenance)
    if resp.task_kind == TaskKind.OCR_FULL_PAGE:
        return _normalize_ocr_page(resp, provenance)
    if resp.task_kind == TaskKind.OCR_REGION:
        return _normalize_ocr_region(resp, provenance)
    if resp.task_kind == TaskKind.FORMULA:
        return _normalize_formula(resp, provenance)
    if resp.task_kind == TaskKind.LAYOUT:
        return _normalize_layout(resp, provenance)
    if resp.task_kind == TaskKind.REFERENCE_BLOCK:
        return _normalize_reference_block(resp, provenance)

    raise ValueError(f"Unknown task_kind: {resp.task_kind}")


# ============================================================================
# Provenance
# ============================================================================

def _build_provenance(resp: VisionResponse, runtime_mode: str) -> dict:
    metadata = resp.metadata or {}
    return {
        "provider_name": resp.provider_name,
        "model_id": resp.model_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_response_hash": resp.raw_response_hash,
        "raw_response_ref": resp.raw_response_ref,
        "input_artifact_ref": metadata.get("input_artifact_ref", ""),
        "input_bbox": metadata.get("input_bbox"),
        "page_number": resp.page_number,
        "latency_ms": resp.latency_ms,
        "api_cost_estimate_cny": resp.api_cost_estimate_cny,
        "runtime_mode": runtime_mode,
    }


# ============================================================================
# 各任务 normalizer
# ============================================================================

def _normalize_table(resp: VisionResponse, provenance: dict) -> dict:
    """
    表格：cells[] 事实层 + derived_views（headers/rows）由 cells 推导。
    """
    raw = resp.raw or {}
    raw_cells = raw.get("cells", []) if isinstance(raw, dict) else []

    cells = []
    for c in raw_cells:
        if not isinstance(c, dict):
            continue
        cells.append({
            "row": int(c.get("row", 0)),
            "col": int(c.get("col", 0)),
            "row_span": int(c.get("row_span", 1)),
            "col_span": int(c.get("col_span", 1)),
            "text": str(c.get("text", "")),
            "normalized_value": c.get("normalized_value"),
            "stars": c.get("stars"),
            "semantic_role": c.get("semantic_role", "other"),
            "bbox": c.get("bbox"),
            "variable_column_flag": bool(c.get("variable_column_flag", False)),
        })

    derived = _derive_table_views(cells)

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "table",
        "provenance": provenance,
        "cells": cells,
        "derived_views": derived,
        "caption": str(raw.get("caption", "")) if isinstance(raw, dict) else "",
        "n_rows": int(raw.get("n_rows", 0)) if isinstance(raw, dict) and raw.get("n_rows") else (max(c["row"] for c in cells) + 1 if cells else 0),
        "n_cols": int(raw.get("n_cols", 0)) if isinstance(raw, dict) and raw.get("n_cols") else (max(c["col"] for c in cells) + 1 if cells else 0),
        "quality_profile": None,       # 待 quality_scorer 填
        "kb_eligibility": None,        # 待 knowledge_bridge 填
        "warnings": resp.warnings or [],
    }


def _derive_table_views(cells: list) -> dict:
    """从 cells[] 推导 headers / rows（只读视图）。"""
    if not cells:
        return {"headers": [], "rows": [], "coefficients_matrix": []}

    max_row = max(c["row"] for c in cells)
    max_col = max(c["col"] for c in cells)

    # 二维矩阵
    grid: list[list[str]] = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]
    for c in cells:
        r, col = c["row"], c["col"]
        if 0 <= r < len(grid) and 0 <= col < len(grid[r]):
            grid[r][col] = c["text"]

    headers = grid[0] if grid else []
    rows = grid[1:] if len(grid) > 1 else []

    return {
        "headers": headers,
        "rows": rows,
        "coefficients_matrix": [],   # Phase 2.5+ 从 semantic_role=coefficient 提取
    }


def _normalize_ocr_page(resp: VisionResponse, provenance: dict) -> dict:
    raw = resp.raw or {}
    blocks_in = raw.get("text_blocks", []) if isinstance(raw, dict) else []
    ocr_blocks = []
    for i, b in enumerate(blocks_in):
        if not isinstance(b, dict):
            continue
        ocr_blocks.append({
            "text": str(b.get("text", "")),
            "bbox": b.get("bbox"),
            "language": b.get("language", "zh"),
            "reading_order_index": b.get("reading_order_index", i),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "ocr_page",
        "provenance": provenance,
        "ocr_blocks": ocr_blocks,
        "quality_profile": None,
        "kb_eligibility": None,
        "warnings": resp.warnings or [],
    }


def _normalize_ocr_region(resp: VisionResponse, provenance: dict) -> dict:
    raw = resp.raw or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "ocr_page",
        "provenance": provenance,
        "ocr_blocks": [{
            "text": str(raw.get("text", "")) if isinstance(raw, dict) else "",
            "bbox": raw.get("bbox") if isinstance(raw, dict) else None,
            "language": "zh",
            "reading_order_index": 0,
        }],
        "quality_profile": None,
        "kb_eligibility": None,
        "warnings": resp.warnings or [],
    }


def _normalize_formula(resp: VisionResponse, provenance: dict) -> dict:
    raw = resp.raw or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "formula",
        "provenance": provenance,
        "formula": {
            "latex": raw.get("latex", "") if isinstance(raw, dict) else "",
            "mathml": None,               # M3.1 不强制
            "bbox": raw.get("bbox", []) if isinstance(raw, dict) else [],
            "symbols": raw.get("symbols", []) if isinstance(raw, dict) else [],
            "image_hash": raw.get("image_hash", "") if isinstance(raw, dict) else "",
            "render_valid": None,          # Phase 4 校验
            "variable_matches": [],
        },
        "quality_profile": None,
        "kb_eligibility": None,
        "warnings": resp.warnings or [],
    }


def _normalize_layout(resp: VisionResponse, provenance: dict) -> dict:
    raw = resp.raw or {}
    regions_in = raw.get("regions", []) if isinstance(raw, dict) else []
    regions = []
    for i, r in enumerate(regions_in):
        if not isinstance(r, dict):
            continue
        regions.append({
            "kind": r.get("kind", "unknown"),
            "bbox": r.get("bbox", []),
            "reading_order_index": r.get("reading_order_index", i),
            "column_index": r.get("column_index", 0),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "layout",
        "provenance": provenance,
        "layout_regions": regions,
        "quality_profile": None,
        "kb_eligibility": None,
        "warnings": resp.warnings or [],
    }


def _normalize_reference_block(resp: VisionResponse, provenance: dict) -> dict:
    raw = resp.raw or {}
    entries_in = raw.get("entries", []) if isinstance(raw, dict) else []
    references = []
    for e in entries_in:
        if not isinstance(e, dict):
            continue
        references.append({
            "raw_text": str(e.get("raw_text", "")),
            "page": e.get("page", resp.page_number),
            "bbox": e.get("bbox", []),
            "parse_quality": e.get("parse_quality", "medium"),
            "csl": e.get("csl"),           # Phase 2.5+ 解析
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "reference_block",
        "provenance": provenance,
        "references": references,
        "quality_profile": None,
        "kb_eligibility": None,
        "warnings": resp.warnings or [],
    }


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    # 自测：用 MockProvider 生成一次并 normalize
    from mock_provider import MockProvider
    from base import VisionRequest
    import json as _json

    p = MockProvider()
    for kind in [TaskKind.TABLE_STRUCTURE, TaskKind.OCR_FULL_PAGE, TaskKind.FORMULA]:
        req = VisionRequest(
            artifact_ref="/tmp/test.png",
            task_kind=kind,
            page_number=1,
        )
        resp = p.recognize(req)
        unified = normalize(resp, runtime_mode="core")
        print(f"=== {kind.value} ===")
        print(_json.dumps(unified, ensure_ascii=False, indent=2)[:600])
        print()
