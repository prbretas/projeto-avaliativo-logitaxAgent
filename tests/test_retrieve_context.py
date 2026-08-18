"""Tests for the retrieve_context node.

Validates:
- Vector search in ChromaDB filtered by scenario (year, regime)
- Returns up to 5 chunks with formatted citations
- Handles zero chunks case: proceeds without citations + warning
- Requirements: 7.1, 7.2, 7.3
"""

import os
import tempfile
from datetime import date

import pytest

from src.graph.nodes.retrieve_context import (
    COLLECTION_NAME,
    MAX_CHUNKS,
    _build_query_text,
    _format_citation,
    _year_in_range,
    retrieve_context,
)


class TestFormatCitation:
    """Test _format_citation helper function."""

    def test_full_citation_with_article_and_source(self):
        meta = {"source_law": "LC 214/2025", "article_number": "art. 343"}
        assert _format_citation(meta) == "art. 343, LC 214/2025"

    def test_citation_source_only(self):
        meta = {"source_law": "LC 214/2025"}
        assert _format_citation(meta) == "LC 214/2025"

    def test_citation_article_only(self):
        meta = {"article_number": "art. 343"}
        assert _format_citation(meta) == "art. 343"

    def test_citation_empty_metadata(self):
        meta = {}
        assert _format_citation(meta) == "fonte desconhecida"

    def test_citation_empty_strings(self):
        meta = {"source_law": "", "article_number": ""}
        assert _format_citation(meta) == "fonte desconhecida"


class TestYearInRange:
    """Test _year_in_range helper function."""

    def test_year_at_start_of_range(self):
        assert _year_in_range("2026-2033", 2026) is True

    def test_year_at_end_of_range(self):
        assert _year_in_range("2026-2033", 2033) is True

    def test_year_in_middle_of_range(self):
        assert _year_in_range("2029-2032", 2030) is True

    def test_year_before_range(self):
        assert _year_in_range("2026-2033", 2025) is False

    def test_year_after_range(self):
        assert _year_in_range("2029-2032", 2033) is False

    def test_invalid_range_format(self):
        assert _year_in_range("invalid", 2026) is False

    def test_empty_range(self):
        assert _year_in_range("", 2026) is False

    def test_single_year_range(self):
        assert _year_in_range("2026-2026", 2026) is True
        assert _year_in_range("2026-2026", 2027) is False


class TestBuildQueryText:
    """Test _build_query_text for correct semantic query construction."""

    def test_2026_test_phase(self):
        query = _build_query_text(2026, "lucro_real")
        assert "2026" in query
        assert "Lucro Real" in query
        assert "teste" in query

    def test_2027_cbs_substitution(self):
        query = _build_query_text(2027, "lucro_presumido")
        assert "2027" in query
        assert "Lucro Presumido" in query
        assert "CBS substitui" in query

    def test_2030_phase_out(self):
        query = _build_query_text(2030, "simples_nacional")
        assert "2030" in query
        assert "Simples Nacional" in query
        assert "phase-out" in query

    def test_2033_full_transition(self):
        query = _build_query_text(2033, "lucro_real")
        assert "2033" in query
        assert "extinção ICMS" in query

    def test_unknown_regime_used_as_is(self):
        query = _build_query_text(2026, "unknown_regime")
        assert "unknown_regime" in query


