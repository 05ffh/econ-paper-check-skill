"""tests for vision_quality_gate_lint."""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.vision_quality_gate_lint import lint_file  # noqa


def _write_result(tmp_path: Path, evidences: list[dict]) -> Path:
    payload = {"provider": "ark_cloud", "available": True, "evidences": evidences}
    p = tmp_path / "vision_result.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _base_evidence(**overrides):
    e = {
        "page_number": 1,
        "latency_ms": 5000,
        "quality_profile": {
            "extraction_quality_score": 0.8,
            "critical_field_score": 1.0,
            "hard_gates_passed": True,
        },
        "table_preview": {"n_rows": 5, "n_cols": 3, "cells": []},
        "kb_eligibility": {"kb_a_evidence_eligible": True},
        "usage": {"total_tokens": 1000},
        "provenance": {"runtime_mode": "basic"},
        "quota_used": 1,
        "quota_limit": 40,
    }
    for k, v in overrides.items():
        e[k] = v
    return e


def test_clean_passes(tmp_path):
    p = _write_result(tmp_path, [_base_evidence()])
    fails, _ = lint_file(p)
    assert fails == [], f"unexpected fails: {fails}"


def test_L01_gate_pass_low_quality(tmp_path):
    e = _base_evidence(quality_profile={"extraction_quality_score": 0.3, "critical_field_score": 1.0, "hard_gates_passed": True})
    p = _write_result(tmp_path, [e])
    fails, _ = lint_file(p)
    assert any("L01" in f for f in fails)


def test_L02_gate_pass_empty_preview(tmp_path):
    e = _base_evidence()
    e["table_preview"] = None
    p = _write_result(tmp_path, [e])
    fails, _ = lint_file(p)
    assert any("L02" in f for f in fails)


def test_L03_gate_pass_zero_dims(tmp_path):
    e = _base_evidence()
    e["table_preview"] = {"n_rows": 0, "n_cols": 0, "cells": []}
    p = _write_result(tmp_path, [e])
    fails, _ = lint_file(p)
    assert any("L03" in f for f in fails)


def test_L04_gate_fail_but_critical_full(tmp_path):
    e = _base_evidence(quality_profile={"extraction_quality_score": 0.2, "critical_field_score": 1.0, "hard_gates_passed": False})
    p = _write_result(tmp_path, [e])
    fails, _ = lint_file(p)
    assert any("L04" in f for f in fails)


def test_L05_latency_alert(tmp_path):
    e = _base_evidence(latency_ms=65000)
    p = _write_result(tmp_path, [e])
    fails, _ = lint_file(p)
    assert any("L05" in f for f in fails)


def test_L06_low_quality_but_kb_eligible(tmp_path):
    e = _base_evidence(quality_profile={"extraction_quality_score": 0.4, "critical_field_score": 0.9, "hard_gates_passed": False})
    e["kb_eligibility"] = {"kb_a_evidence_eligible": True}
    p = _write_result(tmp_path, [e])
    fails, _ = lint_file(p)
    assert any("L06" in f for f in fails)


def test_L07_quota_overrun(tmp_path):
    e = _base_evidence()
    e["quota_used"] = 41
    e["quota_limit"] = 40
    p = _write_result(tmp_path, [e])
    fails, _ = lint_file(p)
    assert any("L07" in f for f in fails)


def test_L08_variance_alert(tmp_path):
    evs = [
        _base_evidence(page_number=1, quality_profile={"extraction_quality_score": 0.9, "critical_field_score": 1.0, "hard_gates_passed": True}),
        _base_evidence(page_number=2, quality_profile={"extraction_quality_score": 0.2, "critical_field_score": 1.0, "hard_gates_passed": True}),
    ]
    p = _write_result(tmp_path, evs)
    fails, _ = lint_file(p)
    assert any("L08" in f for f in fails)


def test_L09_missing_tokens(tmp_path):
    e = _base_evidence()
    e["usage"] = {}
    p = _write_result(tmp_path, [e])
    fails, _ = lint_file(p)
    assert any("L09" in f for f in fails)


def test_L10_bad_runtime_mode(tmp_path):
    e = _base_evidence()
    e["provenance"] = {"runtime_mode": "malicious_injected"}
    p = _write_result(tmp_path, [e])
    fails, _ = lint_file(p)
    assert any("L10" in f for f in fails)
