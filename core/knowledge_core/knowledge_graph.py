#!/usr/bin/env python3
"""
knowledge_graph.py — Adjacency JSON for Obsidian backlinks + chunk relationships.

Graph format:
    {
        chunk_id: {
            "links_to": [chunk_id, ...],
            "tags": [...],
            "title": str
        }
    }

Persisted at: memory/knowledge_graph.json
Thread-safe via threading.Lock.
"""

from __future__ import annotations

import json
import re
import sys
import threading
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

GRAPH_PATH = _IMPERIO_ROOT / "memory" / "knowledge_graph.json"
GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


# ── Graph I/O ─────────────────────────────────────────────────────────────────

def _load_graph() -> dict:
    if GRAPH_PATH.exists():
        try:
            return json.loads(GRAPH_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_graph(graph: dict) -> None:
    try:
        GRAPH_PATH.write_text(json.dumps(graph, indent=2, ensure_ascii=False))
    except Exception:
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def add_node(chunk_id: str, title: str, tags: list[str]) -> None:
    """Add or update a node in the graph."""
    with _lock:
        graph = _load_graph()
        if chunk_id not in graph:
            graph[chunk_id] = {"links_to": [], "tags": [], "title": ""}
        node = graph[chunk_id]
        node["title"] = title
        # Merge tags without duplicates
        existing = set(node.get("tags", []))
        existing.update(tags)
        node["tags"] = sorted(existing)
        _save_graph(graph)


def add_link(from_id: str, to_id: str) -> None:
    """Add a directed link from_id → to_id."""
    with _lock:
        graph = _load_graph()
        if from_id not in graph:
            graph[from_id] = {"links_to": [], "tags": [], "title": ""}
        links = graph[from_id]["links_to"]
        if to_id not in links:
            links.append(to_id)
        _save_graph(graph)


def get_related(chunk_id: str, depth: int = 1) -> list[str]:
    """
    BFS traversal from chunk_id up to `depth` hops.
    Returns list of related chunk_ids (excluding the start node).
    """
    with _lock:
        graph = _load_graph()

    if chunk_id not in graph:
        return []

    visited: set[str] = {chunk_id}
    frontier: list[str] = [chunk_id]
    related: list[str] = []

    for _ in range(depth):
        next_frontier: list[str] = []
        for node_id in frontier:
            node = graph.get(node_id, {})
            for neighbor in node.get("links_to", []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.append(neighbor)
                    related.append(neighbor)
        frontier = next_frontier
        if not frontier:
            break

    return related


def parse_obsidian_links(content: str) -> list[str]:
    """
    Extract Obsidian wikilinks [[Target]] → list of target strings.
    Handles [[Target|Alias]] → returns Target.
    Ignores external URLs (http/https).
    """
    raw = re.findall(r"\[\[([^\]]+)\]\]", content)
    targets: list[str] = []
    for raw_link in raw:
        # Split on pipe: [[Target|Alias]] → Target
        target = raw_link.split("|")[0].strip()
        # Skip external URLs
        if target.startswith("http://") or target.startswith("https://"):
            continue
        if target:
            targets.append(target)
    return targets
