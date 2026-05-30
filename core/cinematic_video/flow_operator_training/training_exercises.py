#!/usr/bin/env python3
"""
training_exercises.py — Flow Operator Training Exercises (Phase 4).

24 DRY-RUN exercises across 4 skill levels that teach the agent:
    - How to navigate Flow's UI
    - How to execute workflows (extend, export, scene build)
    - How to maintain continuity across clips
    - How to optimize credit usage

RESEARCH-ONLY: No video generation. No Flow API calls.
Pure knowledge: button sequences, panel navigation, workflow orchestration.
"""

from __future__ import annotations

from core.cinematic_video.flow_operator_training.schemas import (
    FlowAction,
    FlowExercise,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _act(
    action_id: str,
    name: str,
    description: str,
    ui_element_id: str,
    action_type: str,
    target: str,
    payload: str = "",
) -> FlowAction:
    return FlowAction(
        action_id=action_id,
        name=name,
        description=description,
        ui_element_id=ui_element_id,
        action_type=action_type,
        target=target,
        payload=payload,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 1 — BASIC (6 exercises)
# Goal: Master Flow navigation, tabs, panels, and single-generation workflows.
# ═══════════════════════════════════════════════════════════════════════════════

_BASIC_EXERCISES: tuple[FlowExercise, ...] = (

    # Exercise 1: Tab Discovery
    FlowExercise(
        exercise_id="basic_01_navigate_tabs",
        title="Tab Discovery — Navigate All Flow Tabs",
        skill_level="basic",
        goal="Learn all main tabs in Flow's top navigation bar.",
        description=(
            "Open Google Flow and systematically visit each tab: "
            "Text-to-Video, Image-to-Video, Scene Builder. "
            "Observe how the UI changes between tabs — different input fields, "
            "different right-panel controls."
        ),
        preconditions=(
            "Flow is open at labs.google/fx",
            "Logged in to Google account with credits available",
        ),
        steps=(
            _act("nav_text_tab", "Click Text-to-Video tab", "Switch to text-to-video generation mode",
                 "text_to_video_tab", "navigate", "top_nav"),
            _act("observe_prompt", "Observe prompt input field", "Note the large text area and character limit",
                 "prompt_input_field", "navigate", "center_panel"),
            _act("nav_image_tab", "Click Image-to-Video tab", "Switch to image-based generation",
                 "image_to_video_tab", "navigate", "top_nav"),
            _act("observe_upload", "Observe image upload area", "Note the upload zone and format hints",
                 "image_to_video_tab", "navigate", "center_panel"),
            _act("nav_scene_builder", "Click Scene Builder tab", "Switch to multi-scene planning mode",
                 "scene_builder_panel", "navigate", "top_nav"),
        ),
        expected_outcome="Agent can navigate between all 3 main tabs without confusion.",
        success_criteria=(
            "Visited Text-to-Video tab",
            "Visited Image-to-Video tab",
            "Visited Scene Builder tab",
            "Can describe the center panel for each tab",
        ),
        tips=(
            "Tabs are always at the top — they never move",
            "Scene Builder may be hidden behind a 'More' menu on some accounts",
        ),
        common_mistakes=(
            "Clicking Generate accidentally while exploring",
            "Not noticing the right panel changes between tabs",
        ),
        estimated_minutes=2,
    ),

    # Exercise 2: Prompt Input Mastery
    FlowExercise(
        exercise_id="basic_02_prompt_input",
        title="Prompt Input Mastery — Structure Your First Prompt",
        skill_level="basic",
        goal="Learn how to structure a proper cinematic prompt using the template: PRODUCT + CAMERA + LIGHTING + MOTION + ATMOSPHERE.",
        description=(
            "Write a prompt for a fictional product (e.g., 'matte black smartwatch') "
            "using the standard template. Type it into the prompt input field, "
            "verify the structure, and set aspect ratio to 9:16. DO NOT generate."
        ),
        preconditions=("On Text-to-Video tab",),
        steps=(
            _act("nav_text_tab", "Ensure Text-to-Video tab is active",
                 "Verify correct tab", "text_to_video_tab", "navigate", "top_nav"),
            _act("type_prompt", "Type structured prompt", "Enter PRODUCT+CAMERA+LIGHTING+MOTION+ATMOSPHERE",
                 "prompt_input_field", "type", "prompt_input",
                 payload="Matte black smartwatch, floating above obsidian surface, "
                         "dark luxury lighting, slow orbit, premium commercial"),
            _act("set_aspect_9_16", "Set aspect ratio to 9:16", "Change aspect ratio for vertical video",
                 "aspect_ratio_selector", "select", "aspect_ratio", payload="9:16"),
            _act("verify_prompt", "Verify prompt structure", "Check: PRODUCT present? CAMERA present? LIGHTING present?",
                 "prompt_input_field", "navigate", "center_panel"),
            _act("do_not_generate", "DO NOT click Generate", "Exercise complete — no generation needed",
                 "generate_button", "navigate", "bottom_right"),
        ),
        expected_outcome="Agent produces a well-structured prompt WITHOUT generating.",
        success_criteria=(
            "Prompt follows PRODUCT + CAMERA + LIGHTING + MOTION + ATMOSPHERE order",
            "Aspect ratio is correctly set to 9:16",
            "Generate button was NOT clicked",
            "Prompt is under 200 characters",
        ),
        tips=(
            "Most important keywords FIRST — Flow prioritizes early terms",
            "Product description should be concrete, not abstract",
        ),
        common_mistakes=(
            "Putting atmosphere before camera (weaker results)",
            "Forgetting to set aspect ratio before generating",
        ),
        estimated_minutes=3,
    ),

    # Exercise 3: Credit Check Protocol
    FlowExercise(
        exercise_id="basic_03_credit_check",
        title="Credit Check Protocol — Budget Before Generation",
        skill_level="basic",
        goal="Learn to check remaining credits BEFORE every generation session.",
        description=(
            "Locate the credit display in Flow's UI. Note your remaining credits. "
            "Mentally plan how many generations you can afford before hitting zero. "
            "This habit prevents wasted sessions."
        ),
        preconditions=("Logged into Flow",),
        steps=(
            _act("find_credit_display", "Locate credit display", "Find remaining credits counter",
                 "credit_display", "navigate", "top_right"),
            _act("note_credits", "Note remaining credits", "Record the number shown",
                 "credit_display", "navigate", "top_right"),
            _act("plan_budget", "Plan budget", "If 8 credits remain, plan max 6 generations (save 2)",
                 "credit_display", "navigate", "top_right"),
        ),
        expected_outcome="Agent knows remaining credits and has a generation budget plan.",
        success_criteria=(
            "Credit display located",
            "Remaining credits noted",
            "Generation budget planned (leave 20% buffer)",
        ),
        tips=(
            "Credits reset daily — check reset time for your region",
            "Text-to-video: 1 credit. Extend: 1 credit. Image-to-video: 1 credit",
        ),
        common_mistakes=(
            "Forgetting to check credits before starting a session",
            "Assuming unlimited credits",
        ),
        estimated_minutes=1,
    ),

    # Exercise 4: Aspect Ratio Matrix
    FlowExercise(
        exercise_id="basic_04_aspect_ratio",
        title="Aspect Ratio Matrix — Platform-Specific Ratios",
        skill_level="basic",
        goal="Learn which aspect ratio to use for each platform (9:16 for Reels, 1:1 for feed, 16:9 for YouTube).",
        description=(
            "Practice switching between Flow's aspect ratio presets. "
            "For each platform (Instagram Reel, TikTok, YouTube Short, Instagram Feed), "
            "select the correct ratio and note how the preview changes."
        ),
        preconditions=("On Text-to-Video tab",),
        steps=(
            _act("set_9_16", "Set 9:16 for Reels/TikTok", "Vertical video — full phone screen",
                 "aspect_ratio_selector", "select", "aspect_ratio", payload="9:16"),
            _act("set_1_1", "Set 1:1 for Feed posts", "Square — Instagram feed / thumbnails",
                 "aspect_ratio_selector", "select", "aspect_ratio", payload="1:1"),
            _act("set_16_9", "Set 16:9 for YouTube/landscape", "Horizontal — widescreen format",
                 "aspect_ratio_selector", "select", "aspect_ratio", payload="16:9"),
            _act("set_4_5", "Set 4:5 for portrait feed", "Tall rectangle — Instagram portrait",
                 "aspect_ratio_selector", "select", "aspect_ratio", payload="4:5"),
        ),
        expected_outcome="Agent can instantly recall which ratio maps to which platform.",
        success_criteria=(
            "9:16 → TikTok, Reels, Shorts",
            "1:1 → Instagram Feed, Thumbnails",
            "16:9 → YouTube, Landscape ads",
            "4:5 → Instagram Portrait feed",
        ),
        tips=(
            "Set ratio BEFORE typing prompt — changing ratio can reset some inputs",
            "9:16 crops the most aggressively — center your product",
        ),
        common_mistakes=(
            "Using 1:1 for Reels (wastes screen space)",
            "Setting aspect ratio after typing prompt (may reset)",
        ),
        estimated_minutes=2,
    ),

    # Exercise 5: Style Preset Selection
    FlowExercise(
        exercise_id="basic_05_style_preset",
        title="Style Preset Selection — Match Style to Product",
        skill_level="basic",
        goal="Learn which Flow style presets work best for different product categories.",
        description=(
            "Flow offers style presets: Cinematic, Realistic, Artistic, Animation, etc. "
            "Practice selecting the right preset for: luxury watch, gym supplement, "
            "beauty cream, gaming mouse."
        ),
        preconditions=("On Text-to-Video tab",),
        steps=(
            _act("open_style_panel", "Open Style presets panel", "Locate style selector",
                 "style_presets", "navigate", "right_panel"),
            _act("select_cinematic", "Select 'Cinematic' for luxury watch", "Best for premium products",
                 "style_presets", "select", "style_preset", payload="Cinematic"),
            _act("select_realistic", "Select 'Realistic' for gym supplement", "Best for lifestyle/utility",
                 "style_presets", "select", "style_preset", payload="Realistic"),
            _act("avoid_artistic", "Note: Avoid 'Artistic' for commercial ads", "Artistic distorts product realism",
                 "style_presets", "navigate", "right_panel"),
        ),
        expected_outcome="Agent matches style presets to product categories correctly.",
        success_criteria=(
            "Cinematic → luxury, tech, premium",
            "Realistic → lifestyle, fitness, utility",
            "Artistic → avoid for commercial products",
        ),
        tips=(
            "Style preset OVERRIDES prompt style keywords — be intentional",
            "'Cinematic' + slow orbit = best luxury ad results",
        ),
        common_mistakes=(
            "Using 'Artistic' for product ads (distorted branding)",
            "Not matching preset to product category",
        ),
        estimated_minutes=2,
    ),

    # Exercise 6: First Dry-Run Generation
    FlowExercise(
        exercise_id="basic_06_first_generation",
        title="First Dry-Run Generation — Complete Generation Workflow",
        skill_level="basic",
        goal="Practice the complete single-generation workflow: tab → prompt → aspect → style → (simulated) generate.",
        description=(
            "Execute a complete generation workflow for a fictional product. "
            "Navigate to the right tab, type a structured prompt, set aspect ratio, "
            "choose style, check credits, verify everything. THEN — simulate the Generate click. "
            "In dry-run mode: place cursor over Generate but DO NOT click."
        ),
        preconditions=("On Text-to-Video tab", "Credits checked",),
        steps=(
            _act("nav_text_tab", "Navigate to Text-to-Video", "Start on correct tab",
                 "text_to_video_tab", "navigate", "top_nav"),
            _act("type_full_prompt", "Type complete structured prompt", "PRODUCT + CAMERA + LIGHTING + MOTION + ATMOSPHERE",
                 "prompt_input_field", "type", "prompt_input",
                 payload="Premium wireless earbuds, floating above dark reflective surface, "
                         "soft rim lighting, slow orbit, premium commercial aesthetic"),
            _act("set_ratio", "Set 9:16 for Reels", "Platform-appropriate ratio",
                 "aspect_ratio_selector", "select", "aspect_ratio", payload="9:16"),
            _act("set_style", "Set Cinematic style", "Premium product aesthetic",
                 "style_presets", "select", "style_preset", payload="Cinematic"),
            _act("final_verify", "Final verification checklist", "Prompt? Ratio? Style? Credits?",
                 "generate_button", "navigate", "bottom_right"),
            _act("simulate_generate", "SIMULATE Generate (DO NOT CLICK)", "Hover over Generate, verify all checks, then move cursor away",
                 "generate_button", "navigate", "bottom_right"),
        ),
        expected_outcome="Agent completes a full pre-generation checklist without accidentally generating.",
        success_criteria=(
            "All 4 pre-generation checks passed (prompt, ratio, style, credits)",
            "Generate button was NOT clicked",
            "Agent can describe the complete workflow from memory",
        ),
        tips=(
            "Make this a mental habit: CHECK → PROMPT → RATIO → STYLE → CREDITS → (then) GENERATE",
            "Every generation starts with credit check — no exceptions",
        ),
        common_mistakes=(
            "Skipping the credit check step",
            "Generating before setting aspect ratio",
        ),
        requires_credits=False,
        estimated_minutes=4,
    ),
)

# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 2 — INTERMEDIATE (6 exercises)
# Goal: Extend, export, and multi-generation workflows.
# ═══════════════════════════════════════════════════════════════════════════════

_INTERMEDIATE_EXERCISES: tuple[FlowExercise, ...] = (

    # Exercise 7: Extend Mode Basics
    FlowExercise(
        exercise_id="inter_07_extend_mode",
        title="Extend Mode — Lengthen Generated Clips",
        skill_level="intermediate",
        goal="Learn how to use Flow's Extend feature to add 2-4 seconds to generated videos.",
        description=(
            "Extend Mode adds time to the end of a generated clip. "
            "Each extension costs 1 credit. Practice the decision-making process: "
            "WHEN to extend vs. WHEN to generate a new clip.\n"
            "Rule: extend when the shot is good but too short. Regenerate when the shot is wrong."
        ),
        preconditions=(
            "A generated video exists (simulated)",
            "Video preview is visible",
        ),
        steps=(
            _act("review_clip", "Review generated clip", "Watch the clip and assess: good content but too short?",
                 "generation_history", "navigate", "bottom_panel"),
            _act("locate_extend", "Locate Extend button", "Find Extend in video preview toolbar",
                 "extend_button", "navigate", "video_preview"),
            _act("decide_extend", "Decision: Extend vs Regenerate", "If clip quality is good → Extend. If bad → new generation.",
                 "extend_button", "navigate", "video_preview"),
            _act("simulate_extend", "SIMULATE Extend (DO NOT CLICK)", "Hover over Extend, verify decision, then move away",
                 "extend_button", "navigate", "video_preview"),
        ),
        expected_outcome="Agent understands when to extend vs. regenerate, and locates the Extend button.",
        success_criteria=(
            "Extend button located in video preview toolbar",
            "Agent can articulate extend vs. regenerate decision criteria",
            "Understood: each extension = 1 credit",
        ),
        tips=(
            "Extend: clip is GOOD but SHORT",
            "Regenerate: clip is WRONG (composition, lighting, motion)",
            "Maximum 2 extensions per clip — drift increases after that",
        ),
        common_mistakes=(
            "Extending a clip with poor composition (amplifies the problem)",
            "Extending more than 2 times (severe visual drift)",
        ),
        requires_credits=False,
        estimated_minutes=3,
    ),

    # Exercise 8: Frame Export Protocol
    FlowExercise(
        exercise_id="inter_08_frame_export",
        title="Frame Export Protocol — Build a Frame Library",
        skill_level="intermediate",
        goal="Learn to export key frames from generated videos for continuity workflows.",
        description=(
            "The Frame Export button saves the current frame as a still image. "
            "This is CRITICAL for multi-clip continuity: you export the last frame "
            "of clip 1, then use it as the starting image for clip 2 via Image-to-Video. "
            "Learn: when to export, which frames to export, and how to organize them."
        ),
        preconditions=(
            "A generated video exists (simulated)",
            "Video preview is scrolled to end frame",
        ),
        steps=(
            _act("scrub_to_end", "Scrub to last frame", "Navigate video timeline to the very end",
                 "generation_history", "navigate", "video_preview"),
            _act("pause_end_frame", "Pause on end frame", "Stop playback at exact end frame",
                 "generation_history", "click", "video_timeline"),
            _act("locate_export", "Locate Frame Export button", "Find Export Frame in preview toolbar",
                 "frame_export_button", "navigate", "video_preview"),
            _act("simulate_export", "SIMULATE Export Frame (DO NOT CLICK)", "Hover over Export Frame, verify frame is clean, then move away",
                 "frame_export_button", "navigate", "video_preview"),
            _act("plan_organization", "Plan frame file naming", "Naming convention: {product}_{style}_{shot_number}_endframe.png",
                 "frame_export_button", "navigate", "video_preview"),
        ),
        expected_outcome="Agent understands the end-frame export workflow for clip-to-clip continuity.",
        success_criteria=(
            "Frame Export button located",
            "End frame scrubbing technique understood",
            "File naming convention established",
            "Agent knows: export end frames, not middle frames",
        ),
        tips=(
            "Export END frames (last frame) for continuity — they're the most stable",
            "Never export frames with motion blur — useless as reference",
            "Build a folder: frames/{product}/{style}/ for organization",
        ),
        common_mistakes=(
            "Exporting mid-clip frames (bad as continuity reference)",
            "Forgetting to pause before export (blurry exports)",
        ),
        requires_credits=False,
        estimated_minutes=3,
    ),

    # Exercise 9: Image-to-Video Workflow
    FlowExercise(
        exercise_id="inter_09_image_to_video",
        title="Image-to-Video — From Reference to Generation",
        skill_level="intermediate",
        goal="Learn the Image-to-Video workflow: upload reference image, add prompt, generate anchored video.",
        description=(
            "Image-to-Video uses a reference image as the starting point. "
            "This is the ANCHOR for multi-clip continuity: export end frame of clip 1, "
            "use it as reference for clip 2. Practice the upload + prompt workflow."
        ),
        preconditions=(
            "An end frame image exists from Frame Export exercise",
            "On Image-to-Video tab",
        ),
        steps=(
            _act("nav_image_tab", "Navigate to Image-to-Video tab", "Switch to image-based generation mode",
                 "image_to_video_tab", "navigate", "top_nav"),
            _act("locate_upload", "Locate image upload zone", "Find the upload/select image area",
                 "image_to_video_tab", "navigate", "center_panel"),
            _act("simulate_upload", "SIMULATE Upload reference image", "Pretend to upload end_frame.png",
                 "image_to_video_tab", "click", "upload_zone"),
            _act("type_motion_prompt", "Type motion prompt only", "Only describe camera motion (product already in image)",
                 "prompt_input_field", "type", "prompt_input",
                 payload="Slow push-in camera movement, soft rim light intensifies, premium commercial"),
            _act("verify_match", "Verify prompt matches reference", "Prompt lighting must match image lighting",
                 "image_to_video_tab", "navigate", "center_panel"),
        ),
        expected_outcome="Agent can execute image-to-video workflow for clip-to-clip continuity.",
        success_criteria=(
            "Image-to-Video tab navigated",
            "Upload zone identified",
            "Prompt describes MOTION only (product is in reference)",
            "Lighting in prompt matches lighting in reference image",
        ),
        tips=(
            "Image-to-Video prompt: describe MOTION and minor LIGHTING changes ONLY",
            "Don't re-describe the product — it's already in the reference image",
            "Clean product-on-dark-background photos work best",
        ),
        common_mistakes=(
            "Re-describing the product in the prompt (redundant, confuses Flow)",
            "Mismatched lighting between reference and prompt",
        ),
        requires_credits=False,
        estimated_minutes=3,
    ),

    # Exercise 10: Motion Intensity Calibration
    FlowExercise(
        exercise_id="inter_10_motion_intensity",
        title="Motion Intensity Calibration — Speed Meets Intent",
        skill_level="intermediate",
        goal="Learn to match motion intensity to shot intent: low for luxury, medium for lifestyle, high for kinetic.",
        description=(
            "Flow's Motion Intensity slider controls camera movement speed. "
            "Practice matching intensity to the shot's emotional goal: "
            "low = slow, luxurious, premium. medium = natural, lifestyle. "
            "high = energetic, kinetic, montage."
        ),
        preconditions=("On Text-to-Video tab", "Structured prompt written",),
        steps=(
            _act("locate_slider", "Locate Motion Intensity slider", "Find in right panel > Camera section",
                 "motion_intensity_slider", "navigate", "right_panel"),
            _act("select_low", "Select Low for luxury shot", "Slow, deliberate camera — premium feel",
                 "motion_intensity_slider", "select", "motion_intensity", payload="low"),
            _act("select_medium", "Select Medium for lifestyle shot", "Natural, human-paced movement",
                 "motion_intensity_slider", "select", "motion_intensity", payload="medium"),
            _act("select_high", "Select High for kinetic montage", "Fast, energetic camera — hype content",
                 "motion_intensity_slider", "select", "motion_intensity", payload="high"),
            _act("verify_match", "Verify: intensity matches prompt motion keyword", "Low + slow orbit = consistent. High + slow orbit = contradictory.",
                 "motion_intensity_slider", "navigate", "right_panel"),
        ),
        expected_outcome="Agent matches motion intensity to shot intent without contradictions.",
        success_criteria=(
            "Low → luxury, macro, hero shots",
            "Medium → lifestyle, unboxing, comparison",
            "High → kinetic, montage, social hype",
            "Slider setting matches prompt motion keyword",
        ),
        tips=(
            "Slider and prompt motion keyword MUST agree — contradiction confuses Flow",
            "Low + orbit = cinematic product reveal",
            "High + whip pan = social media hype clip",
        ),
        common_mistakes=(
            "Setting High intensity while prompt says 'slow orbit'",
            "Not adjusting intensity between different shots in a storyboard",
        ),
        estimated_minutes=2,
    ),

    # Exercise 11: History Search & Reuse
    FlowExercise(
        exercise_id="inter_11_history_search",
        title="History Search — Find & Reuse Past Generations",
        skill_level="intermediate",
        goal="Learn to search Flow's generation history and reuse successful prompts.",
        description=(
            "Flow's Generation History stores past prompts and results. "
            "Practice: scroll through history, find a past successful generation, "
            "note its prompt structure, and plan how to reuse the pattern "
            "(not the exact prompt) for a new product."
        ),
        preconditions=("At least 3 past generations (simulated)",),
        steps=(
            _act("open_history", "Open Generation History panel", "Scroll to bottom or sidebar",
                 "generation_history", "navigate", "bottom_panel"),
            _act("scan_history", "Scan past generations", "Look for: highest quality results, note their prompt patterns",
                 "generation_history", "navigate", "bottom_panel"),
            _act("extract_pattern", "Extract prompt pattern from best result", "Don't copy — extract structure: CAMERA + LIGHTING + PACING",
                 "generation_history", "navigate", "bottom_panel"),
            _act("plan_reuse", "Plan pattern reuse for new product", "Same structure, different product description",
                 "generation_history", "navigate", "bottom_panel"),
        ),
        expected_outcome="Agent can extract successful prompt patterns from history without copying content.",
        success_criteria=(
            "History panel found and navigated",
            "Best result identified",
            "Pattern extracted (not copied)",
            "New prompt planned using same pattern",
        ),
        tips=(
            "Look for patterns: 'X camera + Y lighting + Z pacing' structure",
            "Tag your best generations mentally: 'golden_orbit_lighting'",
            "History may be limited — document externally",
        ),
        common_mistakes=(
            "Copying the exact prompt (won't work for different products)",
            "Ignoring failed generations (they teach what NOT to do)",
        ),
        estimated_minutes=3,
    ),

    # Exercise 12: Multi-Clip Continuity Planning
    FlowExercise(
        exercise_id="inter_12_continuity_planning",
        title="Multi-Clip Continuity — Plan Before Generate",
        skill_level="intermediate",
        goal="Learn to plan a 2-clip sequence with continuity: clip 1 → export end frame → clip 2 from end frame.",
        description=(
            "Multi-clip sequences require planning BEFORE any generation. "
            "Plan a 2-shot sequence: SHOT 1 (hero, orbit, dark matte) → "
            "export end frame → SHOT 2 (push-in, same lighting, from end frame). "
            "All dry-run: no actual generation."
        ),
        preconditions=("Text-to-Video tab open", "Frame export workflow understood",),
        steps=(
            _act("plan_shot1", "Plan Shot 1", "Hero shot, orbit camera, dark matte lighting, 9:16",
                 "text_to_video_tab", "navigate", "top_nav"),
            _act("plan_transition", "Plan transition point", "Shot 1 end frame = Shot 2 reference image",
                 "frame_export_button", "navigate", "video_preview"),
            _act("plan_shot2", "Plan Shot 2", "Push-in camera, SAME dark matte lighting, from exported frame",
                 "image_to_video_tab", "navigate", "top_nav"),
            _act("verify_continuity", "Verify continuity: lighting matches?", "Shot 1 dark_matte == Shot 2 dark_matte? YES → proceed",
                 "text_to_video_tab", "navigate", "center_panel"),
            _act("document_plan", "Document the 2-shot plan", "Write down: Shot 1 prompt, transition, Shot 2 prompt",
                 "text_to_video_tab", "type", "prompt_input"),
        ),
        expected_outcome="Agent has a written 2-shot plan with matched lighting and clear transition.",
        success_criteria=(
            "Shot 1 planned with full prompt structure",
            "Transition method defined (end frame → Image-to-Video)",
            "Shot 2 planned with matching lighting",
            "Entire plan documented (can be executed later)",
        ),
        tips=(
            "Lighting MUST match across shots for continuity",
            "Plan all shots BEFORE generating any — prevents wasted credits",
            "Keep first multi-clip to 2 shots — master that before scaling",
        ),
        common_mistakes=(
            "Generating Shot 1 without planning Shot 2 (then stuck)",
            "Different lighting between shots (jarring cut)",
        ),
        requires_credits=False,
        estimated_minutes=5,
    ),
)

# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 3 — ADVANCED (6 exercises)
# Multi-scene storyboards, ingredient combination, credit optimization.
# ═══════════════════════════════════════════════════════════════════════════════

_ADVANCED_EXERCISES: tuple[FlowExercise, ...] = (

    # Exercise 13: Scene Builder — 3-Shot Storyboard
    FlowExercise(
        exercise_id="adv_13_scene_builder_3shot",
        title="Scene Builder — Craft a 3-Shot Storyboard",
        skill_level="advanced",
        goal="Learn to use Flow's Scene Builder for multi-scene video planning.",
        description=(
            "Scene Builder lets you plan multiple scenes in a storyboard grid. "
            "Each scene slot has its own prompt, camera, and style settings. "
            "Plan a 3-shot product ad: HERO → MACRO DETAIL → CTA ENDING.\n"
            "Each shot has a different purpose, camera, and pacing."
        ),
        preconditions=("Scene Builder tab open", "3-shot plan outlined",),
        steps=(
            _act("open_scene_builder", "Open Scene Builder panel", "Navigate to multi-scene view",
                 "scene_builder_panel", "navigate", "top_nav"),
            _act("plan_scene1", "Plan Scene 1: Hero Shot", "Product reveal, orbit, dark matte, 3s",
                 "scene_builder_panel", "type", "scene_1",
                 payload="Matte black electric trimmer, floating on obsidian, dark luxury lighting, slow orbit"),
            _act("plan_scene2", "Plan Scene 2: Macro Detail", "Close-up of blade texture, push-in, soft rim, 2s",
                 "scene_builder_panel", "type", "scene_2",
                 payload="Extreme close-up blade detail, macro lens, soft rim light, slow push-in"),
            _act("plan_scene3", "Plan Scene 3: CTA Ending", "Product + text overlay space, hero shot return, 3s",
                 "scene_builder_panel", "type", "scene_3",
                 payload="Product centered, logo reveal space, premium commercial, slow dolly out"),
            _act("add_transitions", "Add transitions between scenes", "Scene 1→2: dissolve. Scene 2→3: hard cut.",
                 "scene_builder_panel", "select", "transition"),
            _act("verify_rhythm", "Verify overall rhythm", "Slow → Slow → Slow (consistent luxury pacing)",
                 "scene_builder_panel", "navigate", "bottom_panel"),
        ),
        expected_outcome="Agent builds a coherent 3-scene storyboard with transitions and consistent pacing.",
        success_criteria=(
            "All 3 scenes have prompts",
            "Transitions specified (dissolve + hard cut)",
            "Pacing is consistent across scenes",
            "CTA scene has space for text overlay",
        ),
        tips=(
            "Each scene = one idea. Don't try to do everything in one scene.",
            "Transitions MATTER — dissolve for smooth, hard cut for contrast",
            "Leave dead space in CTA scene for text/logo overlay",
        ),
        common_mistakes=(
            "All 3 scenes use the same camera (boring)",
            "No transition planning (jarring cuts)",
            "Forgetting the CTA scene (incomplete ad)",
        ),
        requires_credits=False,
        estimated_minutes=6,
    ),

    # Exercise 14: Ingredient Workflow
    FlowExercise(
        exercise_id="adv_14_ingredients",
        title="Ingredient Combination — Multi-Reference Generation",
        skill_level="advanced",
        goal="Learn to use Flow's Ingredients feature: upload multiple reference images for richer generation.",
        description=(
            "Ingredients lets you upload multiple reference images. "
            "Best practice: ONE product image + ONE style/mood reference. "
            "Practice selecting compatible ingredient pairs that don't conflict."
        ),
        preconditions=("Ingredients panel available", "Product image ready", "Style reference ready",),
        steps=(
            _act("open_ingredients", "Open Ingredients panel", "Locate side panel > Ingredients",
                 "ingredients_panel", "navigate", "side_panel"),
            _act("sim_upload_product", "SIMULATE Upload product image", "Clean product-on-white photo",
                 "ingredients_panel", "click", "upload_product"),
            _act("sim_upload_style", "SIMULATE Upload style reference", "Dark luxury mood board image",
                 "ingredients_panel", "click", "upload_style"),
            _act("verify_compatibility", "Verify ingredient compatibility", "Product lighting matches style reference? Both dark/neutral?",
                 "ingredients_panel", "navigate", "side_panel"),
            _act("simulate_generate_ing", "SIMULATE Generate with ingredients", "Hover over Generate, verify both ingredients loaded",
                 "generate_button", "navigate", "bottom_right"),
        ),
        expected_outcome="Agent can pair compatible ingredients for richer, more controlled generation.",
        success_criteria=(
            "Ingredients panel located",
            "Product image + style reference uploaded",
            "Compatibility verified (matching tones)",
            "Understands: max 2-3 ingredients for best results",
        ),
        tips=(
            "1 product + 1 style reference = optimal balance",
            "Too many ingredients = confused generation",
            "Ingredients must share lighting tone (both dark, both bright, etc.)",
        ),
        common_mistakes=(
            "Uploading 4+ ingredients (dilutes generation quality)",
            "Mixing bright and dark reference images (conflicting signals)",
        ),
        requires_credits=False,
        estimated_minutes=4,
    ),

    # Exercise 15: Credit Budget Orchestration
    FlowExercise(
        exercise_id="adv_15_credit_budget",
        title="Credit Budget Orchestration — Full Ad Within 8 Credits",
        skill_level="advanced",
        goal="Learn to plan a complete video ad within Flow's daily credit budget (8 credits).",
        description=(
            "You have 8 daily credits. Plan a complete 3-shot product ad: "
            "decide which shots use text-to-video (1 credit each), "
            "which use image-to-video from exports (1 credit each), "
            "whether to extend any shots (1 credit each). "
            "Goal: maximize visual quality within the budget."
        ),
        preconditions=("8 credits remaining (simulated)", "3-shot storyboard planned",),
        steps=(
            _act("estimate_shot1", "Estimate Shot 1 cost", "Hero shot: text-to-video = 1 credit",
                 "credit_display", "navigate", "top_right"),
            _act("estimate_shot2", "Estimate Shot 2 cost", "Macro detail: image-to-video from Shot 1 end frame = 1 credit",
                 "credit_display", "navigate", "top_right"),
            _act("estimate_shot3", "Estimate Shot 3 cost", "CTA ending: image-to-video from Shot 2 end frame = 1 credit",
                 "credit_display", "navigate", "top_right"),
            _act("consider_extend", "Consider: extend Shot 1?", "Hero shot is most important — extend by 2s? +1 credit",
                 "extend_button", "navigate", "video_preview"),
            _act("finalize_budget", "Finalize budget", "Shot 1 (t2v) + Shot 2 (i2v) + Shot 3 (i2v) + extend Shot 1 = 4 credits. 4 remain.",
                 "credit_display", "navigate", "top_right"),
        ),
        expected_outcome="Agent produces a budget-optimized 3-shot plan using 4/8 credits with buffer.",
        success_criteria=(
            "All 3 shots costed",
            "Image-to-video used where possible (continuity bonus)",
            "Budget buffer maintained (50% unused = safe)",
            "Agent can explain every credit decision",
        ),
        tips=(
            "Image-to-video = same credit cost, better continuity",
            "Always leave 20-30% credit buffer for retries",
            "Text-to-video for Shot 1, image-to-video for continuity shots",
        ),
        common_mistakes=(
            "Using text-to-video for all shots (sacrifices continuity)",
            "No budget buffer (1 failed generation = incomplete ad)",
            "Extending every shot (credit drain)",
        ),
        requires_credits=False,
        estimated_minutes=5,
    ),

    # Exercise 16: Lighting Continuity Across Scenes
    FlowExercise(
        exercise_id="adv_16_lighting_continuity",
        title="Lighting Continuity — Match Light Across 4 Scenes",
        skill_level="advanced",
        goal="Learn to plan and verify consistent lighting across all scenes in a storyboard.",
        description=(
            "Lighting continuity is the #1 visual coherence factor. "
            "Plan a 4-shot sequence where ALL shots use the same lighting family. "
            "Verify: palette coherence, product spotlight consistency, shadow direction."
        ),
        preconditions=("4-shot storyboard template available",),
        steps=(
            _act("choose_family", "Choose lighting family", "Select: dark_matte (luxury), soft_rim (beauty), or high_key (ecommerce)",
                 "style_presets", "select", "style_preset", payload="Cinematic"),
            _act("scene1_light", "Scene 1: Set lighting", "dark_matte, product on reflective surface",
                 "scene_builder_panel", "type", "scene_1"),
            _act("scene2_light", "Scene 2: SAME lighting", "dark_matte — verify it matches Scene 1",
                 "scene_builder_panel", "type", "scene_2"),
            _act("scene3_light", "Scene 3: SAME lighting", "dark_matte — verify it matches",
                 "scene_builder_panel", "type", "scene_3"),
            _act("scene4_light", "Scene 4: SAME lighting", "dark_matte — final consistency check",
                 "scene_builder_panel", "type", "scene_4"),
            _act("verify_all", "Verify all 4 match", "palette = dark tones, shadow = same direction, product = consistent exposure",
                 "scene_builder_panel", "navigate", "bottom_panel"),
        ),
        expected_outcome="All 4 scenes share identical lighting family — no visual jumps.",
        success_criteria=(
            "Single lighting family chosen for entire sequence",
            "All 4 scenes use same lighting keyword in prompt",
            "No lighting contradictions detected",
            "Agent can explain WHY consistency matters",
        ),
        tips=(
            "Pick ONE lighting family per ad — dark_matte OR soft_rim, never both",
            "Write the lighting keyword first in each scene prompt for emphasis",
            "If unsure: dark matte + rim light = safe luxury look",
        ),
        common_mistakes=(
            "Scene 1 dark, Scene 2 bright (worst possible jump cut)",
            "Using 'natural lighting' in one scene and 'studio' in another",
        ),
        requires_credits=False,
        estimated_minutes=4,
    ),

    # Exercise 17: Download & Archive Protocol
    FlowExercise(
        exercise_id="adv_17_download_archive",
        title="Download & Archive — Save Generated Assets",
        skill_level="advanced",
        goal="Learn the complete asset preservation workflow: download video → name correctly → archive.",
        description=(
            "Generated videos are ephemeral in Flow. Establish a download + archive "
            "protocol: download immediately after successful generation, "
            "use consistent naming, store in organized folder structure."
        ),
        preconditions=("Generated video exists (simulated)",),
        steps=(
            _act("review_final", "Review final generation", "Watch full clip, verify quality",
                 "generation_history", "navigate", "bottom_panel"),
            _act("locate_download", "Locate Download button", "Find in video preview toolbar",
                 "download_button", "navigate", "video_preview"),
            _act("plan_filename", "Plan filename", "Format: {date}_{product}_{shot_number}_{style}.mp4",
                 "download_button", "navigate", "video_preview"),
            _act("simulate_download", "SIMULATE Download", "Hover over Download, verify filename plan",
                 "download_button", "navigate", "video_preview"),
            _act("plan_archive", "Plan archive structure", "videos/{product}/{date}/shot_1.mp4, shot_2.mp4, ...",
                 "download_button", "navigate", "video_preview"),
        ),
        expected_outcome="Agent has a documented archive protocol for all generated assets.",
        success_criteria=(
            "Download button located",
            "Naming convention established",
            "Folder structure planned",
            "Agent knows: download IMMEDIATELY (Flow history is not permanent)",
        ),
        tips=(
            "Download immediately — Flow's history may not persist indefinitely",
            "Back up to cloud + local: redundancy saves work",
            "Keep raw generations AND edited final versions separately",
        ),
        common_mistakes=(
            "Waiting days to download (history may be cleared)",
            "No naming convention (can't find assets later)",
        ),
        requires_credits=False,
        estimated_minutes=2,
    ),

    # Exercise 18: Full Ad Pipeline Simulation
    FlowExercise(
        exercise_id="adv_18_full_pipeline",
        title="Full Ad Pipeline — Plan, Generate, Export, Extend, Download",
        skill_level="advanced",
        goal="Orchestrate the complete cinematic ad pipeline from planning to archive — all dry-run.",
        description=(
            "End-to-end simulation of a full ad creation pipeline: "
            "plan storyboard → check credits → Shot 1 (text-to-video) → "
            "export end frame → Shot 2 (image-to-video) → extend Shot 2 → "
            "Shot 3 (image-to-video) → download all → archive. "
            "Every step mapped but no actual Flow calls."
        ),
        preconditions=("Flow open", "8 credits available (simulated)", "Storyboard planned",),
        steps=(
            _act("check_credits", "Check credits: 8 remaining", "Start every session here",
                 "credit_display", "navigate", "top_right"),
            _act("shot1_gen", "Shot 1: Text-to-Video (Hero, orbit, dark matte, 9:16)", "Simulate generation. 7 credits remain.",
                 "generate_button", "click", "generate", payload="SHOT 1 (simulated)"),
            _act("shot1_export", "Export Shot 1 end frame", "Save as end_frame_hero.png",
                 "frame_export_button", "export", "frame_export"),
            _act("shot2_gen", "Shot 2: Image-to-Video from end frame (Push-in, macro)", "Simulate generation. 6 credits remain.",
                 "generate_button", "click", "generate", payload="SHOT 2 (simulated)"),
            _act("shot2_extend", "Extend Shot 2 (+2s)", "Better macro detail. 5 credits remain.",
                 "extend_button", "extend", "clip_extend"),
            _act("shot2_export", "Export Shot 2 end frame", "Save as end_frame_macro.png",
                 "frame_export_button", "export", "frame_export"),
            _act("shot3_gen", "Shot 3: Image-to-Video from end frame (CTA, dolly out)", "Simulate generation. 4 credits remain.",
                 "generate_button", "click", "generate", payload="SHOT 3 (simulated)"),
            _act("download_all", "Download all 3 clips", "shot_1_hero.mp4, shot_2_macro.mp4, shot_3_cta.mp4",
                 "download_button", "download", "video_download"),
            _act("verify_budget", "Verify final budget: 4/8 used, 4 remain", "50% buffer — excellent",
                 "credit_display", "navigate", "top_right"),
        ),
        expected_outcome="Agent executes complete 3-shot pipeline with 50% credit buffer.",
        success_criteria=(
            "Credit check at start",
            "Shot 1: Text-to-Video + end frame export",
            "Shot 2: Image-to-Video + extend + export",
            "Shot 3: Image-to-Video",
            "All 3 clips downloaded",
            "4/8 credits used, 4 remain",
        ),
        tips=(
            "This is the MASTER workflow — practice until it's automatic",
            "Image-to-Video for shots 2+ saves credits AND improves continuity",
            "Extend only the best clips (macro shots benefit most from extra time)",
        ),
        common_mistakes=(
            "Forgetting to export end frames (can't do Image-to-Video for next shot)",
            "Using Text-to-Video for every shot (wastes continuity opportunity)",
        ),
        requires_credits=False,
        estimated_minutes=8,
    ),
)

# ═══════════════════════════════════════════════════════════════════════════════
# LEVEL 4 — EXPERT (6 exercises)
# Full cinematic orchestration, credit optimization, recovery workflows.
# ═══════════════════════════════════════════════════════════════════════════════

_EXPERT_EXERCISES: tuple[FlowExercise, ...] = (

    # Exercise 19: 5-Shot Cinematic Ad
    FlowExercise(
        exercise_id="expert_19_5shot_cinematic",
        title="5-Shot Cinematic Ad — Full Product Story",
        skill_level="expert",
        goal="Orchestrate a complete 5-shot cinematic product ad within 8 credits.",
        description=(
            "Design a 5-shot ad that tells a complete product story: "
            "HOOK → PROBLEM → SOLUTION → DETAILS → CALL TO ACTION. "
            "Use the budget: 1 text-to-video, 3 image-to-video, 1 extend. "
            "All lighting: dark_matte. All pacing: slow_dramatic."
        ),
        preconditions=("Flow open", "8 credits", "Product: fictional premium headphones",),
        steps=(
            _act("plan_story", "Plan story arc", "Hook (curiosity) → Problem (need) → Solution (product) → Details (quality) → CTA (buy)",
                 "scene_builder_panel", "navigate", "top_nav"),
            _act("shot1_hook", "Shot 1: HOOK — Text-to-Video", "Close-up dark surface, product slowly revealed, orbit",
                 "generate_button", "click", "generate", payload="SHOT 1 HOOK (t2v, 1 credit)"),
            _act("shot1_export", "Export Shot 1 end frame", "Reveal completion frame",
                 "frame_export_button", "export", "frame_export"),
            _act("shot2_problem", "Shot 2: PROBLEM — Image-to-Video", "Before scenario, no product, warm→cold transition",
                 "generate_button", "click", "generate", payload="SHOT 2 PROBLEM (i2v, 1 credit)"),
            _act("shot2_export", "Export Shot 2 end frame", "Transition point",
                 "frame_export_button", "export", "frame_export"),
            _act("shot3_solution", "Shot 3: SOLUTION — Image-to-Video", "Product enters frame, hero lighting",
                 "generate_button", "click", "generate", payload="SHOT 3 SOLUTION (i2v, 1 credit)"),
            _act("shot3_extend", "Extend Shot 3 (+2s)", "Give product more screen time. 1 credit.",
                 "extend_button", "extend", "clip_extend"),
            _act("shot3_export", "Export Shot 3 end frame", "Hero pose",
                 "frame_export_button", "export", "frame_export"),
            _act("shot4_details", "Shot 4: DETAILS — Image-to-Video", "Macro close-up, texture, quality",
                 "generate_button", "click", "generate", payload="SHOT 4 DETAILS (i2v, 1 credit)"),
            _act("shot4_export", "Export Shot 4 end frame", "Product detail",
                 "frame_export_button", "export", "frame_export"),
            _act("shot5_cta", "Shot 5: CTA — Image-to-Video", "Product center, logo overlay space, dolly out",
                 "generate_button", "click", "generate", payload="SHOT 5 CTA (i2v, 1 credit)"),
            _act("verify_budget", "Verify: 6/8 credits used", "2 credits remain — safe buffer",
                 "credit_display", "navigate", "top_right"),
        ),
        expected_outcome="Agent designs and simulates a story-driven 5-shot ad within budget.",
        success_criteria=(
            "Complete story arc: Hook → Problem → Solution → Details → CTA",
            "5 shots, 6 credits (1 t2v + 3 i2v + 1 extend + 1 i2v)",
            "2 credits remaining (25% buffer)",
            "Consistent dark_matte lighting across all 5 shots",
        ),
        tips=(
            "Story arc keeps viewers watching — don't skip the problem phase",
            "Hero shot (Shot 3) gets the extend — it's the most important",
            "CTA must have dead space for text/logo overlay",
        ),
        common_mistakes=(
            "Rushing the story (no problem phase = no emotional hook)",
            "All shots same camera (boring despite good story)",
        ),
        requires_credits=False,
        estimated_minutes=10,
    ),

    # Exercise 20: Edge Case — Credit Exhaustion Recovery
    FlowExercise(
        exercise_id="expert_20_credit_recovery",
        title="Credit Exhaustion Recovery — What To Do When Out of Credits",
        skill_level="expert",
        goal="Learn how to handle running out of credits mid-project without losing work.",
        description=(
            "You have 2 credits and need 4 shots. Plan a recovery strategy: "
            "which 2 shots to generate now, which to defer, "
            "how to save partial work, and how to resume tomorrow."
        ),
        preconditions=("2 credits remaining", "4-shot plan exists",),
        steps=(
            _act("assess_budget", "Assess: 2 credits, 4 shots needed", "Cannot generate all 4 today",
                 "credit_display", "navigate", "top_right"),
            _act("prioritize", "Prioritize: generate 2 most critical shots", "Shot 1 (Hero) + Shot 2 (Detail). Defer Shot 3+4.",
                 "credit_display", "navigate", "top_right"),
            _act("gen_shot1", "Generate Shot 1: Hero (text-to-video)", "1 credit. Most important shot.",
                 "generate_button", "click", "generate", payload="SHOT 1 HERO (simulated)"),
            _act("export_shot1", "Export Shot 1 end frame IMMEDIATELY", "Save before credits hit zero",
                 "frame_export_button", "export", "frame_export"),
            _act("gen_shot2", "Generate Shot 2: Detail (image-to-video from Shot 1)", "1 credit. Last generation today.",
                 "generate_button", "click", "generate", payload="SHOT 2 DETAIL (simulated)"),
            _act("export_shot2", "Export Shot 2 end frame", "Save both end frames for tomorrow",
                 "frame_export_button", "export", "frame_export"),
            _act("document_state", "Document current state for resume", "Write: Shot 3 starts from Shot 2 end frame, dark matte, push-in",
                 "text_to_video_tab", "type", "prompt_input"),
        ),
        expected_outcome="Agent preserves partial work and creates a resume plan for the next day.",
        success_criteria=(
            "2 most critical shots generated",
            "Both end frames exported",
            "Resume plan documented (which frames, which prompts)",
            "Agent accepts credit limits without frustration",
        ),
        tips=(
            "Always export end frames BEFORE credits hit zero",
            "Document prompt + settings for deferred shots",
            "Prioritize: Hero shot > Detail shot > CTA > Lifestyle",
        ),
        common_mistakes=(
            "Trying to squeeze all 4 into 2 credits (impossible)",
            "Not exporting before credits exhausted (work lost)",
        ),
        requires_credits=False,
        estimated_minutes=5,
    ),

    # Exercise 21: Platform Variant Workflow
    FlowExercise(
        exercise_id="expert_21_platform_variants",
        title="Platform Variants — One Product, Three Ratios",
        skill_level="expert",
        goal="Learn to create platform-specific variants of the same product video.",
        description=(
            "Same product needs different versions: 9:16 for TikTok, 1:1 for Instagram Feed, "
            "16:9 for YouTube. Plan a workflow that generates ONE hero shot at 9:16, "
            "then creates variants by changing aspect ratio (Frame Continuation or new generation). "
            "Note: Flow may not support ratio changes on existing clips — plan accordingly."
        ),
        preconditions=("Hero shot generated at 9:16 (simulated)", "3 credits remaining",),
        steps=(
            _act("review_hero", "Review existing 9:16 hero shot", "Confirm it's the master version",
                 "generation_history", "navigate", "bottom_panel"),
            _act("plan_1_1", "Plan 1:1 variant for Feed", "May need new text-to-video at 1:1 ratio",
                 "aspect_ratio_selector", "select", "aspect_ratio", payload="1:1"),
            _act("plan_16_9", "Plan 16:9 variant for YouTube", "New generation at 16:9, same prompt structure",
                 "aspect_ratio_selector", "select", "aspect_ratio", payload="16:9"),
            _act("cost_analysis", "Cost analysis: 3 variants = 3 credits", "9:16 (done) + 1:1 (1 credit) + 16:9 (1 credit) = 2 new credits",
                 "credit_display", "navigate", "top_right"),
            _act("decide_priority", "Decide: which platform is priority?", "TikTok primary → 9:16 master. Feed secondary → 1:1. YouTube optional → skip if budget tight.",
                 "credit_display", "navigate", "top_right"),
        ),
        expected_outcome="Agent has a platform matrix strategy with budget-conscious variant planning.",
        success_criteria=(
            "Master shot identified (9:16)",
            "Variant cost calculated (2 additional credits)",
            "Priority ranking: TikTok > Feed > YouTube",
            "Agent knows: ratio cannot be changed on existing clips",
        ),
        tips=(
            "9:16 master first — converts poorly to other ratios, but it's the most important platform",
            "1:1 can crop from 9:16 externally (save credits)",
            "YouTube 16:9 is lowest priority for most e-commerce brands",
        ),
        common_mistakes=(
            "Assuming one clip works for all platforms (crop disaster)",
            "Generating all 3 variants before validating master shot",
        ),
        requires_credits=False,
        estimated_minutes=4,
    ),

    # Exercise 22: Prompt Iteration Protocol
    FlowExercise(
        exercise_id="expert_22_prompt_iteration",
        title="Prompt Iteration Protocol — A/B Test Prompts Systematically",
        skill_level="expert",
        goal="Learn to iterate prompts systematically: change ONE variable at a time, compare results, converge.",
        description=(
            "Random prompt changes waste credits. Systematic iteration: "
            "generate V1 (baseline), V2 (change camera only), V3 (change lighting only). "
            "Compare V1→V2→V3 to isolate which variable matters most. "
            "All dry-run: plan the A/B test, don't generate."
        ),
        preconditions=("Baseline prompt written", "3 credits available (simulated)",),
        steps=(
            _act("write_baseline", "Write V1 baseline", "Product + orbit + dark_matte + slow + premium",
                 "prompt_input_field", "type", "prompt_input",
                 payload="Wireless earbuds, orbit, dark matte, slow, premium"),
            _act("plan_v2", "Plan V2: Change CAMERA only", "Product + dolly_in + dark_matte + slow + premium",
                 "prompt_input_field", "type", "prompt_input",
                 payload="Wireless earbuds, dolly_in, dark matte, slow, premium"),
            _act("plan_v3", "Plan V3: Change LIGHTING only", "Product + orbit + soft_rim + slow + premium",
                 "prompt_input_field", "type", "prompt_input",
                 payload="Wireless earbuds, orbit, soft rim, slow, premium"),
            _act("define_comparison", "Define comparison criteria", "Which has: better product visibility? better mood? more cinematic feel?",
                 "prompt_input_field", "navigate", "center_panel"),
            _act("document_method", "Document the A/B/C method", "V1 = baseline. V2 = camera test. V3 = lighting test. Only ONE variable changes per version.",
                 "prompt_input_field", "navigate", "center_panel"),
        ),
        expected_outcome="Agent has a documented A/B testing protocol for prompt optimization.",
        success_criteria=(
            "V1 baseline defined",
            "V2 changes ONLY camera",
            "V3 changes ONLY lighting",
            "Comparison criteria defined",
            "Agent understands: ONE variable at a time",
        ),
        tips=(
            "ONE variable per test — changing camera AND lighting = can't attribute results",
            "Run baseline twice sometimes — Flow has inherent randomness",
            "Document which variable matters most for your product category",
        ),
        common_mistakes=(
            "Changing multiple variables (impossible to attribute improvement)",
            "Not defining success criteria BEFORE generating (post-hoc rationalization)",
        ),
        requires_credits=False,
        estimated_minutes=5,
    ),

    # Exercise 23: Flow Failure Recovery
    FlowExercise(
        exercise_id="expert_23_failure_recovery",
        title="Flow Failure Recovery — When Generation Goes Wrong",
        skill_level="expert",
        goal="Learn to diagnose and recover from common Flow generation failures.",
        description=(
            "Flow generations can fail: wrong product, distorted anatomy, bad composition, "
            "completely off-topic. Practice diagnosing failure types and choosing the right "
            "recovery: regenerate (same prompt, different seed), modify prompt, or switch mode."
        ),
        preconditions=("Failed generation (simulated)", "Type: product missing from frame",),
        steps=(
            _act("diagnose", "Diagnose failure type", "Product missing from frame → camera too far or wrong framing",
                 "generation_history", "navigate", "bottom_panel"),
            _act("classify", "Classify: which category?", "Wrong framing = prompt issue, not mode issue",
                 "generation_history", "navigate", "bottom_panel"),
            _act("choose_recovery", "Choose recovery strategy", "Framing issue → modify prompt: add 'close-up' or 'centered'",
                 "prompt_input_field", "type", "prompt_input"),
            _act("decide_regenerate", "Decision: regenerate vs. switch mode", "Wrong framing → regenerate with fixed prompt (not mode switch)",
                 "generate_button", "navigate", "bottom_right"),
            _act("document_learn", "Document what was learned", "Add 'center product framing' to prompt template for this product category",
                 "prompt_input_field", "navigate", "center_panel"),
        ),
        expected_outcome="Agent can diagnose generation failures and apply targeted fixes.",
        success_criteria=(
            "Failure correctly diagnosed (framing issue)",
            "Recovery strategy appropriate (prompt fix, not mode switch)",
            "Learning documented (template improved)",
            "Agent knows: some failures are Flow randomness — retry once",
        ),
        tips=(
            "Product missing → add framing keywords: 'centered', 'close-up', 'foreground'",
            "Distorted product → simplify prompt, remove conflicting keywords",
            "Wrong style → check style preset didn't override prompt",
            "Retry once with same prompt (Flow randomness). If same failure → change prompt.",
        ),
        common_mistakes=(
            "Switching modes when prompt fix would work (mode switch = different result type)",
            "Not learning from failures (same mistake repeated)",
        ),
        requires_credits=False,
        estimated_minutes=4,
    ),

    # Exercise 24: Full Cinematic Director Simulation
    FlowExercise(
        exercise_id="expert_24_director_simulation",
        title="Full Cinematic Director — Complete Ad Campaign Orchestration",
        skill_level="expert",
        goal="Orchestrate a complete 3-platform ad campaign: 5-shot TikTok, 3-shot Feed, 2-shot YouTube Short.",
        description=(
            "You are the cinematic director. Plan and simulate a complete campaign: "
            "10 total shots across 3 platforms, within 24 credits (3-day budget). "
            "Prioritize: TikTok 5-shot (day 1, 6 credits), Feed 3-shot (day 2, 4 credits), "
            "YouTube 2-shot (day 3, 2 credits). Total: 12 credits, 12 buffer."
        ),
        preconditions=("Campaign brief: premium headphones launch", "3-day timeline",),
        steps=(
            _act("plan_day1", "Day 1: TikTok 5-shot cinematic ad", "6 credits: 1 t2v + 3 i2v + 1 extend + 1 i2v CTA",
                 "scene_builder_panel", "navigate", "top_nav"),
            _act("simulate_day1", "SIMULATE Day 1 workflow", "All 5 shots, all exports, all downloads. 6 credits used.",
                 "generate_button", "click", "generate", payload="DAY 1 COMPLETE (simulated)"),
            _act("plan_day2", "Day 2: Instagram Feed 3-shot ad", "4 credits: 1 t2v + 2 i2v. Square format. Shorter pacing.",
                 "scene_builder_panel", "navigate", "top_nav"),
            _act("simulate_day2", "SIMULATE Day 2 workflow", "All 3 shots, square ratio, faster pacing. 10 credits total used.",
                 "generate_button", "click", "generate", payload="DAY 2 COMPLETE (simulated)"),
            _act("plan_day3", "Day 3: YouTube Short 2-shot ad", "2 credits: 1 i2v (from best TikTok shot end frame) + 1 i2v CTA",
                 "scene_builder_panel", "navigate", "top_nav"),
            _act("simulate_day3", "SIMULATE Day 3 workflow", "Repurpose TikTok end frame for YouTube. 12 credits total. 12 remain.",
                 "generate_button", "click", "generate", payload="DAY 3 COMPLETE (simulated)"),
            _act("final_report", "Campaign report", "12/24 credits used. 10 shots across 3 platforms. All assets archived.",
                 "credit_display", "navigate", "top_right"),
        ),
        expected_outcome="Agent orchestrates a multi-platform, multi-day campaign within budget with repurposed assets.",
        success_criteria=(
            "Day 1: 5-shot TikTok (6 credits)",
            "Day 2: 3-shot Feed (4 credits)",
            "Day 3: 2-shot YouTube (2 credits, repurposed)",
            "12/24 credits used (50% buffer across 3 days)",
            "End frames reused across platforms (continuity maximized)",
        ),
        tips=(
            "Repurpose end frames across platforms — saves credits AND maintains brand consistency",
            "Day 1 = most important platform. Day 2+3 = variants + repurposing",
            "This is the final exam — master it and you're a Flow director",
        ),
        common_mistakes=(
            "Starting new from scratch each day (waste — repurpose end frames)",
            "No cross-platform consistency (different lighting, different product framing)",
        ),
        requires_credits=False,
        estimated_minutes=12,
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Catalog — All 24 exercises
# ═══════════════════════════════════════════════════════════════════════════════

_ALL_EXERCISES: tuple[FlowExercise, ...] = (
    *_BASIC_EXERCISES,
    *_INTERMEDIATE_EXERCISES,
    *_ADVANCED_EXERCISES,
    *_EXPERT_EXERCISES,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_exercises() -> tuple[FlowExercise, ...]:
    """Return all 24 training exercises."""
    return _ALL_EXERCISES


def get_exercise(exercise_id: str) -> FlowExercise | None:
    """Look up an exercise by ID."""
    for e in _ALL_EXERCISES:
        if e.exercise_id == exercise_id:
            return e
    return None


def get_exercises_by_level(level: str) -> tuple[FlowExercise, ...]:
    """Get exercises for a specific skill level."""
    return tuple(e for e in _ALL_EXERCISES if e.skill_level == level)


def get_exercise_count() -> int:
    """Total number of exercises."""
    return len(_ALL_EXERCISES)


def get_curriculum() -> dict:
    """Return the full curriculum summary: exercises per level."""
    return {
        level: {
            "count": len(get_exercises_by_level(level)),
            "exercises": [
                {"id": e.exercise_id, "title": e.title, "minutes": e.estimated_minutes}
                for e in get_exercises_by_level(level)
            ],
        }
        for level in ("basic", "intermediate", "advanced", "expert")
    }
