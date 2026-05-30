#!/usr/bin/env python3
"""
camera_motion_library.py — Complete cinematic camera motion catalog.

16 camera movements, each documented with emotional feel, ideal products,
lighting pairings, prompt templates, and common mistakes.

RESEARCH-ONLY: No video generation. Pure knowledge.
"""

from __future__ import annotations

from core.cinematic_video.research.schemas import CameraMotion


_CAMERA_MOTIONS: tuple[CameraMotion, ...] = (
    CameraMotion(
        motion_id="dolly_in",
        name="Dolly In",
        description="Camera moves smoothly toward the subject, increasing intimacy and focus.",
        emotional_feel="Intimate, revealing, focusing attention",
        ideal_for=("luxury watches", "jewelry", "skincare bottles", "premium electronics"),
        recommended_speed="slow",
        lighting_pairing=("dark_matte", "soft_rim", "product_spotlight"),
        prompt_template="slow dolly in toward {product}, {lighting}, cinematic commercial, macro lens, shallow depth of field",
        common_mistakes=(
            "Moving too fast — ruins the luxury feel",
            "Not specifying 'slow' — default speed is too quick",
            "Dolly in without macro lens — loses detail at close range",
        ),
        example_use="Slow dolly in on a matte black watch, revealing dial texture as camera approaches",
    ),
    CameraMotion(
        motion_id="dolly_out",
        name="Dolly Out",
        description="Camera moves smoothly away from the subject, revealing context and scale.",
        emotional_feel="Revealing, contextual, grand",
        ideal_for=("full product kits", "bundles", "lifestyle setups", "product + accessories"),
        recommended_speed="slow",
        lighting_pairing=("studio_three_point", "natural_window", "high_key_commercial"),
        prompt_template="slow dolly out from {product}, revealing {context}, {lighting}, cinematic wide shot",
        common_mistakes=(
            "Starting too close — subject fills frame, no room for dolly",
            "Not having a meaningful background to reveal",
            "Dolly out with wide angle — distortion on edges",
        ),
        example_use="Dolly out from a gaming keyboard to reveal the full desktop battlestation setup",
    ),
    CameraMotion(
        motion_id="orbit",
        name="Orbit",
        description="Camera circles around the subject, showing it from all angles. The definitive product showcase movement.",
        emotional_feel="Dynamic, premium, 360° showcase",
        ideal_for=("all products", "electronics", "shoes", "bottles", "gadgets"),
        recommended_speed="slow",
        lighting_pairing=("dark_matte", "soft_rim", "reflective_surface", "product_spotlight"),
        prompt_template="slow orbit around {product}, {lighting}, cinematic commercial, product on reflective surface, ultra realistic",
        common_mistakes=(
            "Orbit too fast — product blurs, loses detail",
            "Product not centered — orbit reveals empty space",
            "No reflective surface — orbit looks flat without depth cues",
            "Complex background — distracts from orbiting product",
        ),
        example_use="Slow orbit around a perfume bottle on dark reflective obsidian, rim light catching glass edges",
    ),
    CameraMotion(
        motion_id="crane_up",
        name="Crane Up",
        description="Camera rises vertically, revealing the product from below to above. Grand, cinematic reveal.",
        emotional_feel="Epic, grand reveal, cinematic, powerful",
        ideal_for=("flagship products", "premium launches", "hero shots", "complete product sets"),
        recommended_speed="slow",
        lighting_pairing=("dark_matte", "low_key_dramatic", "studio_three_point"),
        prompt_template="slow crane up revealing {product}, {lighting}, cinematic commercial, dramatic reveal, premium aesthetic",
        common_mistakes=(
            "Crane up with nothing interesting at the top — anticlimactic",
            "Too fast — loses dramatic weight",
            "Background too busy — distracts from vertical reveal",
        ),
        example_use="Crane up from base to top of a premium speaker, dramatic lighting, revealing brushed metal texture",
    ),
    CameraMotion(
        motion_id="crane_down",
        name="Crane Down",
        description="Camera descends vertically onto the subject. Creates anticipation and discovery.",
        emotional_feel="Anticipatory, descending, discovery",
        ideal_for=("unboxing-style", "product reveals", "top-down beauty shots"),
        recommended_speed="slow",
        lighting_pairing=("soft_rim", "product_spotlight", "golden_hour"),
        prompt_template="slow crane down onto {product}, {lighting}, cinematic top-down reveal, premium commercial",
        common_mistakes=(
            "Starting too high — takes too long to reach product",
            "Product not centered — crane misses it",
            "Lighting from wrong angle — shadows obscure product as camera descends",
        ),
        example_use="Crane down onto a luxury skincare set arranged on marble, soft rim light creating elegant shadows",
    ),
    CameraMotion(
        motion_id="handheld",
        name="Handheld",
        description="Slightly unsteady, organic camera movement. Feels authentic, documentary-style, real.",
        emotional_feel="Authentic, raw, lifestyle, human, documentary",
        ideal_for=("lifestyle products", "fashion", "outdoor gear", "food/drink", "behind-the-scenes"),
        recommended_speed="medium",
        lighting_pairing=("natural_window", "golden_hour", "warm_lifestyle"),
        prompt_template="handheld camera following {product} in {environment}, natural lighting, lifestyle documentary style, authentic movement",
        common_mistakes=(
            "Too much shake — looks amateur, not cinematic",
            "Handheld with luxury products — wrong vibe (luxury = stable)",
            "No subject tracking — camera wanders away from product",
        ),
        example_use="Handheld following someone using a coffee maker in a sunlit kitchen, warm natural light",
    ),
    CameraMotion(
        motion_id="tracking_shot",
        name="Tracking Shot",
        description="Camera follows a moving subject laterally. Creates momentum and energy.",
        emotional_feel="Energetic, kinetic, following, dynamic",
        ideal_for=("sports gear", "activewear", "shoes", "automotive", "drone shots"),
        recommended_speed="medium",
        lighting_pairing=("golden_hour", "natural_window", "high_key_commercial"),
        prompt_template="tracking shot following {product}, {environment}, {lighting}, dynamic commercial, smooth motion",
        common_mistakes=(
            "Product moves too fast — camera can't track",
            "Static product + tracking shot = camera moves, nothing happens",
            "Jittery background — tracking amplifies background issues",
        ),
        example_use="Tracking shot following running shoes on a trail, golden hour light, dynamic movement",
    ),
    CameraMotion(
        motion_id="macro_close_up",
        name="Macro Close-Up",
        description="Extreme close-up revealing texture, materials, and craftsmanship details invisible to the naked eye.",
        emotional_feel="Intimate, luxurious, detailed, craftsmanship-focused",
        ideal_for=("watches", "jewelry", "leather goods", "skincare texture", "electronics details"),
        recommended_speed="slow",
        lighting_pairing=("soft_rim", "product_spotlight", "dark_matte", "macro_lighting"),
        prompt_template="extreme macro close-up of {product_detail}, {lighting}, macro lens, ultra detailed, shallow depth of field, premium craftsmanship",
        common_mistakes=(
            "Too close — loses context, viewer doesn't know what they're looking at",
            "Wrong lighting — macro needs soft, diffused light to avoid harsh shadows",
            "Motion on macro — even tiny movements look huge, use very slow motion",
        ),
        example_use="Extreme macro of watch movement gears, soft rim light catching polished metal, ultra detailed",
    ),
    CameraMotion(
        motion_id="push_in",
        name="Push In",
        description="Camera pushes forward into the scene. Similar to dolly in but more aggressive and focused.",
        emotional_feel="Dramatic, focused, intensifying",
        ideal_for=("hero shots", "product reveals", "key moments", "CTA transitions"),
        recommended_speed="medium",
        lighting_pairing=("dark_matte", "low_key_dramatic", "product_spotlight"),
        prompt_template="push in toward {product}, {lighting}, dramatic commercial, intensifying focus, cinematic",
        common_mistakes=(
            "Push in on static product without reason — feels random",
            "Too fast — jars the viewer",
            "Push in with wide lens — distortion at close range",
        ),
        example_use="Push in on a gaming mouse as RGB lights activate, dramatic dark lighting, intensifying focus",
    ),
    CameraMotion(
        motion_id="rack_focus",
        name="Rack Focus",
        description="Focus shifts from one subject to another, directing viewer attention. Sophisticated storytelling tool.",
        emotional_feel="Sophisticated, directing attention, cinematic storytelling",
        ideal_for=("product + lifestyle", "before/after", "product + detail", "comparison shots"),
        recommended_speed="slow",
        lighting_pairing=("soft_rim", "studio_three_point", "cinematic_shallow_dof"),
        prompt_template="rack focus from {subject_a} to {product}, {lighting}, shallow depth of field, cinematic commercial",
        common_mistakes=(
            "Subjects too close together — rack focus barely visible",
            "No depth separation — both subjects in same focal plane",
            "Rack focus too fast — disorienting",
        ),
        example_use="Rack focus from blurred background to sharp product in foreground, shallow depth of field",
    ),
    CameraMotion(
        motion_id="hero_shot",
        name="Hero Shot",
        description="The definitive product beauty shot. Centered, perfectly lit, slowly rotating or static. The 'money shot' of product advertising.",
        emotional_feel="Iconic, definitive, premium, aspirational",
        ideal_for=("every product", "flagship items", "hero images", "main ad visual"),
        recommended_speed="slow",
        lighting_pairing=("dark_matte", "soft_rim", "studio_three_point", "product_spotlight"),
        prompt_template="hero shot of {product}, centered composition, {lighting}, cinematic commercial, premium product photography, ultra realistic, high-end advertisement",
        common_mistakes=(
            "Busy background — hero shots need clean focus",
            "Product not perfectly centered",
            "Lighting too flat — hero shots need dramatic lighting",
        ),
        example_use="Hero shot of matte black headphones on dark surface, soft rim light, centered, slowly rotating",
    ),
    CameraMotion(
        motion_id="cinematic_pan",
        name="Cinematic Pan",
        description="Camera pans horizontally across a scene. Reveals product in context, creates narrative flow.",
        emotional_feel="Narrative, sweeping, contextual, cinematic",
        ideal_for=("lifestyle setups", "product lines", "before/after", "environmental context"),
        recommended_speed="slow",
        lighting_pairing=("natural_window", "golden_hour", "warm_lifestyle"),
        prompt_template="slow cinematic pan across {scene}, {lighting}, revealing {product}, cinematic commercial, smooth movement",
        common_mistakes=(
            "Pan speed inconsistent — looks mechanical",
            "Nothing interesting along the pan path",
            "Pan + complex background = motion blur mess",
        ),
        example_use="Cinematic pan across a desk setup, revealing peripherals one by one, warm ambient lighting",
    ),
    CameraMotion(
        motion_id="parallax_movement",
        name="Parallax Movement",
        description="Camera moves while subjects at different depths move at different speeds. Creates 3D depth illusion.",
        emotional_feel="Immersive, 3D, professional, premium",
        ideal_for=("product + environment", "foreground/background separation", "premium tech"),
        recommended_speed="slow",
        lighting_pairing=("dark_matte", "soft_rim", "cinematic_shallow_dof"),
        prompt_template="parallax camera movement around {product}, {lighting}, foreground and background separation, 3D depth, cinematic commercial",
        common_mistakes=(
            "No depth separation — parallax needs distinct foreground/background",
            "Movement too fast — parallax effect becomes chaotic",
            "Single subject only — parallax needs multiple depth planes",
        ),
        example_use="Parallax orbit around smartphone, foreground elements blurring while product stays sharp",
    ),
    CameraMotion(
        motion_id="slow_reveal",
        name="Slow Reveal",
        description="Product is gradually revealed — from darkness, from behind an object, or through gradual lighting. Builds anticipation.",
        emotional_feel="Mysterious, anticipatory, premium, dramatic",
        ideal_for=("product launches", "new releases", "premium items", "teaser content"),
        recommended_speed="slow",
        lighting_pairing=("low_key_dramatic", "dark_matte", "product_spotlight"),
        prompt_template="slow reveal of {product} emerging from darkness, {lighting}, dramatic lighting reveal, cinematic commercial, anticipation",
        common_mistakes=(
            "Reveal too fast — loses all dramatic tension",
            "Nothing worth revealing — anticlimactic",
            "Too dark at start — viewer can't see anything",
        ),
        example_use="Slow reveal of a premium wallet emerging from darkness, single spotlight catching leather texture",
    ),
    CameraMotion(
        motion_id="top_down_rotation",
        name="Top-Down Rotation",
        description="Flat-lay style, camera directly above, product rotates or is arranged on surface. Popular for social media ads.",
        emotional_feel="Clean, organized, satisfying, social-media-friendly",
        ideal_for=("flat lay products", "skincare", "food", "accessories", "organization products"),
        recommended_speed="medium",
        lighting_pairing=("high_key_commercial", "studio_three_point", "natural_window"),
        prompt_template="top-down view of {product} on {surface}, slow rotation, {lighting}, clean composition, commercial flat lay",
        common_mistakes=(
            "Shadows from camera/lights visible in shot",
            "Surface too busy — distracts from product",
            "Rotation not centered — product drifts off frame",
        ),
        example_use="Top-down rotation of skincare products arranged on marble, clean studio lighting, satisfying organization",
    ),
    CameraMotion(
        motion_id="floating_object_orbit",
        name="Floating Object Orbit",
        description="Product appears to float in space while camera orbits. Pure product focus, no environment. Very premium, tech-forward look.",
        emotional_feel="Futuristic, premium, minimal, tech-forward, magical",
        ideal_for=("tech products", "premium gadgets", "minimalist brands", "wireless products"),
        recommended_speed="slow",
        lighting_pairing=("dark_matte", "soft_rim", "reflective_surface", "neon_accent"),
        prompt_template="{product} floating in dark space, slow orbit, {lighting}, no background, minimal composition, futuristic premium commercial",
        common_mistakes=(
            "Product shadow visible — breaks floating illusion",
            "Too much environment — product should float in void",
            "Orbit too fast — floating objects need slow, graceful motion",
        ),
        example_use="Wireless earbuds floating in dark void, slow orbit, soft rim light, futuristic premium aesthetic",
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_motions() -> tuple[CameraMotion, ...]:
    """Return all 16 documented camera motions."""
    return _CAMERA_MOTIONS


def get_motion(motion_id: str) -> CameraMotion | None:
    """Look up a single motion by ID."""
    for m in _CAMERA_MOTIONS:
        if m.motion_id == motion_id:
            return m
    return None


def get_motions_by_emotion(emotion_keyword: str) -> tuple[CameraMotion, ...]:
    """Find motions matching an emotional quality keyword."""
    kw = emotion_keyword.lower()
    return tuple(
        m for m in _CAMERA_MOTIONS
        if kw in m.emotional_feel.lower()
    )


def get_motions_for_product(product_type: str) -> tuple[CameraMotion, ...]:
    """Find motions suitable for a product category."""
    pt = product_type.lower()
    return tuple(
        m for m in _CAMERA_MOTIONS
        if any(pt in ideal.lower() for ideal in m.ideal_for)
        or "all products" in " ".join(m.ideal_for).lower()
    )


def get_motions_by_speed(speed: str) -> tuple[CameraMotion, ...]:
    """Filter motions by recommended speed."""
    return tuple(m for m in _CAMERA_MOTIONS if m.recommended_speed == speed)


def motion_count() -> int:
    return len(_CAMERA_MOTIONS)
