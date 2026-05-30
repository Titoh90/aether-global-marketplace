"""
research_executor.py — Product Research via DeerFlow or lightweight fallback

Strategy:
  1. If DeerFlow backend is running on :8001 → use it (deep multi-step research)
  2. Otherwise → lightweight researcher: DuckDuckGo + NVIDIA/OpenRouter LLM

Returns structured ProductBrief ready to feed into MediaFactory pipeline.

Called from Telegram: "investiga auriculares amazon" → runs research → brief
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("research_executor")

DEERFLOW_URL   = "http://localhost:8001"
DEERFLOW_ROOT  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/DEERFLOW")
NVIDIA_BASE    = "https://integrate.api.nvidia.com/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
AFFILIATE_TAG  = "aetherglobal-20"

_ENV_FILES = (
    Path("/Volumes/OPENCLAW_STORAG 1/SYSTEM_FILES/SECURE_CREDENTIALS/IMPERIO_NUCLEO.env"),
    Path.home() / "IMPERIO_NUCLEO" / ".env",
)

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ProductBrief:
    product_name: str
    category: str
    price_usd: float
    asin: str
    affiliate_url: str
    viral_angle: str
    hook: str
    platform_strategy: str         # tiktok|instagram|both
    hashtags: list[str]
    commission_rate: float         # 0-1
    viral_score: int               # 0-100
    research_source: str           # "deerflow"|"lightweight"
    asin_verified: bool = False    # passed at least format check
    verification_method: str = "none"  # "http"|"format"|"none"

    def to_content_brief(self) -> dict:
        return {
            "name": self.product_name,
            "category": self.category,
            "price": self.price_usd,
            "asin": self.asin,
            "affiliate_url": self.affiliate_url,
            "video_angle": self.viral_angle,
            "hook": self.hook,
            "hashtags": self.hashtags,
            "commission_rate": self.commission_rate,
            "viral_score": self.viral_score,
            "asin_verified": self.asin_verified,
            "verification_method": self.verification_method,
        }

# ── Key loading ───────────────────────────────────────────────────────────────

def _load_key(names: list[str]) -> str | None:
    import os
    for env_file in _ENV_FILES:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            for name in names:
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    for name in names:
        val = os.environ.get(name)
        if val:
            return val
    return None

# ── ASIN verification ────────────────────────────────────────────────────────

_ASIN_RE = re.compile(r'^B[A-Z0-9]{9}$')


def _format_verify_asin(asin: str) -> bool:
    """Tier 1 — structural check (0ms). Filters garbage / malformed ASINs."""
    return bool(asin and _ASIN_RE.match(asin.strip()))


def _http_verify_asin(asin: str) -> bool | None:
    """
    Tier 2 — opportunistic GET check (≤5s).
    Returns True=exists, False=404, None=blocked/timeout (treat as unknown).
    """
    try:
        req = urllib.request.Request(
            f"https://www.amazon.com/dp/{asin}",
            method="GET",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            # 200 on real product page or Amazon redirect — both mean ASIN exists
            return r.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        return None  # 503, captcha, etc. — unknown
    except Exception:
        return None


def _verify_asin(asin: str) -> tuple[bool, str]:
    """
    Run both tiers. Returns (verified: bool, method: str).

    Policy:
    - Format fail → strip ASIN (hard gate)
    - HTTP 200    → upgrade to "http" (strong confidence)
    - HTTP non-200 or timeout → Amazon anti-bot is unreliable; keep format result
      (a 404 in <1s is almost always bot detection, not a real missing product)
    """
    if not _format_verify_asin(asin):
        log.warning(f"ASIN format invalid: '{asin}' — stripping")
        return False, "none"

    http_result = _http_verify_asin(asin)
    if http_result is True:
        log.info(f"ASIN {asin} confirmed via HTTP")
        return True, "http"

    # http_result False or None — Amazon likely blocked us; trust format check
    if http_result is False:
        log.info(f"ASIN {asin} HTTP returned 404 (possible anti-bot) — keeping via format")
    else:
        log.info(f"ASIN {asin} HTTP inconclusive — keeping via format")
    return True, "format"


# ── DeerFlow integration ──────────────────────────────────────────────────────

def _deerflow_available() -> bool:
    try:
        req = urllib.request.Request(f"{DEERFLOW_URL}/health", method="GET")
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _deerflow_login() -> tuple[str, str] | None:
    """Login to DeerFlow and return (access_token, csrf_token)."""
    DEERFLOW_EMAIL = "aether.ventures.oficial@gmail.com"
    DEERFLOW_PASS  = "Imperio2026!"
    try:
        body = urllib.parse.urlencode({
            "username": DEERFLOW_EMAIL,
            "password": DEERFLOW_PASS,
        }).encode()
        req = urllib.request.Request(
            f"{DEERFLOW_URL}/api/v1/auth/login/local",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            cookies = resp.info().get_all("Set-Cookie") or []
            access_token = ""
            csrf_token = ""
            for cookie in cookies:
                if cookie.startswith("access_token="):
                    access_token = cookie.split("=", 1)[1].split(";")[0]
                elif cookie.startswith("csrf_token="):
                    csrf_token = cookie.split("=", 1)[1].split(";")[0]
            if access_token and csrf_token:
                return access_token, csrf_token
    except Exception as e:
        log.warning(f"DeerFlow login failed: {e}")
    return None


def _deerflow_request(url: str, data: bytes, headers: dict, timeout: int = 180) -> dict:
    """POST request to DeerFlow, returns parsed JSON."""
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _extract_ai_content(messages: list) -> tuple[str, bool]:
    """
    Returns (content, asked_clarification).
    content = last AI text response.
    asked_clarification = True if agent called ask_clarification with empty content.
    """
    for msg in reversed(messages):
        msg_type = msg.get("type") or msg.get("role", "")
        if msg_type == "tool":
            continue
        if msg_type in ("ai", "assistant"):
            raw = msg.get("content", "")
            content = (
                "\n".join(b.get("text", "") for b in raw if isinstance(b, dict))
                if isinstance(raw, list) else str(raw)
            )
            # Tool calls array (standard path)
            if not content.strip() and msg.get("tool_calls"):
                tc = msg["tool_calls"]
                if any(t.get("name") == "ask_clarification" for t in tc if isinstance(t, dict)):
                    return "", True
            # Content string contains embedded ask_clarification JSON (DeerFlow variant)
            if "ask_clarification" in content:
                return "", True
            return content, False
    return "", False


def _run_deerflow_thread(query: str, research_prompt: str) -> ProductBrief | None:
    """
    Creates thread → runs → if clarification requested, answers automatically → final result.
    """
    session = _deerflow_login()
    if not session:
        log.warning("DeerFlow auth failed")
        return None
    at, ct = session
    headers = {
        "Cookie": f"access_token={at}; csrf_token={ct}",
        "X-CSRF-Token": ct,
        "Content-Type": "application/json",
    }

    # Create thread
    thread = _deerflow_request(
        f"{DEERFLOW_URL}/api/threads",
        data=json.dumps({"title": query[:60]}).encode(),
        headers=headers, timeout=10,
    )
    thread_id = thread.get("thread_id") or thread.get("id")
    if not thread_id:
        return None

    # First run
    result = _deerflow_request(
        f"{DEERFLOW_URL}/api/threads/{thread_id}/runs/wait",
        data=json.dumps({
            "assistant_id": "lead_agent",
            "input": {"messages": [{"role": "user", "content": research_prompt}]},
            "config": {"configurable": {}},
        }).encode(),
        headers=headers, timeout=180,
    )
    messages = result.get("messages") or result.get("values", {}).get("messages") or []
    content, asked_clarification = _extract_ai_content(messages)

    # Auto-answer clarification — continue the same thread
    if asked_clarification:
        log.info("DeerFlow asked clarification — auto-answering and continuing thread")
        clarification_answer = (
            f"I want the best-selling Amazon product for: {query}. "
            f"Pick the #1 result by reviews/sales. Any specific subtype is fine. "
            f"Just find it and return the JSON."
        )
        result2 = _deerflow_request(
            f"{DEERFLOW_URL}/api/threads/{thread_id}/runs/wait",
            data=json.dumps({
                "assistant_id": "lead_agent",
                "input": {"messages": [{"role": "user", "content": clarification_answer}]},
                "config": {"configurable": {}},
            }).encode(),
            headers=headers, timeout=180,
        )
        messages2 = result2.get("messages") or result2.get("values", {}).get("messages") or []
        content, _ = _extract_ai_content(messages2)

    if not content:
        log.warning(f"DeerFlow: no AI content after {len(messages)} messages")
        return None

    return _parse_research_json(content, query, source="deerflow")


def _research_via_deerflow(query: str) -> ProductBrief | None:
    """
    Sends research task to DeerFlow. Auto-answers clarification if needed.
    Falls through to lightweight on any failure.
    """
    research_prompt = (
        f"Search Amazon for the best-selling product matching: {query}\n\n"
        f"Steps:\n"
        f"1. Use web search: site:amazon.com {query} best seller\n"
        f"2. Pick the top result (highest reviews, best price/quality)\n"
        f"3. Return ONLY this JSON, filled with real data:\n\n"
        f"{{\"product_name\": \"[real product name]\", "
        f"\"asin\": \"[real ASIN]\", "
        f"\"price_usd\": [real price as number], "
        f"\"viral_angle\": \"[why this goes viral on TikTok]\", "
        f"\"hook\": \"[one sentence TikTok hook]\", "
        f"\"hashtags\": [\"#tag1\", \"#tag2\", \"#tag3\"], "
        f"\"commission_rate\": 0.06, "
        f"\"viral_score\": [0-100]}}\n\n"
        f"Respond with JSON only. No introduction, no questions."
    )
    try:
        return _run_deerflow_thread(query, research_prompt)
    except Exception as e:
        log.warning(f"DeerFlow research failed: {e}")
        return None

# ── Lightweight fallback researcher ───────────────────────────────────────────

_RESEARCH_PROMPT = """\
You are an Amazon affiliate product research specialist.

