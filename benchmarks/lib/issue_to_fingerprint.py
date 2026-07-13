"""
issue_to_fingerprint.py — 从 diagnostic_result.json 的 issue dict 提取稳定 fingerprint

参考:
  - plans/M4_Benchmark_CHANGELOG_v0.2.md §5
  - references/issue_schema.md
  - benchmarks/lib/fingerprint.py

核心问题:
  Skill 判断内核输出的 issue 是 LLM 语义结果, 每次运行:
    - issue_id (R-01 / MM-DID-001-p3) 可能变化
    - location 用自然语言 ("第 3 节 §3.2") 可能变
    - evidence 是学生原文摘抄, 完全不稳定
  Benchmark 主键必须稳定 → 需要归一化到 fingerprint。

映射规则:
  rule_id         = issue.rule_id 或 issue.normative_basis[0].norm_id
                    (归一化为 lower_underscore)
  issue_type      = 根据 rule_id 前缀 + issue.domain 映射到 5 白名单:
                    citation / methods / writing / figures_tables / summary
  location_anchor = 根据 issue.location 中的结构化字段:
                    - reference_N     (参考文献第 N 条)
                    - section_N_M     (§N.M)
                    - table_N / figure_N / equation_N
                    - abstract        (摘要)
                    - paragraph_N     (第 N 段, 兜底)
  evidence_key    = 语义标签枚举 (missing_volume_pages, sign_error,
                    missing_parallel_test 等), 不用中文原文

不稳定字段 (严格禁止入 fingerprint):
  - issue_id (LLM 生成的运行期编号)
  - evidence (学生原文)
  - explanation / suggestion (LLM 措辞)
"""
from __future__ import annotations
import re
from typing import Optional

from benchmarks.lib.fingerprint import (
    IssueFingerprint,
    build_fingerprint,
    format_location_anchor,
    FingerprintError,
)


# ============================================================
# rule_id 前缀 → issue_type 映射（严格白名单）
# ============================================================

_RULE_PREFIX_TO_TYPE = {
    # 引用规范
    "SN-REF":  "citation",
    "gb7714":  "citation",
    # 结构规范
    "SN-ABSTRACT":     "summary",
    "SN-ABSTRACT-EN":  "summary",
    "SN-KEYWORDS":     "summary",
    "SN-CONCLUSION":   "summary",
    "SN-ADVICE":       "summary",
    "SN-TABLE":        "figures_tables",
    "SN-LANG":         "writing",
    # 方法模型
    "MM":         "methods",
    "wooldridge": "methods",
    # 选题、文献、数据变量默认落 writing
    # (M4 v0.2 白名单没有独立 issue_type, 需要就未来扩)
    "TQ": "writing",
    "LT": "writing",
    "DV": "writing",
}


def infer_issue_type(rule_id: str, domain: Optional[str] = None) -> str:
    """
    根据 rule_id 前缀映射 issue_type; domain 是备用信号。

    未知 rule_id 抛异常, 逼调用者显式扩表。
    """
    if not rule_id:
        raise FingerprintError("rule_id is empty")

    rid = rule_id.strip()
    # 先按最长前缀匹配
    matches = [
        (prefix, t)
        for prefix, t in _RULE_PREFIX_TO_TYPE.items()
        if rid.startswith(prefix) or rid.lower().startswith(prefix.lower())
    ]
    if matches:
        prefix, t = max(matches, key=lambda x: len(x[0]))
        return t

    # domain 兜底
    if domain:
        d = domain.lower()
        if "引用" in domain or "参考文献" in domain or "citation" in d:
            return "citation"
        if "方法" in domain or "模型" in domain or "method" in d:
            return "methods"
        if "图表" in domain or "table" in d or "figure" in d:
            return "figures_tables"
        if "摘要" in domain or "abstract" in d or "summary" in d:
            return "summary"

    raise FingerprintError(
        f"cannot infer issue_type from rule_id={rule_id!r}, domain={domain!r}. "
        f"Extend _RULE_PREFIX_TO_TYPE or provide domain hint."
    )


# ============================================================
# location → location_anchor 归一化
# ============================================================

