"""palettui application: palette studio, live terminal colors, export."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from palettui.palettes import ANSI_ROLES, PRESETS, ROLE_HELP, ROLE_LABEL, ROLES

SCREENS = [
    ("studio", "Studio"),
    ("ansi", "ANSI 16"),
    ("cube", "256"),
    ("true", "Truecolor"),
    ("library", "Library"),
    ("editor", "Editor"),
    ("contrast", "Contrast"),
    ("export", "Export"),
    ("guide", "Guide"),
]

EXPORTS = ["json", "ghostty", "alacritty", "kitty", "windows-terminal", "css", "python"]

GUIDE = [
    (
        "Why this exists",
        [
            "TUI apps fail in two predictable ways: unreadable text, and chrome that",
            "clashes with the user's terminal theme. palettui is the bench for both.",
            "",
            "Design the semantic roles first (canvas, text, accent, status). Then check",
            "them against the 16 ANSI colors the user's shell already owns. A theme that",
            "looks perfect in your editor can still make `ls` or a log pane unreadable.",
        ],
    ),
    (
        "Three color systems",
        [
            "ANSI 16  — indexes 0–15. The terminal theme decides the actual RGB.",
            "           'red' is not a color. It is a slot. Never paint app chrome with",
            "           these if you need a specific hue.",
            "ANSI 256 — indexes 16–231 are a 6x6x6 cube, 232–255 a gray ramp. Stable",
            "           across themes. Good fallback when truecolor is missing.",
            "Truecolor — 24-bit RGB. Use this for your designed palette. Probe it on",
            "           the Truecolor screen; if the ramp bands, you are being quantized.",
        ],
    ),
    (
        "Semantic roles",
        [
            "background / mantle / surface / surface_alt — four depths, not forty.",
            "text / text_muted / text_dim — three type levels. Dim must still be readable.",
            "accent + accent_text — one brand color and the label that sits on it.",
            "border vs border_focus — idle chrome quiet, focus unmistakable.",
            "selection vs match — row highlight and search hit are different jobs.",
            "success / warning / error / info — status is not decoration. Do not reuse",
            "the accent for error, or every failure looks like a primary button.",
        ],
    ),
    (
        "Contrast, not vibe",
        [
            "WCAG contrast is (Lighter + 0.05) / (darker + 0.05).",
            "Body text on canvas: aim for 7:1 (AAA). 4.5:1 is the floor (AA).",
            "Large UI labels and buttons can live at 3:1. Hints should still clear 3:1.",
            "Accent fills need their own check: accent_text on accent.",
            "Pure #000 and #fff look sharp in a screenshot and harsh for an hour.",
            "The Contrast screen grades the pairs that actually show up in a TUI.",
        ],
    ),
    (
        "ANSI is borrowed",
        [
            "Indexes 0–15 belong to the terminal. Ghostty, Kitty, iTerm, Windows",
            "Terminal, and the user's theme file all overwrite them.",
            "Map your ANSI slots so shell output still makes sense on your canvas:",
            "red stays a red, yellow stays a yellow, bright black stays a comment gray.",
            "If a TUI paints 'error' with ANSI red, it will follow the user. If it paints",
            "a sidebar with ANSI blue, it will fight every theme that is not yours.",
        ],
    ),
    (
        "A recipe",
        [
            "1. Pick a canvas that is not pure black. Note its temperature (warm/cool).",
            "2. Pick body text one family away from pure white. Check 7:1.",
            "3. Lift surface ~8–12% from the canvas. Border a step above that.",
            "4. Choose one accent. Check accent_text on accent at >= 4.5:1.",
            "5. Derive status from the accent's temperature so they coexist.",
            "6. Build the 16 ANSI colors in the same family, then open the ANSI 16",
            "   screen — that page uses the terminal's real slots, not your hex.",
            "7. Export. Wire the hex into the app. Leave ANSI slots to the terminal.",
        ],
    ),
]


def config_dir() -> Path:
    override = os.environ.get("PALETTUI_HOME")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "palettui"


def rel_luminance(hex_color: str) -> float:
    r, g, b = hex_to_rgb(hex_color)

    def channel(c: int) -> float:
        v = c / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(a: str, b: str) -> float:
    l1, l2 = rel_luminance(a), rel_luminance(b)
    light, dark = max(l1, l2), min(l1, l2)
    return (light + 0.05) / (dark + 0.05)


def grade(ratio: float, large: bool = False) -> str:
    if large:
        if ratio >= 4.5:
            return "AAA"
        if ratio >= 3.0:
            return "AA"
        return "fail"
    if ratio >= 7.0:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if ratio >= 3.0:
        return "AA large"
    return "fail"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
        raise ValueError(f"not a hex color: {value}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def normalize_hex(value: str) -> str:
    r, g, b = hex_to_rgb(value)
    return f"#{r:02x}{g:02x}{b:02x}"


def fg(hex_color: str) -> str:
    r, g, b = hex_to_rgb(hex_color)
    return f"\033[38;2;{r};{g};{b}m"


def bg(hex_color: str) -> str:
    r, g, b = hex_to_rgb(hex_color)
    return f"\033[48;2;{r};{g};{b}m"


def ansi_fg(index: int) -> str:
    if index < 8:
        return f"\033[{30 + index}m"
    return f"\033[{82 + index}m"


def ansi_bg(index: int) -> str:
    if index < 8:
        return f"\033[{40 + index}m"
    return f"\033[{92 + index}m"


def sgr_256(index: int, background: bool) -> str:
    return f"\033[{48 if background else 38};5;{index}m"


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
INVERT = "\033[7m"


def swatch(hex_color: str, width: int = 2) -> str:
    return bg(hex_color) + (" " * width) + RESET


def paint(text: str, color: str | None = None, fill: str | None = None, bold: bool = False) -> str:
    parts = []
    if bold:
        parts.append(BOLD)
    if color:
        parts.append(fg(color))
    if fill:
        parts.append(bg(fill))
    parts.append(text)
    parts.append(RESET)
    return "".join(parts)


def visible_len(text: str) -> int:
    length = 0
    i = 0
    while i < len(text):
        if text[i] == "\033":
            i += 1
            while i < len(text) and text[i] != "m":
                i += 1
            i += 1
            continue
        length += 1
        i += 1
    return length


def clip(text: str, width: int) -> str:
    if visible_len(text) <= width:
        return text
    out = []
    length = 0
    i = 0
    while i < len(text) and length < width - 1:
        if text[i] == "\033":
            j = i + 1
            while j < len(text) and text[j] != "m":
                j += 1
            out.append(text[i : j + 1])
            i = j + 1
            continue
        out.append(text[i])
        length += 1
        i += 1
    out.append("…")
    out.append(RESET)
    return "".join(out)


def pad(text: str, width: int) -> str:
    gap = width - visible_len(text)
    if gap <= 0:
        return clip(text, width)
    return text + (" " * gap)


class App:
    def __init__(self) -> None:
        self.screen = 0
        self.preset_names = list(PRESETS)
        self.custom: dict[str, dict] = {}
        self.palette_name = self.preset_names[0]
        self.role_index = 0
        self.guide_page = 0
        self.export_index = 0
        self.cube_page = 0
        self.status = "1-9 screens  ·  [ ] palette  ·  j/k role  ·  e edit  ·  y copy hex  ·  q quit"
        self.editing = False
        self.edit_buf = ""
        self.running = True
        self.load()

    @property
    def names(self) -> list[str]:
        return self.preset_names + list(self.custom)

    def palette(self) -> dict:
        if self.palette_name in PRESETS:
            return PRESETS[self.palette_name]
        return self.custom[self.palette_name]

    def roles(self) -> dict[str, str]:
        return self.palette()["roles"]

    def role_name(self) -> str:
        return ROLES[self.role_index][0]

    def load(self) -> None:
        path = config_dir() / "palettes.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            self.status = "could not read saved palettes"
            return
        self.custom = data.get("custom", {})
        current = data.get("current")
        if current in self.names:
            self.palette_name = current

    def save(self) -> None:
        path = config_dir() / "palettes.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"current": self.palette_name, "custom": self.custom}
        path.write_text(json.dumps(payload, indent=2) + "\n")
        self.status = f"saved {path}"

    def duplicate(self) -> None:
        base = self.palette()
        n = 1
        while f"Custom {n}" in self.names:
            n += 1
        name = f"Custom {n}"
        self.custom[name] = {
            "author": "you",
            "note": f"Forked from {self.palette_name}.",
            "roles": dict(base["roles"]),
        }
        self.palette_name = name
        self.screen = SCREENS.index(("editor", "Editor"))
        self.status = f"editing {name} — e to change the selected hex"
        self.save()

    def delete_custom(self) -> None:
        if self.palette_name not in self.custom:
            self.status = "presets are read-only — n to fork one"
            return
        del self.custom[self.palette_name]
        self.palette_name = self.preset_names[0]
        self.save()
        self.status = "deleted custom palette"

    def commit_edit(self) -> None:
        try:
            value = normalize_hex(self.edit_buf)
        except ValueError:
            self.status = "need 3 or 6 hex digits"
            return
        name = self.palette_name
        if name in PRESETS:
            self.duplicate()
            name = self.palette_name
        self.custom[name]["roles"][self.role_name()] = value
        self.editing = False
        self.edit_buf = ""
        self.save()
        self.status = f"{self.role_name()} = {value}"

    def copy_hex(self) -> None:
        value = self.roles()[self.role_name()]
        payload = _b64(value.encode())
        sys.stdout.write(f"\033]52;c;{payload}\007")
        sys.stdout.flush()
        self.status = f"copied {self.role_name()} {value} (OSC 52)"

    def cycle_palette(self, step: int) -> None:
        names = self.names
        idx = names.index(self.palette_name)
        self.palette_name = names[(idx + step) % len(names)]
        self.status = self.palette_name

    def handle(self, key: str) -> None:
        if self.editing:
            self.handle_edit(key)
            return
        if key in ("q", "\x03"):
            self.running = False
            return
        if key in ("?",):
            self.screen = SCREENS.index(("guide", "Guide"))
            return
        if key.isdigit() and key != "0":
            idx = int(key) - 1
            if idx < len(SCREENS):
                self.screen = idx
            return
        if key in ("left", "h"):
            self.screen = (self.screen - 1) % len(SCREENS)
            return
        if key in ("right", "l", "\t"):
            self.screen = (self.screen + 1) % len(SCREENS)
            return
        if key == "[":
            self.cycle_palette(-1)
            return
        if key == "]":
            self.cycle_palette(1)
            return
        if key == "n":
            self.duplicate()
            return
        if key == "d":
            self.delete_custom()
            return
        if key == "y":
            self.copy_hex()
            return
        if key == "w":
            self.write_export()
            return
        screen_id = SCREENS[self.screen][0]
        if screen_id == "guide":
            if key in ("down", "j", " "):
                self.guide_page = (self.guide_page + 1) % len(GUIDE)
            elif key in ("up", "k"):
                self.guide_page = (self.guide_page - 1) % len(GUIDE)
            return
        if screen_id == "cube":
            if key in ("down", "j"):
                self.cube_page = min(self.cube_page + 1, 2)
            elif key in ("up", "k"):
                self.cube_page = max(self.cube_page - 1, 0)
            return
        if screen_id == "export":
            if key in ("down", "j"):
                self.export_index = (self.export_index + 1) % len(EXPORTS)
            elif key in ("up", "k"):
                self.export_index = (self.export_index - 1) % len(EXPORTS)
            elif key in ("enter", "e"):
                self.write_export()
            return
        if key in ("down", "j"):
            self.role_index = (self.role_index + 1) % len(ROLES)
        elif key in ("up", "k"):
            self.role_index = (self.role_index - 1) % len(ROLES)
        elif key in ("e", "enter"):
            self.editing = True
            self.edit_buf = self.roles()[self.role_name()].lstrip("#")
            self.status = "hex edit — enter to commit, esc to cancel"

    def handle_edit(self, key: str) -> None:
        if key in ("esc", "\x03"):
            self.editing = False
            self.edit_buf = ""
            self.status = "edit cancelled"
            return
        if key == "enter":
            self.commit_edit()
            return
        if key in ("backspace", "\x7f"):
            self.edit_buf = self.edit_buf[:-1]
            return
        if len(key) == 1 and key in "0123456789abcdefABCDEF" and len(self.edit_buf) < 6:
            self.edit_buf += key.lower()

    def write_export(self) -> None:
        fmt = EXPORTS[self.export_index]
        text = render_export(self.palette_name, self.palette(), fmt)
        folder = Path.cwd() / "palettui-export"
        folder.mkdir(exist_ok=True)
        ext = {"json": "json", "css": "css", "python": "py", "alacritty": "yml"}.get(fmt, "txt")
        slug = self.palette_name.lower().replace(" ", "-")
        path = folder / f"{slug}.{fmt}.{ext}"
        path.write_text(text)
        self.status = f"wrote {path}"

    def render(self, width: int, height: int) -> str:
        roles = self.roles()
        canvas = roles["background"]
        text = roles["text"]
        muted = roles["text_muted"]
        accent = roles["accent"]
        lines: list[str] = []

        title = paint(" palettui ", accent, roles["accent_text"], bold=True)
        subtitle = paint(" palette studio for TUI authors", muted, canvas)
        lines.append(pad(title + " " + subtitle, width))

        tabs = []
        for i, (_sid, label) in enumerate(SCREENS):
            mark = f" {i + 1} {label} "
            if i == self.screen:
                tabs.append(paint(mark, roles["accent_text"], accent, bold=True))
            else:
                tabs.append(paint(mark, muted, canvas))
        lines.append(pad("".join(tabs), width))

        meta = self.palette()
        ratio = contrast_ratio(roles["text"], roles["background"])
        header = (
            paint(f" {self.palette_name} ", text, canvas, bold=True)
            + paint(f"  {meta.get('author', '')}  ", muted, canvas)
            + paint(f"text/bg {ratio:.1f}:1 {grade(ratio)}", text, canvas)
        )
        lines.append(pad(header, width))
        lines.append(pad(paint(" " + meta.get("note", ""), muted, canvas), width))
        lines.append(paint("─" * width, roles["border"], canvas))

        body_height = max(1, height - 8)
        screen_id = SCREENS[self.screen][0]
        body = {
            "studio": self.view_studio,
            "ansi": self.view_ansi,
            "cube": self.view_cube,
            "true": self.view_true,
            "library": self.view_library,
            "editor": self.view_editor,
            "contrast": self.view_contrast,
            "export": self.view_export,
            "guide": self.view_guide,
        }[screen_id](width, body_height)
        lines.extend(body[:body_height])
        while len(lines) < height - 2:
            lines.append(paint(" " * width, text, canvas))

        if self.editing:
            prompt = paint(
                f" {self.role_name()} = #{self.edit_buf}{'▏'}",
                roles["accent_text"],
                accent,
            )
            lines.append(pad(prompt, width))
        else:
            lines.append(pad(paint(" " + self.status, muted, roles["mantle"]), width))
        help_line = " [ ] palette   j/k move   e edit   n fork   d delete custom   y copy   w write export   ? guide   q quit "
        lines.append(pad(paint(help_line, roles["text_dim"], roles["mantle"]), width))
        return "\n".join(lines[:height])

    def view_studio(self, width: int, height: int) -> list[str]:
        roles = self.roles()
        left_w = max(36, min(54, width // 2))
        right_w = width - left_w
        demo = self.demo_lines(left_w, height)
        side = self.role_lines(right_w, height)
        out = []
        for i in range(height):
            left = demo[i] if i < len(demo) else paint(" " * left_w, roles["text"], roles["background"])
            right = side[i] if i < len(side) else ""
            out.append(pad(left, left_w) + pad(right, right_w))
        return out

    def demo_lines(self, width: int, height: int) -> list[str]:
        r = self.roles()
        inner = width - 2
        lines = [
            paint("┌" + "─" * (width - 2) + "┐", r["border"], r["background"]),
            self.box_row(" Files", r["text"], r["surface"], r["border"], width, bold=True),
            self.box_row("▸ app.py", r["accent_text"], r["selection"], r["border"], width),
            self.box_row("  theme.py", r["text_muted"], r["surface"], r["border"], width),
            self.box_row("  export.py", r["text_dim"], r["surface"], r["border"], width),
            self.box_row("", r["text"], r["surface"], r["border"], width),
            self.box_row(" primary text sits here", r["text"], r["background"], r["border"], width),
            self.box_row(" muted hint · unsaved", r["text_muted"], r["background"], r["border"], width),
            self.box_row(" dim timestamp 12:04", r["text_dim"], r["background"], r["border"], width),
            self.box_row(" search " + "match", r["background"], r["match"], r["border"], width),
        ]
        button = paint(" Save ", r["accent_text"], r["accent"], bold=True)
        ghost = paint(" Quit ", r["text"], r["surface_alt"])
        action = " " + button + " " + ghost
        lines.append(self.box_row(action, r["text"], r["background"], r["border"], width, raw=True))
        status = (
            paint(" ok ", r["background"], r["success"])
            + " "
            + paint(" warn ", r["background"], r["warning"])
            + " "
            + paint(" err ", r["background"], r["error"])
            + " "
            + paint(" info ", r["background"], r["info"])
        )
        lines.append(self.box_row(status, r["text"], r["background"], r["border"], width, raw=True))
        lines.append(paint("└" + "─" * (width - 2) + "┘", r["border_focus"], r["background"]))
        lines.append(paint(" focus ring uses border_focus", r["text_dim"], r["background"]))
        del inner
        return lines[:height]

    def box_row(
        self,
        content: str,
        color: str,
        fill: str,
        border: str,
        width: int,
        bold: bool = False,
        raw: bool = False,
    ) -> str:
        inner = width - 2
        if raw:
            body = clip(content, inner)
            gap = inner - visible_len(body)
            body = body + paint(" " * max(gap, 0), color, fill)
        else:
            body = paint(pad(clip(content, inner), inner), color, fill, bold=bold)
        return paint("│", border, self.roles()["background"]) + body + paint("│", border, self.roles()["background"])

    def role_lines(self, width: int, height: int) -> list[str]:
        roles = self.roles()
        start = max(0, self.role_index - 2)
        window = ROLES[start : start + height]
        out = []
        for name, label, _help in window:
            selected = name == self.role_name()
            mark = "▸" if selected else " "
            color = roles["text"] if selected else roles["text_muted"]
            fill = roles["surface"] if selected else roles["background"]
            chip = swatch(roles[name])
            line = paint(f"{mark} {label:<12} {roles[name]} ", color, fill) + chip
            out.append(clip(line, width))
        return out

    def view_ansi(self, width: int, height: int) -> list[str]:
        roles = self.roles()
        lines = [
            paint(" Live terminal slots. These are your theme, not the palette hex.", roles["text"], roles["background"]),
            paint(" If a row clashes with the canvas, ANSI-only tools will clash too.", roles["text_muted"], roles["background"]),
            "",
        ]
        names = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
        for base, title in ((0, "normal 0–7"), (8, "bright 8–15")):
            bits = [paint(f"{title:<12}", roles["text_muted"], roles["background"])]
            for i, name in enumerate(names):
                idx = base + i
                chip = ansi_bg(idx) + "    " + RESET
                label = ansi_fg(idx) + BOLD + f"{idx:<3}" + RESET
                bits.append(chip + label + " ")
            lines.append("".join(bits))
        lines.append("")
        lines.append(paint(" Designed hex for the same slots (what export will write):", roles["text_muted"], roles["background"]))
        row = []
        for i, name in enumerate(ANSI_ROLES):
            row.append(swatch(roles[name], 2) + paint(f"{i:<3}", roles["text_dim"], roles["background"]))
            if i == 7:
                lines.append("".join(row))
                row = []
        lines.append("".join(row))
        lines.append("")
        selected = self.role_name()
        lines.append(paint(ROLE_HELP.get(selected, ""), roles["text"], roles["background"]))
        return [pad(line, width) for line in lines[:height]]

    def view_cube(self, width: int, height: int) -> list[str]:
        roles = self.roles()
        lines = [
            paint(" 256-color indexes. 0–15 follow the theme; 16–255 are stable.", roles["text"], roles["background"]),
            paint(f" page {self.cube_page + 1}/3   j/k to page", roles["text_muted"], roles["background"]),
        ]
        if self.cube_page == 0:
            lines.append(paint(" 0–15 terminal palette", roles["text_dim"], roles["background"]))
            row = []
            for i in range(16):
                row.append(sgr_256(i, True) + f"{i:02d}" + RESET + " ")
            lines.append("".join(row))
            lines.append(paint(" 16–231 color cube (first rows)", roles["text_dim"], roles["background"]))
            start = 16
        elif self.cube_page == 1:
            start = 16 + 6 * 12
            lines.append(paint(" cube continued", roles["text_dim"], roles["background"]))
        else:
            start = 16 + 6 * 24
            lines.append(paint(" cube tail + gray ramp 232–255", roles["text_dim"], roles["background"]))
        col = 0
        row = []
        end = 232 if self.cube_page < 2 else 256
        begin = start if self.cube_page < 2 else 232
        if self.cube_page < 2:
            begin = start
            end = min(232, start + 6 * 12)
        for i in range(begin, end):
            row.append(sgr_256(i, True) + "  " + RESET)
            col += 1
            if col == 12 or (i >= 232 and col == 12):
                lines.append("".join(row))
                row = []
                col = 0
        if row:
            lines.append("".join(row))
        if self.cube_page == 2:
            ramp = [sgr_256(i, True) + "  " + RESET for i in range(232, 256)]
            lines.append("".join(ramp))
        return [pad(line, width) for line in lines[:height]]

    def view_true(self, width: int, height: int) -> list[str]:
        roles = self.roles()
        lines = [
            paint(" Truecolor probe. A smooth ramp means 24-bit is getting through.", roles["text"], roles["background"]),
            paint(" Banding means the terminal is quantizing to 256 or 16.", roles["text_muted"], roles["background"]),
            "",
        ]
        ramp_w = max(8, width - 4)
        hue = []
        for i in range(ramp_w):
            t = i / max(ramp_w - 1, 1)
            r = int(255 * abs((t * 6) % 2 - 1))
            g = int(255 * (1 - abs((t * 6 - 2) % 2 - 1))) if False else int(180 * t)
            # simple warm-to-cool ramp plus a gray ramp
            rr = int(255 * (1 - t))
            gg = int(80 + 140 * t)
            bb = int(40 + 200 * t)
            hue.append(f"\033[48;2;{rr};{gg};{bb}m " + RESET)
        lines.append("".join(hue))
        gray = []
        for i in range(ramp_w):
            v = int(255 * i / max(ramp_w - 1, 1))
            gray.append(f"\033[48;2;{v};{v};{v}m " + RESET)
        lines.append("".join(gray))
        lines.append("")
        lines.append(paint(" Palette ramp (mantle → text)", roles["text_dim"], roles["background"]))
        keys = ["mantle", "background", "surface", "surface_alt", "border", "text_dim", "text_muted", "text"]
        lines.append("".join(swatch(roles[k], 4) for k in keys))
        lines.append("".join(paint(f"{k[:4]:<4}", roles["text_dim"], roles["background"]) for k in keys))
        return [pad(line, width) for line in lines[:height]]

    def view_library(self, width: int, height: int) -> list[str]:
        roles = self.roles()
        lines = []
        for name in self.names:
            data = PRESETS.get(name) or self.custom[name]
            selected = name == self.palette_name
            mark = "▸" if selected else " "
            kind = "preset" if name in PRESETS else "custom"
            chips = "".join(swatch(data["roles"][k], 2) for k in ("background", "surface", "accent", "text", "error", "success"))
            label = paint(f"{mark} {name:<18} {kind:<7}", roles["text"] if selected else roles["text_muted"], roles["surface"] if selected else roles["background"])
            lines.append(pad(label + " " + chips, width))
        lines.append("")
        lines.append(paint(" [ ] to switch. n forks the current palette into a custom one.", roles["text_dim"], roles["background"]))
        return lines[:height]

    def view_editor(self, width: int, height: int) -> list[str]:
        roles = self.roles()
        lines = [
            paint(" e edits the selected role. Presets fork themselves on the first edit.", roles["text_muted"], roles["background"])
        ]
        start = max(0, min(self.role_index - 2, len(ROLES) - max(height - 2, 1)))
        for name, label, _help in ROLES[start : start + height - 2]:
            selected = name == self.role_name()
            mark = "▸" if selected else " "
            fill = roles["surface"] if selected else roles["background"]
            color = roles["text"] if selected else roles["text_muted"]
            line = paint(f"{mark} {label:<14} {name:<18} {roles[name]}  ", color, fill) + swatch(roles[name], 4)
            lines.append(clip(line, width))
        if len(lines) < height:
            lines.append(paint(" " + ROLE_HELP[self.role_name()], roles["text_dim"], roles["background"]))
        return [pad(line, width) for line in lines[:height]]

    def view_contrast(self, width: int, height: int) -> list[str]:
        roles = self.roles()
        pairs = [
            ("text", "background", False),
            ("text_muted", "background", False),
            ("text_dim", "background", True),
            ("text", "surface", False),
            ("text_muted", "surface", False),
            ("accent_text", "accent", False),
            ("text", "selection", False),
            ("background", "match", False),
            ("text", "error", True),
            ("text", "warning", True),
            ("text", "success", True),
            ("text", "info", True),
            ("border_focus", "background", True),
        ]
        lines = [paint(" Pair                          ratio   grade", roles["text_dim"], roles["background"])]
        for fg_name, bg_name, large in pairs:
            ratio = contrast_ratio(roles[fg_name], roles[bg_name])
            g = grade(ratio, large)
            sample = paint(f" {fg_name} on {bg_name} ", roles[fg_name], roles[bg_name])
            flag = roles["success"] if g != "fail" else roles["error"]
            line = pad(sample, 34) + paint(f" {ratio:5.1f}:1  {g}", flag, roles["background"])
            lines.append(clip(line, width))
        return lines[:height]

    def view_export(self, width: int, height: int) -> list[str]:
        roles = self.roles()
        lines = [paint(" w writes the selected format into ./palettui-export/", roles["text_muted"], roles["background"])]
        for i, fmt in enumerate(EXPORTS):
            selected = i == self.export_index
            mark = "▸" if selected else " "
            lines.append(
                paint(
                    f"{mark} {fmt}",
                    roles["accent_text"] if selected else roles["text"],
                    roles["accent"] if selected else roles["background"],
                )
            )
        lines.append("")
        preview = render_export(self.palette_name, self.palette(), EXPORTS[self.export_index]).splitlines()
        for line in preview[: max(0, height - len(lines))]:
            lines.append(paint(line, roles["text"], roles["surface_alt"]))
        return [pad(line, width) for line in lines[:height]]

    def view_guide(self, width: int, height: int) -> list[str]:
        roles = self.roles()
        title, paragraphs = GUIDE[self.guide_page]
        lines = [
            paint(f" {self.guide_page + 1}/{len(GUIDE)}  {title}", roles["accent"], roles["background"], bold=True),
            "",
        ]
        for paragraph in paragraphs:
            lines.append(paint(paragraph, roles["text"], roles["background"]))
        lines.append("")
        lines.append(paint(" j/k pages", roles["text_dim"], roles["background"]))
        return [pad(line, width) for line in lines[:height]]


def render_export(name: str, palette: dict, fmt: str) -> str:
    roles = palette["roles"]
    ansi = [roles[key] for key in ANSI_ROLES]
    if fmt == "json":
        return json.dumps({"name": name, "author": palette.get("author", ""), "roles": roles}, indent=2) + "\n"
    if fmt == "ghostty":
        lines = [
            f"# {name}",
            f"background = {roles['background']}",
            f"foreground = {roles['text']}",
            f"cursor-color = {roles['cursor']}",
            f"selection-background = {roles['selection']}",
            f"selection-foreground = {roles['text']}",
        ]
        lines.extend(f"palette = {i}={ansi[i]}" for i in range(16))
        return "\n".join(lines) + "\n"
    if fmt == "kitty":
        lines = [
            f"# {name}",
            f"background {roles['background']}",
            f"foreground {roles['text']}",
            f"cursor {roles['cursor']}",
            f"selection_background {roles['selection']}",
            f"selection_foreground {roles['text']}",
        ]
        lines.extend(f"color{i} {ansi[i]}" for i in range(16))
        return "\n".join(lines) + "\n"
    if fmt == "alacritty":
        normal = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
        lines = [
            f"# {name}",
            "colors:",
            "  primary:",
            f"    background: '{roles['background']}'",
            f"    foreground: '{roles['text']}'",
            "  cursor:",
            f"    cursor: '{roles['cursor']}'",
            "  selection:",
            f"    background: '{roles['selection']}'",
            f"    text: '{roles['text']}'",
            "  normal:",
        ]
        lines.extend(f"    {normal[i]}: '{ansi[i]}'" for i in range(8))
        lines.append("  bright:")
        lines.extend(f"    {normal[i]}: '{ansi[i + 8]}'" for i in range(8))
        return "\n".join(lines) + "\n"
    if fmt == "windows-terminal":
        keys = [
            "black", "red", "green", "yellow", "blue", "purple", "cyan", "white",
            "brightBlack", "brightRed", "brightGreen", "brightYellow",
            "brightBlue", "brightPurple", "brightCyan", "brightWhite",
        ]
        data = {
            "name": name,
            "background": roles["background"],
            "foreground": roles["text"],
            "cursorColor": roles["cursor"],
            "selectionBackground": roles["selection"],
        }
        data.update({keys[i]: ansi[i] for i in range(16)})
        return json.dumps(data, indent=2) + "\n"
    if fmt == "css":
        lines = [f"/* {name} */", ":root {"]
        lines.extend(f"  --{key.replace('_', '-')}: {value};" for key, value in roles.items())
        lines.append("}")
        return "\n".join(lines) + "\n"
    if fmt == "python":
        body = json.dumps(roles, indent=4)
        return f"# {name}\nPALETTE = {body}\n"
    raise ValueError(fmt)


def _b64(data: bytes) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    out = []
    for i in range(0, len(data), 3):
        chunk = data[i : i + 3]
        n = int.from_bytes(chunk.ljust(3, b"\0"), "big")
        out.append(alphabet[(n >> 18) & 63])
        out.append(alphabet[(n >> 12) & 63])
        out.append(alphabet[(n >> 6) & 63] if len(chunk) > 1 else "=")
        out.append(alphabet[n & 63] if len(chunk) > 2 else "=")
    return "".join(out)


def read_key(unix: bool) -> str:
    if not unix:
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            nxt = msvcrt.getwch()
            return {"H": "up", "P": "down", "K": "left", "M": "right"}.get(nxt, "")
        if ch == "\x1b":
            return "esc"
        if ch == "\r":
            return "enter"
        if ch == "\x08":
            return "backspace"
        return ch
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            rest = ""
            import select

            while select.select([sys.stdin], [], [], 0.02)[0]:
                rest += sys.stdin.read(1)
                if len(rest) > 4:
                    break
            mapping = {"[A": "up", "[B": "down", "[C": "right", "[D": "left"}
            return mapping.get(rest, "esc")
        if ch in ("\r", "\n"):
            return "enter"
        if ch in ("\x7f", "\x08"):
            return "backspace"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def run() -> int:
    if not sys.stdin.isatty():
        print("palettui needs a terminal. Run it directly, not in a pipe.", file=sys.stderr)
        return 1
    unix = os.name != "nt"
    app = App()
    sys.stdout.write("\033[?1049h\033[?25l")
    sys.stdout.flush()
    try:
        while app.running:
            size = shutil.get_terminal_size(fallback=(80, 24))
            width, height = max(size.columns, 60), max(size.lines, 16)
            frame = app.render(width, height)
            sys.stdout.write("\033[H" + frame + "\033[J")
            sys.stdout.flush()
            key = read_key(unix)
            if key:
                app.handle(key)
    finally:
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()
    return 0
