"""
visual_intelligence — Self-improving visual ad system for IMPERIO.

Pipeline:
    product image
        ↓
    clip_encoder        → 512D embedding vector
        ↓
    vector_store        → FAISS index per product_id + performance metadata
        ↓
    archetype_engine    → KMeans clusters → ArchetypeDirective
        ↓
    performance_linker  → maps post_id → revenue → embedding score
        ↓
    visual_optimizer    → selects best archetype → prompt bias for Flow

Operating modes:
    COLLECTION  — encode + store only (< MIN_SAMPLES_FOR_CLUSTERING)
    LEARNING    — clustering active (>= MIN_SAMPLES_FOR_CLUSTERING)
    OPTIMIZING  — auto-optimizer active (>= MIN_SAMPLES_FOR_OPTIMIZER)

MIN_SAMPLES_FOR_CLUSTERING  = 20   (posts with stored embeddings)
MIN_SAMPLES_FOR_OPTIMIZER   = 50   (posts with non-zero performance scores)

ZERO AI calls in collection/clustering path.
Only visual_optimizer.get_archetype_prompt() injects text into Flow prompts.
"""

MIN_SAMPLES_FOR_CLUSTERING = 20
MIN_SAMPLES_FOR_OPTIMIZER  = 50
