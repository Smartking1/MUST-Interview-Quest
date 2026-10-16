"""Run a command with variables from .env added to its environment. Never prints values.

Usage: python audit/harness/with_env.py <command> [args...]
Parses KEY=VALUE lines, trims spaces and trailing comments, ignores blanks
and comment lines. Exists because shell `source .env` executes malformed
lines and can echo secrets in its errors.
"""

import os
import sys
from pathlib import Path


def load(path: Path) -> dict[str, str]:
    env = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #")[0].strip().strip('"').strip("'")
        if value:
            env[key.strip()] = value
    return env


if __name__ == "__main__":
    os.execvpe(sys.argv[1], sys.argv[1:], {**os.environ, **load(Path(__file__).resolve().parents[2] / ".env")})
