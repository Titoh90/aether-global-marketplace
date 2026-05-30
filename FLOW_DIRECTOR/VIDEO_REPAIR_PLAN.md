# PLAN DE REPARACIÓN — Video Generation Pipeline
# Fecha: 2026-05-29
# Estado: INVESTIGACIÓN COMPLETA — NO EJECUTAR AÚN
# Objetivo: Restaurar creación de video SIN romper generación de imágenes

---

## CONTEXTO

Google Flow rediseñó su UI a chat-style editor (May 2026). Los selectores viejos
ya no funcionan. La generación de imágenes SÍ funciona con el nuevo UI.
El pipeline de video está ROTO porque busca elementos que ya no existen.

---

## SELECTORES NUEVOS CONFIRMADOS (via CDP Playwright)

### Bottom Bar
- Prompt input: `[contenteditable="true"]` — "Describe tus cambios" (x=481, y=786)
- Gallery button: `button` con "add_2" (x=486, y=831)
- Agent button: `button` con "Agente" (x=518, y=809)
- Video chip: `button` con "Video crop_9_16 1x" (x=938, y=808)
- Generate: `button` con "arrow_forward Crear" (x=1031, y=826)

### Video Mode Panel (después de click en Video chip)
- Imagen tab: `button` con "image Imagen" (x=762, y=572)
- Video tab: `button` con "play_circle Video" (x=894, y=572)
- Fotogramas: `button` con "crop_free Fotogramas" (x=762, y=610)
- Model selector: "Veo 3.1 - Lite" con dropdown (x=762, y=724)
- Credits: "La generación usará 10 créditos" (x=762, y=762)

### Gallery Sidebar (después de click en add_2)
- Upload: `button` con "add Agregar archivo multimedia" (x=1297)
- Cargas: `button` con "drive_folder_upload Ver contenido multimedia subido" (x=20, y=344)
- Videos: `button` con "videocam Ver videos" (x=20, y=186)
- Escenas: `button` con "movie Ver escenas" (x=20, y=291)
- Herramientas: `button` con "apps_spark_2 Herramientas" (x=20, y=419)

### Frame Slots
- Iniciar: aparece DESPUÉS de click en "crop_free Fotogramas"
- Fin: aparece DESPUÉS de click en "crop_free Fotogramas"
- Upload: `input[type="file"] accept="image/*" multiple`

### Model Chip (modo imagen)
- "pen_magic Omni Flash" — ya NO es Nano Banana
- Aspect ratio: "crop_portrait 9:16" (x=8, y=275)

---

## FUNCIONES QUE HAY QUE CAMBIAR

### 1. `_find_model_btn()` — Línea 749
**PROBLEMA:** Busca 'nano banana', 'veo', 'imagen 4'. El modelo ahora es 'Omni Flash'.
**SOLUCIÓN:** Agregar 'omni flash' a MODEL_KW. Buscar también el chip "Video crop_9_16 1x".

```python
# AGREGAR:
MODEL_KW = ['nano banana', 'veo', 'imagen 4', 'omni flash']
CHIP_KW  = ['crop_', 'x2', 'x3', 'x4', 'video']
```

### 2. `_ensure_video_frames_mode()` — Línea 907
**PROBLEMA:** Busca tabs por 'Video'+'play_circle' con restricción de ancho.
Flujo viejo: model picker → Video tab → Fotogramas → aspect ratio → Escape.
**SOLUCIÓN:** Nuevo flujo:
1. Click en Video chip (bottom bar)
2. Click en "play_circle Video" tab
3. Click en "crop_free Fotogramas"
4. Verificar slots Iniciar/Fin

```python
# FLUJO NUEVO:
# 1. Click Video chip en bottom bar
video_chip = await self._pg.evaluate('''() => {
    const btns = Array.from(document.querySelectorAll("button"));
    const b = btns.find(b => {
        const t = (b.innerText||"").trim();
        return t.includes("Video") && t.includes("crop_") && b.getBoundingClientRect().y > 750;
    });
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return {x: r.x+r.width/2, y: r.y+r.height/2};
}''')
await self._pg.mouse.click(video_chip["x"], video_chip["y"])
await asyncio.sleep(2)

# 2. Click Video tab
video_tab = await self._pg.evaluate('''() => {
    const btns = Array.from(document.querySelectorAll("button"));
    const b = btns.find(b => (b.innerText||"").includes("play_circle") && (b.innerText||"").includes("Video"));
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return {x: r.x+r.width/2, y: r.y+r.height/2};
}''')
await self._pg.mouse.click(video_tab["x"], video_tab["y"])
await asyncio.sleep(1)

# 3. Click Fotogramas
fotogramas = await self._pg.evaluate('''() => {
    const btns = Array.from(document.querySelectorAll("button"));
    const b = btns.find(b => (b.innerText||"").includes("crop_free") && (b.innerText||"").includes("Fotogramas"));
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return {x: r.x+r.width/2, y: r.y+r.height/2};
}''')
await self._pg.mouse.click(fotogramas["x"], fotogramas["y"])
await asyncio.sleep(2)

# 4. Verificar slots
slots = await self._check_frame_slots()
return slots.get("has_iniciar") or slots.get("has_fin")
```

### 3. `_switch_mode()` — Línea 799
**PROBLEMA:** Busca tabs por `[role="tab"]` con keywords de imagen/video.
El nuevo UI usa botones directos, no tabs ARIA.
**SOLUCIÓN:** Click en Video chip → panel → click en tab Imagen o Video.

```python
# Si mode == "Image": click en "image Imagen" tab
# Si mode == "Video": click en "play_circle Video" tab
```

