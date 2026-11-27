"""Rich script output: the `#telegram-json` protocol (text, buttons, edit, silent).

A script whose stdout starts with the line `#telegram-json` (the JSON object may
also follow on the same line) gets a JSON reply. Anything else is plain text.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

MARKER = "#telegram-json"
MAX_CALLBACK_BYTES = 64


@dataclass
class Rich:
    text: str = ""
    buttons: List[List[dict]] = field(default_factory=list)  # rows of {"text", "cmd"}
    edit: Optional[bool] = None  # None = default (edit when button-triggered)
    silent: bool = False


def script_env(chat_id, trigger: str, message_id=None) -> dict:
    """Environment for a script run: the bot's own plus the TG_* variables."""
    env = dict(os.environ)
    env["TG_CHAT_ID"] = str(chat_id)
    env["TG_TRIGGER"] = trigger
    env.pop("TG_MESSAGE_ID", None)
    if trigger == "button" and message_id is not None:
        env["TG_MESSAGE_ID"] = str(message_id)
    return env


def parse(output: str) -> Optional[Rich]:
    """Return a Rich reply, or None when output is plain text or malformed JSON."""
    if not output.startswith(MARKER):
        return None
    rest = output[len(MARKER):]
    if rest and not rest[0].isspace():
        return None  # e.g. "#telegram-jsonx": not the marker
    try:
        data = json.loads(rest)
    except ValueError:
        logger.warning("Malformed #telegram-json output, sending it as plain text")
        return None
    if not isinstance(data, dict):
        logger.warning("#telegram-json is not an object, sending it as plain text")
        return None
    text = data.get("text", "")
    edit = data.get("edit")
    return Rich(
        text=text if isinstance(text, str) else str(text),
        buttons=clean_buttons(data.get("buttons")),
        edit=edit if isinstance(edit, bool) else None,
        silent=data.get("silent") is True,
    )


def clean_buttons(rows) -> List[List[dict]]:
    """Keep well-formed buttons; drop (with a warning) any cmd over 64 bytes."""
    out: List[List[dict]] = []
    for row in rows if isinstance(rows, list) else []:
        kept = []
        for b in row if isinstance(row, list) else []:
            if not isinstance(b, dict) or not isinstance(b.get("text"), str) \
                    or not isinstance(b.get("cmd"), str) or not b["cmd"]:
                logger.warning("Dropping malformed button: %r", b)
                continue
            if len(b["cmd"].encode("utf-8")) > MAX_CALLBACK_BYTES:
                logger.warning("Dropping button %r: cmd over %d bytes", b["text"], MAX_CALLBACK_BYTES)
                continue
            kept.append({"text": b["text"], "cmd": b["cmd"]})
        if kept:
            out.append(kept)
    return out


def should_edit(rich: Rich, trigger: str) -> bool:
    """Edit the tapped message? Only for button taps; default on, `edit: false` opts out."""
    return trigger == "button" and rich.edit is not False


def keyboard(rich: Rich):
    """Build an InlineKeyboardMarkup, or None when there are no buttons."""
    if not rich.buttons:
        return None
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(b["text"], callback_data=b["cmd"]) for b in row] for row in rich.buttons]
    )
