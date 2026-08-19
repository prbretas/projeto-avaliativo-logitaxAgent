"""Node retrieve_context: RAG retrieval from ChromaDB filtered by scenario.

Performs vector search in ChromaDB for legislative excerpts relevant to the
simulation scenario (year, regime). Returns up to 5 chunks with formatted
citations (e.g., "art. 343, LC 214/2025").

If zero chunks are found, proceeds without citations and adds a warning
to the alerts list.

Requirements: 7.1, 7.2, 7.3
"""

from __future__ import annotations

import logging
import os
from typing import Any

import chromadb

logger = logging.getLogger(__name__)

# ChromaDB collection name (must match ingestion script)
COLLECTION_NAME = "legislacao_tributaria"

# Maximum number of chunks to retrieve
MAX_CHUNKS = 5


def _get_chromadb_path() -> str:
    """Get ChromaDB path from environment variable or default."""
    return os.environ.get("CHROMADB_PATH", "./data/chromadb")


def _format_citation(metadata: dict) -> str:
    """Format a chunk's metadata into a citation string.

    Args:
        metadata: Chunk metadata with source_law and article_number.

    Returns:
        Formatted citation, e.g. "art. 343, LC 214/2025"
    """
    article = metadata.get("article_number", "")
    source = metadata.get("source_law", "")
    if article and source:
        return f"{article}, {source}"
    if source:
        return source
    return article or "fonte desconhecida"


def _build_where_filter(ano: int) -> dict | None:
    """Build ChromaDB metadata filter for applicable year range.

    Filters chunks whose applicable_year_range contains the target year.
    The year range is stored as "YYYY-YYYY" string in metadata.

    Since ChromaDB has limited filter operators, we query broadly and
    perform post-filtering in Python for year range matching.

    Args:
        ano: Target simulation year.

    Returns:
        None (we rely on post-filtering for year range matching).
    """
    # ChromaDB doesn't support range queries on string-encoded year ranges.
    # We'll retrieve more results and post-filter.
    return None


def _year_in_range(applicable_year_range: str, target_year: int) -> bool:
    """Check if target_year falls within an applicable_year_range string.

    Args:
        applicable_year_range: String in format "YYYY-YYYY".
        target_year: The year to check.

    Returns:
        True if the target year is within the range (inclusive).
    """
    try:
        parts = applicable_year_range.split("-")
        if len(parts) == 2:
            start_year = int(parts[0])
            end_year = int(parts[1])
            return start_year <= target_year <= end_year
    except (ValueError, TypeError):
        pass
    return False


def _retrieve_chunks(
    ano: int,
    regime: str,
    chromadb_path: str | None = None,
) -> list[dict]:
    """Retrieve relevant legislative chunks from ChromaDB.

    Args:
        ano: Reference year for the simulation.
        regime: Tax regime (lucro_real, lucro_presumido, simples_nacional).
        chromadb_path: Optional path override for ChromaDB storage.

    Returns:
        List of dicts with 'document', 'metadata', and 'citation' keys,
        filtered by year applicability, up to MAX_CHUNKS results.
    """
    path = chromadb_path or _get_chromadb_path()

    try:
        client = chromadb.PersistentClient(path=path)
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception as e:
        logger.warning(
            "Falha ao acessar coleção ChromaDB '%s': %s",
            COLLECTION_NAME,
            e,
        )
        return []

    # Build query text based on scenario context
    query_text = _build_query_text(ano, regime)

    # Retrieve more than needed so we can post-filter by year range
    n_results = MAX_CHUNKS * 3

    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, collection.count()),
        )
    except Exception as e:
        logger.warning("Falha na busca vetorial ChromaDB: %s", e)
        return []

    if not results or not results.get("documents") or not results["documents"][0]:
        return []

    # Post-filter by year range and format results
    filtered_chunks: list[dict] = []
    documents = results["documents"][0]
    metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(documents)

    for doc, meta in zip(documents, metadatas):
        applicable_range = meta.get("applicable_year_range", "")

        if _year_in_range(applicable_range, ano):
            filtered_chunks.append(
                {
                    "document": doc,
                    "metadata": meta,
                    "citation": _format_citation(meta),
                }
            )

        if len(filtered_chunks) >= MAX_CHUNKS:
            break

    return filtered_chunks


def _build_query_text(ano: int, regime: str) -> str:
    """Build a query text for semantic search based on scenario.

    Args:
        ano: Reference year.
        regime: Tax regime.

    Returns:
        Query string for ChromaDB semantic search.
    """
    regime_desc = {
        "simples_nacional": "Simples Nacional sem créditos",
        "lucro_real": "Lucro Real com créditos não-cumulativos",
        "lucro_presumido": "Lucro Presumido",
    }

    regime_text = regime_desc.get(regime, regime)

    if ano == 2026:
        context = "período de teste CBS 0,9% IBS 0,1%"
    elif ano <= 2028:
        context = "CBS substitui PIS COFINS, ICMS integral"
    elif ano <= 2032:
        context = f"phase-out ICMS, transição IBS CBS ano {ano}"
    else:
        context = "extinção ICMS, IBS CBS plenos 2033"

    return f"Alíquotas IBS CBS transporte frete {ano} {regime_text} {context}"


def retrieve_context(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: retrieve legislative context from ChromaDB via RAG.

    Performs vector search in ChromaDB filtered by the simulation scenario
    (year and regime). Returns up to 5 chunks with formatted citations.

    If zero chunks are found, proceeds without citations and adds a warning.

    Args:
        state: Current AgentState dict. Expected keys:
            - operacao: OperacaoFrete (or dict) with regime_tributario and data_referencia
            - resultados_por_ano: list[ResultadoAno] with simulation results

    Returns:
        Partial state update with:
            - trechos_rag: list[str] formatted citations with document excerpts
            - alertas: list[str] warnings (appended to existing)
    """
    operacao = state["operacao"]
    alertas: list[str] = list(state.get("alertas", []))

    # Extract operation fields (support both Pydantic model and dict)
    if hasattr(operacao, "regime_tributario"):
        regime = operacao.regime_tributario
        data_ref = operacao.data_referencia
        ano = data_ref.year if hasattr(data_ref, "year") else data_ref
    else:
        regime = operacao["regime_tributario"]
        data_ref = operacao["data_referencia"]
        ano = data_ref.year if hasattr(data_ref, "year") else data_ref

    logger.info(
        "retrieve_context: buscando trechos RAG para ano=%d, regime=%s",
        ano,
        regime,
    )

    # Perform retrieval
    chunks = _retrieve_chunks(ano=ano, regime=regime)

    # Format results as citation strings with document text
    trechos_rag: list[str] = []

    if chunks:
        for chunk in chunks:
            citation = chunk["citation"]
            # Truncate document text to keep state manageable
            doc_text = chunk["document"][:300]
            formatted = f"[{citation}] {doc_text}"
            trechos_rag.append(formatted)

        logger.info(
            "retrieve_context: %d trechos recuperados com citações: %s",
            len(trechos_rag),
            [c["citation"] for c in chunks],
        )
    else:
        # Zero chunks: proceed without citations + warning
        warning_msg = (
            "RAG: nenhum trecho legislativo encontrado para o cenário "
            f"(ano={ano}, regime={regime}). Justificativa será gerada "
            "sem citações legislativas."
        )
        alertas.append(warning_msg)
        logger.warning(warning_msg)

    return {
        "trechos_rag": trechos_rag,
        "alertas": alertas,
    }
