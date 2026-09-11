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


_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_ACCENT = "\x1b[36m"
_DIM = "\x1b[2m"
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _ansi(text: str, style: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR") is not None:
        return text
    return f"{style}{text}{_RESET}"


def _display_width(text: str) -> int:
    plain = _ANSI_RE.sub("", text)
    return sum(
        2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        for char in plain
    )


def _pad_cells(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


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
        return "other"
    if char in {" ", "\r", "\n"}:
        return "select"
    if char == "\x1b" or char.lower() == "q":
        return "back"
    return "other"


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
        tty.setcbreak(fd)
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
            return "back"
        if char in {b" ", b"\r", b"\n"}:
            return "select"
        if char in {b"q", b"Q"}:
            return "back"
        return "other"
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
) -> int | None:
    if not items:
        return None
    selected = 0
    while True:
        _clear()
        print(_ansi("星原 SIS", _BOLD + _ACCENT))
        if title:
            print(_ansi(f"{title}\n", _DIM))
        else:
            print()

        for index, label in enumerate(items):
            if index == selected:
                print(f"{_ansi('›', _ACCENT)} {_ansi(label, _BOLD)}")
            else:
                print(f"  {label}")

        back_hint = f"   Esc/q {back_label}" if allow_back else ""
        print(_ansi(f"\n↑↓ 移动   Space 确定{back_hint}", _DIM))

        key = _read_key()
        if key == "up":
            selected = (selected - 1) % len(items)
        elif key == "down":
            selected = (selected + 1) % len(items)
        elif key == "select":
            return selected
        elif key == "back" and allow_back:
            return None


_PHI = (1.0 + math.sqrt(5.0)) / 2.0
_ICO_VERTICES: tuple[tuple[float, float, float], ...] = (
    (0, -1, -_PHI), (0, -1, _PHI), (0, 1, -_PHI), (0, 1, _PHI),
    (-1, -_PHI, 0), (-1, _PHI, 0), (1, -_PHI, 0), (1, _PHI, 0),
    (-_PHI, 0, -1), (_PHI, 0, -1), (-_PHI, 0, 1), (_PHI, 0, 1),
)


def _icosahedron_edges() -> tuple[tuple[int, int], ...]:
    distances: list[tuple[float, int, int]] = []
    for left in range(len(_ICO_VERTICES)):
        x1, y1, z1 = _ICO_VERTICES[left]
        for right in range(left + 1, len(_ICO_VERTICES)):
            x2, y2, z2 = _ICO_VERTICES[right]
            distance = (x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2
            distances.append((distance, left, right))
    edge_length = min(distance for distance, _, _ in distances)
    return tuple(
        (left, right)
        for distance, left, right in distances
        if abs(distance - edge_length) < 1e-7
    )


_ICO_EDGES = _icosahedron_edges()


def _rotate_point(
    point: tuple[float, float, float],
    angle: float,
) -> tuple[float, float, float]:
    x, y, z = point

    ay = angle
    cy, sy = math.cos(ay), math.sin(ay)
    x, z = x * cy + z * sy, -x * sy + z * cy

    ax = angle * 0.63 + 0.45
    cx, sx = math.cos(ax), math.sin(ax)
    y, z = y * cx - z * sx, y * sx + z * cx

    az = angle * 0.31
    cz, sz = math.cos(az), math.sin(az)
    x, y = x * cz - y * sz, x * sz + y * cz
    return x, y, z


def _project_point(
    point: tuple[float, float, float],
    width: int,
    height: int,
) -> tuple[int, int, float]:
    x, y, z = point
    distance = 5.2
    perspective = distance / (distance + z)
    screen_x = int(round(width / 2 + x * perspective * width * 0.22))
    screen_y = int(round(height / 2 - y * perspective * height * 0.34))
    return screen_x, screen_y, z


def _draw_line(
    canvas: list[list[str]],
    start: tuple[int, int, float],
    end: tuple[int, int, float],
) -> None:
    x0, y0, z0 = start
    x1, y1, z1 = end
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    depth = (z0 + z1) / 2
    char = "." if depth > 0.45 else ":" if depth > -0.45 else "*"

    while True:
        if 0 <= y0 < len(canvas) and 0 <= x0 < len(canvas[0]):
            if canvas[y0][x0] == " ":
                canvas[y0][x0] = char
        if x0 == x1 and y0 == y1:
            break
        twice = 2 * error
        if twice >= dy:
            error += dy
            x0 += sx
        if twice <= dx:
            error += dx
            y0 += sy


def _render_3d(width: int, height: int, angle: float) -> list[str]:
    width = max(20, width)
    height = max(8, height)
    canvas = [[" " for _ in range(width)] for _ in range(height)]

    rotated = [_rotate_point(point, angle) for point in _ICO_VERTICES]
    projected = [_project_point(point, width, height) for point in rotated]

    for left, right in _ICO_EDGES:
        _draw_line(canvas, projected[left], projected[right])

    for x, y, z in projected:
        if 0 <= y < height and 0 <= x < width:
            canvas[y][x] = "o" if z > 0 else "O"

    # Two orbital rings make the wireframe feel less like a static demo shape.
    for tilt, phase in ((0.55, angle * 0.35), (-0.75, -angle * 0.28)):
        for step in range(52):
            theta = step * math.tau / 52 + phase
            point = (
                2.25 * math.cos(theta),
                0.45 * math.sin(theta + tilt),
                2.25 * math.sin(theta),
            )
            x, y, _ = _project_point(_rotate_point(point, angle * 0.35 + tilt), width, height)
            if 0 <= y < height and 0 <= x < width and canvas[y][x] == " ":
                canvas[y][x] = "."

    lines = ["".join(row).rstrip() for row in canvas]
    if lines:
        caption = " XINGYUAN / CORE "
        start = max(0, (width - len(caption)) // 2)
        row = list(lines[0].ljust(width))
        for offset, char in enumerate(caption):
            if start + offset < width:
                row[start + offset] = char
        lines[0] = "".join(row).rstrip()
    return lines


def _overview_lines(stats: dict[str, object]) -> list[str]:
    average = stats.get("average_score")
    if average is None:
        average_text = "—"
    else:
        try:
            average_text = f"{float(average):.1f}"
        except (TypeError, ValueError):
            average_text = str(average)

    return [
        _ansi("OVERVIEW", _DIM),
        f"{_ansi(str(stats.get('students', 0)), _BOLD)} 学生   "
        f"{_ansi(str(stats.get('classes', 0)), _BOLD)} 班级",
        f"{_ansi(str(stats.get('courses', 0)), _BOLD)} 课程   "
        f"{_ansi(average_text, _BOLD)} 平均成绩",
    ]


def _home_lines(
    labels: Sequence[str],
    selected: int,
    stats: dict[str, object],
    angle: float,
) -> list[str]:
    terminal = shutil.get_terminal_size((80, 24))
    width = max(36, terminal.columns)
    height = max(16, terminal.lines)

    left: list[str] = [
        _ansi("星原 SIS", _BOLD + _ACCENT),
        _ansi("星原大学学生信息系统", _DIM),
        "",
        *_overview_lines(stats),
        "",
    ]
    for index, label in enumerate(labels):
        if index == selected:
            left.append(f"{_ansi('›', _ACCENT)} {_ansi(label, _BOLD)}")
        else:
            left.append(f"  {label}")
    left.extend(("", _ansi("↑↓ 移动   Space 确定   Esc/q 退出", _DIM)))

    if width >= 70:
        graph_width = min(40, max(28, width // 2 - 2))
        left_width = max(28, width - graph_width - 3)
        graph_height = min(16, max(11, height - 5))
        graph = [_ansi(line, _ACCENT + _DIM) for line in _render_3d(graph_width, graph_height, angle)]
        total = max(len(left), len(graph))
        lines: list[str] = []
        for row in range(total):
            left_line = left[row] if row < len(left) else ""
            graph_line = graph[row] if row < len(graph) else ""
            lines.append(f"{_pad_cells(left_line, left_width)}   {graph_line}".rstrip())
        return lines

    graph_width = min(width - 2, 34)
    graph_height = 9 if height < 25 else 11
    graph = [_ansi(line, _ACCENT + _DIM) for line in _render_3d(graph_width, graph_height, angle)]
    return [*left, "", *graph]


def _paint(lines: Sequence[str]) -> None:
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[H" + "\n".join(lines) + "\x1b[J")
        sys.stdout.flush()
        return
    _clear()
    print("\n".join(lines))


def _home(db_path: Path | str | None, labels: Sequence[str]) -> int | None:
    from .service import XingyuanService

    stats = dict(XingyuanService(db_path).stats())
    selected = 0
    _clear()
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()

    try:
        while True:
            _paint(_home_lines(labels, selected, stats, time.monotonic() * 0.85))
            key = _read_key(0.075)
            if key == "up":
                selected = (selected - 1) % len(labels)
            elif key == "down":
                selected = (selected + 1) % len(labels)
            elif key == "select":
                return selected
            elif key == "back":
                return None
    finally:
        if sys.stdout.isatty():
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()


def _pause() -> None:
    input("\n按 Enter 返回…")


def _read(label: str) -> str:
    return input(f"{label}: ").strip()


def _db_args(db_path: Path | str | None) -> list[str]:
    return [] if db_path is None else ["--db", str(db_path)]


def _command(db_path: Path | str | None, argv: list[str]) -> None:
    from .entry import main as entry_main

    _clear()
    try:
        code = entry_main([*_db_args(db_path), *argv])
    except SystemExit as error:
        code = int(error.code or 0)
    if code:
        print(f"\n命令返回状态 {code}")
    _pause()


def _menu(title: str, items: Sequence[tuple[str, Callable[[], None]]]) -> None:
    while True:
        choice = _select(title, [label for label, _ in items])
        if choice is None:
            return
        items[choice][1]()


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
            year = _read("新入学年份（留空不改）")
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
        credits = _read("新学分（留空不改）")
        hours = _read("新课时（留空不改）")
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
        score = _read("新成绩（输入 - 清空，留空保持）")
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

    while True:
        choice = _home(db_path, labels)
        if choice is None or choice == len(labels) - 1:
            _clear()
            return
        actions[choice]()
