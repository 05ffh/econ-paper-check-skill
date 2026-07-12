"""Tests for benchmarks/lib/fingerprint.py"""
import pytest
from benchmarks.lib.fingerprint import (
    build_fingerprint,
    is_valid,
    format_location_anchor,
    diff_fingerprint_sets,
    FingerprintError,
    IssueFingerprint,
)


class TestBuild:
    def test_basic(self):
        fp = build_fingerprint(
            "gb7714_2015_journal_completeness",
            "citation",
            "reference_12",
            "missing_volume_pages",
        )
        assert str(fp) == "gb7714_2015_journal_completeness|citation|reference_12|missing_volume_pages"
        assert is_valid(str(fp))

    def test_normalize_whitespace_and_case(self):
        fp = build_fingerprint("GB 7714", "Citation", "Reference 12", "Missing Pages")
        assert str(fp) == "gb_7714|citation|reference_12|missing_pages"

    def test_illegal_issue_type(self):
        with pytest.raises(FingerprintError):
            build_fingerprint("r", "unknown_type", "table_1", "e")

    def test_empty_segment_rejected(self):
        with pytest.raises(FingerprintError):
            build_fingerprint("   ", "citation", "reference_12", "e")

    def test_chinese_chars_normalized_out(self):
        # 中文字符应被替换为 _
        fp = build_fingerprint("规则A", "citation", "reference_12", "错误B")
        # 归一化后必然合法
        assert is_valid(str(fp))


class TestParse:
    def test_roundtrip(self):
        s = "wooldridge_did_parallel_trends|methods|section_4_2|missing_parallel_test"
        fp = IssueFingerprint.parse(s)
        assert str(fp) == s

    def test_bad_format(self):
        with pytest.raises(FingerprintError):
            IssueFingerprint.parse("a|b|c")   # 只有 3 段
        with pytest.raises(FingerprintError):
            IssueFingerprint.parse("A|citation|section_1|k")   # 大写


class TestLocationAnchor:
    def test_reference(self):
        assert format_location_anchor("reference_entry", 12) == "reference_12"

    def test_section(self):
        assert format_location_anchor("section", "4.2") == "section_4_2"

    def test_table(self):
        assert format_location_anchor("table", 3) == "table_3"

    def test_abstract(self):
        assert format_location_anchor("abstract", "anything") == "abstract"

    def test_bad_type(self):
        with pytest.raises(FingerprintError):
            format_location_anchor("page", 5)


class TestDiff:
    def test_recall(self):
        b = {
            "r1|citation|reference_1|missing_year",
            "r2|methods|section_4_2|missing_parallel_test",
        }
        c = {
            "r1|citation|reference_1|missing_year",
            "r3|writing|abstract|missing_conclusion",
        }
        d = diff_fingerprint_sets(b, c)
        assert d["only_in_baseline"] == ["r2|methods|section_4_2|missing_parallel_test"]
        assert d["only_in_candidate"] == ["r3|writing|abstract|missing_conclusion"]
        assert d["in_both"] == ["r1|citation|reference_1|missing_year"]
        assert d["recall"] == 0.5

    def test_empty_baseline(self):
        d = diff_fingerprint_sets(set(), {"r1|citation|reference_1|missing_year"})
        assert d["recall"] is None

    def test_reject_invalid(self):
        with pytest.raises(FingerprintError):
            diff_fingerprint_sets({"bad-key"}, set())
