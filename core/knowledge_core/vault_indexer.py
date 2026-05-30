#!/usr/bin/env python3
"""
vault_indexer.py — Incremental Obsidian vault + IMPERIO docs indexer.

Strategy:
- Manifest: memory/vault_index_manifest.json — {file_path: {mtime, hash, chunk_count}}
- On each run: skip files where mtime AND hash unchanged
- Only re-index changed/new files
- NEVER blocks pipeline — designed for batch/background runs

Two entry points:
    index_vault()         — ~/Documents/VAULT_IMPERIO_M4/
    index_imperio_docs()  — IMPERIO_ROOT docs and .md files
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.knowledge_core.schemas import KnowledgeChunk, MEMORY_TYPES
from core.knowledge_core.document_ingestor import ingest_file, SKIP_DIRS
from core.knowledge_core.embedding_cache import get_embedding
from core.knowledge_core import knowledge_store as ks

VAULT_PATH      = Path("~/Documents/VAULT_IMPERIO_M4").expanduser()
INDEX_MANIFEST  = _IMPERIO_ROOT / "memory" / "vault_index_manifest.json"

# Auto-detect memory_type from file path / tags
_TYPE_KEYWORDS: dict[str, list[str]] = {
    "architecture":       ["architecture", "arch", "system", "design", "structure"],
    "technical":          ["technical", "code", "python", "api", "debug", "fix"],
    "prompt":             ["prompt", "copy", "caption", "formula", "hook"],
    "revenue":            ["revenue", "affiliate", "commission", "monetization", "income"],
    "visual_archetype":   ["visual", "carousel", "creative", "design", "aesthetic"],
    "failure":            ["failure", "bug", "error", "broken", "fix", "issue"],
    "provider_reliability": ["provider", "openrouter", "groq", "anthropic", "llm"],
    "tooling":            ["tool", "script", "automation", "pipeline", "launchd"],
}


# ── Manifest I/O ──────────────────────────────────────────────────────────────

def _load_manifest() -> dict:
    if INDEX_MANIFEST.exists():
        try:
            return json.loads(INDEX_MANIFEST.read_text())
        except Exception:
            pass
    return {}


def _save_manifest(manifest: dict) -> None:
    try:
        INDEX_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        INDEX_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    except Exception:
        pass


def _file_hash(path: Path) -> str:
    try:
        data = path.read_bytes()
        return hashlib.sha256(data).hexdigest()[:16]
    except Exception:
        return ""


def _needs_reindex(path: Path, manifest: dict, force: bool) -> bool:
    if force:
        return True
    key   = str(path)
    entry = manifest.get(key)
    if entry is None:
        return True
    try:
        mtime = path.stat().st_mtime
        if abs(mtime - entry.get("mtime", 0)) > 1.0:
            return True
        fhash = _file_hash(path)
        return fhash != entry.get("hash", "")
    except Exception:
        return True


# ── Memory type detection ─────────────────────────────────────────────────────

def _detect_memory_type(file_path: Path, tags: list[str]) -> str:
    """Infer memory_type from file path components and tags."""
    path_str = str(file_path).lower()
    combined = path_str + " " + " ".join(tags).lower()

    scores: dict[str, int] = {}
    for mtype, keywords in _TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            scores[mtype] = score

    if scores:
        return max(scores, key=lambda k: scores[k])
    return "technical"


# ── Chunk ID ──────────────────────────────────────────────────────────────────

def _make_chunk_id(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# ── Core indexing ─────────────────────────────────────────────────────────────

def _index_file(
    file_path:   Path,
    source_root: Path,
    manifest:    dict,
    force:       bool,
) -> tuple[int, int]:
    """
    Index a single file.
    Returns (chunks_added, chunks_skipped).
    """
    if not _needs_reindex(file_path, manifest, force):
        return 0, 0

    chunks = ingest_file(file_path)
    if not chunks:
        return 0, 0

    try:
        rel_path = str(file_path.relative_to(source_root))
    except ValueError:
        rel_path = str(file_path)

    now     = datetime.datetime.now(datetime.timezone.utc).isoformat()
    added   = 0
    skipped = 0

    for i, (chunk_text, tags) in enumerate(chunks):
        if not chunk_text or not chunk_text.strip():
            continue

        memory_type = _detect_memory_type(file_path, tags)
        chunk_id    = _make_chunk_id(chunk_text)

        chunk = KnowledgeChunk(
            chunk_id    = chunk_id,
            content     = chunk_text,
            source_file = rel_path,
            memory_type = memory_type,
            tags        = tuple(tags),
            created_at  = now,
            chunk_index = i,
        )

        try:
            embedding = get_embedding(chunk_text)
            row = ks.add_chunk(memory_type, embedding, chunk)
            if row >= 0:
                added += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1

    # Update manifest
    try:
        manifest[str(file_path)] = {
            "mtime":       file_path.stat().st_mtime,
            "hash":        _file_hash(file_path),
            "chunk_count": added,
            "indexed_at":  now,
        }
    except Exception:
        pass

    return added, skipped


# ── Public API ────────────────────────────────────────────────────────────────

def index_vault(
    vault_path: Path = VAULT_PATH,
    force:      bool = False,
) -> dict:
    """
    Index Obsidian vault incrementally.

    Args:
        vault_path: path to Obsidian vault (default ~/Documents/VAULT_IMPERIO_M4)
        force:      re-index all files even if unchanged

    Returns:
        {"indexed": N, "skipped": N, "errors": N, "vault_path": str}
    """
    if not vault_path.exists():
        return {"indexed": 0, "skipped": 0, "errors": 0, "vault_path": str(vault_path), "error": "vault not found"}

    manifest = _load_manifest()
    total_indexed = 0
    total_skipped = 0
    total_errors  = 0

    md_files = [p for p in vault_path.rglob("*.md") if not any(
        part in SKIP_DIRS or part.startswith(".")
        for part in p.parts
    )]

    for file_path in md_files:
        try:
            added, skipped = _index_file(file_path, vault_path, manifest, force)
            total_indexed += added
            total_skipped += skipped
        except Exception:
            total_errors += 1

    _save_manifest(manifest)

    return {
        "indexed":    total_indexed,
        "skipped":    total_skipped,
        "errors":     total_errors,
        "vault_path": str(vault_path),
        "files_seen": len(md_files),
    }


def index_imperio_docs(
    dirs: list[str] | None = None,
    force: bool = False,
) -> dict:
    """
    Index IMPERIO_ROOT documentation files.

    Defaults to: docs/, any .md files in REVENUE/, conversion_surface/
    Returns same summary dict as index_vault().
    """
    if dirs is None:
        dirs = ["docs", "REVENUE", "conversion_surface", "core"]

    manifest      = _load_manifest()
    total_indexed = 0
    total_skipped = 0
    total_errors  = 0
    files_seen    = 0

    for dir_name in dirs:
        target = _IMPERIO_ROOT / dir_name
        if not target.exists():
            continue

        md_files = [p for p in target.rglob("*.md") if not any(
            part in SKIP_DIRS or part.startswith(".")
            for part in p.parts
        )]

        for file_path in md_files:
            files_seen += 1
            try:
                added, skipped = _index_file(file_path, _IMPERIO_ROOT, manifest, force)
                total_indexed += added
                total_skipped += skipped
            except Exception:
                total_errors += 1

    _save_manifest(manifest)

    return {
        "indexed":    total_indexed,
        "skipped":    total_skipped,
        "errors":     total_errors,
        "dirs":       dirs,
        "files_seen": files_seen,
    }
