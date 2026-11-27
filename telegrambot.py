#!/usr/bin/env python3
"""Modular Telegram Bot — runs scripts from builtin/ and scripts/."""
import os
import logging
import asyncio
from datetime import datetime

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from config import bot_token, id_a, username, log_level
from core.auth import AuthManager
from core import commands as registry
from core.output import send_output, looks_like_url, sanitise, chunk
from core import rich
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
# httpx logs every request URL at INFO, and Telegram URLs carry the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)


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
        if cmd.name == "url":
            await message.reply_text("Fetching URL, please wait...")
        await self.run_and_reply(cmd, args, message, "text", message.chat_id)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user = query.from_user
        if not self.auth.is_authorised(user.id, user.username, user.is_bot):
            await query.answer("Forbidden access!", show_alert=True)
            return
        data = (query.data or "").strip()
        logger.info("Got button: %s", data)
        resolved = registry.resolve(data, self.commands)
        if resolved is None or query.message is None:
            await query.answer("Unknown or expired button.", show_alert=True)
            return
        await query.answer()  # stops the spinner
        cmd, args = resolved
        await self.run_and_reply(cmd, args, query.message, "button", query.message.chat_id, query)

    async def run_and_reply(self, cmd, args, message, trigger, chat_id, query=None):
        try:
            env = rich.script_env(chat_id, trigger, message.message_id)
            result = run_command([cmd.path] + args, env=env)
            reply = rich.parse(result)
            if reply is None:
                await send_output(message, result)
            else:
                await self.send_rich(reply, message, trigger, query)
        except Exception as e:
            logger.error("Error running %s: %s", cmd.name, e)
            await message.reply_text(f"Error executing command: {e}")

    async def send_rich(self, reply, message, trigger, query=None):
        if reply.silent:
            return
        markup = rich.keyboard(reply)
        parts = chunk(sanitise(reply.text))
        if query is not None and rich.should_edit(reply, trigger):
            try:
                await query.edit_message_text(parts[0], reply_markup=markup)
                return
            except BadRequest as e:
                if "not modified" in str(e).lower():
                    return
                logger.warning("Edit failed (%s), sending a new message", e)
        for i, part in enumerate(parts):
            last = i == len(parts) - 1
            await message.reply_text(part, reply_markup=markup if last else None)

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
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        await self.startup_message(app)
        await app.run_polling()


async def main():
    await TelegramBot().run()


if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
