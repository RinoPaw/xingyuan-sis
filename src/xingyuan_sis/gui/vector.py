"""Resolution-independent decoration rendered by Tk 9's built-in SVG handler.

Canvas items retain the source coordinates for inspection; only their rendering
is replaced. Text and interactive controls remain native Tk/ttk widgets.
"""
from __future__ import annotations

import tkinter as tk
from xml.sax.saxutils import quoteattr


class VectorCanvas(tk.Canvas):
    """A small polygon/line scene, antialiased at its actual physical size.

    Call render() after drawing a scene. No image is stretched, no bitmap asset
    is loaded, and each resize creates a fresh render from the vector geometry.
    Older Tk builds without SVG retain native Canvas paths (without SVG AA).
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.image = None
        self.svg_source = ""
        # Probe once per interpreter, including vendor builds/backported SVG.
        root = self._root()
        if not hasattr(root, "campus_svg_supported"):
            try:
                tk.PhotoImage(master=self, data='<svg width="1" height="1"/>',
                              format=("svg", "-scale", 1))
            except tk.TclError:
                root.campus_svg_supported = False
            else:
                root.campus_svg_supported = True
        self.antialiased = root.campus_svg_supported

    def render(self):
        if not self.antialiased:
            return
        width, height = self.winfo_width(), self.winfo_height()
        if width < 2 or height < 2:
            return
        self.delete("vector-render")
        shapes = []
        for item in self.find_all():
            kind = self.type(item)
            if kind not in {"polygon", "line"}:
                continue
            coords = self.coords(item)
            points = " ".join(f"{x:g},{y:g}" for x, y in zip(coords[::2], coords[1::2]))
            fill = quoteattr(self.itemcget(item, "fill"))
            if kind == "polygon":
                shapes.append(f'<polygon points="{points}" fill={fill}/>')
            else:
                stroke_width = quoteattr(self.itemcget(item, "width"))
                shapes.append(f'<polyline points="{points}" fill="none" stroke={fill} stroke-width={stroke_width}/>')
            self.itemconfigure(item, state="hidden")
        background = quoteattr(self.cget("background"))
        source = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
            f'<rect width="{width}" height="{height}" fill={background}/>'
            + "".join(shapes) + '</svg>'
        )
        # Configure and state callbacks often redraw identical vector scenes.
        # Reuse the decoded Tk image when only the Canvas item IDs changed.
        # A new size, palette or geometry still produces a fresh SVG raster.
        if source != self.svg_source or self.image is None:
            # Coordinates already include DPI and zoom; do not scale twice.
            image = tk.PhotoImage(master=self, data=source,
                                  format=("svg", "-scale", 1))
            self.image = image
            self.svg_source = source
        layer = self.create_image(0, 0, image=self.image, anchor="nw", tags="vector-render")
        # Native Canvas text has no rectangular background. Keep it above the
        # SVG decoration instead of baking glyphs into an image.
        self.tag_lower(layer)

    def destroy(self):
        super().destroy()
        self.image = None
