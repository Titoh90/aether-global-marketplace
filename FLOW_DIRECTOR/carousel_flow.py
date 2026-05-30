#!/usr/bin/env python3
"""
carousel_flow.py — Generate product carousel images via Google Flow (FREE).

Uses FlowOperator.generate_images() with nano-banana-pro prompts library.
Google Flow = Nano Banana / Imagen 4, free with your Google account.

Pipeline:
  prompt_parser → select product prompts → FlowOperator.generate_images()
  → optional PIL text overlay → carousel PNGs

Usage:
  python3 carousel_flow.py \
    --product "gaming headset" \
    --category tech \
    --slides 5 \
    --aspect 1:1 \
    --overlay    # add text/price overlay on top of AI images

  python3 carousel_flow.py \
    --product "wireless earbuds" \
    --price "$49.99" \
    --rating "4.7/5" \
    --features "ANC,30h battery,IPX4" \
    --aspect 1:1 \
    --overlay
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "PIXELLE_VIDEO"))

from flow_operator import FlowOperator, ensure_chrome_ready, CAROUSEL_DIR

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    from prompt_parser import (
        parse_readme,
        select_carousel_prompts,
        build_slide_prompt,
        detect_category,
    )
    PROMPTS_OK = True
except ImportError:
    PROMPTS_OK = False

# ─── Output ─────────────────────────────────────────────────────────────────

FLOW_CAROUSEL_OUT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/carousels")

# ─── Condensed Tech Bento (Flow-safe, ~730 chars) ─────────────────────────────

TECH_BENTO = (
    "An 8-module Bento grid infographic for {product} against a premium dark background. "
    "Clean Apple-style commercial tech photography. "
    "M1: Large hero shot of the product from a dynamic 3/4 angle with cinematic rim lighting. "
    "M2: Macro detail highlighting the premium materials and physical build quality. "
    "M3: 'Chip & Performance' module featuring a stylized glowing microchip processor. "
    "M4: 'Battery Life' module with a modern glowing energy indicator. "
    "M5: 'Connectivity' module displaying sleek wireless waves and seamless pairing graphics. "
    "M6: 'Weight & Form' module emphasizing the ultra-slim, lightweight profile. "
    "M7: Minimalist product styling, floating over a glossy reflective surface. "
    "M8: Cinematic lifestyle scene of the product in active use. "
    "Hyper-detailed, 8k resolution, modern UI aesthetic, without text overlays."
)

# ─── Category-specific fallback prompts (direct, Flow-safe, < 900 chars) ─────

CATEGORY_FALLBACKS = {
    "tech": {
        "hero": (
            "Professional tech product photography of {product} on dark premium studio background. "
            "Dramatic rim lighting, 3/4 view, ultra realistic 8K commercial photography, no text."
        ),
        "features": TECH_BENTO,
        "lifestyle": (
            "Modern lifestyle photography of {product} in use on a sleek minimalist desk setup "
            "with neon accents. Commercial aesthetic, shallow depth of field, no text."
        ),
        "detail": (
            "Macro close-up shot of {product} showing precise engineering, brushed metal textures, "
            "and premium build quality. Cinematic lighting, no text."
        ),
        "cta": (
            "Apple-style glossy ad of {product} floating perfectly over a pure black reflective background. "
            "Single overhead softbox light, no text."
        ),
    },
    "beauty": {
        "hero": (
            "Luxury beauty product photography of {product} on an elegant marble surface. "
            "Soft pastel lighting, water ripples, highly commercial Sephora aesthetic, no text."
        ),
        "features": (
            "Flat lay of {product} surrounded by fresh botanical ingredients, glowing smears of texture, "
            "bright natural light, beauty editorial style, no text."
        ),
        "lifestyle": (
            "Editorial beauty portrait with {product} featured prominently. Soft glowing skin, "
            "natural lighting, high fashion commercial, out of focus aesthetic background, no text."
        ),
        "detail": (
            "Macro shot of {product} texture, glossy and luminous. Perfect lighting, "
            "high-end cosmetic ad style, 8k, ultra sharp, no text."
        ),
        "cta": (
            "Minimalist luxury presentation of {product} on a silk pedestal. "
            "Soft glowing aura, premium cosmetic photography, no text."
        ),
    },
    "fashion": {
        "hero": (
            "High-end fashion product photography of {product}. Clean studio backdrop, "
            "dramatic lighting, editorial Vogue style, 8K commercial quality, no text."
        ),
        "features": (
            "Fashion flat lay of {product} with curated accessories. Styled composition, "
            "bright natural light, editorial catalog aesthetic, no text."
        ),
        "lifestyle": (
            "Lifestyle fashion shot of {product} in a modern urban setting. "
            "Natural golden hour light, aspirational aesthetic, no text."
        ),
        "detail": (
            "Macro close-up of {product} showing fabric texture and stitching detail. "
            "Luxury craftsmanship focus, cinematic lighting, no text."
        ),
        "cta": (
            "Minimalist fashion ad of {product} on a clean monochromatic background. "
            "Soft directional light, premium editorial style, no text."
        ),
    },
    "food": {
        "hero": (
            "Appetizing professional food photography of {product}. Steaming hot, perfectly lit, "
            "dark rustic wooden background with scattered raw ingredients, no text."
        ),
        "features": (
            "Deconstructed layout showing the fresh ingredients of {product} flying perfectly in mid-air. "
            "Vibrant colors, high speed commercial photography, no text."
        ),
        "lifestyle": (
            "Cozy lifestyle shot of a person enjoying {product} in a warm rustic cafe setting. "
            "Bokeh background, golden hour lighting, no text."
        ),
        "detail": (
            "Macro mouth-watering close-up of {product}, glossy and perfectly lit to show texture. "
            "Extremely sharp focus, no text."
        ),
        "cta": (
            "{product} presented perfectly on a pristine white ceramic plate against a dark moody background. "
            "Spotlight illumination, no text."
        ),
    },
    "home": {
        "hero": (
            "Premium interior product photography of {product} in a beautifully styled living space. "
            "Warm natural light, cozy aspirational aesthetic, no text."
        ),
        "features": (
            "Styled flat lay of {product} with complementary decor items on a light wood surface. "
            "Bright natural light, Scandinavian interior aesthetic, no text."
        ),
        "lifestyle": (
            "Lifestyle shot of {product} in a beautifully designed modern home interior. "
            "Soft diffused daylight, cozy atmosphere, no text."
        ),
        "detail": (
            "Macro close-up of {product} showing material texture and craftsmanship detail. "
            "Warm side lighting, premium product photography, no text."
        ),
        "cta": (
            "Minimalist ad of {product} floating over a clean light background. "
            "Soft shadows, premium interior design catalog style, no text."
        ),
    },
    "sports": {
        "hero": (
            "Dynamic action product photography of {product}. Dramatic lighting, motion blur background, "
            "high-energy commercial sports ad style, no text."
        ),
        "features": (
            "Technical detail shot of {product} showing performance materials and construction. "
            "Dramatic studio lighting, sharp focus, no text."
        ),
        "lifestyle": (
            "Athlete in action using {product} in a modern gym or outdoor training environment. "
            "Dynamic composition, natural lighting, no text."
        ),
        "detail": (
            "Macro close-up of {product} highlighting technical fabric texture and engineering. "
            "Cinematic contrast lighting, no text."
        ),
        "cta": (
            "Bold minimalist ad of {product} on a dark gradient background with dramatic rim light. "
            "High-contrast sports brand aesthetic, no text."
        ),
    },
    "tools": {
        "hero": (
            "Professional product photography of {product} on a dark industrial metal surface. "
            "Dramatic side lighting, ultra-sharp detail, commercial hardware catalog quality, no text."
        ),
        "features": (
            "Technical flat lay of {product} showing all components and accessories. "
            "Clean overhead shot, grey industrial background, no text."
        ),
        "lifestyle": (
            "Skilled worker using {product} on a professional job site. "
            "Cinematic natural lighting, action shot, no text."
        ),
        "detail": (
            "Macro close-up of {product} showing precision engineering, steel texture, and build quality. "
            "Industrial cinematic lighting, no text."
        ),
        "cta": (
            "Minimalist hardware ad: {product} displayed on a clean dark surface with a single dramatic spotlight. "
            "Premium tool catalog aesthetic, no text."
        ),
    },
    "kids": {
        "hero": (
            "Bright colorful product photography of {product} on a clean pastel background. "
            "Fun commercial toy catalog style, perfect studio lighting, no text."
        ),
        "features": (
            "Styled flat lay of {product} with colorful accessories on a white surface. "
            "Bright cheerful lighting, playful composition, no text."
        ),
        "lifestyle": (
            "Happy child playing with {product} in a bright sunny modern playroom. "
            "Natural light, joyful commercial photography, no text."
        ),
        "detail": (
            "Close-up of {product} showing safe materials, vibrant colors and quality construction. "
            "Bright studio lighting, no text."
        ),
        "cta": (
            "Playful product presentation of {product} on a bright colorful background. "
            "Commercial toy catalog style, fun energetic, no text."
        ),
    },
    "pet": {
        "hero": (
            "Premium product photography of {product} on a clean light background. "
            "Warm soft lighting, pet lifestyle commercial style, no text."
        ),
        "features": (
            "Detailed flat lay of {product} showing materials and features. "
            "Natural light, clean neutral background, no text."
        ),
        "lifestyle": (
            "Happy dog or cat with {product} in a cozy stylish home setting. "
            "Warm natural light, lifestyle pet photography, no text."
        ),
        "detail": (
            "Close-up macro of {product} showing premium materials and craftsmanship. "
            "Soft studio lighting, no text."
        ),
        "cta": (
            "Clean minimalist ad of {product} on a warm neutral background with a soft rim light. "
            "Premium pet brand aesthetic, no text."
        ),
    },
}

# Default fallbacks for any unmatched category
DEFAULT_FALLBACKS = {
    "hero": (
        "Premium dynamic product photography of {product} in a clean studio setting. "
        "Commercial lighting, high-end advertising style, no text."
    ),
    "features": (
        "Stylized flat lay of {product} showing all components meticulously arranged. "
        "Bright clean commercial lighting, no text."
    ),
    "lifestyle": (
        "Aspirational lifestyle shot of {product} in an elegant environment. "
        "Depth of field, natural sunlight, no text."
    ),
    "detail": (
        "Macro shot detailing the texture and material quality of {product}. "
        "High commercial fidelity, warm grading, no text."
    ),
    "cta": (
        "Striking minimalist presentation of {product} on a vibrant contrasting solid color backdrop. "
        "Sharp rim lighting, no text."
    ),
}


def _lifestyle_environment(category: str, season: str) -> str:
    """Return category + season appropriate environment description."""
    environments = {
        ("beauty", "winter"): "a luxury marble bathroom counter at dawn, warm candlelight beside frosted windows, fresh white roses in a crystal vase",
        ("beauty", "spring"): "an airy minimalist vanity table by open windows, soft morning light filtering through sheer curtains, fresh botanicals",
        ("beauty", "summer"): "a sun-drenched luxury terrace vanity, golden hour light, Mediterranean tiles and fresh flowers",
        ("beauty", "autumn"): "a warm cozy dressing room, amber candlelight, dark wood surfaces, a single cashmere throw nearby",
        ("beauty-personal-care", "winter"): "a luxury marble bathroom counter at dawn, warm candlelight beside frosted windows, fresh white roses in a crystal vase",
        ("beauty-personal-care", "spring"): "an airy minimalist vanity table by open windows, soft morning light, fresh botanicals",
        ("beauty-personal-care", "summer"): "a sun-drenched luxury terrace vanity, golden hour light, fresh flowers",
        ("beauty-personal-care", "autumn"): "a warm cozy dressing room, amber candlelight, dark wood surfaces",
        ("tech", "winter"): "a premium dark wood desk at night, warm task lamp creating dramatic shadows, soft bokeh city lights outside window",
        ("tech", "spring"): "a modern minimalist workspace, clean lines, natural light on concrete and glass surfaces",
        ("tech", "summer"): "an open-plan premium office with floor-to-ceiling windows, bright sharp daylight, clean modern aesthetic",
        ("tech", "autumn"): "a moody home studio setup, warm Edison lighting, premium materials, dark productive atmosphere",
        ("electronics", "winter"): "a premium dark wood desk at night, warm task lamp, soft bokeh city lights outside window",
        ("electronics", "summer"): "an open-plan premium office with floor-to-ceiling windows, bright daylight",
        ("kitchen", "winter"): "a warm rustic kitchen counter, soft morning light, steaming coffee nearby, natural wood and stone surfaces",
        ("kitchen", "spring"): "a bright airy modern kitchen, natural daylight, fresh herbs on the counter",
        ("home-kitchen", "winter"): "a warm rustic kitchen counter, soft morning light, steaming coffee, natural wood and stone",
        ("home-kitchen", "summer"): "a bright airy modern kitchen, natural summer daylight, fresh produce nearby",
        ("sports", "summer"): "a premium gym with dramatic window light creating strong diagonal shadow patterns on concrete floors",
        ("sports", "winter"): "a sleek modern home gym at night, dramatic spot lighting, motivational dark atmosphere",
        ("sports-and-fitness", "summer"): "a premium gym with dramatic window light, strong diagonal shadows on concrete floors",
        ("sports-and-fitness", "winter"): "a sleek modern home gym at night, dramatic spot lighting, dark motivational atmosphere",
    }
    key = (category, season)
    fallback = f"a beautifully styled premium interior with intentional cinematic lighting, luxury materials, and careful editorial composition that evokes {season}"
    return environments.get(key, fallback)


def _build_prompt(
    slide_index: int,
    product: str,
    category: str,
    library_slides: list | None = None,
    price: str = "",
    rating: str = "",
    affiliate: str = "",
    creative_modes: list[str] | None = None,
    season: str | None = None,
    product_colors: dict | None = None,
    anchor_description: str = "",
) -> str:
    """
    AI Creative Marketing OS — full cinematic prompt engine.

    Applies: Mode selection + Seasonal engine + Color psychology +
    Scroll-stopping composition + Cinematic shot library + Brand emulation.

    No people, no skin close-ups → avoids Flow safety filters.
    No img2img reference → Flow interprets prompts freely and creatively.
    anchor_description: for slide 0, injected as PRODUCT ANCHOR to steer generation
    toward the correct product type/form without using img2img (which triggers MP4 mode).
    """
    from datetime import date as _date

    short_name = " ".join(product.split()[:4])

    # ── Seasonal context ──────────────────────────────────────────────────────
    if not season:
        month = _date.today().month
        if month in (12, 1, 2):   season = "winter"
        elif month in (3, 4, 5):  season = "spring"
        elif month in (6, 7, 8):  season = "summer"
        else:                     season = "autumn"

    seasonal_mood = {
        "winter": "warm amber candlelight atmosphere, cozy luxury indoor mood, soft golden volumetric glow",
        "spring": "fresh clean natural daylight, airy whites, soft botanical freshness",
        "summer": "bright vibrant energy, warm golden hour light, luminous highlights",
        "autumn": "rich warm earthy cinematic tones, deep amber shadows, nostalgic color grade",
    }.get(season, "dramatic premium cinematic lighting")

    # ── Color palette by category ─────────────────────────────────────────────
    cat = category.lower().replace(" & ", "-").replace(" ", "-")

    palettes = {
        "beauty":                   ("deep midnight blue and rose gold", "champagne and ivory", "blush pink and platinum"),
        "beauty-personal-care":     ("deep midnight blue and rose gold", "champagne and ivory", "blush pink and platinum"),
        "tech":                     ("pure black and electric blue", "space gray and neon cyan", "gunmetal and white"),
        "electronics":              ("pure black and electric blue", "space gray and neon cyan", "gunmetal and white"),
        "kitchen":                  ("warm cream and brushed copper", "rustic oak and white", "slate gray and warm amber"),
        "home-kitchen":             ("warm cream and brushed copper", "rustic oak and white", "slate gray and warm amber"),
        "home-garden":              ("sage green and natural linen", "terracotta and warm white", "nordic oak and ivory"),
        "sports":                   ("electric orange and deep black", "neon green and charcoal", "bold red and white"),
        "sports-and-fitness":       ("electric orange and deep black", "neon green and charcoal", "bold red and white"),
        "fashion":                  ("editorial black and ivory", "warm caramel and cream", "bold monochrome"),
        "pet":                      ("warm amber and cream", "earthy brown and sage", "natural linen and gold"),
        "kids":                     ("vibrant primary colors", "sunshine yellow and white", "bold candy tones"),
        "tools":                    ("industrial steel and electric orange", "matte black and chrome", "deep gunmetal"),
    }
    pal = palettes.get(cat, ("deep navy and champagne gold", "platinum and midnight", "rich black and electric"))

    # ── COLOR ACCURACY RULE (NON-NEGOTIABLE) ──────────────────────────────────
    # Use ONLY verified colors from Amazon listing. Never invent variants.
    color_instruction = ""
    if product_colors and product_colors.get("primary_color"):
        primary_c  = product_colors["primary_color"]
        available  = product_colors.get("available") or product_colors.get("colors_available", [])
        color_src  = product_colors.get("source", product_colors.get("color_source", "unknown"))
        color_instruction = (
            f"CRITICAL COLOR RULE — Product color truth (source: {color_src}): "
            f"The product MUST appear in its EXACT real color: '{primary_c}'. "
            f"Available verified variants: {available if available else [primary_c]}. "
            f"DO NOT invent, enhance, or stylize the product color beyond reality. "
            f"Lighting and environment vary freely — product color identity is LOCKED. "
        )
    else:
        color_instruction = (
            f"CRITICAL COLOR RULE: Render the product in its EXACT real color as shown on Amazon. "
            f"Do NOT invent color variants. Match real product appearance precisely. "
        )

    # ── Hero anchor — text-only product identity lock (no img2img to avoid MP4 mode) ──
    # Injected only for slide 0 so Flow renders the CORRECT product type/form.
    hero_anchor = ""
    if slide_index == 0 and anchor_description:
        hero_anchor = (
            f"PRODUCT ANCHOR — RENDER EXACTLY THIS PRODUCT: {anchor_description}. "
            f"This is the specific physical object that must appear in the image. "
            f"DO NOT substitute any other product type, shape, or category. "
            f"Match the exact form factor, material, and packaging described above. "
        )

    # ── 5 story beats — cinematic, category-intelligent, season-aware ─────────
    stories = [

        # SLIDE 0 — HOOK: Cinematic hero shot
        # Mode: CINEMATIC_HERO + LUXURY_PREMIUM
        # Shot: dramatic overhead hero with volumetric rim lighting + anamorphic flare
        (
            hero_anchor +
            f"Ultra-premium luxury commercial product photography, production quality of a $200,000 ad campaign. "
            f"The {short_name} — maintaining its exact real shape, colors, branding, and material textures — "
            f"floats perfectly centered in pure negative space against a deep {pal[0]} gradient background. "
            f"A single dramatic overhead Profoto studio light creates a perfect circular halo of light on the product surface. "
            f"Dual rim lighting from left and right adds cinematic depth and dimension. "
            f"Subtle anamorphic lens flare sends elegant horizontal light streaks across the mid-frame. "
            f"The product casts a perfect long dramatic shadow on a glossy reflective surface beneath it. "
            f"Seasonal mood: {seasonal_mood}. "
            f"Ultra-sharp 8K detail. Every texture and material perfectly rendered. "
            f"Inspired by Apple product launch cinematography meets Rolex Oyster Perpetual advertising. "
            f"Final mood: expensive, iconic, legendary — the product feels like the most important object in the world."
        ),

        # SLIDE 1 — PROOF: Social proof editorial with trust badges
        # Mode: AMAZON_BESTSELLER + LUXURY_PREMIUM
        # Shot: editorial magazine layout with floating graphic elements
        (
            f"Full-page premium advertising editorial spread, shot on Hasselblad X2D 100C, 90mm f/3.2. "
            f"The {short_name} sits on a {pal[1]} metallic surface surrounded by fresh organic elements — "
            f"botanical sprigs, crystalline water droplets frozen in mid-air, premium material swatches. "
            f"Floating above the product: a bold gold star rating badge, "
            f"a premium red ribbon banner reading '#1 Best Seller', "
            f"and an elegant white pill-shaped badge showing '24,000+ Verified Reviews'. "
            f"Integrated editorial typography at top: a headline in elegant premium serif font. "
            f"Soft studio bokeh background in {pal[2]} tones with layered depth. "
            f"Seasonal atmosphere: {seasonal_mood}. "
            f"Inspired by Sephora editorial meets Tatcha luxury campaign meets Goop editorial photography. "
            f"This image builds instant desire and trust — the viewer immediately understands this is the #1 choice."
        ),

        # SLIDE 2 — PRODUCT STORY: Deconstructed components / ingredients
        # Mode: CINEMATIC_STORY + VIRAL_TIKTOK
        # Shot: high-speed freeze-frame explosion in radial symmetry
        (
            f"High-speed commercial freeze-frame still, 1/8000s strobe sync, shot on ARRI Alexa 35. "
            f"The {short_name} sits centered as the hero, surrounded by its key ingredients or components "
            f"bursting outward in perfect radial symmetry against a pure premium white background. "
            f"Each element frozen at peak visual drama: "
            f"liquid components as translucent jewel-like spheres catching studio light, "
            f"powder elements as glowing crystalline micro-clouds, "
            f"botanical or mechanical components as perfect floating detailed fragments. "
            f"Ultra-fine hairline annotation lines extend from each element to clean minimal sans-serif labels. "
            f"The product itself is the undisputed center — exact real product shape, colors, and branding perfectly preserved. "
            f"Multiple directional strobe lights create zero-shadow product detail and maximum material clarity. "
            f"Inspired by Dyson product advertising meets Aesop ingredient storytelling meets Kinfolk magazine. "
            f"Mood: science meets luxury — serious ingredients, premium results."
        ),

        # SLIDE 3 — LIFESTYLE ATMOSPHERE: Premium environment storytelling
        # Mode: EMOTIONAL_LIFESTYLE + CINEMATIC_STORY
        # Shot: cinematic still life, 85mm f/1.4, shallow DOF environmental storytelling
        (
            f"Cinematic premium lifestyle still life photography, shot on Sony Venice 2, 85mm Zeiss Batis f/1.4. "
            f"The {short_name} — photographed with exact real product accuracy, every detail preserved — "
            f"sits as the undisputed hero object in a beautifully art-directed high-end environment. "
            f"Setting: {_lifestyle_environment(cat, season)}. "
            f"Seasonal atmosphere woven naturally into the scene: {seasonal_mood}. "
            f"A single ray of perfect natural light illuminates the product surface, revealing every material detail. "
            f"Background elements deliberately blurred at f/1.4 — complementary luxury objects reinforcing aspirational status. "
            f"Cinematic color grade in {pal[0]} tones: rich shadows, luminous highlights, perfect tonal balance. "
            f"Inspired by: Aesop store aesthetic meets Kinfolk magazine meets Ace Hotel photography. "
            f"Mood: This product belongs in the most beautiful spaces. The viewer immediately wants this life."
        ),

        # SLIDE 4 — CTA: Conversion-optimized scroll-stopper
        # Mode: VIRAL_TIKTOK + AMAZON_BESTSELLER + HOOK ENGINE
        # Shot: bold poster with hero spotlight and conversion typography
        (
            f"High-impact premium advertising poster, engineered for maximum conversion. "
            f"Rich {pal[0]} gradient background with subtle authentic texture — never flat, never generic. "
            f"The {short_name} — exact real product, real branding, real materials — "
            f"sits dramatically center-frame under a single powerful overhead Profoto spotlight. "
            f"Perfect long product shadow extends downward on a reflective surface, adding cinematic depth. "
            f"Large bold white uppercase sans-serif typography above the product: 'GET YOURS NOW'. "
            f"Below the product: a glowing {pal[1]} price tag badge with '{price}' in large clean numerals. "
            f"Elegant supporting text: 'Amazon Best Seller  |  Link in Bio  |  @alexanderaether'. "
            f"Gold star row and rating number positioned directly under price for immediate trust. "
            f"The entire composition creates a single clear visual hierarchy: product → price → desire → action. "
            f"Inspired by Nike product drop visual language meets Apple Store meets luxury ecommerce. "
            f"This image makes people stop scrolling, feel desire, and act immediately."
        ),
    ]

    idx = slide_index % len(stories)
    return stories[idx] + " " + color_instruction


# ─── Autonomous QC ───────────────────────────────────────────────────────────

def _qc_evaluate(img_path: Path, slot: str, product: str) -> dict:
    """
    Evaluate slide quality using Claude vision API.
    Returns:
      {"score": 1-10, "product_clarity": 1-10, "verdict": str, "reason": str, "passed": bool}

    Criteria (each 1-10):
    - Cinematic quality (not flat, not generic AI)
    - Emotional scroll-stopping power
    - product_clarity: product CLEARLY visible & accurate (MANDATORY ≥8 to pass)
    - Composition and lighting quality
    - Premium brand perception (not amateur)

    PASS conditions: overall score >= 7 AND product_clarity >= 8.
    Falls back to size-based heuristic if API unavailable.
    """
    import base64, json as _json, os, urllib.request as _ul

    # Fast size heuristic: <150KB = thumbnail/failed render = instant fail
    size_kb = img_path.stat().st_size // 1024
    if size_kb < 150:
        return {
            "score": 3, "product_clarity": 3,
            "verdict": "REJECT",
            "reason": f"Too small ({size_kb}KB) — likely thumbnail or failed render",
            "passed": False,
        }

    # Try Claude vision API
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        score = 8 if size_kb >= 400 else 6
        clarity = 8 if size_kb >= 400 else 6
        passed = score >= 7 and clarity >= 8
        return {
            "score": score, "product_clarity": clarity,
            "verdict": "PASS" if passed else "MARGINAL",
            "reason": f"Heuristic: {size_kb}KB",
            "passed": passed,
        }

    try:
        img_b64 = base64.standard_b64encode(img_path.read_bytes()).decode()
        ext = img_path.suffix.lower().lstrip(".")
        media_type = f"image/{'jpeg' if ext == 'jpg' else ext}"

        qc_prompt = f"""You are an elite advertising creative director reviewing AI-generated product images for a premium brand campaign.

