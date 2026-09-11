from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import math
import os
from pathlib import Path
import random
import re
import select
import shutil
import sys
import time
import unicodedata
from typing import Callable, Sequence

from .terminal_input import read_input
from .terminal_ui import read_number, run_action, run_command, search_grades, search_students


_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_ACCENT = "\x1b[38;5;110m"
_DIM = "\x1b[38;5;245m"
_SELECTED = "\x1b[48;5;238m\x1b[38;5;255m"
_GOLD = "\x1b[38;5;180m"
_BAR = "\x1b[38;5;245m"
_SURFACE = "\x1b[48;5;235m\x1b[38;5;252m"
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _ansi(text: str, style: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR") is not None:
        return text
    return f"{style}{text}{_RESET}"


def _display_width(text: str) -> int:
    plain = _ANSI_RE.sub("", text)
    return sum(_cell_width(char) for char in plain)


def _cell_width(char: str) -> int:
    if unicodedata.combining(char) or unicodedata.category(char) in {"Cf", "Mn", "Me"}:
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def _pad_cells(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))



def _terminal_size() -> os.terminal_size:
    # Termux/proot can retain stale COLUMNS/LINES after pinch-to-zoom.
    # Prefer the live PTY dimensions over environment variables.
    try:
        return os.get_terminal_size(sys.stdout.fileno())
    except (OSError, ValueError, AttributeError):
        return shutil.get_terminal_size((80, 24))


def _clear() -> None:
    if os.name == "nt":
        os.system("cls")
    elif sys.stdout.isatty():
        print("\x1b[2J\x1b[H", end="", flush=True)
    else:
        print("\n" * 40)



@dataclass(frozen=True)
class MouseClick:
    x: int
    y: int


@dataclass(frozen=True)
class HitRegion:
    x: int
    y: int
    width: int
    action: str


@dataclass
class ScreenFrame:
    lines: list[str]
    regions: list[HitRegion]


def _mouse_event(sequence: bytes) -> str | MouseClick:
    match = re.fullmatch(rb"\[<(\d+);(\d+);(\d+)([Mm])", sequence)
    if match is None:
        return "other"
    button, x, y = (int(match[i]) for i in (1, 2, 3))
    if x < 1 or y < 1:
        return "other"
    # Activate on release, so a pending release sequence cannot leak into
    # the native text input opened by a click.
    if match[4] == b"m":
        return MouseClick(x, y) if button == 0 else "other"
    if button == 64:
        return "up"
    if button == 65:
        return "down"
    return "other"


@contextmanager
def _mouse_tracking():
    enabled = os.name != "nt" and sys.stdin.isatty() and sys.stdout.isatty()
    if enabled:
        sys.stdout.write("\x1b[?25l\x1b[?1000h\x1b[?1006h")
        sys.stdout.flush()
    try:
        yield
    finally:
        if enabled:
            sys.stdout.write("\x1b[?1000l\x1b[?1006l\x1b[?25h")
            sys.stdout.flush()


def _hit_action(click: MouseClick, regions: Sequence[HitRegion]) -> str | None:
    return next((region.action for region in regions
                 if click.y == region.y and region.x <= click.x < region.x + region.width), None)


def _footer(width: int, buttons: Sequence[tuple[str, str, str]], row: int) -> tuple[str, list[HitRegion]]:
    compact = sum(_display_width(button[0]) + 3 for button in buttons) > width
    text = ""
    regions = []
    for long, short, action in buttons:
        label = short if compact else long
        shown = f" {label} "
        if _display_width(text + shown) > width:
            continue
        regions.append(HitRegion(_display_width(text) + 1, row, _display_width(shown), action))
        text += shown + " "
    return _ansi(_pad_cells(_clip_cells(text, width), width), _BAR), regions


