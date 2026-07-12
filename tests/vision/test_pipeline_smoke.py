"""tests/vision/test_pipeline_smoke.py · v1.6.0-rc.3 · v0.3.1 轻量化

不依赖 paddleocr / openai 真实 SDK。仅走 MockProvider → normalizer → quality_scorer → knowledge_bridge。

已删除（v0.3.1）：
- paddle_provider 相关 3 个测试
- ALLOW_CLOUD_UPLOAD 相关断言

运行：
    python -m pytest tests/vision/test_pipeline_smoke.py -v
    # 或不装 pytest 时：
    python tests/vision/test_pipeline_smoke.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "vision"))
sys.path.insert(0, str(REPO / "scripts" / "vision" / "providers"))

from base import VisionRequest, TaskKind, ProviderError, ProviderErrorKind
from mock_provider import MockProvider
from ark_provider import ArkCloudProvider
from normalizer import normalize
from quality_scorer import score
from knowledge_bridge import compute_kb_eligibility, build_vision_student_evidence


# ============================================================================
# MockProvider 端到端
# ============================================================================

def _run_pipeline(task_kind: TaskKind) -> dict:
    p = MockProvider()
    req = VisionRequest(
        artifact_ref="/tmp/test.png",
        task_kind=task_kind,
        page_number=1,
    )
    resp = p.recognize(req)
    unified = normalize(resp, runtime_mode="basic")
    score(unified)
    compute_kb_eligibility(unified)
    return unified


def test_mock_provider_available():
    p = MockProvider()
    ok, reasons = p.available()
    assert ok is True
    assert reasons == []


def test_pipeline_table():
    u = _run_pipeline(TaskKind.TABLE_STRUCTURE)
    assert u["schema_version"] == "vision.v1"
    assert u["artifact_type"] == "table"
    assert len(u["cells"]) > 0
    c0 = u["cells"][0]
    assert "row" in c0 and "col" in c0 and "text" in c0
    assert "headers" in u["derived_views"]
    assert "rows" in u["derived_views"]
    assert u["quality_profile"]["extraction_quality_score"] > 0.5
    assert u["kb_eligibility"]["kb_a_query_eligible"] is True


def test_pipeline_ocr_page():
    u = _run_pipeline(TaskKind.OCR_FULL_PAGE)
    assert u["artifact_type"] == "ocr_page"
    assert len(u["ocr_blocks"]) > 0
    assert u["quality_profile"]["hard_gates_passed"] is True


def test_pipeline_formula():
    u = _run_pipeline(TaskKind.FORMULA)
    assert u["artifact_type"] == "formula"
    assert u["formula"]["latex"]
    latex = u["formula"]["latex"]
    assert latex.count("{") == latex.count("}")


def test_pipeline_reference_block():
    u = _run_pipeline(TaskKind.REFERENCE_BLOCK)
    assert u["artifact_type"] == "reference_block"
    assert len(u["references"]) > 0
    assert all(r.get("raw_text") for r in u["references"])


def test_student_evidence_shape():
    u = _run_pipeline(TaskKind.TABLE_STRUCTURE)
    ev = build_vision_student_evidence(u)
    for k in [
        "source_type", "parsed_text", "page_number", "bbox",
        "artifact_ref", "provenance", "quality_profile",
        "requires_visual_review", "review_notice",
    ]:
        assert k in ev, f"missing field {k}"
    assert ev["source_type"] == "vision"
    assert "视觉解析" not in ev["parsed_text"]
    assert "视觉解析" in ev["review_notice"]


# ============================================================================
# Ark Provider · v0.3.1 收窄任务 + 未配置降级
# ============================================================================

def test_ark_provider_unavailable_no_config():
    """无 Ark 配置时 available() 返回 False + 原因清单（不再包含 ALLOW_CLOUD_UPLOAD）。"""
    saved = {}
    for k in ("VISION_ENABLED", "ARK_API_KEY", "ARK_VISION_MODEL_ID"):
        saved[k] = os.environ.pop(k, None)
    try:
        p = ArkCloudProvider()
        ok, reasons = p.available()
        assert ok is False
        assert any("VISION_ENABLED" in r for r in reasons)
        # v0.3.1: ALLOW_CLOUD_UPLOAD 已删除
        assert not any("ALLOW_CLOUD_UPLOAD" in r for r in reasons)
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_ark_provider_m31_only_supports_two_tasks():
    """v0.3.1 P0-4: Ark Provider M3.1 仅支持 OCR_REGION + TABLE_STRUCTURE。"""
    p = ArkCloudProvider()
    assert p.supports(TaskKind.OCR_REGION) is True
    assert p.supports(TaskKind.TABLE_STRUCTURE) is True
    # 其余 4 种全部不支持（延期 M3.2+）
    assert p.supports(TaskKind.OCR_FULL_PAGE) is False
    assert p.supports(TaskKind.LAYOUT) is False
    assert p.supports(TaskKind.FORMULA) is False
    assert p.supports(TaskKind.REFERENCE_BLOCK) is False


def test_ark_provider_recognize_not_configured():
    """未配置时 recognize() 抛 NOT_CONFIGURED。"""
    saved = {}
    for k in ("VISION_ENABLED", "ARK_API_KEY", "ARK_VISION_MODEL_ID"):
        saved[k] = os.environ.pop(k, None)
    try:
        p = ArkCloudProvider()
        raised = False
        try:
            p.recognize(VisionRequest(
                artifact_ref="/tmp/x.png",
                task_kind=TaskKind.OCR_REGION,
            ))
        except ProviderError as e:
            raised = True
            assert e.kind == ProviderErrorKind.NOT_CONFIGURED
        assert raised
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


# ============================================================================
# KB eligibility 门禁
# ============================================================================

def test_kb_eligibility_low_quality_rejection():
    """人工构造低质量 profile，验证门禁拒绝。"""
    u = {
        "provenance": {},
        "artifact_type": "table",
        "quality_profile": {
            "extraction_quality_score": 0.5,
            "critical_field_score": 0.4,
            "hard_gates_passed": False,
            "structural_issues": ["缺少表头"],
            "recognition_coverage": 0.4,
        },
    }
    result = compute_kb_eligibility(u)
    assert result["kb_a_query_eligible"] is True
    assert result["kb_a_evidence_eligible"] is False
    assert result["kb_b_eligible"] is False
    assert len(result["reasons"]) > 0


# ============================================================================
# CLI 兼容
# ============================================================================

if __name__ == "__main__":
    tests = [
        test_mock_provider_available,
        test_pipeline_table,
        test_pipeline_ocr_page,
        test_pipeline_formula,
        test_pipeline_reference_block,
        test_student_evidence_shape,
        test_ark_provider_unavailable_no_config,
        test_ark_provider_m31_only_supports_two_tasks,
        test_ark_provider_recognize_not_configured,
        test_kb_eligibility_low_quality_rejection,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
        except AssertionError as e:
            print(f"  ❌ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print("---")
    print(f"通过：{len(tests) - failed}/{len(tests)}")
    sys.exit(0 if failed == 0 else 1)
