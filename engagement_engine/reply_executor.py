"""
reply_executor.py — Post replies to Instagram comments.

Supports two modes:
  SHADOW: generates reply but only logs it (no posting)
  LIVE:   posts reply via instagrapi after human-like delay

Human behavior simulation:
  - Random delay before reply (5-45 min)
  - 65-80% response rate (skip some comments)
  - Vary response length
  - Non-linear timing (not every 5 minutes)
"""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from datetime import datetime, timezone

_ROOT = Path(__file__).resolve().parent.parent
_REVENUE = _ROOT / "REVENUE"
_SHADOW_LOG = _REVENUE / "engagement_shadow_log.jsonl"
_REPLY_LOG = _REVENUE / "engagement_reply_log.jsonl"
_CREDS_DIR = _ROOT.parent / "SYSTEM_FILES" / "SECURE_CREDENTIALS"
_SESSION_FILE = _CREDS_DIR / "instagram_session.json"

# Response rate: skip 20-35% of respondable comments
RESPONSE_RATE_MIN = 0.65
RESPONSE_RATE_MAX = 0.80

# Delay range before replying (seconds)
DELAY_MIN = 300    # 5 min
DELAY_MAX = 2700   # 45 min


def should_respond() -> bool:
    """Probabilistic response gate — skip some comments to seem human."""
    rate = random.uniform(RESPONSE_RATE_MIN, RESPONSE_RATE_MAX)
    return random.random() < rate


def human_delay() -> int:
    """Generate human-like delay in seconds. Gaussian, not uniform."""
    # Mean ~15 min, std ~8 min, clamped to [5, 45] min
    delay = random.gauss(900, 480)
    return max(DELAY_MIN, min(DELAY_MAX, int(delay)))


class ReplyExecutor:
    """Execute comment replies in shadow or live mode."""

    def __init__(self, mode: str = "shadow"):
        """
        mode: "shadow" (log only) or "live" (actually post)
        """
        if mode not in ("shadow", "live"):
            raise ValueError(f"Invalid mode: {mode}. Use 'shadow' or 'live'.")
        self.mode = mode
        self._client = None

    def _get_client(self):
        """Lazy-init instagrapi client."""
        if self._client is None:
            from instagrapi import Client
            cl = Client()
            session = json.loads(_SESSION_FILE.read_text())
            cl.set_settings(session)
            cl.login_by_sessionid(
                session.get("authorization_data", {}).get("sessionid", "")
            )
            self._client = cl
        return self._client

    def execute_reply(
        self,
        comment_id: str,
        media_id: str,
        response_text: str,
        comment_text: str = "",
        username: str = "",
        intent: str = "",
        method: str = "",
        delay: bool = True,
    ) -> dict:
        """
        Execute a reply (shadow or live).

        Returns:
            {
                "status": "posted" | "shadow" | "skipped" | "error",
                "reply_text": str,
                "delay_seconds": int,
                "mode": str,
            }
        """
        # Probabilistic skip
        if not should_respond():
            result = {
                "status": "skipped",
                "reason": "human_variance_skip",
                "reply_text": response_text,
                "delay_seconds": 0,
                "mode": self.mode,
            }
            self._log(comment_id, media_id, comment_text, username, intent, result)
            return result

        # Calculate delay
        delay_secs = human_delay() if delay else 0

        if self.mode == "shadow":
            result = {
                "status": "shadow",
                "reply_text": response_text,
                "delay_seconds": delay_secs,
                "mode": "shadow",
                "would_post_after": f"{delay_secs // 60}m {delay_secs % 60}s",
            }
            self._log_shadow(comment_id, media_id, comment_text, username, intent, method, response_text, delay_secs)
            return result

        # LIVE mode — apply delay then post
        if delay and delay_secs > 0:
            time.sleep(delay_secs)

        try:
            cl = self._get_client()
            # Reply to specific comment
            reply = cl.media_comment(
                media_id,
                response_text,
                replied_to_comment_id=int(comment_id),
            )
            result = {
                "status": "posted",
                "reply_text": response_text,
                "reply_id": str(reply.pk) if reply else "",
                "delay_seconds": delay_secs,
                "mode": "live",
            }
        except Exception as e:
            result = {
                "status": "error",
                "error": str(e)[:200],
                "reply_text": response_text,
                "delay_seconds": delay_secs,
                "mode": "live",
            }

        self._log(comment_id, media_id, comment_text, username, intent, result)
        return result

    def _log_shadow(
        self, comment_id, media_id, comment_text, username, intent, method, response, delay_secs
    ):
        """Log shadow mode entry for human review."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "comment_id": comment_id,
            "media_id": media_id,
            "username": username,
            "comment": comment_text,
            "intent": intent,
            "method": method,
            "proposed_reply": response,
            "delay_would_be": f"{delay_secs // 60}m",
            "mode": "shadow",
        }
        try:
            with open(_SHADOW_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _log(self, comment_id, media_id, comment_text, username, intent, result):
        """Log reply attempt."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "comment_id": comment_id,
            "media_id": media_id,
            "username": username,
            "comment": comment_text,
            "intent": intent,
            **result,
        }
        try:
            with open(_REPLY_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