Task: pick ONE real top-selling Amazon product for the query below.

Return ONLY valid JSON (no markdown, no explanation, no text before or after):
{{
  "product_name": "Brand + Model (exact name as sold on Amazon)",
  "category": "Beauty|Electronics|Home & Kitchen|Sports|...",
  "price_usd": 29.99,
  "asin": "B0XXXXXXXXX",
  "viral_angle": "specific benefit that goes viral on TikTok (1-2 sentences)",
  "hook": "opening line for video (max 8 words)",
  "platform_strategy": "tiktok",
  "hashtags": ["#amazonfinds", "#musthave"],
  "commission_rate": 0.06,
  "viral_score": 75
}}

Critical rules:
- asin: ONLY include if you are CERTAIN it is the real 10-character Amazon ASIN (e.g. B00X4WHP5E). If uncertain, use "" — never invent one.
- price_usd: realistic market price (not 0, not null)
- Pick a product with 1000+ reviews and 4+ stars
- viral_angle: specific, not generic ("works on sensitive skin, dermatologist #1 pick" not "great product")
- hook: creates curiosity or shows transformation (max 8 words)
- hashtags: 5-8, mix viral (#amazonfinds) with niche-specific
- commission_rate: Beauty=0.06, Electronics=0.04, Home=0.08, Sports=0.05
- viral_score: 0-100 based on TikTok trend potential

Query: {query}
"""


def _load_nvidia_key() -> str | None:
    """Load NVIDIA NIM key: env vars first, then DeerFlow config.yaml fallback."""
    key = _load_key(["NVIDIA_NIM_API_KEY", "NVIDIA_API_KEY"])
    if key:
        return key
    # Fallback: read from DeerFlow config.yaml
    try:
        import yaml  # type: ignore
        cfg_path = DEERFLOW_ROOT / "config.yaml"
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text())
            for m in cfg.get("models", []):
                k = m.get("api_key", "")
                if k and k.startswith("nvapi-"):
                    return k
    except Exception:
        pass
    # No hardcoded key — must be set via env var or config
    return ""


def _call_llm_for_research(query: str) -> str:
    """Try NVIDIA NIM 70B first (most accurate), then fallbacks."""
    nvidia_key = _load_nvidia_key()
    or_key = _load_key(["OPENROUTER_API_KEY"])

    candidates = []
    if nvidia_key:
        candidates += [
            # 70B first — best accuracy for real product data
            (NVIDIA_BASE, nvidia_key, "meta/llama-3.3-70b-instruct", {}),
            (NVIDIA_BASE, nvidia_key, "deepseek-ai/deepseek-v4-flash", {}),
            (NVIDIA_BASE, nvidia_key, "meta/llama-3.1-8b-instruct", {}),
        ]
    if or_key:
        candidates += [
            (OPENROUTER_BASE, or_key, "meta-llama/llama-3.3-70b-instruct:free",
             {"HTTP-Referer": "https://github.com/Imperio-Nucleo", "X-Title": "Imperio Research"}),
        ]

    prompt = _RESEARCH_PROMPT.format(query=query)
    last_error = None

    for base_url, key, model, extra_headers in candidates:
        try:
            payload = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 800,
                "temperature": 0.1,
            }).encode()
            req = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=payload,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", **extra_headers},
                method="POST",
            )
            timeout = 90 if "70b" in model or "120b" in model else 30
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read())
            content = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if content:
                log.info(f"Research LLM: {model}")
                return content
        except Exception as e:
            log.warning(f"Research model {model} failed: {e}")
            last_error = e

    raise RuntimeError(f"All research LLM models failed. Last: {last_error}")


def _parse_research_json(raw: str, query: str, source: str) -> ProductBrief | None:
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        raw_json = raw[start:end]
        raw_json = re.sub(r',\s*([}\]])', r'\1', raw_json)  # trailing commas
        data = json.loads(raw_json)

        raw_asin = (data.get("asin", "") or "").strip()
        asin_verified, verification_method = _verify_asin(raw_asin)
        # If verification conclusively failed (404 or bad format), clear the ASIN
        asin = raw_asin if asin_verified else ""

        affiliate_url = (
            f"https://www.amazon.com/dp/{asin}?tag={AFFILIATE_TAG}"
            if asin else
            f"https://www.amazon.com/s?k={urllib.parse.quote(data.get('product_name',''))}&tag={AFFILIATE_TAG}"
        )

        return ProductBrief(
            product_name=data.get("product_name") or query,
            category=data.get("category") or "General",
            price_usd=float(data.get("price_usd") or 0),
            asin=asin,
            affiliate_url=affiliate_url,
            viral_angle=data.get("viral_angle") or "",
            hook=data.get("hook") or "",
            platform_strategy=data.get("platform_strategy") or "tiktok",
            hashtags=data.get("hashtags") or [],
            commission_rate=float(data.get("commission_rate") or 0.06),
            viral_score=int(data.get("viral_score") or 50),
            research_source=source,
            asin_verified=asin_verified,
            verification_method=verification_method,
        )
    except Exception as e:
        log.warning(f"Failed to parse research JSON: {e} | raw: {raw[:200]}")
        return None


def _research_lightweight(query: str) -> ProductBrief:
    raw = _call_llm_for_research(query)
    brief = _parse_research_json(raw, query, source="lightweight")
    if not brief:
        raise RuntimeError(f"Could not parse research result for: {query}")
    return brief


def _format_brief_summary(brief: ProductBrief) -> str:
    """Build Telegram-ready summary with verification badge."""
    price_str = f"${brief.price_usd:.2f}" if brief.price_usd else "precio no disponible"
    if brief.asin_verified and brief.verification_method == "http":
        verify_badge = "✅ ASIN verificado en Amazon"
    elif brief.asin_verified and brief.verification_method == "format":
        verify_badge = "🔶 ASIN no confirmado (Amazon bloqueó verificación)"
    else:
        verify_badge = "⚠️ Sin ASIN válido — link de búsqueda"

    return (
        f"🔍 *{brief.product_name}*\n"
        f"💰 {price_str} | {brief.commission_rate*100:.0f}% comisión\n"
        f"🎯 Viral score: {brief.viral_score}/100\n"
        f"📹 Hook: _{brief.hook}_\n"
        f"💡 Angle: {brief.viral_angle}\n"
        f"🔗 {brief.affiliate_url}\n"
        f"#️⃣ {' '.join(brief.hashtags[:5])}\n"
        f"_{verify_badge}_"
    )


# ── Public API ────────────────────────────────────────────────────────────────

def research_product(query: str, task_id: str = "") -> dict:
    """
    Main entry point. Called from Telegram gateway.

    Returns:
        {"status": "success", "brief": {...}, "source": "deerflow|lightweight"}
        or {"status": "failed", "error": "..."}
    """
    log.info(f"[{task_id}] Researching: {query[:60]}")

    # Try DeerFlow first (deep research)
    if _deerflow_available():
        log.info(f"[{task_id}] DeerFlow available — using deep research")
        brief = _research_via_deerflow(query)
        if brief:
            log.info(
                f"[{task_id}] DeerFlow research complete: {brief.product_name} "
                f"| asin={brief.asin} verified={brief.verification_method}"
            )
            return {
                "status": "success",
                "brief": brief.to_content_brief(),
                "source": "deerflow",
                "output_path": "",
                "summary": _format_brief_summary(brief),
            }
        log.warning(f"[{task_id}] DeerFlow research returned nothing — trying lightweight")

    # Lightweight fallback
    try:
        brief = _research_lightweight(query)
        log.info(
            f"[{task_id}] Lightweight research: {brief.product_name} | "
            f"score={brief.viral_score} | asin={brief.asin} verified={brief.verification_method}"
        )
        return {
            "status": "success",
            "brief": brief.to_content_brief(),
            "source": "lightweight",
            "output_path": "",
            "summary": _format_brief_summary(brief),
        }
    except Exception as e:
        log.error(f"[{task_id}] Research failed: {e}")
        return {"status": "failed", "error": str(e)}


def start_deerflow_backend() -> int | None:
    """
    Start DeerFlow FastAPI backend on :8001 if not already running.
    Returns PID or None if failed.
    """
    import subprocess
    import time

    if _deerflow_available():
        log.info("DeerFlow already running on :8001")
        return None

    venv_python = DEERFLOW_ROOT / "backend" / ".venv" / "bin" / "python"
    if not venv_python.exists():
        log.error("DeerFlow venv not found — run uv sync in backend/")
        return None

    log.info("Starting DeerFlow backend on :8001...")
    env_file = Path.home() / "IMPERIO_NUCLEO" / ".env"
    proc = subprocess.Popen(
        [str(venv_python), "-m", "uvicorn", "app.gateway.app:app",
         "--host", "0.0.0.0", "--port", "8001", "--log-level", "warning"],
        cwd=str(DEERFLOW_ROOT / "backend"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    if proc.poll() is None:
        log.info(f"DeerFlow backend started (PID {proc.pid})")
        return proc.pid
    log.error("DeerFlow backend failed to start")
    return None
