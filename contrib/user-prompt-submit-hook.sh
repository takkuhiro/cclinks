#!/bin/bash
# Claude Code UserPromptSubmit hook for `cclinks --active`.
#
# A picker launched from a hotkey is not a child of Claude Code, so it cannot read
# CLAUDE_CODE_SESSION_ID. Picking the transcript with the newest mtime instead picks
# whichever session wrote last, which may be another tab working through a long task
# while you watch this one. This records the session you are typing into.
#
# Install: copy somewhere, chmod +x, then in ~/.claude/settings.json:
#
#   "hooks": {
#     "UserPromptSubmit": [
#       { "hooks": [ { "type": "command",
#                      "command": "bash /path/to/user-prompt-submit-hook.sh",
#                      "timeout": 5 } ] }
#     ]
#   }
#
# Requires jq. Writes nothing to stdout on purpose: a UserPromptSubmit hook's stdout
# is added to the prompt's context.

input=$(cat)
transcript=$(echo "$input" | jq -r '.transcript_path // empty')
[ -z "$transcript" ] && exit 0

target="${CCLINKS_ACTIVE_FILE:-$HOME/.claude/cclinks-active.json}"
# Write then swap, so a reader never sees a half-written file. The prompt itself is
# not recorded -- only what is needed to find the transcript again.
echo "$input" | jq -c '{session_id, transcript_path, cwd}' > "$target.tmp" 2>/dev/null \
  && mv -f "$target.tmp" "$target"
exit 0
