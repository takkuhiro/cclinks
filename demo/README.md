# Demo

`docs/demo.gif` is generated, not hand-recorded. To rebuild it:

```sh
brew install vhs      # or see https://github.com/charmbracelet/vhs
vhs demo/cclinks.tape
```

Run it from the repository root with `cclinks` on your PATH.

`demo.sh` prints a reply the way Claude Code prints one: Markdown links become
OSC 8 hyperlinks, so the label is on screen and the URL is nowhere in the
terminal buffer. That is the situation `cclinks` exists for, and the recording
shows it rather than describing it.

The fixture transcript in `session.jsonl` is copied into a throwaway `HOME`, so
recording never reads or touches your real sessions.
