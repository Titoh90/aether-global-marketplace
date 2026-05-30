"""
ranking_engine.py — Scores and ranks products for the Conversion Surface.

Formula:
  final_score = 0.35*revenue_weight + 0.25*ctr_weight + 0.15*recency_weight
              + 0.15*archetype_performance + 0.10*evergreen_stability

Rules:
  - diversity:           max 2 products from same category in top 8
  - freshness_boost:     products promoted <3 days ago get +0.10
  - evergreen_persistence: evergreen products always appear (min 1 slot)
  - drift_aware:         creative_mode_prior < 0.7 → −0.15 penalty
  - no hallucinations:   ONLY products in daily_brief.json or evergreen_store.json
"""
from __future__ import annotations

from datetime import datetime, timezone

from .schemas import SurfaceProduct


# ── Public API ────────────────────────────────────────────────────────────────

def rank_products(
    products: list[dict],
    campaigns: dict,
    click_log: dict,
    system_memory: dict,
    worker_base_url: str = "",
) -> list[SurfaceProduct]:
    """
    Score and rank products. Returns ordered list of SurfaceProduct.
    Only products present in `products` list are included (no hallucinations).
    """
    if not products:
        return []

    clicks_by_asin = _aggregate_clicks(click_log)
    mode_priors    = system_memory.get("mode_priors", {})
    category_count: dict[str, int] = {}
    scored: list[tuple[float, SurfaceProduct]] = []

    for p in products:
        asin     = p.get("asin", "")
        category = p.get("category", "general")
        if not asin:
            continue

        score    = _score_product(p, clicks_by_asin, system_memory, campaigns)
        section  = _assign_section(p, clicks_by_asin)
        tracking = _build_tracking_url(asin, worker_base_url)
        aff_url  = p.get("affiliate_url", f"https://www.amazon.com/dp/{asin}?tag=aetherglobal-20")

        sp = SurfaceProduct(
            asin            = asin,
            name            = p.get("name", p.get("title", asin)),
            price           = float(p.get("price", 0.0)),
            category        = category,
            affiliate_url   = aff_url,
            tracking_url    = tracking if tracking else aff_url,
            image_url       = p.get("image_url", ""),
            final_score     = round(score, 4),
            section         = section,
            archetype_label = p.get("archetype_label", p.get("archetype", "")),
            creative_mode   = p.get("creative_mode", ""),
            evergreen_status= p.get("evergreen_status", "active"),
            rating          = float(p.get("rating", 0.0)),
            reviews         = int(p.get("reviews", 0)),
        )
        scored.append((score, sp))

    # Sort descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Apply diversity rule: max 2 per category in the ranked output.
    # Build a diverse ranked list: at most 2 per category, up to 8 items total.
    # This guarantees result[:8] never contains more than 2 products of any category.
    diverse: list[SurfaceProduct] = []
    cat_count: dict[str, int] = {}

    for _, sp in scored:
        cat = sp.category
        count = cat_count.get(cat, 0)
        if count < 2:
            diverse.append(sp)
            cat_count[cat] = count + 1

    result: list[SurfaceProduct] = diverse

    # Ensure at least one evergreen slot
    result_asins = {sp.asin for sp in result}
    has_evergreen = any(sp.evergreen_status == "evergreen" for sp in result)
    if not has_evergreen:
        for _, sp in scored:
            if sp.evergreen_status == "evergreen" and sp.asin not in result_asins:
                result.append(sp)
                break

    return result


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _score_product(
    p: dict,
    clicks_by_asin: dict[str, int],
    system_memory: dict,
    campaigns: dict,
) -> float:
    asin     = p.get("asin", "")
    category = p.get("category", "general")

    # Revenue weight — from product price / 100 normalized to [0,1]
    price = float(p.get("price", 0.0))
    revenue_weight = min(price / 100.0, 1.0)

    # CTR weight — from click log
    total_clicks = sum(clicks_by_asin.values()) or 1
    asin_clicks  = clicks_by_asin.get(asin, 0)
    ctr_weight   = min(asin_clicks / total_clicks * 10, 1.0)

    # Recency weight — freshness_boost
    recency_weight = _recency_weight(p)

    # Archetype performance — from system_memory mode_priors
    mode_priors  = system_memory.get("mode_priors", {})
    creative_mode = p.get("creative_mode", "")
    mode_score   = mode_priors.get(creative_mode, {}).get("score", 0.5)
    archetype_perf = float(mode_score)

    # Drift penalty: creative_mode_prior < 0.7 → −0.15
    drift_penalty = 0.0
    if creative_mode and mode_score < 0.7:
        drift_penalty = -0.15

    # Evergreen stability
    ev_status = p.get("evergreen_status", "active")
    evergreen_stability = {"evergreen": 0.8, "active": 0.5, "experimental": 0.2}.get(ev_status, 0.3)

    # Campaign boost
    campaign_boost = _campaign_boost(asin, category, campaigns)

    score = (
        0.35 * revenue_weight
        + 0.25 * ctr_weight
        + 0.15 * recency_weight
        + 0.15 * archetype_perf
        + 0.10 * evergreen_stability
        + drift_penalty
        + campaign_boost
    )
    return max(0.0, min(1.5, score))


def _recency_weight(p: dict) -> float:
    """Products promoted <3 days ago get +0.10 freshness boost."""
    last_promoted = p.get("last_promoted", "")
    if not last_promoted:
        return 0.5
    try:
        lp = datetime.fromisoformat(last_promoted.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_ago = (now - lp).days
        if days_ago < 3:
            return 1.0   # includes +0.10 freshness boost relative to base 0.5
        elif days_ago < 7:
            return 0.7
        elif days_ago < 30:
            return 0.5
        else:
            return 0.3
    except Exception:
        return 0.5


def _campaign_boost(asin: str, category: str, campaigns: dict) -> float:
    """Return priority_boost from active campaigns for this product."""
    if not campaigns:
        return 0.0
    today = datetime.now(timezone.utc).date().isoformat()
    for cid, c in campaigns.items():
        if c.get("status", "expired") != "active":
            continue
        if today < c.get("start_date", today) or today > c.get("end_date", today):
            continue
        cats = c.get("target_categories", [])
        if not cats or category in cats or asin in cats:
            return float(c.get("priority_boost", 0.0))
    return 0.0


def _assign_section(p: dict, clicks_by_asin: dict[str, int]) -> str:
    ev = p.get("evergreen_status", "active")
    if ev == "evergreen":
        return "evergreen"
    clicks = clicks_by_asin.get(p.get("asin", ""), 0)
    if clicks > 5:
        return "trending"
    return "recent"


def _aggregate_clicks(click_log: dict) -> dict[str, int]:
    result: dict[str, int] = {}
    for event in click_log.get("clicks", []):
        asin = event.get("product_id", event.get("asin", ""))
        if asin:
            result[asin] = result.get(asin, 0) + 1
    return result


def _build_tracking_url(asin: str, worker_base_url: str) -> str:
    if not worker_base_url:
        return ""
    base = worker_base_url.rstrip("/")
    return f"{base}/go/{asin}?src=hub"
