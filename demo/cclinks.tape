# Records docs/demo.gif.
#
#   brew install vhs
#   vhs demo/cclinks.tape
#
# Run it from the repository root, with cclinks already on PATH.

Output docs/demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1100
Set Height 620
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 60ms
Set PlaybackSpeed 1.0

Hide
Type "clear" Enter
Show

Type "demo/demo.sh"
Sleep 400ms
Enter

# The reply lands: five links, and not one URL among them.
Sleep 2.5s

# The picker has them all, labels and URLs both.
Sleep 2s

# Narrow by label, the way you would remember it.
Type "ruff"
Sleep 2s

Backspace 4
Sleep 700ms

Type "docs"
Sleep 2s

# Enter would open the highlighted one in the browser.
Sleep 1s
Escape
Sleep 800ms
