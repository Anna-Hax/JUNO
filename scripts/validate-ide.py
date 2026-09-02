#!/usr/bin/env python3
"""Validate apps/ide layout, required modules, and Python syntax."""

from __future__ import annotations

import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDE = ROOT / "apps" / "ide"

REQUIRED_FILES = (
    "README.md",
    "cursor_vscdb.py",
    "config.py",
    "api.py",
    "sync.py",
    "smoke.py",
)


def _fail(msg: str) -> None:
    print(f"validate-ide: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not IDE.is_dir():
        _fail(f"ide dir not found: {IDE}")
    for rel in REQUIRED_FILES:
        path = IDE / rel
        if not path.is_file():
            _fail(f"missing required file: {rel}")
    py_files = sorted(IDE.glob("*.py"))
    for path in py_files:
        text = path.read_text(encoding="utf-8")
        if "0.0.0.0" in text:
            _fail(f"{path.name} must not bind 0.0.0.0")
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            _fail(f"syntax error in {path.name}: {exc}")
    print(f"validate-ide: OK ({len(REQUIRED_FILES)} required files, {len(py_files)} py)")


if __name__ == "__main__":
    main()
