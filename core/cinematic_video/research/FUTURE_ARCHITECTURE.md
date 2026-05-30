# FUTURE INTEGRATION ARCHITECTURE — Cinematic Video Pipeline

> **STATUS:** Documentation only. **DO NOT IMPLEMENT** until cinematographic training is validated.
>
> The agent must first LEARN → EXPERIMENT → OPTIMIZE → only then AUTOMATIZE.

---

## Pipeline Architecture (Target)

```
trend_scout
    ↓
Truth Layer
    ↓
Visual Intelligence
    ↓
Storyboard Planner        ← cinematic_video/research/storyboard_patterns.py
    ↓
Shot Planner              ← cinematic_video/research/shot_taxonomy.py
    ↓
Flow Director             ← cinematic_video/research/flow_feature_registry.py
    ↓
Clip Extension Engine     ← cinematic_video/research/continuity_rules.py
    ↓
Continuity Validator      ← cinematic_video/research/video_continuity_validator.py
    ↓
Assembler                 ← (future: cinematic_video/assembler.py)
    ↓
Posting Layer
```

---

## Integration Points (not yet connected)

### 1. Truth Layer → Storyboard
**Trigger:** New product detected via `trend_scout`  
**Action:** Query `storyboard_patterns.recommend_storyboard(product_category, budget_credits)`  
**Output:** `StoryboardPattern` with shot sequence

### 2. Visual Intelligence → Shot Planner
**Trigger:** `visual_optimizer.get_archetype_directive()` returns visual style  
**Action:** Map archetype → `CinematicShot` via `shot_taxonomy.get_shots_by_aesthetic(aesthetic)`  
**Output:** Priority-ordered shot list

### 3. Flow Director → Clip Generation
**Trigger:** `shot_sequence` from Storyboard Planner  
**Action:** Sequential Flow calls via `flow_feature_registry.get_feature(mode)`  
**Output:** Raw generated clips (`.mp4`)

### 4. Continuity Validator → Quality Gate
**Trigger:** After each Flow generation  
**Action:** `video_continuity_validator.validate_storyboard_continuity(sequence)`  
**Output:** `ContinuityValidation` with `passed: bool` and warning list

### 5. Assembler → Final Export
**Trigger:** All clips pass continuity validation  
**Action:** Stitch clips with transitions from `scene_transition_library`  
**Output:** Final `.mp4` ad

---

## Integration Rules (when implemented)

| Rule | Description |
|---|---|
| **NO runtime blocking** | Flow generation is slow — run in background thread/subprocess |
| **NO internet in critical path** | Fallback to static/placeholder if Flow API is down |
| **Credit budget enforced** | `generation_cost_estimator` must gate every Flow call |
| **Failsafe abort** | `should_abort_sequence()` called before each generation |
| **Log everything** | Every generation, decision, abort logged to `logs/cinematic_video/` |
| **Never auto-post** | Assembly output goes to review queue, never direct to Posting Layer |

---

## Pre-Flight Checklist (before any implementation)

- [ ] All 12 knowledge modules have real-world validation (not just synthetic data)
- [ ] `generation_cost_estimator` tested against real Flow credit consumption
- [ ] `video_continuity_validator` thresholds calibrated with real clips
- [ ] Storyboard patterns validated with at least 3 real product categories
- [ ] Camera motion prompts tested (not generated — tested for prompt quality)
- [ ] Flow UI map verified against current Flow interface (UI changes frequently)
- [ ] Approval gate added: NO generation without explicit user confirmation

---

## Phase Dependencies

| Phase | Depends On | Status |
|---|---|---|
| Storyboard Planner | Trend Scout + Truth Layer | NOT IMPLEMENTED |
| Shot Planner | Visual Intelligence | NOT IMPLEMENTED |
| Flow Director | Storyboard Planner + Shot Planner | NOT IMPLEMENTED |
| Clip Extension Engine | Flow Director + Continuity Rules | NOT IMPLEMENTED |
| Continuity Validator | Clip Extension Engine | NOT IMPLEMENTED |
| Assembler | Continuity Validator + Transition Library | NOT IMPLEMENTED |

---

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Flow API changes UI | High | `flow_ui_mapper.py` must be updated before each session |
| Credit depletion | Medium | `generation_cost_estimator` hard cap per product |
| Visual drift between clips | Medium | `continuity_validator` as quality gate |
| Cost escalation | Low | `should_abort_sequence()` early termination |
| Prompt drift | Low | `prompt_cinema_patterns` with deterministic scaffolds |

---

## Decision Log

| Decision | Rationale | Date |
|---|---|---|
| Research-only phase first | Avoid wasting credits on unvalidated prompts | — |
| No auto-generation | Safety: Flow is expensive and irreversible | — |
| Knowledge before action | Agent needs cinematographic vocabulary first | — |
| Archive architecture, don't implement | Prevents premature integration | — |

---

*Document version: 1.0 — Phase 13 Future Integration only*
