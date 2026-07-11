#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M1 · 改进参照卡片生成器（v1）

供 skill 主流程（issue → report）在报告生成阶段调用：
输入 issue 结构，返回一段可直接嵌入到「修改建议」下方的参照卡片 markdown。

调用示例：
    from scripts.build_reference_card import build_card_for_issue
    card_md = build_card_for_issue(issue)   # 返回 str 或 None

对齐:
- agent_instructions/issue_writing_protocol.md § 4bis 触发条件与红线
- agent_instructions/evidence_requirement.md § 15 KB-B 引用红线
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/root/.openclaw/workspace/econ-paper-check-skill")
sys.path.insert(0, str(ROOT))

from scripts.kb_query import search  # 模块级便捷入口

# ---- issue_type 白名单：只对结构/规范类问题挂参照 ----
ALLOWED_ISSUE_TYPES = {
    "writing",        # 文献综述/结构性写作
    "citation",       # 参考文献格式/引用规范
    "methods",        # 方法章节呈现
    "figures_tables", # 图表规范
    "summary",        # 摘要
    # 显式排除：variable_definition, data_source, evidence_conflict, 灰色等
}

# ---- 相似度阈值 ----
CARD_MIN_SIMILARITY = 0.45  # v1.4 实测：真实 brief 含否定词，相似度一般 0.35-0.55
# ---- chunk 截断 ----
MAX_CHUNK_CHARS = 500
# ---- 主报告参照卡片总数上限 ----
MAX_CARDS_PER_REPORT = 8


# ---- 问题 brief → 正向查询重写 ----
_REWRITE_PATTERNS = [
    # (触发关键词, 重写后的查询模板或 lambda)
    ("文献综述", "文献综述写作规范与述评环节"),
    ("稳健性检验", "稳健性检验常见做法与补充方法"),
    ("异质性", "异质性分析展开方式"),
    ("平行趋势", "平行趋势检验的做法"),
    ("机制检验", "影响机制检验中介分析与路径"),
    ("参考文献", "参考文献格式规范"),
    ("回归表注释", "回归表注释与显著性说明规范"),
    ("摩要", "摩要写作规范与关键信息"),
    ("摘要", "摘要写作规范与关键信息"),
    ("变量定义", "变量定义与数据来源写作规范"),
    ("图表", "图表命名与注释规范"),
    ("结论", "结论与建议写作规范"),
]


def _rewrite_query(brief: str) -> str:
    """将问题描述（含否定词）重写为正向检索查询。
    国内 sentence-transformers 对否定词不敏感，直接用 brief 会射中零散糟片；
    重写后命中相关章节标题的概率大幅提升。"""
    if not brief:
        return brief
    for kw, tmpl in _REWRITE_PATTERNS:
        if kw in brief:
            return tmpl
    return brief


def _truncate(text: str, n: int = MAX_CHUNK_CHARS) -> str:
    t = text.strip().replace("\n", " ")
    if len(t) <= n:
        return t
    return t[:n] + "…"


def _paper_brief(paper_id: str) -> str:
    """返回论文简述（不含真实作者/学校，只返回 EXAMPLE-XXXX + 主题）"""
    return paper_id  # 主题信息由 topic_hint 单独字段承载


def build_card_for_issue(issue: dict,
                          global_card_count: int = 0,
                          min_similarity: float = CARD_MIN_SIMILARITY) -> str | None:
    """
    输入:
      issue = {
        "issue_id": "R-01",
        "issue_type": "writing" | "citation" | ...,
        "level": "red" | "yellow" | "green" | "gray",
        "location": "...",
        "brief": "问题简述（用作检索 query）",
        "topic_hint": (可选)论文主题
        "method_hint": (可选) 方法过滤
      }
      global_card_count: 当前报告已生成的卡片数（用于 MAX_CARDS_PER_REPORT 限制）

    返回:
      markdown 卡片字符串 或 None（表示不附卡）
    """
    # 触发条件 1: issue_type 白名单
    itype = (issue.get("issue_type") or "").lower()
    if itype not in ALLOWED_ISSUE_TYPES:
        return None

    # 触发条件 2: 灰色/通过/不适用不挂卡
    if (issue.get("level") or "").lower() in ("gray", "grey", "pass", "na", "n/a"):
        return None

    # 触发条件 3: 全局数量上限
    if global_card_count >= MAX_CARDS_PER_REPORT:
        return None

    # 触发条件 4: brief 必填
    brief = (issue.get("brief") or "").strip()
    if not brief or len(brief) < 5:
        return None

    # 检索（先尝试重写 query）
    query = _rewrite_query(brief)
    try:
        res = search(query=query, topk=1,
                     method=issue.get("method_hint"),
                     paper_type=None)
    except Exception as e:
        # KB-B 加载失败 → 静默降级
        return None

    if res.get("route") != "B" or not res.get("results"):
        return None

    top = res["results"][0]
    if top["similarity"] < min_similarity:
        return None

    # 组装 markdown
    text = _truncate(top["text"])
    section = top.get("current_section") or top.get("section") or "-"
    section = section.replace("body_", "")

    lines = []
    lines.append("**改进参照** *（KB-B 范例层 · 仅作改进方向参照，非错误判定依据）*")
    lines.append("")
    lines.append(f"- 范例出处：`{top['paper_id']}` · {top.get('topic_hint','-')}")
    lines.append(f"- 参照章节：{section}")
    lines.append(f"- 相似度：{top['similarity']:.2f}")
    lines.append(f"- 参照片段：")
    lines.append(f"  > {text}")
    if top.get("expanded"):
        # 只挂第一个展开段（避免过长）
        ex = top["expanded"][0]
        ex_text = _truncate(ex["text"])
        lines.append(f"  > ")
        lines.append(f"  > {ex_text}")
    lines.append(f"- 提示：范例仅作改进方向参照，具体规范请以学校模板/国标为准。")

    return "\n".join(lines)