Evaluate this image as if approving it for a real paid ad.

Product: {product}
Slide role: {slot}

Score 1-10 on each criterion:
1. cinematic_quality — not flat, not generic AI, looks shot with expensive camera
2. emotional_impact — scroll-stopping, emotionally engaging, not boring
3. product_clarity — the actual product is CLEARLY VISIBLE, accurately represented, not distorted or missing (this is CRITICAL)
4. composition_lighting — strong focal hierarchy, professional lighting, no dead zones
5. premium_perception — looks expensive, not amateur, premium brand feel

CRITICAL RULE: product_clarity MUST be >= 8 for any slide to pass. If the product is hidden, blurry, distorted, or barely visible, score it <=5 regardless of other criteria.

Respond with ONLY valid JSON (no markdown, no explanation):
{{"cinematic_quality": <1-10>, "emotional_impact": <1-10>, "product_clarity": <1-10>, "composition_lighting": <1-10>, "premium_perception": <1-10>, "verdict": "PASS or REJECT", "reason": "<one sentence>"}}"""

        body = _json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 150,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                    {"type": "text", "text": qc_prompt},
                ]
            }]
        }).encode()

        req = _ul.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with _ul.urlopen(req, timeout=20) as r:
            resp = _json.loads(r.read())

        text = resp["content"][0]["text"].strip()
        import re as _re
        m = _re.search(r'\{[^}]+\}', text, _re.DOTALL)
        if m:
            data = _json.loads(m.group())
            clarity   = max(1, min(10, int(data.get("product_clarity", 5))))
            cinematic = max(1, min(10, int(data.get("cinematic_quality", 5))))
            emotional = max(1, min(10, int(data.get("emotional_impact", 5))))
            comp      = max(1, min(10, int(data.get("composition_lighting", 5))))
            premium   = max(1, min(10, int(data.get("premium_perception", 5))))
            score     = int((cinematic + emotional + clarity + comp + premium) / 5)
            reason    = data.get("reason", "")
            # Dual gate: overall ≥7 AND product_clarity ≥8
            passed    = score >= 7 and clarity >= 8
            verdict   = "PASS" if passed else ("REJECT_CLARITY" if clarity < 8 else "REJECT")
            return {
                "score": score, "product_clarity": clarity,
                "verdict": verdict, "reason": reason, "passed": passed,
            }

    except Exception as e:
        score   = 8 if size_kb >= 400 else (6 if size_kb >= 200 else 4)
        clarity = 8 if size_kb >= 400 else 6
        passed  = score >= 7 and clarity >= 8
        return {
            "score": score, "product_clarity": clarity,
            "verdict": "PASS" if passed else "MARGINAL",
            "reason": f"API unavailable ({e}), heuristic: {size_kb}KB",
            "passed": passed,
        }

    return {
        "score": 5, "product_clarity": 5,
        "verdict": "MARGINAL", "reason": "Could not parse QC response",
        "passed": False,
    }


# ─── Product Truth Validator Engine (PTVE) ───────────────────────────────────

def _ptve_validate(
    img_path: Path,
    slide_index: int,
    product: str,
    product_colors: dict | None = None,
    reference_image_path: Path | None = None,
) -> dict:
    """
    Product Truth Validator Engine.

    Validates factual fidelity between generated image and Amazon product data.
    Does NOT evaluate aesthetics — ONLY enforces product truth.

    Returns:
        {
          "status":  "PASS" | "FAIL" | "WARNING",
          "issues":  [{type, severity, slide, expected, detected}],
          "action":  "publish" | "regenerate" | "review",
          "passed":  bool
        }

    Falls back to size heuristic if API unavailable (always PASS in that case —
    PTVE requires vision to be meaningful).
    """
    import base64, json as _json, os, urllib.request as _ul

    size_kb = img_path.stat().st_size // 1024
    slide_n = slide_index + 1

    # Cheap fail: too small = failed render, skip PTVE
    if size_kb < 150:
        return {
            "status": "FAIL", "action": "regenerate", "passed": False,
            "issues": [{"type": "render_failure", "severity": "high",
                        "slide": slide_n, "expected": ">150KB", "detected": f"{size_kb}KB"}]
        }

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        # No API — cannot validate truth, pass with warning
        return {
            "status": "WARNING", "action": "publish", "passed": True,
            "issues": [{"type": "no_api_key", "severity": "low",
                        "slide": slide_n, "expected": "PTVE vision check",
                        "detected": "API unavailable — skipped"}]
        }

    # Build color context
    primary_color = ""
    colors_available = []
    if product_colors:
        primary_color    = product_colors.get("primary_color", product_colors.get("primary", ""))
        colors_available = product_colors.get("colors_available", product_colors.get("available", []))

    color_context = (
        f"Verified product color from Amazon listing: '{primary_color}'. "
        f"All available variants: {colors_available}. "
        if primary_color else
        "No verified color data — check that product appears in its real Amazon color."
    )

    try:
        img_b64    = base64.standard_b64encode(img_path.read_bytes()).decode()
        ext        = img_path.suffix.lower().lstrip(".")
        media_type = f"image/{'jpeg' if ext == 'jpg' else ext}"

        # Build content blocks — add reference image if available
        content_blocks = []
        if reference_image_path and reference_image_path.exists():
            ref_b64 = base64.standard_b64encode(reference_image_path.read_bytes()).decode()
            ref_ext = reference_image_path.suffix.lower().lstrip(".")
            ref_media = f"image/{'jpeg' if ref_ext == 'jpg' else ref_ext}"
            content_blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": ref_media, "data": ref_b64}
            })
            content_blocks.append({
                "type": "text",
                "text": "Image 1: REAL AMAZON PRODUCT REFERENCE (ground truth)"
            })

        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": img_b64}
        })

        ptve_prompt = f"""You are the Product Truth Validator Engine (PTVE).

