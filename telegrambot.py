#!/usr/bin/env python3
import os
import subprocess
import time
import smtplib
import asyncio
import logging
import string
import random
import re
from email.mime.text import MIMEText
from datetime import datetime

from config import (
    id_a,
    username,
    bot_token,
    recipient_email,
    email_address,
    email_password,
    smtp_server,
    smtp_port,
    log_level,
)

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
import asyncio
import nest_asyncio


# Configure logging using the config value
numeric_level = getattr(logging, log_level.upper(), logging.INFO)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=numeric_level,
)
logger = logging.getLogger(__name__)


# File paths
password_file = '/tmp/exec_password.txt'
attempt_file = '/tmp/exec_attempts.txt'
temp_command_file = '/tmp/temp_command.txt'
temp_script_path = '/tmp/temp-telegram-script.sh'
max_attempts = 3

# Telegram message length safety margin
# Telegram hard limit is 4096 chars. Stay below to allow for formatting overhead.
TELEGRAM_CHUNK_SIZE = 3500

# Path to helper script that fetches and cleans URLs.
# We resolve it relative to this file so the bot works wherever the repo lives.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FETCH_SCRIPT = os.path.join(SCRIPT_DIR, 'utils', 'fetch_clean_url.py')


# Startup message
async def startup_message(app):
    chat_id = id_a[0]
    msg = f"Hey, just woke up man! It is {datetime.now().strftime('%d %B %Y - %I:%M %p')}"
    await app.bot.send_message(chat_id=chat_id, text=msg)


# Email sender
def send_email(subject, body, to):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = email_address
    msg['To'] = to

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(email_address, email_password)
        server.sendmail(email_address, to, msg.as_string())


# Generate a random password
def generate_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for _ in range(length))


# Execute a shell command
def execute_command(command_list):
    try:
        result = subprocess.check_output(
            command_list,
            stderr=subprocess.STDOUT,
        ).decode('utf-8', errors='replace')
    except subprocess.CalledProcessError as e:
        result = e.output.decode('utf-8', errors='replace')
    except Exception as e:
        result = f'Error executing command: {str(e)}'
    return result


def is_url_like(text: str) -> bool:
    return bool(re.match(r'^\s*https?://', text, re.IGNORECASE))


def chunk_text_for_telegram(text: str, max_len: int = TELEGRAM_CHUNK_SIZE):
    """
    Split text into chunks that fit within Telegram message size limits.

    We try to split at newline boundaries. If a single line is longer than max_len,
    we do a hard split.
    """
    chunks = []
    buffer = []

    current_len = 0
    for line in text.splitlines(keepends=True):
        line_len = len(line)
        if current_len + line_len <= max_len:
            buffer.append(line)
            current_len += line_len
            continue

        # flush current buffer
        if buffer:
            chunks.append(''.join(buffer).rstrip())
            buffer = []
            current_len = 0

        # if the line itself is too long, hard-split it
        while line_len > max_len:
            chunks.append(line[:max_len])
            line = line[max_len:]
            line_len = len(line)

        if line:
            buffer.append(line)
            current_len = len(line)

    if buffer:
        chunks.append(''.join(buffer).rstrip())

    # Final guard - if somehow an empty list, ensure at least one chunk
    if not chunks:
        return [text[:max_len]]
    return chunks


async def send_chunked_text(message, text, chunk_size=TELEGRAM_CHUNK_SIZE):
    """Send long text in multiple Telegram-friendly chunks."""
    if not text:
        await message.reply_text('[no text returned]')
        return
    for chunk in chunk_text_for_telegram(text, chunk_size):
        await message.reply_text(chunk)


