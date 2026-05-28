#!/usr/bin/env python3
"""
test_knowledge_core.py — Tests for core/knowledge_core/

Coverage:
- Schemas: frozen, deterministic chunk_id, MEMORY_TYPES
- Chunker: text splitting, overlap, markdown, wikilinks, code blocks
- Document ingestor: .md, .json, .py, directory walk
- Embedding cache: hash dedup, shape, float32, fallback
- Knowledge store: FAISS add/search/dedup/thread-safety
- Vault indexer: incremental, manifest, vault missing
- Retrieval engine: search_memory, format_for_context
- Semantic memory: persist_learning, queue append-only
- Knowledge graph: add_node, add_link, BFS, wikilink parsing
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

_IMPERIO_ROOT = Path(__file__).parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemas:
    def test_knowledge_chunk_frozen(self):
        from core.knowledge_core.schemas import KnowledgeChunk
        chunk = KnowledgeChunk(
            chunk_id="abc123", content="test", source_file="test.md",
            memory_type="technical", tags=("tag1",), created_at="2026-01-01T00:00:00Z",
            chunk_index=0,
        )
        with pytest.raises((AttributeError, TypeError)):
            chunk.content = "mutated"

    def test_search_result_frozen(self):
        from core.knowledge_core.schemas import KnowledgeChunk, SearchResult
        chunk = KnowledgeChunk(
            chunk_id="abc", content="x", source_file="f.md",
            memory_type="technical", tags=(), created_at="2026-01-01T00:00:00Z",
            chunk_index=0,
        )
        result = SearchResult(chunk=chunk, score=0.9, rank=1)
        with pytest.raises((AttributeError, TypeError)):
            result.score = 0.5

    def test_memory_types_is_frozenset(self):
        from core.knowledge_core.schemas import MEMORY_TYPES
        assert isinstance(MEMORY_TYPES, frozenset)

    def test_memory_types_contains_expected(self):
        from core.knowledge_core.schemas import MEMORY_TYPES
        expected = {"technical", "prompt", "revenue", "visual_archetype", "failure", "architecture"}
        assert expected.issubset(MEMORY_TYPES)

    def test_chunk_id_deterministic(self):
        from core.knowledge_core.schemas import KnowledgeChunk
        import hashlib
        content = "test content"
        chunk_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        chunk = KnowledgeChunk(
            chunk_id=chunk_id, content=content, source_file="f.md",
            memory_type="technical", tags=(), created_at="now", chunk_index=0,
        )
        assert chunk.chunk_id == chunk_id


# ─────────────────────────────────────────────────────────────────────────────
# Chunker
# ─────────────────────────────────────────────────────────────────────────────

class TestChunker:
    def test_chunk_text_basic(self):
        from core.knowledge_core.chunker import chunk_text
        text = "This is a test. " * 20
        chunks = chunk_text(text)
        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)

    def test_chunk_text_empty_returns_empty(self):
        from core.knowledge_core.chunker import chunk_text
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_chunk_text_size_respects_limit(self):
        from core.knowledge_core.chunker import chunk_text, CHARS_PER_TOKEN
        text = "word " * 1000
        chunks = chunk_text(text, chunk_size=100)
        hard_limit = 100 * CHARS_PER_TOKEN * 1.5
        for chunk in chunks:
            assert len(chunk) <= hard_limit

    def test_chunk_markdown_strips_wikilinks(self):
        from core.knowledge_core.chunker import chunk_markdown
        md = "# Header\n\nSee [[Architecture Overview]] for details. [[Pipeline|Main Pipeline]]."
        result = chunk_markdown(md)
        assert len(result) > 0
        full_text = " ".join(chunk for chunk, tags in result)
        assert "[[" not in full_text
        assert "Architecture Overview" in full_text

    def test_chunk_markdown_wikilink_alias(self):
        from core.knowledge_core.chunker import chunk_markdown
        md = "# Test\n\nSee [[Target|Alias Display]] for more."
        result = chunk_markdown(md)
        full_text = " ".join(chunk for chunk, tags in result)
        assert "Alias Display" in full_text
        assert "[[" not in full_text

    def test_chunk_markdown_extracts_tags_from_headers(self):
        from core.knowledge_core.chunker import chunk_markdown
        md = "# Title\n\n## Architecture Section\n\nSome content here."
        result = chunk_markdown(md)
        assert len(result) > 0
        all_tags = [tag for _, tags in result for tag in tags]
        assert any("architecture" in tag.lower() for tag in all_tags)

    def test_chunk_markdown_empty_returns_empty(self):
        from core.knowledge_core.chunker import chunk_markdown
        assert chunk_markdown("") == []
        assert chunk_markdown("   ") == []

    def test_chunk_markdown_no_headers(self):
        from core.knowledge_core.chunker import chunk_markdown
        md = "Just some plain text without headers. More text here."
        result = chunk_markdown(md)
        assert len(result) >= 1

    def test_chunk_markdown_returns_list_of_tuples(self):
        from core.knowledge_core.chunker import chunk_markdown
        md = "# Header\n\nContent here."
        result = chunk_markdown(md)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)
            assert isinstance(item[1], list)

    def test_chunk_markdown_frontmatter_tags_extracted(self):
        from core.knowledge_core.chunker import chunk_markdown
        md = "---\ntags: technical architecture\n---\n\n# Content\n\nSome text."
        result = chunk_markdown(md)
        all_tags = [tag for _, tags in result for tag in tags]
        assert any("technical" in t or "architecture" in t for t in all_tags)


# ─────────────────────────────────────────────────────────────────────────────
# Document Ingestor
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentIngestor:
    def test_ingest_markdown_file(self, tmp_path):
        from core.knowledge_core.document_ingestor import ingest_file
        md_file = tmp_path / "test.md"
        md_file.write_text("# Title\n\nSome content here.\n\n## Section\n\nMore content.")
        result = ingest_file(md_file)
        assert len(result) >= 1
        assert all(isinstance(r, tuple) and len(r) == 2 for r in result)

    def test_ingest_json_file(self, tmp_path):
        from core.knowledge_core.document_ingestor import ingest_file
        json_file = tmp_path / "data.json"
        json_file.write_text(json.dumps({"key": "This is a value with enough text to chunk."}))
        result = ingest_file(json_file)
        assert len(result) >= 1

    def test_ingest_python_file(self, tmp_path):
        from core.knowledge_core.document_ingestor import ingest_file
        py_file = tmp_path / "module.py"
        py_file.write_text('"""Module docstring for testing."""\n\ndef func():\n    """Function docstring."""\n    pass\n')
        result = ingest_file(py_file)
        assert len(result) >= 1

    def test_ingest_nonexistent_file_returns_empty(self):
        from core.knowledge_core.document_ingestor import ingest_file
        result = ingest_file(Path("/nonexistent/file.md"))
        assert result == []

    def test_ingest_directory_walks_recursively(self, tmp_path):
        from core.knowledge_core.document_ingestor import ingest_directory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.md").write_text("# Root\n\nContent.")
        (subdir / "nested.md").write_text("# Nested\n\nNested content.")
        result = ingest_directory(tmp_path, patterns=["*.md"])
        paths = [str(r[0]) for r in result]
        assert any("root.md" in p for p in paths)
        assert any("nested.md" in p for p in paths)

    def test_ingest_directory_skips_obsidian(self, tmp_path):
        from core.knowledge_core.document_ingestor import ingest_directory
        obsidian = tmp_path / ".obsidian"
        obsidian.mkdir()
        (obsidian / "config.md").write_text("# Obsidian Config\n\nDo not index.")
        (tmp_path / "real.md").write_text("# Real content\n\nIndex this.")
        result = ingest_directory(tmp_path, patterns=["*.md"])
        paths = [str(r[0]) for r in result]
        assert not any(".obsidian" in p for p in paths)
        assert any("real.md" in p for p in paths)

    def test_ingest_directory_skips_pycache(self, tmp_path):
        from core.knowledge_core.document_ingestor import ingest_directory
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "module.py").write_text("cached = True")
        (tmp_path / "real.py").write_text('"""Real module."""\ndef fn(): pass\n')
        result = ingest_directory(tmp_path, patterns=["*.py"])
        paths = [str(r[0]) for r in result]
        assert not any("__pycache__" in p for p in paths)

    def test_ingest_empty_file_returns_empty(self, tmp_path):
        from core.knowledge_core.document_ingestor import ingest_file
        empty = tmp_path / "empty.md"
        empty.write_text("")
        result = ingest_file(empty)
        assert result == []

    def test_ingest_directory_returns_path_chunk_tags(self, tmp_path):
        from core.knowledge_core.document_ingestor import ingest_directory
        (tmp_path / "doc.md").write_text("# Title\n\nContent here.")
        result = ingest_directory(tmp_path, patterns=["*.md"])
        assert len(result) >= 1
        for path, chunk_text, tags in result:
            assert isinstance(path, Path)
            assert isinstance(chunk_text, str)
            assert isinstance(tags, list)


# ─────────────────────────────────────────────────────────────────────────────
# Embedding Cache
# ─────────────────────────────────────────────────────────────────────────────

class TestEmbeddingCache:
    def test_get_embedding_returns_array(self, tmp_path, monkeypatch):
        import core.knowledge_core.embedding_cache as ec
        monkeypatch.setattr(ec, "CACHE_DIR", tmp_path)
        vec = ec.get_embedding("test text for embedding")
        assert isinstance(vec, np.ndarray)

    def test_embedding_shape_correct(self, tmp_path, monkeypatch):
        import core.knowledge_core.embedding_cache as ec
        monkeypatch.setattr(ec, "CACHE_DIR", tmp_path)
        vec = ec.get_embedding("shape test")
        assert vec.shape == (ec.EMBEDDING_DIM,)

    def test_embedding_is_float32(self, tmp_path, monkeypatch):
        import core.knowledge_core.embedding_cache as ec
        monkeypatch.setattr(ec, "CACHE_DIR", tmp_path)
        vec = ec.get_embedding("dtype test")
        assert vec.dtype == np.float32

    def test_same_text_same_embedding(self, tmp_path, monkeypatch):
        import core.knowledge_core.embedding_cache as ec
        monkeypatch.setattr(ec, "CACHE_DIR", tmp_path)
        vec1 = ec.get_embedding("deterministic text")
        vec2 = ec.get_embedding("deterministic text")
        np.testing.assert_array_equal(vec1, vec2)

    def test_different_texts_different_embeddings(self, tmp_path, monkeypatch):
        import core.knowledge_core.embedding_cache as ec
        monkeypatch.setattr(ec, "CACHE_DIR", tmp_path)
        vec1 = ec.get_embedding("first unique text abc")
        vec2 = ec.get_embedding("second different text xyz")
        assert not np.allclose(vec1, vec2, atol=1e-6)

    def test_cache_saves_file(self, tmp_path, monkeypatch):
        import core.knowledge_core.embedding_cache as ec
        monkeypatch.setattr(ec, "CACHE_DIR", tmp_path)
        text = "cache save test"
        ec.get_embedding(text)
        cache_files = list(tmp_path.glob("*.npy"))
        assert len(cache_files) >= 1

    def test_cache_hit_on_second_call(self, tmp_path, monkeypatch):
        import core.knowledge_core.embedding_cache as ec
        monkeypatch.setattr(ec, "CACHE_DIR", tmp_path)
        text = "cache hit test"
        # First call computes
        ec.get_embedding(text)
        # Patch _compute_embedding to detect if called again
        call_count = {"n": 0}
        original_compute = ec._compute_embedding
        def counting_compute(t):
            call_count["n"] += 1
            return original_compute(t)
        monkeypatch.setattr(ec, "_compute_embedding", counting_compute)
        # Second call should use cache
        ec.get_embedding(text)
        assert call_count["n"] == 0  # Should not recompute

    def test_empty_text_returns_zeros(self, tmp_path, monkeypatch):
        import core.knowledge_core.embedding_cache as ec
        monkeypatch.setattr(ec, "CACHE_DIR", tmp_path)
        vec = ec.get_embedding("")
        assert vec.shape == (ec.EMBEDDING_DIM,)
        assert np.all(vec == 0)

    def test_tfidf_fallback_produces_valid_embedding(self):
        import core.knowledge_core.embedding_cache as ec
        vec = ec._compute_tfidf("tfidf fallback test text")
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (ec.EMBEDDING_DIM,)
        assert vec.dtype == np.float32

    def test_clear_stale_removes_old_files(self, tmp_path, monkeypatch):
        import time as _time
        import core.knowledge_core.embedding_cache as ec
        monkeypatch.setattr(ec, "CACHE_DIR", tmp_path)
        old_file = tmp_path / "old.npy"
        np.save(str(old_file), np.zeros(384, dtype=np.float32))
        # Manually set old mtime
        old_time = _time.time() - 40 * 86400
        os.utime(str(old_file), (old_time, old_time))
        removed = ec.clear_stale(max_age_days=30)
        assert removed >= 1
        assert not old_file.exists()


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge Store
# ─────────────────────────────────────────────────────────────────────────────

class TestKnowledgeStore:
    def _make_chunk(self, chunk_id="c1", content="test content"):
        from core.knowledge_core.schemas import KnowledgeChunk
        return KnowledgeChunk(
            chunk_id=chunk_id, content=content, source_file="test.md",
            memory_type="technical", tags=("test",), created_at="2026-01-01T00:00:00Z",
            chunk_index=0,
        )

    def _make_embedding(self):
        vec = np.random.rand(384).astype(np.float32)
        return vec / np.linalg.norm(vec)

    def test_add_chunk_returns_row_index(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_store as ks
        monkeypatch.setattr(ks, "STORE_DIR", tmp_path)
        chunk = self._make_chunk()
        emb   = self._make_embedding()
        idx = ks.add_chunk("technical", emb, chunk)
        assert isinstance(idx, int)
        assert idx >= 0

    def test_add_chunk_dedup_by_chunk_id(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_store as ks
        monkeypatch.setattr(ks, "STORE_DIR", tmp_path)
        chunk = self._make_chunk()
        emb   = self._make_embedding()
        idx1 = ks.add_chunk("technical", emb, chunk)
        idx2 = ks.add_chunk("technical", emb, chunk)  # same chunk_id
        assert idx1 == idx2
        assert ks.count("technical") == 1

    def test_search_returns_results(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_store as ks
        monkeypatch.setattr(ks, "STORE_DIR", tmp_path)
        emb   = self._make_embedding()
        chunk = self._make_chunk()
        ks.add_chunk("technical", emb, chunk)
        results = ks.search("technical", emb, top_k=5)
        assert len(results) >= 1
        score, found_chunk = results[0]
        assert isinstance(score, float)
        assert found_chunk.chunk_id == chunk.chunk_id

    def test_search_empty_store_returns_empty(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_store as ks
        monkeypatch.setattr(ks, "STORE_DIR", tmp_path)
        emb = self._make_embedding()
        results = ks.search("empty_type_xyz", emb, top_k=5)
        assert results == []

    def test_count_reflects_added_chunks(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_store as ks
        monkeypatch.setattr(ks, "STORE_DIR", tmp_path)
        for i in range(3):
            chunk = self._make_chunk(chunk_id=f"c{i}", content=f"content {i}")
            emb   = self._make_embedding()
            ks.add_chunk("technical", emb, chunk)
        assert ks.count("technical") == 3

    def test_list_types_returns_indexed_types(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_store as ks
        monkeypatch.setattr(ks, "STORE_DIR", tmp_path)
        for mtype in ["technical", "prompt"]:
            chunk = self._make_chunk(chunk_id=mtype, content=f"{mtype} content")
            emb   = self._make_embedding()
            ks.add_chunk(mtype, emb, chunk)
        types = ks.list_types()
        assert "technical" in types
        assert "prompt" in types

    def test_search_all_types_merges(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_store as ks
        monkeypatch.setattr(ks, "STORE_DIR", tmp_path)
        emb = self._make_embedding()
        for mtype in ["technical", "architecture"]:
            chunk = self._make_chunk(chunk_id=mtype, content=f"{mtype} content")
            ks.add_chunk(mtype, emb, chunk)
        results = ks.search_all_types(emb, top_k=5)
        assert len(results) >= 2

    def test_thread_safety_concurrent_adds(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_store as ks
        monkeypatch.setattr(ks, "STORE_DIR", tmp_path)
        errors = []

        def add_chunk_worker(i):
            try:
                chunk = self._make_chunk(chunk_id=f"thread_{i}", content=f"thread content {i}")
                emb   = self._make_embedding()
                ks.add_chunk("technical", emb, chunk)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=add_chunk_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert ks.count("technical") == 10


# ─────────────────────────────────────────────────────────────────────────────
# Vault Indexer
# ─────────────────────────────────────────────────────────────────────────────

class TestVaultIndexer:
    def test_index_vault_missing_returns_error_dict(self):
        from core.knowledge_core.vault_indexer import index_vault
        result = index_vault(vault_path=Path("/nonexistent/vault_xyz"))
        assert "error" in result or result["indexed"] == 0

    def test_index_vault_indexes_md_files(self, tmp_path, monkeypatch):
        from core.knowledge_core import vault_indexer as vi
        import core.knowledge_core.knowledge_store as ks
        monkeypatch.setattr(vi, "INDEX_MANIFEST", tmp_path / "manifest.json")
        monkeypatch.setattr(ks, "STORE_DIR", tmp_path / "store")
        (tmp_path / "store").mkdir()
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "note1.md").write_text("# Note\n\nContent for indexing.")
        (vault / "note2.md").write_text("# Another\n\nMore content.")

        with patch("core.knowledge_core.vault_indexer.get_embedding") as mock_emb:
            mock_emb.return_value = np.zeros(384, dtype=np.float32)
            with patch("core.knowledge_core.vault_indexer.ks.add_chunk", return_value=0) as mock_add:
                result = vi.index_vault(vault_path=vault, force=True)
        assert result["files_seen"] >= 2

    def test_index_vault_skips_obsidian_dir(self, tmp_path, monkeypatch):
        from core.knowledge_core import vault_indexer as vi
        monkeypatch.setattr(vi, "INDEX_MANIFEST", tmp_path / "manifest.json")
        vault = tmp_path / "vault"
        vault.mkdir()
        obsidian = vault / ".obsidian"
        obsidian.mkdir()
        (obsidian / "config.md").write_text("# Config\n\nInternal.")
        (vault / "real.md").write_text("# Real\n\nActual content.")

        with patch("core.knowledge_core.vault_indexer.get_embedding") as mock_emb:
            mock_emb.return_value = np.zeros(384, dtype=np.float32)
            with patch("core.knowledge_core.vault_indexer.ks.add_chunk", return_value=0):
                result = vi.index_vault(vault_path=vault, force=True)
        assert result["files_seen"] == 1  # only real.md

    def test_index_vault_updates_manifest(self, tmp_path, monkeypatch):
        from core.knowledge_core import vault_indexer as vi
        manifest_path = tmp_path / "manifest.json"
        monkeypatch.setattr(vi, "INDEX_MANIFEST", manifest_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "note.md").write_text("# Note\n\nContent.")
        with patch("core.knowledge_core.vault_indexer.get_embedding") as mock_emb:
            mock_emb.return_value = np.zeros(384, dtype=np.float32)
            with patch("core.knowledge_core.vault_indexer.ks.add_chunk", return_value=0):
                vi.index_vault(vault_path=vault, force=True)
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert len(manifest) >= 1

    def test_incremental_skips_unchanged_files(self, tmp_path, monkeypatch):
        from core.knowledge_core import vault_indexer as vi
        manifest_path = tmp_path / "manifest.json"
        monkeypatch.setattr(vi, "INDEX_MANIFEST", manifest_path)
        vault = tmp_path / "vault"
        vault.mkdir()
        note = vault / "note.md"
        note.write_text("# Note\n\nContent.")

        add_calls = {"count": 0}
        with patch("core.knowledge_core.vault_indexer.get_embedding") as mock_emb:
            mock_emb.return_value = np.zeros(384, dtype=np.float32)
            with patch("core.knowledge_core.vault_indexer.ks.add_chunk") as mock_add:
                mock_add.return_value = 0
                # First run — should index
                vi.index_vault(vault_path=vault, force=True)
                first_count = mock_add.call_count
                # Second run without changes — should skip
                vi.index_vault(vault_path=vault, force=False)
                second_count = mock_add.call_count

        assert second_count == first_count  # no new add_chunk calls


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval Engine
# ─────────────────────────────────────────────────────────────────────────────

class TestRetrievalEngine:
    def _make_chunk(self, chunk_id="r1", content="retrieval test content", mtype="technical"):
        from core.knowledge_core.schemas import KnowledgeChunk
        return KnowledgeChunk(
            chunk_id=chunk_id, content=content, source_file="test.md",
            memory_type=mtype, tags=("test",), created_at="2026-01-01T00:00:00Z",
            chunk_index=0,
        )

    def test_search_memory_empty_query_returns_empty(self):
        from core.knowledge_core.retrieval_engine import search_memory
        assert search_memory("") == []
        assert search_memory("   ") == []

    def test_search_memory_returns_search_results(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_store as ks
        import core.knowledge_core.embedding_cache as ec
        from core.knowledge_core.retrieval_engine import search_memory
        from core.knowledge_core.schemas import SearchResult
        monkeypatch.setattr(ks, "STORE_DIR", tmp_path)
        # Add a chunk first
        emb   = np.random.rand(384).astype(np.float32)
        emb  /= np.linalg.norm(emb)
        chunk = self._make_chunk()
        ks.add_chunk("technical", emb, chunk)
        monkeypatch.setattr(ec, "CACHE_DIR", tmp_path / "ecache")
        (tmp_path / "ecache").mkdir()
        with patch("core.knowledge_core.retrieval_engine.get_embedding", return_value=emb):
            results = search_memory("retrieval test", memory_type="technical")
        assert isinstance(results, list)
        if results:
            assert isinstance(results[0], SearchResult)

    def test_search_memory_top_k_respected(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_store as ks
        from core.knowledge_core.retrieval_engine import search_memory
        monkeypatch.setattr(ks, "STORE_DIR", tmp_path)
        for i in range(5):
            emb = np.random.rand(384).astype(np.float32)
            emb /= np.linalg.norm(emb)
            chunk = self._make_chunk(chunk_id=f"top_{i}", content=f"content {i}")
            ks.add_chunk("technical", emb, chunk)
        query_emb = np.random.rand(384).astype(np.float32)
        query_emb /= np.linalg.norm(query_emb)
        with patch("core.knowledge_core.retrieval_engine.get_embedding", return_value=query_emb):
            results = search_memory("query", memory_type="technical", top_k=3)
        assert len(results) <= 3

    def test_format_for_context_empty_returns_empty(self):
        from core.knowledge_core.retrieval_engine import format_for_context
        assert format_for_context([]) == ""

    def test_format_for_context_includes_source_file(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_store as ks
        from core.knowledge_core.retrieval_engine import format_for_context
        from core.knowledge_core.schemas import KnowledgeChunk, SearchResult
        chunk = KnowledgeChunk(
            chunk_id="fmt1", content="Context content here.",
            source_file="docs/architecture.md", memory_type="architecture",
            tags=(), created_at="2026-01-01T00:00:00Z", chunk_index=0,
        )
        result = SearchResult(chunk=chunk, score=0.9, rank=1)
        context = format_for_context([result])
        assert "docs/architecture.md" in context

    def test_format_for_context_respects_token_budget(self, tmp_path, monkeypatch):
        from core.knowledge_core.retrieval_engine import format_for_context
        from core.knowledge_core.schemas import KnowledgeChunk, SearchResult
        # Large content that would exceed small budget
        large_content = "word " * 500
        chunk = KnowledgeChunk(
            chunk_id="large", content=large_content,
            source_file="big.md", memory_type="technical",
            tags=(), created_at="2026-01-01T00:00:00Z", chunk_index=0,
        )
        result = SearchResult(chunk=chunk, score=0.8, rank=1)
        context = format_for_context([result], max_tokens=50)
        assert len(context) <= 50 * 4 * 2  # some slack for headers


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Memory
# ─────────────────────────────────────────────────────────────────────────────

class TestSemanticMemory:
    def test_persist_learning_returns_chunk(self, tmp_path, monkeypatch):
        import core.knowledge_core.semantic_memory as sm
        monkeypatch.setattr(sm, "PERSIST_QUEUE", tmp_path / "queue.jsonl")
        chunk = sm.persist_learning("Test learning", "technical", tags=["test"])
        from core.knowledge_core.schemas import KnowledgeChunk
        assert isinstance(chunk, KnowledgeChunk)

    def test_persist_learning_appends_to_queue(self, tmp_path, monkeypatch):
        import core.knowledge_core.semantic_memory as sm
        queue_path = tmp_path / "queue.jsonl"
        monkeypatch.setattr(sm, "PERSIST_QUEUE", queue_path)
        sm.persist_learning("First learning", "technical")
        sm.persist_learning("Second learning", "architecture")
        lines = queue_path.read_text().splitlines()
        assert len(lines) == 2

    def test_persist_queue_append_only(self, tmp_path, monkeypatch):
        import core.knowledge_core.semantic_memory as sm
        queue_path = tmp_path / "queue.jsonl"
        monkeypatch.setattr(sm, "PERSIST_QUEUE", queue_path)
        for i in range(5):
            sm.persist_learning(f"Learning {i}", "technical")
        lines = queue_path.read_text().splitlines()
        assert len(lines) == 5
        # Verify all are valid JSON
        for line in lines:
            entry = json.loads(line)
            assert "content" in entry
            assert "memory_type" in entry

    def test_persist_architecture_decision(self, tmp_path, monkeypatch):
        import core.knowledge_core.semantic_memory as sm
        queue_path = tmp_path / "queue.jsonl"
        monkeypatch.setattr(sm, "PERSIST_QUEUE", queue_path)
        sm.persist_architecture_decision(
            title="Use dispatch() for all AI calls",
            decision="All modules must use dispatch(task_type, payload)",
            rationale="Single point of control for fallback and logging",
        )
        lines = queue_path.read_text().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["memory_type"] == "architecture"

    def test_persist_provider_event(self, tmp_path, monkeypatch):
        import core.knowledge_core.semantic_memory as sm
        queue_path = tmp_path / "queue.jsonl"
        monkeypatch.setattr(sm, "PERSIST_QUEUE", queue_path)
        sm.persist_provider_event("openrouter", "timeout", "30s timeout on caption_generation")
        lines = queue_path.read_text().splitlines()
        entry = json.loads(lines[0])
        assert entry["memory_type"] == "provider_reliability"

    def test_persist_revenue_insight(self, tmp_path, monkeypatch):
        import core.knowledge_core.semantic_memory as sm
        queue_path = tmp_path / "queue.jsonl"
        monkeypatch.setattr(sm, "PERSIST_QUEUE", queue_path)
        sm.persist_revenue_insight("Owala FreeSip", "High CTR on TikTok carousels", score=0.87)
        lines = queue_path.read_text().splitlines()
        entry = json.loads(lines[0])
        assert entry["memory_type"] == "revenue"

    def test_persist_invalid_memory_type_defaults_to_technical(self, tmp_path, monkeypatch):
        import core.knowledge_core.semantic_memory as sm
        queue_path = tmp_path / "queue.jsonl"
        monkeypatch.setattr(sm, "PERSIST_QUEUE", queue_path)
        chunk = sm.persist_learning("test", memory_type="invalid_type_xyz")
        assert chunk.memory_type == "technical"


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge Graph
# ─────────────────────────────────────────────────────────────────────────────

class TestKnowledgeGraph:
    def test_add_node_creates_entry(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_graph as kg
        monkeypatch.setattr(kg, "GRAPH_PATH", tmp_path / "graph.json")
        kg.add_node("chunk1", "Architecture Overview", ["architecture", "system"])
        graph = json.loads((tmp_path / "graph.json").read_text())
        assert "chunk1" in graph
        assert graph["chunk1"]["title"] == "Architecture Overview"

    def test_add_link_creates_adjacency(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_graph as kg
        monkeypatch.setattr(kg, "GRAPH_PATH", tmp_path / "graph.json")
        kg.add_node("a", "Node A", [])
        kg.add_link("a", "b")
        graph = json.loads((tmp_path / "graph.json").read_text())
        assert "b" in graph["a"]["links_to"]

    def test_add_link_no_duplicates(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_graph as kg
        monkeypatch.setattr(kg, "GRAPH_PATH", tmp_path / "graph.json")
        kg.add_link("a", "b")
        kg.add_link("a", "b")  # duplicate
        graph = json.loads((tmp_path / "graph.json").read_text())
        assert graph["a"]["links_to"].count("b") == 1

    def test_get_related_returns_direct_links(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_graph as kg
        monkeypatch.setattr(kg, "GRAPH_PATH", tmp_path / "graph.json")
        kg.add_link("root", "child1")
        kg.add_link("root", "child2")
        related = kg.get_related("root", depth=1)
        assert "child1" in related
        assert "child2" in related
        assert "root" not in related

    def test_get_related_respects_depth(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_graph as kg
        monkeypatch.setattr(kg, "GRAPH_PATH", tmp_path / "graph.json")
        kg.add_link("root", "level1")
        kg.add_link("level1", "level2")
        related_d1 = kg.get_related("root", depth=1)
        related_d2 = kg.get_related("root", depth=2)
        assert "level1" in related_d1
        assert "level2" not in related_d1
        assert "level2" in related_d2

    def test_get_related_unknown_node_returns_empty(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_graph as kg
        monkeypatch.setattr(kg, "GRAPH_PATH", tmp_path / "graph.json")
        related = kg.get_related("nonexistent_node")
        assert related == []

    def test_parse_obsidian_links_extracts_targets(self):
        from core.knowledge_core.knowledge_graph import parse_obsidian_links
        content = "See [[Architecture Overview]] and [[Pipeline|Main Pipeline]]."
        links = parse_obsidian_links(content)
        assert "Architecture Overview" in links
        assert "Pipeline" in links
        assert "Main Pipeline" not in links

    def test_parse_obsidian_links_ignores_external_urls(self):
        from core.knowledge_core.knowledge_graph import parse_obsidian_links
        content = "See [[https://example.com]] and [[Real Note]]."
        links = parse_obsidian_links(content)
        assert not any("http" in link for link in links)
        assert "Real Note" in links

    def test_parse_obsidian_links_empty_content(self):
        from core.knowledge_core.knowledge_graph import parse_obsidian_links
        assert parse_obsidian_links("") == []
        assert parse_obsidian_links("No links here.") == []

    def test_graph_persists_to_json(self, tmp_path, monkeypatch):
        import core.knowledge_core.knowledge_graph as kg
        graph_path = tmp_path / "graph.json"
        monkeypatch.setattr(kg, "GRAPH_PATH", graph_path)
        kg.add_node("persist_test", "Persist Test", ["test"])
        assert graph_path.exists()
        data = json.loads(graph_path.read_text())
        assert "persist_test" in data