Your ONLY job: verify that the generated ad image matches the REAL Amazon product.
You do NOT evaluate aesthetics or creativity — ONLY factual product fidelity.

Product: {product}
Slide: {slide_n}/5
{color_context}

VALIDATION CHECKLIST:
1. COLOR: Does the product shown match the verified Amazon color exactly? No invented variants?
2. MATERIAL: Does the material/finish (metal, plastic, glass, matte, glossy) look consistent with a real product?
3. SHAPE/STRUCTURE: Is the product shape recognizable and consistent with the product name?
4. IDENTITY: Is this clearly the same product — not a redesigned or hallucinated version?
5. CROSS-SLIDE: No color shift from what was specified ('{primary_color}' if known)?

FAIL CONDITIONS (automatic rejection):
- Product appears in a color NOT in: {colors_available if colors_available else ["real Amazon color"]}
- Product shape/structure appears modified or hallucinated
- Product material clearly inconsistent with product type
- Product identity unrecognizable

Respond with ONLY valid JSON (no markdown):
{{
  "status": "PASS or FAIL or WARNING",
  "issues": [
    {{
      "type": "color_mismatch | material_mismatch | identity_drift | shape_distortion",
      "severity": "low | medium | high",
      "slide": {slide_n},
      "expected": "what was expected",
      "detected": "what was found"
    }}
  ],
  "action": "publish | regenerate | review",
  "reasoning": "one sentence"
}}

