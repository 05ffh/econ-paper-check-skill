#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_ark_mock_openai.py · M3 v1.6.0 · Ark Provider 契约测试（无真 Key）

通过 monkey-patch `openai.OpenAI` 让 CI 环境（无 ARK_API_KEY）也能验证：
- 正常 chat/completions 调用路径
- 错误映射（RateLimit / Auth / Timeout / Network / BadRequest / InternalServer）
- 幂等 hash 生成
- 系统提示注入锚定
- M3.1 任务收窄

不需要真实 Ark Key。
"""
import base64
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "vision" / "providers"))

from base import (  # noqa: E402
    ProviderError,
    ProviderErrorKind,
    TaskKind,
    VisionRequest,
)


# =========================================================================
# 通用 fixtures
# =========================================================================

@pytest.fixture
def env_configured(monkeypatch, tmp_path):
    """配齐 Ark 所需 env（假 Key）。"""
    monkeypatch.setenv("VISION_ENABLED", "true")
    monkeypatch.setenv("ARK_API_KEY", "sk-fake-for-testing-only-xxxxxxxxxxxxxxxx")
    monkeypatch.setenv("ARK_VISION_MODEL_ID", "mock-model-1234")
    monkeypatch.setenv("ARK_BASE_URL", "https://ark.example.com/api/v3")
    monkeypatch.setenv("VISION_REQUEST_TIMEOUT_SECONDS", "10")
    return tmp_path


@pytest.fixture
def synthetic_png(tmp_path) -> Path:
    """生成一个 100x100 的假图片。"""
    img = Image.new("RGB", (100, 100), "white")
    p = tmp_path / "fake.png"
    img.save(p, "PNG")
    return p


@pytest.fixture
def mock_openai_success():
    """monkey-patch openai.OpenAI，返回一个合法的 table_structure JSON。"""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "task": "table_structure",
        "n_rows": 2, "n_cols": 2,
        "cells": [
            {"row": 0, "col": 0, "text": "A"},
            {"row": 0, "col": 1, "text": "B"},
            {"row": 1, "col": 0, "text": "1"},
            {"row": 1, "col": 1, "text": "2"},
        ],
        "caption": "mock table"
    })
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    mock_response.usage.total_tokens = 150

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# =========================================================================
# 契约测试
# =========================================================================

def test_provider_available_when_configured(env_configured):
    """env 齐全 + openai 装了 → available=True"""
    from ark_provider import ArkCloudProvider
    p = ArkCloudProvider()
    ok, reasons = p.available()
    assert ok, f"应可用，但 reasons: {reasons}"


def test_provider_unavailable_missing_env(monkeypatch):
    """env 缺 → available=False，reasons 列举"""
    monkeypatch.delenv("VISION_ENABLED", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("ARK_VISION_MODEL_ID", raising=False)
    from ark_provider import ArkCloudProvider
    p = ArkCloudProvider()
    ok, reasons = p.available()
    assert not ok
    assert any("VISION_ENABLED" in r for r in reasons)


def test_recognize_success_with_mock_openai(env_configured, synthetic_png, mock_openai_success):
    """正常调用路径：openai 返回合法 JSON → normalize 通过 → hash 稳定"""
    from ark_provider import ArkCloudProvider

    with patch("openai.OpenAI", return_value=mock_openai_success):
        p = ArkCloudProvider()
        req = VisionRequest(
            artifact_ref=str(synthetic_png),
            task_kind=TaskKind.TABLE_STRUCTURE,
            page_number=1,
        )
        resp = p.recognize(req)

    assert resp.raw["task"] == "table_structure"
    assert resp.raw["n_rows"] == 2
    assert resp.raw["n_cols"] == 2
    assert len(resp.raw["cells"]) == 4
    assert resp.provider_name == "ark_cloud"
    assert resp.model_id == "mock-model-1234"
    assert resp.raw_response_hash  # 存在
    assert len(resp.raw_response_hash) == 64  # sha256 hex
    assert resp.metadata["usage"]["total_tokens"] == 150


def test_recognize_idempotent_hash(env_configured, synthetic_png, mock_openai_success):
    """幂等：同一 mock 返回，两次 recognize 的 raw_response_hash 相同"""
    from ark_provider import ArkCloudProvider

    with patch("openai.OpenAI", return_value=mock_openai_success):
        p = ArkCloudProvider()
        req = VisionRequest(
            artifact_ref=str(synthetic_png),
            task_kind=TaskKind.TABLE_STRUCTURE,
        )
        r1 = p.recognize(req)

        p2 = ArkCloudProvider()  # 新实例
        r2 = p2.recognize(req)

    assert r1.raw_response_hash == r2.raw_response_hash


def test_system_prompt_sent_to_openai(env_configured, synthetic_png, mock_openai_success):
    """openai 调用参数里必须含 _SYSTEM_PROMPT_STRICT（提示注入锚定）"""
    from ark_provider import ArkCloudProvider, _SYSTEM_PROMPT_STRICT

    with patch("openai.OpenAI", return_value=mock_openai_success):
        p = ArkCloudProvider()
        req = VisionRequest(
            artifact_ref=str(synthetic_png),
            task_kind=TaskKind.TABLE_STRUCTURE,
        )
        p.recognize(req)

    # 断言 openai.chat.completions.create 被调用，且 messages[0] 是 system prompt
    call_args = mock_openai_success.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == _SYSTEM_PROMPT_STRICT


def test_recognize_unsupported_task_raises(env_configured, synthetic_png):
    """M3.1 收窄：FORMULA 请求 → UNSUPPORTED_TASK"""
    from ark_provider import ArkCloudProvider

    p = ArkCloudProvider()
    req = VisionRequest(
        artifact_ref=str(synthetic_png),
        task_kind=TaskKind.FORMULA,
    )
    with pytest.raises(ProviderError) as exc:
        p.recognize(req)
    assert exc.value.kind == ProviderErrorKind.UNSUPPORTED_TASK


# =========================================================================
# 错误映射测试
# =========================================================================

def _make_mock_client_that_raises(exc_class, *args, **kwargs):
    """构造一个会抛特定 openai 异常的 mock client"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = exc_class(*args, **kwargs)
    return mock_client