def build_cards_for_issues(issues: list[dict],
                            min_similarity: float = CARD_MIN_SIMILARITY) -> dict:
    """
    批量：为一批 issue 生成卡片 dict，key=issue_id, value=card_md or None

    返回:
      {
        "cards": {"R-01": "...markdown...", "Y-03": None, ...},
        "stats": {"total_issues": ..., "cards_generated": ...,
                  "cards_skipped_by_type": ..., "cards_skipped_by_similarity": ...},
      }
    """
    cards = {}
    stats = {
        "total_issues": len(issues),
        "cards_generated": 0,
        "cards_skipped_by_type": 0,
        "cards_skipped_by_similarity": 0,
        "cards_skipped_by_limit": 0,
        "cards_skipped_by_error": 0,
    }
    global_count = 0
    for iss in issues:
        iid = iss.get("issue_id") or f"UNKNOWN-{stats['total_issues']}"
        itype = (iss.get("issue_type") or "").lower()
        if itype not in ALLOWED_ISSUE_TYPES:
            stats["cards_skipped_by_type"] += 1
            cards[iid] = None
            continue
        if global_count >= MAX_CARDS_PER_REPORT:
            stats["cards_skipped_by_limit"] += 1
            cards[iid] = None
            continue
        try:
            card = build_card_for_issue(iss, global_card_count=global_count,
                                          min_similarity=min_similarity)
        except Exception:
            stats["cards_skipped_by_error"] += 1
            cards[iid] = None
            continue
        if card is None:
            stats["cards_skipped_by_similarity"] += 1
            cards[iid] = None
        else:
            cards[iid] = card
            stats["cards_generated"] += 1
            global_count += 1

    return {"cards": cards, "stats": stats}


# ---- CLI: 演示 ----
if __name__ == "__main__":
    import json, argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="跑一组 demo issues")
    ap.add_argument("--file", help="加载 issues JSON 文件")
    args = ap.parse_args()

    if args.demo:
        demo_issues = [
            {
                "issue_id": "R-01",
                "issue_type": "writing",
                "level": "red",
                "location": "第二章 文献综述",
                "brief": "文献综述部分应该怎么写更规范",
                "topic_hint": "银行业实证",
            },
            {
                "issue_id": "Y-02",
                "issue_type": "methods",
                "level": "yellow",
                "location": "第四章 稳健性",
                "brief": "稳健性检验应该做哪些常见做法",
                "method_hint": "DID",
            },
            {
                "issue_id": "R-03",
                "issue_type": "variable_definition",  # 应被跳过
                "level": "red",
                "location": "第三章",
                "brief": "变量定义缺失",
            },
            {
                "issue_id": "G-04",
                "issue_type": "figures_tables",
                "level": "green",
                "location": "全文",
                "brief": "回归表注释规范怎么写",
            },
            {
                "issue_id": "GR-05",
                "issue_type": "writing",
                "level": "gray",  # 灰色应被跳过
                "location": "-",
                "brief": "-",
            },
        ]
        out = build_cards_for_issues(demo_issues)
        print("=" * 70)
        print("Demo · 5 个 issue，参照卡片生成结果")
        print("=" * 70)
        print(json.dumps(out["stats"], ensure_ascii=False, indent=2))
        print()
        for iid, card in out["cards"].items():
            print(f"\n--- {iid} ---")
            print(card if card else "(不挂卡)")
    elif args.file:
        issues = json.load(open(args.file, encoding="utf-8"))
        out = build_cards_for_issues(issues)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        ap.print_help()
