#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mock Provider · M3 v1.6.0 · Phase 2

用于单元测试与骨架验证。**不做真实识别**，返回预设 mock 数据。

用途：
- Phase 2 单测：验证 dispatcher / normalizer / quality_scorer 骨架能跑通
- Phase 5 benchmark：可作为"零成本 Provider"占位
- CI：无 Key 无 GPU 环境下的最小可跑通链路

**永远 available，永远返回合成 raw**。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

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


class MockProvider(BaseVisionProvider):
    """总是可用；根据 task_kind 返回预设 mock 数据。"""

    name = "mock"
    model_id = "mock-v1"
    requires_network = False

    SUPPORTED_TASKS = set(TaskKind)  # 全部支持

    def available(self) -> tuple[bool, list[str]]:
        return True, []

    def supports(self, task_kind: TaskKind) -> bool:
        return task_kind in self.SUPPORTED_TASKS

    def recognize(self, req: VisionRequest) -> VisionResponse:
        t0 = time.time()

        # 构造 mock raw
        if req.task_kind == TaskKind.OCR_FULL_PAGE:
            raw = {
                "type": "ocr_full_page",
                "text_blocks": [
                    {"text": "第一章 引言（mock）", "bbox": [50, 50, 200, 70]},
                    {"text": "本文研究数字经济对就业的影响（mock）", "bbox": [50, 80, 400, 100]},
                ],
                "language": "zh",
            }
        elif req.task_kind == TaskKind.OCR_REGION:
            raw = {
                "type": "ocr_region",
                "text": "mock region text",
                "bbox": req.bbox or [0, 0, 100, 20],
            }
        elif req.task_kind == TaskKind.TABLE_STRUCTURE:
            raw = {
                "type": "table_structure",
                "cells": [
                    {"row": 0, "col": 0, "text": "变量", "bbox": [50, 50, 100, 70]},
                    {"row": 0, "col": 1, "text": "均值", "bbox": [100, 50, 150, 70]},
                    {"row": 0, "col": 2, "text": "标准差", "bbox": [150, 50, 200, 70]},
                    {"row": 1, "col": 0, "text": "GDP", "bbox": [50, 70, 100, 90]},
                    {"row": 1, "col": 1, "text": "5.2", "bbox": [100, 70, 150, 90]},
                    {"row": 1, "col": 2, "text": "0.8", "bbox": [150, 70, 200, 90]},
                ],
                "n_rows": 2,
                "n_cols": 3,
            }
        elif req.task_kind == TaskKind.FORMULA:
            raw = {
                "type": "formula",
                "latex": "Y_{it} = \\beta_0 + \\beta_1 X_{it} + \\epsilon_{it}",
                "symbols": ["Y_{it}", "\\beta_0", "\\beta_1", "X_{it}", "\\epsilon_{it}"],
                "bbox": req.bbox or [0, 0, 200, 40],
            }
        elif req.task_kind == TaskKind.LAYOUT:
            raw = {
                "type": "layout",
                "regions": [
                    {"kind": "text", "bbox": [50, 50, 400, 200]},
                    {"kind": "table", "bbox": [50, 220, 400, 400]},
                    {"kind": "figure", "bbox": [50, 420, 400, 600]},
                ],
            }
        elif req.task_kind == TaskKind.REFERENCE_BLOCK:
            raw = {
                "type": "reference_block",
                "entries": [
                    {"raw_text": "张三. 数字经济研究. 经济研究, 2023, 58(1): 1-15.", "bbox": [50, 700, 500, 720]},
                    {"raw_text": "Li Y. Digital Economy. AER, 2024, 114(3): 456-478.", "bbox": [50, 725, 500, 745]},
                ],
            }
        else:
            raise ProviderError(
                ProviderErrorKind.UNSUPPORTED_TASK,
                f"MockProvider 未覆盖 {req.task_kind.value}",
                retriable=False,
            )

        raw_str = json.dumps(raw, ensure_ascii=False, sort_keys=True)
        raw_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
        latency_ms = int((time.time() - t0) * 1000)

        return VisionResponse(
            raw=raw,
            raw_response_hash=raw_hash,
            raw_response_ref=None,  # Mock 不落盘
            provider_name=self.name,
            model_id=self.model_id,
            task_kind=req.task_kind,
            page_number=req.page_number,
            latency_ms=latency_ms,
            api_cost_estimate_cny=0.0,
            warnings=[],
            metadata={
                "mock": True,
                "input_artifact_ref": req.artifact_ref,
                "input_bbox": req.bbox,
            },
        )


if __name__ == "__main__":
    p = MockProvider()
    import json
    print(json.dumps(p.describe(), ensure_ascii=False, indent=2))
    print("---")
    resp = p.recognize(VisionRequest(
        artifact_ref="/tmp/nonexistent.png",
        task_kind=TaskKind.TABLE_STRUCTURE,
        page_number=1,
    ))
    print(json.dumps(resp.to_dict(), ensure_ascii=False, indent=2))
    print("raw preview:", resp.raw)