### 4. `_upload_and_set_slot()` — Línea 383
**PROBLEMA:** Busca swap_horiz como anchor. Ya no existe.
Flujo viejo: clear slot → upload → click slot → picker dialog → Cargas tab → click item.
**SOLUCIÓN:** Nuevo flujo:
1. Upload via `input[type="file"]`
2. Abrir gallery sidebar (click add_2)
3. Click en "Cargas" tab
4. Click en el item subido
5. Verificar slot lleno

```python
# FLUJO NUEVO:
# 1. Upload
await self._pg.locator('input[type="file"]').first.set_input_files(str(image_path))
await asyncio.sleep(4)

# 2. Abrir gallery (add_2)
add_btn = await self._pg.evaluate('''() => {
    const btns = Array.from(document.querySelectorAll("button"));
    const b = btns.find(b => (b.innerText||"").includes("add_2"));
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return {x: r.x+r.width/2, y: r.y+r.height/2};
}''')
await self._pg.mouse.click(add_btn["x"], add_btn["y"])
await asyncio.sleep(2)

# 3. Click Cargas
cargas = await self._pg.evaluate('''() => {
    const btns = Array.from(document.querySelectorAll("button"));
    const b = btns.find(b => (b.innerText||"").includes("Cargas"));
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return {x: r.x+r.width/2, y: r.y+r.height/2};
}''')
await self._pg.mouse.click(cargas["x"], cargas["y"])
await asyncio.sleep(2)

# 4. Click en el item subido (primer item en la gallery)
# 5. Verificar slot lleno
```

### 5. `_wait_for_iniciar()` — Línea 260
**PROBLEMA:** Busca 'Iniciar' como texto exacto o swap_horiz como anchor.
**SOLUCIÓN:** Buscar texto 'Iniciar' que aparezca después de click en Fotogramas.
También buscar por "chrome_extension" icon + "Iniciar" truncado.

```python
# BUSCAR:
iniciar = await self._pg.evaluate('''() => {
    const all = Array.from(document.querySelectorAll("*"));
    const el = all.find(e => {
        const t = (e.innerText||"").trim();
        return (t === "Iniciar" || t.includes("chrome_extension") && t.includes("In"))
            && e.getBoundingClientRect().width > 0
            && e.getBoundingClientRect().width < 200;
    });
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: r.x+r.width/2, y: r.y+r.height/2, m: "empty"};
}''')
```

### 6. `_check_frame_slots()` — Línea 1031
**PROBLEMA:** Usa swap_horiz como anchor para distinguir Iniciar vs Fin.
**SOLUCIÓN:** Buscar los slots por posición (Iniciar a la izquierda, Fin a la derecha)
o por texto contenido.

```python
# NUEVO ENFOQUE:
# Buscar todos los elementos con 'Iniciar' o 'Fin' o 'chrome_extension'
# Iniciar = el que está más a la izquierda
# Fin = el que está más a la derecha
```

### 7. `_find_generate_btn()` — Línea 562
**PROBLEMA:** Funciona bien — "arrow_forward Crear" sigue existiendo.
**SOLUCIÓN:** Sin cambios necesarios. ✅

### 8. `_find_prompt_input()` — Línea 603
**PROBLEMA:** Funciona bien — `[contenteditable="true"]` sigue existiendo.
**SOLUCIÓN:** Sin cambios necesarios. ✅

---

## FUNCIONES QUE NO HAY QUE CAMBIAR

| Función | Razón |
|---|---|
| `_find_generate_btn()` | "arrow_forward Crear" sigue igual |
| `_find_prompt_input()` | `[contenteditable="true"]` sigue igual |
| `_type_prompt()` | Usa element handle, no coordenadas |
| `_click_generate()` | Usa JS click como fallback |
| `_upload_image()` | `input[type="file"]` sigue existiendo |
| `_dismiss_dialog()` | "Aceptar"/"Accept"/"OK" sigue igual |
| `_poll_uuid_until_ready()` | Lógica de polling unchanged |
| `_wait_for_new_uuid()` | Lógica de UUID unchanged |
| `_extract_last_frame()` | FFmpeg unchanged |
| `generate_images()` | Funciona con Omni Flash |
| `research_amazon()` | Playwright CDP unchanged |

---

## ORDEN DE IMPLEMENTACIÓN

### FASE 1: Selectores base (sin romper nada)
1. Actualizar `_find_model_btn()` — agregar 'omni flash'
2. Actualizar `_check_frame_slots()` — quitar swap_horiz
3. Actualizar `_wait_for_iniciar()` — nuevo selector

### FASE 2: Video mode (nuevo flujo)
4. Reescribir `_ensure_video_frames_mode()` — nuevo flujo de clicks
5. Reescribir `_switch_mode()` — tabs Imagen/Video

### FASE 3: Upload + slots
6. Reescribir `_upload_and_set_slot()` — gallery sidebar flow
7. Actualizar `_clear_slot()` — si es necesario

### FASE 4: Testing
8. Test con escena individual (1 scene)
9. Test pipeline completo (4 scenes)
10. Verificar que imágenes siguen funcionando

---

## RIESGOS

| Riesgo | Mitigación |
|---|---|
| Romper generación de imágenes | FASE 1 primero, testear imágenes |
| Coordenadas cambien con viewport | Usar selectores por texto, no posición |
| Google Flow cambie de nuevo | Documentar selectores en FLOW_UI_REFERENCE.md |
| Créditos agotados | Verificar saldo antes de generar |

---

## ESTADO ACTUAL

- ✅ Investigación completa
- ✅ Selectores nuevos documentados
- ✅ Plan de修复ión escrito
- ⏳ Pendiente: ejecutar FASE 1-4
- ⏳ Pendiente: testing

---

*Este archivo es solo documentación. NO ejecuta cambios.*
