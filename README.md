# palettui

A terminal palette studio for people building TUI apps.

It shows the colors your terminal actually has, separates those from the semantic roles a TUI needs (canvas, text, accent, status), grades contrast, and exports the palette to Ghostty, Kitty, Alacritty, Windows Terminal, CSS, JSON, and Python.

No dependencies. Python 3.9+.

## Install

```bash
pip install palettui
palettui
```

Or from a checkout:

```bash
python3 -m palettui
```

## What you are looking at

A TUI has two color systems that must not be confused.

**Terminal slots (ANSI 0–15)** belong to the user. `ls`, git, and logs ask for "red", and the terminal theme decides the RGB. The ANSI 16 screen paints those live slots, so you see *your* theme, not a screenshot of someone else's.

**Semantic roles** belong to the app. Background, surface, text, accent, selection, success, warning, error. Design these in truecolor. If you paint a sidebar with ANSI blue, it will fight every theme that is not yours.

The 256-color cube and the truecolor ramp are there so you can tell which path the terminal will actually honor.

## Screens

| Key | Screen | Use it for |
| --- | --- | --- |
| 1 | Studio | A fake file pane, so roles are judged in a layout, not as chips |
| 2 | ANSI 16 | Live terminal colors next to the hex you plan to export |
| 3 | 256 | Indexed color, including the gray ramp |
| 4 | Truecolor | Smooth ramp vs banding |
| 5 | Library | Nord, Catppuccin Mocha, Tokyo Night, Dracula, Gruvbox, Solarized, Garden Dusk |
| 6 | Editor | Change a role. Editing a preset forks it |
| 7 | Contrast | WCAG grades for the pairs a TUI actually draws |
| 8 | Export | Ghostty, Kitty, Alacritty, Windows Terminal, CSS, JSON, Python |
| 9 | Guide | The short version of how to pick colors on purpose |

## Keys

```
1-9 or h/l    switch screen
[ ]           previous / next palette
j/k           move (role, page, or export format)
e             edit the selected hex
n             fork the current palette
d             delete a custom palette
y             copy the selected hex (OSC 52)
w             write the export into ./palettui-export/
?             guide
q             quit
```

Custom palettes are stored in `~/.config/palettui/palettes.json` (or `$PALETTUI_HOME`).

## Roles worth naming

- `background` canvas. Near-black, not `#000`.
- `mantle` the layer behind the canvas.
- `surface` / `surface_alt` panels and wells.
- `border` / `border_focus` idle chrome and the focus ring.
- `text` / `text_muted` / `text_dim` three type levels.
- `accent` / `accent_text` one brand color and the label on it.
- `selection` vs `match` row highlight and search hit are different jobs.
- `success` / `warning` / `error` / `info` status is not decoration.
- `ansi_*` the 16 slots shell tools will use on this theme.

Body text on the canvas should clear 7:1 if you can. 4.5:1 is the floor. Accent text on the accent fill gets its own check.

## Export

From the Export screen, `w` writes `./palettui-export/<palette>.<format>.<ext>`.

Presets are starting points, not canon. Catppuccin, Nord, Tokyo Night, Dracula, Gruvbox, and Solarized are other people's work; the hex here is for designing against, and the license of this tool does not relicense those themes.

## License

MIT.
