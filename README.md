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

## Buttons (rich output)

Every script run gets these environment variables:

- `TG_CHAT_ID`: the chat the command came from (always set).
- `TG_TRIGGER`: `text` (typed message) or `button` (an inline button was tapped).
- `TG_MESSAGE_ID`: id of the message whose button was tapped (button trigger only).

If stdout starts with the exact line `#telegram-json`, the rest is one JSON object
(the object may also follow the marker on the same line):

```json
{"text": "Move Mummies (2023)?",
 "buttons": [[{"text": "Yes", "cmd": "tidy yes abc123"}, {"text": "No", "cmd": "tidy close"}]],
 "edit": true, "silent": false}
```

- `text`: the message text.
- `buttons`: optional rows of inline buttons. `cmd` is handled exactly like typed
  text when tapped (same command lookup, same authorisation), with `TG_TRIGGER=button`.
  `cmd` is limited to 64 bytes (UTF-8); longer buttons are dropped with a log warning.
- `edit`: defaults to true for a button tap, which edits the tapped message (text and
  buttons; no buttons removes the keyboard). `false`, or a typed trigger, sends a new message.
- `silent`: true sends nothing (use when a background worker will message or edit by itself).

Malformed JSON is sent as plain text. Output without the marker behaves as before.
A detached worker can put the same buttons in `reply_markup` itself (`inline_keyboard`,
`callback_data` = the `cmd` string) and taps on its messages work too.

Example (`scripts/ask`):

```bash
#!/bin/bash
# description: Example with buttons
cat <<JSON
#telegram-json
{"text": "Trigger was ${TG_TRIGGER}. Pick one:",
 "buttons": [[{"text": "Uptime", "cmd": "uptime"}, {"text": "Disk", "cmd": "df"}]]}
JSON
```

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
