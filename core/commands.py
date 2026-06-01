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
