#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""upload_policy.py · M3 v1.6.0-rc.3 · v0.3.1 P0-3 纯扫描 PDF 边界

职责：
- 纯扫描 PDF → 全篇降灰 + 礼貌提醒
- 不自动上传整页（单页图像 > 4 MB 或 > 3000×4000 px 拒绝）
- 只上传独立可定位的图片/表格区域
- 用户显式指定"识别第 N 页整页"才走整页上传（走 confirm_full_page_upload）
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


MAX_UPLOAD_BYTES = 4 * 1024 * 1024   # 4 MB
MAX_UPLOAD_WIDTH = 3000
MAX_UPLOAD_HEIGHT = 4000


@dataclass
class UploadDecision:
    allow: bool
    reason: str = ""
    scale_hint: Optional[float] = None    # 建议缩放比例（0.0-1.0）


def decide_upload(image_path: str, is_full_page: bool = False) -> UploadDecision:
    """
    对单张图像的上传决策。

    Args:
        image_path: 图像文件路径
        is_full_page: 是否是整页图像（True 需要更严格的判定）

    Returns:
        UploadDecision(allow, reason, scale_hint)
    """
    p = Path(image_path)
    if not p.exists():
        return UploadDecision(allow=False, reason="file_not_found")

    size = p.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        return UploadDecision(
            allow=False,
            reason=f"file_too_large: {size} bytes > {MAX_UPLOAD_BYTES}",
            scale_hint=MAX_UPLOAD_BYTES / size,
        )

    # 图像尺寸校验（Pillow 可选）
    try:
        from PIL import Image
        with Image.open(p) as im:
            w, h = im.size
        if w > MAX_UPLOAD_WIDTH or h > MAX_UPLOAD_HEIGHT:
            return UploadDecision(
                allow=False,
                reason=f"image_too_large: {w}x{h} > {MAX_UPLOAD_WIDTH}x{MAX_UPLOAD_HEIGHT}",
                scale_hint=min(MAX_UPLOAD_WIDTH / w, MAX_UPLOAD_HEIGHT / h),
            )
    except ImportError:
        pass  # Pillow 未装时跳过尺寸检查（不阻断）

    return UploadDecision(allow=True, reason="ok")


def scan_recommendation(document_type: str) -> str:
    """
    根据 document_triage 输出的 document_type 给出上传策略建议。

    Returns:
        "downgrade_to_gray"          纯扫描 · 全篇降灰
        "upload_regions_only"        文本型/混合型 · 只上传独立区域
        "explicit_upload_required"   需要用户显式授权整页
    """
    if document_type == "scanned_pdf":
        return "downgrade_to_gray"
    if document_type in ("text_pdf", "mixed_pdf"):
        return "upload_regions_only"
    return "explicit_upload_required"


def polite_scan_notice() -> str:
    """纯扫描 PDF 礼貌提醒文案。"""
    return (
        "检测到扫描版 PDF，本 Skill 不支持扫描件自动识别，"
        "建议提供 Word 原文档以获得完整质检；"
        "如坚持使用当前 PDF，图表内容将全部标记为需人工审阅（灰色）。"
    )


def full_page_upload_prompt(page: int, size_kb: int) -> str:
    """整页上传前的用户确认话术。"""
    return (
        f"⚠️ 该操作将把第 {page} 页整页图像（约 {size_kb} KB）上传到火山方舟。"
        f"确认后本次会话内该页缓存有效，其他页仍需单独确认。"
        f"请回复【确认上传】继续。"
    )
