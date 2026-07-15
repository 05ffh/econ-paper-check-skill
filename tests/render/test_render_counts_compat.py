"""
回归测试：报告渲染器的 counts 字段兼容性。

Bug 回顾：
  diagnostic_result.json 里字段名是 `counts`（如 {"pass":3,"red":3,"yellow":6,...}），
  但 scripts/render_report.py 和 scripts/render_report_html.py 早期只读
  `summary_counts`，导致「类别|数量」表格全部渲染成 0。
  修复后两处应同时兼容 `counts` 和 `summary_counts` 两种字段名。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# 尝试导入渲染器，缺依赖时跳过（docx 不是运行时必需）
docx = pytest.importorskip("docx", reason="python-docx 未安装，跳过 renderer 兼容性测试")

import sys
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from scripts import render_report  # type: ignore  # noqa: E402
from scripts import render_report_html  # type: ignore  # noqa: E402


def _base_result() -> dict:
    """构造最小化 diagnostic_result 骨架，供渲染器消费。"""
    return {
        "paper_meta": {
            "title": "测试论文",
            "author": "测试作者",
            "student_id": "TEST-001",
        },
        "paper_profile": {
            "paper_type": "实证研究",
            "data_type": "微观截面",
            "detected_methods": ["OLS"],
            "trigger_plan": {
                "triggered_rule_groups": ["citation"],
                "not_applicable_rule_groups": [],
                "manual_confirmation_items": [],
            },
        },
        "overall_risk_level": "低",
        "pass_items": [],
        "issues": [],
        "manual_confirmation_items": [],
        "skill_boundary_notice": [],
    }


def _extract_counts_table_from_docx(docx_path: Path) -> dict:
    """从生成的 docx 里找『类别|数量』表并解析为 dict。"""
    d = docx.Document(str(docx_path))
    for table in d.tables:
        header = [c.text.strip() for c in table.rows[0].cells]
        if header[:2] == ["类别", "数量"]:
            return {
                row.cells[0].text.strip(): row.cells[1].text.strip()
                for row in table.rows[1:]
            }
    raise AssertionError("未找到『类别|数量』表格")


def _extract_counts_chips_from_html(html_path: Path) -> dict:
    """从 html 报告里抽出 chip 计数。"""
    text = html_path.read_text(encoding="utf-8")
    result = {}
    for label in ["通过", "红色", "黄色", "绿色", "灰色", "不适用"]:
        m = re.search(rf"{label}\s*(\d+)", text)
        if m:
            result[label] = int(m.group(1))
    return result


# --- docx 渲染器 -------------------------------------------------

def test_render_docx_reads_counts_field(tmp_path):
    """新格式：字段名是 `counts`。渲染器必须读到。"""
    result = _base_result()
    result["counts"] = {
        "pass": 3, "red": 3, "yellow": 6, "green": 3, "manual": 2, "na": 0,
    }
    out = tmp_path / "r.docx"
    render_report.write_report(result, "test.docx", out)
    parsed = _extract_counts_table_from_docx(out)
    assert parsed["通过项"] == "3"
    assert parsed["红色必改问题"] == "3"
    assert parsed["黄色建议补充"] == "6"
    assert parsed["绿色优化提升"] == "3"
    assert parsed["灰色需人工确认"] == "2"
    assert parsed["不适用项"] == "0"


def test_render_docx_reads_summary_counts_field(tmp_path):
    """旧格式：字段名是 `summary_counts`。向后兼容必须仍然工作。"""
    result = _base_result()
    result["summary_counts"] = {
        "pass": 1, "red": 2, "yellow": 4, "green": 5, "manual": 6, "na": 7,
    }
    out = tmp_path / "r.docx"
    render_report.write_report(result, "test.docx", out)
    parsed = _extract_counts_table_from_docx(out)
    assert parsed["通过项"] == "1"
    assert parsed["红色必改问题"] == "2"
    assert parsed["黄色建议补充"] == "4"
    assert parsed["绿色优化提升"] == "5"
    assert parsed["灰色需人工确认"] == "6"
    assert parsed["不适用项"] == "7"


def test_render_docx_summary_counts_wins_when_both_present(tmp_path):
    """两个字段都存在时，优先用 `summary_counts`（旧契约）。"""
    result = _base_result()
    result["summary_counts"] = {"pass": 9, "red": 9, "yellow": 9, "green": 9, "manual": 9, "na": 9}
    result["counts"] = {"pass": 1, "red": 1, "yellow": 1, "green": 1, "manual": 1, "na": 1}
    out = tmp_path / "r.docx"
    render_report.write_report(result, "test.docx", out)
    parsed = _extract_counts_table_from_docx(out)
    assert parsed["通过项"] == "9"
    assert parsed["红色必改问题"] == "9"


def test_render_docx_missing_counts_field_falls_back_to_zero(tmp_path):
    """两个字段都缺失时，全部 0（保持旧行为，避免炸报告）。"""
    result = _base_result()
    out = tmp_path / "r.docx"
    render_report.write_report(result, "test.docx", out)
    parsed = _extract_counts_table_from_docx(out)
    for v in parsed.values():
        assert v == "0"


# --- html 渲染器 -------------------------------------------------

def test_render_html_reads_counts_field(tmp_path):
    result = _base_result()
    result["counts"] = {
        "pass": 3, "red": 3, "yellow": 6, "green": 3, "manual": 2, "na": 0,
    }
    out = tmp_path / "r.html"
    render_report_html.write_html(result, "test.docx", out)
    parsed = _extract_counts_chips_from_html(out)
    assert parsed["通过"] == 3
    assert parsed["红色"] == 3
    assert parsed["黄色"] == 6
    assert parsed["绿色"] == 3
    assert parsed["灰色"] == 2
    assert parsed["不适用"] == 0


def test_render_html_reads_summary_counts_field(tmp_path):
    result = _base_result()
    result["summary_counts"] = {
        "pass": 1, "red": 2, "yellow": 4, "green": 5, "manual": 6, "na": 7,
    }
    out = tmp_path / "r.html"
    render_report_html.write_html(result, "test.docx", out)
    parsed = _extract_counts_chips_from_html(out)
    assert parsed["通过"] == 1
    assert parsed["红色"] == 2
    assert parsed["黄色"] == 4
    assert parsed["绿色"] == 5
    assert parsed["灰色"] == 6
    assert parsed["不适用"] == 7