def test_error_mapping_rate_limit(env_configured, synthetic_png):
    """openai.RateLimitError → ProviderError(QUOTA, retriable=True)"""
    from ark_provider import ArkCloudProvider
    import openai

    # RateLimitError 的构造签名较复杂，走一个通用替身
    class FakeRateLimit(openai.RateLimitError):
        def __init__(self):
            pass  # 跳过父类初始化
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = FakeRateLimit()

    with patch("openai.OpenAI", return_value=mock_client):
        p = ArkCloudProvider()
        req = VisionRequest(artifact_ref=str(synthetic_png), task_kind=TaskKind.TABLE_STRUCTURE)
        with pytest.raises(ProviderError) as exc:
            p.recognize(req)
        assert exc.value.kind == ProviderErrorKind.QUOTA
        assert exc.value.retriable is True


def test_error_mapping_auth(env_configured, synthetic_png):
    """openai.AuthenticationError → UNAUTHORIZED, retriable=False"""
    from ark_provider import ArkCloudProvider
    import openai

    class FakeAuth(openai.AuthenticationError):
        def __init__(self):
            pass
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = FakeAuth()

    with patch("openai.OpenAI", return_value=mock_client):
        p = ArkCloudProvider()
        req = VisionRequest(artifact_ref=str(synthetic_png), task_kind=TaskKind.TABLE_STRUCTURE)
        with pytest.raises(ProviderError) as exc:
            p.recognize(req)
        assert exc.value.kind == ProviderErrorKind.UNAUTHORIZED
        assert exc.value.retriable is False


def test_error_mapping_timeout(env_configured, synthetic_png):
    """openai.APITimeoutError → TIMEOUT, retriable=True"""
    from ark_provider import ArkCloudProvider
    import openai

    class FakeTimeout(openai.APITimeoutError):
        def __init__(self):
            pass
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = FakeTimeout()

    with patch("openai.OpenAI", return_value=mock_client):
        p = ArkCloudProvider()
        req = VisionRequest(artifact_ref=str(synthetic_png), task_kind=TaskKind.TABLE_STRUCTURE)
        with pytest.raises(ProviderError) as exc:
            p.recognize(req)
        assert exc.value.kind == ProviderErrorKind.TIMEOUT
        assert exc.value.retriable is True


