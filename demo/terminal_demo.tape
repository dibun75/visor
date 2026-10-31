# Reproducible terminal demo. Run from the repository root:
#   vhs demo/terminal_demo.tape
#
# Requires https://github.com/charmbracelet/vhs
# The shell wrapper in demo/vhs_bashrc executes the real CLI and sanitizes
# home paths, usernames, and the workspace hash. It does not invent results.
#
# A cold `visor index` of this repository can take longer than the 10–15s
# target. Index once before recording so the taped `visor index` refreshes
# an existing local index. Do not retype the output. The context line pipes
# through sed so the frame shows the first lines of the real result.

Output docs/assets/terminal-demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 800
Set Padding 16
Set Theme "Catppuccin Mocha"
Set TypingSpeed 10ms
Set Framerate 12

Hide
Type "source demo/vhs_bashrc"
Enter
Type "clear"
Enter
Show

Type "uv run visor doctor"
Enter
Sleep 2s

Type "uv run visor index"
Enter
Sleep 4s

Type "clear"
Enter

Type `uv run visor context "resolve local workspace project root" | sed -n '1,42p'`
Enter
Sleep 5s
