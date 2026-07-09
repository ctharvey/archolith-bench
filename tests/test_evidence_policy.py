"""Offline tests for the evidence policy validator (no network, no model calls)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from archolith_bench.core.evidence_policy import (
    _contains_rejected_term,
    _is_commit_like,
    _is_date_like,
    _is_placeholder,
    _parse_headline_table,
    validate_evidence_artifact,
    validate_headline_numbers,
    validate_policy,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "evidence_policy"


# ===================================================================
# Unit: helpers
# ===================================================================

class TestHelpers:
    def test_is_commit_like(self):
        assert _is_commit_like("a1b2c3d")
        assert _is_commit_like("abcdef1234567890abcdef1234567890abcdef12")
        assert not _is_commit_like("")
        assert not _is_commit_like("unknown")
        assert not _is_commit_like("TBD")
        assert not _is_commit_like("not a commit")

    def test_is_date_like(self):
        assert _is_date_like("2026-07-01")
        assert _is_date_like("2024-01-31")
        assert not _is_date_like("")
        assert not _is_date_like("2026-13-01")
        assert not _is_date_like("pending")
        assert not _is_date_like("07-01-2026")

    def test_is_placeholder(self):
        assert _is_placeholder("_none_")
        assert _is_placeholder("pending")
        assert _is_placeholder("none")
        assert _is_placeholder("TBD")
        assert _is_placeholder("unknown")
        assert not _is_placeholder("real value")
        assert not _is_placeholder("")

    def test_contains_rejected_term(self):
        assert _contains_rejected_term("this is a fixture result")
        assert _contains_rejected_term("sample data only")
        assert _contains_rejected_term("demo run")
        assert _contains_rejected_term("historical evidence")
        assert _contains_rejected_term("candidate numbers")
        assert _contains_rejected_term("pending review")
        assert _contains_rejected_term("not for copy")
        assert _contains_rejected_term("internal only")
        assert _contains_rejected_term("smoke only test")
        assert _contains_rejected_term("offline stub result")
        assert not _contains_rejected_term("Live run against production")
        assert not _contains_rejected_term("Real benchmark output")

    def test_parse_headline_table_no_section(self):
        assert _parse_headline_table("no table here") == []

    def test_parse_headline_table_none_placeholder(self):
        text = """## Active Headline Numbers
