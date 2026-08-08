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

## Why not just scrape the screen?

|                          | Screen scraping | cclinks |
| ------------------------ | --------------- | ------------ |
| Bare URLs                | Yes             | Yes          |
| Markdown links           | **No**          | Yes          |
| Scrolled out of view     | **No**          | Yes          |
| Label available for search | No            | Yes          |

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

## Binding it to a key

Claude Code occupies the terminal, so the picker has to run somewhere else. Pick whichever
fits your setup.

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

Put this in `~/Library/Application Support/Cursor/User/tasks.json` (or the `Code` equivalent),
then bind a key to `workbench.action.tasks.runTask` with `args: "cclinks"`.

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
