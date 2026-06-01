# Telegrambot Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the bot's dynamic plugin system with a simple "run scripts from a folder" engine, and split the monolithic Ansible `telegram-bot` role into focused roles.

**Architecture:** The bot scans `builtin/` (shipped, tracked) and `scripts/` (host-specific, gitignored) for executable files; filename = command. The only stateful built-in is `exec`. The torrent watcher moves out of the bot into its own systemd service. Ansible: `telegram-bot` becomes pure framework that deploys commands from a data-driven `telegram_bot_scripts` list; host tooling moves to `energenie`, new `windows-control`, new `ssh-tunnel`, and new `torrent` roles.

**Tech Stack:** Python 3.11+, python-telegram-bot v20, pytest + pytest-asyncio (dev only), Ansible.

**Spec:** `docs/superpowers/specs/2026-06-01-architecture-redesign.md`

**Two repos:**
- Bot repo: `/home/chris/scripts/telegrambot` (Phase A — push to `main` first)
- Ansible repo: `/home/chris/2026_audit/fish_and_chips_infra` (Phase B — deploys the new bot)

**Operator rules baked in:**
- The playbook is the **fresh-install source of truth**. No remove/fix/migration tasks.
- One-time cleanup of the existing raspberrino deploy is a **manual checklist** (Phase C), never in the playbook.

**Refinement vs spec:** the role supports two script entry types — `inline` (generates a sudo-capable wrapper) and `template` (deploys a file). The spec's `link` type is dropped (YAGNI): every host tool here needs `sudo`, so it is exposed via an `inline` wrapper while the real tool stays in `/usr/local/bin` for shell use.

---

# PHASE A — Bot repo

