#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""document_triage.py · M3 v1.6.0 · Phase 1

PDF 页级类型分诊器。**Core 模式即执行**，**不做 OCR 内容识别**。

设计原则（v0.2 §3 + BUILD_GATE_ADDENDUM）：
- 每页输出 page triage 对象 + 全文 document summary 双输出
- 扫描页判定使用**组合条件**（图片覆盖率 + 原生字符数 + 文本区域占比）
- 三分类阈值：<20% text_pdf / 20-80% mixed_pdf / ≥80% scanned_pdf
- 阈值必须在真实论文集上校准（Phase 5 benchmark）
- 双栏判断：文本块横向聚类 + 列间距 + 垂直重叠综合

用途：
- Core 模式：告诉用户"哪些页面 Core 处理不了"
- Local/Cloud 模式：驱动 vision_planner 决定视觉处理策略
- 报告：显示 PDF 覆盖率、成功识别内容、未覆盖内容

CLI：
    python scripts/vision/document_triage.py paper.pdf
    python scripts/vision/document_triage.py paper.pdf --json
    python scripts/vision/document_triage.py paper.pdf --out triage.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional


# ============================================================================
# 常量（可通过 config/vision/document_triage.yaml 覆盖，Phase 2 接入）
# ============================================================================

# 扫描页判定阈值（组合条件）
TEXT_CHAR_MIN_PER_PAGE = 200          # 每页最小字符数（原生文本层）
TEXT_AREA_RATIO_MIN = 0.20            # 文本区域占比最低
IMAGE_AREA_RATIO_MAX_FOR_TEXT = 0.50  # 图片占比超此值倾向扫描

# 三分类阈值（scanned 页占比）
TEXT_PDF_MAX_RATIO = 0.20    # < 20% 扫描 → text_pdf
SCANNED_PDF_MIN_RATIO = 0.80  # ≥ 80% 扫描 → scanned_pdf

# 双栏判断
DOUBLE_COLUMN_MIN_BLOCKS = 6       # 页面至少这么多文本块才尝试判双栏
COLUMN_GAP_MIN_RATIO = 0.03        # 列间距占页宽最低比例
VERTICAL_OVERLAP_MIN_RATIO = 0.30  # 双栏文本块垂直重叠最低


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class PageTriage:
    page_index: int
    text_layer_char_count: int
    text_area_ratio: float
    image_area_ratio: float
    rotation_degrees: float
    skew_estimate: float
    column_layout: str            # single | double | multi | unknown
    reading_order_confidence: float
    has_vector_tables: bool
    page_type: str                # text | mixed | scanned | empty
    coverable_by_mode: List[str]  # 哪些模式能覆盖

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DocumentSummary:
    total_pages: int
    text_pages: int
    mixed_pages: int
    scanned_pages: int
    empty_pages: int
    document_type: str            # text_pdf | mixed_pdf | scanned_pdf
    double_column_pages: int
    rotation_issues: List[int] = field(default_factory=list)
    recommended_mode: str = "core"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TriageReport:
    source_path: str
    schema_version: str
    summary: DocumentSummary
    pages: List[PageTriage]
    provenance: dict

    def to_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "schema_version": self.schema_version,
            "summary": self.summary.to_dict(),
            "pages": [p.to_dict() for p in self.pages],
            "provenance": self.provenance,
        }


# ============================================================================
# 分诊核心逻辑
# ============================================================================

def _classify_page(
    char_count: int,
    text_area_ratio: float,
    image_area_ratio: float,
) -> str:
    """单页分类：text / mixed / scanned / empty。"""
    if char_count == 0 and image_area_ratio < 0.05:
        return "empty"
    # scanned：原生字符稀少 + 图片区域大
    if char_count < TEXT_CHAR_MIN_PER_PAGE and image_area_ratio >= IMAGE_AREA_RATIO_MAX_FOR_TEXT:
        return "scanned"
    # scanned：文本区域占比极低
    if text_area_ratio < 0.05 and image_area_ratio > 0.30:
        return "scanned"
    # mixed：有原生文本但图片区域也大
    if image_area_ratio >= 0.20 and char_count >= TEXT_CHAR_MIN_PER_PAGE:
        return "mixed"
    if text_area_ratio < TEXT_AREA_RATIO_MIN and char_count < TEXT_CHAR_MIN_PER_PAGE * 3:
        return "mixed"
    return "text"


