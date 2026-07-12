#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vision_pipeline.py · M3 v1.6.0-rc.3 · Phase B 端到端视觉链路

**职责**：接收 PDF 论文 + parsed units，识别关键页（含表格/图片）→ 用 Ark 视觉
识别 → 走 normalizer/quality_scorer/knowledge_bridge → 输出可以塞入 issue
evidence 字段的 vision_student_evidence 列表。

**输入**：
- pdf_path: PDF 文件路径
- parsed_units: parse_paper.py 输出的 units 列表
- target_pages: 需要视觉辅助的页码（1-indexed）
- workdir: 工作目录（渲染图片、缩略图落这里）

**输出**：
- vision_evidences: list[dict]，每项含 page_number/artifact_ref/parsed_text/
                    quality_profile/kb_eligibility/review_notice 等
- artifacts_dir: 图片缩略图目录（供 renderer 引用）

**约束**（v0.3.1 复读）：
- 只识别不评分；quality 由 quality_scorer 打
- 走 dispatcher + upload_policy 保护（40 区域 / 5 页 / 30s）
- 缩略图入 artifacts/thumb_pXX.png（renderer 引用）
- 视觉失败降灰不阻断
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE / "vision" / "providers"))
sys.path.insert(0, str(HERE / "vision"))
sys.path.insert(0, str(ROOT))

from base import TaskKind, VisionRequest  # noqa: E402
from ark_provider import ArkCloudProvider  # noqa: E402
from dispatcher import VisionDispatcher  # noqa: E402
from upload_policy import decide_upload, scan_recommendation, polite_scan_notice  # noqa: E402
from normalizer import normalize  # noqa: E402
from quality_scorer import score  # noqa: E402
from knowledge_bridge import (  # noqa: E402
    compute_kb_eligibility,
    build_vision_student_evidence,
)


def render_pdf_page(pdf_path: str, page_num_1indexed: int, out_path: Path,
                    scale: float = 2.0) -> tuple[int, int]:
    """用 pypdfium2 把 PDF 单页渲染成 PNG。返回 (width, height)。"""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(pdf_path)
    if page_num_1indexed > len(pdf) or page_num_1indexed < 1:
        raise ValueError(f"页码越界: {page_num_1indexed} not in [1, {len(pdf)}]")
    page = pdf[page_num_1indexed - 1]
    img = page.render(scale=scale).to_pil()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path), "PNG")
    return img.size  # (w, h)


def make_thumbnail(src_png: Path, dst_png: Path, max_width: int = 800) -> None:
    """把整页 PNG 生成缩略图（等比缩放）。"""
    from PIL import Image
    with Image.open(src_png) as im:
        w, h = im.size
        if w > max_width:
            ratio = max_width / w
            im = im.resize((max_width, int(h * ratio)), Image.LANCZOS)
        dst_png.parent.mkdir(parents=True, exist_ok=True)
        im.save(str(dst_png), "PNG", optimize=True)


def run_vision_on_page(
    dispatcher: VisionDispatcher,
    image_path: Path,
    page_num: int,
    task_kind: TaskKind = TaskKind.TABLE_STRUCTURE,
    timeout_seconds: float = 60.0,
    is_full_page: bool = True,
    allow_full_page_upload: bool = True,
) -> dict:
    """
    对单页图像做一次视觉识别，返回打包好的 vision_student_evidence 结构。
    识别失败/降级 → 返回带 downgrade_reason 的降灰结构。

    v0.3.1 P0-3 & P0-7：
    - 先走 upload_policy.decide_upload（尺寸/字节数阈值）
    - 整页上传需 allow_full_page_upload=True（否则降灰）
    """
    # v0.3.1 上传策略前置检查
    if is_full_page and not allow_full_page_upload:
        return {
            "source_type": "vision_failed",
            "page_number": page_num,
            "artifact_ref": str(image_path),
            "parsed_text": "",
            "downgrade_reason": "full_page_upload_not_authorized: 需用户显式【确认上传】",
            "review_notice": "整页图像未获授权上传，请人工核对原图",
            "requires_visual_review": True,
        }

    decision = decide_upload(str(image_path), is_full_page=is_full_page)
    if not decision.allow:
        return {
            "source_type": "vision_failed",
            "page_number": page_num,
            "artifact_ref": str(image_path),
            "parsed_text": "",
            "downgrade_reason": f"upload_policy_rejected: {decision.reason}",
            "scale_hint": decision.scale_hint,
            "review_notice": "图像超上传阈值，未进行视觉识别，请人工核对原图",
            "requires_visual_review": True,
        }

    req = VisionRequest(
        artifact_ref=str(image_path),
        task_kind=task_kind,
        page_number=page_num,
        timeout_seconds=timeout_seconds,
    )
    result = dispatcher.recognize(req)

    if not result.ok:
        # 降灰
        return {
            "source_type": "vision_failed",
            "page_number": page_num,
            "artifact_ref": str(image_path),
            "parsed_text": "",
            "downgrade_reason": result.downgrade_reason,
            "review_notice": "视觉识别未完成，请人工核对原图",
            "requires_visual_review": True,
            "quota_used": result.quota_used,
            "quota_limit": result.quota_limit,
        }

    resp = result.response
    unified = normalize(resp, runtime_mode="basic")
    unified["quality_profile"] = score(unified)
    compute_kb_eligibility(unified)
    evidence = build_vision_student_evidence(unified)

    # 补充分派信息
    evidence["quota_used"] = result.quota_used
    evidence["quota_limit"] = result.quota_limit
    evidence["latency_ms"] = resp.latency_ms
    evidence["model_id"] = resp.model_id
    # 保留原始 cells 供 renderer 展示（限量）
    if unified.get("artifact_type") == "table":
        evidence["table_preview"] = {
            "n_rows": unified.get("n_rows"),
            "n_cols": unified.get("n_cols"),
            "caption": unified.get("caption", ""),
            "cells": unified.get("cells", [])[:30],  # 限 30 个
        }
    evidence["usage"] = resp.metadata.get("usage") if resp.metadata else None

    return evidence


