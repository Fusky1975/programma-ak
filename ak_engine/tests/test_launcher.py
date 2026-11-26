"""The Windows launcher shipped in ``launcher/`` (a .bat that a tester double-clicks)."""

from __future__ import annotations

import re
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[2] / "launcher"


def test_the_bat_is_plain_ascii_with_windows_line_endings():
    raw = (LAUNCHER / "Avvia_GM_Interface.bat").read_bytes()
    raw.decode("ascii")  # cmd.exe reads it in the OEM code page: no accented letters
    assert raw.count(b"\r\n") == raw.count(b"\n")  # every line ends in CRLF


def test_the_bat_calls_only_labels_and_files_that_exist():
    text = (LAUNCHER / "Avvia_GM_Interface.bat").read_text(encoding="ascii")
    labels = set(re.findall(r"^:(\w+)", text, flags=re.M))
    for target in re.findall(r"(?:goto|call)\s+:(\w+)", text):
        assert target in labels, target
    assert (LAUNCHER / "run_server.py").exists() and "launcher\\run_server.py" in text


def test_every_parenthesis_that_is_echoed_inside_a_block_is_escaped():
    # An unescaped ")" in an echo ends the surrounding ( ... ) block early and breaks the script.
    text = (LAUNCHER / "Avvia_GM_Interface.bat").read_text(encoding="ascii")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("echo") and not stripped.lower().startswith(("echo.", "echo off")):
            assert re.search(r"(?<!\^)[()]", stripped) is None, stripped


def test_the_server_script_has_a_main():
    source = (LAUNCHER / "run_server.py").read_text(encoding="utf-8")
    assert "debug=False" in source and "server.log" in source
