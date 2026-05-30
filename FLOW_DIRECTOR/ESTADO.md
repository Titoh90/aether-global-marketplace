# FLOW_DIRECTOR — Estado de Instalación
**Instalado:** 2026-05-17 | **Versión:** v1.0.0

---

## ✅ QUÉ QUEDÓ INSTALADO

| Componente | Path | Estado |
|-----------|------|--------|
| scene_director.py | `FLOW_DIRECTOR/scene_director.py` | ✅ Validado (dry-run) |
| frame_extractor.py | `FLOW_DIRECTOR/frame_extractor.py` | ✅ Listo |
| flow_operator.py | `FLOW_DIRECTOR/flow_operator.py` | ✅ Listo |
| flow_agent.py | `FLOW_DIRECTOR/flow_agent.py` | ✅ Validado (dry-run) |
| assets/ | `FLOW_DIRECTOR/assets/` | ✅ Directorio creado |
| clips/ | `FLOW_DIRECTOR/clips/` | ✅ Directorio creado |
| frames/ | `FLOW_DIRECTOR/frames/` | ✅ Directorio creado |
| output/ | `FLOW_DIRECTOR/output/` | ✅ Tiene plan de prueba |
| logs/ | `FLOW_DIRECTOR/logs/` | ✅ Directorio creado |
| prompts/ | `FLOW_DIRECTOR/prompts/` | ✅ Directorio creado |

### Plan de prueba generado:
`output/flow_20260517_091356.json` — 4 escenas, AI Chatbot Builder, TikTok 9:16

---

## ❌ QUÉ NO QUEDÓ INSTALADO

| Componente | Razón |
|-----------|-------|
| Ejecución real en Google Flow | Requiere cuenta Google + Chrome abierto + login manual |
| Imagen de producto de prueba | `assets/product_main.jpg` — debe poner imagen real el usuario |
| Clips reales generados | Depende de Flow UI — sin clips aún |
| Integración Hermes activa | Interface lista (`from_hermes_input()`), conector no activado |
| Veo 3.1 acceso garantizado | Free tier limitado (100+50 créditos/día), depende de cuenta |

---

## 🏗️ ARQUITECTURA DEL AGENTE

```
flow_agent.py (Orquestador principal)
├── CLI: --product, --angle, --platform, --scenes, --plan, --dry-run
├── Hermes interface: from_hermes_input(hermes_data: dict)
│
├── [Phase 1] scene_director.py
│   ├── Ollama (qwen2.5:1.5b) → narrativa cinematográfica
│   ├── CINEMATIC_BASE → base de prompt para Google Flow
│   ├── SCENE_MODIFIERS → modificadores por tipo de escena
│   └── Continuity chain: product_image → last_frame_extract
│
├── [Phase 2] Pre-flight checks
│   ├── Verificar assets/product_image.jpg
│   └── Verificar Chrome corriendo
│
├── [Phase 3] flow_operator.py → Google Flow UI real
│   ├── Chrome real (AppleScript + JS) — NO headless
│   ├── navigate_to_flow() → https://labs.google/fx/tools/flow
│   ├── enter_prompt() → contenteditable div
│   ├── switch_to_video_frames_mode() → Video > Frames
│   ├── upload_start_frame() → input[type="file"] / manual fallback
│   ├── wait_for_generation() → polling video elements, 30s screenshots
│   └── download_latest_clip() → ~/Downloads polling
│
├── [After each scene] frame_extractor.py
│   ├── FFmpeg: extrae frame a (duration - 0.1s)
│   └── Output: frames/scene_NN_last_frame.png → input de siguiente escena
│
└── [Phase 4] Resultados
    ├── output/flow_YYYYMMDD_HHMMSS.json (plan actualizado)
    ├── logs/flow_execution_*.json
    └── output/report_*.md (markdown)
```

---

## 🎬 TIPOS DE ESCENA

| Tipo | Uso | Prompt modifier |
|------|-----|----------------|
| HOOK | Escena 1 siempre | dramatic opening, close-up impact shot, product reveal moment |
| FEATURE | Escena 2 | detailed product functionality demonstration, slow-motion texture reveal |
| LIFESTYLE | Escena 3 | real world usage, human interaction, authentic environment, warm tones |
| EMOTION | Escena 4 | emotional close, lifestyle aspiration, brand highlight, golden hour |
| CTA | Escena 5 (si n=5) | brand identity close-up, cinematic fade out, logo reveal, premium feel |

---

## 🔗 CONTINUIDAD VISUAL (regla crítica)

```
Scene 1: image_input = product_main.jpg        ← imagen de producto
            ↓ generate → clips/scene_01_hook.mp4
            ↓ FFmpeg extract last frame
         frames/scene_01_last_frame.png

Scene 2: image_input = scene_01_last_frame.png ← continuidad
            ↓ generate → clips/scene_02_feature.mp4
            ↓ FFmpeg extract last frame
         frames/scene_02_last_frame.png

Scene 3: image_input = scene_02_last_frame.png ← continuidad
   ...
```

---

## 🚀 CÓMO USAR

### Paso 0 — Prerequisito
```bash
# 1. Abrir Google Chrome
# 2. Navegar a: https://labs.google/fx/tools/flow
# 3. Login con cuenta Google (mantener sesión abierta)
# 4. Poner imagen de producto en:
cp tu_imagen.jpg "/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR/assets/product_main.jpg"
```