Work in `/home/chris/scripts/telegrambot`. All commits in this phase happen on `main` (small personal repo, operator's workflow). Push only at Task A10.

---

### Task A1: Test scaffolding

**Files:**
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create dev requirements**

`requirements-dev.txt`:
```
pytest
pytest-asyncio
```

- [ ] **Step 2: Create pytest config**

`pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 3: Create empty test package init**

`tests/__init__.py`: (empty file)

- [ ] **Step 4: Create shared FakeMessage fixture**

`tests/conftest.py`:
```python
import pytest


class FakeMessage:
    """Stand-in for a telegram Message; records replies instead of sending."""
    def __init__(self):
        self.replies = []

    async def reply_text(self, text):
        self.replies.append(text)


@pytest.fixture
def fake_message():
    return FakeMessage()
```

- [ ] **Step 5: Install dev deps and verify pytest runs**

Run: `pip install -r requirements-dev.txt && python -m pytest -q`
Expected: `no tests ran` (exit 5) or "collected 0 items" — confirms pytest + asyncio plugin import cleanly.

- [ ] **Step 6: Commit**

```bash
git add requirements-dev.txt pytest.ini tests/__init__.py tests/conftest.py
git commit -m "test: add pytest scaffolding"
```

---

### Task A2: `core/runner.py` — subprocess wrapper

**Files:**
- Create: `core/runner.py`
- Test: `tests/test_runner.py`

- [ ] **Step 1: Write failing tests**

`tests/test_runner.py`:
```python
from core.runner import run_command


def test_run_command_returns_stdout():
    assert run_command(["echo", "hello"]).strip() == "hello"


def test_run_command_captures_stderr_on_failure():
    # `ls` of a missing path exits non-zero and writes to stderr; we still get text
    out = run_command(["ls", "/no/such/path/xyz"])
    assert "No such file" in out or "cannot access" in out


def test_run_command_timeout():
    out = run_command(["sleep", "5"], timeout=1)
    assert "timed out" in out.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_runner.py -v`
Expected: FAIL (`ModuleNotFoundError: core.runner`)

- [ ] **Step 3: Implement**

`core/runner.py`:
```python
"""Run an executable and return its combined stdout+stderr as text."""
import subprocess


def run_command(argv: list, timeout: int = 30) -> str:
    try:
        out = subprocess.check_output(argv, stderr=subprocess.STDOUT, timeout=timeout)
        return out.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as e:
        return e.output.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {e}"
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_runner.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add core/runner.py tests/test_runner.py
git commit -m "feat: add runner.run_command (replaces shell_utils)"
```

---

### Task A3: `core/output.py` — sanitise, chunk, send

**Files:**
- Create: `core/output.py`
- Test: `tests/test_output.py`

- [ ] **Step 1: Write failing tests**

`tests/test_output.py`:
```python
import pytest
from core.output import looks_like_url, sanitise, chunk, send_output
from tests.conftest import FakeMessage


def test_looks_like_url():
    assert looks_like_url("https://example.com")
    assert looks_like_url("  http://x.y")
    assert not looks_like_url("hello world")
    assert not looks_like_url("ftp://x")


def test_sanitise_strips_control_chars_but_keeps_newline_tab():
    assert sanitise("a\x00b\tc\nd") == "ab\tc\nd"


def test_chunk_splits_long_text():
    text = "\n".join(f"line{i}" for i in range(2000))
    parts = chunk(text, max_len=100)
    assert len(parts) > 1
    assert all(len(p) <= 100 for p in parts)


def test_chunk_empty_returns_placeholder():
    assert chunk("") == ["[no text returned]"]


async def test_send_output_replies_in_chunks():
    msg = FakeMessage()
    await send_output(msg, "hello", max_len=100)
    assert msg.replies == ["hello"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_output.py -v`
Expected: FAIL (`ModuleNotFoundError: core.output`)

- [ ] **Step 3: Implement**

`core/output.py`:
```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_output.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add core/output.py tests/test_output.py
git commit -m "feat: add output helpers (replaces message_utils)"
```

---

### Task A4: `core/commands.py` — discovery + routing

**Files:**
- Create: `core/commands.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write failing tests**

`tests/test_commands.py`:
```python
import os
import stat
from core.commands import read_description, discover, resolve, Command


def _write_script(path, body, executable=True):
    with open(path, "w") as f:
        f.write(body)
    if executable:
        os.chmod(path, 0o755)


def test_read_description_parses_second_line(tmp_path):
    p = tmp_path / "foo"
    _write_script(p, "#!/bin/bash\n# description: Does a thing\necho hi\n")
    assert read_description(str(p)) == "Does a thing"


def test_read_description_missing_returns_empty(tmp_path):
    p = tmp_path / "foo"
    _write_script(p, "#!/bin/bash\necho hi\n")
    assert read_description(str(p)) == ""


def test_discover_finds_executables_only(tmp_path):
    _write_script(tmp_path / "run_me", "#!/bin/bash\necho a\n")
    _write_script(tmp_path / "not_exec", "#!/bin/bash\necho b\n", executable=False)
    cmds = discover([str(tmp_path)])
    assert "run_me" in cmds
    assert "not_exec" not in cmds


def test_discover_scripts_override_builtin(tmp_path):
    builtin = tmp_path / "builtin"
    scripts = tmp_path / "scripts"
    builtin.mkdir()
    scripts.mkdir()
    _write_script(builtin / "df", "#!/bin/bash\necho builtin\n")
    _write_script(scripts / "df", "#!/bin/bash\necho override\n")
    cmds = discover([str(builtin), str(scripts)])
    assert cmds["df"].path == str(scripts / "df")


def test_resolve_splits_name_and_args(tmp_path):
    _write_script(tmp_path / "restart", "#!/bin/bash\necho x\n")
    cmds = discover([str(tmp_path)])
    cmd, args = resolve("restart router now", cmds)
    assert isinstance(cmd, Command)
    assert cmd.name == "restart"
    assert args == ["router", "now"]


def test_resolve_unknown_returns_none(tmp_path):
    cmds = discover([str(tmp_path)])
    assert resolve("nope", cmds) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_commands.py -v`
Expected: FAIL (`ModuleNotFoundError: core.commands`)

- [ ] **Step 3: Implement**

`core/commands.py`:
```python
"""Command discovery and routing. A command is an executable file."""
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_DESCRIPTION_PREFIX = "# description:"


@dataclass
class Command:
    name: str
    path: str
    description: str


def read_description(path: str) -> str:
    """Return the text after `# description:` on line 2, or empty string."""
    try:
        with open(path, "r", errors="replace") as f:
            f.readline()              # shebang
            second = f.readline().strip()
    except OSError:
        return ""
    if second.startswith(_DESCRIPTION_PREFIX):
        return second[len(_DESCRIPTION_PREFIX):].strip()
    return ""


def discover(dirs: List[str]) -> Dict[str, Command]:
    """Scan dirs in order; later dirs override earlier on name collision."""
    commands: Dict[str, Command] = {}
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            path = os.path.join(d, name)
            if not os.path.isfile(path) or not os.access(path, os.X_OK):
                continue
            commands[name] = Command(name, path, read_description(path))
    return commands


def resolve(text: str, commands: Dict[str, Command]) -> Optional[Tuple[Command, List[str]]]:
    parts = text.strip().split()
    if not parts:
        return None
    cmd = commands.get(parts[0])
    if cmd is None:
        return None
    return cmd, parts[1:]
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_commands.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add core/commands.py tests/test_commands.py
git commit -m "feat: add command discovery and routing (replaces command_loader)"
```

---

### Task A5: `core/exec.py` — the one built-in stateful command

Ports `commands/exec_commands.py`. Fixes: `secrets.choice` for the password; runs the stored command via `sudo bash -c <cmd>` (argument, not embedded script text). The `config` import is local to `_send_email` so the module imports without a `config.py` present (needed for tests).

**Files:**
- Create: `core/exec.py`
- Test: `tests/test_exec.py`

- [ ] **Step 1: Write failing tests**

`tests/test_exec.py`:
```python
import os
import string
import core.exec as execmod
from core.exec import generate_password, ExecFeature
from tests.conftest import FakeMessage


def test_generate_password_length_and_charset():
    pw = generate_password(20)
    assert len(pw) == 20
    assert all(c in (string.ascii_letters + string.digits) for c in pw)


def _feature(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAMBOT_STATE_DIR", str(tmp_path))
    feat = ExecFeature()
    # never send real email
    monkeypatch.setattr(feat, "_send_email", lambda *a, **k: None)
    return feat


def test_handles_prefixes():
    feat = ExecFeature.__new__(ExecFeature)  # no __init__/mkdir
    assert feat.handles("exec ls")
    assert feat.handles("PASSWORD: abc")
    assert not feat.handles("execute foo")
    assert not feat.handles("uptime")


async def test_request_stores_state(tmp_path, monkeypatch):
    feat = _feature(tmp_path, monkeypatch)
    msg = FakeMessage()
    await feat.handle(msg, "exec echo hi")
    assert feat.password_file.exists()
    assert feat.command_file.read_text().strip() == "echo hi"
    assert "password has been sent" in msg.replies[0].lower()


async def test_wrong_password_decrements_attempts(tmp_path, monkeypatch):
    feat = _feature(tmp_path, monkeypatch)
    await feat.handle(FakeMessage(), "exec echo hi")
    msg = FakeMessage()
    await feat.handle(msg, "PASSWORD: wrong")
    assert "2 left" in msg.replies[0] or "2 " in msg.replies[0]
    assert feat.attempt_file.read_text().strip() == "1"


async def test_correct_password_runs_and_cleans_up(tmp_path, monkeypatch):
    feat = _feature(tmp_path, monkeypatch)
    captured = {}
    monkeypatch.setattr(execmod, "run_command", lambda argv: captured.setdefault("argv", argv) or "OK")
    await feat.handle(FakeMessage(), "exec echo hi")
    pw = feat.password_file.read_text().strip()
    msg = FakeMessage()
    await feat.handle(msg, f"PASSWORD: {pw}")
    assert captured["argv"] == ["sudo", "bash", "-c", "echo hi"]
    assert "OK" in msg.replies[0]
    assert not feat.password_file.exists()  # cleaned up


async def test_password_without_request_is_rejected(tmp_path, monkeypatch):
    feat = _feature(tmp_path, monkeypatch)
    msg = FakeMessage()
    await feat.handle(msg, "PASSWORD: anything")
    assert "expired or invalid" in msg.replies[0].lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_exec.py -v`
Expected: FAIL (`ModuleNotFoundError: core.exec`)

- [ ] **Step 3: Implement**

`core/exec.py`:
```python
"""The single built-in stateful command: email-verified arbitrary execution.

State files live under $TELEGRAMBOT_STATE_DIR (default /var/lib/telegrambot),
mode 0600. The `config` import is local to _send_email so this module imports
without a config.py present.
"""
import os
import secrets
import string
from pathlib import Path
from email.mime.text import MIMEText

from core.runner import run_command

_ALPHABET = string.ascii_letters + string.digits
STATE_DIR = Path(os.environ.get("TELEGRAMBOT_STATE_DIR", "/var/lib/telegrambot"))


def generate_password(length: int = 12) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


class ExecFeature:
    def __init__(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.password_file = STATE_DIR / "exec_password.txt"
        self.attempt_file = STATE_DIR / "exec_attempts.txt"
        self.command_file = STATE_DIR / "exec_command.txt"
        self.max_attempts = 3

    def handles(self, command: str) -> bool:
        return command == "exec" or command.startswith("exec ") or command.startswith("PASSWORD")

    async def handle(self, message, command: str):
        if command.startswith("PASSWORD"):
            await self._verify(message, command)
        else:
            await self._request(message, command)

    async def _request(self, message, command: str):
        password = generate_password()
        self._write(self.password_file, password)
        self._write(self.attempt_file, "0")
        self._write(self.command_file, command[len("exec"):].strip())
        self._send_email("Your exec Command Password", f"PASSWORD: {password}")
        await message.reply_text(
            'A temporary password has been sent to your email. '
            'Reply with "PASSWORD: yourpassword" to execute the command.'
        )

    async def _verify(self, message, command: str):
        if not self.password_file.exists():
            await message.reply_text("Password has expired or is invalid. Please generate a new exec command.")
            return
        parts = command.split(" ", 1)
        if len(parts) < 2:
            await message.reply_text('Invalid password format. Reply with "PASSWORD: yourpassword".')
            return
        if parts[1].strip() != self.password_file.read_text().strip():
            await self._failed_attempt(message)
            return
        await self._run(message)

    async def _failed_attempt(self, message):
        attempts = int(self.attempt_file.read_text().strip()) + 1
        self._write(self.attempt_file, str(attempts))
        if attempts >= self.max_attempts:
            await message.reply_text("Too many failed attempts. The password has expired.")
            self._cleanup()
        else:
            await message.reply_text(f"Unauthorised access attempt! {self.max_attempts - attempts} attempts left.")

    async def _run(self, message):
        cmd = self.command_file.read_text().strip()
        result = run_command(["sudo", "bash", "-c", cmd])
        await message.reply_text(f"Command execution result:\n\n{result}")
        self._cleanup()

    def _write(self, path: Path, content: str):
        path.write_text(content)
        os.chmod(path, 0o600)

    def _send_email(self, subject: str, body: str):
        import smtplib
        from config import recipient_email, email_address, email_password, smtp_server, smtp_port
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = email_address
        msg["To"] = recipient_email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.sendmail(email_address, recipient_email, msg.as_string())

    def _cleanup(self):
        for f in (self.password_file, self.attempt_file, self.command_file):
            if f.exists():
                f.unlink()
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_exec.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add core/exec.py tests/test_exec.py
git commit -m "feat: add exec built-in (secrets password, sudo bash -c, no temp script)"
```

---

### Task A6: Built-in scripts + scripts/ dir + .gitignore

**Files:**
- Create: `builtin/uptime`, `builtin/df`, `builtin/last`, `builtin/mem`, `builtin/url`
- Create: `scripts/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: Create the four trivial built-ins**

`builtin/uptime`:
```bash
#!/bin/bash
# description: Show system uptime and load
exec uptime
```

`builtin/df`:
```bash
#!/bin/bash
# description: Show disk usage (human readable)
exec df -h
```

`builtin/last`:
```bash
#!/bin/bash
# description: Show recent logins
exec last
```

`builtin/mem`:
```bash
#!/bin/bash
# description: Show memory usage
exec free -h
```

- [ ] **Step 2: Create the url built-in**

`builtin/url`:
```bash
#!/bin/bash
# description: Fetch a URL and return cleaned text — usage: url <https://...>
here="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$here/../utils/fetch_clean_url.py" "$@"
```

- [ ] **Step 3: Make them executable**

Run: `chmod +x builtin/uptime builtin/df builtin/last builtin/mem builtin/url`

- [ ] **Step 4: Create the scripts drop-in placeholder**

Run: `touch scripts/.gitkeep`

- [ ] **Step 5: Update .gitignore**

In `.gitignore`, under the `# Telegrambot` section, add these lines (keep existing entries):
```
# Host-specific scripts are deployed by Ansible, never committed
scripts/*
!scripts/.gitkeep
```

- [ ] **Step 6: Verify discovery picks them up**

Run:
```bash
python -c "from core.commands import discover; import json; print(sorted(discover(['builtin','scripts'])))"
```
Expected: `['df', 'last', 'mem', 'uptime', 'url']`

- [ ] **Step 7: Commit**

```bash
git add builtin scripts/.gitkeep .gitignore
git commit -m "feat: add built-in scripts and scripts/ drop-in dir"
```

---

### Task A7: Rewrite `telegrambot.py` + integration test

**Files:**
- Modify: `telegrambot.py` (full rewrite)
- Test: `tests/test_integration.py`

- [ ] **Step 1: Write the integration test (no config import)**

This exercises discover → resolve → run_command → send_output against real temp scripts, mirroring `handle_message`'s body without importing `telegrambot.py` (which needs `config.py`).

`tests/test_integration.py`:
```python
import os
from core.commands import discover, resolve
from core.runner import run_command
from core.output import send_output, looks_like_url
from tests.conftest import FakeMessage


def _script(path, body):
    with open(path, "w") as f:
        f.write(body)
    os.chmod(path, 0o755)


async def test_end_to_end_command_run(tmp_path):
    _script(tmp_path / "greet", "#!/bin/bash\n# description: greet\necho \"hi $1\"\n")
    commands = discover([str(tmp_path)])

    text = "greet world"
    assert not looks_like_url(text)
    cmd, args = resolve(text, commands)
    result = run_command([cmd.path] + args)

    msg = FakeMessage()
    await send_output(msg, result)
    assert msg.replies == ["hi world"]


async def test_url_normalisation_routes_to_url_command(tmp_path):
    _script(tmp_path / "url", "#!/bin/bash\necho \"fetched $1\"\n")
    commands = discover([str(tmp_path)])

    text = "https://example.com"
    assert looks_like_url(text)
    text = f"url {text}"
    cmd, args = resolve(text, commands)
    assert cmd.name == "url"
    assert args == ["https://example.com"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_integration.py -v`
Expected: FAIL (`greet`/`url` resolution works only after… actually these pass already since they use existing modules). If they PASS here, that's fine — they guard the wiring. Proceed.

> Note: this test depends only on Task A2–A6 modules, so it should PASS. It exists to lock the wiring contract that `telegrambot.py` implements in Step 3.

- [ ] **Step 3: Rewrite telegrambot.py**

`telegrambot.py` (replace entire file):
```python
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
```

- [ ] **Step 4: Run integration tests + full suite**

Run: `python -m pytest -v`
Expected: PASS (all tests green)

- [ ] **Step 5: Byte-compile telegrambot.py to catch syntax errors**

Run: `python -m py_compile telegrambot.py && echo OK`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add telegrambot.py tests/test_integration.py
git commit -m "refactor: rewrite telegrambot.py as a script runner"
```

---

### Task A8: Delete the obsolete plugin system

**Files:**
- Delete: `commands/` (whole directory)
- Delete: `core/command_loader.py`, `core/message_utils.py`, `core/shell_utils.py`

- [ ] **Step 1: Confirm nothing still imports them**

Run:
```bash
grep -rn -E "command_loader|message_utils|shell_utils|from commands|import commands\b" --include="*.py" . | grep -v tests/
```
Expected: no output (only possible matches are in this plan/docs, not code).

- [ ] **Step 2: Remove the files**

```bash
git rm -r commands
git rm core/command_loader.py core/message_utils.py core/shell_utils.py
```

- [ ] **Step 3: Run full suite + compile**

Run: `python -m pytest -q && python -m py_compile telegrambot.py && echo OK`
Expected: all tests pass, `OK`

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: delete plugin system (commands/, command_loader, message_utils, shell_utils)"
```

---

### Task A9: Rewrite README.md

**Files:**
- Modify: `README.md` (full rewrite)

- [ ] **Step 1: Replace README.md with the new model**

`README.md`:
```markdown
# Telegram Assistant

A small, generic Telegram bot that runs scripts on your server. Drop an
executable in a folder and it becomes a command. Authorised users only.

## How it works

The bot scans two folders on startup and treats every executable file as a command:

- `builtin/` — universal, zero-config scripts shipped with the bot (`uptime`, `df`, `last`, `mem`, `url`).
- `scripts/` — your host-specific scripts. Gitignored; managed by your deployment (e.g. Ansible).

The **filename is the command name**. Anything you type after it is passed as
arguments, exactly like a shell. Output is sent back to Telegram (long output is
split into multiple messages). On a name clash, `scripts/` wins over `builtin/`.

Examples:

| You send        | Bot runs                    |
|-----------------|-----------------------------|
| `uptime`        | `builtin/uptime`            |
| `df`            | `builtin/df`                |
| `restart router`| `scripts/restart router`    |
| `https://x.y`   | `builtin/url https://x.y`   |

## Adding a command

1. Create an executable file in `scripts/`:
   ```bash
   #!/bin/bash
   # description: Ping a host
   exec ping -c 3 "$@"
   ```
2. `chmod +x` it.
3. Restart the bot. Done.

Line 2 (`# description: ...`) is shown in the help listing. It is optional.

To expose an existing `/usr/local/bin` tool that needs root, add a tiny wrapper
in `scripts/` that calls it via `sudo`.

## The `exec` built-in

`exec <any shell command>` runs an arbitrary command — guarded by email
verification. The bot emails you a one-time password; reply with
`PASSWORD: <password>` to run it. Three attempts, then the password expires.

Requires SMTP settings in `config.py`: `recipient_email`, `email_address`,
`email_password`, `smtp_server`, `smtp_port`.

## Setup

1. `python3 -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Copy `config.py.template` to `config.py` and fill in your bot token,
   authorised user IDs/usernames, and SMTP details.
4. `python telegrambot.py`

`requests` and `beautifulsoup4` are required (used by `builtin/url`). `lxml` and
`readability-lxml` are optional and improve URL parsing.

## Running tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Sudoers

Commands that need root run via `sudo`. The bot's service user must be allowed
to run them without a password. The `exec` built-in needs broad sudo by design.
Configure `/etc/sudoers.d/` accordingly for your scripts.

## License

MIT.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for the script-runner model"
```

---

### Task A10: Final verification + push to main

- [ ] **Step 1: Full suite + compile all modules**

Run:
```bash
python -m pytest -q && python -m compileall -q core telegrambot.py && echo OK
```
Expected: all pass, `OK`

- [ ] **Step 2: Confirm the repo tree matches the spec**

Run: `ls core builtin scripts; echo '---'; test ! -d commands && echo "commands removed"`
Expected: core has `auth.py commands.py exec.py output.py runner.py __init__.py`; builtin has the 5 scripts; scripts has `.gitkeep`; `commands removed`.

- [ ] **Step 3: Push to main**

```bash
git push origin main
```

> **Gate:** Phase B deploys from `main`. Do not start Phase B until this push succeeds.

---

# PHASE B — Ansible repo

Work in `/home/chris/2026_audit/fish_and_chips_infra`. No TDD here; verification is `--syntax-check`, `ansible-lint`, and a `--check` dry run. Commit per task.

**Shared facts (already in `roles/telegram-bot/defaults/main.yml`):** `telegram_bot_user: telegrambot`, `telegram_bot_install_dir: /opt/telegrambot`, `telegram_bot_state_dir: /var/lib/telegrambot`, `telegram_bot_repo`, `telegram_bot_repo_version: main`. The `tunnel_*` vars also live there and move in Task B5.

---

### Task B1: Add the data-driven script list to host_vars

**Files:**
- Create: `inventory/host_vars/raspberrino/telegrambot.yml`

- [ ] **Step 1: Create the host var file**

`inventory/host_vars/raspberrino/telegrambot.yml`:
```yaml
---
# Single source of truth for what the bot can do on this host.
# Each entry becomes a script in /opt/telegrambot/scripts/.
#   inline:   generate a wrapper that runs this command (args appended)
#   template: deploy a script file from the role's templates/
telegram_bot_scripts:
  - { name: vpn-restart,   description: "Restart the OpenVPN service",  inline: "sudo systemctl restart openvpn.service" }
  - { name: tunnel-ssh,    description: "Restart the reverse SSH tunnel", inline: "sudo systemctl restart ssh-tunnel" }
  - { name: restart,       description: "Restart a device (router|raspberrino)", inline: "sudo /usr/local/bin/restart_device" }
  - { name: shutdown-nuky, description: "Shut down the Windows PC",      inline: "sudo /usr/local/bin/shutdown-nuky" }

# Extra writable paths the bot's systemd unit needs (shutdown-nuky uses net(8),
# which needs /run/samba writable inside the service namespace).
telegram_bot_extra_rw_paths:
  - /run/samba
```

- [ ] **Step 2: Verify host_vars parses**

Run: `ansible-inventory -i inventory --host raspberrino >/dev/null && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add inventory/host_vars/raspberrino/telegrambot.yml
git commit -m "telegram-bot: add data-driven telegram_bot_scripts list for raspberrino"
```

---

### Task B2: Make the telegram-bot role framework-only

Strip everything host-specific. Keep: deps (python3-venv), user, install dir, sudoers, remote_tmp, state dir, deploy key, git clone, requirements, venv, pip, config.py, systemd unit. Add: scripts/ dir + inline/template deployment loops.

**Files:**
- Modify: `roles/telegram-bot/tasks/main.yml`
- Modify: `roles/telegram-bot/templates/telegram-bot.service.j2`

- [ ] **Step 1: Replace tasks/main.yml**

`roles/telegram-bot/tasks/main.yml`:
```yaml
---
- name: Install bot dependencies
  apt:
    name:
      - python3-venv
    state: present
    cache_valid_time: 86400

- name: Create telegrambot system user (in gpio group for GPIO access)
  user:
    name: "{{ telegram_bot_user }}"
    system: yes
    create_home: no
    shell: /usr/sbin/nologin
    groups: gpio
    append: yes
    comment: Telegram bot service account

- name: Ensure telegrambot install dir exists
  file:
    path: "{{ telegram_bot_install_dir }}"
    state: directory
    owner: "{{ telegram_bot_user }}"
    group: "{{ telegram_bot_user }}"

- name: Deploy telegrambot sudoers drop-in (must precede become_user tasks)
  template:
    src: telegrambot.sudoers.j2
    dest: /etc/sudoers.d/telegrambot
    owner: root
    group: root
    mode: '0440'
    validate: 'visudo -cf %s'

- name: Ensure ansible remote_tmp for {{ telegram_bot_user }} exists
  file:
    path: /tmp/.ansible-{{ telegram_bot_user }}
    state: directory
    owner: "{{ telegram_bot_user }}"
    group: "{{ telegram_bot_user }}"
    mode: '0700'

- name: Ensure telegrambot state dir exists (holds the GitHub deploy key)
  file:
    path: "{{ telegram_bot_state_dir }}"
    state: directory
    owner: "{{ telegram_bot_user }}"
    group: "{{ telegram_bot_user }}"
    mode: '0700'

- name: Deploy GitHub deploy key for {{ telegram_bot_user }}
  copy:
    content: "{{ vault_github_deploy_key }}"
    dest: "{{ telegram_bot_deploy_key }}"
    owner: "{{ telegram_bot_user }}"
    group: "{{ telegram_bot_user }}"
    mode: '0600'
  no_log: true

- name: Clone/update telegrambot repo to {{ telegram_bot_repo_version }}
  git:
    repo: "{{ telegram_bot_repo }}"
    dest: "{{ telegram_bot_install_dir }}"
    version: "{{ telegram_bot_repo_version }}"
    update: yes
    force: yes
  become: yes
  become_user: "{{ telegram_bot_user }}"
  environment:
    GIT_SSH_COMMAND: "ssh -i {{ telegram_bot_deploy_key }} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile={{ telegram_bot_state_dir }}/known_hosts"
  vars:
    ansible_remote_tmp: /tmp/.ansible-{{ telegram_bot_user }}
  notify: Restart telegram-bot

- name: Deploy requirements.txt (overrides upstream)
  copy:
    src: requirements.txt
    dest: "{{ telegram_bot_install_dir }}/requirements.txt"
    owner: "{{ telegram_bot_user }}"
    group: "{{ telegram_bot_user }}"
    mode: '0644'

- name: Create Python venv
  command: python3 -m venv {{ telegram_bot_install_dir }}/.venv
  args:
    creates: "{{ telegram_bot_install_dir }}/.venv"
  become: yes
  become_user: "{{ telegram_bot_user }}"
  vars:
    ansible_remote_tmp: /tmp/.ansible-{{ telegram_bot_user }}

- name: Install Python requirements
  pip:
    requirements: "{{ telegram_bot_install_dir }}/requirements.txt"
    virtualenv: "{{ telegram_bot_install_dir }}/.venv"
  become: yes
  become_user: "{{ telegram_bot_user }}"
  vars:
    ansible_remote_tmp: /tmp/.ansible-{{ telegram_bot_user }}

- name: Deploy config.py
  template:
    src: config.py.j2
    dest: "{{ telegram_bot_install_dir }}/config.py"
    owner: "{{ telegram_bot_user }}"
    group: "{{ telegram_bot_user }}"
    mode: '0600'
    backup: yes
  no_log: true
  notify: Restart telegram-bot

- name: Create scripts drop-in dir
  file:
    path: "{{ telegram_bot_install_dir }}/scripts"
    state: directory
    owner: "{{ telegram_bot_user }}"
    group: "{{ telegram_bot_user }}"
    mode: '0755'

- name: Deploy inline command scripts
  copy:
    dest: "{{ telegram_bot_install_dir }}/scripts/{{ item.name }}"
    content: |
      #!/bin/bash
      # description: {{ item.description | default(item.name) }}
      exec {{ item.inline }} "$@"
    owner: "{{ telegram_bot_user }}"
    group: "{{ telegram_bot_user }}"
    mode: '0755'
  loop: "{{ telegram_bot_scripts | default([]) | selectattr('inline', 'defined') | list }}"
  loop_control:
    label: "{{ item.name }}"
  notify: Restart telegram-bot

- name: Deploy template command scripts
  template:
    src: "{{ item.template }}"
    dest: "{{ telegram_bot_install_dir }}/scripts/{{ item.name }}"
    owner: "{{ telegram_bot_user }}"
    group: "{{ telegram_bot_user }}"
    mode: '0755'
  loop: "{{ telegram_bot_scripts | default([]) | selectattr('template', 'defined') | list }}"
  loop_control:
    label: "{{ item.name }}"
  notify: Restart telegram-bot

- name: Deploy telegram-bot systemd service
  template:
    src: telegram-bot.service.j2
    dest: /etc/systemd/system/telegram-bot.service
    mode: '0644'
    backup: yes
  notify: Restart telegram-bot

- name: Enable and start telegram-bot
  systemd:
    name: telegram-bot
    enabled: yes
    state: started
    daemon_reload: yes
```

- [ ] **Step 2: Update the service template for configurable RW paths**

In `roles/telegram-bot/templates/telegram-bot.service.j2`, replace the two lines:
```
ReadWritePaths={{ telegram_bot_install_dir }}
ReadWritePaths=/run/samba
```
with:
```
ReadWritePaths={{ telegram_bot_install_dir }}
{% for p in telegram_bot_extra_rw_paths | default([]) %}
ReadWritePaths={{ p }}
{% endfor %}
```

- [ ] **Step 3: Remove now-unused files from the role**

These move to other roles in B3–B6. Remove from the telegram-bot role:
```bash
git rm roles/telegram-bot/templates/restart_device.sh.j2
git rm roles/telegram-bot/templates/shutdown-nuky.sh.j2
git rm roles/telegram-bot/templates/ssh-port-forward.sh.j2
git rm roles/telegram-bot/templates/ssh-tunnel.service.j2
git rm roles/telegram-bot/templates/torrent_sync.sh.j2
git rm roles/telegram-bot/templates/vps_torrent_commands.py.j2
git rm roles/telegram-bot/templates/vps_torrent_config.json.j2
git rm roles/telegram-bot/files/vps_torrent.py
git rm roles/telegram-bot/files/samba-run.conf
```

- [ ] **Step 4: Remove the ssh-tunnel handler (moves to ssh-tunnel role)**

Edit `roles/telegram-bot/handlers/main.yml` to keep only the telegram-bot handler:
```yaml
---
- name: Restart telegram-bot
  systemd:
    name: telegram-bot
    state: restarted
    daemon_reload: yes
```

- [ ] **Step 5: Syntax check**

Run: `ansible-playbook -i inventory playbooks/raspberrino.yml --syntax-check`
Expected: prints the playbook name, no errors. (It will still reference roles created in later tasks — that's fine; syntax-check does not require role bodies to be complete, but if it errors on a missing role, proceed to B3–B6 and re-run at B7.)

- [ ] **Step 6: Commit**

```bash
git add roles/telegram-bot
git commit -m "telegram-bot: reduce role to framework + data-driven script deployment"
```

---

### Task B3: Move restart_device into the energenie role

**Files:**
- Create: `roles/energenie/templates/restart_device.sh.j2` (content from the old telegram-bot template)
- Modify: `roles/energenie/tasks/main.yml`

- [ ] **Step 1: Create the template**

`roles/energenie/templates/restart_device.sh.j2`:
```bash
#!/bin/bash
# description: Restart a device (router|raspberrino)
# Managed by Ansible (roles/energenie).

case "$1" in
  router)
    echo "Switching OFF router socket, waiting 5s, switching ON..."
    /usr/local/bin/energenie socket_1 off
    sleep 5
    /usr/local/bin/energenie socket_1 on
    echo "Router power-cycled. Allow 2-3 minutes for it to come back."
    ;;
  raspberrino)
    echo "Rebooting raspberrino..."
    sleep 2
    /sbin/shutdown -r now
    ;;
  *)
    echo "Usage: restart_device router|raspberrino"
    exit 1
    ;;
esac
```

> Note: line 2 is now a `# description:` so it reads cleanly if ever surfaced.

- [ ] **Step 2: Append the deploy task to energenie tasks**

Add to the end of `roles/energenie/tasks/main.yml`:
```yaml
- name: Deploy restart_device control script
  template:
    src: restart_device.sh.j2
    dest: /usr/local/bin/restart_device
    mode: '0755'
    backup: yes
```

- [ ] **Step 3: Syntax check + commit**

Run: `ansible-playbook -i inventory playbooks/raspberrino.yml --syntax-check` (may warn on not-yet-created roles; that's resolved by B7)
```bash
git add roles/energenie
git commit -m "energenie: own restart_device (moved from telegram-bot)"
```

---

### Task B4: New `windows-control` role (shutdown-nuky + Samba)

**Files:**
- Create: `roles/windows-control/tasks/main.yml`
- Create: `roles/windows-control/templates/shutdown-nuky.sh.j2`
- Create: `roles/windows-control/files/samba-run.conf`

- [ ] **Step 1: Create the shutdown-nuky template (from old telegram-bot template)**

`roles/windows-control/templates/shutdown-nuky.sh.j2`:
```bash
#!/bin/bash
net rpc shutdown -I {{ vault_windows_pc_ip }} \
  -U '{{ vault_windows_pc_username }}%{{ vault_windows_pc_password }}' \
  -f -t 0
```

- [ ] **Step 2: Create the tmpfiles file (from old telegram-bot files/)**

`roles/windows-control/files/samba-run.conf`:
```
# /run/samba must exist so that net(8) (samba-common-bin) can initialise its
# messaging context. Without the full samba daemon, nothing creates this dir.
# The telegram-bot service's ReadWritePaths=/run/samba requires it to exist at
# service-start time (systemd namespace setup fails if it is absent).
d /run/samba 0755 root root -
```

- [ ] **Step 3: Create the tasks (Samba install + stub + shutdown-nuky)**

`roles/windows-control/tasks/main.yml`:
```yaml
---
- name: Install samba client tools (net(8) for remote Windows shutdown)
  apt:
    name:
      - samba-common-bin
    state: present
    cache_valid_time: 86400

- name: Deploy tmpfiles.d rule to create /run/samba at boot
  copy:
    src: samba-run.conf
    dest: /etc/tmpfiles.d/samba-run.conf
    owner: root
    group: root
    mode: '0644'

- name: Create /run/samba now (tmpfiles.d only fires at boot otherwise)
  command: systemd-tmpfiles --create /etc/tmpfiles.d/samba-run.conf
  changed_when: false

# samba-common-bin ships a sample /etc/samba/smb.conf with [print$] pointing at
# a path only the full samba package creates; MOTD flags it. Neutralise it only
# if it is the untouched sample or our previous stub.
- name: Detect current /etc/samba/smb.conf state
  command: head -5 /etc/samba/smb.conf
  register: smb_conf_head
  changed_when: false
  failed_when: false

- name: Deploy minimal smb.conf (neutralises [print$] alert)
  copy:
    dest: /etc/samba/smb.conf
    content: |
      # Managed by Ansible (windows-control stub) — remove this line to opt out
      # samba-common-bin is kept for net(8) (used by shutdown-nuky).
      [global]
         server role = standalone server
    owner: root
    group: root
    mode: '0644'
    backup: yes
  when: >-
    smb_conf_head.rc != 0 or
    'Sample configuration file for the Samba suite' in smb_conf_head.stdout or
    'Managed by Ansible' in smb_conf_head.stdout

- name: Deploy shutdown-nuky script
  template:
    src: shutdown-nuky.sh.j2
    dest: /usr/local/bin/shutdown-nuky
    mode: '0700'
    backup: yes
```

- [ ] **Step 4: Commit**

```bash
git add roles/windows-control
git commit -m "windows-control: new role for shutdown-nuky + samba client (moved from telegram-bot)"
```

---

### Task B5: New `ssh-tunnel` role (autossh + reverse tunnel)

**Files:**
- Create: `roles/ssh-tunnel/defaults/main.yml`
- Create: `roles/ssh-tunnel/tasks/main.yml`
- Create: `roles/ssh-tunnel/handlers/main.yml`
- Create: `roles/ssh-tunnel/templates/ssh-port-forward.sh.j2`
- Create: `roles/ssh-tunnel/templates/ssh-tunnel.service.j2`
- Modify: `roles/telegram-bot/defaults/main.yml` (remove the moved `tunnel_*` vars)

- [ ] **Step 1: Create role defaults (moved tunnel vars)**

`roles/ssh-tunnel/defaults/main.yml`:
```yaml
---
tunnel_remote_host: proxino.tian.it
tunnel_remote_user: root
tunnel_remote_ssh_port: 8022
```

- [ ] **Step 2: Create the two templates (from old telegram-bot templates, comment updated)**

`roles/ssh-tunnel/templates/ssh-port-forward.sh.j2`:
```bash
#!/bin/bash
# Managed by Ansible (roles/ssh-tunnel).
# Reverse SSH tunnel via autossh to {{ tunnel_remote_host }}.

export AUTOSSH_GATETIME=0
export AUTOSSH_POLL=30

exec /usr/bin/autossh -M 0 -NT \
  -o "StrictHostKeyChecking=accept-new" \
  -o "ServerAliveInterval=30" \
  -o "ServerAliveCountMax=3" \
  -R "0.0.0.0:{{ tunnel_remote_ssh_port }}:localhost:22" \
  "{{ tunnel_remote_user }}@{{ tunnel_remote_host }}"
```

`roles/ssh-tunnel/templates/ssh-tunnel.service.j2`:
```
# Managed by Ansible (roles/ssh-tunnel).
[Unit]
Description=Reverse SSH tunnel to {{ tunnel_remote_host }}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/ssh-port-forward.sh
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Create tasks**

`roles/ssh-tunnel/tasks/main.yml`:
```yaml
---
- name: Install autossh
  apt:
    name:
      - autossh
    state: present
    cache_valid_time: 86400

- name: Deploy ssh-port-forward.sh
  template:
    src: ssh-port-forward.sh.j2
    dest: /usr/local/bin/ssh-port-forward.sh
    mode: '0755'
    backup: yes
  notify: Restart ssh-tunnel

- name: Deploy ssh-tunnel systemd service
  template:
    src: ssh-tunnel.service.j2
    dest: /etc/systemd/system/ssh-tunnel.service
    mode: '0644'
    backup: yes
  notify: Restart ssh-tunnel

- name: Enable and start ssh-tunnel
  systemd:
    name: ssh-tunnel
    enabled: yes
    state: started
    daemon_reload: yes
```

- [ ] **Step 4: Create handler**

`roles/ssh-tunnel/handlers/main.yml`:
```yaml
---
- name: Restart ssh-tunnel
  systemd:
    name: ssh-tunnel
    state: restarted
    daemon_reload: yes
```

- [ ] **Step 5: Remove the moved tunnel vars from telegram-bot defaults**

In `roles/telegram-bot/defaults/main.yml`, delete these three lines (they now live in the ssh-tunnel role):
```yaml
tunnel_remote_host: proxino.tian.it
tunnel_remote_user: root
tunnel_remote_ssh_port: 8022
```

- [ ] **Step 6: Commit**

```bash
git add roles/ssh-tunnel roles/telegram-bot/defaults/main.yml
git commit -m "ssh-tunnel: new role for autossh reverse tunnel (moved from telegram-bot)"
```

---

### Task B6: New `torrent` role + `vps_torrent.py watch` subcommand

The watcher becomes a standalone systemd service. `vps_torrent.py` gains a `watch` subcommand and helper functions, with the two audit fixes (error notification, config-load error handling).

**Files:**
- Create: `roles/torrent/defaults/main.yml`
- Create: `roles/torrent/tasks/main.yml`
- Create: `roles/torrent/handlers/main.yml`
- Create: `roles/torrent/files/vps_torrent.py` (existing CLI + new `watch`)
- Create: `roles/torrent/templates/vps_torrent_config.json.j2` (from old telegram-bot template)
- Create: `roles/torrent/templates/torrent.j2` (the bot command wrapper)
- Create: `roles/torrent/templates/torrent-watcher.service.j2`
- Create: `roles/torrent/templates/torrent_sync.sh.j2` (from old telegram-bot template)

- [ ] **Step 1: Create role defaults**

`roles/torrent/defaults/main.yml`:
```yaml
---
torrent_install_dir: /opt/telegrambot
torrent_user: telegrambot
```

- [ ] **Step 2: Copy vps_torrent.py and add the watch subcommand + helpers**

Start from the current file `roles/telegram-bot/files/vps_torrent.py` content (the lifecycle CLI). Create `roles/torrent/files/vps_torrent.py` with that content, then apply these three changes:

(a) Add a Telegram helper near the top-level functions (after `die`):
```python
def send_telegram(token: str, chat_id: str, text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception:
        pass  # never let a notification failure crash the watcher


def poll_transmission(ip: str, password: str) -> list:
    auth = ("transmission", password)
    r = requests.get(f"http://{ip}:9091/transmission/rpc", auth=auth, timeout=10)
    sid = r.headers.get("X-Transmission-Session-Id", "")
    r = requests.post(
        f"http://{ip}:9091/transmission/rpc",
        auth=auth,
        headers={"X-Transmission-Session-Id": sid},
        json={"method": "torrent-get", "arguments": {"fields": ["id", "name", "status"]}},
        timeout=10,
    )
    return r.json()["arguments"]["torrents"]
```

(b) Refactor `cmd_sync` so its rsync logic is callable and returns text. Replace the body of `cmd_sync` with a thin wrapper over a new `_sync(ip) -> str`:
```python
def _sync(ip: str) -> str:
    result = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=accept-new",
         "-o", "UserKnownHostsFile=/var/lib/telegrambot/known_hosts",
         "-i", "/root/.ssh/id_ed25519",
         "root@bananacapsule",
         f"/usr/local/bin/torrent_sync.sh {ip}"],
        capture_output=True, text=True, timeout=600,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        return f"Sync failed (exit {result.returncode}):\n{output}"
    return output or "Sync completed."


def cmd_sync():
    state = load_state()
    if not state.get("public_ip"):
        die("No VPS running — nothing to sync.")
    print(_sync(state["public_ip"]))
```

(c) Harden `load_config` and add `cmd_watch`; register `watch` in `COMMANDS`:
```python
def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text())
    except FileNotFoundError:
        die(f"Config file not found: {CONFIG_FILE}")
    except json.JSONDecodeError as e:
        die(f"Config file {CONFIG_FILE} is not valid JSON: {e}")
    except Exception as e:
        die(f"Cannot read config {CONFIG_FILE}: {e}")


def cmd_watch():
    cfg = load_config()
    token = cfg["telegram_token"]
    chat_id = cfg["telegram_chat_id"]
    password = cfg["webui_password"]
    synced = set()
    while True:
        time.sleep(60)
        state = load_state()
        ip = state.get("public_ip")
        if not ip:
            synced.clear()
            continue
        try:
            for t in poll_transmission(ip, password):
                if t["status"] == 6 and t["id"] not in synced:
                    synced.add(t["id"])
                    send_telegram(token, chat_id, f"Torrent done: {t['name']}\nSyncing to bananacapsule...")
                    send_telegram(token, chat_id, _sync(ip))
        except Exception as e:
            send_telegram(token, chat_id, f"Torrent watcher error: {e}")
```

And update the dispatch dict:
```python
COMMANDS = {
    "start":  cmd_start,
    "status": cmd_status,
    "sync":   cmd_sync,
    "stop":   cmd_stop,
    "watch":  cmd_watch,
}
```

- [ ] **Step 3: Byte-compile the new CLI to catch errors**

Run: `python -m py_compile roles/torrent/files/vps_torrent.py && echo OK`
Expected: `OK`

- [ ] **Step 4: Create the config template (from old telegram-bot template, unchanged)**

`roles/torrent/templates/vps_torrent_config.json.j2`:
```json
{
  "cloud_token":         "{{ vault_vps_cloud_token }}",
  "datacenter_id":       "{{ vault_vps_datacenter_id }}",
  "operator_ssh_pubkey": "{{ vault_fleet_keys[inventory_hostname].operator_pub }}",
  "bananacapsule_pubkey": "{{ vault_fleet_keys.bananacapsule.root_pub }}",
  "webui_password":      "{{ vault_vps_webui_password }}",
  "telegram_token":      "{{ vault_telegram_token }}",
  "telegram_chat_id":    "{{ vault_telegram_chat_id }}"
}
```

- [ ] **Step 5: Create the bot command wrapper**

`roles/torrent/templates/torrent.j2`:
```bash
#!/bin/bash
# description: Manage the on-demand torrent VPS (start|stop|status|sync)
exec sudo {{ torrent_install_dir }}/.venv/bin/python {{ torrent_install_dir }}/utils/vps_torrent.py "$@"
```

- [ ] **Step 6: Create the watcher service**

`roles/torrent/templates/torrent-watcher.service.j2`:
```
# Managed by Ansible (roles/torrent).
[Unit]
Description=Torrent VPS watcher (polls Transmission, syncs completed torrents)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={{ torrent_install_dir }}/.venv/bin/python {{ torrent_install_dir }}/utils/vps_torrent.py watch
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 7: Create the bananacapsule sync script template (from old telegram-bot template)**

`roles/torrent/templates/torrent_sync.sh.j2`:
```bash
#!/bin/bash
# /usr/local/bin/torrent_sync.sh <vps_ip>
# Ansible-managed — rsync completed downloads from torrent VPS to local NAS storage.
VPS_IP="$1"
[ -z "$VPS_IP" ] && echo "Usage: torrent_sync.sh <vps_ip>" && exit 1

mkdir -p "{{ torrent_sync_dest }}"
rsync -a --stats \
  -e "ssh -o StrictHostKeyChecking=accept-new -i /root/.ssh/id_ed25519" \
  root@"${VPS_IP}":/var/lib/transmission-daemon/downloads/ \
  "{{ torrent_sync_dest }}/"
```

- [ ] **Step 8: Create the tasks**

`roles/torrent/tasks/main.yml`:
```yaml
---
- name: Ensure utils dir exists in telegrambot install
  file:
    path: "{{ torrent_install_dir }}/utils"
    state: directory
    owner: "{{ torrent_user }}"
    group: "{{ torrent_user }}"
    mode: '0755'

- name: Deploy vps_torrent.py lifecycle + watcher script
  copy:
    src: vps_torrent.py
    dest: "{{ torrent_install_dir }}/utils/vps_torrent.py"
    owner: "{{ torrent_user }}"
    group: "{{ torrent_user }}"
    mode: '0755'
  notify: Restart torrent-watcher

- name: Deploy vps_torrent_config.json (vault secrets)
  template:
    src: vps_torrent_config.json.j2
    dest: "{{ torrent_install_dir }}/utils/vps_torrent_config.json"
    owner: "{{ torrent_user }}"
    group: "{{ torrent_user }}"
    mode: '0600'
  no_log: true
  notify: Restart torrent-watcher

- name: Deploy torrent command into the bot's scripts dir
  template:
    src: torrent.j2
    dest: "{{ torrent_install_dir }}/scripts/torrent"
    owner: "{{ torrent_user }}"
    group: "{{ torrent_user }}"
    mode: '0755'
  notify: Restart telegram-bot

- name: Deploy torrent-watcher systemd service
  template:
    src: torrent-watcher.service.j2
    dest: /etc/systemd/system/torrent-watcher.service
    mode: '0644'
    backup: yes
  notify: Restart torrent-watcher

- name: Enable and start torrent-watcher
  systemd:
    name: torrent-watcher
    enabled: yes
    state: started
    daemon_reload: yes

- name: Deploy torrent_sync.sh to bananacapsule
  template:
    src: torrent_sync.sh.j2
    dest: /usr/local/bin/torrent_sync.sh
    owner: root
    group: root
    mode: '0755'
  delegate_to: bananacapsule
  vars:
    torrent_sync_dest: "{{ hostvars['bananacapsule'].torrent_sync_dest }}"
```

- [ ] **Step 9: Create handlers**

`roles/torrent/handlers/main.yml`:
```yaml
---
- name: Restart torrent-watcher
  systemd:
    name: torrent-watcher
    state: restarted
    daemon_reload: yes

- name: Restart telegram-bot
  systemd:
    name: telegram-bot
    state: restarted
    daemon_reload: yes
```

> Note: the `Restart telegram-bot` handler is duplicated here because handlers are role-scoped by name resolution across the play; defining it in this role guarantees the `torrent` command notify resolves even if role ordering changes.

- [ ] **Step 10: Commit**

```bash
git add roles/torrent
git commit -m "torrent: new role — torrent command + standalone watcher service"
```

---

### Task B7: Wire the new roles into the playbook

**Files:**
- Modify: `playbooks/raspberrino.yml`

- [ ] **Step 1: Update the roles list and ordering**

Replace the `roles:` block in `playbooks/raspberrino.yml` with (tool-providing roles run before `telegram-bot` so its symlink/wrapper targets exist; `torrent` runs after, since it writes into the bot's `scripts/` and `utils/` dirs):
```yaml
  roles:
    - { role: common,          tags: [common] }
    - { role: packages,        tags: [packages] }
    - { role: dev,             tags: [dev] }
    - { role: base,            tags: [base] }
    - { role: motd,            tags: [motd] }
    - { role: state-mounts,    tags: [state-mounts] }
    - { role: energenie,       tags: [energenie] }
    - { role: windows-control, tags: [windows-control] }
    - { role: ssh-tunnel,      tags: [ssh-tunnel] }
    - { role: telegram-bot,    tags: [telegram-bot] }
    - { role: torrent,         tags: [torrent] }
    - { role: pihole,          tags: [pihole] }
    - { role: monit,           tags: [monit] }
    - { role: monit-dashboard, tags: [monit-dashboard] }
```

- [ ] **Step 2: Full syntax check (all roles now exist)**

Run: `ansible-playbook -i inventory playbooks/raspberrino.yml --syntax-check`
Expected: no errors.

- [ ] **Step 3: Lint (if available)**

Run: `ansible-lint playbooks/raspberrino.yml roles/telegram-bot roles/torrent roles/windows-control roles/ssh-tunnel roles/energenie || true`
Expected: review output; fix any genuine errors (warnings are acceptable).

- [ ] **Step 4: Commit**

```bash
git add playbooks/raspberrino.yml
git commit -m "playbooks: wire energenie/windows-control/ssh-tunnel/torrent; order tool roles before telegram-bot"
```

---

### Task B8: Dry-run verification

- [ ] **Step 1: Check-mode dry run against raspberrino**

Run:
```bash
ansible-playbook -i inventory playbooks/raspberrino.yml \
  --tags "telegram-bot,energenie,windows-control,ssh-tunnel,torrent" \
  --check --diff
```
Expected: completes without fatal errors. Review the diff: it should show the new `scripts/*` files, the new role files, and the new `torrent-watcher.service`. `--check` may report errors for tasks that depend on prior-task results (e.g. pip in a venv not yet created on a fresh run) — note these and confirm they are check-mode artifacts, not real failures.

- [ ] **Step 2: Push the Ansible branch**

```bash
git push
```

---

# PHASE C — Deploy + one-time manual cleanup

This phase runs against the live host. The playbook does **not** clean up the old layout; that is done by hand here, once.

### Task C1: One-time manual cleanup on raspberrino

Run these by hand (not in the playbook). They remove artifacts the old layout created that the new layout never references.

- [ ] **Step 1: Snapshot what exists now (for safety)**

```bash
ssh -i ~/.ssh/ansible_key root@raspberrino \
  'ls -la /opt/telegrambot; echo ---; ls -la /opt/telegrambot/commands 2>/dev/null'
```

- [ ] **Step 2: Remove the obsolete in-bot command plugins**

The new `main` has no `commands/` dir; `git pull` (via the role's `force: yes`) removes tracked files, but the Ansible-deployed `vps_torrent_commands.py` was untracked and the dir may persist. Remove it:
```bash
ssh -i ~/.ssh/ansible_key root@raspberrino 'rm -rf /opt/telegrambot/commands'
```

- [ ] **Step 3: Remove obsolete core modules if any linger as untracked .pyc/__pycache__**

```bash
ssh -i ~/.ssh/ansible_key root@raspberrino \
  'rm -rf /opt/telegrambot/core/__pycache__ /opt/telegrambot/commands 2>/dev/null; true'
```

### Task C2: Run the playbook and verify

- [ ] **Step 1: Run the playbook for real**

```bash
cd /home/chris/2026_audit/fish_and_chips_infra
ansible-playbook -i inventory playbooks/raspberrino.yml \
  --tags "telegram-bot,energenie,windows-control,ssh-tunnel,torrent"
```
Expected: changed tasks for the git update, scripts deployment, new services; handlers restart telegram-bot and torrent-watcher.

- [ ] **Step 2: Verify services are up**

```bash
ssh -i ~/.ssh/ansible_key root@raspberrino \
  'systemctl is-active telegram-bot torrent-watcher ssh-tunnel'
```
Expected: `active` for all three.

- [ ] **Step 3: Verify the bot loaded the expected commands**

```bash
ssh -i ~/.ssh/ansible_key root@raspberrino \
  'journalctl -u telegram-bot -n 20 --no-pager | grep -i "Loaded.*commands"'
```
Expected: a line listing `df, last, mem, restart, shutdown-nuky, torrent, tunnel-ssh, uptime, url, vpn-restart`.

- [ ] **Step 4: Verify scripts dir contents**

```bash
ssh -i ~/.ssh/ansible_key root@raspberrino 'ls -la /opt/telegrambot/scripts'
```
Expected: `restart`, `shutdown-nuky`, `tunnel-ssh`, `vpn-restart`, `torrent` (all executable), plus `.gitkeep`.

- [ ] **Step 5: Functional smoke test from Telegram (manual)**

From your authorised Telegram account, send: `uptime`, `df`, then `restart` (should print usage), then `torrent status`. Confirm sane replies. Confirm `exec echo hello` emails a password and `PASSWORD: <pw>` runs it.

- [ ] **Step 6: Update the memory index**

Note in project memory that the redesign is deployed (bot = script runner; torrent watcher = its own service; Ansible split into energenie/windows-control/ssh-tunnel/telegram-bot/torrent).

---

## Notes for the implementer

- **Phase order is strict:** A (push to main) → B (Ansible) → C (deploy). The role's `git` task pulls `main`, so the bot code must be pushed first.
- **No cleanup tasks in the playbook** — Task C1 is the only place stale artifacts are removed, and it is manual by design.
- **vault variables** referenced (`vault_windows_pc_*`, `vault_vps_*`, `vault_telegram_*`, `vault_fleet_keys`, `vault_github_deploy_key`, `vault_telegrambot_username`, `vault_msmtp_gmail_*`) are unchanged — they already exist in the vault; the roles just reference them from new locations.
- If `ansible-lint` is not installed, skip that step; `--syntax-check` and `--check --diff` are the required gates.
```
