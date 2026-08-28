#!/usr/bin/env python3
"""Validate apps/extension layout, manifest, and JS syntax (Node when available)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "apps" / "extension"

REQUIRED_FILES = (
    "manifest.json",
    "background.js",
    "content.js",
    "options.html",
    "options.js",
    "popup.html",
    "popup.js",
    "README.md",
    "lib/config.js",
    "lib/api.js",
    "lib/capture.js",
    "lib/tabs.js",
    "lib/excludes.js",
)

IMPORT_SCRIPTS = re.compile(r"""importScripts\s*\(\s*(['"].+?['"](?:\s*,\s*['"].+?['"])*)\s*\)""")
SCRIPT_SRC = re.compile(r"""<script[^>]+src=["']([^"']+)["']""", re.I)


def _fail(msg: str) -> None:
    print(f"validate-extension: {msg}", file=sys.stderr)
    sys.exit(1)


def _quoted_paths(import_args: str) -> list[str]:
    return re.findall(r"""['"]([^'"]+)['"]""", import_args)


def _check_files_exist(relative_paths: set[str]) -> None:
    for rel in sorted(relative_paths):
        if not (EXT / rel).is_file():
            _fail(f"missing referenced file: {rel}")


def _load_manifest() -> dict:
    manifest_path = EXT / "manifest.json"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _fail(f"invalid manifest.json: {exc}")
    if data.get("manifest_version") != 3:
        _fail("manifest_version must be 3")
    sw = (data.get("background") or {}).get("service_worker")
    if sw != "background.js":
        _fail("background.service_worker must be background.js")
    hosts = data.get("host_permissions") or []
    if not any("127.0.0.1:8787" in h for h in hosts):
        _fail("host_permissions must include loopback 127.0.0.1:8787")
    for entry in data.get("content_scripts") or []:
        for js in entry.get("js") or []:
            _check_files_exist({js})
    return data


def _collect_js_references() -> set[str]:
    refs: set[str] = {"background.js"}
    bg = (EXT / "background.js").read_text(encoding="utf-8")
    match = IMPORT_SCRIPTS.search(bg)
    if not match:
        _fail("background.js must call importScripts(...)")
    refs.update(_quoted_paths(match.group(1)))
    for html_name in ("options.html", "popup.html"):
        html = (EXT / html_name).read_text(encoding="utf-8")
        refs.update(SCRIPT_SRC.findall(html))
        refs.add(html_name.replace(".html", ".js"))
    refs.add("content.js")
    return refs


def _check_js_syntax(js_files: list[Path]) -> None:
    node = shutil.which("node")
    if not node:
        print("validate-extension: node not found — skipping JS syntax check")
        return
    for path in js_files:
        proc = subprocess.run(
            [node, "--check", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            _fail(f"JS syntax error in {path.relative_to(ROOT)}: {detail}")


def main() -> None:
    if not EXT.is_dir():
        _fail(f"extension dir not found: {EXT}")
    for rel in REQUIRED_FILES:
        if not (EXT / rel).is_file():
            _fail(f"missing required file: {rel}")
    _load_manifest()
    refs = _collect_js_references()
    _check_files_exist(refs)
    js_files = sorted(EXT.rglob("*.js"))
    _check_js_syntax(js_files)
    print(f"validate-extension: OK ({len(REQUIRED_FILES)} required files, {len(js_files)} JS)")


if __name__ == "__main__":
    main()