# 参考文献: "[12]" / "第12条参考文献" / "reference 12" / "参考文献 [3]"
_REF_RE = re.compile(r"(?:reference[_\s]*|参考文献\s*|\[)(\d{1,3})")
# 章节: "§3.2" / "第3章 3.2 节" / "section 3.2" / "3.2 节"
_SEC_RE = re.compile(r"(?:§|section[_\s]*|第)?(\d{1,2})(?:章)?[\.\s]*(\d{1,3})")
# 单章节: "§3" / "第3章"
_SEC1_RE = re.compile(r"(?:§|第)\s*(\d{1,2})(?:章|节)?")
# 表格: "表 3" / "Table 3" / "table_3"
_TABLE_RE = re.compile(r"(?:表|table)[_\s]*(\d{1,3})", re.IGNORECASE)
# 图: "图 4" / "Figure 4"
_FIGURE_RE = re.compile(r"(?:图|figure|fig)[_\s\.]*(\d{1,3})", re.IGNORECASE)
# 公式: "式 (1)" / "equation 2" / "公式 3"
_EQ_RE = re.compile(r"(?:式|公式|equation|eq)[_\s\.]*\(?(\d{1,3})\)?", re.IGNORECASE)
# 摘要
_ABS_RE = re.compile(r"(摘要|abstract)", re.IGNORECASE)


def normalize_location(loc: str | dict) -> str:
    """
    输入可以是:
      - str: "参考文献 [12]", "§3.2", "表 3", "摘要"
      - dict: issue.location 完整对象, 至少含 anchor/type/text
    输出稳定 location_anchor: reference_12, section_3_2, table_3, abstract, ...
    """
    if isinstance(loc, dict):
        # 结构化 location 优先
        typ = (loc.get("type") or "").strip().lower()
        anchor = loc.get("anchor") or loc.get("value") or loc.get("id")
        text = loc.get("text") or ""

        if typ in {"reference_entry", "section", "table", "figure", "equation", "abstract", "paragraph"} and anchor is not None:
            return format_location_anchor(typ, anchor)

        # 结构化字段不完整, 退化到文本解析
        loc = text or str(anchor or "")

    s = str(loc).strip()
    if not s:
        raise FingerprintError("location is empty")

    # 优先级: abstract > reference > section > table > figure > equation
    if _ABS_RE.search(s):
        return format_location_anchor("abstract", "abstract")

    m = _REF_RE.search(s)
    if m:
        return format_location_anchor("reference_entry", int(m.group(1)))

    m = _TABLE_RE.search(s)
    if m:
        return format_location_anchor("table", int(m.group(1)))

    m = _FIGURE_RE.search(s)
    if m:
        return format_location_anchor("figure", int(m.group(1)))

    m = _EQ_RE.search(s)
    if m:
        return format_location_anchor("equation", int(m.group(1)))

    # 章节 §N.M 优先于 §N
    m = _SEC_RE.search(s)
    if m:
        return format_location_anchor("section", f"{m.group(1)}.{m.group(2)}")
    m = _SEC1_RE.search(s)
    if m:
        return format_location_anchor("section", m.group(1))

    # 兜底: paragraph
    raise FingerprintError(
        f"cannot normalize location from {s!r}. "
        f"Prefer structured location dict with type/anchor."
    )


# ============================================================
# evidence_key 归一化 (最难; 必须由标注方或 issue.evidence_tag 提供)
# ============================================================

# rule_id → 默认 evidence_key (当 issue.evidence_tag 缺失时兜底)
_RULE_DEFAULT_EVIDENCE_KEY = {
    "gb7714_2015_journal_completeness":      "missing_volume_pages",
    "gb7714_2015_book_publication_place":    "missing_publisher_place",
    "gb7714_2015_dissertation_completeness": "missing_degree_grantor",
    "gb7714_2015_electronic_url_date":       "missing_access_date",
    "gb7714_2015_document_type_marker":      "missing_type_marker",
    "gb7714_2015_intext_reference_consistency": "reference_mismatch",
    "gb7714_2015_author_format":             "wrong_author_format",
    "gb7714_2015_general_element_order":     "wrong_element_order",
    "gb7714_2015_mixed_language":            "mixed_language_disorder",
    "wooldridge_did_parallel_trends":        "missing_parallel_test",
    "wooldridge_did_two_way_fe":             "missing_two_way_fe",
    "wooldridge_panel_fe_re_choice":         "missing_hausman",
    "wooldridge_robust_se":                  "missing_robust_se",
    "wooldridge_iv_relevance_exclusion":     "missing_exclusion_arg",
    "wooldridge_mediation_analysis":         "missing_bootstrap_sobel",
    "wooldridge_ols_assumptions":            "ols_assumption_violation",
    "wooldridge_heterogeneity_analysis":     "missing_heterogeneity",
    "wooldridge_robustness_categories":      "insufficient_robustness",
    # 内置规则 (SN/MM/TQ/DV) 建议由 issue.evidence_tag 显式指定,
    # 未提供时归一化到 "rule_default"
}


