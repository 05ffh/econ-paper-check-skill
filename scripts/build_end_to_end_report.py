#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_end_to_end_report.py · M3 v1.6.0-rc.3 · Phase C 端到端报告集成

**职责**：从 parse_paper 的 units + vision_pipeline 的 vision_result → 生成
diagnostic_result.json，然后调 render_report.py 和 render_report_html.py 输出报告。

**特点**：
- 视觉 issue 的 evidence 字段带 [视觉解析·请核对原图] 前缀 + parsed_text 摘要
- 视觉证据附上 artifact_ref（缩略图路径）供 HTML 版展示
- 判断内核逻辑简化版：文本规则 + 视觉证据 → 灰色 issue 生成
- 支持 --with-vision / --without-vision 两分支对照

这不是替代判断内核，是 M3 视觉的**端到端演示**，用于本 turn 的验收。
真实生产判断由 rules/ + agent_instructions/ 走。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))


# =============================================================================
# 简化版判断内核（仅演示用；生产由 agent + rules 决策）
# =============================================================================

def _detect_paper_profile(units: list) -> dict:
    """从 units 抽取论文画像。"""
    all_text = " ".join(u.get("text", "") for u in units if isinstance(u, dict))

    profile = {
        "paper_type": "本科毕业论文",
        "data_type": "面板数据" if "面板" in all_text or "panel" in all_text.lower() else "不确定，需人工确认",
        "sample_object": "商业银行" if "商业银行" in all_text else "不确定，需人工确认",
        "sample_period": "不确定，需人工确认",
        "detected_methods": [],
    }
    if "固定效应" in all_text and "随机效应" in all_text:
        profile["detected_methods"].append("固定效应/随机效应面板")
    if "Hausman" in all_text or "豪斯曼" in all_text:
        profile["detected_methods"].append("Hausman 检验")
    if "DID" in all_text or "双重差分" in all_text:
        profile["detected_methods"].append("DID")
    if "工具变量" in all_text or "IV" in all_text.split():
        profile["detected_methods"].append("工具变量")

    # 匹配样本期间
    m = re.search(r"(20\d{2})\s*[-—～至到]\s*(20\d{2})", all_text)
    if m:
        profile["sample_period"] = f"{m.group(1)}-{m.group(2)}"

    profile["trigger_plan"] = {
        "triggered_rule_groups": ["数据、变量与口径质检", "方法模型与实证结果质检",
                                  "文献综述与理论链条质检", "结构表达与学术规范质检"],
        "not_applicable_rule_groups": ["选题与研究问题质检 · 硕博盲审"],
        "manual_confirmation_items": ["PDF 输入证据强度默认下调一档"],
    }
    return profile


