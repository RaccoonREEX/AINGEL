"""Loopback development server with persistent local session secret and optional Meta key file."""

import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file", type=Path)
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[1]
    local = backend.parent / ".local"
    local.mkdir(exist_ok=True)
    secret = local / "server-secret.txt"
    if not secret.exists():
        secret.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    os.environ["DJANGO_SECRET_KEY"] = secret.read_text(encoding="utf-8").strip()
    os.environ["DJANGO_DEBUG"] = "0"
    os.environ["AINGEL_AI_MODE"] = "mock"
    if args.key_file:
        try:
            content = args.key_file.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            raise SystemExit("Credential file unreadable; no secret printed.") from None
        candidates = set(re.findall(r"LLM_[A-Za-z0-9_-]+", content))
        if len(candidates) != 1:
            raise SystemExit("Expected exactly one Meta key in credential file.")
        os.environ["MODEL_API_KEY"] = candidates.pop()
        os.environ["AINGEL_AI_MODE"] = "meta"
        os.environ["AINGEL_SYNTHETIC_TESTS_ONLY"] = "1"
        del content, candidates
    try:
        return subprocess.call(
            [sys.executable, "manage.py", "runserver", "127.0.0.1:8010", "--noreload"],
            cwd=backend,
        )
    finally:
        os.environ.pop("MODEL_API_KEY", None)


if __name__ == "__main__":
    raise SystemExit(main())