def _selection_frame(title: str, items: Sequence[str], selected: int, back_label: str) -> ScreenFrame:
    terminal = _terminal_size()
    width, height = max(1, terminal.columns - 1), max(3, terminal.lines)
    capacity = max(1, height - 5)
    first = min(max(0, selected - capacity + 1), max(0, len(items) - capacity))
    lines = [_ansi("✦ 星原 / 教务台", _BOLD + _ACCENT),
             _ansi(f"首页 / {title}", _DIM), _ansi("─" * width, _DIM)]
    regions = []
    panel_width = min(width, 38 if width >= 72 else width)
    for index in range(first, min(len(items), first + capacity)):
        text = _pad_cells(_clip_cells(f" {'›' if index == selected else ' '} {index + 1}  {items[index]}", panel_width), panel_width)
        regions.append(HitRegion(1, len(lines) + 1, panel_width, f"item:{index}"))
        lines.append(_ansi(text, _SELECTED) if index == selected else text)
    while len(lines) < height:
        lines.append("")
    if width >= 72 and height >= 10:
        details = [items[selected], "", "点击菜单项或按 Enter 打开。", "方向键 / 滚轮切换选项。", "q 返回上一级。"]
        for offset, detail in enumerate(details, start=3):
            if offset < height - 1:
                lines[offset] = _pad_cells(lines[offset], panel_width + 3) + _ansi(detail, _ACCENT if offset == 3 else _DIM)
    footer, controls = _footer(width, (("↑↓/滚轮 移动", "↑↓", "down"),
                                     ("Enter/点击 打开", "Enter", "select"),
                                     (f"q {back_label}", f"q{back_label}", "back")), height)
    lines[-1] = footer
    return ScreenFrame([_clip_cells(line, width) for line in lines], regions + controls)

def _read_key_windows(timeout: float | None = None) -> str | None:
    import msvcrt

    if timeout is not None:
        deadline = time.monotonic() + timeout
        while not msvcrt.kbhit():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            time.sleep(min(0.01, remaining))

    char = msvcrt.getwch()
    if char in {"\x00", "\xe0"}:
        code = msvcrt.getwch()
        if code == "H":
            return "up"
        if code == "P":
            return "down"
        if code == "G":
            return "home"
        if code == "O":
            return "end"
        return "other"
    return _plain_key(char)


def _plain_key(char: str) -> str:
    if char == "\x03":
        raise KeyboardInterrupt
    if not char or char == "\x04":
        raise EOFError
    if char in {" ", "\r", "\n"}:
        return "select"
    if char in {"\x1b", "\x08", "\x7f", "0"} or char.lower() == "q":
        return "back"
    if char.lower() == "k":
        return "up"
    if char.lower() == "j":
        return "down"
    if char.lower() == "p":
        return "pause"
    if char.lower() == "n":
        return "next"
    return char if char in "123456789" else "other"


def _read_escape_sequence(fd: int) -> bytes:
    """Read the bytes following ESC without going through TextIO buffering."""
    sequence = bytearray()
    while len(sequence) < 64:
        ready, _, _ = select.select([fd], [], [], 0.08)
        if not ready:
            break
        chunk = os.read(fd, 1)
        if not chunk:
            break
        sequence += chunk
        byte = chunk[0]
        if len(sequence) >= 2 and 0x40 <= byte <= 0x7E:
            break
    return bytes(sequence)


def _read_key_posix(timeout: float | None = None) -> str | MouseClick | None:
    import termios
    import tty

    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    try:
        # TCSAFLUSH (the default) discards keys typed while a frame is drawn.
        tty.setcbreak(fd, termios.TCSANOW)
        if timeout is not None:
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                return None
        char = os.read(fd, 1)
        if char == b"\x1b":
            sequence = _read_escape_sequence(fd)
            if sequence.startswith(b"[<"):
                return _mouse_event(sequence)
            if sequence in {b"[A", b"OA"} or (
                sequence.startswith(b"[") and sequence.endswith(b"A")
            ):
                return "up"
            if sequence in {b"[B", b"OB"} or (
                sequence.startswith(b"[") and sequence.endswith(b"B")
            ):
                return "down"
            if sequence == b"[5~":
                return "page_up"
            if sequence == b"[6~":
                return "page_down"
            if sequence in {b"[H", b"OH", b"[1~", b"[7~"}:
                return "home"
            if sequence in {b"[F", b"OF", b"[4~", b"[8~"}:
                return "end"
            return "other" if sequence else "back"
        return _plain_key(char.decode("ascii", errors="replace"))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def _read_key(timeout: float | None = None) -> str | MouseClick | None:
    if os.name == "nt":
        return _read_key_windows(timeout)
    return _read_key_posix(timeout)


