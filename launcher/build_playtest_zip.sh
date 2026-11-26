#!/usr/bin/env bash
# Builds a self-contained playtest zip (no GitHub needed on the tester's PC):
#   Adventurer-Kings-Playtest/{Avvia_GM_Interface.bat, LEGGIMI_TESTER.txt, VERSION.txt, ak_engine/, launcher/run_server.py}
# Usage: launcher/build_playtest_zip.sh [output.zip]
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
out="${1:-$root/Adventurer-Kings-Playtest.zip}"
work="$(mktemp -d)"
dir="$work/Adventurer-Kings-Playtest"
mkdir -p "$dir/ak_engine" "$dir/launcher"
cp "$root/launcher/Avvia_GM_Interface.bat" "$root/launcher/LEGGIMI_TESTER.txt" "$dir/"
cp "$root/launcher/run_server.py" "$dir/launcher/"
cp "$root/ak_engine/pyproject.toml" "$dir/ak_engine/"
# Only the program itself: no tests, no README of the dev log, no caches.
(cd "$root/ak_engine" && git ls-files src | xargs -I{} cp --parents {} "$dir/ak_engine/")
{ git -C "$root" rev-parse HEAD; git -C "$root" log -1 --format="  %h  %cd  %s" --date=short; } | tr -d '\r' | sed 's/$/\r/' > "$dir/VERSION.txt"
rm -f "$out"
(cd "$work" && zip -q -r "$out" Adventurer-Kings-Playtest)
echo "$out"
