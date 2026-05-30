# Google Flow UI Reference (2026-05-29)
# Source: manual documentation by Hernán
# Purpose: guide flow_operator.py automation decisions

## Bottom Bar (Prompt Input)
- Textbox with `contenteditable="true"`
- Model chip button: shows model name + aspect ratio + count (e.g. "🍌 Nano Banana 2 crop_16_9 x2")
- Generate button: "arrow_forward Crear" (disabled until prompt typed)
- Agent toggle button

## Model Chip → Config Panel
Clicking model chip opens panel with:
- **Tabs:** Imagen | Video
- **Aspect ratios:** 16:9, 4:3, 1:1, 3:4, 9:16
- **Count buttons:** 1x, x2, x3, x4
- **Model dropdown:** Nano Banana 2 (free) | Nano Banana Pro (credits)
- Close with Escape

## Image Models
- 🍌 Nano Banana 2 — FREE, standard quality
- 🍌 Nano Banana Pro — credits, higher quality
- Engine: Imagen 4

## Video Models
- 🍌 Nano Banana 2 — FREE for video too
- 🍌 Nano Banana Pro — credits
- Omni Flash — used in video editor (not generation)
- Engine: Veo

## Gallery Item Hover Actions
- ♥ Favorite
- 🔄 Regenerate
- ⋮ Context menu

## Context Menu (Image)
Animar | Agregar a instrucción | Descargar | Cambiar nombre | Compartir | Portada proyecto | Comentario | Papelera

## Context Menu (Video)
Agregar a escena | Agregar a instrucción | Descargar | Cambiar nombre | Compartir | Publicar en YouTube | Portada proyecto | Comentario | Papelera

## Sections
- **Videos** — generated clips, Veo engine
- **Escenas** — concatenated video sequences (NLE)
- **Personajes** — consistent character identity across generations
- **Cargas** — uploaded files (product photos, references)
- **Herramientas** — tools ecosystem

## Tools (relevant for automation)
- Mockup — product mockups on devices/contexts
- Image Editor — transform objects, add text, resize
- Style Writer — mood board → style prompt
- Whisk — images as prompts (subject + scene + style)

## Video Editor
- Timeline with + button → "Agregar video" or "Extender"
- Extend prompt: "¿Qué sucederá ahora?"
- Editor model: Omni Flash (different from generation model)

## Agent Mode
- System instructions configurable
- Agent instructions with visual references
- Can generate, rename, ideate

## Key Selectors for Automation
- Model chip: `button` containing "Nano Banana" or "Veo" text
- Aspect ratio buttons: direct text "16:9", "9:16", etc.
- Generate: `button` with text "arrow_forward Crear"
- Prompt input: `[contenteditable="true"]` with width > 200
- Tabs in config panel: `[role="tab"]` with "Imagen"/"Video" text