| Product | Claim |
|---------|-------|
| _none_ | _placeholder_ |
"""
        rows = _parse_headline_table(text)
        assert len(rows) == 1
        # Parser strips surrounding underscores
        assert rows[0]["Product"] == "none"


# ===================================================================
# HEADLINE-NUMBERS.md validation
# ===================================================================

class TestValidateHeadlineNumbers:
    def test_no_claims_placeholder_passes(self):
        path = FIXTURES / "headline_numbers_no_claims.md"
        result = validate_headline_numbers(path)
        assert result.ok is True
        assert result.summary["headline_active_claims"] == 0

    def test_valid_active_claim_passes(self):
        path = FIXTURES / "headline_numbers_valid_claim.md"
        result = validate_headline_numbers(path)
        assert result.ok is True
        assert result.summary["headline_active_claims"] == 1

    def test_active_claim_missing_commit_fails(self):
        path = FIXTURES / "headline_numbers_invalid_claim.md"
        result = validate_headline_numbers(path)
        assert result.ok is False
        assert any(e.code == "missing_commit" for e in result.errors), (
            [e.code for e in result.errors]
        )

    def test_active_claim_invalid_run_date_fails(self):
        path = FIXTURES / "headline_numbers_invalid_claim.md"
        result = validate_headline_numbers(path)
        assert result.ok is False
        assert any(e.code == "invalid_run_date" for e in result.errors), (
            [e.code for e in result.errors]
        )

    def test_active_claim_with_fixture_language_fails(self):
        path = FIXTURES / "headline_numbers_invalid_claim.md"
        result = validate_headline_numbers(path)
        assert result.ok is False
        assert any(e.code == "rejected_term_in_active_claim" for e in result.errors), (
            [e.code for e in result.errors]
        )

    def test_retired_section_with_fixture_language_does_not_fail(self):
        """Retired section uses 'fixture' and 'sample' — those should not trigger errors."""
        path = FIXTURES / "headline_numbers_valid_claim.md"
        result = validate_headline_numbers(path)
        # The retired section says 'fixture' and 'historical' but only active rows are checked.
        assert result.ok is True

    def test_file_not_found(self):
        result = validate_headline_numbers(Path("/nonexistent/HEADLINE-NUMBERS.md"))
        assert result.ok is False
        assert any(e.code == "file_not_found" for e in result.errors)


# ===================================================================
# Evidence artifact validation
# ===================================================================

class TestValidateEvidenceArtifact:
    def test_public_copy_false_missing_fields_gives_warnings(self):
        path = FIXTURES / "evidence_missing_provenance.json"
        result = validate_evidence_artifact(path)
        assert result.ok is True
        assert len(result.warnings) > 0
        assert any(w.code == "missing_field" for w in result.warnings)

    def test_public_copy_true_full_provenance_passes(self):
        path = FIXTURES / "evidence_valid_public.json"
        result = validate_evidence_artifact(path)
        assert result.ok is True, [e.message for e in result.errors]

    def test_public_copy_true_fixture_source_fails(self):
        path = FIXTURES / "evidence_fixture_public_invalid.json"
        result = validate_evidence_artifact(path)
        assert result.ok is False
        assert any(e.code == "fixture_source_rejected" for e in result.errors), (
            [e.code for e in result.errors]
        )

    def test_public_copy_true_empty_caveats_fails(self):
        data = {
            "title": "Test",
            "command": "bench",
            "commit": "a1b2c3d",
            "product": "test",
            "ability": "test",
            "fixture_or_live_source": "Live run",
            "model_provider": "gpt-4o-mini",
            "environment_caveats": [],
            "public_copy_allowed": True,
            "metric_rows": [{"n": 1}],
            "artifact": {},
        }
        p = _write_tmp_json(data)
        result = validate_evidence_artifact(p)
        assert result.ok is False
        assert any(e.code == "empty_caveats" for e in result.errors)
        p.unlink()

    def test_public_copy_true_empty_metric_rows_fails(self):
        data = {
            "title": "Test",
            "command": "bench",
            "commit": "a1b2c3d",
            "product": "test",
            "ability": "test",
            "fixture_or_live_source": "Live run",
            "model_provider": "gpt-4o-mini",
            "environment_caveats": ["One caveat"],
            "public_copy_allowed": True,
            "metric_rows": [],
            "artifact": {},
        }
        p = _write_tmp_json(data)
        result = validate_evidence_artifact(p)
        assert result.ok is False
        assert any(e.code == "empty_metric_rows" for e in result.errors)
        p.unlink()

    def test_malformed_json(self):
        p = _write_tmp_str("not json")
        result = validate_evidence_artifact(p)
        assert result.ok is False
        assert any(e.code == "malformed_json" for e in result.errors)
        p.unlink()

    def test_non_dict_json(self):
        p = _write_tmp_str('["list", "not", "dict"]')
        result = validate_evidence_artifact(p)
        assert result.ok is False
        assert any(e.code == "malformed_json" for e in result.errors)
        p.unlink()

    def test_file_not_found(self):
        result = validate_evidence_artifact(Path("/nonexistent/evidence.json"))
        assert result.ok is False
        assert any(e.code == "file_not_found" for e in result.errors)


# ===================================================================
# Cross-check
# ===================================================================

class TestCrossCheck:
    def test_public_copy_true_no_matching_headline_warns(self, tmp_path):
        hl = tmp_path / "HEADLINE-NUMBERS.md"
        hl.write_text("""## Active Headline Numbers
| Product | Claim | Value | Source | Commit | Run date | Notes |
|---------|-------|-------|--------|--------|----------|-------|
| archolith-filter | compression | 50% | filter suite run | a1b2c3d | 2026-07-01 | Real run. |
""")
        ev = tmp_path / "evidence.json"
        ev.write_text(json.dumps({
            "title": "Proxy suite evidence",
            "command": "archolith-bench proxy",
            "commit": "a1b2c3d",
            "product": "archolith-context",
            "ability": "curation",
            "fixture_or_live_source": "Live run",
            "model_provider": "gpt-4o-mini",
            "environment_caveats": ["One caveat"],
            "public_copy_allowed": True,
            "metric_rows": [{"n": 1}],
            "artifact": {},
        }))
        result = validate_policy(hl, [ev])
        cross_warnings = [w for w in result.warnings if w.code == "no_matching_headline_claim"]
        assert len(cross_warnings) == 1, [w.message for w in result.warnings]

    def test_public_copy_true_matching_headline_ok(self, tmp_path):
        hl = tmp_path / "HEADLINE-NUMBERS.md"
        hl.write_text("""## Active Headline Numbers
