#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Provider 抽象基类 · M3 v1.6.0 · Phase 2

所有视觉 Provider（Local PaddleOCR / Cloud Ark / 二级云 Provider）都实现本接口。

设计原则（v0.2 §6 + BUILD_GATE_ADDENDUM）：
- 输入：PIL.Image / bytes / path（本骨架统一用 path，Phase 3 补图像内存流）
- 输出：**统一 Schema**（cells[] 事实层 + derived_views）由调用方 normalize
- Provider **只做识别**，**不做质量评分**（quality 由 quality_scorer 系统结构校验，禁模型自报 confidence）
- Provider **不做隐私裁剪**（隐私由 privacy_gate 前置处理）
- Provider **不做缓存**（缓存由 cache 层负责）

Provider 契约：
- 幂等：同输入同输出（哈希稳定）
- 无副作用：不改动传入文件
- 无网络（Local）/ 有网络（Cloud）在 metadata 声明
- 失败：raise ProviderError，不吞异常
- 超时：Provider 内部实现，返回 ProviderError(kind="timeout")

**Phase 2 骨架**：接口 + 数据结构 + 三个 Provider 存根（PaddleLocal / ArkCloud / MockProvider）
**Phase 3**：Ark Cloud Provider 完整实现
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ============================================================================
# 错误类型
# ============================================================================

class ProviderErrorKind(str, Enum):
    NOT_INSTALLED = "not_installed"
    NOT_CONFIGURED = "not_configured"
    NETWORK = "network"
    TIMEOUT = "timeout"
    QUOTA = "quota"
    UNAUTHORIZED = "unauthorized"
    INVALID_INPUT = "invalid_input"
    INTERNAL = "internal"
    UNSUPPORTED_TASK = "unsupported_task"


class ProviderError(Exception):
    """Provider 内部错误。dispatcher 据此决定重试/降级/放弃。"""

    def __init__(self, kind: ProviderErrorKind, message: str, *, retriable: bool = False):
        super().__init__(f"[{kind.value}] {message}")
        self.kind = kind
        self.message = message
        self.retriable = retriable


# ============================================================================
# 任务类型
# ============================================================================

class TaskKind(str, Enum):
    """Provider 支持的任务类型。"""
    OCR_FULL_PAGE = "ocr_full_page"           # 整页 OCR
    OCR_REGION = "ocr_region"                 # bbox 区域 OCR
    TABLE_STRUCTURE = "table_structure"       # 表格结构识别
    FORMULA = "formula"                       # 公式识别
    LAYOUT = "layout"                         # 版面分析
    REFERENCE_BLOCK = "reference_block"       # 参考文献块


# ============================================================================
# 输入 / 输出
# ============================================================================

@dataclass
class VisionRequest:
    """
    统一 Provider 请求。

    - artifact_ref：图像文件路径（Phase 2）；Phase 3 补 bytes / PIL.Image
    - bbox：可选，指定裁剪区域（None 表示整图）
    - page_number：来源 PDF 页码，用于 provenance
    - task_kind：任务类型
    - hints：语言/领域等提示
    """
    artifact_ref: str
    task_kind: TaskKind
    page_number: Optional[int] = None
    bbox: Optional[list] = None               # [x0, y0, x1, y1]
    hints: dict = field(default_factory=dict)
    timeout_seconds: float = 30.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["task_kind"] = self.task_kind.value
        return d


@dataclass
class VisionResponse:
    """
    **Provider 原生输出**，未 normalize。normalizer 转成统一 Schema。

    - raw：Provider 原生返回体（Ark JSON / Paddle dict / ...）
    - raw_response_hash：SHA-256 of raw JSON string
    - raw_response_ref：正常模式为 null；Debug 模式为文件路径
    - provider_name / model_id：可 Provenance
    - latency_ms / api_cost_estimate_cny：可用于预算
    - warnings：非致命告警
    """
    raw: Any
    raw_response_hash: str
    raw_response_ref: Optional[str]           # 正常模式 None
    provider_name: str
    model_id: str
    task_kind: TaskKind
    page_number: Optional[int]
    latency_ms: int
    api_cost_estimate_cny: float = 0.0
    warnings: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["task_kind"] = self.task_kind.value
        # raw 可能是复杂对象，to_dict 时省略详细序列化
        d["raw"] = "<omitted, see raw_response_hash>" if self.raw_response_ref is None else "<see raw_response_ref>"
        return d


# ============================================================================
# Provider 基类
# ============================================================================

class BaseVisionProvider(ABC):
    """
    所有 Provider 必须继承并实现 recognize() + supports()。

    实例化时读环境变量或配置；实例化本身不能失败，
    不可用性通过 `.available()` 与 recognize() 抛 ProviderError 暴露。
    """

    name: str = "base"
    model_id: str = ""
    requires_network: bool = False

    @abstractmethod
    def available(self) -> tuple[bool, list[str]]:
        """
        探测本 Provider 是否可用。

        Returns:
            (available, reasons)
            available=True 时 reasons 为空
        """
        raise NotImplementedError

    @abstractmethod
    def supports(self, task_kind: TaskKind) -> bool:
        """Provider 是否支持该任务类型。"""
        raise NotImplementedError

    @abstractmethod
    def recognize(self, req: VisionRequest) -> VisionResponse:
        """
        执行识别。

        Raises:
            ProviderError(kind=NOT_INSTALLED/NOT_CONFIGURED/NETWORK/...)
        """
        raise NotImplementedError

    def describe(self) -> dict:
        """Provider 元信息，供 doctor / benchmark 使用。"""
        ok, reasons = self.available()
        return {
            "name": self.name,
            "model_id": self.model_id,
            "available": ok,
            "reasons": reasons,
            "requires_network": self.requires_network,
        }
