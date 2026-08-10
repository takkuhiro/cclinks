# cclinks

**English** | [日本語](README.ja.md)

Open links from your Claude Code session with the keyboard, without touching the mouse.

Claude Code renders `[label](url)` as **the label only**. The URL never reaches the terminal
buffer, so tools that scrape the screen — `tmux-fzf-url`, your terminal's own link detector,
VS Code's *Open Detected Link* — cannot find it. There is nothing on screen to find.

`cclinks` reads the session transcript instead, where the URLs are still intact.

![cclinks in action](docs/demo.gif)

The `Sources:` list behind the popup is what Claude Code actually printed: labels, and not
one URL among them. The picker has all eleven.

Pick with the arrow keys or by typing, press Enter, and the link opens in your browser.

## Why not just scrape the screen, or click the link?

|                              | Screen scraping | Ctrl/⌘-click | cclinks |
| ---------------------------- | --------------- | ------------ | ------- |
| Bare URLs                    | Yes             | Yes          | Yes     |
| Markdown links               | **No**          | Yes¹         | Yes     |
| Scrolled out of view         | **No**          | **No**       | Yes     |
| Label available for search   | No              | No           | Yes     |
| Without leaving the keyboard | Yes             | **No**       | Yes     |

¹ In terminals that render OSC 8 hyperlinks — iTerm2, WezTerm, Ghostty, the VS Code and
Cursor integrated terminals. The URL is still absent from the buffer; the terminal holds it
out of band.

Clicking works, and it is the reason this tool is not about *reaching* the link. It is about
not moving your hand to reach it. If your hands are on the keyboard while Claude is talking,
they stay there.

Screen scrapers are still useful for file paths and for output from other programs.
The two complement each other; bind them to neighbouring keys.

## Install

Requires Python 3.10+ and [fzf](https://github.com/junegunn/fzf).

```sh
uv tool install git+https://github.com/takkuhiro/cclinks
```

Or with pipx:

```sh
pipx install git+https://github.com/takkuhiro/cclinks
```

## Usage

```sh
cclinks              # pick a link and open it
cclinks --print      # list links, open nothing
cclinks --active     # use the session you last typed into (needs a hook, below)
cclinks --latest     # ignore the working directory, use the newest session
cclinks --cwd PATH   # target the session for a specific directory
cclinks --no-color   # do not color the picker
```

Links are listed newest first, deduplicated. When the same URL appears both as a bare
URL and as a Markdown link, the label is kept.

### Colors

The picker colors the label and the URL differently so the list reads by label.
Override with raw SGR parameters, or turn it off:

```sh
CCLINKS_LABEL_COLOR=35 cclinks   # magenta labels (default: 36, cyan)
CCLINKS_URL_COLOR=32 cclinks     # green URLs     (default: 90, grey)
cclinks --no-color
```

`--print` is always plain, so it stays usable in a pipe.

### Which session does it read?

By default it looks for the session belonging to the current working directory, and falls
back to the most recently updated session if there is none. `--latest` skips the lookup
entirely — use it when launching from a hotkey, where the working directory is arbitrary.

Both can land on the wrong session once you keep more than one open. A picker started from
a hotkey is a *sibling* of Claude Code, not a child, so `CLAUDE_CODE_SESSION_ID` never
reaches it, and several sessions routinely share a working directory. Modification time is
a poor tiebreak too: a tab working through a long task writes continuously, so it wins on
mtime while you are reading a different one.

`--active` uses the session you last typed into, which is a much closer match for the tab
in front of you. The session has to announce itself, which is what the hook below does.

#### The hook

`contrib/user-prompt-submit-hook.sh` records the session on every prompt you submit. It
needs [jq](https://jqlang.github.io/jq/). Copy it somewhere, `chmod +x` it, then add this
to `~/.claude/settings.json`:

```jsonc
"hooks": {
  "UserPromptSubmit": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "bash /path/to/user-prompt-submit-hook.sh",
          "timeout": 5
        }
      ]
    }
  ]
}
```

It writes `~/.claude/cclinks-active.json` — the session id, its transcript path, and its
working directory. Not the prompt itself. Override the location with
`CCLINKS_ACTIVE_FILE`.

Without the hook, `--active` behaves exactly like `--latest`, so you can put it in a
keybinding first and set the hook up afterwards.

## Binding it to a key

Claude Code occupies the terminal, so the picker has to run somewhere else. Pick whichever
fits your setup.

The examples below use `--latest`, which needs no setup. Swap it for `--active` once the
hook is in place.

### tmux

Needs tmux 3.2 or newer for `display-popup`.

```tmux
bind-key u display-popup -E -w 80% -h 60% "cclinks --latest"
```

The popup does not source your shell rc, so it uses the PATH the tmux server
started with. If the popup flashes and vanishes, use an absolute path instead.

### Shell alias

```sh
alias ccl='cclinks'
```

### VS Code / Cursor task

Two files, both in the user directory rather than a workspace, so the key also works in a
window with no folder open.

First the task, in `~/Library/Application Support/Cursor/User/tasks.json` (for VS Code,
`Code` in place of `Cursor`).

```jsonc
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "cclinks",
      "type": "shell",
      "command": "${userHome}/.local/bin/cclinks --latest",
      "options": {
        "env": { "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${env:PATH}" }
      },
      "presentation": {
        "echo": false, "reveal": "always", "focus": true,
        "panel": "dedicated", "close": true, "clear": true, "showReuseMessage": false
      },
      "problemMatcher": []
    }
  ]
}
```

The task shell does not inherit your interactive `PATH`, which is why the command and the
`PATH` entry are spelled out.

Then the key, in `keybindings.json` beside it:

```jsonc
{
  "key": "alt+cmd+q",
  "command": "workbench.action.tasks.runTask",
  "args": "cclinks",
  "when": "terminalFocus"
}
```

`terminalFocus` keeps the binding to the terminal, so the key stays free while you are
editing. Drop it to reach the picker from anywhere in the window.

### Raycast

Drop a script command in your Raycast script directory and give it a hotkey:

```sh
#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title cclinks
# @raycast.mode silent
open -a Terminal "$HOME/.local/bin/cclinks --latest"
```

## Development

```sh
uv sync
uv run pytest
```

## Limitations

- Only Claude Code transcripts (`~/.claude/projects/**/*.jsonl`) are supported.
- The transcript is written when a response completes, so a link is pickable only after
  Claude finishes speaking.
- `open` / `xdg-open` are used to launch the browser. Tested on macOS with tmux 3.6.

## License

MIT
