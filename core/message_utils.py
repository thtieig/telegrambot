# core/message_utils.py
"""Message handling utilities"""
import re
from typing import List

TELEGRAM_CHUNK_SIZE = 3500

def chunk_text_for_telegram(text: str, max_len: int = TELEGRAM_CHUNK_SIZE) -> List[str]:
    """Split text into Telegram-friendly chunks"""
    if not text:
        return ["[no text returned]"]
    
    chunks = []
    buffer = []
    current_len = 0
    
    for line in text.splitlines(keepends=True):
        line_len = len(line)
        if current_len + line_len <= max_len:
            buffer.append(line)
            current_len += line_len
            continue

        # Flush current buffer
        if buffer:
            chunks.append(''.join(buffer).rstrip())
            buffer = []
            current_len = 0

        # Hard-split long lines
        while line_len > max_len:
            chunks.append(line[:max_len])
            line = line[max_len:]
            line_len = len(line)

        if line:
            buffer.append(line)
            current_len = len(line)

    if buffer:
        chunks.append(''.join(buffer).rstrip())

    return chunks or [text[:max_len]]

async def send_chunked_text(message, text: str, chunk_size: int = TELEGRAM_CHUNK_SIZE):
    """Send long text in multiple chunks"""
    for chunk in chunk_text_for_telegram(text, chunk_size):
        await message.reply_text(chunk)

def is_url_like(text: str) -> bool:
    """Check if text looks like a URL"""
    return bool(re.match(r'^\s*https?://', text, re.IGNORECASE))
