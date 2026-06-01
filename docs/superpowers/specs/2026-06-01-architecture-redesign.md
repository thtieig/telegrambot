# Telegrambot Architecture Redesign

**Date:** 2026-06-01
**Status:** Approved

---

## Goal

Make the bot a small, reusable, generic "run my scripts via Telegram" engine. Delete the plugin system. Move host-specific scripts and secrets out of the bot repo into Ansible. Make adding/removing a command a one-line change.

---

## Core realisation

The complexity is the plugin system. Every command is a `BaseCommandHandler` subclass, dynamically imported via `importlib`, implementing `can_handle`/`execute`/`get_help`. That machinery exists for ~2 commands that genuinely need state; the other 90% are "run a shell command, send the output".

**Decision: delete the plugin system entirely. A command is a file.**

Two commands genuinely need more than request/response and are handled as explicit exceptions:
- `exec` — needs state across two messages (send password → wait for reply). Kept as a single hardcoded framework feature.
- `torrent` watcher — pushes messages proactively on a timer. Moved out of the bot into its own systemd service.

After this, the bot has **no plugin system and no async background state.**

---

## Repo split

| Repo | Contents | Visibility |
|---|---|---|
| `telegrambot` | Generic bot engine, universal built-in scripts, `exec` | Public |
| `fish_and_chips_infra` (Ansible) | Host-specific scripts, secrets, torrent feature | Private |

---

## Bot repo: target structure

```
telegrambot/
├── telegrambot.py           # main loop: auth → route → run → sanitise → chunk → reply
├── config.py.template
├── requirements.txt
├── core/
│   ├── __init__.py
│   ├── auth.py              # authorised user check (unchanged)
│   ├── runner.py            # run a file, capture stdout+stderr, 30s timeout (was shell_utils.py)
│   ├── output.py            # strip control chars + chunk for Telegram (was message_utils.py)
│   └── exec.py              # the ONE built-in stateful command
├── builtin/                 # universal scripts, tracked in git, zero-config
│   ├── uptime
│   ├── df
│   ├── last
│   ├── mem
│   └── url                  # wraps utils/fetch_clean_url.py
├── scripts/                 # host-specific drop-in, gitignored
│   └── .gitkeep
├── utils/
│   └── fetch_clean_url.py   # helper called by builtin/url (unchanged)
├── docs/
└── extras/                  # reference/sample deployment files (kept, see note)
```

**Deleted from the repo:** `core/command_loader.py`, `core/message_utils.py`, `core/shell_utils.py`, the entire `commands/` directory (all six `*_commands.py` files).

---

## How the bot works

On startup, scan `builtin/` then `scripts/`. Build a name→path map of every regular file (filename = command name). `scripts/` overrides `builtin/` on name collision.

On each message (after auth):

1. `exec`/`PASSWORD` prefixes → routed to the built-in `exec` feature (special-cased before script lookup).
2. Message looks like a URL (`^\s*https?://`) → rewrite to `url <message>` for convenience.
3. First token = command name → look up in the map.
   - Found → run `<path> <remaining args>` via `runner`, sanitise + chunk output, reply.
   - Not found → reply with help (list of command names + their `# description:` line).

**Argument passing:** Unix-style, transparent. `restart router` runs `scripts/restart router`. No parsing.

**Output handling** is a framework concern applied to *all* command output: capture stdout+stderr, 30s timeout, strip control characters Telegram rejects, chunk to ≤3500 chars.

**Help text** for each script comes from a `# description: <text>` comment on line 2. Missing → list filename only.

---

## Script conventions

Any executable file, any language:

```bash
#!/bin/bash
# description: Show disk usage
df -h
```

- Line 1: shebang
- Line 2: `# description: <text>` (optional, recommended)
- Executable bit set

---

## The `exec` built-in

Ported from `commands/exec_commands.py` into `core/exec.py`, keeping the email-2FA flow. State files stay under `$TELEGRAMBOT_STATE_DIR` (default `/var/lib/telegrambot`).

Two security fixes applied during the move:
- Use `secrets.choice` instead of `random.choice` for password generation.
- Pass the stored command to the shell as an argument, not embedded in generated bash script text (avoids metacharacter injection into the script body).

---

## The torrent feature: out of the bot

Today `commands/vps_torrent_commands.py` runs an in-bot async watcher that must be resumed on restart. This is removed from the bot entirely.

