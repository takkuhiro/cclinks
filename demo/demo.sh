#!/usr/bin/env bash
# Drives the README demo.
#
# Prints a reply the way Claude Code prints one — Markdown links become OSC 8
# hyperlinks, so only the label is on screen and the URL is nowhere in the
# terminal buffer — then runs cclinks against a fixture transcript.
#
# The transcript lives under a throwaway HOME so the recording never touches
# your real sessions.

set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)

home=$(mktemp -d)
trap 'rm -rf "$home"' EXIT
mkdir -p "$home/.claude/projects/-demo"
cp "$here/session.jsonl" "$home/.claude/projects/-demo/session.jsonl"

link() { printf '\e]8;;%s\e\\%s\e]8;;\e\\' "$2" "$1"; }

printf '\e[1m>\e[0m Give me a few references.\n\n'
printf 'Here are the references for what we discussed.\n\n'
printf '  - '; link "Astral'\''s uv documentation" "https://docs.astral.sh/uv/"; printf '\n'
printf '  - '; link "The fzf repository" "https://github.com/junegunn/fzf"; printf '\n'
printf '  - '; link "Ruff'\''s rule index" "https://docs.astral.sh/ruff/rules/"; printf '\n'
printf '  - '; link "DuckDB documentation" "https://duckdb.org/docs/"; printf '\n'
printf '  - '; link "The Rust book" "https://doc.rust-lang.org/book/"; printf '\n'
printf '\nLet me know which one you want to dig into.\n\n'

HOME="$home" cclinks --latest