def _select(
    title: str,
    items: Sequence[str],
    *,
    allow_back: bool = True,
    back_label: str = "返回",
    selected: int = 0,
) -> int | None:
    if not items:
        return None
    selected = min(max(0, selected), len(items) - 1)
    previous: list[str] = []
    with _mouse_tracking():
        while True:
            frame = _selection_frame(title, items, selected, back_label)
            if frame.lines != previous:
                _paint(frame.lines, previous)
                previous = frame.lines
            key = _read_key(0.15)
            if isinstance(key, MouseClick):
                key = _hit_action(key, frame.regions)
                if key and key.startswith("item:"):
                    return int(key.split(":")[1])
            if key == "up":
                selected = (selected - 1) % len(items)
            elif key == "down":
                selected = (selected + 1) % len(items)
            elif key == "select":
                return selected
            elif key == "home":
                selected = 0
            elif key == "end":
                selected = len(items) - 1
            elif key in tuple("123456789") and int(key) <= len(items):
                return int(key) - 1
            elif key == "back" and allow_back:
                return None


_MODULES = (
    ("学生档案", "查询每位学生的档案与成长记录。", "查询 / 搜索 / 新建 / 编辑"),
    ("教务结构", "从学院到班级，管理校园的组织。", "学院 / 专业 / 班级"),
    ("课程目录", "课程安排、学分与课时一目了然。", "课程详情 / 学分 / 课时"),
    ("选课与成绩", "记录选课，跟进每一次学习进展。", "选课 / 录入成绩 / 搜索"),
    ("数据工作台", "查看全校概况，导入或带走记录。", "统计 / CSV / 演示数据"),
    ("结束本次工作", "已完成的操作已保存。", "Enter 退出 / 上下键继续浏览"),
)


def _clip_cells(text: str, width: int) -> str:
    """Clip terminal cells without dropping or splitting SGR sequences."""
    if width <= 0:
        return ""
    if _display_width(text) <= width:
        return text
    result: list[str] = []
    used = 0
    for token in re.split(f"({_ANSI_RE.pattern})", text):
        if _ANSI_RE.fullmatch(token):
            result.append(token)
            continue
        for char in token:
            cells = _cell_width(char)
            if used + cells > width - 1:
                return "".join(result) + "…" + (_RESET if "\x1b" in text else "")
            result.append(char)
            used += cells
    return "".join(result)


