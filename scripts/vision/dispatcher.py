#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dispatcher.py · M3 v1.6.0-rc.3 · v0.3.1 P0-7 最小调用保护

职责（严格收窄）：
- 单文档配额（MAX_VISION_REGIONS_PER_DOCUMENT，默认 40）
- 单页配额（≤ 5 个区域，按面积降序取）
- 单次超时（VISION_REQUEST_TIMEOUT_SECONDS，默认 30）
- 简单内嵌 LRU 缓存（image_hash + task_kind → response）
- 触及上限 / Provider 失败 → 返回降灰指示，不阻断报告

不做：
- 复杂费用系统
- 二级 Provider 仲裁
- 跨文档持久缓存
"""
from __future__ import annotations

import hashlib
import os
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import sys
_HERE = Path(__file__).resolve().parent
if str(_HERE / "providers") not in sys.path:
    sys.path.insert(0, str(_HERE / "providers"))

from base import (  # noqa: E402
    BaseVisionProvider,
    ProviderError,
    ProviderErrorKind,
    TaskKind,
    VisionRequest,
    VisionResponse,
)


DEFAULT_MAX_REGIONS_PER_DOC = 40
DEFAULT_MAX_REGIONS_PER_PAGE = 5
DEFAULT_CACHE_SIZE = 64


@dataclass
class DispatchResult:
    """dispatch 返回统一形态。"""
    ok: bool
    response: Optional[VisionResponse] = None
    downgrade_reason: Optional[str] = None
    quota_used: int = 0
    quota_limit: int = 0


class VisionDispatcher:
    """
    单文档生命周期内的 Provider 调用调度器。

    典型用法：
        d = VisionDispatcher(provider=ArkCloudProvider())
        for region in regions:
            result = d.recognize(req)
            if result.ok:
                use(result.response)
            else:
                downgrade_to_gray(region, reason=result.downgrade_reason)
    """

    def __init__(
        self,
        provider: BaseVisionProvider,
        max_regions_per_document: Optional[int] = None,
        max_regions_per_page: int = DEFAULT_MAX_REGIONS_PER_PAGE,
        cache_size: int = DEFAULT_CACHE_SIZE,
    ):
        self.provider = provider
        self.max_regions = int(
            max_regions_per_document
            or os.getenv("MAX_VISION_REGIONS_PER_DOCUMENT", DEFAULT_MAX_REGIONS_PER_DOC)
        )
        self.max_regions_per_page = max_regions_per_page
        self._used = 0
        self._cache: OrderedDict[str, VisionResponse] = OrderedDict()
        self._cache_size = cache_size

    # ------------------------------------------------------------------ 配额

    @property
    def quota_remaining(self) -> int:
        return max(0, self.max_regions - self._used)

    @property
    def quota_used(self) -> int:
        return self._used

    def budget_exhausted(self) -> bool:
        return self._used >= self.max_regions

    # ------------------------------------------------------------------ 单页选择

    def select_top_regions_per_page(self, regions: list) -> list:
        """
        单页超过 max_regions_per_page 的区域按面积降序取前 N。
        regions 每项需含 bbox: [x0, y0, x1, y1]。
        """
        def _area(r):
            bbox = r.get("bbox") or [0, 0, 0, 0]
            x0, y0, x1, y1 = bbox
            return max(0, x1 - x0) * max(0, y1 - y0)

        sorted_regions = sorted(regions, key=_area, reverse=True)
        return sorted_regions[: self.max_regions_per_page]

    # ------------------------------------------------------------------ 主入口

    def recognize(self, req: VisionRequest) -> DispatchResult:
        # 配额检查
        if self.budget_exhausted():
            return DispatchResult(
                ok=False,
                downgrade_reason=f"quota_exhausted: 已达单文档配额 {self.max_regions}",
                quota_used=self._used,
                quota_limit=self.max_regions,
            )

        # 缓存查找
        key = self._cache_key(req)
        if key in self._cache:
            self._cache.move_to_end(key)
            return DispatchResult(
                ok=True,
                response=self._cache[key],
                quota_used=self._used,
                quota_limit=self.max_regions,
            )

        # 调 Provider
        try:
            resp = self.provider.recognize(req)
        except ProviderError as e:
            reason = f"provider_error({e.kind.value}): {e.message[:80]}"
            return DispatchResult(
                ok=False,
                downgrade_reason=reason,
                quota_used=self._used,
                quota_limit=self.max_regions,
            )

        # 记账
        self._used += 1
        self._cache[key] = resp
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

        return DispatchResult(
            ok=True,
            response=resp,
            quota_used=self._used,
            quota_limit=self.max_regions,
        )

    # ------------------------------------------------------------------ 内部

    def _cache_key(self, req: VisionRequest) -> str:
        """基于图像内容 hash + task_kind + bbox 的稳定 key。"""
        try:
            img_hash = hashlib.sha256(Path(req.artifact_ref).read_bytes()).hexdigest()[:16]
        except Exception:
            img_hash = "no_file"
        bbox_str = "-".join(str(int(v)) for v in (req.bbox or []))
        return f"{img_hash}::{req.task_kind.value}::{bbox_str}"
