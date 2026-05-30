#!/usr/bin/env python3
"""
knowledge_core — Local second brain for IMPERIO.

Public API:
    from core.knowledge_core.retrieval_engine import search_memory, format_for_context
    from core.knowledge_core.semantic_memory import persist_learning

100% LOCAL — zero external calls.
"""

from core.knowledge_core.retrieval_engine import search_memory, format_for_context
from core.knowledge_core.semantic_memory import persist_learning

__all__ = ["search_memory", "format_for_context", "persist_learning"]