class TestRetrieveContextNodeZeroChunks:
    """Test retrieve_context node with zero chunks (no ChromaDB data)."""

    def test_zero_chunks_returns_warning(self):
        """When no chunks found, should proceed without citations + add warning."""
        # Use a nonexistent path so ChromaDB collection won't be found
        os.environ["CHROMADB_PATH"] = os.path.join(tempfile.gettempdir(), "nonexistent_chromadb")

        state = {
            "operacao": {
                "regime_tributario": "lucro_real",
                "data_referencia": date(2026, 6, 15),
            },
            "resultados_por_ano": [],
            "alertas": [],
        }

        result = retrieve_context(state)

        assert result["trechos_rag"] == []
        assert len(result["alertas"]) == 1
        assert "nenhum trecho legislativo" in result["alertas"][0]
        assert "ano=2026" in result["alertas"][0]
        assert "regime=lucro_real" in result["alertas"][0]

    def test_zero_chunks_preserves_existing_alerts(self):
        """Existing alerts in state should be preserved."""
        os.environ["CHROMADB_PATH"] = os.path.join(tempfile.gettempdir(), "nonexistent_chromadb")

        state = {
            "operacao": {
                "regime_tributario": "simples_nacional",
                "data_referencia": date(2030, 1, 1),
            },
            "resultados_por_ano": [],
            "alertas": ["alerta anterior"],
        }

        result = retrieve_context(state)

        assert len(result["alertas"]) == 2
        assert result["alertas"][0] == "alerta anterior"
        assert "nenhum trecho legislativo" in result["alertas"][1]


class TestRetrieveContextNodeWithChromDB:
    """Test retrieve_context node with actual ChromaDB data."""

    def test_retrieval_with_existing_chromadb(self):
        """When ChromaDB has data, should retrieve relevant chunks with citations."""
        # Use the project's actual ChromaDB data (populated by run_ingestao.py)
        chromadb_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "chromadb",
        )

        if not os.path.exists(chromadb_path):
            pytest.skip("ChromaDB data not available - run scripts/run_ingestao.py first")

        os.environ["CHROMADB_PATH"] = chromadb_path

        state = {
            "operacao": {
                "regime_tributario": "lucro_real",
                "data_referencia": date(2026, 6, 15),
            },
            "resultados_por_ano": [],
            "alertas": [],
        }

        result = retrieve_context(state)

        # If chunks exist for 2026, they should be formatted with citations
        if result["trechos_rag"]:
            assert len(result["trechos_rag"]) <= MAX_CHUNKS
            for trecho in result["trechos_rag"]:
                # Each trecho should be formatted as "[citation] text..."
                assert trecho.startswith("[")
                assert "]" in trecho
            # No warning should be added if chunks were found
            assert all("nenhum trecho" not in a for a in result["alertas"])

    def test_retrieval_max_5_chunks(self):
        """Should never return more than 5 chunks."""
        chromadb_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "chromadb",
        )

        if not os.path.exists(chromadb_path):
            pytest.skip("ChromaDB data not available - run scripts/run_ingestao.py first")

        os.environ["CHROMADB_PATH"] = chromadb_path

        state = {
            "operacao": {
                "regime_tributario": "lucro_real",
                "data_referencia": date(2030, 6, 15),
            },
            "resultados_por_ano": [],
            "alertas": [],
        }

        result = retrieve_context(state)
        assert len(result["trechos_rag"]) <= 5

    def test_supports_pydantic_model_operacao(self):
        """Should support Pydantic OperacaoFrete model as well as dict."""
        chromadb_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "chromadb",
        )

        if not os.path.exists(chromadb_path):
            pytest.skip("ChromaDB data not available - run scripts/run_ingestao.py first")

        os.environ["CHROMADB_PATH"] = chromadb_path

        from src.models.operacao import OperacaoFrete

        operacao = OperacaoFrete(
            modal="rodoviario",
            origem_uf="SP",
            destino_uf="RJ",
            regime_tributario="lucro_real",
            valor_frete=10000.00,
            data_referencia=date(2026, 6, 15),
        )

        state = {
            "operacao": operacao,
            "resultados_por_ano": [],
            "alertas": [],
        }

        # Should not raise - should handle both dict and Pydantic model
        result = retrieve_context(state)
        assert "trechos_rag" in result
        assert "alertas" in result


class TestMaxChunksConstant:
    """Verify MAX_CHUNKS is set to 5 per requirements."""

    def test_max_chunks_is_5(self):
        assert MAX_CHUNKS == 5


class TestCollectionName:
    """Verify the collection name matches the ingestion script."""

    def test_collection_name_matches_ingestao(self):
        assert COLLECTION_NAME == "legislacao_tributaria"
