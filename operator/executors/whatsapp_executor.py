"""
whatsapp_executor.py — OpenWA REST API wrapper for IMPERIO Operator
Sends WhatsApp messages via self-hosted OpenWA gateway.

Setup required (once):
  bash ~/IMPERIO_NUCLEO/docker/setup_openwa.sh
  → scan QR → session 'hvac-outreach' ready

Usage from gateway:
  /whatsapp 5215512345678 Hola, tenemos leads HVAC calificados...
  /wa_broadcast leads.txt "Mensaje de campaña"
"""

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

log = logging.getLogger("whatsapp_executor")

OPENWA_URL    = "http://localhost:2785/api"
OPENWA_APIKEY = "openwa-imperio-key-2026"
SESSION_NAME  = "hvac-outreach"
LOGS_DIR      = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/logs/whatsapp")


def _req(method: str, endpoint: str, body: dict = None) -> dict:
    """Make authenticated request to OpenWA API."""
    url = f"{OPENWA_URL}{endpoint}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": OPENWA_APIKEY,
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()[:300]
        raise RuntimeError(f"OpenWA HTTP {e.code}: {body_txt}")
    except Exception as e:
        raise RuntimeError(f"OpenWA request failed: {e}")


def openwa_active() -> bool:
    """Check if OpenWA API is reachable."""
    try:
        _req("GET", "/health")
        return True
    except Exception:
        return False


def session_active(session: str = SESSION_NAME) -> bool:
    """Check if WhatsApp session is authenticated."""
    try:
        s = _req("GET", f"/sessions/{session}")
        return s.get("status") in ("CONNECTED", "authenticated", "ready")
    except Exception:
        return False


def get_qr(session: str = SESSION_NAME) -> str:
    """Get QR code for WhatsApp session (base64 PNG)."""
    try:
        r = _req("POST", "/sessions", {"name": session})
    except Exception:
        pass  # session may already exist
    try:
        r = _req("GET", f"/sessions/{session}/qr")
        return r.get("qr") or r.get("data") or "No QR in response"
    except Exception as e:
        return f"QR error: {e}"


def send_message(phone: str, text: str, session: str = SESSION_NAME) -> dict:
    """
    Send WhatsApp text message.
    phone: international format without + (e.g. '15305551234')
    Returns result dict with status/messageId.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    if not openwa_active():
        return {"status": "failed", "error": "OpenWA not running. Run setup_openwa.sh first."}

    if not session_active(session):
        return {
            "status": "failed",
            "error": f"Session '{session}' not authenticated. Scan QR at http://localhost:2786"
        }

    # WhatsApp chat ID format: {phone}@c.us
    chat_id = f"{phone}@c.us" if "@" not in phone else phone

    try:
        result = _req("POST", f"/sessions/{session}/messages/send-text", {
            "chatId": chat_id,
            "text": text
        })
        log.info(f"WA sent → {phone}: {text[:60]}")
        _log_message(phone, text, "sent", result.get("id", ""))
        return {"status": "success", "phone": phone, "messageId": result.get("id")}
    except Exception as e:
        log.error(f"WA send failed → {phone}: {e}")
        return {"status": "failed", "error": str(e), "phone": phone}


def broadcast(contacts: list, message: str, session: str = SESSION_NAME,
              delay_s: float = 3.0) -> dict:
    """
    Send message to list of phone numbers with delay between sends.
    contacts: list of phone strings (international, no +)
    Returns summary dict.
    """
    import time
    results = {"sent": [], "failed": [], "total": len(contacts)}

    for phone in contacts:
        r = send_message(phone, message, session)
        if r["status"] == "success":
            results["sent"].append(phone)
        else:
            results["failed"].append({"phone": phone, "error": r.get("error", "")})
        if delay_s > 0:
            time.sleep(delay_s)

    results["success_rate"] = f"{len(results['sent'])}/{results['total']}"
    return results


def send_hvac_outreach(phone: str, business_name: str, city: str,
                       task_id: str = "") -> dict:
    """
    Pre-built HVAC lead machine outreach message.
    Customizes message per business.
    """
    message = (
        f"Hola {business_name}! 👋\n\n"
        f"Tenemos leads calificados de clientes buscando HVAC en {city}.\n\n"
        f"💼 *5 leads verificados* — $99 USD\n"
        f"✅ Clientes activos, con presupuesto confirmado\n"
        f"📍 Solo para tu zona ({city})\n\n"
        f"¿Te interesa hablar? Responde aquí o llámanos."
    )
    result = send_message(phone, message)
    result["campaign"] = "hvac_outreach"
    result["business"] = business_name
    result["city"] = city
    return result


def get_status() -> dict:
    """Return current OpenWA stack status."""
    active = openwa_active()
    session = session_active() if active else False
    return {
        "openwa_api": "running" if active else "down",
        "api_url": OPENWA_URL,
        "session": SESSION_NAME,
        "session_status": "connected" if session else "not_authenticated",
        "dashboard": "http://localhost:2886",
        "api_key": OPENWA_APIKEY,
    }


def _log_message(phone: str, text: str, direction: str, msg_id: str):
    """Append message to daily log file."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOGS_DIR / f"wa_{today}.jsonl"
        entry = {
            "ts": datetime.now().isoformat(),
            "direction": direction,
            "phone": phone,
            "text": text[:200],
            "msg_id": msg_id,
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