If no issues: return {{"status":"PASS","issues":[],"action":"publish","reasoning":"Product truth verified."}}"""

        content_blocks.append({"type": "text", "text": ptve_prompt})

        body = _json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": content_blocks}]
        }).encode()

        req = _ul.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with _ul.urlopen(req, timeout=25) as r:
            resp = _json.loads(r.read())

        text = resp["content"][0]["text"].strip()
        import re as _re
        m = _re.search(r'\{.*\}', text, _re.DOTALL)
        if m:
            data    = _json.loads(m.group())
            status  = data.get("status", "PASS")
            issues  = data.get("issues", [])
            action  = data.get("action", "publish")
            has_high = any(i.get("severity") == "high" for i in issues)
            # Override: any high severity → regenerate
            if has_high:
                action = "regenerate"
            passed = action != "regenerate"
            return {
                "status":  status,
                "issues":  issues,
                "action":  action,
                "passed":  passed,
                "reasoning": data.get("reasoning", ""),
            }

    except Exception as e:
        # API failed — cannot validate, pass with warning
        return {
            "status": "WARNING", "action": "publish", "passed": True,
            "issues": [{"type": "api_error", "severity": "low",
                        "slide": slide_n, "expected": "PTVE check",
                        "detected": f"API error: {e}"}]
        }

    return {
        "status": "WARNING", "action": "publish", "passed": True,
        "issues": [{"type": "parse_error", "severity": "low",
                    "slide": slide_n, "expected": "JSON response", "detected": "parse failed"}]
    }


# ─── PIL text overlay ────────────────────────────────────────────────────────

def _load_font(size: int) -> "ImageFont.FreeTypeFont":
    for path in ["/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _strip_emoji(text: str) -> str:
    """Remove emoji/unicode symbols that Helvetica can't render."""
    import re
    # Keep basic ASCII + latin extended only
    return re.sub(r'[^\x00-\xFF]', '', text).strip()


