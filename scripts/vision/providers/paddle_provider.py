#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PaddleOCR 3.x Local Provider · M3 v1.6.0 · Phase 2 骨架

**Phase 2**：本文件仅提供存根 + available() 探测。**不实际调用 PaddleOCR**。
**Phase 2.5+**：完整实现 recognize()，覆盖：
- OCR_FULL_PAGE / OCR_REGION（PP-OCRv4 detect + recognize）
- LAYOUT（PP-StructureV3 版面分析）
- TABLE_STRUCTURE（PP-StructureV3 表格结构）
- REFERENCE_BLOCK（版面分析 + OCR 组合）
- FORMULA（暂不支持，Phase 3+ 引入 PaddleOCR 公式管线）

安装（Phase 2.5+）：
    scripts/install_paddle.sh    # CPU-only 默认

Provider 契约见 base.py。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 允许作为独立模块与从 scripts/vision 导入
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from base import (
    BaseVisionProvider,
    ProviderError,
    ProviderErrorKind,
    TaskKind,
    VisionRequest,
    VisionResponse,
)


class PaddleLocalProvider(BaseVisionProvider):
    """PaddleOCR 3.x + PP-StructureV3 本地 Provider。"""

    name = "paddle_local"
    requires_network = False

    SUPPORTED_TASKS = {
        TaskKind.OCR_FULL_PAGE,
        TaskKind.OCR_REGION,
        TaskKind.LAYOUT,
        TaskKind.TABLE_STRUCTURE,
        TaskKind.REFERENCE_BLOCK,
    }

    def __init__(self):
        self.model_id = os.getenv("LOCAL_MODEL_PATH", "paddleocr-pp-structurev3-default")
        self.device = os.getenv("LOCAL_DEVICE", "cpu")

    def available(self) -> tuple[bool, list[str]]:
        reasons = []

        if os.getenv("LOCAL_VISION_ENABLED", "false").lower() != "true":
            reasons.append("LOCAL_VISION_ENABLED != true（Phase 2 未启用）")

        try:
            import paddleocr  # noqa: F401
        except ImportError:
            reasons.append(
                "paddleocr 未安装（Phase 2.5+ 通过 scripts/install_paddle.sh 单独安装）"
            )

        try:
            import cv2  # noqa: F401
        except ImportError:
            reasons.append("opencv-python-headless 未安装")

        # 模型文件检查（Phase 2.5+ 完善）
        # 目前 PaddleOCR 3.x 默认从 HF/官方源自动下载，无强制路径
        return (len(reasons) == 0), reasons

    def supports(self, task_kind: TaskKind) -> bool:
        return task_kind in self.SUPPORTED_TASKS

    def recognize(self, req: VisionRequest) -> VisionResponse:
        """
        **Phase 2 骨架：抛 NOT_INSTALLED 或 UNSUPPORTED_TASK**
        **Phase 2.5+**：完整实现 PP-OCRv4 + PP-StructureV3 调用
        """
        ok, reasons = self.available()
        if not ok:
            raise ProviderError(
                ProviderErrorKind.NOT_INSTALLED,
                "PaddleOCR 未启用/未安装：" + " · ".join(reasons),
                retriable=False,
            )

        if not self.supports(req.task_kind):
            raise ProviderError(
                ProviderErrorKind.UNSUPPORTED_TASK,
                f"PaddleLocalProvider 不支持任务类型 {req.task_kind.value}（公式识别在 Phase 3+）",
                retriable=False,
            )

        # 兜底：Phase 2.5 前不真跑
        raise ProviderError(
            ProviderErrorKind.NOT_INSTALLED,
            "PaddleLocalProvider.recognize() 骨架未实现，等待 Phase 2.5",
            retriable=False,
        )


# ============================================================================
# CLI（调试用）
# ============================================================================

if __name__ == "__main__":
    p = PaddleLocalProvider()
    import json
    print(json.dumps(p.describe(), ensure_ascii=False, indent=2))
