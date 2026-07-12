"""tests/vision/test_pipeline_smoke.py · Phase 2 端到端骨架冒烟测试

不依赖 paddleocr / volcengine SDK。仅走 MockProvider → normalizer → quality_scorer → knowledge_bridge。

运行：
    python -m pytest tests/vision/test_pipeline_smoke.py -v
    # 或不装 pytest 时：
    python tests/vision/test_pipeline_smoke.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "vision"))
sys.path.insert(0, str(REPO / "scripts" / "vision" / "providers"))

from base import VisionRequest, TaskKind, ProviderError
from mock_provider import MockProvider
from paddle_provider import PaddleLocalProvider
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
    unified = normalize(resp, runtime_mode="core")
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
    # cells 事实层
    c0 = u["cells"][0]
    assert "row" in c0 and "col" in c0 and "text" in c0
    # derived_views 是衍生
    assert "headers" in u["derived_views"]
    assert "rows" in u["derived_views"]
    # quality_profile 已填
    assert u["quality_profile"]["extraction_quality_score"] > 0.5
    # kb_eligibility
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
    # 大括号平衡检查
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
    # 决策 8 要求的字段
    for k in [
        "source_type", "parsed_text", "page_number", "bbox",
        "artifact_ref", "provenance", "quality_profile",
        "requires_visual_review", "review_notice",
    ]:
        assert k in ev, f"missing field {k}"
    assert ev["source_type"] == "vision"
    # 硬编码警告语禁令：不在 parsed_text 中
    assert "视觉解析" not in ev["parsed_text"]
    # review_notice 承载警告
    assert "视觉解析" in ev["review_notice"]


# ============================================================================
# 骨架 Provider 不可用性验证
# ============================================================================

def test_paddle_provider_unavailable_phase1():
    """Phase 2 未启用 PaddleOCR，available() 必须返回 False + 原因清单。"""
    p = PaddleLocalProvider()
    ok, reasons = p.available()
    assert ok is False
    assert any("LOCAL_VISION_ENABLED" in r or "paddleocr" in r for r in reasons)


def test_ark_provider_unavailable_no_config():
    """无 Ark 配置时，available() 必须返回 False + 明确原因。"""
    import os
    # 临时清空 ARK_API_KEY 检验
    old = os.environ.get("ARK_API_KEY")
    if "ARK_API_KEY" in os.environ:
        del os.environ["ARK_API_KEY"]
    try:
        p = ArkCloudProvider()
        ok, reasons = p.available()
        assert ok is False
        assert any("ARK_" in r or "ALLOW_CLOUD_UPLOAD" in r for r in reasons)
    finally:
        if old is not None:
            os.environ["ARK_API_KEY"] = old


def test_paddle_recognize_raises_not_installed():
    from base import ProviderErrorKind
    p = PaddleLocalProvider()
    try:
        p.recognize(VisionRequest(
            artifact_ref="/tmp/x.png",
            task_kind=TaskKind.OCR_FULL_PAGE,
        ))
        raised = False
    except ProviderError as e:
        raised = True
        assert e.kind == ProviderErrorKind.NOT_INSTALLED
    assert raised


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
# CLI 兼容（无 pytest 也能跑）
# ============================================================================

if __name__ == "__main__":
    tests = [
        test_mock_provider_available,
        test_pipeline_table,
        test_pipeline_ocr_page,
        test_pipeline_formula,
        test_pipeline_reference_block,
        test_student_evidence_shape,
        test_paddle_provider_unavailable_phase1,
        test_ark_provider_unavailable_no_config,
        test_paddle_recognize_raises_not_installed,
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