def _add_overlay(
    img_path: Path,
    slot: str,
    product: str,
    price: str = "",
    rating: str = "",
    features: list[str] | None = None,
    affiliate: str = "@alexanderaether",
) -> Path:
    """
    Add text overlay: solid black bar at BOTTOM of image.
    Product image stays fully visible — text lives in dedicated bar.
    """
    if not PIL_OK:
        return img_path

    img = Image.open(img_path).convert("RGB")
    W, H = img.size

    # Bar height: ~18% of image height (enough for 2 lines of text)
    bar_h = max(120, int(H * 0.18))

    # Extend canvas downward with solid black bar
    new_img = Image.new("RGB", (W, H + bar_h), (10, 10, 10))
    new_img.paste(img, (0, 0))
    draw = ImageDraw.Draw(new_img)

    # Thin accent line separating image from bar
    accent_color = (0, 200, 255)
    draw.rectangle([(0, H), (W, H + 3)], fill=accent_color)

    font_big   = _load_font(56)
    font_med   = _load_font(42)
    font_small = _load_font(30)
    font_xs    = _load_font(22)

    def draw_text_centered(text, y, font, color=(255, 255, 255)):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        draw.text((x, y), text, font=font, fill=color)

    def draw_text_left(text, x, y, font, color=(200, 200, 200)):
        draw.text((x, y), text, font=font, fill=color)

    def draw_text_right(text, x, y, font, color=(200, 200, 200)):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((x - tw, y), text, font=font, fill=color)

    bar_top = H + 10  # padding inside bar

    if slot == "hero":
        # Product name + price
        name_short = product[:35] + "…" if len(product) > 35 else product
        draw_text_centered(name_short.upper(), bar_top, font_med)
        if price:
            draw_text_centered(price, bar_top + 52, font_big, accent_color)

    elif slot == "features":
        # Rating + affiliate handle
        if rating:
            draw_text_centered(f"★ {rating}  •  Amazon Best Seller", bar_top + 8, font_med, (255, 215, 0))
        draw_text_centered(f"@{affiliate.lstrip('@')}", bar_top + 58, font_small, (180, 180, 180))

    elif slot == "lifestyle":
        # Short product name + rating
        name_short = product[:40] + "…" if len(product) > 40 else product
        draw_text_centered(name_short, bar_top + 8, font_med)
        if rating:
            draw_text_centered(f"★ {rating}  on Amazon", bar_top + 60, font_small, (255, 215, 0))

    elif slot == "detail":
        # Feature list — strip emojis, font can't render them
        if features:
            y = bar_top + 5
            for feat in features[:2]:
                draw_text_centered(_strip_emoji(feat.strip()), y, font_small, (220, 220, 220))
                y += 40
        if price:
            draw_text_right(price, W - 20, bar_top + 5, font_big, accent_color)

    elif slot == "cta":
        # Bold CTA
        draw_text_centered("GET YOURS NOW  →", bar_top + 5, font_big, accent_color)
        draw_text_centered(f"{price}  •  Amazon  •  Link in Bio", bar_top + 68, font_small, (200, 200, 200))

    # Watermark bottom-right of bar
    wm_text = f"@{affiliate.lstrip('@')}"
    if slot not in ("features", "lifestyle"):
        draw_text_right(wm_text, W - 12, H + bar_h - 28, font_xs, (100, 100, 100))

    out = img_path.with_stem(img_path.stem + "_overlay")
    new_img.save(out, "PNG", quality=95)
    return out