def test_error_mapping_connection(env_configured, synthetic_png):
    """openai.APIConnectionError → NETWORK, retriable=True"""
    from ark_provider import ArkCloudProvider
    import openai

    class FakeConn(openai.APIConnectionError):
        def __init__(self):
            pass
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = FakeConn()

    with patch("openai.OpenAI", return_value=mock_client):
        p = ArkCloudProvider()
        req = VisionRequest(artifact_ref=str(synthetic_png), task_kind=TaskKind.TABLE_STRUCTURE)
        with pytest.raises(ProviderError) as exc:
            p.recognize(req)
        assert exc.value.kind == ProviderErrorKind.NETWORK
        assert exc.value.retriable is True


# =========================================================================
# JSON 解析兜底
# =========================================================================

def test_parse_response_with_json_codeblock(env_configured, synthetic_png):
    """模型带 ```json ...``` 包裹时也能正确解析"""
    from ark_provider import ArkCloudProvider

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        '```json\n'
        '{"task": "ocr_region", "text": "hello world", "line_count": 1}\n'
        '```'
    )
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 50
    mock_response.usage.completion_tokens = 20
    mock_response.usage.total_tokens = 70

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        p = ArkCloudProvider()
        req = VisionRequest(artifact_ref=str(synthetic_png), task_kind=TaskKind.OCR_REGION)
        resp = p.recognize(req)

    assert resp.raw["task"] == "ocr_region"
    assert resp.raw["text"] == "hello world"


def test_parse_response_with_garbage_content(env_configured, synthetic_png):
    """完全垃圾的 content → 兜底不 raise，返回带 warnings 的空结构"""
    from ark_provider import ArkCloudProvider

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "this is not json at all!"
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_response.usage.total_tokens = 15

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        p = ArkCloudProvider()
        req = VisionRequest(artifact_ref=str(synthetic_png), task_kind=TaskKind.TABLE_STRUCTURE)
        resp = p.recognize(req)  # 不 raise，quality_scorer 会打低分

    assert resp.raw.get("warnings") == ["json_parse_failed"]


def test_parse_response_empty_content(env_configured, synthetic_png):
    """content 为空字符串 → 兜底返回 empty_response warning"""
    from ark_provider import ArkCloudProvider

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = ""
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 0
    mock_response.usage.total_tokens = 10

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        p = ArkCloudProvider()
        req = VisionRequest(artifact_ref=str(synthetic_png), task_kind=TaskKind.TABLE_STRUCTURE)
        resp = p.recognize(req)

    assert resp.raw.get("warnings") == ["empty_response"]


# =========================================================================
# 幂等 & 契约
# =========================================================================

def test_provider_supports_only_m31_tasks():
    """M3.1 supports() 严格：仅 OCR_REGION + TABLE_STRUCTURE"""
    from ark_provider import ArkCloudProvider

    p = ArkCloudProvider()
    assert p.supports(TaskKind.OCR_REGION)
    assert p.supports(TaskKind.TABLE_STRUCTURE)
    assert not p.supports(TaskKind.FORMULA)
    assert not p.supports(TaskKind.LAYOUT)
    assert not p.supports(TaskKind.OCR_FULL_PAGE)
    assert not p.supports(TaskKind.REFERENCE_BLOCK)


def test_provider_no_confidence_in_output(env_configured, synthetic_png, mock_openai_success):
    """Provider 契约：raw 中不应含 confidence / level / red-yellow-gray 等禁字段"""
    from ark_provider import ArkCloudProvider

    with patch("openai.OpenAI", return_value=mock_openai_success):
        p = ArkCloudProvider()
        req = VisionRequest(artifact_ref=str(synthetic_png), task_kind=TaskKind.TABLE_STRUCTURE)
        resp = p.recognize(req)

    forbidden = {"confidence", "level", "red", "yellow", "gray", "green", "quality"}
    raw_flat = json.dumps(resp.raw, ensure_ascii=False).lower()
    for f in forbidden:
        assert f'"{f}"' not in raw_flat, f"raw 输出含禁字段: {f}"
