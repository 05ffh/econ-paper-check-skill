#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mode_resolver.py · M3 v1.6.0

职责：**根据环境状态解析实际运行模式**。

关键设计（v0.2 §2.4 + BUILD_GATE_ADDENDUM 修订 3）：
- 分离 `requested_mode`（用户/配置请求）与 `effective_mode`（实际可用）
- 自动降级路径：Cloud Enhanced → Local Vision → Core → 视觉区域降灰
- 自动降级**不需要**用户再次授权
- 升级到 Cloud 必须**三条件全部满足**：
    1. 用户显式授权（会话首次云端调用前，本模块不负责询问，由 Agent 层负责）
    2. `ALLOW_CLOUD_UPLOAD=true`
    3. API Key 和模型可用

Doctor 状态映射（Addendum 修订 3）：
    requested == effective         → healthy
    requested > effective          → degraded  (+ degradation_reason)
    连 core 都跑不起来              → failed
    requested=auto                 → healthy（用户已授权自动选择）

CLI：
    python scripts/mode_resolver.py           # 输出人类可读
    python scripts/mode_resolver.py --json    # 输出机器可读
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


# ============================================================================
# 常量
# ============================================================================

VALID_MODES = ("core", "local_vision", "cloud_enhanced", "auto")

MODE_RANK = {  # 越大越"高级"
    "core": 0,
    "local_vision": 1,
    "cloud_enhanced": 2,
}


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class ModeResolution:
    requested_mode: str            # 用户/env 请求的模式
    effective_mode: str            # 实际可用模式（已降级）
    status: str                    # healthy | degraded | failed
    degradation_reason: Optional[str] = None
    available_modes: list = None   # 环境能支持的所有模式
    checks: dict = None            # 详细检查结果

    def to_dict(self) -> dict:
        d = asdict(self)
        if d["available_modes"] is None:
            d["available_modes"] = []
        if d["checks"] is None:
            d["checks"] = {}
        return d


# ============================================================================
# 能力探测
# ============================================================================

def _check_core() -> tuple[bool, list[str]]:
    """Core 模式能力检查：不需要任何视觉依赖。"""
    reasons = []
    # 依赖检测（软探测：只 import，不要求版本）
    try:
        import docx  # noqa: F401
    except ImportError:
        reasons.append("python-docx 未安装")
    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        reasons.append("pdfplumber 未安装")
    try:
        import yaml  # noqa: F401
    except ImportError:
        reasons.append("pyyaml 未安装")
    return (len(reasons) == 0), reasons


def _check_local_vision() -> tuple[bool, list[str]]:
    """Local Vision 模式能力检查：PaddleOCR + 图像库。"""
    reasons = []
    # 环境变量开关
    if os.getenv("LOCAL_VISION_ENABLED", "false").lower() != "true":
        reasons.append("LOCAL_VISION_ENABLED != true")
    try:
        import paddleocr  # noqa: F401
    except ImportError:
        reasons.append("paddleocr 未安装（Phase 1 未启用视觉）")
    try:
        import cv2  # noqa: F401
    except ImportError:
        reasons.append("opencv-python-headless 未安装")
    return (len(reasons) == 0), reasons


def _check_cloud_vision() -> tuple[bool, list[str]]:
    """Cloud Enhanced 模式能力检查：Key + SDK + 上传开关。"""
    reasons = []
    if not os.getenv("ARK_API_KEY"):
        reasons.append("ARK_API_KEY 未配置")
    if not os.getenv("ARK_BASE_URL"):
        reasons.append("ARK_BASE_URL 未配置")
    if not os.getenv("ARK_VISION_MODEL_ID"):
        reasons.append("ARK_VISION_MODEL_ID 未配置")
    if os.getenv("ALLOW_CLOUD_UPLOAD", "false").lower() != "true":
        reasons.append("ALLOW_CLOUD_UPLOAD != true（部署者未授权上传）")
    try:
        import volcenginesdkarkruntime  # noqa: F401
    except ImportError:
        try:
            import volcengine  # noqa: F401
        except ImportError:
            reasons.append("volcengine-python-sdk 未安装")
    return (len(reasons) == 0), reasons


def _detect_available_modes() -> tuple[list[str], dict]:
    """返回可用模式列表 + 各模式检查详情。"""
    checks = {}
    available = []

    core_ok, core_reasons = _check_core()
    checks["core"] = {"available": core_ok, "reasons": core_reasons}
    if core_ok:
        available.append("core")

    local_ok, local_reasons = _check_local_vision()
    checks["local_vision"] = {"available": local_ok, "reasons": local_reasons}
    if local_ok and core_ok:
        available.append("local_vision")

    cloud_ok, cloud_reasons = _check_cloud_vision()
    checks["cloud_vision"] = {"available": cloud_ok, "reasons": cloud_reasons}
    if cloud_ok and core_ok:
        available.append("cloud_enhanced")

    return available, checks


