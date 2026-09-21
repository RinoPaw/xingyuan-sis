"""Terminal animation primitives and decorative effects."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
import math
import os
import re
import time

from .screen import (
    _ANSI_RE,
    _TEXT_ACCENT,
    _DECORATIVE_GOLD,
    _ansi,
    _cell_width,
    _display_width,
    _hit_action,
    _paint,
    _paint_region,
    MouseClick,
    ScreenFrame,
)


_TRANSIENT_FRAME_INTERVAL = 1 / 60
_SPARKLE_DOTS = ("⠁", "⠂", "⠄", "⠈", "⠐", "⠠", "⡀", "⢀")
_SPARKLE_FRAME = 0.150
_SPARKLE_BG = 38
_SPARKLE_FG = 208
_SPARKLE_DENSITY_DENOMINATOR = 10
_RING_INNER_SCALE = 1.8
_RING_OUTER_SCALE = 2.12
_RING_MINOR_SCALE = 0.48


def play_region_frames(
    base_lines: Sequence[str],
    x: int,
    y: int,
    width: int,
    frames: Iterable[str],
) -> None:
    """Play transient canvases without repainting the application between frames."""
    _paint(base_lines)
    previous_top = y + 1

    for frame in frames:
        rows = frame.split("\n")
        top = y - len(rows) + 1

        # If the new canvas is shorter, restore only rows uncovered by it. The
        # rest of the application never needs to be repainted during an effect.
        for target_y in range(previous_top, min(top, y)):
            if 1 <= target_y <= len(base_lines):
                base = base_lines[target_y - 1]
                _paint_region(1, target_y, max(1, _display_width(base)), base)

        for offset, row in enumerate(rows):
            target_y = top + offset
            if 1 <= target_y <= len(base_lines):
                _paint_region(x, target_y, width, row)

        previous_top = top
        time.sleep(_TRANSIENT_FRAME_INTERVAL)


def _ring_band_contains(u: float, v: float, radius: float) -> bool:
    """Return whether an unrotated point lies in the ring's solid physical band.

    The UI draws only the two boundaries, but the space between them is still
    treated as ring material for sparkle occlusion.
    """
    outer_a = radius * _RING_OUTER_SCALE
    outer_b = radius * _RING_MINOR_SCALE
    inner_a = radius * _RING_INNER_SCALE
    inner_b = radius * _RING_MINOR_SCALE
    outer = (u / outer_a) ** 2 + (v / outer_b) ** 2
    inner = (u / inner_a) ** 2 + (v / inner_b) ** 2
    return outer <= 1.0 and inner >= 1.0


def _orbit(width: int, height: int, angle: float, selected: int) -> list[str]:
    """Draw a rotating globe and the outlined edges of a solid tilted ring."""
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

    tilt = -0.32 + math.sin(angle * 0.18) * 0.1

    def ring(t: float, scale: float) -> tuple[float, float]:
        x = radius * scale * math.cos(t)
        y = radius * _RING_MINOR_SCALE * math.sin(t)
        return x * math.cos(tilt) - y * math.sin(tilt), x * math.sin(tilt) + y * math.cos(tilt)

    def hidden_by_globe(t: float, x: float, y: float) -> bool:
        return math.sin(t) < 0 and x * x + y * y < radius * radius

    for scale in (_RING_INNER_SCALE, _RING_OUTER_SCALE):
        steps = max(120, width * 10)
        for step in range(steps):
            t = step * math.tau / steps
            x, y = ring(t, scale)
            if hidden_by_globe(t, x, y):
                continue
            point(x, y, 3)

    t = angle * 0.9 + selected * math.tau / 6
    x, y = ring(t, _RING_OUTER_SCALE)
    for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
        marker_x, marker_y = x + dx, y + dy
        if hidden_by_globe(t, marker_x, marker_y):
            continue
        point(marker_x, marker_y, 4)

    styles = ("", "\x1b[38;5;60m", _TEXT_ACCENT, _DECORATIVE_GOLD, "\x1b[38;5;252m")
    lines = []
    for row in range(height):
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


def _orbit_exclusion_mask(width: int, height: int, angle: float) -> set[tuple[int, int]]:
    """Protect the globe interior and the ring's physical band from sparkles."""
    width, height = max(1, width), max(1, height)
    pixels_w, pixels_h = width * 2, height * 4
    radius = min(pixels_w / 4.8, pixels_h / 2.5)
    cx, cy = pixels_w / 2, pixels_h / 2
    tilt = -0.32 + math.sin(angle * 0.18) * 0.1
    cos_t, sin_t = math.cos(tilt), math.sin(tilt)
    protected: set[tuple[int, int]] = set()

    for row in range(height):
        for col in range(width):
            for dy in range(4):
                for dx in range(2):
                    x = col * 2 + dx - cx
                    y = row * 4 + dy - cy
                    if x * x + y * y <= radius * radius:
                        protected.add((row, col))
                        break

                    u = x * cos_t + y * sin_t
                    v = -x * sin_t + y * cos_t
                    if _ring_band_contains(u, v, radius):
                        protected.add((row, col))
                        break
                if (row, col) in protected:
                    break

    return protected


def _starlight(
    frame: ScreenFrame,
    width: int,
    phase: float,
    protected_cells: set[tuple[int, int]] | None = None,
) -> ScreenFrame:
    """Render a stable sparkle field over untouched empty cells."""
    seconds = max(0.0, phase / 0.85)
    seconds = math.floor(seconds / _SPARKLE_FRAME) * _SPARKLE_FRAME
    mask = (1 << 64) - 1
    truecolor = os.environ.get("COLORTERM", "").lower() in {"truecolor", "24bit"}
    protected_cells = protected_cells or set()

    for row in range(1, len(frame.lines) - 1):
        original = frame.lines[row]
        plain = _ANSI_RE.sub("", original)

        allowed: set[int] = set()
        cell = 0
        run_start: int | None = None
        for char in plain + "x":
            if char == " " and run_start is None:
                run_start = cell
            elif char != " " and run_start is not None:
                start = run_start + 2
                stop = min(cell - 2, width)
                for x in range(start, stop):
                    if (
                        (row, x) not in protected_cells
                        and _hit_action(MouseClick(x + 1, row + 1), frame.regions) is None
                    ):
                        allowed.add(x)
                run_start = None
            cell += _cell_width(char)

        if not allowed:
            continue

        targets: dict[int, str] = {}
        for x in allowed:
            hash_value = ((row - 1) * 65537 + x) & mask
            hash_value = ((hash_value ^ (hash_value >> 16)) * 0x45D9F3B) & mask
            hash_value = ((hash_value ^ (hash_value >> 16)) * 0x45D9F3B) & mask
            hash_value ^= hash_value >> 16
            if hash_value % _SPARKLE_DENSITY_DENOMINATOR != 0:
                continue

            period = 6.0 + (hash_value % 41) / 10.0
            sparkle_phase = (seconds / period + (hash_value % 997) / 997.0) % 1.0
            brightness = math.sin(sparkle_phase * math.pi) ** 12 * 0.55
            if brightness < 0.04:
                continue

            glyph = _SPARKLE_DOTS[(hash_value // 161) % len(_SPARKLE_DOTS)]
            level = round(_SPARKLE_BG + (_SPARKLE_FG - _SPARKLE_BG) * brightness)
            if truecolor:
                style = f"\x1b[38;2;{level};{level};{level}m"
            else:
                gray = max(235, min(244, 232 + round((level - 8) / 10)))
                style = f"\x1b[38;5;{gray}m"
            targets[x] = _ansi(glyph, style)

        if not targets:
            continue

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