def _detect_column_layout(text_blocks: List[dict], page_width: float) -> str:
    """
    双栏判断（简化版）：
    - 少于 DOUBLE_COLUMN_MIN_BLOCKS 直接单栏
    - 计算 x 中心分布，若明显双峰（间距 > COLUMN_GAP_MIN_RATIO） → double
    - 综合垂直重叠判断
    """
    if len(text_blocks) < DOUBLE_COLUMN_MIN_BLOCKS or page_width <= 0:
        return "single"

    x_centers = [(b["x0"] + b["x1"]) / 2 for b in text_blocks]
    x_centers.sort()

    # 简单聚类：找出 x_centers 中最大 gap
    gaps = [(x_centers[i + 1] - x_centers[i], i) for i in range(len(x_centers) - 1)]
    if not gaps:
        return "single"
    max_gap, split_idx = max(gaps, key=lambda g: g[0])
    max_gap_ratio = max_gap / page_width

    if max_gap_ratio < COLUMN_GAP_MIN_RATIO:
        return "single"

    left_blocks = text_blocks[: split_idx + 1]
    right_blocks = text_blocks[split_idx + 1 :]
    if not left_blocks or not right_blocks:
        return "single"

    # 垂直重叠：左栏与右栏是否覆盖相似 y 范围
    left_ymin = min(b["y0"] for b in left_blocks)
    left_ymax = max(b["y1"] for b in left_blocks)
    right_ymin = min(b["y0"] for b in right_blocks)
    right_ymax = max(b["y1"] for b in right_blocks)

    overlap_y = min(left_ymax, right_ymax) - max(left_ymin, right_ymin)
    total_y = max(left_ymax, right_ymax) - min(left_ymin, right_ymin)
    if total_y <= 0:
        return "single"
    overlap_ratio = overlap_y / total_y

    if overlap_ratio >= VERTICAL_OVERLAP_MIN_RATIO:
        return "double"
    return "single"


def _analyze_page(page) -> PageTriage:
    """
    分析单页。pdfplumber Page 对象。
    """
    page_width = float(page.width or 0)
    page_height = float(page.height or 0)
    page_area = page_width * page_height if page_width and page_height else 1.0

    # 原生文本层字符数
    text = page.extract_text() or ""
    char_count = len(text)

    # 文本块（用于版面/双栏分析）
    text_blocks = []
    try:
        for w in (page.extract_words() or []):
            text_blocks.append({
                "x0": float(w.get("x0", 0)),
                "y0": float(w.get("top", 0)),
                "x1": float(w.get("x1", 0)),
                "y1": float(w.get("bottom", 0)),
                "text": w.get("text", ""),
            })
    except Exception:
        pass

    # 文本区域占比
    if text_blocks:
        text_area = sum(
            max(0, b["x1"] - b["x0"]) * max(0, b["y1"] - b["y0"])
            for b in text_blocks
        )
        text_area_ratio = min(1.0, text_area / page_area) if page_area > 0 else 0.0
    else:
        text_area_ratio = 0.0

    # 图片区域占比
    image_area = 0.0
    try:
        for im in (page.images or []):
            w = max(0, float(im.get("x1", 0)) - float(im.get("x0", 0)))
            h = max(0, float(im.get("bottom", 0)) - float(im.get("top", 0)))
            image_area += w * h
    except Exception:
        pass
    image_area_ratio = min(1.0, image_area / page_area) if page_area > 0 else 0.0

    # 旋转（pdfplumber 不直接提供，占位 0）
    rotation = 0.0
    try:
        rotation = float(page.rotation or 0)
    except Exception:
        pass

    # 倾斜（Phase 1 不做实际检测，占位）
    skew = 0.0

    # 矢量表格（简化：能否 extract_tables）
    has_vector_tables = False
    try:
        tables = page.extract_tables() or []
        has_vector_tables = any(t and any(any(cell for cell in row) for row in t) for t in tables)
    except Exception:
        pass

    # 双栏判断
    column_layout = _detect_column_layout(text_blocks, page_width)

    # 阅读顺序置信度（Phase 1 简化：文本块 y 排序单调即高信心）
    reading_order_conf = 1.0
    if len(text_blocks) > 1:
        # 相邻块 y 差为正的比例
        y_seq = [b["y0"] for b in text_blocks]
        monotonic = sum(1 for i in range(len(y_seq) - 1) if y_seq[i + 1] >= y_seq[i] - 5)
        reading_order_conf = monotonic / max(1, len(y_seq) - 1)

    # 页分类
    page_type = _classify_page(char_count, text_area_ratio, image_area_ratio)

    # 可覆盖模式
    if page_type in ("text",):
        coverable = ["core", "local_vision", "cloud_enhanced"]
    elif page_type == "mixed":
        coverable = ["local_vision", "cloud_enhanced"]
    elif page_type == "scanned":
        coverable = ["local_vision", "cloud_enhanced"]
    else:
        coverable = ["core"]

    return PageTriage(
        page_index=page.page_number,
        text_layer_char_count=char_count,
        text_area_ratio=round(text_area_ratio, 4),
        image_area_ratio=round(image_area_ratio, 4),
        rotation_degrees=rotation,
        skew_estimate=skew,
        column_layout=column_layout,
        reading_order_confidence=round(reading_order_conf, 3),
        has_vector_tables=has_vector_tables,
        page_type=page_type,
        coverable_by_mode=coverable,
    )


