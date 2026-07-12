#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""火山方舟多模态 Provider · M3 v1.6.0 · Phase 2 骨架

**Phase 2**：本文件仅提供存根 + available() 探测。**不实际调用 API**。
**Phase 3**：完整实现 recognize()，覆盖 OCR / TABLE_STRUCTURE / FORMULA / REFERENCE_BLOCK。

设计原则（追加补齐清单 + BUILD_GATE_ADDENDUM）：
- **不绑豆包**：调用统一走 OpenAI 兼容接口（`base_url` + `model`）
- **模型 ID 部署者配**：`ARK_VISION_MODEL_ID` 环境变量
- **上传粒度**：默认 bbox 裁剪 + 少量上下文
- **整页上传**需要 `ALLOW_FULL_PAGE_UPLOAD=true` + 用户再次授权（本 Provider 不做授权判断，由 privacy_gate 前置处理）
- **正常模式**：raw_response_ref=None，只存 raw_response_hash
- **Debug 模式**：`DEBUG_KEEP_RAW_RESPONSE=true` 时 raw_response_ref 临时落盘 ≤24h
- **成本估算**：Phase 3 根据 usage tokens 计算
- **重试**：GONE/NETWORK/5xx 可重试；QUOTA/UNAUTHORIZED 不重试

Provider 契约见 base.py。
"""
from __future__ import annotations

import os
import sys
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


class ArkCloudProvider(BaseVisionProvider):
    """火山方舟多模态 Provider。不绑豆包，模型 ID 由部署者配置。"""

    name = "ark_cloud"
    requires_network = True

    # Cloud 支持全部任务
    SUPPORTED_TASKS = {
        TaskKind.OCR_FULL_PAGE,
        TaskKind.OCR_REGION,
        TaskKind.LAYOUT,
        TaskKind.TABLE_STRUCTURE,
        TaskKind.FORMULA,
        TaskKind.REFERENCE_BLOCK,
    }

    def __init__(self):
        self.model_id = os.getenv("ARK_VISION_MODEL_ID", "")
        self.base_url = os.getenv("ARK_BASE_URL", "")
        self.region = os.getenv("ARK_REGION", "")

    def available(self) -> tuple[bool, list[str]]:
        reasons = []

        if not os.getenv("ARK_API_KEY"):
            reasons.append("ARK_API_KEY 未配置")
        if not self.base_url:
            reasons.append("ARK_BASE_URL 未配置")
        if not self.model_id:
            reasons.append("ARK_VISION_MODEL_ID 未配置（部署者按 benchmark 选定 endpoint id）")
        if os.getenv("ALLOW_CLOUD_UPLOAD", "false").lower() != "true":
            reasons.append("ALLOW_CLOUD_UPLOAD != true（部署者未授权上传）")

        # SDK 探测（volcengine-python-sdk 提供 ark 子模块）
        try:
            import volcenginesdkarkruntime  # noqa: F401
        except ImportError:
            try:
                import volcengine  # noqa: F401
                # 老版本 SDK；兼容但告警
            except ImportError:
                reasons.append(
                    "volcengine-python-sdk 未安装（Phase 3 通过 requirements-vision-cloud.txt 安装）"
                )

        return (len(reasons) == 0), reasons

    def supports(self, task_kind: TaskKind) -> bool:
        return task_kind in self.SUPPORTED_TASKS

    def recognize(self, req: VisionRequest) -> VisionResponse:
        """
        **Phase 2 骨架**：抛 NOT_CONFIGURED
        **Phase 3 完整实现**：
        - 加载图像 → bbox 裁剪（如提供）→ base64 编码
        - 按 task_kind 构造 prompt
        - 调 volcenginesdkarkruntime.Ark 客户端
        - 解析 response，返回 VisionResponse（raw + hash + 可选 raw_ref）
        """
        ok, reasons = self.available()
        if not ok:
            raise ProviderError(
                ProviderErrorKind.NOT_CONFIGURED,
                "Ark Cloud 未配置：" + " · ".join(reasons),
                retriable=False,
            )

        if not self.supports(req.task_kind):
            raise ProviderError(
                ProviderErrorKind.UNSUPPORTED_TASK,
                f"ArkCloudProvider 不支持任务类型 {req.task_kind.value}",
                retriable=False,
            )

        raise ProviderError(
            ProviderErrorKind.NOT_CONFIGURED,
            "ArkCloudProvider.recognize() 骨架未实现，等待 Phase 3",
            retriable=False,
        )


# ============================================================================
# CLI（调试用）
# ============================================================================

if __name__ == "__main__":
    p = ArkCloudProvider()
    import json
    print(json.dumps(p.describe(), ensure_ascii=False, indent=2))
