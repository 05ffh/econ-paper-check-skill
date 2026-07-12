#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vision_hint.py · M3 v1.6.2 · 视觉未配置时的礼貌提醒生成器

用户上传 PDF 但视觉辅助未配置时，Skill 需要生成一条**只提示一次**的礼貌通知。

触发条件（4 个必须同时满足）：
1. 输入是 PDF（不是 DOCX）
2. document_triage 判定 doc_type ∈ {mixed_pdf, scanned_pdf} 或 recommended ∈ {vision_recommended, vision_required}
3. 视觉状态 == unconfigured
4. 本会话尚未提示过（`.workdir/<session>/.vision_hint_shown` 未存在）

不触发的场景（务必静默）：
- DOCX 输入
- text_pdf（无图片型关键区域）
- 视觉已配置（无论是否验证）
- 本会话已提示过一次

术语：只用「PDF 视觉辅助识别」，禁 Core / Cloud Enhanced / Local Vision。
"""
from __future__ import annotations

import os
from pathlib import Path


HINT_TEMPLATE = """━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📄 检测到 PDF 中含图片型关键区域
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  当前状态：
     · 基础质检将正常继续（Word 层文本、参考文献、结构等）
     · PDF 中的图片型表格 / 公式 / 图表将进入
       「需人工复核」清单，不做自动识别

  可选增强：配置火山方舟 PDF 视觉辅助识别后，
             这些图片区域可获得自动结构化识别

  查看启用方式：
     python3 scripts/doctor.py
     （会给出 requirements-vision.txt 安装、.env 配置、
       VISION_ENABLED 启用的完整步骤）

  本次质检不受影响，继续进行。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


def _hint_lock_path(session_workdir: Path) -> Path:
    return session_workdir / ".vision_hint_shown"


def should_show_hint(
    document_type: str,
    recommended_mode: str,
    vision_state: str,
    session_workdir: Path,
) -> bool:
    """
    判断是否应该显示提示（不实际显示、不落盘）。

    Args:
        document_type: document_triage.summary.document_type，text_pdf/mixed_pdf/scanned_pdf
        recommended_mode: text_only / vision_optional / vision_recommended / vision_required
        vision_state: unconfigured / configured_unverified / verified
        session_workdir: 会话工作目录（用于锁存本会话是否已提示）
    """
    # 视觉已配置 → 静默
    if vision_state != "unconfigured":
        return False

    # 无关键图片区域 → 静默
    needs_vision = document_type in ("mixed_pdf", "scanned_pdf") or \
                   recommended_mode in ("vision_recommended", "vision_required")
    if not needs_vision:
        return False

    # 本会话已提示 → 静默
    if _hint_lock_path(session_workdir).exists():
        return False

    return True


def emit_hint_if_needed(
    document_type: str,
    recommended_mode: str,
    vision_state: str,
    session_workdir: Path,
) -> str | None:
    """
    组合判定 + 落盘 + 返回提示文本。

    仅当 should_show_hint 为 True 时返回提示字符串并落盘锁；
    否则返回 None。
    """
    if not should_show_hint(document_type, recommended_mode, vision_state, session_workdir):
        return None

    try:
        session_workdir.mkdir(parents=True, exist_ok=True)
        _hint_lock_path(session_workdir).write_text("shown", encoding="utf-8")
    except Exception:
        pass

    return HINT_TEMPLATE


def main():
    """CLI 演示：`python3 scripts/vision_hint.py --doc-type mixed_pdf --workdir /tmp/x`"""
    import argparse

    ap = argparse.ArgumentParser(description="视觉未配置提示生成器")
    ap.add_argument("--doc-type", default="mixed_pdf",
                    choices=["text_pdf", "mixed_pdf", "scanned_pdf"])
    ap.add_argument("--recommended", default="vision_recommended",
                    choices=["text_only", "vision_optional",
                             "vision_recommended", "vision_required"])
    ap.add_argument("--vision-state", default="unconfigured",
                    choices=["unconfigured", "configured_unverified", "verified"])
    ap.add_argument("--workdir", required=True, help="会话工作目录")
    ap.add_argument("--force", action="store_true",
                    help="忽略会话锁强制显示（调试用，不落盘）")
    args = ap.parse_args()

    wd = Path(args.workdir)
    if args.force:
        # 检查条件但不消费锁
        if args.vision_state == "unconfigured" and (
            args.doc_type in ("mixed_pdf", "scanned_pdf")
            or args.recommended in ("vision_recommended", "vision_required")
        ):
            print(HINT_TEMPLATE)
        return

    hint = emit_hint_if_needed(
        args.doc_type, args.recommended, args.vision_state, wd
    )
    if hint:
        print(hint)


if __name__ == "__main__":
    main()
