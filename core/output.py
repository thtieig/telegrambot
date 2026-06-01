"""Telegram output helpers: URL detection, control-char stripping, chunking."""
import re
import unicodedata
from typing import List

CHUNK_SIZE = 3500
_URL_RE = re.compile(r"^\s*https?://", re.IGNORECASE)


def looks_like_url(text: str) -> bool:
    return bool(_URL_RE.match(text))


def sanitise(text: str) -> str:
    """Drop control characters Telegram rejects, keeping newlines and tabs."""
    return "".join(
        c for c in text
        if unicodedata.category(c)[0] != "C" or c in "\n\t"
    )


def chunk(text: str, max_len: int = CHUNK_SIZE) -> List[str]:
    if not text:
        return ["[no text returned]"]

    chunks: List[str] = []
    buffer: List[str] = []
    current_len = 0

    for line in text.splitlines(keepends=True):
        line_len = len(line)
        if current_len + line_len <= max_len:
            buffer.append(line)
            current_len += line_len
            continue

        if buffer:
            chunks.append("".join(buffer).rstrip())
            buffer = []
            current_len = 0

        while line_len > max_len:
            chunks.append(line[:max_len])
            line = line[max_len:]
            line_len = len(line)

        if line:
            buffer.append(line)
            current_len = len(line)

    if buffer:
        chunks.append("".join(buffer).rstrip())

    return chunks or [text[:max_len]]


async def send_output(message, text: str, max_len: int = CHUNK_SIZE):
    """Sanitise, chunk, and reply with each chunk."""
    for part in chunk(sanitise(text), max_len):
        await message.reply_text(part)
