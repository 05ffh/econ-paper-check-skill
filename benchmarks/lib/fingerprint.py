"""
Issue Fingerprint normalization (M4 v0.2).

参考: plans/M4_Benchmark_CHANGELOG_v0.2.md §5

Fingerprint = rule_id | issue_type | location_anchor | evidence_key
每段仅小写字母/数字/下划线, 用 "|" 连接.

主键用途:
  - Benchmark 回归对比
  - expected.yaml 定位
  - compare_run.py 集合 diff

不用页码, 不用中文原文, 不用运行期 issue_id.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

_ALLOWED_ISSUE_TYPES = {
    "citation", "methods", "writing", "figures_tables", "summary",
}

_ALLOWED_LOCATION_TYPES = {
    "reference_entry", "section", "table", "figure", "equation",
    "abstract", "paragraph",
}

_FP_RE = re.compile(r"^[a-z0-9_]+\|[a-z_]+\|[a-z0-9_]+\|[a-z0-9_]+$")
_SEG_RE = re.compile(r"^[a-z0-9_]+$")
_TYPE_RE = re.compile(r"^[a-z_]+$")


class FingerprintError(ValueError):
    pass


@dataclass(frozen=True)
class IssueFingerprint:
    rule_id: str
    issue_type: str
    location_anchor: str
    evidence_key: str

    def __str__(self) -> str:
        return f"{self.rule_id}|{self.issue_type}|{self.location_anchor}|{self.evidence_key}"

    def as_string(self) -> str:
        return str(self)

    @classmethod
    def parse(cls, s: str) -> "IssueFingerprint":
        if not _FP_RE.match(s):
            raise FingerprintError(f"invalid fingerprint format: {s!r}")
        parts = s.split("|")
        return cls(*parts)


def _norm_seg(x: str, field: str) -> str:
    """Normalize one segment (rule_id / location_anchor / evidence_key)."""
    if x is None:
        raise FingerprintError(f"{field} is None")
    x = x.strip().lower()
    x = re.sub(r"\s+", "_", x)
    x = re.sub(r"[^a-z0-9_]", "_", x)
    x = re.sub(r"_+", "_", x).strip("_")
    if not x:
        raise FingerprintError(f"{field} became empty after normalization")
    if not _SEG_RE.match(x):
        raise FingerprintError(f"{field} contains illegal chars after norm: {x!r}")
    return x


def _norm_issue_type(t: str) -> str:
    t = (t or "").strip().lower().replace(" ", "_")
    if t not in _ALLOWED_ISSUE_TYPES:
        raise FingerprintError(
            f"issue_type must be one of {_ALLOWED_ISSUE_TYPES}, got {t!r}"
        )
    if not _TYPE_RE.match(t):
        raise FingerprintError(f"issue_type contains illegal chars: {t!r}")
    return t


def build_fingerprint(
    rule_id: str,
    issue_type: str,
    location_anchor: str,
    evidence_key: str,
) -> IssueFingerprint:
    fp = IssueFingerprint(
        rule_id=_norm_seg(rule_id, "rule_id"),
        issue_type=_norm_issue_type(issue_type),
        location_anchor=_norm_seg(location_anchor, "location_anchor"),
        evidence_key=_norm_seg(evidence_key, "evidence_key"),
    )
    # sanity check
    if not _FP_RE.match(str(fp)):
        raise FingerprintError(f"assembled fingerprint invalid: {fp}")
    return fp


def is_valid(s: str) -> bool:
    return bool(_FP_RE.match(s or ""))


def format_location_anchor(
    location_type: str,
    identifier: str | int,
) -> str:
    """
    Convenience helper for expected authors.

    Examples:
        format_location_anchor("reference_entry", 12) -> "reference_12"
        format_location_anchor("section", "4.2")       -> "section_4_2"
        format_location_anchor("table", 3)             -> "table_3"
    """
    lt = (location_type or "").strip().lower()
    if lt not in _ALLOWED_LOCATION_TYPES:
        raise FingerprintError(
            f"location_type must be one of {_ALLOWED_LOCATION_TYPES}, got {lt!r}"
        )
    base_map = {
        "reference_entry": "reference",
        "section": "section",
        "table": "table",
        "figure": "figure",
        "equation": "equation",
        "abstract": "abstract",
        "paragraph": "paragraph",
    }
    prefix = base_map[lt]
    if lt == "abstract":
        return "abstract"
    ident = str(identifier).strip()
    ident_norm = _norm_seg(ident, "identifier")
    return f"{prefix}_{ident_norm}"


# ---- diff helpers ----

def diff_fingerprint_sets(
    baseline: set[str],
    candidate: set[str],
) -> dict:
    """Return set diff, used by compare_run.py."""
    for s in baseline | candidate:
        if not is_valid(s):
            raise FingerprintError(f"invalid fingerprint in set: {s!r}")
    return {
        "only_in_baseline": sorted(baseline - candidate),
        "only_in_candidate": sorted(candidate - baseline),
        "in_both": sorted(baseline & candidate),
        "recall": (
            len(baseline & candidate) / len(baseline) if baseline else None
        ),
    }
