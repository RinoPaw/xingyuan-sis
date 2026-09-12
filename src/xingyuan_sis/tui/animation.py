"""Home-screen orbital illustration and quiet background stars."""
from __future__ import annotations
from dataclasses import dataclass
import math
import random
import re
from .screen import (_ansi, _ACCENT, _GOLD, _ANSI_RE, _cell_width, _hit_action,
                     MouseClick, ScreenFrame)


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