# Handle all messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat_id = message.chat_id
    user_id = message.from_user.id
    username_input = message.from_user.username
    is_bot = message.from_user.is_bot
    command = message.text.strip()

    logger.info(f"Got command: {command}")

    # Authorisation gate
    if user_id not in id_a or is_bot or username_input not in username:
        await message.reply_text('Forbidden access!')
        return

    # URL fetch branch
    # Accept any of:
    #   url <http://...>
    #   fetch <http://...>
    #   <http://...> (bare URL)
    lower_cmd = command.lower()
    url = None
    if lower_cmd.startswith('url '):
        url = command.split(' ', 1)[1].strip()
    elif lower_cmd.startswith('fetch '):
        url = command.split(' ', 1)[1].strip()
    elif is_url_like(command):
        url = command.strip()

    if url:
        # Run helper script
        if not os.path.exists(FETCH_SCRIPT) or not os.access(FETCH_SCRIPT, os.X_OK):
            await message.reply_text(f'Fetch script not found or not executable at {FETCH_SCRIPT}')
            return

        logger.info(f"Fetching URL: {url}")
        # We call python3 explicitly. If your venv python is required, change to sys.executable.
        result = execute_command(['python3', FETCH_SCRIPT, url])
        await send_chunked_text(message, result)
        return

    # Existing exec flow
    if command.startswith('exec'):
        password = generate_password()
        with open(password_file, 'w') as f:
            f.write(password)
        with open(attempt_file, 'w') as f:
            f.write('0')

        send_email('Your exec Command Password', f'PASSWORD: {password}', recipient_email)
        await message.reply_text('A temporary password has been sent to your email. Please reply with PASSWORD: yourpassword to execute the command.')

        with open(temp_command_file, 'w') as f:
            f.write(' '.join(command.split(' ')[1:]))

    elif command.startswith('PASSWORD'):
        if not os.path.exists(password_file):
            await message.reply_text('Password has expired or is invalid. Please generate a new exec command.')
            return

        parts = command.split(' ', 1)
        if len(parts) < 2:
            await message.reply_text('Invalid password format. Please reply with PASSWORD: yourpassword.')
            return

        input_password = parts[1].strip()

        with open(password_file, 'r') as f:
            stored_password = f.read().strip()

        if input_password != stored_password:
            with open(attempt_file, 'r') as f:
                attempts = int(f.read().strip())
            attempts += 1
            with open(attempt_file, 'w') as f:
                f.write(str(attempts))

            if attempts >= max_attempts:
                await message.reply_text('Too many failed attempts. The password has expired.')
                for file in [password_file, attempt_file, temp_command_file]:
                    if os.path.exists(file):
                        os.remove(file)
            else:
                await message.reply_text(f'Unauthorized access attempt! {max_attempts - attempts} attempts left.')
            return

        with open(temp_command_file, 'r') as f:
            command_to_execute = f.read().strip()

        with open(temp_script_path, 'w') as f:
            f.write(f'#!/bin/bash\n\n')
            f.write(f'# Script generated by Telegram bot at {datetime.now()}\n')
            f.write(f'# Command to execute: {command_to_execute}\n')
            f.write(f'{command_to_execute}\n')

        os.chmod(temp_script_path, 0o755)

        result = execute_command(['sudo', temp_script_path])
        await message.reply_text(f'Command execution result:\n\n{result}')

        for file in [password_file, attempt_file, temp_command_file, temp_script_path]:
            if os.path.exists(file):
                os.remove(file)

    else:
        command_dict = {
            'uptime': ['uptime'],
            'df': ['df', '-h'],
            'last': ['last'],
            'vpn-restart': ['sudo', 'systemctl', 'restart', 'openvpn.service'],
            'kodi stop': ['sudo', 'manage_kodi', 'off'],
            'kodi start': ['sudo', 'manage_kodi', 'on'],
            'upgrade raspbxino': ['sudo', 'upgrade_raspbxino'],
            'tunnel-ssh': ['/usr/local/bin/ssh-port-forward.sh'],
        }

        if command in command_dict:
            result = execute_command(command_dict[command])
            await message.reply_text(result)
        elif command.startswith('restart'):
            cmd = command.split('restart', 1)[1].strip()
            device_dict = {
                'router': ['sudo', 'restart_device', 'router'],
                'raspberrino': ['sudo', 'restart_device', 'raspberrino'],
                'raspbxino': ['sudo', 'restart_device', 'raspbxino'],
            }
            if cmd in device_dict:
                result = execute_command(device_dict[cmd])
                await message.reply_text(result)
            else:
                await message.reply_text('Usage: restart (router|raspberrino|raspbxino)')
        else:
            cmds = '\n'.join(
                list(command_dict.keys())
                + [
                    'restart <device>',
                    'exec <custom shell command - use at your own risk>',
                    'url <http[s]://...> - fetch a web page and return clean text',
                ]
            )
            await message.reply_text(f'Commands available:\n{cmds}')


# Main application
async def main():
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # Clean temp script on startup
    if os.path.exists(temp_script_path):
        os.remove(temp_script_path)

    await startup_message(app)
    await app.run_polling()


if __name__ == '__main__':
    nest_asyncio.apply()
    asyncio.run(main())