def process_pdf(
    pdf_path: str,
    target_pages: list[int],
    workdir: Path,
    task_kind: TaskKind = TaskKind.TABLE_STRUCTURE,
    document_type: str = "text_pdf",
    allow_full_page_upload: bool = True,
) -> dict:
    """
    对 PDF 指定页做视觉识别，输出结果字典。

    Args:
        document_type: 来自 document_triage.py（text_pdf / mixed_pdf / scanned_pdf）
        allow_full_page_upload: 整页上传授权（默认 True，主链路已经预筛选目标页）

    Returns:
        {
          "provider": "ark_cloud",
          "model_id": "...",
          "document_type": "text_pdf",
          "scan_recommendation": "upload_regions_only",
          "target_pages": [...],
          "evidences": [ {...page 20 vision result}, ... ],
          "artifacts_dir": ".../artifacts/",
          "totals": {"quota_used": N, "quota_limit": M, ...},
        }
    """
    # v0.3.1 P0-3：纯扫描 PDF 全篇降灰
    recommendation = scan_recommendation(document_type)
    if recommendation == "downgrade_to_gray":
        return {
            "provider": "ark_cloud",
            "available": False,
            "reasons": [polite_scan_notice()],
            "document_type": document_type,
            "scan_recommendation": recommendation,
            "target_pages": target_pages,
            "evidences": [],
        }

    provider = ArkCloudProvider()
    ok, reasons = provider.available()
    if not ok:
        return {
            "provider": "ark_cloud",
            "available": False,
            "reasons": reasons,
            "target_pages": target_pages,
            "evidences": [],
        }

    dispatcher = VisionDispatcher(provider=provider)
    artifacts_dir = workdir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    evidences = []
    total_tokens = 0

    for page in target_pages:
        # 渲染 → 缩略图 → 识别
        full_png = artifacts_dir / f"page_{page:02d}.png"
        thumb_png = artifacts_dir / f"thumb_p{page:02d}.png"

        try:
            w, h = render_pdf_page(pdf_path, page, full_png, scale=2.0)
        except Exception as e:
            evidences.append({
                "source_type": "vision_failed",
                "page_number": page,
                "downgrade_reason": f"render_pdf_page 失败: {e}",
                "review_notice": "无法渲染页面为图像",
                "requires_visual_review": True,
            })
            continue

        # 缩略图供 renderer
        try:
            make_thumbnail(full_png, thumb_png, max_width=800)
        except Exception:
            pass  # 缩略图失败不影响识别

        # 视觉识别（挂 upload_policy）
        evidence = run_vision_on_page(
            dispatcher, full_png, page, task_kind=task_kind,
            is_full_page=True,
            allow_full_page_upload=allow_full_page_upload,
        )
        evidence["thumbnail_ref"] = str(thumb_png) if thumb_png.exists() else None
        evidence["full_image_ref"] = str(full_png)
        evidence["page_size"] = [w, h]

        if evidence.get("usage"):
            total_tokens += evidence["usage"].get("total_tokens", 0)

        evidences.append(evidence)

    return {
        "provider": "ark_cloud",
        "available": True,
        "model_id": provider.model_id,
        "document_type": document_type,
        "scan_recommendation": recommendation,
        "allow_full_page_upload": allow_full_page_upload,
        "target_pages": target_pages,
        "evidences": evidences,
        "artifacts_dir": str(artifacts_dir),
        "totals": {
            "quota_used": dispatcher.quota_used,
            "quota_limit": dispatcher.max_regions,
            "total_tokens": total_tokens,
        },
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="M3 视觉链路端到端管线")
    parser.add_argument("pdf", help="PDF 文件路径")
    parser.add_argument("--pages", required=True,
                        help="需要视觉识别的页码，逗号分隔，如 13,14,15,20")
    parser.add_argument("--workdir", required=True, help="工作目录")
    parser.add_argument("--task", default="TABLE_STRUCTURE",
                        choices=["TABLE_STRUCTURE", "OCR_REGION"],
                        help="视觉任务类型")
    parser.add_argument("--document-type", default="text_pdf",
                        choices=["text_pdf", "mixed_pdf", "scanned_pdf"],
                        help="文档类型（来自 document_triage.py；text_pdf/mixed_pdf/scanned_pdf）")
    parser.add_argument("--no-full-page-upload", action="store_true",
                        help="禁止整页上传（默认允许）")
    parser.add_argument("--out", help="输出 JSON 路径（默认 workdir/vision_result.json）")
    args = parser.parse_args(argv)

    workdir = Path(args.workdir).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    target_pages = [int(p.strip()) for p in args.pages.split(",") if p.strip()]
    task_kind = TaskKind[args.task]

    result = process_pdf(
        args.pdf, target_pages, workdir,
        task_kind=task_kind,
        document_type=args.document_type,
        allow_full_page_upload=not args.no_full_page_upload,
    )

    out_path = Path(args.out) if args.out else workdir / "vision_result.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅ 视觉识别完成 → {out_path}")
    print(f"   provider available: {result.get('available')}")
    if result.get("available"):
        print(f"   model: {result.get('model_id')}")
        print(f"   pages: {result.get('target_pages')}")
        print(f"   evidences: {len(result.get('evidences', []))}")
        print(f"   quota: {result['totals']['quota_used']}/{result['totals']['quota_limit']}")
        print(f"   total tokens: {result['totals']['total_tokens']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
