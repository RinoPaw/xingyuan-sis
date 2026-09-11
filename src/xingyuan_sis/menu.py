from __future__ import annotations

import math
import os
from pathlib import Path
import re
import select
import shutil
import sys
import time
import unicodedata
from typing import Callable, Sequence

from .terminal_ui import read_number, run_action, run_command, search_grades, search_students


_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_ACCENT = "\x1b[36m"
_DIM = "\x1b[2m"
_SELECTED = "\x1b[30;106m"
_GOLD = "\x1b[93m"
_BAR = "\x1b[37;44m"
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
    return char if char in "123456789" else "other"


def _read_escape_sequence(fd: int) -> bytes:
    """Read the bytes following ESC without going through TextIO buffering."""
    sequence = bytearray()
    while len(sequence) < 16:
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


def _read_key_posix(timeout: float | None = None) -> str | None:
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
            if sequence in {b"[A", b"OA"} or (
                sequence.startswith(b"[") and sequence.endswith(b"A")
            ):
                return "up"
            if sequence in {b"[B", b"OB"} or (
                sequence.startswith(b"[") and sequence.endswith(b"B")
            ):
                return "down"
            if sequence in {b"[H", b"OH", b"[1~", b"[7~"}:
                return "home"
            if sequence in {b"[F", b"OF", b"[4~", b"[8~"}:
                return "end"
            return "other" if sequence else "back"
        return _plain_key(char.decode("ascii", errors="replace"))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def _read_key(timeout: float | None = None) -> str | None:
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
    while True:
        _clear()
        print(_ansi("✦ 星原 / 教务台", _BOLD + _ACCENT))
        if title:
            print(_ansi(f"首页 / {title}\n", _DIM))
        else:
            print()

        for index, label in enumerate(items):
            if index == selected:
                print(f"{_ansi('›', _ACCENT)} {index + 1}. {_ansi(label, _BOLD)}")
            else:
                print(f"  {index + 1}. {label}")

        back_hint = f"   Esc/q {back_label}" if allow_back else ""
        print(_ansi("\n↑↓/j/k 移动 · Enter/Space 确定", _DIM))
        print(_ansi(f"数字直达{back_hint}", _DIM))

        key = _read_key()
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

    styles = ("", "\x1b[34m", "\x1b[96m", _GOLD, "\x1b[97m")
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


def _bottom_bar(width: int, animate: bool) -> str:
    motion = "暂停" if animate else "播放"
    candidates = (
        f" ↑↓/jk 移动   Enter/Space 打开   1–5 直达   p {motion}   q/0 退出 ",
        f" ↑↓ 移动  Enter 打开  数字直达  p {motion}  q 退出 ",
        f" ↑↓  Enter打开  p{motion}  q退出 ",
        f" ↑↓ Enter p{motion} q退出 ",
        " Enter打开 q退出 ",
    )
    text = next((text for text in candidates if _display_width(text) <= width), candidates[-1])
    return _ansi(_pad_cells(_clip_cells(text, width), width), _BAR)


def _home_lines(
    labels: Sequence[str],
    selected: int,
    stats: dict[str, object],
    angle: float,
    *,
    animate: bool = True,
    database: str = "xingyuan.db",
) -> list[str]:
    terminal = _terminal_size()
    width, height = max(1, terminal.columns - 1), max(3, terminal.lines)
    title, description, actions = _MODULES[selected]
    header = _ansi("✦ 星原 / 教务台", _BOLD + _ACCENT)
    database_label = _ansi(f"LOCAL / {database}", _DIM)
    if width >= 64:
        header = _pad_cells(header, max(24, width - _display_width(database_label))) + database_label
    top = [header, _ansi("─" * width, _DIM)]
    body_height = height - len(top) - 1
    nav_width = min(26, max(12, width // 3))
    graph_width = max(1, width - nav_width - 3)
    spacious = body_height >= 17 and width >= 64
    left = [_ansi("工作区 / NAVIGATION", _DIM), ""] if spacious else []
    for index, label in enumerate(labels):
        number = "0" if index == len(labels) - 1 else str(index + 1)
        text = f" {'›' if selected == index else ' '} {number}  {label}"
        text = _pad_cells(_clip_cells(text, nav_width - 1), nav_width - 1)
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
    return [_clip_cells(line, width) for line in [*top, *body, _bottom_bar(width, animate)]]


def _paint(lines: Sequence[str]) -> None:
    if sys.stdout.isatty():
        # Absolute row positions work even when the terminal disables ONLCR.
        # Reset BEFORE erasing, so the selection background cannot bleed.
        frame = "".join(f"\x1b[{row};1H{_RESET}\x1b[2K{line}{_RESET}"
                        for row, line in enumerate(lines, start=1))
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
        while True:
            animate = preferences.get("animate", True)
            if animate:
                angle = time.monotonic() * 0.85
            lines = _home_lines(labels, selected, stats, angle, animate=animate,
                                database=Path(db_path).name if db_path else "xingyuan.db")
            if lines != previous_lines:
                _paint(lines)
                previous_lines = lines
            key = _read_key(0.08 if animate else 0.5)
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
    finally:
        if sys.stdout.isatty():
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()


def _read(label: str) -> str:
    return input(f"{label}: ").strip()


def _command(db_path: Path | str | None, argv: list[str]) -> None:
    run_command(db_path, argv, _clear)


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
        run_action(items[choice][1], _clear)


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
            run_action(actions[choice], _clear)
    except (KeyboardInterrupt, EOFError):
        print("\n已退出星原 SIS。")