# ============================================================================
# 主解析逻辑
# ============================================================================

def resolve_mode(requested_mode: Optional[str] = None) -> ModeResolution:
    """
    解析实际运行模式。

    Args:
        requested_mode: 用户请求的模式。None 时读取 RUNTIME_MODE，默认 core。

    Returns:
        ModeResolution 对象，包含 requested / effective / status / reason。
    """
    if requested_mode is None:
        requested_mode = os.getenv("RUNTIME_MODE", "core").lower().strip()

    if requested_mode not in VALID_MODES:
        return ModeResolution(
            requested_mode=requested_mode,
            effective_mode="core",
            status="failed",
            degradation_reason=(
                f"未知的 RUNTIME_MODE={requested_mode!r}，"
                f"允许值：{'/'.join(VALID_MODES)}"
            ),
            available_modes=[],
            checks={},
        )

    available, checks = _detect_available_modes()

    # 连 core 都不可用 → failed
    if "core" not in available:
        return ModeResolution(
            requested_mode=requested_mode,
            effective_mode="core",
            status="failed",
            degradation_reason=(
                "Core 模式必要依赖缺失："
                + " · ".join(checks.get("core", {}).get("reasons", []))
            ),
            available_modes=available,
            checks=checks,
        )

    # auto 模式：选可用最高级
    if requested_mode == "auto":
        if "cloud_enhanced" in available:
            effective = "cloud_enhanced"
        elif "local_vision" in available:
            effective = "local_vision"
        else:
            effective = "core"
        return ModeResolution(
            requested_mode="auto",
            effective_mode=effective,
            status="healthy",
            degradation_reason=None,
            available_modes=available,
            checks=checks,
        )

    # 显式请求模式：能满足就 healthy，不能满足降级为 degraded
    if requested_mode in available:
        return ModeResolution(
            requested_mode=requested_mode,
            effective_mode=requested_mode,
            status="healthy",
            degradation_reason=None,
            available_modes=available,
            checks=checks,
        )

    # 需要降级
    # cloud_enhanced 不可用 → 尝试 local_vision
    if requested_mode == "cloud_enhanced":
        cloud_reasons = " · ".join(checks["cloud_vision"]["reasons"])
        if "local_vision" in available:
            return ModeResolution(
                requested_mode="cloud_enhanced",
                effective_mode="local_vision",
                status="degraded",
                degradation_reason=f"Cloud Enhanced 不可用：{cloud_reasons}",
                available_modes=available,
                checks=checks,
            )
        return ModeResolution(
            requested_mode="cloud_enhanced",
            effective_mode="core",
            status="degraded",
            degradation_reason=(
                f"Cloud 和 Local 均不可用：Cloud[{cloud_reasons}]"
                f" · Local[{' · '.join(checks['local_vision']['reasons'])}]"
            ),
            available_modes=available,
            checks=checks,
        )

    # local_vision 不可用 → 降 core
    if requested_mode == "local_vision":
        local_reasons = " · ".join(checks["local_vision"]["reasons"])
        return ModeResolution(
            requested_mode="local_vision",
            effective_mode="core",
            status="degraded",
            degradation_reason=f"Local Vision 不可用：{local_reasons}",
            available_modes=available,
            checks=checks,
        )

    # 兜底
    return ModeResolution(
        requested_mode=requested_mode,
        effective_mode="core",
        status="degraded",
        degradation_reason="未知的降级路径",
        available_modes=available,
        checks=checks,
    )


# ============================================================================
# CLI
# ============================================================================

def _format_human(res: ModeResolution) -> str:
    lines = [
        "=" * 60,
        "M3 · Mode Resolver",
        "=" * 60,
        f"请求模式（requested_mode）: {res.requested_mode}",
        f"实际模式（effective_mode）: {res.effective_mode}",
        f"状态                       : {res.status}",
    ]
    if res.degradation_reason:
        lines.append(f"降级原因                   : {res.degradation_reason}")
    lines.append(f"可用模式集合               : {res.available_modes}")
    lines.append("")
    lines.append("模式检查详情：")
    for mode, detail in (res.checks or {}).items():
        avail = "✅" if detail.get("available") else "❌"
        reasons = detail.get("reasons") or []
        lines.append(f"  [{avail}] {mode}")
        for r in reasons:
            lines.append(f"       · {r}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="M3 Mode Resolver")
    parser.add_argument(
        "--mode",
        default=None,
        help="覆盖 RUNTIME_MODE 请求。可选：core|local_vision|cloud_enhanced|auto",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    res = resolve_mode(requested_mode=args.mode)

    if args.json:
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_format_human(res))

    # 返回码：healthy=0 / degraded=0 / failed=1
    sys.exit(0 if res.status != "failed" else 1)


if __name__ == "__main__":
    main()