# ─── Main carousel generator ─────────────────────────────────────────────────

async def generate_carousel_flow(
    product: str,
    category: str = "tech",
    n_slides: int = 5,
    aspect: str = "1:1",
    price: str = "",
    rating: str = "",
    features: list[str] | None = None,
    affiliate: str = "@alexanderaether • link en bio",
    add_overlay: bool = True,
    output_dir: Path | None = None,
    delay_between: float = 8.0,
    product_image_url: str | None = None,
    creative_modes: list[str] | None = None,
    season: str | None = None,
    product_colors: dict | None = None,
) -> list[Path]:
    """
    Generate carousel images via Google Flow (Nano Banana, FREE).

    Chrome with CDP must be running (or flow_operator auto-launches it).
    product_image_url: URL de imagen del producto Amazon → usada como referencia img2img.
    """
    import urllib.request as _ul
    import tempfile as _tmp

    # Descargar imagen de referencia del producto si se provee
    # NOTE: _ref_image is ONLY used for PTVE (QC validation via Claude vision).
    # It is NEVER passed to generate_images() — doing so activates Flow's img2img mode
    # which outputs MP4 instead of PNG. Product identity is enforced via prompt text anchor.
    _ref_image: Path | None = None
    if product_image_url:
        try:
            _tmp_file = _tmp.NamedTemporaryFile(suffix=".jpg", delete=False)
            _tmp_file.close()
            _ul.urlretrieve(product_image_url, _tmp_file.name)
            _ref_image = Path(_tmp_file.name)
            print(f"   📸 Imagen referencia descargada (PTVE only): {_ref_image} ({_ref_image.stat().st_size//1024}KB)")
        except Exception as e:
            print(f"   ⚠️  No se pudo descargar imagen referencia: {e}")
            _ref_image = None

    # Build hero anchor description: full product name + primary color (no img2img needed)
    _anchor_description = product
    if product_colors and product_colors.get("primary_color"):
        _anchor_description += f", color: {product_colors['primary_color']}"
    if product_colors and product_colors.get("colors_available"):
        _anchor_description += f" (available: {', '.join(product_colors['colors_available'][:3])})"

    slug = product.lower().replace(" ", "_")[:40]
    if output_dir is None:
        output_dir = FLOW_CAROUSEL_OUT / f"{slug}_flow"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🎨 Carousel via Google Flow: '{product}' ({n_slides} slides)")
    print(f"   Aspect: {aspect}  |  Overlay: {add_overlay}")
    print(f"   Output: {output_dir}")

    # Auto-detect category if not provided or 'general'
    if PROMPTS_OK and (category == "general" or not category):
        category = detect_category(product)

    # Load nano-banana-pro prompt library (category-aware)
    library_slides = None
    if PROMPTS_OK:
        try:
            entries = parse_readme()
            library_slides = select_carousel_prompts(product, product_category=category,
                                                      n_slides=n_slides, entries=entries)
            # Count how many library prompts were actually selected vs None fallbacks
            lib_count = sum(1 for e, _ in library_slides if e is not None)
            print(f"   Library prompts loaded: {lib_count}/{len(library_slides)} (category: {category})")
        except Exception as e:
            print(f"   Warning: prompt library unavailable: {e}")

    slots = ["hero", "features", "lifestyle", "detail", "cta"]
    slides = [{"slot": slots[i % len(slots)]} for i in range(n_slides)]

    # Ensure Chrome CDP is running
    if not ensure_chrome_ready():
        raise RuntimeError("Chrome CDP not available on port 9222. Launch Chrome with --remote-debugging-port=9222")

    saved: list[Path] = []

    async def _run():
        op = FlowOperator(plan={}, no_interactive=True)
        if not await op.connect():
            raise RuntimeError("FlowOperator connect failed")

        try:
            for i, slide_cfg in enumerate(slides):
                slot = slide_cfg["slot"]
                print(f"\n  Slide {i+1}/{n_slides}: [{slot}]")

                prompt = _build_prompt(
                    slide_index=i,
                    product=product,
                    category=category,
                    library_slides=library_slides,
                    price=price,
                    rating=rating,
                    affiliate=affiliate,
                    creative_modes=creative_modes,
                    season=season,
                    product_colors=product_colors,
                    anchor_description=_anchor_description if i == 0 else "",
                )
                print(f"    Prompt: {prompt[:80]}...")
                if i == 0:
                    print(f"    Anchor: {_anchor_description[:100]}")

                out_prefix = f"{slug}_slide{i+1:02d}_{slot}"

                # NEVER pass reference_image to generate_images() — activates img2img/video mode → MP4 output.
                # Product identity for hero slide is enforced via anchor_description in prompt text.
                # _ref_image is reserved exclusively for PTVE (post-generation QC via Claude vision).
                imgs = await op.generate_images(
                    prompt=prompt,
                    aspect_ratio=aspect,
                    count=1,
                    out_prefix=out_prefix,
                    reference_image=None,
                )

                if not imgs:
                    print(f"    ✗ Generation failed for slide {i+1}")
                    continue

                # Filter: only real image files (PNG, JPEG, WebP) — reject MP4/video named .png
                def _is_real_image(p: Path) -> bool:
                    """Check file magic bytes — accept PNG, JPEG, WebP."""
                    try:
                        with open(p, "rb") as _f:
                            hdr = _f.read(12)
                        return (
                            hdr[:4] == b"\x89PNG"                     # PNG
                            or hdr[:2] == b"\xff\xd8"                 # JPEG
                            or (hdr[:4] == b"RIFF" and hdr[8:12] == b"WEBP")  # WebP
                        )
                    except Exception:
                        return False

                valid_imgs  = [p for p in imgs if p.exists() and _is_real_image(p)]
                invalid_imgs = [p for p in imgs if p.exists() and not _is_real_image(p)]
                if invalid_imgs:
                    print(f"    ⚠️  Filtered {len(invalid_imgs)} non-image file(s) (MP4/video): {[p.name for p in invalid_imgs]}")
                    for p in invalid_imgs:
                        p.unlink(missing_ok=True)

                if not valid_imgs:
                    print(f"    ✗ All {len(imgs)} generated files are video/unknown. Skipping slide {i+1}.")
                    continue

                # Select best image: largest valid PNG = highest quality AI output
                best = max(valid_imgs, key=lambda p: p.stat().st_size if p.exists() else 0)
                print(f"    Selected best: {best.name} ({best.stat().st_size//1024}KB) from {len(valid_imgs)} valid PNG(s)")

                # Cleanup other variants
                for p in imgs:
                    if p != best and p.exists():
                        p.unlink()

                # ── Autonomous QC — reject and regenerate if below standard ──
                MAX_QC_RETRIES = 2
                qc_attempt = 0
                qc_passed = False
                current_best = best

                while qc_attempt <= MAX_QC_RETRIES:
                    qc_result = _qc_evaluate(current_best, slot, product)
                    score    = qc_result["score"]
                    clarity  = qc_result.get("product_clarity", 10)
                    verdict  = qc_result["verdict"]
                    reason   = qc_result["reason"]

                    if qc_result["passed"]:
                        print(f"    QC OK {score}/10 clarity:{clarity}/10 — {verdict}")
                        qc_passed = True
                        best = current_best
                        break
                    else:
                        if clarity < 8:
                            print(f"    QC FAIL clarity:{clarity}/10 (need >=8) — {reason}")
                        else:
                            print(f"    QC FAIL {score}/10 — {reason}")
                        if qc_attempt < MAX_QC_RETRIES:
                            print(f"    Regenerating (attempt {qc_attempt+1}/{MAX_QC_RETRIES})...")
                            await asyncio.sleep(5)
                            retry_imgs = await op.generate_images(
                                prompt=prompt,
                                aspect_ratio=aspect,
                                count=1,
                                out_prefix=f"{out_prefix}_retry{qc_attempt+1}",
                                reference_image=None,
                            )
                            if retry_imgs:
                                retry_best = max(retry_imgs, key=lambda p: p.stat().st_size if p.exists() else 0)
                                for p in retry_imgs:
                                    if p != retry_best and p.exists():
                                        p.unlink()
                                current_best = retry_best
                        qc_attempt += 1

                if not qc_passed:
                    print(f"    QC: keeping best available after {MAX_QC_RETRIES} retries")

                # ── PTVE — Product Truth Validator ────────────────────────────
                ptve = _ptve_validate(
                    img_path=current_best,
                    slide_index=i,
                    product=product,
                    product_colors=product_colors,
                    reference_image_path=_ref_image,
                )
                if ptve["action"] == "regenerate":
                    issues_str = "; ".join(
                        f"{iss['type']}({iss['severity']}): {iss['detected']}"
                        for iss in ptve["issues"]
                    )
                    print(f"    PTVE FAIL [{ptve['status']}] — {issues_str}")
                    # One PTVE regeneration attempt (don't loop — already retried in QC)
                    if qc_attempt < MAX_QC_RETRIES + 1:
                        print(f"    PTVE: regenerating for product truth...")
                        await asyncio.sleep(5)
                        ptve_imgs = await op.generate_images(
                            prompt=prompt, aspect_ratio=aspect, count=1,
                            out_prefix=f"{out_prefix}_ptve",
                            reference_image=None,
                        )
                        if ptve_imgs:
                            ptve_best = max(ptve_imgs, key=lambda p: p.stat().st_size if p.exists() else 0)
                            for p in ptve_imgs:
                                if p != ptve_best and p.exists():
                                    p.unlink()
                            current_best = ptve_best
                            print(f"    PTVE retry: {ptve_best.name}")
                        # Use best available regardless
                    else:
                        print(f"    PTVE: max retries — keeping best available")
                elif ptve["action"] == "review":
                    print(f"    PTVE WARNING [{ptve['status']}] — {ptve.get('reasoning','')}")
                else:
                    print(f"    PTVE OK [{ptve['status']}] — {ptve.get('reasoning','Product truth verified.')}")

                dest = output_dir / f"slide_{i+1:02d}_{slot}.png"
                current_best.rename(dest)
                print(f"    ✅ {dest.name}  ({dest.stat().st_size//1024}KB)")

                # PIL overlay: barra sólida inferior con texto legible
                if add_overlay and PIL_OK:
                    dest = _add_overlay(
                        dest,
                        slot=slot,
                        product=product,
                        price=price,
                        rating=rating,
                        features=features,
                        affiliate=affiliate,
                    )
                    print(f"    + overlay → {dest.name}")

                saved.append(dest)

                # Rate-limit buffer between generations
                if i < len(slides) - 1:
                    print(f"    Waiting {delay_between}s...")
                    await asyncio.sleep(delay_between)

        finally:
            await op.close()

    await _run()

    # Manifest
    manifest = {
        "product": product,
        "category": category,
        "aspect": aspect,
        "slides": [str(p) for p in saved],
        "type": "flow_ai",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\n✅ Carousel complete: {len(saved)}/{n_slides} slides")
    return saved


# ─── Amazon image extractor ───────────────────────────────────────────────────

def get_amazon_product_image(asin: str) -> str | None:
    """Extrae URL de imagen principal de Amazon dado un ASIN."""
    import urllib.request as _ul, re as _re
    url = f"https://www.amazon.com/dp/{asin}"
    req = _ul.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with _ul.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")
        for pat in [
            r'"hiRes":"(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"',
            r'"large":"(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"',
            r'id="landingImage"[^>]+src="([^"]+)"',
        ]:
            m = _re.search(pat, html)
            if m:
                return m.group(1)
    except Exception as e:
        print(f"   ⚠️  get_amazon_product_image({asin}): {e}")
    return None


def get_amazon_product_colors(asin: str, product_name: str = "") -> dict:
    """
    Extract real color/variant data from Amazon product listing.

    Returns:
        {
          "colors_available": ["Teal", "Pink", "Black", ...],  # real variants
          "primary_color":    "Teal",                          # detected from title/listing
          "color_source":     "amazon_listing" | "title_parse" | "unknown",
          "raw_variants":     [...],                           # raw strings for debug
        }

    FAIL CONDITION: if no colors found, returns empty colors_available.
    Caller must STOP generation if colors_available is empty and product is color-variant.
    """
    import urllib.request as _ul, re as _re, json as _json

    result = {
        "colors_available": [],
        "primary_color":    "",
        "color_source":     "unknown",
        "raw_variants":     [],
    }

    url = f"https://www.amazon.com/dp/{asin}"
    req = _ul.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })

    try:
        with _ul.urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8", errors="ignore")

        # ── Strategy 1: twister-plus JSON (most reliable) ──────────────────
        twister_match = _re.search(r'"variationValues"\s*:\s*(\{[^}]{0,2000}\})', html)
        if twister_match:
            try:
                vv = _json.loads(twister_match.group(1))
                # color_name key is common for color variants
                for key in ("color_name", "color", "Color", "colour"):
                    if key in vv:
                        colors = vv[key] if isinstance(vv[key], list) else [vv[key]]
                        result["colors_available"] = [c.strip() for c in colors if c.strip()]
                        result["color_source"] = "amazon_listing"
                        break
            except Exception:
                pass

        # ── Strategy 2: dimension buttons / swatch labels ──────────────────
        if not result["colors_available"]:
            swatches = _re.findall(
                r'class="[^"]*swatch[^"]*"[^>]*title="([^"]{2,40})"', html, _re.IGNORECASE
            )
            if swatches:
                result["colors_available"] = list(dict.fromkeys(s.strip() for s in swatches))
                result["color_source"] = "amazon_listing"

        # ── Strategy 3: parse product title for color hint ─────────────────
        # e.g. "Owala FreeSip ... Teal/Blue" → primary color
        COMMON_COLORS = [
            "black", "white", "gray", "grey", "silver", "gold", "rose gold",
            "blue", "navy", "teal", "cyan", "green", "olive", "mint",
            "red", "pink", "coral", "orange", "yellow", "purple", "violet",
            "brown", "tan", "beige", "cream", "ivory", "copper", "bronze",
            "multicolor", "clear", "transparent",
        ]
        name_lower = product_name.lower()
        found_in_title = [c for c in COMMON_COLORS if c in name_lower]
        if found_in_title:
            result["primary_color"] = found_in_title[0].title()
            if not result["colors_available"]:
                result["colors_available"] = [result["primary_color"]]
                result["color_source"] = "title_parse"

        # ── Strategy 4: colorImages JSON block ────────────────────────────
        if not result["colors_available"]:
            color_imgs = _re.findall(
                r'"colorImages"\s*:\s*\{[^}]*"([A-Za-z][A-Za-z\s/&+]{1,30})"', html
            )
            if color_imgs:
                result["colors_available"] = list(dict.fromkeys(c.strip() for c in color_imgs[:10]))
                result["color_source"] = "amazon_listing"

        result["raw_variants"] = result["colors_available"][:20]

        # Set primary_color to first available if not set yet
        if result["colors_available"] and not result["primary_color"]:
            result["primary_color"] = result["colors_available"][0]

    except Exception as e:
        print(f"   ⚠️  get_amazon_product_colors({asin}): {e}")

    return result