def _summarize(pages: List[PageTriage]) -> DocumentSummary:
    total = len(pages)
    text_count = sum(1 for p in pages if p.page_type == "text")
    mixed_count = sum(1 for p in pages if p.page_type == "mixed")
    scanned_count = sum(1 for p in pages if p.page_type == "scanned")
    empty_count = sum(1 for p in pages if p.page_type == "empty")

    non_empty = max(1, total - empty_count)
    scanned_ratio = scanned_count / non_empty

    if scanned_ratio < TEXT_PDF_MAX_RATIO:
        doc_type = "text_pdf"
    elif scanned_ratio >= SCANNED_PDF_MIN_RATIO:
        doc_type = "scanned_pdf"
    else:
        doc_type = "mixed_pdf"

    double_col = sum(1 for p in pages if p.column_layout == "double")
    rotation_issues = [p.page_index for p in pages if abs(p.rotation_degrees) > 5]

    # 推荐模式（骨架版；Phase 2+ 会结合 mode_resolver）
    if doc_type == "text_pdf":
        recommended = "core"
    elif doc_type == "mixed_pdf":
        recommended = "local_vision"
    else:
        recommended = "local_vision"

    return DocumentSummary(
        total_pages=total,
        text_pages=text_count,
        mixed_pages=mixed_count,
        scanned_pages=scanned_count,
        empty_pages=empty_count,
        document_type=doc_type,
        double_column_pages=double_col,
        rotation_issues=rotation_issues,
        recommended_mode=recommended,
    )


# ============================================================================
# 对外接口
# ============================================================================

def triage_pdf(pdf_path: Path) -> TriageReport:
    """
    对 PDF 做分诊。**不做 OCR**。
    """
    try:
        import pdfplumber
    except ImportError as e:
        raise RuntimeError(
            "pdfplumber 未安装，无法执行 PDF 分诊。请：pip install pdfplumber"
        ) from e

    from datetime import datetime, timezone

    pages: List[PageTriage] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            pages.append(_analyze_page(page))

    summary = _summarize(pages)

    provenance = {
        "tool": "document_triage.py",
        "schema_version": "triage.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": {
            "text_char_min_per_page": TEXT_CHAR_MIN_PER_PAGE,
            "text_area_ratio_min": TEXT_AREA_RATIO_MIN,
            "image_area_ratio_max_for_text": IMAGE_AREA_RATIO_MAX_FOR_TEXT,
            "text_pdf_max_ratio": TEXT_PDF_MAX_RATIO,
            "scanned_pdf_min_ratio": SCANNED_PDF_MIN_RATIO,
        },
    }

    return TriageReport(
        source_path=str(pdf_path),
        schema_version="triage.v1",
        summary=summary,
        pages=pages,
        provenance=provenance,
    )


# ============================================================================
# CLI
# ============================================================================

def _format_human(report: TriageReport) -> str:
    s = report.summary
    lines = [
        "=" * 60,
        "M3 · PDF 类型分诊",
        "=" * 60,
        f"文件：{report.source_path}",
        f"总页数：{s.total_pages}",
        f"  · 文本页 : {s.text_pages}",
        f"  · 混合页 : {s.mixed_pages}",
        f"  · 扫描页 : {s.scanned_pages}",
        f"  · 空白页 : {s.empty_pages}",
        f"  · 双栏页 : {s.double_column_pages}",
        f"  · 旋转异常页 : {s.rotation_issues}",
        f"文档类型：{s.document_type}",
        f"推荐模式：{s.recommended_mode}",
    ]

    if s.total_pages <= 20:
        lines.append("")
        lines.append("--- 页级明细 ---")
        for p in report.pages:
            lines.append(
                f"  p{p.page_index:>3}: {p.page_type:<8} "
                f"chars={p.text_layer_char_count:>5} "
                f"text_ratio={p.text_area_ratio:.2f} "
                f"img_ratio={p.image_area_ratio:.2f} "
                f"cols={p.column_layout} "
                f"vtable={'Y' if p.has_vector_tables else 'N'}"
            )
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="M3 · PDF 类型分诊")
    parser.add_argument("pdf", help="PDF 文件路径")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--out", default=None, help="保存 JSON 到文件")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"[ERROR] 找不到文件：{pdf_path}", file=sys.stderr)
        sys.exit(1)

    report = triage_pdf(pdf_path)
    data = report.to_dict()

    if args.out:
        Path(args.out).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"✅ 分诊结果已写入：{args.out}")

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(_format_human(report))


if __name__ == "__main__":
    main()