def _build_issues_from_units_and_vision(
    units: list, vision_result: Optional[dict], profile: dict
) -> tuple[list, list, list]:
    """
    生成 issues / pass_items / manual_confirmation_items。

    简化演示版：只跑几条最具代表性的规则。
    生产版由 agent 读 rules/ 全套跑。
    """
    all_text = " ".join(u.get("text", "") for u in units if isinstance(u, dict))
    issues = []
    passes = []
    manuals = []

    # ---- 规则 1：稳健性检验的常见方向（黄色）
    if "稳健性" in all_text or "稳健性检验" in all_text:
        # 检查是否有多种稳健性方法
        variety_hits = sum(1 for kw in ["替换核心变量", "替换被解释变量", "工具变量法",
                                        "缩尾", "分样本", "剔除异常", "更换样本"]
                          if kw in all_text)
        if variety_hits < 2:
            issues.append({
                "issue_id": "Y-01",
                "issue_type": "methods",
                "level": "黄色",
                "domain": "方法模型与实证结果质检",
                "location": "第五章 稳健性检验",
                "evidence": "全文提及 '稳健性' 但仅识别到不多于 1 种稳健性方法关键词。",
                "evidence_strength": "中",
                "explanation": "稳健性检验建议至少覆盖 2-3 种不同方向，如替换核心变量、替换样本、工具变量法或分样本回归等。",
                "suggestion": "补充至少 1-2 种额外稳健性检验方法（替换被解释变量、缩尾处理、剔除异常样本等）。",
                "need_manual_confirmation": False,
            })

    # ---- 规则 2：Hausman 检验缺失（黄色）
    if ("固定效应" in all_text and "随机效应" in all_text and
            "Hausman" not in all_text and "豪斯曼" not in all_text):
        issues.append({
            "issue_id": "Y-02",
            "issue_type": "methods",
            "level": "黄色",
            "domain": "方法模型与实证结果质检",
            "location": "第四章 实证结果",
            "evidence": "全文同时使用固定效应和随机效应模型，但未见 Hausman 检验相关文字。",
            "evidence_strength": "中",
            "explanation": "面板数据同时报告 FE/RE 时应通过 Hausman 检验确定最终采用哪一个（伍德里奇 §14.3）。",
            "suggestion": "补充 Hausman 检验及其结果，并根据 p 值明确选择 FE 或 RE。",
            "need_manual_confirmation": False,
        })

    # ---- 规则 3：参考文献著录形式（灰色，需人工）
    if "参考文献" in all_text:
        # 简易探测：找 "[1]" 等引用标记
        ref_marks = len(re.findall(r"\[\s*\d+\s*\]", all_text))
        passes.append({
            "id": "P-01",
            "domain": "结构表达与学术规范质检",
            "text": "已列出参考文献",
            "evidence": f"识别到 {ref_marks} 个 [数字] 引用标记" if ref_marks else "已有参考文献章节",
        })

    # ---- 规则 4：图片/表格证据（灰色 → 若有视觉证据，可升级）
    if vision_result and vision_result.get("available") and vision_result.get("evidences"):
        for ev in vision_result["evidences"]:
            page = ev.get("page_number")
            if ev.get("source_type") == "vision_failed":
                issues.append({
                    "issue_id": f"G-V{page:02d}",
                    "issue_type": "figures_tables",
                    "level": "灰色",
                    "domain": "结构表达与学术规范质检",
                    "location": f"第 {page} 页图表",
                    "evidence": f"[视觉识别未完成] {ev.get('downgrade_reason', '')}",
                    "evidence_strength": "低",
                    "explanation": "视觉辅助识别失败，请人工核对原图。",
                    "suggestion": "对照 PDF 原页面确认表格/图形内容是否规范。",
                    "need_manual_confirmation": True,
                    "vision_evidence": {
                        "page_number": page,
                        "thumbnail_ref": None,
                        "downgrade_reason": ev.get("downgrade_reason"),
                    },
                })
            else:
                tp = ev.get("table_preview") or {}
                caption = tp.get("caption", "")
                n_rows = tp.get("n_rows", 0)
                n_cols = tp.get("n_cols", 0)

                # 视觉识别到表 → 灰色 issue，附证据
                text_snip = (ev.get("parsed_text", "")[:200] + "...") if ev.get("parsed_text") else ""
                issues.append({
                    "issue_id": f"G-V{page:02d}",
                    "issue_type": "figures_tables",
                    "level": "灰色",
                    "domain": "结构表达与学术规范质检",
                    "location": f"第 {page} 页表格：{caption}" if caption else f"第 {page} 页表格",
                    "evidence": f"[视觉解析·请核对原图] 识别到 {n_rows}×{n_cols} 表格。\n预览：\n{text_snip}",
                    "evidence_strength": "中（视觉辅助）",
                    "explanation": (
                        "PDF 中的复杂表格通过视觉模型辅助识别，用于交叉核对报告主回归表是否"
                        "包含（1）系数（2）标准误/t 值（3）显著性标记（4）R²/N 等基本项。"
                    ),
                    "suggestion": (
                        "请对照原表核对：① 显著性星号（*/**/***）是否说明；② 报告是否含 R²、样本量 N；"
                        "③ 括号内是否说明为标准误还是 t 值；④ 控制变量注释是否齐全。"
                    ),
                    "need_manual_confirmation": True,
                    "vision_evidence": {
                        "page_number": page,
                        "thumbnail_ref": ev.get("thumbnail_ref"),
                        "model_id": ev.get("model_id"),
                        "quality_profile": ev.get("quality_profile"),
                        "kb_eligibility": ev.get("kb_eligibility"),
                        "table_preview": tp,
                        "review_notice": ev.get("review_notice"),
                    },
                })

    # ---- 规则 5：PDF 输入 → 表格公式相关问题降灰（红线）
    if not vision_result or not vision_result.get("available"):
        manuals.append({
            "id": "M-01",
            "item": "论文中的表格/图片/公式内容",
            "location": "全文图片、公式、复杂表格",
            "reason": "PDF 输入 + 视觉辅助未启用/未配置，表格/公式识别可能不完整。",
            "how_to_check": "对照 PDF 原页面人工核对；如需自动识别可配置 Ark API Key 后重跑。",
        })

    return issues, passes, manuals