# ─── Sync wrapper ─────────────────────────────────────────────────────────────

def generate_carousel_flow_sync(**kwargs) -> list[Path]:
    return asyncio.run(generate_carousel_flow(**kwargs))


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Generate product carousel via Google Flow (Nano Banana, FREE)"
    )
    ap.add_argument("--product",   required=True, help="Product name")
    ap.add_argument("--category",  default="general",
                    choices=["tech","beauty","fashion","food","home","sports",
                             "tools","kids","pet","general"],
                    help="Product category (default: auto-detect from product name)")
    ap.add_argument("--slides",    type=int, default=5, help="Number of slides (1-6)")
    ap.add_argument("--aspect",    default="1:1",
                    choices=["1:1","9:16","16:9","3:4"],
                    help="Aspect ratio (1:1 = Instagram square, 9:16 = TikTok)")
    ap.add_argument("--price",     default="", help="Product price e.g. '$89.99'")
    ap.add_argument("--rating",    default="", help="Rating e.g. '4.6/5'")
    ap.add_argument("--features",  default="",
                    help="Comma-separated features e.g. 'ANC,30h battery,IPX4'")
    ap.add_argument("--affiliate", default="@alexanderaether • link en bio")
    ap.add_argument("--overlay",   action="store_true",
                    help="Add text overlay (product name, price, features) on images")
    ap.add_argument("--no-overlay", dest="overlay", action="store_false")
    ap.set_defaults(overlay=True)
    ap.add_argument("--output",    type=Path, default=None)
    ap.add_argument("--delay",     type=float, default=8.0,
                    help="Seconds between generations (default: 8)")
    args = ap.parse_args()

    feats = [f.strip() for f in args.features.split(",")] if args.features else None

    paths = asyncio.run(generate_carousel_flow(
        product=args.product,
        category=args.category,
        n_slides=args.slides,
        aspect=args.aspect,
        price=args.price,
        rating=args.rating,
        features=feats,
        affiliate=args.affiliate,
        add_overlay=args.overlay,
        output_dir=args.output,
        delay_between=args.delay,
    ))

    print("\nGenerated slides:")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()