### Dry-run (solo genera plan, sin abrir Flow)
```bash
cd "/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR"
python3 flow_agent.py --dry-run \
  --product "Tu Producto" \
  --image product_main.jpg \
  --angle "beneficio principal" \
  --platform TikTok \
  --audience "tu audiencia" \
  --cta "texto del CTA"
```

### Ejecución completa (real, abre Google Flow)
```bash
python3 flow_agent.py \
  --product "AI Chatbot Builder" \
  --image product_main.jpg \
  --angle "saves 10 hours per week" \
  --platform TikTok \
  --cta "Try free at link in bio"
# → Pide confirmación antes de abrir Flow
# → Usa --yes para skip confirmaciones
```

### Ejecución una sola escena (step-through debug)
```bash
python3 flow_agent.py --plan output/flow_20260517_091356.json --scene 1
```

### Reanudar plan existente (escenas pendientes)
```bash
python3 flow_agent.py --plan output/flow_20260517_091356.json
```

### Solo generar plan (scene_director standalone)
```bash
python3 scene_director.py \
  --product "Tu Producto" \
  --angle "beneficio" \
  --scenes 4
```

### Extraer último frame de clip manualmente
```bash
python3 frame_extractor.py clips/scene_01_hook.mp4 --scene-id 1
```

---

## 🔌 INTEGRACIÓN CON HERMES

```python
from flow_agent import from_hermes_input
from scene_director import build_scene_plan

hermes_data = {
    "product": "AI Chatbot Builder",
    "product_image": "product_main.jpg",
    "marketing_angle": "saves 10 hours per week",
    "platform": "TikTok",
    "audience": "small business owners",
    "cta": "Try free at link in bio",
    "n_scenes": 4
}

# Convertir formato Hermes → agente
args = from_hermes_input(hermes_data)

# Generar plan
plan = build_scene_plan(**args)
```

---

## 📊 TEST DE VALIDACIÓN (dry-run 2026-05-17)

```
✅ syntax_ok          flow_agent.py + scene_director.py sin errores
✅ ollama_connected   qwen2.5:1.5b respondió en ~15s
✅ json_valid         Narrativa LLM parseada correctamente
✅ plan_generated     flow_20260517_091356.json — 4 escenas
✅ continuity_chain   Scene 1→product_main.jpg, 2-4→last_frame_extract
✅ prompts_built      CINEMATIC_BASE + SCENE_MODIFIERS + energy aplicados
✅ file_saved         output/flow_20260517_091356.json
```

**Plan generado:**
- Video: "Chatbot Dreams Come True"
- 4 escenas × 8s = 32s total
- HOOK → FEATURE → LIFESTYLE → EMOTION
- Formato: 9:16 (TikTok)
- Modelo: Veo 3.1

---

## ⚠️ RIESGOS Y LIMITACIONES

| Riesgo | Nivel | Mitigación |
|--------|-------|-----------|
| Google Flow UI cambia | MEDIO | Múltiples estrategias JS + fallback manual |
| Free tier: 100+50 créditos/día | MEDIO | Planificar 4-5 escenas por sesión (una campaña/día) |
| Chrome TCC en macOS | BAJO | Chrome real user session — no headless, no bot detection |
| image upload drag-and-drop | ALTO | Fallback a input() manual hasta encontrar selector estable |
| Veo 3.1 genera ~60-90s/clip | INFO | wait_for_generation() espera hasta 10 min por escena |
| Sin imagen de producto | BLOQUEANTE | assets/product_main.jpg debe existir antes de correr |
| Ollama qwen falla | BAJO | Aumentar timeout o cambiar a gemma3:12b con --model |

---

## 🗺️ PIPELINE COMPLETO (IMPERIO)

```
Hermes (Revenue Router)
↓ from_hermes_input()
flow_agent.py (Scene Orchestrator)
↓ Ollama qwen2.5:1.5b
scene_director.py → ScenePlan JSON
↓ Chrome real (AppleScript)
flow_operator.py → Google Flow UI
↓ Veo 3.1 generate × N escenas
clips/scene_NN_*.mp4
↓ FFmpeg frame_extractor.py
frames/scene_NN_last_frame.png → siguiente escena
↓ Todos los clips
Pixelle-Video (FFmpeg assembly)
↓
REVENUE/videos/final_*.mp4 → TikTok/Reels/Shorts
```

---

## 🎯 PRÓXIMOS PASOS

### Inmediato (antes de primera ejecución real):
1. Poner imagen de producto en `assets/product_main.jpg`
2. Abrir Chrome → login en Google Flow
3. Correr `python3 flow_agent.py --scene 1` para probar una sola escena
4. Validar que image upload funciona sin intervención manual

### Esta semana:
5. Hacer primera campaña real (4 escenas de "AI Chatbot Builder")
6. Conectar output a Pixelle-Video para ensamblaje final
7. Testear modo `--yes` para pipeline automático desde Hermes

### Opcional:
8. Mejorar `upload_start_frame()` con selector CSS estable de Google Flow
9. Agregar retry automático si generación falla (status != "completed")
10. Conectar Telegram bot: Hermes → flow_agent → notificación de clips listos

---

## 🔄 ROLLBACK COMPLETO

```bash
rm -rf "/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR/"
# Sin impacto en ComfyUI, Pixelle-Video, jcode ni otros servicios.
# Dependencias: Python stdlib + httpx + subprocess (ffmpeg, osascript)
# — todas pre-existentes, ninguna instalada nueva.
```
