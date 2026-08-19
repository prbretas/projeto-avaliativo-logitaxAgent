"""Tests for the ChromaDB ingestion script (scripts/run_ingestao.py)."""

import shutil
import tempfile

import pytest

from scripts.run_ingestao import (
    CHUNKS,
    COLLECTION_NAME,
    get_chromadb_path,
    run_ingestao,
)


@pytest.fixture
def temp_chromadb_path():
    """Create a temporary directory for ChromaDB during tests."""
    tmp_dir = tempfile.mkdtemp(prefix="test_chromadb_")
    yield tmp_dir
    # Cleanup after test
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestRunIngestao:
    """Tests for the ingestion script execution."""

    def test_ingestao_completes_without_errors(self, temp_chromadb_path):
        """Verify the ingestion script runs to completion without errors."""
        stats = run_ingestao(temp_chromadb_path)

        assert stats["total_chunks"] > 0
        assert stats["errors"] == []

    def test_ingestao_indexes_all_chunks(self, temp_chromadb_path):
        """Verify all defined chunks are indexed."""
        stats = run_ingestao(temp_chromadb_path)

        assert stats["total_chunks"] == len(CHUNKS)

    def test_ingestao_is_idempotent(self, temp_chromadb_path):
        """Verify running ingestion twice does not duplicate documents."""
        import chromadb

        # Run twice
        run_ingestao(temp_chromadb_path)
        run_ingestao(temp_chromadb_path)

        # Verify count matches expected (no duplicates)
        client = chromadb.PersistentClient(path=temp_chromadb_path)
        collection = client.get_collection(name=COLLECTION_NAME)
        assert collection.count() == len(CHUNKS)

    def test_chunks_have_required_metadata(self, temp_chromadb_path):
        """Verify all indexed chunks contain the required metadata fields."""
        import chromadb

        run_ingestao(temp_chromadb_path)

        client = chromadb.PersistentClient(path=temp_chromadb_path)
        collection = client.get_collection(name=COLLECTION_NAME)

        results = collection.get(include=["metadatas"])

        for metadata in results["metadatas"]:
            assert "source_law" in metadata
            assert "article_number" in metadata
            assert "applicable_year_range" in metadata
            # Validate year range format (YYYY-YYYY)
            year_range = metadata["applicable_year_range"]
            parts = year_range.split("-")
            assert len(parts) == 2
            assert all(p.isdigit() and len(p) == 4 for p in parts)

    def test_chunks_cover_all_source_laws(self, temp_chromadb_path):
        """Verify chunks cover LC 214/2025, EC 132/2023, and NTs CT-e."""
        import chromadb

        run_ingestao(temp_chromadb_path)

        client = chromadb.PersistentClient(path=temp_chromadb_path)
        collection = client.get_collection(name=COLLECTION_NAME)

        results = collection.get(include=["metadatas"])
        source_laws = {m["source_law"] for m in results["metadatas"]}

        assert any("LC 214" in s for s in source_laws)
        assert any("EC 132" in s for s in source_laws)
        assert any("NT CT-e" in s for s in source_laws)

    def test_query_returns_relevant_results(self, temp_chromadb_path):
        """Verify vector search returns relevant chunks for a query."""
        import chromadb

        run_ingestao(temp_chromadb_path)

        client = chromadb.PersistentClient(path=temp_chromadb_path)
        collection = client.get_collection(name=COLLECTION_NAME)

        # Query about 2026 test phase
        results = collection.query(
            query_texts=["alíquota CBS IBS fase de teste 2026"],
            n_results=3,
        )

        assert len(results["documents"][0]) > 0
        # At least one result should mention 2026
        assert any("2026" in doc for doc in results["documents"][0])


class TestGetChromadbPath:
    """Tests for the path resolution function."""

    def test_returns_arg_path_when_provided(self):
        """Verify argument path takes priority."""
        result = get_chromadb_path("/custom/path")
        assert result == "/custom/path"

    def test_returns_env_path_when_set(self, monkeypatch):
        """Verify environment variable is used when no arg provided."""
        monkeypatch.setenv("CHROMADB_PATH", "/env/path")
        result = get_chromadb_path(None)
        assert result == "/env/path"

    def test_returns_default_path(self, monkeypatch):
        """Verify default path is returned when no arg or env set."""
        monkeypatch.delenv("CHROMADB_PATH", raising=False)
        result = get_chromadb_path(None)
        assert result == "./data/chromadb"


class TestChunksIntegrity:
    """Tests for the integrity of the hardcoded chunks."""

    def test_minimum_chunk_count(self):
        """Verify at least 10 chunks are defined."""
        assert len(CHUNKS) >= 10

    def test_all_chunks_have_required_fields(self):
        """Verify each chunk has id, document, and metadata."""
        for chunk in CHUNKS:
            assert "id" in chunk, f"Chunk missing 'id': {chunk}"
            assert "document" in chunk, f"Chunk '{chunk['id']}' missing 'document'"
            assert "metadata" in chunk, f"Chunk '{chunk['id']}' missing 'metadata'"

    def test_all_chunks_have_unique_ids(self):
        """Verify all chunk IDs are unique."""
        ids = [c["id"] for c in CHUNKS]
        assert len(ids) == len(set(ids)), "Duplicate chunk IDs found"

    def test_metadata_fields_present(self):
        """Verify all chunks have the three required metadata fields."""
        for chunk in CHUNKS:
            meta = chunk["metadata"]
            assert "source_law" in meta, f"Chunk '{chunk['id']}' missing source_law"
            assert "article_number" in meta, f"Chunk '{chunk['id']}' missing article_number"
            assert "applicable_year_range" in meta, (
                f"Chunk '{chunk['id']}' missing applicable_year_range"
            )

    def test_documents_are_non_empty(self):
        """Verify no chunk has an empty document text."""
        for chunk in CHUNKS:
            assert len(chunk["document"].strip()) > 0, f"Chunk '{chunk['id']}' has empty document"