def build_diagnostic_result(
    units_json_path: str,
    vision_json_path: Optional[str] = None,
    source_name: str = "未提供",
) -> dict:
    """构造 diagnostic_result（renderer 输入）。"""
    parsed = json.loads(Path(units_json_path).read_text(encoding="utf-8"))
    units = parsed.get("units", [])

    vision_result = None
    if vision_json_path and Path(vision_json_path).exists():
        vision_result = json.loads(Path(vision_json_path).read_text(encoding="utf-8"))

    profile = _detect_paper_profile(units)
    issues, passes, manuals = _build_issues_from_units_and_vision(units, vision_result, profile)

    # 统计
    counts = {"pass": len(passes), "red": 0, "yellow": 0, "green": 0, "manual": 0, "na": 0}
    for f in issues:
        lv = f.get("level", "")
        if lv == "红色":
            counts["red"] += 1
        elif lv == "黄色":
            counts["yellow"] += 1
        elif lv == "绿色":
            counts["green"] += 1
        elif lv == "灰色":
            counts["manual"] += 1

    counts["manual"] += len(manuals)

    # 综合风险
    if counts["red"] > 0:
        risk = "高"
    elif counts["yellow"] >= 3:
        risk = "中"
    else:
        risk = "低-中"

    priority_actions = []
    for i, f in enumerate(issues[:5], 1):
        if f["level"] in ("红色", "黄色"):
            priority_actions.append({
                "priority": i,
                "action": f.get("suggestion", ""),
                "issue_ref": f.get("issue_id", ""),
                "expected": f"关闭 {f.get('issue_id', '')}"
            })

    return {
        "paper_profile": profile,
        "summary_counts": counts,
        "overall_risk_level": risk,
        "pass_items": passes,
        "issues": issues,
        "manual_confirmation_items": manuals,
        "priority_actions": priority_actions,
        "not_applicable_items": [],
        "vision_meta": {
            "enabled": bool(vision_result and vision_result.get("available")),
            "provider": (vision_result or {}).get("provider"),
            "model_id": (vision_result or {}).get("model_id"),
            "target_pages": (vision_result or {}).get("target_pages", []),
            "totals": (vision_result or {}).get("totals", {}),
        } if vision_result else {"enabled": False},
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="M3 端到端报告构建器")
    parser.add_argument("--units", required=True, help="parse_paper.py 输出的 paper_text.json")
    parser.add_argument("--vision", help="vision_pipeline.py 输出的 vision_result.json")
    parser.add_argument("--source", required=True, help="原论文文件名")
    parser.add_argument("--out", required=True, help="输出 diagnostic_result.json 路径")
    args = parser.parse_args(argv)

    result = build_diagnostic_result(args.units, args.vision, args.source)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"✅ diagnostic_result.json → {args.out}")
    print(f"   issues: {len(result['issues'])} · passes: {len(result['pass_items'])}")
    print(f"   counts: {result['summary_counts']}")
    print(f"   risk: {result['overall_risk_level']}")
    print(f"   vision enabled: {result['vision_meta'].get('enabled')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
