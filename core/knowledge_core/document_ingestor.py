#!/usr/bin/env python3
"""
document_ingestor.py — Multi-format document ingestion for knowledge_core.

Supported formats:
- .md   → chunk_markdown() — sections + tags
- .json → key paths as chunks (architectural decisions, config)
- .py   → docstrings + module/function-level comments

Returns list of (chunk_text, tags) tuples — never raises.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.knowledge_core.chunker import chunk_markdown, chunk_text

SKIP_DIRS: list[str] = [
    ".obsidian", "__pycache__", ".git", ".claude", "node_modules",
    ".venv", "venv", "env", ".mypy_cache", ".pytest_cache", "dist", "build",
]

DEFAULT_PATTERNS: list[str] = ["*.md", "*.json"]


# ── Format handlers ───────────────────────────────────────────────────────────

def _ingest_markdown(path: Path) -> list[tuple[str, list[str]]]:
    """Read and chunk a Markdown file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return chunk_markdown(text)
    except Exception:
        return []


def _ingest_json(path: Path) -> list[tuple[str, list[str]]]:
    """
    Extract text chunks from a JSON file.
    Strategy: serialize each top-level key's value as a chunk,
    or serialize the whole object if it's a flat dict.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        data = json.loads(text)
    except Exception:
        return []

    chunks: list[tuple[str, list[str]]] = []
    tags   = [path.stem.lower()]

    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, str) and val.strip():
                chunks.extend([(ch, tags + [key]) for ch in chunk_text(val)])
            elif isinstance(val, (dict, list)):
                serialized = json.dumps(val, indent=2, ensure_ascii=False)
                if len(serialized) > 20:
                    chunks.extend([(ch, tags + [key]) for ch in chunk_text(serialized)])
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, str) and item.strip():
                chunks.extend([(ch, tags) for ch in chunk_text(item)])
            elif isinstance(item, dict):
                serialized = json.dumps(item, indent=2, ensure_ascii=False)
                chunks.extend([(ch, tags) for ch in chunk_text(serialized)])

    return chunks


def _ingest_python(path: Path) -> list[tuple[str, list[str]]]:
    """
    Extract docstrings and comments from a Python file.
    Uses AST to find module/function/class docstrings.
    Falls back to raw text if AST parse fails.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    tags   = ["python", path.stem.lower()]
    chunks: list[tuple[str, list[str]]] = []

    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Fallback: chunk raw source
        return [(ch, tags) for ch in chunk_text(text)]

    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docstring = ast.get_docstring(node)
            if docstring and docstring.strip():
                node_tags = list(tags)
                if hasattr(node, "name"):
                    node_tags.append(node.name.lower())
                chunks.extend([(ch, node_tags) for ch in chunk_text(docstring)])

    # Also extract inline comments (lines starting with #)
    comment_lines = [
        line.lstrip("#").strip()
        for line in text.splitlines()
        if line.strip().startswith("#") and len(line.strip()) > 3
    ]
    if comment_lines:
        comment_block = "\n".join(comment_lines)
        chunks.extend([(ch, tags + ["comments"]) for ch in chunk_text(comment_block)])

    return chunks


# ── Public API ────────────────────────────────────────────────────────────────

def ingest_file(path: Path) -> list[tuple[str, list[str]]]:
    """
    Ingest a single file into (chunk_text, tags) pairs.

    Supported: .md, .json, .py
    Unknown extensions: attempt as plain text.
    Returns empty list on error — never raises.
    """
    if not path.is_file():
        return []

    suffix = path.suffix.lower()
    try:
        if suffix == ".md":
            return _ingest_markdown(path)
        elif suffix == ".json":
            return _ingest_json(path)
        elif suffix == ".py":
            return _ingest_python(path)
        else:
            # Plain text fallback
            text = path.read_text(encoding="utf-8", errors="replace")
            tags = [path.suffix.lstrip(".").lower(), path.stem.lower()]
            return [(ch, tags) for ch in chunk_text(text)]
    except Exception:
        return []


def ingest_directory(
    root: Path,
    patterns: list[str] = DEFAULT_PATTERNS,
    skip_dirs: list[str] = SKIP_DIRS,
) -> list[tuple[Path, str, list[str]]]:
    """
    Walk a directory and ingest all matching files.

    Returns list of (source_path, chunk_text, tags).
    Skips binary files, hidden directories, and SKIP_DIRS.
    Never raises.
    """
    results: list[tuple[Path, str, list[str]]] = []

    if not root.is_dir():
        return results

    def _should_skip(p: Path) -> bool:
        for part in p.parts:
            if part in skip_dirs or part.startswith("."):
                return True
        return False

    # Collect matching files
    files: list[Path] = []
    for pattern in patterns:
        try:
            files.extend(root.rglob(pattern))
        except Exception:
            pass

    seen: set[Path] = set()
    for file_path in files:
        try:
            resolved = file_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)

            if _should_skip(file_path):
                continue
            if not file_path.is_file():
                continue

            chunks = ingest_file(file_path)
            for chunk_text_str, tags in chunks:
                results.append((file_path, chunk_text_str, tags))
        except Exception:
            continue

    return results
