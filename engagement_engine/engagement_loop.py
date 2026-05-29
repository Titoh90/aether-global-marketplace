"""
engagement_loop.py — Main orchestrator for the Brand Personality Engagement Engine.

Pipeline: poll comments → classify → generate response → execute reply
Supports shadow mode (log only) and live mode (actually post).

Usage:
    python engagement_loop.py --shadow          # shadow mode (default)
    python engagement_loop.py --live            # live mode (posts replies)
    python engagement_loop.py --stats           # show engagement stats
    python engagement_loop.py --review          # review shadow log
    python engagement_loop.py --dry-run         # check what would be polled
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

from .comment_poller import poll_comments, get_media_context
from .comment_classifier import classify
from .response_generator import generate_response
from .reply_executor import ReplyExecutor
from .response_memory import record_response, get_stats

_ROOT = Path(__file__).resolve().parent.parent
_REVENUE = _ROOT / "REVENUE"
_SHADOW_LOG = _REVENUE / "engagement_shadow_log.jsonl"


def run_engagement_loop(mode: str = "shadow") -> dict:
    """
    Run one engagement cycle.

    mode: "shadow" (log only) or "live" (post replies)

    Returns summary stats for this run.
    """
    results = {
        "mode": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "comments_found": 0,
        "classified": {"purchase_intent": 0, "question": 0, "viral_positive": 0,
                       "compliment": 0, "humor": 0, "neutral": 0, "hate": 0, "spam": 0},
        "responded": 0,
        "skipped": 0,
        "errors": 0,
        "replies": [],
    }

    # 1. Poll for new comments
    new_comments = poll_comments()
    results["comments_found"] = len(new_comments)

    if not new_comments:
        return results

    executor = ReplyExecutor(mode=mode)

    for comment in new_comments:
        cid = comment.get("comment_id", "")
        text = comment.get("text", "")
        username = comment.get("username", "")
        media_id = comment.get("media_id", "")

        # 2. Classify intent
        classification = classify(text)
        intent = classification["intent"]
        results["classified"][intent] = results["classified"].get(intent, 0) + 1

        # Skip non-respondable
        if not classification["should_respond"]:
            continue

        # 3. Get product context for this post
        context = get_media_context(media_id)
        product_name = context.get("product_name", "")
        category = context.get("category", "default")

        # 4. Generate response
        gen = generate_response(
            comment_text=text,
            intent=intent,
            category=category,
            product_name=product_name,
        )

        response_text = gen.get("response", "")
        if not response_text:
            continue

        # 5. Execute reply (shadow or live)
        reply_result = executor.execute_reply(
            comment_id=cid,
            media_id=media_id,
            response_text=response_text,
            comment_text=text,
            username=username,
            intent=intent,
            method=gen.get("method", ""),
        )

        status = reply_result.get("status", "")
        if status in ("posted", "shadow"):
            results["responded"] += 1
        elif status == "skipped":
            results["skipped"] += 1
        elif status == "error":
            results["errors"] += 1

        results["replies"].append({
            "username": username,
            "comment": text[:80],
            "intent": intent,
            "response": response_text[:80],
            "status": status,
        })

        # 6. Record for memory
        record_response(
            intent=intent,
            method=gen.get("method", ""),
            response_text=response_text,
            status=status,
            category=category,
        )

    return results


def review_shadow_log(last_n: int = 20) -> list[dict]:
    """Read last N shadow log entries for human review."""
    entries = []
    try:
        if _SHADOW_LOG.exists():
            lines = _SHADOW_LOG.read_text().strip().split("\n")
            for line in lines[-last_n:]:
                if line.strip():
                    entries.append(json.loads(line))
    except Exception:
        pass
    return entries


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--stats" in args:
        stats = get_stats()
        print(json.dumps(stats, indent=2))
        return

    if "--review" in args:
        entries = review_shadow_log()
        if not entries:
            print("No shadow log entries yet.")
            return
        for e in entries:
            print(f"\n@{e.get('username','?')}: \"{e.get('comment','')[:60]}\"")
            print(f"  Intent: {e.get('intent','')} | Method: {e.get('method','')}")
            print(f"  → {e.get('proposed_reply','')}")
            print(f"  Delay: {e.get('delay_would_be','')}")
        return

    if "--dry-run" in args:
        result = poll_comments(dry_run=True)
        print(json.dumps(result, indent=2))
        return

    mode = "live" if "--live" in args else "shadow"
    print(f"Running engagement loop in {mode.upper()} mode...")

    results = run_engagement_loop(mode=mode)

    print(f"\nComments found: {results['comments_found']}")
    print(f"Responded: {results['responded']}")
    print(f"Skipped (human variance): {results['skipped']}")
    print(f"Errors: {results['errors']}")

    if results["replies"]:
        print("\nReplies:")
        for r in results["replies"]:
            print(f"  @{r['username']}: \"{r['comment']}\"")
            print(f"    → [{r['intent']}] {r['response']} ({r['status']})")


if __name__ == "__main__":
    main()
