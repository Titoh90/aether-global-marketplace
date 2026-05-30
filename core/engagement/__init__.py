#!/usr/bin/env python3
"""
core/engagement — Engagement Layer for IMPERIO (Phase 1).

Handles social media comments and auto-responses WITHOUT affecting:
  - Visual Intelligence / Truth Layer
  - Revenue Layer
  - Flow pipeline
  - Dispatch Gate

Public API:
    from core.engagement.engagement_executor import process_comment, process_batch
    from core.engagement.comment_listener import listen, batch_listen
    from core.engagement.intent_classifier import classify_intent
    from core.engagement.response_generator import generate_response
    from core.engagement.tone_guard import validate, sanitize
    from core.engagement.memory_logger import log_engagement

Flow:
    COMMENT IN → comment_listener → intent_classifier → response_generator
              → tone_guard → engagement_executor → memory_logger
"""

from core.engagement.schemas import (
    CommentEvent,
    IntentResult,
    ResponseResult,
    EngagementRecord,
    INTENT_TYPES,
)
from core.engagement.engagement_executor import process_comment, process_batch

__all__ = [
    "process_comment",
    "process_batch",
    "CommentEvent",
    "IntentResult",
    "ResponseResult",
    "EngagementRecord",
    "INTENT_TYPES",
    "listen",
    "classify_intent",
    "generate_response",
    "validate",
    "sanitize",
    "log_engagement",
]
