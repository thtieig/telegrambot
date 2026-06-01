# Telegrambot Architecture Redesign

**Date:** 2026-06-01  
**Status:** Approved

---

## Goal

Simplify the bot so that adding, removing, or understanding a command requires no Python knowledge and no framework boilerplate. One folder, drop a script in, it works.

---

## Repo Split

| Repo | What lives there | Visibility |
|---|---|---|
| `telegrambot` | Bot framework, core logic, built-in commands | Public |
| Private scripts | Personal scripts, `vps_torrent`, config | Private (Ansible-managed) |

The public repo has no personal data. Anyone can clone it and run their own instance.

---

## Folder Structure

```
telegrambot/
├── telegrambot.py           # entry point, unchanged
├── config.py.template       # configuration template
├── requirements.txt
├── core/
│   ├── auth.py              # authentication (unchanged)
│   ├── command_loader.py    # updated: scans builtins/ and scripts/
│   ├── message_utils.py     # chunking, url detection (unchanged)
│   └── shell_utils.py       # subprocess wrapper (unchanged)
├── builtins/                # ships with the framework, committed to public repo
│   ├── exec.py              # Python plugin — secure arbitrary command execution
│   ├── url.py               # Python plugin — fetch and clean a webpage
│   ├── uptime               # bash script
│   ├── df                   # bash script
│   ├── last                 # bash script
│   ├── mem                  # bash script (free -h)
│   ├── myip                 # bash script (public + local IP)
│   └── ping                 # bash script (passes args through)
├── scripts/                 # gitignored, empty in public repo, Ansible-managed
│   └── .gitkeep
├── utils/
│   └── fetch_clean_url.py   # helper called by builtins/url.py (unchanged)
├── docs/
└── extras/                  # reference/sample deployment files (unchanged)
```

The `commands/` folder is removed entirely.

---

## Command Discovery

The loader scans `builtins/` then `scripts/` on startup.

**Resolution rules:**

1. A file in `scripts/` with the same name as a file in `builtins/` wins — `scripts/` always overrides built-ins.
2. A `.py` file containing a `BaseCommandHandler` subclass → loaded as a Python plugin.
3. Any file with the executable bit set (that is not a `.py` plugin) → run as a subprocess.
4. Anything else is ignored.

**Load order matters for help text and command routing** — `scripts/` entries appear after `builtins/` in the help list, but take routing priority.

---

## Running Scripts

When a message arrives:

1. First token = command name. Looked up against loaded commands (by filename, without extension for `.py` plugins).
2. Remaining tokens = arguments, passed as-is to the script (`$1`, `$2`, ... or `sys.argv[1:]`).
3. Stdout + stderr captured, sent to Telegram (chunked if long).
4. 30-second timeout. Exit code non-zero: output is still sent (may contain useful error text).

Examples:

| Telegram message | What runs |
|---|---|
| `uptime` | `builtins/uptime` |
| `ping 8.8.8.8` | `builtins/ping 8.8.8.8` |
| `restart router` | `scripts/restart router` |
| `torrent start` | `scripts/vps_torrent.py` plugin, `can_handle("torrent start")` |
| `exec rm -rf /tmp/test` | `builtins/exec.py` plugin |
| `https://example.com` | `builtins/url.py` plugin (bare URL detection) |

---

## Script Conventions

**Executable scripts** (bash, python, anything):

```bash
#!/bin/bash
# description: Show disk usage
df -h
```

- Line 1: shebang
- Line 2: `# description: <text>` — used in help output. Optional but recommended.
- Must have executable bit: `chmod +x`

**Python plugins** (stateful / multi-step commands):

- Inherit from `BaseCommandHandler` (unchanged interface)
- `can_handle()`, `execute()`, `get_help()` as today
- Do NOT need the executable bit

---

## Scripts Available on the Host AND in the Bot

Scripts that need to be usable by a regular user on the shell AND via Telegram follow this pattern:

- Real script lives in `/usr/local/bin/<name>` (system-wide, in PATH)
- Ansible creates a symlink: `/opt/telegrambot/scripts/<name>` → `/usr/local/bin/<name>`
- Bot discovers the symlink as a normal executable

```
/usr/local/bin/shutdown-nuky       ← real file, usable by chris
/opt/telegrambot/scripts/shutdown-nuky  → symlink
```

Ansible task example:
```yaml
- name: Symlink shutdown-nuky into telegrambot scripts
  file:
    src: /usr/local/bin/shutdown-nuky
    dest: /opt/telegrambot/scripts/shutdown-nuky
    state: link
```

---

## Migration: What Moves Where

| Current location | New location |
|---|---|
| `commands/system_commands.py` | Replaced by `builtins/uptime`, `builtins/df`, `builtins/last` (bash scripts) |
| `commands/service_commands.py` | Replaced by `scripts/vpn-restart`, `scripts/tunnel-ssh` (bash, private) |
| `commands/restart_commands.py` | Replaced by `scripts/restart` (bash, private, calls existing `/usr/local/bin/restart_device`) |
| `commands/windows_commands.py` | Replaced by symlink: `scripts/shutdown-nuky` → `/usr/local/bin/shutdown-nuky` |
| `commands/exec_commands.py` | Moved to `builtins/exec.py` (unchanged logic) |
| `commands/url_fetch.py` | Moved to `builtins/url.py` (unchanged logic) |
| `commands/vps_torrent_commands.py` | Renamed to `vps_torrent.py`, moved to private `scripts/` (Ansible-managed). Class renamed `VpsTorrentHandler`. |
| `utils/vps_torrent.py` | Stays at `utils/vps_torrent.py` — called as subprocess by the plugin, not a command itself. |

---

## Documentation

The `README.md` is rewritten to reflect the new mental model:

- **How to add a command:** drop an executable script in `scripts/`, add a `# description:` line, done.
- **How to add a complex command:** create a `.py` file with a `BaseCommandHandler` subclass in `scripts/`.
- **How to make a script available on the host too:** put it in `/usr/local/bin/`, symlink into `scripts/`.
- Remove all references to `commands/`, `BaseCommandHandler` boilerplate examples, old plugin architecture.
- Keep the sudoers section and security section (`exec` docs).

---

## Known Issues Fixed (from audit)

These are addressed during the rewrite:

- `exec`: use `secrets.choice` instead of `random.choice` for password generation
- `exec`: pass stored command as argument, not embedded in bash script text
- `vps_torrent` watcher: add error notification instead of silently swallowing exceptions
- `vps_torrent._load_cfg()`: add error handling for missing config file
