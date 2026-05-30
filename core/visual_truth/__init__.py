"""
visual_truth — Visual ground-truth subsystem for IMPERIO.

Pipeline contract:
    Amazon Image
        ↓
    product_color_extractor  → ColorPalette (truth anchor)
        ↓
    Prompt Generation (Flow) — receives constrained palette
        ↓
    Generated Carousel
        ↓
    carousel_validator       → ValidationResult (gating layer)
        ↓
    Approved Output → Posting

Rule: Flow never receives unconstrained visual input without a reference truth vector.

ZERO AI calls. ZERO mutation of source data.
"""