def _orbit(width: int, height: int, angle: float, selected: int) -> list[str]:
    """Draw a rotating globe and tilted rings at 2×4 dots per terminal cell."""
    width, height = max(1, width), max(1, height)
    pixels_w, pixels_h = width * 2, height * 4
    radius = min(pixels_w / 4.8, pixels_h / 2.5)
    cx, cy = pixels_w / 2, pixels_h / 2
    dots = [[0] * width for _ in range(height)]
    colors = [[0] * width for _ in range(height)]
    bits = ((1, 8), (2, 16), (4, 32), (64, 128))

    def point(x: float, y: float, color: int) -> None:
        px, py = round(cx + x), round(cy + y)
        if 0 <= px < pixels_w and 0 <= py < pixels_h:
            dots[py // 4][px // 2] |= bits[py % 4][px % 2]
            colors[py // 4][px // 2] = max(colors[py // 4][px // 2], color)

    # Moving longitude lines and lit dots give the globe depth and rotation.
    for y in range(-math.ceil(radius), math.ceil(radius) + 1):
        for x in range(-math.ceil(radius), math.ceil(radius) + 1):
            nx, ny = x / radius, y / radius
            if nx * nx + ny * ny >= 1:
                continue
            nz = math.sqrt(1 - nx * nx - ny * ny)
            longitude = math.atan2(nx, nz) + angle * 0.55
            latitude = math.asin(ny)
            light = -0.4 * nx - 0.35 * ny + 0.7 * nz
            grid = abs(math.sin(longitude * 7)) < 0.14 or abs(math.sin(latitude * 7)) < 0.12
            if grid or (light > 0.6 and (x + y * 3) % 5 == 0):
                point(x, y, 1 if light < 0.45 else 2)

    for step in range(max(90, width * 4)):
        t = step * math.tau / max(90, width * 4)
        point(radius * math.cos(t), radius * math.sin(t), 2)

    # Two gold rings cross the globe; their far halves disappear behind it.
    tilt = -0.32 + math.sin(angle * 0.18) * 0.1
    def ring(t: float, scale: float) -> tuple[float, float]:
        x, y = radius * scale * math.cos(t), radius * 0.48 * math.sin(t)
        return x * math.cos(tilt) - y * math.sin(tilt), x * math.sin(tilt) + y * math.cos(tilt)

    for scale in (1.8, 2.12):
        for step in range(max(120, width * 10)):
            t = step * math.tau / max(120, width * 10)
            x, y = ring(t, scale)
            if math.sin(t) < 0 and x * x + y * y < radius * radius:
                continue
            point(x, y, 3)
    t = angle * 0.9 + selected * math.tau / 6
    x, y = ring(t, 2.12)
    for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
        point(x + dx, y + dy, 4)

    styles = ("", "\x1b[38;5;60m", _ACCENT, _GOLD, "\x1b[38;5;252m")
    lines = []
    for row in range(height):
        # Group adjacent equal colors, avoiding an escape sequence per dot.
        chunks: list[str] = []
        run, last_color = "", 0
        for col in range(width):
            color = colors[row][col]
            char = chr(0x2800 + dots[row][col]) if dots[row][col] else " "
            if color != last_color and run:
                chunks.append(_ansi(run, styles[last_color]) if last_color else run)
                run = ""
            run += char
            last_color = color
        if run:
            chunks.append(_ansi(run, styles[last_color]) if last_color else run)
        lines.append("".join(chunks))
    return lines


def _home_footer(width: int, height: int, animate: bool) -> tuple[str, list[HitRegion]]:
    motion = "暂停" if animate else "播放"
    return _footer(width, (("↑↓/滚轮 移动", "↑↓", "down"),
                           ("Enter/点击 打开", "Enter", "select"),
                           (f"p {motion}", f"p{motion}", "pause"),
                           ("q/0 退出", "q退出", "back")), height)


def _bottom_bar(width: int, animate: bool) -> str:
    return _home_footer(width, 1, animate)[0]


def _home_frame(
    labels: Sequence[str],
    selected: int,
    stats: dict[str, object],
    angle: float,
    *,
    animate: bool = True,
    database: str = "xingyuan.db",
) -> ScreenFrame:
    terminal = _terminal_size()
    width, height = max(1, terminal.columns - 1), max(3, terminal.lines)
    title, description, actions = _MODULES[selected]
    header = _ansi("✦ 星原 / 教务台", _BOLD + _ACCENT)
    database_label = _ansi(f"LOCAL / {database}", _DIM)
    if width >= 64:
        header = _pad_cells(header, max(24, width - _display_width(database_label))) + database_label
    top = [header, _ansi("─" * width, _DIM)]
    body_height = height - len(top) - 1
    footer, controls = _home_footer(width, height, animate)
    regions = []
    if width < 50 or height < 10:
        columns = 2 if width >= 26 else 1
        nav_rows = math.ceil(len(labels) / columns)
        graph_height = max(0, body_height - nav_rows - 1)
        body = [_ansi(title, _BOLD + _ACCENT), *_orbit(width, graph_height, angle, selected)] if graph_height else []
        cell_width = width // columns
        for row in range(nav_rows):
            parts = []
            for col in range(columns):
                index = row * columns + col
                if index >= len(labels):
                    continue
                number = "0" if index == len(labels) - 1 else str(index + 1)
                text = _pad_cells(_clip_cells(f" {'›' if selected == index else ' '} {number} {labels[index]}", cell_width), cell_width)
                parts.append(_ansi(text, _SELECTED) if selected == index else text)
                regions.append(HitRegion(col * cell_width + 1, len(top) + len(body) + 1, cell_width, f"item:{index}"))
            body.append("".join(parts))
        body = (body + [""] * body_height)[:body_height]
        return _starlight(ScreenFrame([_clip_cells(line, width) for line in [*top, *body, footer]], regions + controls), width, angle)
    nav_width = min(26, max(12, width // 3))
    graph_width = max(1, width - nav_width - 3)
    spacious = body_height >= 17 and width >= 64
    left = [_ansi("工作区 / NAVIGATION", _DIM), ""] if spacious else []
    for index, label in enumerate(labels):
        number = "0" if index == len(labels) - 1 else str(index + 1)
        text = f" {'›' if selected == index else ' '} {number}  {label}"
        text = _pad_cells(_clip_cells(text, nav_width - 1), nav_width - 1)
        regions.append(HitRegion(1, len(top) + len(left) + 1, nav_width - 1, f"item:{index}"))
        left.append(_ansi(text, _SELECTED) if index == selected else text)
        if spacious and index < len(labels) - 1:
            left.append("")
    if len(left) + 3 <= body_height:
        left.extend(["", _ansi("校园概览", _DIM),
                     f"学生 {stats.get('students', 0)}" if nav_width < 22 else
                     f"学生 {stats.get('students', 0)} / 班级 {stats.get('classes', 0)}"])
    if len(left) < body_height:
        left.append(f"课程 {stats.get('courses', 0)}" if nav_width < 22 else
                    f"课程 {stats.get('courses', 0)} / 选课 {stats.get('enrollments', 0)}")

    right = [_ansi(f"{selected + 1:02d} / {title}", _BOLD + _ACCENT)]
    if width >= 64 and body_height >= 12:
        right.extend([_ansi(description, _DIM), ""])
    tail = [_ansi(actions, _DIM)] if graph_width >= 28 else []
    if not stats.get("students") and graph_width >= 28:
        tail.append(_ansi("从「数据」写入演示数据，开始探索。", _GOLD))
    graph_height = max(1, body_height - len(right) - len(tail))
    right.extend(_orbit(graph_width, graph_height, angle, selected))
    right.extend(tail)
    body = []
    for row in range(body_height):
        left_line = left[row] if row < len(left) else ""
        right_line = right[row] if row < len(right) else ""
        body.append(_pad_cells(_clip_cells(left_line, nav_width), nav_width)
                    + _ansi(" │ ", _DIM) + _clip_cells(right_line, graph_width))
    return _starlight(ScreenFrame([_clip_cells(line, width) for line in [*top, *body, footer]], regions + controls), width, angle)


@dataclass
class _StarGlint:
    x: int
    row: int
    born: float
    lifetime: float
    pulse: float


_STAR_RNG = random.Random()
_STAR_GLINTS: list[_StarGlint] = []
_STAR_LAST_PHASE: float | None = None


def _starlight_positions(frame: ScreenFrame, width: int) -> list[tuple[int, int]]:
    """Return safe blank cells where a glint may be drawn."""
    positions: list[tuple[int, int]] = []
    for row in range(3, len(frame.lines) - 1):
        plain = _ANSI_RE.sub("", frame.lines[row])
        cell = 0
        run_start: int | None = None
        for char in plain + "x":
            if char == " " and run_start is None:
                run_start = cell
            elif char != " " and run_start is not None:
                start = run_start + 3
                stop = min(cell - 3, width)
                for x in range(start, stop):
                    if _hit_action(MouseClick(x + 1, row + 1), frame.regions) is None:
                        positions.append((row, x))
                run_start = None
            cell += _cell_width(char)
    return positions


def _starlight(frame: ScreenFrame, width: int, phase: float) -> ScreenFrame:
    """Random, short-lived glints that fade in and out across safe empty space."""
    global _STAR_LAST_PHASE

    allowed = _starlight_positions(frame, width)
    allowed_set = set(allowed)

    # Tests and previews may render older phases out of order. Treat a
    # backwards clock as a fresh sky instead of keeping future stars alive.
    if _STAR_LAST_PHASE is not None and phase < _STAR_LAST_PHASE:
        _STAR_GLINTS.clear()
    _STAR_LAST_PHASE = phase

    _STAR_GLINTS[:] = [
        star for star in _STAR_GLINTS
        if (star.row, star.x) in allowed_set and phase < star.born + star.lifetime
    ]

    desired = min(14, max(2, len(allowed) // 80)) if allowed else 0
    attempts = 0
    while len(_STAR_GLINTS) < desired and allowed and attempts < desired * 24:
        attempts += 1
        row, x = _STAR_RNG.choice(allowed)
        if any(abs(row - star.row) <= 1 and abs(x - star.x) < 7 for star in _STAR_GLINTS):
            continue
        lifetime = _STAR_RNG.uniform(1.8, 4.5)
        _STAR_GLINTS.append(_StarGlint(
            x=x,
            row=row,
            born=phase - _STAR_RNG.uniform(0.0, min(0.55, lifetime * 0.25)),
            lifetime=lifetime,
            pulse=_STAR_RNG.uniform(0.0, math.tau),
        ))

    by_row: dict[int, dict[int, str]] = {}
    for star in _STAR_GLINTS:
        progress = min(1.0, max(0.0, (phase - star.born) / star.lifetime))
        envelope = math.sin(math.pi * progress) ** 0.7
        twinkle = 0.72 + 0.28 * (math.sin(phase * 3.2 + star.pulse) + 1.0) / 2.0
        glow = min(1.0, max(0.0, envelope * twinkle))
        glyph = "✦" if glow > 0.82 else "·"
        color = 238 + round(glow * 9)
        by_row.setdefault(star.row, {})[star.x] = _ansi(glyph, f"\x1b[38;5;{color}m")

    for row, targets in by_row.items():
        original = frame.lines[row]
        parts: list[str] = []
        cell = 0
        for token in re.split(f"({_ANSI_RE.pattern})", original):
            if _ANSI_RE.fullmatch(token):
                parts.append(token)
                continue
            for char in token:
                parts.append(targets.get(cell, char) if char == " " else char)
                cell += _cell_width(char)
        frame.lines[row] = "".join(parts)
    return frame


def _home_lines(*args, **kwargs) -> list[str]:
    return _home_frame(*args, **kwargs).lines


def _paint(lines: Sequence[str], previous: Sequence[str] = ()) -> None:
    if sys.stdout.isatty():
        # Absolute row positions work even when the terminal disables ONLCR.
        # Reset BEFORE erasing, so the selection background cannot bleed.
        surface = _SURFACE if os.environ.get("NO_COLOR") is None else ""
        if len(lines) != len(previous) or max(map(_display_width, lines), default=0) != max(map(_display_width, previous), default=0):
            previous = ()
        frame = "".join(f"\x1b[{row};1H{_RESET}{surface}\x1b[2K"
                        + line.replace(_RESET, _RESET + surface) + _RESET
                        for row, line in enumerate(lines, start=1)
                        if row > len(previous) or line != previous[row - 1])
        sys.stdout.write(frame)
        sys.stdout.flush()
        return
    print("\n".join(lines))


def _home(
    db_path: Path | str | None,
    labels: Sequence[str],
    *,
    selected: int = 0,
    preferences: dict[str, bool] | None = None,
) -> int | None:
    from .service import XingyuanService

    stats = dict(XingyuanService(db_path).stats())
    preferences = preferences if preferences is not None else {"animate": True}
    angle = time.monotonic() * 0.85
    previous_lines: list[str] = []
    _clear()
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()

    try:
        with _mouse_tracking():
            return _home_loop(labels, stats, db_path, selected, preferences, angle, previous_lines)
    finally:
        if sys.stdout.isatty():
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()


def _home_loop(
    labels: Sequence[str], stats: dict[str, object], db_path: Path | str | None,
    selected: int, preferences: dict[str, bool], angle: float, previous_lines: list[str],
) -> int | None:
    while True:
        animate = preferences.get("animate", True)
        if animate:
            angle = time.monotonic() * 0.85
        frame = _home_frame(labels, selected, stats, angle, animate=animate,
                            database=Path(db_path).name if db_path else "xingyuan.db")
        lines = frame.lines
        if lines != previous_lines:
            _paint(lines, previous_lines)
            previous_lines = lines
        key = _read_key(0.08 if animate else 0.15)
        if isinstance(key, MouseClick):
            key = _hit_action(key, frame.regions)
            if key and key.startswith("item:"):
                return int(key.split(":")[1])
        if key == "up":
            selected = (selected - 1) % len(labels)
        elif key == "down":
            selected = (selected + 1) % len(labels)
        elif key == "select":
            return selected
        elif key == "home":
            selected = 0
        elif key == "end":
            selected = len(labels) - 1
        elif key in tuple("123456789") and int(key) <= len(labels):
            return int(key) - 1
        elif key == "pause":
            preferences["animate"] = not animate
        elif key == "back":
            return None

def _read(label: str) -> str:
    return read_input(f"{label}: ").strip()


def _command(db_path: Path | str | None, argv: list[str]) -> None:
    run_command(db_path, argv, _clear, interactive=True)


def _menu(title: str, items: Sequence[tuple[str, Callable[[], None]]]) -> None:
    selected = 0
    while True:
        try:
            choice = _select(title, [label for label, _ in items], selected=selected)
        except KeyboardInterrupt:
            return
        if choice is None:
            return
        selected = choice
        run_action(items[choice][1], _clear, interactive=True, title=f"{title} / {items[choice][0]}")


def _students(db_path: Path | str | None) -> None:
    def show() -> None:
        no = _read("学号")
        if no:
            _command(db_path, ["stu", "show", no])

    def edit() -> None:
        no = _read("学号")
        if no:
            _command(db_path, ["stu", "edit", no])

    def remove() -> None:
        no = _read("学号")
        if no:
            _command(db_path, ["stu", "rm", no])

    _menu(
        "学生",
        (
            ("学生列表", lambda: _command(db_path, ["stu", "ls"])),
            ("查看学生", show),
            ("新建学生", lambda: _command(db_path, ["stu", "add"])),
            ("编辑学生", edit),
            ("删除学生", remove),
            ("搜索学生", lambda: search_students(lambda argv: _command(db_path, argv))),
        ),
    )


def _academic_entity(db_path: Path | str | None, entity: str, title: str) -> None:
    def edit() -> None:
        code = _read("编号")
        if not code:
            return
        argv = ["acad", entity, "edit", code]
        new_code = _read("新编号（留空不改）")
        name = _read("新名称（留空不改）")
        if new_code:
            argv += ["--new-code", new_code]
        if name:
            argv += ["--name", name]
        if entity == "major":
            college = _read("新学院编号（留空不改）")
            if college:
                argv += ["--college", college]
        elif entity == "class":
            major = _read("新专业编号（留空不改）")
            year = read_number("新入学年份（留空不改）", integer=True, minimum=1900)
            if major:
                argv += ["--major", major]
            if year:
                argv += ["--year", year]
        _command(db_path, argv)

    def remove() -> None:
        code = _read("编号")
        if code:
            _command(db_path, ["acad", entity, "rm", code])

    _menu(
        title,
        (
            ("列表", lambda: _command(db_path, ["acad", entity, "ls"])),
            ("新建", lambda: _command(db_path, ["acad", entity, "add"])),
            ("编辑", edit),
            ("删除", remove),
        ),
    )


def _academics(db_path: Path | str | None) -> None:
    _menu(
        "教务",
        (
            ("学院", lambda: _academic_entity(db_path, "college", "教务 / 学院")),
            ("专业", lambda: _academic_entity(db_path, "major", "教务 / 专业")),
            ("班级", lambda: _academic_entity(db_path, "class", "教务 / 班级")),
        ),
    )


def _courses(db_path: Path | str | None) -> None:
    def show() -> None:
        code = _read("课程编号")
        if code:
            _command(db_path, ["course", "show", code])

    def edit() -> None:
        code = _read("课程编号")
        if not code:
            return
        argv = ["course", "edit", code]
        new_code = _read("新课程编号（留空不改）")
        name = _read("新名称（留空不改）")
        department = _read("新学院编号（留空不改）")
        credits = read_number("新学分（留空不改）")
        hours = read_number("新课时（留空不改）", integer=True)
        if new_code:
            argv += ["--new-code", new_code]
        if name:
            argv += ["--name", name]
        if department:
            argv += ["--department", department]
        if credits:
            argv += ["--credits", credits]
        if hours:
            argv += ["--hours", hours]
        _command(db_path, argv)

    def remove() -> None:
        code = _read("课程编号")
        if code:
            _command(db_path, ["course", "rm", code])

    _menu(
        "课程",
        (
            ("课程列表", lambda: _command(db_path, ["course", "ls"])),
            ("查看课程", show),
            ("新建课程", lambda: _command(db_path, ["course", "add"])),
            ("编辑课程", edit),
            ("删除课程", remove),
        ),
    )


def _grades(db_path: Path | str | None) -> None:
    def edit() -> None:
        student = _read("学号")
        course = _read("课程编号")
        semester = _read("学期")
        if not all((student, course, semester)):
            return
        score = read_number("新成绩（输入 - 清空，留空保持）", maximum=100, clearable=True)
        argv = ["grade", "edit", student, course, semester]
        if score == "-":
            argv.append("--clear-score")
        elif score:
            argv += ["--score", score]
        _command(db_path, argv)

    def remove() -> None:
        student = _read("学号")
        course = _read("课程编号")
        semester = _read("学期")
        if all((student, course, semester)):
            _command(db_path, ["grade", "rm", student, course, semester])

    _menu(
        "成绩",
        (
            ("成绩列表", lambda: _command(db_path, ["grade", "ls"])),
            ("添加选课 / 成绩", lambda: _command(db_path, ["grade", "add"])),
            ("编辑成绩", edit),
            ("删除选课", remove),
            ("搜索成绩", lambda: search_grades(lambda argv: _command(db_path, argv))),
        ),
    )


def _data(db_path: Path | str | None) -> None:
    def export() -> None:
        path = _read("导出文件") or "data/students.csv"
        _command(db_path, ["data", "export", path])

    def import_() -> None:
        path = _read("导入文件") or "data/students.csv"
        _command(db_path, ["data", "import", path])

    _menu(
        "数据",
        (
            ("统计摘要", lambda: _command(db_path, ["data", "stats"])),
            ("导出学生 CSV", export),
            ("导入学生 CSV", import_),
            ("写入演示数据", lambda: _command(db_path, ["data", "seed"])),
        ),
    )


def run(db_path: Path | str | None = None) -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise RuntimeError("当前环境不是交互终端；请使用 xy <command>")

    actions: tuple[Callable[[], None], ...] = (
        lambda: _students(db_path),
        lambda: _academics(db_path),
        lambda: _courses(db_path),
        lambda: _grades(db_path),
        lambda: _data(db_path),
    )
    labels = ("学生", "教务", "课程", "成绩", "数据", "退出")

    selected = 0
    preferences = {"animate": True}
    try:
        while True:
            choice = _home(db_path, labels, selected=selected, preferences=preferences)
            if choice is None or choice == len(labels) - 1:
                _clear()
                return
            selected = choice
            run_action(actions[choice], _clear, interactive=True, title=labels[choice])
    except (KeyboardInterrupt, EOFError):
        print("\n已退出星原 SIS。")