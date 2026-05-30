#!/usr/bin/env python3
"""
visual_optimizer.py — Brain of the Visual Intelligence system.

Two entry points:

1. ingest_carousel(post_id, product_id, platform, slide_paths)
   Called AFTER carousel generation. Encodes slides → vector_store.
   No blocking — async-safe, fast enough for pipeline.

2. get_archetype_directive(product_id) → ArchetypeDirective
   Called BEFORE carousel generation. Returns prompt bias from best archetype.
   Returns random directive if insufficient data (< MIN_SAMPLES_FOR_OPTIMIZER).

Operating modes (auto-detected):
    COLLECTION  → ingest only, get_archetype_directive returns random
    LEARNING    → ingest + clustering active
    OPTIMIZING  → ingest + clustering + prompt injection active

Mode transitions are automatic — no manual configuration needed.

ZERO AI calls. ZERO modification of Truth Layer.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.visual_intelligence import MIN_SAMPLES_FOR_CLUSTERING, MIN_SAMPLES_FOR_OPTIMIZER
from core.visual_intelligence.schemas import ArchetypeDirective, ImageEmbedding


# ── Public API ────────────────────────────────────────────────────────────────

def ingest_carousel(
    post_id:     str,
    product_id:  str,
    platform:    str,
    slide_paths: list[Path],
) -> dict:
    """
    Encode and store all carousel slides for a post.

    Called after generate_carousel_flow_sync() completes.
    Non-blocking: fails silently on individual slide errors.

    Returns:
        Summary: {encoded: int, skipped: int, mode: str}
    """
    from core.visual_intelligence import clip_encoder, vector_store

    encoded  = 0
    skipped  = 0

    for path in slide_paths:
        if not path.exists():
            skipped += 1
            continue

        try:
            img_bytes = path.read_bytes()
            emb, model_name = clip_encoder.encode_image(img_bytes)
            img_hash = clip_encoder.image_hash(img_bytes)

            meta = ImageEmbedding(
                post_id=post_id,
                product_id=product_id,
                platform=platform,
                image_path=str(path),
                image_hash=img_hash,
                embedding_model=model_name,
                encoded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )

            vector_store.add_embedding(product_id, emb, meta)
            encoded += 1

        except Exception:
            skipped += 1

    total = vector_store.count(product_id)
    mode  = _get_mode(total)

    return {"encoded": encoded, "skipped": skipped, "total_stored": total, "mode": mode}


def get_archetype_directive(product_id: str, category: str = "") -> ArchetypeDirective:
    """
    Return the best visual archetype directive for prompt injection.

    Mode COLLECTION (< MIN_SAMPLES_FOR_OPTIMIZER):
        Returns ArchetypeDirective.random() — no bias

    Mode LEARNING (>= MIN_SAMPLES_FOR_CLUSTERING, < MIN_SAMPLES_FOR_OPTIMIZER):
        Returns directive with soft_hint populated (style hints, comma-separated)
        Format: "Visual hints: {label} — {top_2_style_labels}"

    Mode OPTIMIZING (>= MIN_SAMPLES_FOR_OPTIMIZER):
        Returns directive with full_archetype_injection populated
        Format: full formatted injection string for Flow prompt

    Args:
        product_id: ASIN
        category:   optional category tag (used for soft hints from style_labels)

    Never raises.
    """
    from core.visual_intelligence import vector_store, archetype_engine

    try:
        total = vector_store.count(product_id)
        mode  = _get_mode(total)

        if mode == "COLLECTION":
            return ArchetypeDirective.random(product_id)

        # Try to get cached best archetype
        best = archetype_engine.get_best_archetype(product_id)

        if best is None and mode in ("LEARNING", "OPTIMIZING"):
            # Trigger computation if not cached
            archetypes = archetype_engine.compute_archetypes(product_id)
            best = archetypes[0] if archetypes else None

        if best is None:
            return ArchetypeDirective.random(product_id)

        bias_strength = _bias_strength(total)
        prompt_text   = archetype_engine.get_prompt_bias(best.label)

        # Build mode-specific hint fields
        soft_hint               = ""
        full_archetype_injection = ""

        if mode == "LEARNING":
            # Extract style labels from archetype (get first 2 words of prompt bias as hints)
            style_words = prompt_text.split(",")[:2] if prompt_text else []
            top2 = ", ".join(w.strip() for w in style_words) if style_words else best.label
            soft_hint = f"Visual hints: {best.label} — {top2}"

        elif mode == "OPTIMIZING":
            # Full injection: formatted multi-line string for Flow prompt
            style_lines = [f"- {s.strip()}" for s in prompt_text.split(",") if s.strip()][:3]
            style_block = "\n".join(style_lines) if style_lines else f"- {prompt_text}"
            full_archetype_injection = (
                f"Use visual style: {best.label}\n"
                f"{style_block}\n"
                "minimal typography\n"
                "high-end commercial aesthetic"
            )

        return ArchetypeDirective(
            product_id=product_id,
            archetype_id=best.archetype_id,
            label=best.label,
            prompt_injection=prompt_text,
            bias_strength=bias_strength,
            source="optimizer",
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            soft_hint=soft_hint,
            full_archetype_injection=full_archetype_injection,
        )

    except Exception:
        return ArchetypeDirective.random(product_id)


def run_batch_update(product_id: str = "") -> dict:
    """
    Offline batch: link performance scores + recompute archetypes.
    Call from cron or manually — never from real-time pipeline.

    Args:
        product_id: empty = all products
    """
    from core.visual_intelligence import performance_linker, archetype_engine, vector_store

    results = {}

    # Step 1: Link performance data
    link_result = performance_linker.link_performance(product_id)
    results["performance_link"] = link_result

    # Step 2: Recompute archetypes for products with enough data
    products = [product_id] if product_id else vector_store.list_products()
    archetypes_computed = 0

    for pid in products:
        total = vector_store.count(pid)
        if total >= MIN_SAMPLES_FOR_CLUSTERING:
            archetype_list = archetype_engine.compute_archetypes(pid)
            if archetype_list:
                archetypes_computed += 1

    results["archetypes_computed"] = archetypes_computed
    results["run_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return results


def get_system_status() -> dict:
    """Current mode + stats across all products."""
    from core.visual_intelligence import vector_store

    products = vector_store.list_products()
    statuses = {}
    for pid in products:
        total = vector_store.count(pid)
        statuses[pid] = {"embeddings": total, "mode": _get_mode(total)}

    return {
        "total_products": len(products),
        "products": statuses,
        "thresholds": {
            "clustering": MIN_SAMPLES_FOR_CLUSTERING,
            "optimizer":  MIN_SAMPLES_FOR_OPTIMIZER,
        },
    }


# ── Internal ──────────────────────────────────────────────────────────────────

def _get_mode(total_embeddings: int) -> str:
    if total_embeddings < MIN_SAMPLES_FOR_CLUSTERING:
        return "COLLECTION"
    if total_embeddings < MIN_SAMPLES_FOR_OPTIMIZER:
        return "LEARNING"
    return "OPTIMIZING"


def _bias_strength(total_embeddings: int) -> float:
    """
    Bias strength scales with data volume.
    At MIN_SAMPLES_FOR_OPTIMIZER → 0.3
    At 200+ → 0.8 (never full 1.0 — always allow some creative randomness)
    """
    if total_embeddings < MIN_SAMPLES_FOR_OPTIMIZER:
        return 0.0
    ratio = min((total_embeddings - MIN_SAMPLES_FOR_OPTIMIZER) / 150.0, 1.0)
    return round(0.3 + ratio * 0.5, 2)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--status",   action="store_true")
    parser.add_argument("--directive", metavar="PRODUCT_ID")
    parser.add_argument("--batch",    metavar="PRODUCT_ID", default=None)
    args = parser.parse_args()

    if args.status:
        print(json.dumps(get_system_status(), indent=2))
    elif args.directive:
        d = get_archetype_directive(args.directive)
        print(json.dumps(d.to_dict(), indent=2))
    elif args.batch is not None:
        result = run_batch_update(args.batch)
        print(json.dumps(result, indent=2))
