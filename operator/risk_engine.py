"""
risk_engine.py — JARVIS Decision Layer (pure, context-aware, deterministic)

SCOPE:
  - SOLO toma decisiones: INPUT → SCORE → POLICY DECISION
  - NO ejecuta nada, NO llama tools, NO hace retries
  - Misma input → siempre mismo output (determinístico)

PIPELINE:
  classify(text) → intent
      ↓
  score_intent(intent, context) → RiskResult     ← ESTE MÓDULO
      ↓
  pre_execution_gate(result) → GateDecision
      ↓
  arbitrate(intent, allowed_tools)
      ↓
  execute(tool, params)

INVARIANTE CRÍTICO:
  El nivel resultante NUNCA puede bajar por overrides.
  Overrides solo pueden SUBIR (o bloquear). Nunca bajar.

Versión: 1.0 (basado en spec jarvis-skill-contract v1.1)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ─── ENUMERACIONES ─────────────────────────────────────────────────────────────

class GateDecision(str, Enum):
    PROCEED = "proceed"      # 🟢 ejecuta directo
    NOTIFY  = "notify"       # 🟡 ejecuta + notifica después
    CONFIRM = "confirm"      # 🔴 para, pregunta a Hernán, espera
    BLOCK   = "blocked"      # 🚫 no ejecuta nunca, explica por qué


# ─── DATA CLASSES ──────────────────────────────────────────────────────────────

@dataclass
class RiskContext:
    """
    Estado del sistema en el momento de la evaluación.
    Requerido para scoring context-aware.

    IMPORTANTE: El riesgo NO es función solo del intent —
    también depende de quién está presente, historial, y estado del sistema.
    """
    # Presencia de Hernán
    hernán_online: bool = True           # activo en últimos 5 min
    hernán_offline_minutes: int = 0      # minutos desde última actividad

    # Historial de la sesión
    session_actions_count: int = 0       # acciones ejecutadas en esta sesión
    last_action_pipeline: str = ""       # pipeline de la última acción
    last_action_failed: bool = False     # ¿la última acción falló?
    in_automated_loop: bool = False      # ¿corriendo desde cron/launchd?

    # Historial de esta skill específica
    skill_total_runs: int = 0            # total de veces que se ejecutó esta skill
    skill_last_failed: bool = False      # ¿la última ejecución de esta skill falló?
    skill_success_rate: float = 1.0      # tasa de éxito histórica (0.0 - 1.0)

    # Disponibilidad de herramientas
    deerflow_available: bool = True
    comfyui_available: bool = True
    chrome_available: bool = True

    # Estado del sistema
    disk_free_gb: float = 51.0           # GB libres en disco interno
    system_load: float = 0.0             # load average

    # Modo especial
    review_mode: bool = False            # todo es ROJO hasta que Hernán aprueba


@dataclass
class RiskResult:
    """Output del risk engine. Todo lo que necesita el gate."""
    pipeline: str
    action: str

    # Score y nivel
    base_score: int          # score 3D antes de overrides y contexto
    context_delta: int       # suma de modificadores de contexto
    final_score: int         # base_score + context_delta

    base_level: str          # "green" | "yellow" | "red"
    final_level: str         # puede ser mayor que base_level por overrides

    # Overrides activados
    overrides_triggered: list[str] = field(default_factory=list)

    # Gate output
    gate: GateDecision = GateDecision.PROCEED
    needs_confirm: bool = False
    blocked: bool = False

    # Mensajes (en español simple, sin jerga)
    reason: str = ""                     # por qué este nivel
    confirm_message: str = ""            # mensaje Telegram si necesita confirmación
    notify_message: str = ""             # mensaje Telegram post-ejecución (yellow)

    # Herramientas permitidas (filtradas por risk)
    allowed_tools: list[str] = field(default_factory=list)


# ─── TABLAS DE SCORING (inmutables) ─────────────────────────────────────────

AUTONOMY_SCORE: dict[str, int] = {
    "low":    1,
    "medium": 2,
    "high":   3,
}

EXTERNAL_IMPACT_SCORE: dict[bool, int] = {
    False: 0,
    True:  3,
}

IRREVERSIBILITY_SCORE: dict[str, int] = {
    "none":      0,
    "low":       1,
    "medium":    2,
    "high":      4,
    "permanent": 6,
}

# Score resultante → nivel semáforo
SCORE_TO_LEVEL: list[tuple[int, str]] = [
    (2,  "green"),   # 0-2  → 🟢 ejecuta directo
    (5,  "yellow"),  # 3-5  → 🟡 ejecuta + notifica
    (99, "red"),     # 6+   → 🔴 para + pide confirmación
]


# ─── REGISTRO DE SKILLS (policies embebidas) ─────────────────────────────────
# Mapeado: (pipeline, action) → policy dict
# Fuente: spec jarvis-skill-contract v1.1 Section E

SKILL_POLICIES: dict[tuple[str, str], dict] = {

    # ── CONTENT PIPELINE (research + video + post) ──────────────────────────
    ("content_pipeline", "research_and_create"): {
        "execution_autonomy": "medium",
        "external_impact": False,         # post=False by default; set True when posting
        "irreversibility": "low",
        "risk_flags": [],
        "allowed_tools": ["pipeline_full"],
        "description_human": "Investigo un producto Amazon y creo un video de afiliado",
        "notify_message": (
            "✅ Pipeline completo: {topic}\n"
            "Video listo en {output_path}\n"
            "¿Lo publico? → `postea el video`"
        ),
    },

    # ── RESEARCH ────────────────────────────────────────────────────────────
    ("research", "product_research"): {
        "execution_autonomy": "low",
        "external_impact": False,
        "irreversibility": "none",
        "risk_flags": [],
        "allowed_tools": ["deerflow", "scrapegraph", "llm_lightweight"],
        "description_human": "Investigo un producto en internet",
        "notify_message": "Investigué {topic}. ¿Quieres que cree contenido con esto?",
    },

    # ── MEDIA — VIDEO ────────────────────────────────────────────────────────
    ("mediafactory", "create_video"): {
        "execution_autonomy": "medium",
        "external_impact": False,
        "irreversibility": "low",
        "risk_flags": [],
        "allowed_tools": ["flow_director", "comfyui", "fooocus"],
        "description_human": "Creo un video con IA",
        "notify_message": "Video listo: {output_path}. ¿Lo publico?",
    },
    ("flow_director", "generate_video"): {
        "execution_autonomy": "medium",
        "external_impact": False,
        "irreversibility": "low",
        "risk_flags": [],
        "allowed_tools": ["flow_director", "comfyui"],
        "description_human": "Genero video con Flow Director",
        "notify_message": "Video listo en {output_path}.",
    },
    ("flow_director", "generate_carousel"): {
        "execution_autonomy": "medium",
        "external_impact": False,
        "irreversibility": "low",
        "risk_flags": [],
        "allowed_tools": ["carousel_flow"],
        "description_human": "Genero carousel de producto con Google Flow",
        "notify_message": "Carousel listo: {slide_count} slides de {product}.",
    },

    # ── MEDIA — IMAGEN ───────────────────────────────────────────────────────
    ("flow_director", "generate_image"): {
        "execution_autonomy": "low",
        "external_impact": False,
        "irreversibility": "low",
        "risk_flags": [],
        "allowed_tools": ["comfyui", "fooocus"],
        "description_human": "Creo una imagen con IA",
        "notify_message": "Imagen lista: {output_path}.",
    },
    ("comfy", "generate"): {
        "execution_autonomy": "low",
        "external_impact": False,
        "irreversibility": "low",
        "risk_flags": [],
        "allowed_tools": ["comfyui"],
        "description_human": "Genero imagen con ComfyUI",
        "notify_message": "Imagen ComfyUI lista.",
    },

    # ── SOCIAL — PUBLICAR ────────────────────────────────────────────────────
    ("social_poster", "post_tiktok"): {
        "execution_autonomy": "high",
        "external_impact": True,
        "irreversibility": "medium",
        "risk_flags": ["content_publish"],
        "allowed_tools": ["tiktok_playwright"],
        "description_human": "Publico un video en TikTok",
        "confirm_message": (
            "Quiero publicar este video en TikTok.\n"
            "Motivo: completar el pipeline de contenido.\n"
            "Consecuencia si lo hago: el video queda público en @alexanderaether.\n"
            "Consecuencia si NO lo hago: el video queda guardado sin publicar.\n"
            "¿Qué prefieres?\n  A) Sí, publica\n  B) No, guárdalo\n  C) Revísalo primero"
        ),
    },
    ("social_poster", "post_instagram"): {
        "execution_autonomy": "high",
        "external_impact": True,
        "irreversibility": "medium",
        "risk_flags": ["content_publish"],
        "allowed_tools": ["instagram_instagrapi"],
        "description_human": "Publico un reel en Instagram",
        "confirm_message": (
            "Quiero publicar este reel en Instagram.\n"
            "Motivo: completar el pipeline de contenido.\n"
            "Consecuencia si lo hago: el reel queda público.\n"
            "Consecuencia si NO lo hago: el reel queda guardado sin publicar.\n"
            "¿Qué prefieres?\n  A) Sí, publica\n  B) No, guárdalo"
        ),
    },
    ("social_poster", "post_youtube"): {
        "execution_autonomy": "high",
        "external_impact": True,
        "irreversibility": "medium",
        "risk_flags": ["content_publish"],
        "allowed_tools": ["youtube_executor"],
        "description_human": "Publico video/Short en YouTube",
        "confirm_message": (
            "Quiero publicar este video en YouTube (@alexanderaether).\n"
            "Consecuencia si lo hago: video queda público.\n"
            "¿Qué prefieres?\n  A) Sí, publica\n  B) No, guárdalo"
        ),
    },
    ("social_poster", "post_facebook"): {
        "execution_autonomy": "high",
        "external_impact": True,
        "irreversibility": "medium",
        "risk_flags": ["content_publish"],
        "allowed_tools": ["facebook_executor"],
        "description_human": "Publico Reel en Facebook",
        "confirm_message": (
            "Quiero publicar este Reel en Facebook (@alexanderaether).\n"
            "Consecuencia si lo hago: el Reel queda público.\n"
            "¿Qué prefieres?\n  A) Sí, publica\n  B) No, guárdalo"
        ),
    },
    ("social_poster", "post_pinterest"): {
        "execution_autonomy": "high",
        "external_impact": True,
        "irreversibility": "medium",
        "risk_flags": ["content_publish"],
        "allowed_tools": ["pinterest_executor"],
        "description_human": "Creo Pin en Pinterest con link de afiliado",
        "notify_message": "Pin publicado en Pinterest (@aetherventuresoficial).",
    },
    ("social_poster", "post_twitter"): {
        "execution_autonomy": "high",
        "external_impact": True,
        "irreversibility": "medium",
        "risk_flags": ["content_publish"],
        "allowed_tools": ["twitter_executor"],
        "description_human": "Publico tweet en X",
        "confirm_message": (
            "Quiero publicar este tweet en X (@AAether32355).\n"
            "¿Qué prefieres?\n  A) Sí, publica\n  B) No"
        ),
    },
    ("social_poster", "post_x"): {
        "execution_autonomy": "high",
        "external_impact": True,
        "irreversibility": "medium",
        "risk_flags": ["content_publish"],
        "allowed_tools": ["twitter_executor"],
        "description_human": "Publico tweet en X (@AAether32355)",
        "notify_message": "Tweet publicado en X.",
    },
    ("social_poster", "post"): {
        "execution_autonomy": "high",
        "external_impact": True,
        "irreversibility": "medium",
        "risk_flags": ["content_publish"],
        "allowed_tools": ["tiktok_playwright", "instagram_instagrapi", "youtube_executor", "facebook_executor", "pinterest_executor", "twitter_executor"],
        "description_human": "Publico contenido en redes sociales",
        "confirm_message": (
            "Quiero publicar contenido en redes sociales.\n"
            "¿En qué plataforma y con qué video?\n"
            "¿Qué prefieres?\n  A) Sí, especifica plataforma\n  B) No todavía"
        ),
    },

    # ── COMUNICACIÓN — EMAIL ─────────────────────────────────────────────────
    ("email", "send_email"): {
        "execution_autonomy": "high",
        "external_impact": True,
        "irreversibility": "high",
        "risk_flags": ["external_comm"],
        "allowed_tools": ["gmail_mcp"],
        "description_human": "Envío un email",
        "confirm_message": (
            "Quiero enviar un email a {recipient}.\n"
            "Asunto: {subject}\n"
            "Motivo: {reason}\n"
            "Consecuencia: el email llega al destinatario y no se puede recuperar.\n"
            "¿Qué prefieres?\n  A) Sí, envíalo\n  B) No, guárdalo como borrador\n  C) Revísalo primero"
        ),
    },
    ("email", "read_email"): {
        "execution_autonomy": "low",
        "external_impact": False,
        "irreversibility": "none",
        "risk_flags": ["privacy"],
        "allowed_tools": ["gmail_mcp"],
        "description_human": "Leo emails",
        "notify_message": "Revisé tu correo. {summary}",
    },

    # ── COMUNICACIÓN — WHATSAPP ───────────────────────────────────────────────
    ("whatsapp", "send_message"): {
        "execution_autonomy": "high",
        "external_impact": True,
        "irreversibility": "high",
        "risk_flags": ["external_comm"],
        "allowed_tools": ["whatsapp_executor"],
        "description_human": "Envío un mensaje de WhatsApp a {recipient}",
        "confirm_message": (
            "Quiero enviar un WhatsApp a {recipient}.\n"
            "Mensaje: \"{message_preview}\"\n"
            "Consecuencia: el mensaje llega instantáneamente.\n"
            "¿Qué prefieres?\n  A) Sí, envíalo\n  B) No"
        ),
    },

    # ── WEB / BROWSER ────────────────────────────────────────────────────────
    ("browser", "browse"): {
        "execution_autonomy": "low",
        "external_impact": False,
        "irreversibility": "none",
        "risk_flags": [],
        "allowed_tools": ["playwright_mcp", "browser_use", "scrapegraph"],
        "description_human": "Navego una página web",
        "notify_message": "Navegué {url}. {summary}",
    },

    # ── SISTEMA ──────────────────────────────────────────────────────────────
    ("system", "status"): {
        "execution_autonomy": "low",
        "external_impact": False,
        "irreversibility": "none",
        "risk_flags": [],
        "allowed_tools": ["hermes_status"],
        "description_human": "Reviso el estado del sistema",
        "notify_message": "",
    },
    ("system", "revenue"): {
        "execution_autonomy": "low",
        "external_impact": False,
        "irreversibility": "none",
        "risk_flags": [],
        "allowed_tools": ["hermes_status"],
        "description_human": "Reviso los ingresos del día",
        "notify_message": "",
    },
    ("system", "tasks"): {
        "execution_autonomy": "low",
        "external_impact": False,
        "irreversibility": "none",
        "risk_flags": [],
        "allowed_tools": ["hermes_status"],
        "description_human": "Reviso la cola de tareas",
        "notify_message": "",
    },
    ("system", "answer_question"): {
        "execution_autonomy": "low",
        "external_impact": False,
        "irreversibility": "none",
        "risk_flags": [],
        "allowed_tools": ["llm_lightweight"],
        "description_human": "Respondo una pregunta",
        "notify_message": "",
    },
    ("system", "pause_pipeline"): {
        "execution_autonomy": "medium",
        "external_impact": False,
        "irreversibility": "low",
        "risk_flags": ["system_critical"],
        "allowed_tools": ["hermes_status"],
        "description_human": "Pauso un pipeline activo",
        "confirm_message": (
            "Quiero pausar el pipeline {pipeline_name}.\n"
            "Consecuencia: deja de ejecutarse hasta que lo reanudes.\n"
            "¿Qué prefieres?\n  A) Sí, pausa\n  B) No, sigue corriendo"
        ),
    },

    # ── ARCHIVOS / SISTEMA CRÍTICO ────────────────────────────────────────────
    ("system", "delete_file"): {
        "execution_autonomy": "high",
        "external_impact": False,
        "irreversibility": "permanent",
        "risk_flags": ["delete"],
        "allowed_tools": ["filesystem_mcp"],
        "description_human": "Elimino un archivo",
        "confirm_message": (
            "Quiero eliminar el archivo {filepath}.\n"
            "Motivo: {reason}\n"
            "Consecuencia si lo hago: el archivo se borra. Si no hay backup, es permanente.\n"
            "Consecuencia si NO lo hago: el archivo sigue ocupando espacio.\n"
            "Alternativa más segura: moverlo al disco externo en vez de borrarlo.\n"
            "¿Qué prefieres?\n  A) Sí, bórralo\n  B) No, déjalo\n  C) Muévelo al externo"
        ),
    },
}

# Política por defecto para pipelines no registrados
_DEFAULT_POLICY: dict = {
    "execution_autonomy": "medium",
    "external_impact": False,
    "irreversibility": "low",
    "risk_flags": [],
    "allowed_tools": [],
    "description_human": "Ejecuto una acción",
    "notify_message": "Acción completada.",
}


# ─── OVERRIDE RULES (evaluadas en orden, 1 = mayor prioridad) ──────────────

def _or001_privacy_exposure(policy: dict, context: RiskContext, params: dict) -> bool:
    """OR-001: Expone datos personales de terceros sin consentimiento."""
    return "privacy" in policy.get("risk_flags", []) and not context.hernán_online

def _or002_illegal_content(policy: dict, context: RiskContext, params: dict) -> bool:
    """OR-002: Genera contenido ilegal. (Placeholder — LLM validation en capa superior)"""
    return False  # Evaluado en capa de contenido, no aquí

def _or003_permanent_irreversibility(policy: dict, context: RiskContext, params: dict) -> bool:
    """OR-003: Irreversibilidad permanente."""
    return policy.get("irreversibility") == "permanent"

def _or004_delete_flag(policy: dict, context: RiskContext, params: dict) -> bool:
    """OR-004: Flag delete presente."""
    return "delete" in policy.get("risk_flags", [])

def _or005_system_critical(policy: dict, context: RiskContext, params: dict) -> bool:
    """OR-005: Flag system_critical presente."""
    return "system_critical" in policy.get("risk_flags", [])

def _or006_config_modification(policy: dict, context: RiskContext, params: dict) -> bool:
    """OR-006: Modifica archivos de configuración del sistema."""
    filepath = str(params.get("filepath", ""))
    config_patterns = [".env", "settings.json", ".claude", "/etc/", "launchd", ".plist"]
    return any(p in filepath for p in config_patterns)

def _or007_privacy_flag(policy: dict, context: RiskContext, params: dict) -> bool:
    """OR-007: Flag privacy presente Y Hernán está offline.
    Si Hernán está activo (acaba de mandar un mensaje), leer email propio
    no requiere confirmación extra — es su bandeja, no datos de terceros."""
    return "privacy" in policy.get("risk_flags", []) and not context.hernán_online

def _or008_credentials_in_params(policy: dict, context: RiskContext, params: dict) -> bool:
    """OR-008: Detecta credenciales/tokens en los parámetros."""
    sensitive_patterns = [
        r"(password|passwd|token|secret|api_key|apikey|bearer|sk-|nvapi-)",
        r"(credential|auth|login|contraseña)",
    ]
    params_str = str(params).lower()
    return any(re.search(p, params_str) for p in sensitive_patterns)


# Tabla de override rules: (id, función, nivel forzado, bloquea_total)
ORDERED_OVERRIDE_RULES: list[tuple[str, callable, str, bool]] = [
    ("OR-001", _or001_privacy_exposure,       "red",     False),
    ("OR-002", _or002_illegal_content,        "blocked", True),
    ("OR-003", _or003_permanent_irreversibility, "red",  False),
    ("OR-004", _or004_delete_flag,            "red",     False),
    ("OR-005", _or005_system_critical,        "red",     False),
    ("OR-006", _or006_config_modification,    "red",     False),
    ("OR-007", _or007_privacy_flag,           "red",     False),
    ("OR-008", _or008_credentials_in_params,  "red",     False),
]


# ─── FUNCIONES INTERNAS ──────────────────────────────────────────────────────

def _level_rank(level: str) -> int:
    return {"green": 0, "yellow": 1, "red": 2, "blocked": 3}.get(level, 0)


def _score_to_level(score: int) -> str:
    for threshold, level in SCORE_TO_LEVEL:
        if score <= threshold:
            return level
    return "red"


def _context_modifiers(policy: dict, context: RiskContext) -> int:
    """
    Modificadores de contexto. Incrementan el score según el estado del sistema.
    Cada modificador suma 1 al score final.
    """
    delta = 0

    # Primera vez ejecutando esta skill → más cuidado
    if context.skill_total_runs == 0:
        delta += 1

    # La última ejecución de esta skill falló
    if context.skill_last_failed:
        delta += 1

    # Ejecutando en loop automático (cron, launchd)
    if context.in_automated_loop:
        delta += 1

    # Hernán está offline hace más de 2 horas
    if context.hernán_offline_minutes > 120:
        delta += 1

    # Modo revisión activado → todo sube
    if context.review_mode:
        delta += 2

    # Tasa de éxito histórica baja (<60%)
    if context.skill_success_rate < 0.60 and context.skill_total_runs >= 5:
        delta += 1

    # Disco con poco espacio (< 5GB libres)
    if context.disk_free_gb < 5.0:
        delta += 1

    return delta


def _apply_overrides(
    policy: dict,
    context: RiskContext,
    params: dict,
    base_level: str,
) -> tuple[list[str], str]:
    """
    Evalúa override rules en orden de prioridad.
    El nivel SOLO puede subir. Nunca bajar.

    Retorna: (rules_triggered, final_level)
    """
    triggered: list[str] = []
    final_level = base_level

    for rule_id, condition_fn, forced_level, blocks_total in ORDERED_OVERRIDE_RULES:
        if condition_fn(policy, context, params):
            triggered.append(rule_id)

            if blocks_total:
                return triggered, "blocked"

            if _level_rank(forced_level) > _level_rank(final_level):
                final_level = forced_level

    return triggered, final_level


def _filter_tools_by_context(
    allowed_tools: list[str],
    context: RiskContext,
    final_level: str,
) -> list[str]:
    """
    Filtra las herramientas disponibles según el contexto del sistema.
    Devuelve la lista ordenada: herramientas disponibles primero.
    """
    availability = {
        "deerflow":           True,       # asume disponible (health check en arbitration)
        "scrapegraph":        True,
        "llm_lightweight":    True,
        "flow_director":      context.chrome_available,
        "comfyui":            context.comfyui_available,
        "fooocus":            context.comfyui_available,
        "playwright_mcp":     context.chrome_available,
        "browser_use":        True,
        "tiktok_playwright":  context.chrome_available,
        "instagram_instagrapi": True,
        "gmail_mcp":          True,
        "whatsapp_executor":  True,
        "filesystem_mcp":     True,
        "hermes_status":      True,
        "x_api":              True,
        "notion_mcp":         True,
        "github_mcp":         True,
    }

    # Red level: excluir herramientas que requieren Chrome si no está disponible
    if final_level == "red" and not context.chrome_available:
        allowed_tools = [t for t in allowed_tools if t not in ("tiktok_playwright", "playwright_mcp")]

    return [t for t in allowed_tools if availability.get(t, True)]


def _build_reason(
    policy: dict,
    base_score: int,
    context_delta: int,
    final_level: str,
    overrides: list[str],
    context: RiskContext,
) -> str:
    """Genera explicación en español simple."""
    parts = []

    if final_level == "blocked":
        return "Esta acción está bloqueada permanentemente por reglas de seguridad."

    if overrides:
        override_reasons = {
            "OR-001": "expone datos personales",
            "OR-003": "es permanente e irreversible",
            "OR-004": "borra archivos",
            "OR-005": "afecta el sistema",
            "OR-006": "modifica configuración crítica",
            "OR-007": "involucra información privada",
            "OR-008": "contiene credenciales o tokens",
        }
        triggered_msgs = [override_reasons.get(r, r) for r in overrides]
        parts.append(f"Requiere confirmación porque {' y '.join(triggered_msgs)}.")

    if context.in_automated_loop:
        parts.append("Se ejecuta en modo automático (+cuidado).")

    if context.hernán_offline_minutes > 120:
        parts.append("Hernán está offline hace más de 2 horas.")

    if context.skill_last_failed:
        parts.append("La última ejecución de esta acción falló.")

    if not parts:
        level_msgs = {
            "green": "Acción segura. Sin efectos permanentes.",
            "yellow": "Acción con efecto visible. Te aviso cuando termine.",
            "red": "Acción con impacto externo o difícil de revertir.",
        }
        parts.append(level_msgs.get(final_level, "Evaluando acción."))

    return " ".join(parts)


def _gate_from_level(final_level: str, policy: dict) -> tuple[GateDecision, bool]:
    """
    Convierte nivel semáforo → decisión de gate.
    Retorna (GateDecision, needs_confirm).
    """
    if final_level == "blocked":
        return GateDecision.BLOCK, False
    if final_level == "red":
        return GateDecision.CONFIRM, True
    if final_level == "yellow":
        return GateDecision.NOTIFY, False
    return GateDecision.PROCEED, False


# ─── FUNCIÓN PRINCIPAL ──────────────────────────────────────────────────────

def score_intent(intent: dict, context: RiskContext | None = None) -> RiskResult:
    """
    Función principal del Risk Engine.
    Determinística: mismo input → siempre mismo output.

    Args:
        intent:  Output de hermes_core.classify()
                 {pipeline, action, params, confidence, raw}
        context: Estado del sistema. Si None, usa defaults conservadores.

    Returns:
        RiskResult con todo lo necesario para que el gate decida.
    """
    if context is None:
        # Defaults conservadores: asume Hernán offline, primer run
        context = RiskContext(hernán_online=False, hernán_offline_minutes=999)

    pipeline = intent.get("pipeline", "system")
    action   = intent.get("action", "answer_question")
    params   = intent.get("params", {})

    # 1. Obtener política de la skill
    policy = SKILL_POLICIES.get((pipeline, action), _DEFAULT_POLICY)

    # 2. Score base 3D (determinístico)
    base_score = (
        AUTONOMY_SCORE.get(policy.get("execution_autonomy", "medium"), 2)
        + EXTERNAL_IMPACT_SCORE.get(policy.get("external_impact", False), 0)
        + IRREVERSIBILITY_SCORE.get(policy.get("irreversibility", "low"), 1)
    )

    # 3. Modificadores de contexto
    context_delta = _context_modifiers(policy, context)
    final_score   = base_score + context_delta

    # 4. Nivel base desde score
    base_level = _score_to_level(final_score)

    # 5. Aplicar override rules (solo pueden SUBIR el nivel)
    overrides, final_level = _apply_overrides(policy, context, params, base_level)

    # 6. Gate decision
    gate, needs_confirm = _gate_from_level(final_level, policy)

    # 7. Herramientas permitidas (filtradas por contexto)
    allowed_tools = _filter_tools_by_context(
        policy.get("allowed_tools", []),
        context,
        final_level,
    )

    # 8. Mensajes
    reason = _build_reason(policy, base_score, context_delta, final_level, overrides, context)

    # Construir confirm_message con params interpolados
    confirm_template = policy.get("confirm_message", "")
    notify_template  = policy.get("notify_message", "")
    try:
        confirm_message = confirm_template.format(**params) if confirm_template else ""
        notify_message  = notify_template.format(**params)  if notify_template  else ""
    except (KeyError, ValueError):
        confirm_message = confirm_template
        notify_message  = notify_template

    return RiskResult(
        pipeline=pipeline,
        action=action,
        base_score=base_score,
        context_delta=context_delta,
        final_score=final_score,
        base_level=base_level,
        final_level=final_level,
        overrides_triggered=overrides,
        gate=gate,
        needs_confirm=needs_confirm,
        blocked=(final_level == "blocked"),
        reason=reason,
        confirm_message=confirm_message,
        notify_message=notify_message,
        allowed_tools=allowed_tools,
    )


# ─── PRE-EXECUTION GATE ─────────────────────────────────────────────────────

def pre_execution_gate(result: RiskResult) -> tuple[bool, str]:
    """
    Gate que se ejecuta ANTES de cualquier tool.
    Debe estar en la capa de risk, NO dentro de execution.

    Returns:
        (can_proceed: bool, message: str)

        can_proceed=True  → el dispatcher puede llamar al executor
        can_proceed=False → el dispatcher PARA, devuelve message a Hernán

    IMPORTANTE: Si can_proceed=False con needs_confirm=True,
    el dispatcher debe esperar respuesta de Hernán y re-evaluar.
    """
    if result.gate == GateDecision.BLOCK:
        return False, f"🚫 {result.reason}"

    if result.gate == GateDecision.CONFIRM:
        msg = result.confirm_message or (
            f"Quiero ejecutar: *{result.action}*\n"
            f"Motivo: {result.reason}\n"
            f"¿Qué prefieres?\n  A) Sí, hazlo\n  B) No, cancela"
        )
        return False, msg

    # PROCEED o NOTIFY — puede ejecutar
    return True, ""


# ─── HELPERS DE DIAGNÓSTICO ─────────────────────────────────────────────────

def explain_result(result: RiskResult) -> str:
    """
    Formatea RiskResult como texto legible para debugging.
    No se usa en producción, solo para diagnóstico.
    """
    emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴", "blocked": "🚫"}.get(
        result.final_level, "❓"
    )
    lines = [
        f"{emoji} [{result.pipeline}.{result.action}]",
        f"   Score base: {result.base_score} | Contexto: +{result.context_delta} | Total: {result.final_score}",
        f"   Nivel: {result.base_level} → {result.final_level}",
        f"   Gate: {result.gate.value} | Confirm: {result.needs_confirm}",
    ]
    if result.overrides_triggered:
        lines.append(f"   Overrides: {', '.join(result.overrides_triggered)}")
    if result.allowed_tools:
        lines.append(f"   Tools: {', '.join(result.allowed_tools)}")
    lines.append(f"   Razón: {result.reason}")
    return "\n".join(lines)


# ─── QUICK TEST ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test 1: Research (verde, sin contexto especial)
    intent_research = {"pipeline": "research", "action": "product_research",
                       "params": {"topic": "auriculares Amazon"}, "confidence": "pattern"}
    ctx_online = RiskContext(hernán_online=True, skill_total_runs=5, skill_success_rate=0.9)
    r1 = score_intent(intent_research, ctx_online)
    print(explain_result(r1))

    # Test 2: Post TikTok (rojo — publicación externa)
    intent_post = {"pipeline": "social_poster", "action": "post_tiktok",
                   "params": {"output_path": "/RENDER/video.mp4"}, "confidence": "pattern"}
    r2 = score_intent(intent_post, ctx_online)
    print(explain_result(r2))

    # Test 3: Borrar archivo (rojo + override OR-004)
    intent_delete = {"pipeline": "system", "action": "delete_file",
                     "params": {"filepath": "/important/data.json", "reason": "liberar espacio"},
                     "confidence": "pattern"}
    r3 = score_intent(intent_delete, ctx_online)
    print(explain_result(r3))

    # Test 4: Email en loop automático (rojo elevado por contexto)
    intent_email = {"pipeline": "email", "action": "send_email",
                    "params": {"recipient": "cliente@example.com", "subject": "Oferta"},
                    "confidence": "llm"}
    ctx_auto = RiskContext(hernán_online=False, hernán_offline_minutes=180, in_automated_loop=True)
    r4 = score_intent(intent_email, ctx_auto)
    print(explain_result(r4))

    # Test 5: Status (verde siempre)
    intent_status = {"pipeline": "system", "action": "status",
                     "params": {}, "confidence": "pattern"}
    r5 = score_intent(intent_status, ctx_online)
    print(explain_result(r5))
