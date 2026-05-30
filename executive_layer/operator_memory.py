"""
operator_memory.py — Conversational memory for operator interactions.

Tracks what the operator asked, what was answered, what was decided.
Persisted to JSONL for cross-session continuity.

NOT a replacement for system memory (knowledge_core) — this is purely
for the Telegram conversational context.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
MEMORY_FILE = IMPERIO_ROOT / "logs" / "operator_memory.jsonl"
MAX_CONTEXT_ENTRIES = 50  # rolling window for LLM context


@dataclass
class MemoryEntry:
    timestamp: str
    role: str       # "operator" | "hermes"
    content: str
    category: str   # "question", "answer", "decision", "command", "alert"


class OperatorMemory:
    """
    Rolling conversational memory for operator ↔ HERMES interactions.
    Persists to disk. Provides context window for LLM reasoning.
    """

    def __init__(self):
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    def record(self, role: str, content: str, category: str = "message"):
        """Record an interaction."""
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "role": role,
            "content": content[:1000],  # cap size
            "category": category,
        }
        try:
            with open(MEMORY_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def record_question(self, question: str):
        self.record("operator", question, "question")

    def record_answer(self, answer: str):
        self.record("hermes", answer, "answer")

    def record_decision(self, decision: str):
        self.record("operator", decision, "decision")

    def get_context(self, limit: int = MAX_CONTEXT_ENTRIES) -> list[dict]:
        """Get recent interactions for LLM context window."""
        if not MEMORY_FILE.exists():
            return []

        entries = []
        try:
            with open(MEMORY_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass

        return entries[-limit:]

    def format_for_prompt(self, limit: int = 10) -> str:
        """Format recent context as text for LLM prompt."""
        entries = self.get_context(limit)
        if not entries:
            return "Sin interacciones previas."

        lines = []
        for e in entries:
            role = "Operador" if e["role"] == "operator" else "HERMES"
            lines.append(f"[{e['ts']}] {role}: {e['content']}")
        return "\n".join(lines)

    def get_decisions(self, limit: int = 10) -> list[dict]:
        """Get recent operator decisions only."""
        context = self.get_context(limit=200)
        decisions = [e for e in context if e.get("category") == "decision"]
        return decisions[-limit:]
