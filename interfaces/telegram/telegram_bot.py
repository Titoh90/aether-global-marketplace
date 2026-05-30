"""
telegram_bot.py — HERMES Telegram Control Center.

Async polling bot. Receives commands, dispatches to command_router,
sends reports and alerts. Uses existing BOT_TOKEN and CHAT_ID.

HERMES safety model applies:
- Read-only commands execute immediately
- State-changing commands require confirmation
- Forbidden actions are BLOCKED
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

import aiohttp

log = logging.getLogger("hermes.telegram")

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")

# Credentials — same as master_pipeline.py
BOT_TOKEN = "8668867221:AAEiKlkEWzeATpaBMLgu4cE0VhZi945evI8"
CHAT_ID = "5403253763"
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Only accept commands from authorized chat
AUTHORIZED_CHATS = {int(CHAT_ID)}


class HermesTelegramBot:
    """
    Async Telegram bot for HERMES supervisor control.

    Polls for updates, routes commands, sends alerts.
    Does NOT use webhooks — polling is simpler for local deployment.
    """

    def __init__(self):
        self._offset = 0
        self._running = False
        self._session: aiohttp.ClientSession | None = None
        self._command_handler: Callable | None = None
        self._question_handler: Callable | None = None
        self._poll_interval = 2.0  # seconds

    def set_command_handler(self, handler: Callable):
        """Set the command router function. Called with (command, args, chat_id)."""
        self._command_handler = handler

    def set_question_handler(self, handler: Callable):
        """Set the free-form question handler. Called with (question_text)."""
        self._question_handler = handler

    async def start(self):
        """Start polling loop."""
        self._running = True
        self._session = aiohttp.ClientSession()
        log.info("HERMES Telegram bot starting...")

        # Send startup message
        await self.send_message("HERMES online. /help para comandos.")

        try:
            while self._running:
                try:
                    await self._poll()
                except Exception as e:
                    log.error(f"Poll error: {e}")
                    await asyncio.sleep(5)
                await asyncio.sleep(self._poll_interval)
        finally:
            await self._session.close()

    async def stop(self):
        """Stop polling loop."""
        self._running = False
        log.info("HERMES Telegram bot stopping...")

    async def _poll(self):
        """Fetch new updates from Telegram."""
        url = f"{API_BASE}/getUpdates"
        params = {"offset": self._offset, "timeout": 10}

        async with self._session.get(url, params=params) as resp:
            if resp.status != 200:
                return
            data = await resp.json()

        if not data.get("ok"):
            return

        for update in data.get("result", []):
            self._offset = update["update_id"] + 1
            await self._handle_update(update)

    async def _handle_update(self, update: dict):
        """Process a single update."""
        message = update.get("message") or update.get("callback_query", {}).get("message")
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        if chat_id not in AUTHORIZED_CHATS:
            log.warning(f"Unauthorized chat: {chat_id}")
            return

        text = message.get("text", "").strip()
        if not text:
            return

        if text.startswith("/"):
            # Parse command and args
            parts = text.split(maxsplit=1)
            command = parts[0].lower().split("@")[0]  # strip @botname
            args = parts[1] if len(parts) > 1 else ""

            log.info(f"Command: {command} args='{args}' from chat={chat_id}")

            if self._command_handler:
                try:
                    response = await self._command_handler(command, args, chat_id)
                    if response:
                        await self.send_message(response, chat_id=chat_id)
                except Exception as e:
                    log.error(f"Command handler error: {e}")
                    await self.send_message(
                        f"Error procesando {command}: {str(e)[:200]}",
                        chat_id=chat_id,
                    )
        else:
            # Free-form question → executive agent
            if self._question_handler:
                try:
                    response = await self._question_handler(text)
                    if response:
                        await self.send_message(response, chat_id=chat_id)
                except Exception as e:
                    log.error(f"Question handler error: {e}")
                    await self.send_message(
                        f"Error: {str(e)[:200]}",
                        chat_id=chat_id,
                    )

    async def send_message(
        self,
        text: str,
        chat_id: int | str = None,
        parse_mode: str = None,
    ) -> dict | None:
        """Send text message to chat."""
        chat_id = chat_id or CHAT_ID
        url = f"{API_BASE}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text[:4096],  # Telegram limit
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            async with self._session.post(url, json=payload) as resp:
                result = await resp.json()
                if not result.get("ok"):
                    log.error(f"Send failed: {result}")
                return result
        except Exception as e:
            log.error(f"Send error: {e}")
            return None

    async def send_alert(
        self,
        title: str,
        body: str,
        severity: str = "info",
    ):
        """Send formatted alert message."""
        icon = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🔵",
            "info": "⚪",
        }.get(severity, "⚪")

        msg = f"{icon} {title}\n\n{body}"
        await self.send_message(msg)

    async def send_approval_request(
        self,
        incident_id: str,
        title: str,
        details: str,
        recommended_action: str,
    ) -> dict | None:
        """Send approval request with inline keyboard."""
        text = (
            f"🔐 APROBACION REQUERIDA\n\n"
            f"Incidente: {title}\n"
            f"{details}\n\n"
            f"Accion recomendada: {recommended_action}\n\n"
            f"Responder:\n"
            f"/approve {incident_id}\n"
            f"/reject {incident_id}"
        )
        return await self.send_message(text)


# Singleton
_bot: HermesTelegramBot | None = None


def get_bot() -> HermesTelegramBot:
    global _bot
    if _bot is None:
        _bot = HermesTelegramBot()
    return _bot