| Product | Claim | Value | Source | Commit | Run date | Notes |
|---------|-------|-------|--------|--------|----------|-------|
| archolith-context | token savings | 60% | Proxy suite: `archolith-bench proxy` | a1b2c3d | 2026-07-01 | Real run. |
""")
        ev = tmp_path / "evidence.json"
        ev.write_text(json.dumps({
            "title": "Proxy suite evidence",
            "command": "archolith-bench proxy",
            "commit": "a1b2c3d",
            "product": "archolith-context",
            "ability": "curation",
            "fixture_or_live_source": "Live run",
            "model_provider": "gpt-4o-mini",
            "environment_caveats": ["One caveat"],
            "public_copy_allowed": True,
            "metric_rows": [{"n": 1}],
            "artifact": {},
        }))
        result = validate_policy(hl, [ev])
        cross_warnings = [w for w in result.warnings if w.code == "no_matching_headline_claim"]
        assert len(cross_warnings) == 0, [w.message for w in cross_warnings]


# ===================================================================
# Aggregate validate_policy
# ===================================================================

class TestValidatePolicy:
    def test_directory_mode_discovers_json_files(self, tmp_path):
        hl = tmp_path / "HEADLINE-NUMBERS.md"
        hl.write_text("## Active Headline Numbers\n| Product | Claim |\n|---------|-------|\n| _none_ | _none_ |\n")
        ev_dir = tmp_path / "evidence"
        ev_dir.mkdir()
        (ev_dir / "a.json").write_text("{}")
        (ev_dir / "b.json").write_text("{}")
        (ev_dir / "c.txt").write_text("not json")
        result = validate_policy(hl, sorted(ev_dir.glob("*.json")))
        assert result.summary["evidence_files_checked"] == 2

    def test_no_errors_passes(self, tmp_path):
        hl = tmp_path / "HEADLINE-NUMBERS.md"
        hl.write_text("## Active Headline Numbers\n| Product | Claim |\n|---------|-------|\n| _none_ | _none_ |\n")
        result = validate_policy(hl, [])
        assert result.ok is True


# ===================================================================
# CLI script
# ===================================================================

class TestCli:
    def test_json_mode_emits_parseable_json(self, tmp_path):
        hl = tmp_path / "HEADLINE-NUMBERS.md"
        hl.write_text("## Active Headline Numbers\n| Product | Claim |\n|---------|-------|\n| _none_ | _none_ |\n")
        result = subprocess.run(
            [sys.executable, "-m", "scripts.check_evidence_policy",
             "--headline", str(hl), "--json"],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parent.parent,
        )
        # Output must be parseable JSON only (no extra text in json mode)
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "ok" in data
        assert "errors" in data
        assert "warnings" in data
        assert "summary" in data

    def test_human_mode_prints_summary(self, tmp_path):
        hl = tmp_path / "HEADLINE-NUMBERS.md"
        hl.write_text("## Active Headline Numbers\n| Product | Claim |\n|---------|-------|\n| _none_ | _none_ |\n")
        result = subprocess.run(
            [sys.executable, "-m", "scripts.check_evidence_policy",
             "--headline", str(hl)],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parent.parent,
        )
        assert result.returncode == 0
        assert "Evidence policy: PASS" in result.stdout
        assert "headline_active_claims=0" in result.stdout

    def test_human_mode_fail_prints_fail(self, tmp_path):
        hl = tmp_path / "HEADLINE-NUMBERS.md"
        hl.write_text("""## Active Headline Numbers
| Product | Claim | Value | Source | Commit | Run date | Notes |
|---------|-------|-------|--------|--------|----------|-------|
| archolith-context | savings | pending | pending | pending | pending | pending |
""")
        result = subprocess.run(
            [sys.executable, "-m", "scripts.check_evidence_policy",
             "--headline", str(hl)],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parent.parent,
        )
        assert result.returncode == 1
        assert "Evidence policy: FAIL" in result.stdout

    def test_exit_code_2_on_missing_headline(self, tmp_path):
        result = subprocess.run(
            [sys.executable, "-m", "scripts.check_evidence_policy",
             "--headline", str(tmp_path / "nonexistent.md")],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parent.parent,
        )
        assert result.returncode == 2
        assert "ERROR" in result.stderr

    def test_directory_mode_discovery(self, tmp_path):
        hl = tmp_path / "HEADLINE-NUMBERS.md"
        hl.write_text("## Active Headline Numbers\n| Product | Claim |\n|---------|-------|\n| _none_ | _none_ |\n")
        ev_dir = tmp_path / "ev"
        ev_dir.mkdir()
        (ev_dir / "a.json").write_text('{"public_copy_allowed": false}')
        (ev_dir / "b.json").write_text('{"public_copy_allowed": false}')
        result = subprocess.run(
            [sys.executable, "-m", "scripts.check_evidence_policy",
             "--headline", str(hl), "--evidence-dir", str(ev_dir), "--json"],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parent.parent,
        )
        data = json.loads(result.stdout)
        assert data["summary"]["evidence_files_checked"] == 2


# ===================================================================
# Helpers
# ===================================================================

def _write_tmp_json(data: dict) -> Path:
    import tempfile
    p = Path(tempfile.mktemp(suffix=".json"))
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _write_tmp_str(s: str) -> Path:
    import tempfile
    p = Path(tempfile.mktemp(suffix=".json"))
    p.write_text(s, encoding="utf-8")
    return p
