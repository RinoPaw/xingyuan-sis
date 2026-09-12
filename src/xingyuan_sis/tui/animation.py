"""Home-screen orbital illustration and quiet background stars."""
from __future__ import annotations

import math
import os
import re

from .screen import (
    _ACCENT,
    _ANSI_RE,
    _GOLD,
    _ansi,
    _cell_width,
    _hit_action,
    MouseClick,
    ScreenFrame,
)


_SPARKLE_DOTS = ("⠁", "⠂", "⠄", "⠈", "⠐", "⠠", "⡀", "⢀")
_SPARKLE_FRAME = 0.150
_SPARKLE_BG = 38
_SPARKLE_FG = 208
_SPARKLE_DENSITY_NUMERATOR = 3
_SPARKLE_DENSITY_DENOMINATOR = 20
_SPARKLE_DURATION_SCALE = 1.25


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


def _orbit_exclusion_mask(width: int, height: int, angle: float) -> set[tuple[int, int]]:
    """Protect the globe interior and the two orbital strokes from sparkles.

    The empty sky between the globe and the rings stays available for stars. The
    rings themselves get a thin protected band so a sparkle cannot visually sit
    on an orbital stroke even when Braille rasterization leaves nearby blank cells.
    """
    width, height = max(1, width), max(1, height)
    pixels_w, pixels_h = width * 2, height * 4
    radius = min(pixels_w / 4.8, pixels_h / 2.5)
    cx, cy = pixels_w / 2, pixels_h / 2
    tilt = -0.32 + math.sin(angle * 0.18) * 0.1
    cos_t, sin_t = math.cos(tilt), math.sin(tilt)
    ring_b = radius * 0.48
    # About one Braille pixel on either side of the orbital curve.
    ring_band = 1.25 / max(1.0, ring_b)
    protected: set[tuple[int, int]] = set()

    for row in range(height):
        for col in range(width):
            # A terminal cell contains 2×4 Braille pixels. Protect the whole
            # cell when any subpixel lies in the globe or close to either ring.
            for dy in range(4):
                for dx in range(2):
                    x = col * 2 + dx - cx
                    y = row * 4 + dy - cy
                    if x * x + y * y <= radius * radius:
                        protected.add((row, col))
                        break

                    # Undo the ring tilt and measure distance from each ellipse
                    # in normalized coordinates. Only the narrow stroke is
                    # protected; the ellipse interior remains usable sky.
                    u = x * cos_t + y * sin_t
                    v = -x * sin_t + y * cos_t
                    on_ring = False
                    for scale in (1.8, 2.12):
                        ring_a = radius * scale
                        ellipse_radius = math.sqrt((u / ring_a) ** 2 + (v / ring_b) ** 2)
                        if abs(ellipse_radius - 1.0) <= ring_band:
                            on_ring = True
                            break
                    if on_ring:
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
    """Render a stable Codex-style sparkle field over untouched empty cells.

    A coordinate hash fixes each star's position, Braille glyph, period and phase.
    The layout therefore stays still while individual dots briefly brighten, which
    avoids the particle-like popping of the previous random star lifecycle.
    """
    # ``phase`` is the globe angle (monotonic seconds * 0.85). Convert it back
    # to seconds and quantize to Codex's 150 ms sparkle cadence.
    seconds = max(0.0, phase / 0.85)
    seconds = math.floor(seconds / _SPARKLE_FRAME) * _SPARKLE_FRAME
    mask = (1 << 64) - 1
    truecolor = os.environ.get("COLORTERM", "").lower() in {"truecolor", "24bit"}
    protected_cells = protected_cells or set()

    # Leave the top bar and footer untouched. Within the body, only use the
    # interior of blank runs and exclude clickable/protected regions.
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
            # Same coordinate hash as Codex, with a 15% candidate density:
            # 3/20 is exactly one quarter fewer stars than the original 1/5.
            hash_value = ((row - 1) * 65537 + x) & mask
            hash_value = ((hash_value ^ (hash_value >> 16)) * 0x45D9F3B) & mask
            hash_value = ((hash_value ^ (hash_value >> 16)) * 0x45D9F3B) & mask
            hash_value ^= hash_value >> 16
            if hash_value % _SPARKLE_DENSITY_DENOMINATOR >= _SPARKLE_DENSITY_NUMERATOR:
                continue

            # Stretch each sparkle cycle by 25%, preserving the same phase curve.
            period = (4.0 + (hash_value % 31) / 10.0) * _SPARKLE_DURATION_SCALE
            sparkle_phase = (seconds / period + (hash_value % 997) / 997.0) % 1.0
            brightness = math.sin(sparkle_phase * math.pi) ** 12 * 0.55
            if brightness < 0.04:
                continue

            glyph = _SPARKLE_DOTS[(hash_value // 161) % len(_SPARKLE_DOTS)]
            level = round(_SPARKLE_BG + (_SPARKLE_FG - _SPARKLE_BG) * brightness)
            if truecolor:
                style = f"\x1b[38;2;{level};{level};{level}m"
            else:
                # xterm's grayscale ramp approximates the same foreground/background blend.
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
