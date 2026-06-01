#!/usr/bin/env python3
"""Modular Telegram Bot — runs scripts from builtin/ and scripts/."""
import os
import logging
import asyncio
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from config import bot_token, id_a, username, log_level
from core.auth import AuthManager
from core import commands as registry
from core.output import send_output, looks_like_url
from core.runner import run_command
from core.exec import ExecFeature

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUILTIN_DIR = os.path.join(BASE_DIR, "builtin")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, log_level.upper(), logging.INFO),
)
logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self):
        self.auth = AuthManager(id_a, username)
        self.exec_feature = ExecFeature()
        self.commands = registry.discover([BUILTIN_DIR, SCRIPTS_DIR])
        logger.info("Loaded %d commands: %s", len(self.commands), ", ".join(sorted(self.commands)))

    async def startup_message(self, app):
        msg = f"Hey, just woke up man! It is {datetime.now().strftime('%d %B %Y - %I:%M %p')}"
        await app.bot.send_message(chat_id=id_a[0], text=msg)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.effective_message
        user = message.from_user
        text = message.text.strip()
        logger.info("Got command: %s", text)

        if not self.auth.is_authorised(user.id, user.username, user.is_bot):
            await message.reply_text("Forbidden access!")
            return

        if self.exec_feature.handles(text):
            await self.exec_feature.handle(message, text)
            return

        if looks_like_url(text):
            text = f"url {text}"

        resolved = registry.resolve(text, self.commands)
        if resolved is None:
            await self.show_help(message)
            return

        cmd, args = resolved
        try:
            result = run_command([cmd.path] + args)
            await send_output(message, result)
        except Exception as e:
            logger.error("Error running %s: %s", cmd.name, e)
            await message.reply_text(f"Error executing command: {e}")

    async def show_help(self, message):
        lines = ["Commands available:"]
        for name in sorted(self.commands):
            c = self.commands[name]
            lines.append(f"  {name}" + (f" — {c.description}" if c.description else ""))
        lines.append("  exec <shell command> — run a command (email-verified)")
        await send_output(message, "\n".join(lines))

    async def run(self):
        app = ApplicationBuilder().token(bot_token).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        await self.startup_message(app)
        await app.run_polling()


async def main():
    await TelegramBot().run()


if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