def infer_evidence_key(rule_id: str, evidence_tag: Optional[str] = None) -> str:
    """
    evidence_key 优先取 issue.evidence_tag (标注方明确指定),
    否则回落到 _RULE_DEFAULT_EVIDENCE_KEY,
    再否则 raise —— 逼调用者补 tag。
    """
    if evidence_tag:
        return evidence_tag.strip().lower().replace(" ", "_")

    rid = (rule_id or "").strip()
    if rid in _RULE_DEFAULT_EVIDENCE_KEY:
        return _RULE_DEFAULT_EVIDENCE_KEY[rid]

    raise FingerprintError(
        f"cannot infer evidence_key for rule_id={rid!r}. "
        f"Provide issue.evidence_tag explicitly, or extend _RULE_DEFAULT_EVIDENCE_KEY."
    )


# ============================================================
# 主入口: issue → fingerprint
# ============================================================

def issue_to_fingerprint(issue: dict) -> IssueFingerprint:
    """
    从一个 issue dict 构造 fingerprint.

    期望的最小字段:
      - rule_id (必填)
      - location (str 或 dict, 必填)
      - domain (可选, 用作 issue_type 兜底)
      - evidence_tag (可选, 建议标注方提供)
      - normative_basis[0].norm_id (可选, 用作 rule_id 兜底)

    返回: IssueFingerprint 对象; 转字符串直接可与 expected fingerprint 对比.
    """
    if not isinstance(issue, dict):
        raise FingerprintError(f"issue must be dict, got {type(issue)}")

    # 1) rule_id: 优先用 issue.rule_id, 兜底 KB-A 规范挂载
    rule_id = issue.get("rule_id") or ""
    if not rule_id:
        nb = issue.get("normative_basis") or []
        if isinstance(nb, list) and nb:
            first = nb[0] if isinstance(nb[0], dict) else {}
            rule_id = first.get("norm_id") or first.get("id") or ""
    if not rule_id:
        raise FingerprintError("issue has no rule_id nor normative_basis[0].norm_id")

    # 2) issue_type
    domain = issue.get("domain") or issue.get("issue_type_zh")
    issue_type = infer_issue_type(rule_id, domain)

    # 3) location
    loc = issue.get("location")
    if loc is None:
        raise FingerprintError("issue has no location")
    location_anchor = normalize_location(loc)

    # 4) evidence_key
    evidence_tag = issue.get("evidence_tag")
    evidence_key = infer_evidence_key(rule_id, evidence_tag)

    return build_fingerprint(rule_id, issue_type, location_anchor, evidence_key)


def diagnostic_to_fingerprints(diagnostic: dict) -> list[str]:
    """
    diagnostic_result.json → fingerprint list

    优雅退化: 遇到无法归一化的 issue, 不阻塞, 累积到日志.
    """
    result = []
    errors = []
    dr = diagnostic.get("diagnostic_result") or diagnostic
    for issue in dr.get("issues", []) or []:
        try:
            fp = issue_to_fingerprint(issue)
            result.append(str(fp))
        except FingerprintError as e:
            errors.append({
                "issue_id": issue.get("issue_id", "<unknown>"),
                "error": str(e),
            })
    return result, errors  # 双返回, 调用方决定是否 hard-fail


__all__ = [
    "issue_to_fingerprint",
    "diagnostic_to_fingerprints",
    "infer_issue_type",
    "normalize_location",
    "infer_evidence_key",
]
