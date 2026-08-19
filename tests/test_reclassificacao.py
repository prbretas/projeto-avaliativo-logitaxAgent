"""Tests for the reclassification stopping condition node.

Validates:
- Counter increments correctly on each reclassification
- Counter at 3 forces human_review (revisao_manual=True)
- No re-entry after revisao_manual=True

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

from __future__ import annotations

from src.graph.nodes.check_reclassificacao import (
    check_reclassificacao,
    should_continue_or_review,
)
from src.models.estado import MAX_TENTATIVAS_RECLASSIFICACAO


class TestCheckReclassificacao:
    """Tests for the check_reclassificacao node function."""

    def test_first_reclassification_increments_counter(self) -> None:
        """Counter goes from 0 to 1 on first reclassification."""
        state = {
            "tentativas_reclassificacao": 0,
            "revisao_manual": False,
        }
        result = check_reclassificacao(state)

        assert result["tentativas_reclassificacao"] == 1
        assert result["revisao_manual"] is False

    def test_second_reclassification_increments_counter(self) -> None:
        """Counter goes from 1 to 2 on second reclassification."""
        state = {
            "tentativas_reclassificacao": 1,
            "revisao_manual": False,
        }
        result = check_reclassificacao(state)

        assert result["tentativas_reclassificacao"] == 2
        assert result["revisao_manual"] is False

    def test_third_reclassification_forces_human_review(self) -> None:
        """Counter at 2 → increment to 3 → forces revisao_manual=True."""
        state = {
            "tentativas_reclassificacao": 2,
            "revisao_manual": False,
        }
        result = check_reclassificacao(state)

        assert result["tentativas_reclassificacao"] == 3
        assert result["revisao_manual"] is True

    def test_no_reentry_when_revisao_manual_true(self) -> None:
        """If revisao_manual is already True, counter does NOT increment."""
        state = {
            "tentativas_reclassificacao": 3,
            "revisao_manual": True,
        }
        result = check_reclassificacao(state)

        # Counter stays the same, revisao_manual stays True
        assert result["tentativas_reclassificacao"] == 3
        assert result["revisao_manual"] is True

    def test_no_reentry_even_with_lower_counter(self) -> None:
        """If revisao_manual is True (e.g., forced early), no re-entry."""
        state = {
            "tentativas_reclassificacao": 1,
            "revisao_manual": True,
        }
        result = check_reclassificacao(state)

        # Counter stays at 1, revisao_manual stays True
        assert result["tentativas_reclassificacao"] == 1
        assert result["revisao_manual"] is True

    def test_counter_never_exceeds_max(self) -> None:
        """Counter should reach MAX but never exceed it via normal flow."""
        state = {
            "tentativas_reclassificacao": 0,
            "revisao_manual": False,
        }

        # Simulate sequential reclassifications
        for i in range(1, MAX_TENTATIVAS_RECLASSIFICACAO + 2):
            result = check_reclassificacao(state)
            state = {
                "tentativas_reclassificacao": result["tentativas_reclassificacao"],
                "revisao_manual": result["revisao_manual"],
            }

            if i < MAX_TENTATIVAS_RECLASSIFICACAO:
                assert result["tentativas_reclassificacao"] == i
                assert result["revisao_manual"] is False
            else:
                # Once MAX is reached, revisao_manual=True blocks further increments
                assert result["tentativas_reclassificacao"] <= MAX_TENTATIVAS_RECLASSIFICACAO
                assert result["revisao_manual"] is True

    def test_defaults_when_fields_missing(self) -> None:
        """Handles state dict without explicit keys (uses defaults)."""
        state: dict = {}
        result = check_reclassificacao(state)

        assert result["tentativas_reclassificacao"] == 1
        assert result["revisao_manual"] is False


class TestShouldContinueOrReview:
    """Tests for the should_continue_or_review conditional edge function."""

    def test_returns_continue_when_counter_zero(self) -> None:
        """Fresh state → continue."""
        state = {
            "tentativas_reclassificacao": 0,
            "revisao_manual": False,
        }
        assert should_continue_or_review(state) == "continue"

    def test_returns_continue_when_counter_below_max(self) -> None:
        """Counter below MAX and no manual flag → continue."""
        state = {
            "tentativas_reclassificacao": 2,
            "revisao_manual": False,
        }
        assert should_continue_or_review(state) == "continue"

    def test_returns_human_review_when_counter_at_max(self) -> None:
        """Counter at MAX → human_review."""
        state = {
            "tentativas_reclassificacao": MAX_TENTATIVAS_RECLASSIFICACAO,
            "revisao_manual": False,
        }
        assert should_continue_or_review(state) == "human_review"

    def test_returns_human_review_when_revisao_manual_true(self) -> None:
        """revisao_manual=True → human_review regardless of counter."""
        state = {
            "tentativas_reclassificacao": 1,
            "revisao_manual": True,
        }
        assert should_continue_or_review(state) == "human_review"

    def test_returns_human_review_when_both_conditions_met(self) -> None:
        """Both counter at MAX and revisao_manual=True → human_review."""
        state = {
            "tentativas_reclassificacao": MAX_TENTATIVAS_RECLASSIFICACAO,
            "revisao_manual": True,
        }
        assert should_continue_or_review(state) == "human_review"

    def test_defaults_when_fields_missing(self) -> None:
        """Handles missing keys gracefully (defaults to continue)."""
        state: dict = {}
        assert should_continue_or_review(state) == "continue"

    def test_counter_above_max_still_routes_to_review(self) -> None:
        """Edge case: if counter somehow exceeds MAX, still routes to review."""
        state = {
            "tentativas_reclassificacao": 5,
            "revisao_manual": False,
        }
        assert should_continue_or_review(state) == "human_review"
