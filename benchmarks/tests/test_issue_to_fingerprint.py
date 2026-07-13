"""Tests for benchmarks/lib/issue_to_fingerprint.py — Phase C 反循环核心."""
from __future__ import annotations
import pytest

from benchmarks.lib.fingerprint import FingerprintError
from benchmarks.lib.issue_to_fingerprint import (
    infer_issue_type,
    normalize_location,
    infer_evidence_key,
    issue_to_fingerprint,
    diagnostic_to_fingerprints,
)


# ============================================================
# infer_issue_type
# ============================================================

class TestInferIssueType:
    def test_gb7714_prefix(self):
        assert infer_issue_type("gb7714_2015_journal_completeness") == "citation"

    def test_wooldridge_prefix(self):
        assert infer_issue_type("wooldridge_did_parallel_trends") == "methods"

    def test_sn_ref_prefix(self):
        assert infer_issue_type("SN-REF-001") == "citation"

    def test_sn_table_prefix(self):
        assert infer_issue_type("SN-TABLE-001") == "figures_tables"

    def test_sn_abstract_prefix(self):
        assert infer_issue_type("SN-ABSTRACT-001") == "summary"

    def test_mm_prefix(self):
        assert infer_issue_type("MM-DID-001") == "methods"

    def test_unknown_prefix_with_domain(self):
        assert infer_issue_type("XX-YY", domain="参考文献质检") == "citation"
        assert infer_issue_type("XX-YY", domain="模型方法") == "methods"

    def test_unknown_prefix_no_domain_raises(self):
        with pytest.raises(FingerprintError):
            infer_issue_type("ZZ-QQ-999")

    def test_empty_rule_id_raises(self):
        with pytest.raises(FingerprintError):
            infer_issue_type("")


# ============================================================
# normalize_location
# ============================================================

class TestNormalizeLocation:
    def test_reference_text(self):
        assert normalize_location("参考文献 [12]") == "reference_12"
        assert normalize_location("[3] 王某某") == "reference_3"
        assert normalize_location("reference 5") == "reference_5"

    def test_section_dotted(self):
        assert normalize_location("§3.2") == "section_3_2"
        assert normalize_location("section 4.1") == "section_4_1"

    def test_table(self):
        assert normalize_location("表 3") == "table_3"
        assert normalize_location("Table 12") == "table_12"

    def test_abstract(self):
        assert normalize_location("摘要") == "abstract"
        assert normalize_location("abstract") == "abstract"
        # 忽略 anchor 后缀
        assert normalize_location({"type": "abstract", "anchor": "any"}) == "abstract"

    def test_structured_dict(self):
        assert normalize_location({"type": "reference_entry", "anchor": 12}) == "reference_12"
        assert normalize_location({"type": "table", "anchor": 3}) == "table_3"
        assert normalize_location({"type": "section", "anchor": "4.2"}) == "section_4_2"

    def test_equation(self):
        assert normalize_location("式 (1)") == "equation_1"
        assert normalize_location("equation 2") == "equation_2"

    def test_cannot_normalize_raises(self):
        with pytest.raises(FingerprintError):
            normalize_location("正文某处")


# ============================================================
# infer_evidence_key
# ============================================================

class TestInferEvidenceKey:
    def test_explicit_tag_wins(self):
        assert infer_evidence_key(
            "gb7714_2015_journal_completeness", evidence_tag="my_custom_key"
        ) == "my_custom_key"

    def test_rule_default(self):
        assert infer_evidence_key("gb7714_2015_journal_completeness") == "missing_volume_pages"
        assert infer_evidence_key("wooldridge_did_parallel_trends") == "missing_parallel_test"

    def test_unknown_raises(self):
        with pytest.raises(FingerprintError):
            infer_evidence_key("SN-REF-001")


# ============================================================
# issue_to_fingerprint 端到端
# ============================================================

class TestIssueToFingerprint:
    def test_kb_a_style_issue(self):
        issue = {
            "issue_id": "R-01",
            "rule_id": "gb7714_2015_journal_completeness",
            "domain": "参考文献质检",
            "location": {"type": "reference_entry", "anchor": 1},
        }
        fp = issue_to_fingerprint(issue)
        assert str(fp) == "gb7714_2015_journal_completeness|citation|reference_1|missing_volume_pages"

    def test_did_issue(self):
        issue = {
            "rule_id": "wooldridge_did_parallel_trends",
            "domain": "方法模型",
            "location": {"type": "section", "anchor": "4.2"},
        }
        fp = issue_to_fingerprint(issue)
        assert str(fp) == "wooldridge_did_parallel_trends|methods|section_4_2|missing_parallel_test"

    def test_kb_a_norm_fallback(self):
        issue = {
            "issue_id": "R-05",
            # rule_id 缺失, 从 normative_basis 拿
            "normative_basis": [{"norm_id": "gb7714_2015_electronic_url_date"}],
            "location": "参考文献 [4]",
        }
        fp = issue_to_fingerprint(issue)
        assert str(fp) == "gb7714_2015_electronic_url_date|citation|reference_4|missing_access_date"

    def test_explicit_evidence_tag(self):
        issue = {
            "rule_id": "SN-REF-001",
            "domain": "参考文献质检",
            "location": {"type": "reference_entry", "anchor": 12},
            "evidence_tag": "missing_volume_pages",
        }
        fp = issue_to_fingerprint(issue)
        assert str(fp) == "sn_ref_001|citation|reference_12|missing_volume_pages"

    def test_missing_rule_id_and_norm_raises(self):
        with pytest.raises(FingerprintError):
            issue_to_fingerprint({"location": "参考文献 [1]"})

    def test_missing_location_raises(self):
        with pytest.raises(FingerprintError):
            issue_to_fingerprint({"rule_id": "gb7714_2015_journal_completeness"})


# ============================================================
# diagnostic_to_fingerprints
# ============================================================

class TestDiagnosticToFingerprints:
    def test_batch_extraction(self):
        d = {
            "diagnostic_result": {
                "issues": [
                    {
                        "rule_id": "gb7714_2015_journal_completeness",
                        "location": {"type": "reference_entry", "anchor": 1},
                    },
                    {
                        "rule_id": "wooldridge_did_parallel_trends",
                        "domain": "方法模型",
                        "location": {"type": "section", "anchor": "4.2"},
                    },
                ],
            },
        }
        fps, errors = diagnostic_to_fingerprints(d)
        assert len(fps) == 2
        assert len(errors) == 0
        assert "gb7714_2015_journal_completeness|citation|reference_1|missing_volume_pages" in fps

    def test_partial_failure_logs(self):
        d = {
            "issues": [
                {
                    "rule_id": "gb7714_2015_journal_completeness",
                    "location": {"type": "reference_entry", "anchor": 1},
                },
                {
                    "issue_id": "BAD",
                    # 缺 rule_id
                    "location": "somewhere",
                },
            ],
        }
        fps, errors = diagnostic_to_fingerprints(d)
        assert len(fps) == 1
        assert len(errors) == 1
        assert errors[0]["issue_id"] == "BAD"
