#!/usr/bin/env python3
"""
performance_linker.py — Maps post_id → clicks → revenue → embedding performance score.

Joins:
    click_tracker.get_clicks_for_product()
    revenue_ledger.get_revenue_record()
    vector_store.update_performance()

Performance score formula:
    score = revenue / max(impressions, 1)
    where impressions = post_count (proxy until real impression tracking)

Runs as offline batch — never in real-time posting path.
Can be called from cron or manually after each revenue update.

ZERO AI calls. Read-only from revenue_layer. Write-only to vector_store.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))


def link_performance(product_id: str = "") -> dict:
    """
    Update performance scores for all stored embeddings.

    For each stored embedding (image_hash → post_id mapping):
      1. Count clicks attributed to that post's product
      2. Sum revenue attributed to product
      3. Compute performance_score = revenue / max(post_count, 1)
      4. Write back to vector_store

    Args:
        product_id: if set, update only this product. Empty = all products.

    Returns:
        Summary dict with updated counts.
    """
    from core.visual_intelligence import vector_store
    from revenue_layer.revenue_ledger import get_revenue_record

    products = [product_id] if product_id else vector_store.list_products()

    updated   = 0
    no_data   = 0
    processed = 0

    for pid in products:
        _, meta_objects = vector_store.get_all_embeddings(pid)
        if not meta_objects:
            continue

        # Aggregate performance per product (post-level granularity not available yet)
        # When real impression tracking is added, this becomes per-post
        try:
            rev_record  = get_revenue_record(pid)
            total_rev   = rev_record.total_revenue
            total_clicks = rev_record.total_clicks
            post_count   = max(len(meta_objects), 1)

            # Revenue per post (uniform distribution — v1 approximation)
            rev_per_post    = total_rev   / post_count
            clicks_per_post = total_clicks // post_count

            for meta in meta_objects:
                score = rev_per_post  # upgrade to per-post when impression data exists
                success = vector_store.update_performance(
                    product_id=pid,
                    image_hash=meta.image_hash,
                    performance_score=score,
                    clicks=clicks_per_post,
                    revenue=rev_per_post,
                )
                if success:
                    updated += 1
                processed += 1

        except Exception:
            no_data += 1

    return {
        "products_processed": len(products),
        "embeddings_updated": updated,
        "products_no_data":   no_data,
        "processed_at":       datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", default="", help="Product ID (empty=all)")
    args = parser.parse_args()

    result = link_performance(args.product)
    print(json.dumps(result, indent=2))
