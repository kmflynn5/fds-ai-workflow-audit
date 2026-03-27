from __future__ import annotations

import os
from unittest.mock import patch

from engine.claude_enricher import EnrichmentResult, is_available


def test_is_available_no_key():
    """Without API key, is_available returns False."""
    with patch.dict(os.environ, {}, clear=True):
        # Also need to handle case where ANTHROPIC_API_KEY might be inherited
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            assert is_available() is False


def test_is_available_no_package():
    """With API key but no anthropic package, is_available returns False."""
    import sys

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        # Mock the import to fail
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def mock_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("No module named 'anthropic'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Need to also remove from sys.modules cache
            cached = sys.modules.pop("anthropic", None)
            try:
                assert is_available() is False
            finally:
                if cached is not None:
                    sys.modules["anthropic"] = cached


def test_enrichment_result_defaults():
    """EnrichmentResult has sensible defaults."""
    result = EnrichmentResult()
    assert result.additional_failure_modes == []
    assert result.eval_criteria == []
    assert result.guardrail_recommendations == []
    assert result.model_mismatch_flags == []
    assert result.implicit_assumptions == []
    assert result.raw_response == ""


def test_enrich_raises_without_key():
    """enrich_assessment raises RuntimeError without API key."""
    import pytest

    from engine.claude_enricher import enrich_assessment

    with patch.dict(os.environ, {}, clear=True):
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                enrich_assessment("test", {})
