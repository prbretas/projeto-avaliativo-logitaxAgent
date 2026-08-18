"""Property tests para condição de parada (reclassificação).

Property 9: Reclassification counter never exceeds 3.
Property 10: No re-entry after forced human review.

Validates: Requirements 6.3, 6.4, 6.5
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from src.models.estado import AgentState, MAX_TENTATIVAS_RECLASSIFICACAO
from src.graph.nodes.check_reclassificacao import check_reclassificacao


# --- Property 9: Reclassification counter never exceeds 3 ---


@given(tentativas=st.integers(min_value=0, max_value=10))
@settings(max_examples=30)
def test_reclassification_counter_never_exceeds_3(tentativas):
    """Property 9: tentativas_reclassificacao never exceeds MAX (3)."""
    if tentativas > MAX_TENTATIVAS_RECLASSIFICACAO:
        # Pydantic should reject values > 3
        try:
            from src.models.operacao import OperacaoFrete
            AgentState(
                operacao=OperacaoFrete(
                    modal="rodoviario",
                    origem_uf="SP",
                    destino_uf="RJ",
                    regime_tributario="lucro_real",
                    valor_frete=10000.0,
                    data_referencia="2026-06-15",
                ),
                thread_id="test",
                tentativas_reclassificacao=tentativas,
            )
            assert False, f"Should reject tentativas={tentativas} > {MAX_TENTATIVAS_RECLASSIFICACAO}"
        except (ValidationError, ValueError):
            pass  # Expected
    else:
        # Valid values should be accepted
        from src.models.operacao import OperacaoFrete
        state = AgentState(
            operacao=OperacaoFrete(
                modal="rodoviario",
                origem_uf="SP",
                destino_uf="RJ",
                regime_tributario="lucro_real",
                valor_frete=10000.0,
                data_referencia="2026-06-15",
            ),
            thread_id="test",
            tentativas_reclassificacao=tentativas,
        )
        assert state.tentativas_reclassificacao <= MAX_TENTATIVAS_RECLASSIFICACAO


@given(tentativas=st.integers(min_value=0, max_value=3))
@settings(max_examples=10)
def test_max_attempts_forces_human_review(tentativas):
    """Property 9b: When counter reaches 3, human_review is forced."""
    state = {
        "tentativas_reclassificacao": tentativas,
        "revisao_manual": False,
    }

    result = check_reclassificacao(state)

    if tentativas >= MAX_TENTATIVAS_RECLASSIFICACAO:
        assert result.get("revisao_manual") is True, (
            f"Should force human_review when tentativas={tentativas}"
        )


# --- Property 10: No re-entry after forced human review ---


@given(tentativas=st.integers(min_value=0, max_value=3))
@settings(max_examples=10)
def test_no_reentry_after_forced_review(tentativas):
    """Property 10: After revisao_manual=True, no return to simulation loop."""
    state = {
        "tentativas_reclassificacao": tentativas,
        "revisao_manual": True,  # Already forced
    }

    # Once revisao_manual is True, should stay True
    result = check_reclassificacao(state)
    assert result.get("revisao_manual") is True, (
        "revisao_manual should remain True once set"
    )