**`torrent` becomes a plain script** (`scripts/torrent`, deployed by Ansible) that calls the existing `vps_torrent.py` CLI:
```
torrent start|stop|status|sync  →  sudo .venv/bin/python utils/vps_torrent.py <subcmd>
```

**The watcher becomes `torrent-watcher.service`** — a standalone systemd service running a new `vps_torrent.py watch` subcommand. It:
- Polls the state file each loop; idle when no VPS exists, active when one does.
- Polls Transmission, sends Telegram messages directly via the bot token (already in config).
- On torrent completion, triggers `sync`.
- Is `enabled` and always running; systemd handles restart-on-failure.

The bot needs no knowledge of torrents beyond the `torrent` script being present in `scripts/`.

Two fixes applied during the move:
- Watcher notifies on errors instead of silently swallowing all exceptions.
- Config load handles a missing/invalid config file with a clear error.

---

## Bare-URL convenience

Keep the "paste a URL" convenience as a small framework normalisation: if a message matches `^\s*https?://`, route it to the `url` command. If `url` is not present (e.g. someone removed it), fall through to help.

---

## Ansible: three roles instead of one

### Role 1 — `telegram-bot` (generic framework, reusable)

Responsibilities only:
- Create `telegrambot` system user, install dir, venv, pip install.
- Clone the public repo, deploy `config.py` (from vault), deploy systemd unit.
- Create the empty `scripts/` drop-in dir.
- Deploy the host's command scripts by **looping over a data-driven list** — no script names hardcoded in the role.

Data-driven list lives in `host_vars/raspberrino.yml`:

```yaml
telegram_bot_scripts:
  - { name: vpn-restart,   inline: "sudo systemctl restart openvpn.service" }
  - { name: tunnel-ssh,    inline: "sudo systemctl restart ssh-tunnel" }
  - { name: restart,       link:   /usr/local/bin/restart_device }
  - { name: shutdown-nuky, link:   /usr/local/bin/shutdown-nuky }
```

Three entry types the role handles:
- `inline` — role generates a one-line wrapper script (with shebang + `# description`).
- `link` — symlink in `scripts/` pointing at an existing `/usr/local/bin` binary (usable from shell too).
- `template` — deploy a real script file from the role's templates.

This is the single source of truth for "what can the bot do on this host."

### Role 2 — `energenie` (already exists, unchanged)

Already deploys `/usr/local/bin/energenie` and `/usr/local/bin/restart_device`. The `link:` entry in the list exposes `restart_device` to the bot. No change to this role beyond confirming it runs before `telegram-bot` (so the link target exists).

### Role 3 — `torrent` (new — owns the complex feature)

Owns everything torrent, all in one place:
- `vps_torrent.py` CLI → `{{ install_dir }}/utils/vps_torrent.py` (with new `watch` subcommand).
- `vps_torrent_config.json` (vault secrets) → `{{ install_dir }}/utils/`.
- `torrent` script → dropped into the bot's `scripts/` dir.
- `torrent-watcher.service` → systemd unit, enabled + started.
- `torrent_sync.sh` → delegated to bananacapsule (as today).

Runs after `telegram-bot` (needs `scripts/` to exist).

---

## requirements.txt

`requests` and `beautifulsoup4` remain (used by `builtin/url` via `fetch_clean_url.py`). `python-telegram-bot`, `nest_asyncio` remain. The bot itself no longer needs anything new.

---

## Documentation

Rewrite `README.md` around the new model:
- The bot runs scripts from a folder. Filename = command.
- Add a command: drop an executable in `scripts/` with a `# description:` line. Or, on this fleet, add one line to `host_vars`.
- Expose a `/usr/local/bin` tool to the bot: add a `link:` entry.
- The one built-in special command: `exec` (with its security notes + sudoers section, kept).
- Remove all references to `commands/`, `BaseCommandHandler`, the plugin architecture, individual-handler testing.

---

## Out of scope / manual

Per the operator's rule, the playbook describes the **fresh-install desired state only** — no remove/fix/migration tasks. Cleanup of the *existing* raspberrino deploy (stale `commands/` dir, old in-bot torrent handler, etc.) is a one-time **manual** checklist, kept separate from the playbook.

`extras/` sample files in the repo are kept as-is (reference only, not used at runtime).
