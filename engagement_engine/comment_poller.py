"""
comment_poller.py — Poll Instagram for new comments on recent posts.

Uses instagrapi to read comments. Tracks already-seen comments
to avoid double-processing. Reads post history from posting logs.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

_ROOT = Path(__file__).resolve().parent.parent
_REVENUE = _ROOT / "REVENUE"
_CREDS_DIR = _ROOT.parent / "SYSTEM_FILES" / "SECURE_CREDENTIALS"
_SESSION_FILE = _CREDS_DIR / "instagram_session.json"
_SEEN_FILE = _REVENUE / "engagement_seen_comments.json"
_IG_LOG = _REVENUE / "instagram_posts.jsonl"

# How far back to check posts (days)
POST_LOOKBACK_DAYS = 7
# Max comments to fetch per post
MAX_COMMENTS_PER_POST = 50


def _load_seen() -> dict:
    """Load set of already-processed comment IDs."""
    try:
        if _SEEN_FILE.exists():
            return json.loads(_SEEN_FILE.read_text())
    except Exception:
        pass
    return {"seen_ids": [], "last_poll": ""}


def _save_seen(data: dict) -> None:
    """Persist seen comment IDs."""
    try:
        _SEEN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _get_recent_media_ids() -> list[str]:
    """Get Instagram media IDs from recent posting log."""
    media_ids = []
    try:
        if not _IG_LOG.exists():
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(days=POST_LOOKBACK_DAYS)
        for line in _IG_LOG.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                # Check timestamp
                ts = entry.get("timestamp", "")
                if ts:
                    posted = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if posted < cutoff:
                        continue
                mid = entry.get("media_id") or entry.get("media_pk") or ""
                if mid:
                    media_ids.append(str(mid))
            except Exception:
                continue
    except Exception:
        pass
    return media_ids


def _init_client():
    """Initialize instagrapi client from saved session."""
    from instagrapi import Client
    cl = Client()
    try:
        if _SESSION_FILE.exists():
            session = json.loads(_SESSION_FILE.read_text())
            cl.set_settings(session)
            cl.login_by_sessionid(session.get("authorization_data", {}).get("sessionid", ""))
        else:
            raise FileNotFoundError("No Instagram session file")
    except Exception as e:
        raise RuntimeError(f"Instagram auth failed: {e}")
    return cl


def poll_comments(dry_run: bool = False) -> list[dict]:
    """
    Poll for new comments on recent posts.

    Returns list of unseen comments:
    [{
        "comment_id": str,
        "media_id": str,
        "text": str,
        "username": str,
        "timestamp": str,
        "like_count": int,
    }]
    """
    media_ids = _get_recent_media_ids()
    if not media_ids:
        return []

    seen_data = _load_seen()
    seen_ids = set(seen_data.get("seen_ids", []))

    if dry_run:
        return [{"info": f"Would poll {len(media_ids)} posts, {len(seen_ids)} seen comments"}]

    cl = _init_client()
    new_comments = []

    for media_id in media_ids:
        try:
            comments = cl.media_comments(media_id, amount=MAX_COMMENTS_PER_POST)
            for c in comments:
                cid = str(c.pk)
                if cid in seen_ids:
                    continue

                # Skip our own comments
                if c.user and c.user.username == "alexanderaether":
                    seen_ids.add(cid)
                    continue

                new_comments.append({
                    "comment_id": cid,
                    "media_id": str(media_id),
                    "text": c.text or "",
                    "username": c.user.username if c.user else "",
                    "timestamp": c.created_at_utc.isoformat() if c.created_at_utc else "",
                    "like_count": c.like_count or 0,
                })
                seen_ids.add(cid)

            # Rate limiting — be gentle
            time.sleep(2 + 3 * (hash(media_id) % 3) / 3)  # 2-5s between posts

        except Exception:
            continue

    # Save updated seen IDs (keep last 5000 to prevent unbounded growth)
    seen_list = list(seen_ids)[-5000:]
    seen_data["seen_ids"] = seen_list
    seen_data["last_poll"] = datetime.now(timezone.utc).isoformat()
    _save_seen(seen_data)

    return new_comments


def get_media_context(media_id: str) -> dict:
    """Get product context for a media post (for response generation)."""
    try:
        if not _IG_LOG.exists():
            return {}
        for line in _IG_LOG.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                mid = str(entry.get("media_id") or entry.get("media_pk") or "")
                if mid == str(media_id):
                    return {
                        "product_name": entry.get("product_name", ""),
                        "category": entry.get("category", ""),
                        "asin": entry.get("asin", ""),
                        "caption": entry.get("caption", "")[:200],
                    }
            except Exception:
                continue
    except Exception:
        pass
    return {}
