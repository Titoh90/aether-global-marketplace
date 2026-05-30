"""
memory_adapter.py — Memory layer adapter for HERMES Executive Agent.

Supports two backends:
1. GBrain (via MCP or CLI) — full knowledge graph, synthesis, gap analysis
2. Local knowledge_core — FAISS + JSONL (built-in, no dependencies)

Auto-detects GBrain availability. Falls back to local.

Architecture:
  Telegram → Hermes (reasoning) → memory_adapter → GBrain or knowledge_core → IMPERIO data
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("hermes.memory")

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")


@dataclass
class MemoryEntry:
    slug: str
    content: str
    source: str         # "gbrain" | "local"
    timestamp: str
    tags: list[str]


class MemoryAdapter:
    """
    Unified memory interface for HERMES.
    Tries GBrain first, falls back to local knowledge_core.
    """

    def __init__(self):
        self._gbrain_available = self._check_gbrain()
        if self._gbrain_available:
            log.info("GBrain detected — using as primary memory")
        else:
            log.info("GBrain not available — using local knowledge_core")

    def _check_gbrain(self) -> bool:
        """Check if gbrain CLI is installed and responding."""
        try:
            env = os.environ.copy()
            env["PATH"] = os.path.expanduser("~/.bun/bin") + ":" + env.get("PATH", "")
            result = subprocess.run(
                ["gbrain", "--version"],
                capture_output=True, text=True, timeout=10, env=env,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _gbrain_env(self) -> dict:
        """Get env with bun in PATH for gbrain calls."""
        env = os.environ.copy()
        env["PATH"] = os.path.expanduser("~/.bun/bin") + ":" + env.get("PATH", "")
        return env

    # ── READ Operations ────────────────────────────────────

    def query(self, question: str) -> str:
        """Query memory with natural language question."""
        if self._gbrain_available:
            return self._gbrain_query(question)
        return self._local_query(question)

    def search(self, terms: str, limit: int = 5) -> list[MemoryEntry]:
        """Search memory by keywords."""
        if self._gbrain_available:
            return self._gbrain_search(terms, limit)
        return self._local_search(terms, limit)

    def get_page(self, slug: str) -> str | None:
        """Get specific page by slug."""
        if self._gbrain_available:
            return self._gbrain_get(slug)
        return self._local_get(slug)

    # ── WRITE Operations (reports/notes only) ──────────────

    def store_report(self, slug: str, content: str, tags: list[str] = None):
        """Store executive report or agent note."""
        if self._gbrain_available:
            self._gbrain_put(f"reports/{slug}", content)
        self._local_store(slug, content, tags or [])

    def store_recommendation(self, slug: str, content: str):
        """Store optimization recommendation."""
        if self._gbrain_available:
            self._gbrain_put(f"recommendations/{slug}", content)
        self._local_store(f"rec_{slug}", content, ["recommendation"])

    def store_anomaly(self, slug: str, content: str):
        """Store anomaly report."""
        if self._gbrain_available:
            self._gbrain_put(f"anomalies/{slug}", content)
        self._local_store(f"anomaly_{slug}", content, ["anomaly"])

    # ── GBrain Backend ─────────────────────────────────────

    def _gbrain_query(self, question: str) -> str:
        """Use gbrain query for synthesized answer."""
        try:
            result = subprocess.run(
                ["gbrain", "query", question],
                capture_output=True, text=True, timeout=30, env=self._gbrain_env(),
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return f"GBrain query failed: {result.stderr[:200]}"
        except Exception as e:
            return f"GBrain error: {e}"

    def _gbrain_search(self, terms: str, limit: int) -> list[MemoryEntry]:
        """Use gbrain search for keyword matching."""
        try:
            result = subprocess.run(
                ["gbrain", "search", terms, "--limit", str(limit), "--json"],
                capture_output=True, text=True, timeout=15, env=self._gbrain_env(),
            )
            if result.returncode != 0:
                return []
            data = json.loads(result.stdout)
            entries = []
            for item in data[:limit]:
                entries.append(MemoryEntry(
                    slug=item.get("slug", ""),
                    content=item.get("content", item.get("snippet", ""))[:500],
                    source="gbrain",
                    timestamp=item.get("updated_at", ""),
                    tags=item.get("tags", []),
                ))
            return entries
        except Exception:
            return []

    def _gbrain_get(self, slug: str) -> str | None:
        try:
            result = subprocess.run(
                ["gbrain", "get", slug],
                capture_output=True, text=True, timeout=10, env=self._gbrain_env(),
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def _gbrain_put(self, slug: str, content: str):
        try:
            subprocess.run(
                ["gbrain", "put", slug],
                input=content, capture_output=True, text=True, timeout=15,
            )
        except Exception as e:
            log.error(f"GBrain put failed: {e}")

    # ── Local Backend (knowledge_core) ─────────────────────

    def _local_query(self, question: str) -> str:
        """Search local knowledge core."""
        try:
            from core.knowledge_core.retrieval_engine import search_memory
            results = search_memory(question, top_k=3)
            if results:
                return "\n\n".join([r.get("content", "")[:300] for r in results])
            return "Sin resultados en memoria local."
        except ImportError:
            return self._local_file_search(question)

    def _local_search(self, terms: str, limit: int) -> list[MemoryEntry]:
        """Search local JSONL logs and state files."""
        entries = []
        # Search agent notes
        notes_dir = IMPERIO_ROOT / "logs" / "agent_notes"
        if notes_dir.exists():
            for f in sorted(notes_dir.glob("*.jsonl"), reverse=True)[:5]:
                try:
                    with open(f) as fh:
                        for line in fh:
                            if terms.lower() in line.lower():
                                data = json.loads(line.strip())
                                entries.append(MemoryEntry(
                                    slug=data.get("slug", f.stem),
                                    content=data.get("content", line)[:300],
                                    source="local",
                                    timestamp=data.get("ts", ""),
                                    tags=data.get("tags", []),
                                ))
                                if len(entries) >= limit:
                                    return entries
                except Exception:
                    continue
        return entries

    def _local_get(self, slug: str) -> str | None:
        """Get from local notes."""
        notes_file = IMPERIO_ROOT / "logs" / "agent_notes" / f"{slug}.json"
        if notes_file.exists():
            return notes_file.read_text()
        return None

    def _local_store(self, slug: str, content: str, tags: list[str]):
        """Store to local JSONL."""
        notes_dir = IMPERIO_ROOT / "logs" / "agent_notes"
        notes_dir.mkdir(parents=True, exist_ok=True)

        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "slug": slug,
            "content": content[:2000],
            "tags": tags,
        }
        log_file = notes_dir / f"{time.strftime('%Y-%m-%d')}.jsonl"
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            log.error(f"Local store failed: {e}")

    def _local_file_search(self, question: str) -> str:
        """Fallback: grep through state files."""
        results = []
        state_files = [
            "REVENUE/campaign_memory.json",
            "REVENUE/ssmie_state.json",
            "REVENUE/posting_safety.json",
            "REVENUE/system_memory.json",
        ]
        q_lower = question.lower()
        for sf in state_files:
            fp = IMPERIO_ROOT / sf
            if fp.exists():
                try:
                    content = fp.read_text()
                    if any(word in content.lower() for word in q_lower.split()):
                        results.append(f"[{sf}]: {content[:200]}")
                except Exception:
                    pass
        return "\n\n".join(results) if results else "Sin resultados."
