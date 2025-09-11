#!/usr/bin/env python3
"""
Modular Telegram Bot - Main Application
"""
import os
import logging
from datetime import datetime
from typing import Dict, List
import asyncio

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from config import bot_token, id_a, username, log_level
from core.auth import AuthManager
from core.command_loader import CommandLoader
from core.message_utils import send_chunked_text

# Configure logging
numeric_level = getattr(logging, log_level.upper(), logging.INFO)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=numeric_level,
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.auth_manager = AuthManager(id_a, username)
        self.command_loader = CommandLoader()
        self.commands = {}
        
    async def startup_message(self, app):
        """Send startup notification"""
        chat_id = id_a[0]
        msg = f"Hey, just woke up man! It is {datetime.now().strftime('%d %B %Y - %I:%M %p')}"
        await app.bot.send_message(chat_id=chat_id, text=msg)
    
    async def load_commands(self):
        """Load all available commands from plugins"""
        self.commands = await self.command_loader.load_all_commands()
        logger.info(f"Loaded {len(self.commands)} command categories")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main message handler"""
        message = update.effective_message
        user_id = message.from_user.id
        username_input = message.from_user.username
        is_bot = message.from_user.is_bot
        command = message.text.strip()

        logger.info(f"Got command: {command}")

        # Authentication check
        if not self.auth_manager.is_authorised(user_id, username_input, is_bot):
            await message.reply_text('Forbidden access!')
            return

        # Process command through loaded handlers
        handled = False
        for category, handler in self.commands.items():
            try:
                if await handler.can_handle(command):
                    await handler.execute(message, command)
                    handled = True
                    break
            except Exception as e:
                logger.error(f"Error in {category} handler: {e}")
                await message.reply_text(f"Error executing command: {str(e)}")
                handled = True
                break
        
        if not handled:
            await self.show_help(message)
    
    async def show_help(self, message):
        """Show available commands"""
        help_text = "Commands available:\n"
        for category, handler in self.commands.items():
            commands = await handler.get_help()
            if commands:
                help_text += f"\n{commands}"
        
        await send_chunked_text(message, help_text)
    
    async def run(self):
        """Start the bot"""
        await self.load_commands()
        
        app = ApplicationBuilder().token(bot_token).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        
        await self.startup_message(app)
        await app.run_polling()

async def main():
    bot = TelegramBot()
    await bot.run()

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())