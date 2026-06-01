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
