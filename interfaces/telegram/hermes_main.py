"""
hermes_main.py — Entry point for HERMES: Telegram bot + autonomous loop.

Usage:
    python3 interfaces/telegram/hermes_main.py          # full (bot + autonomous)
    python3 interfaces/telegram/hermes_main.py --bot     # bot only
    python3 interfaces/telegram/hermes_main.py --auto    # autonomous only
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ensure IMPERIO_ROOT is in path
IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
sys.path.insert(0, str(IMPERIO_ROOT))

from interfaces.telegram.telegram_bot import get_bot
from interfaces.telegram.command_router import CommandRouter
from interfaces.telegram.alert_dispatcher import get_dispatcher
from executive_layer.executive_agent import ExecutiveAgent
from executive_layer.autonomous_loop import AutonomousLoop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("hermes")


async def main():
    """Start HERMES: Telegram bot + autonomous background agent."""
    mode = "full"
    if "--bot" in sys.argv:
        mode = "bot"
    elif "--auto" in sys.argv:
        mode = "auto"

    log.info(f"Initializing HERMES (mode={mode})...")

    # 1. Bot
    bot = get_bot()

    # 2. Command router
    router = CommandRouter()
    bot.set_command_handler(router.handle)

    # 3. Executive agent — free-form questions
    agent = ExecutiveAgent()
    bot.set_question_handler(agent.answer)

    # 4. Alert dispatcher — connect to event bus
    dispatcher = get_dispatcher()
    dispatcher.connect(bot)
    dispatcher.register_handlers()

    # 5. Autonomous loop
    auto_loop = AutonomousLoop()
    auto_loop.connect_telegram(bot)

    if mode == "bot":
        log.info("HERMES bot-only mode. Starting Telegram polling...")
        await bot.start()
    elif mode == "auto":
        log.info("HERMES autonomous-only mode. Starting background agent...")
        await auto_loop.start()
    else:
        # Full mode — run both concurrently
        log.info("HERMES full mode. Bot + autonomous agent running...")
        await asyncio.gather(
            bot.start(),
            auto_loop.start(),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("HERMES shutdown.")
