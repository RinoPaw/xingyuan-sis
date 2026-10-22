"""Shared wheel routing and quiet native scrollbars for the desktop workspace."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk


def scroll_view(view, event):
    """One wheel gesture scrolls one viewport, including high-resolution wheels."""
    number = getattr(event, "num", None)
    if number in (4, 5):
        units = -1 if number == 4 else 1
    else:
        divisor = 1 if sys.platform == "darwin" else 120
        remainder = getattr(view, "_wheel_remainder", 0) - event.delta / divisor
        units = int(remainder)
        view._wheel_remainder = remainder - units
    if units:
        view.yview_scroll(units, "units")
    return "break"


def route_wheel(event):
    """Closed choices never change value; route to the nearest reading surface."""
    widget = event.widget
    while widget is not None:
        if isinstance(widget, ttk.Notebook) and widget.select():
            page = widget.nametowidget(widget.select())
            # Notebook tabs scroll their selected page, never cycle categories.
            queue = [page]
            while queue:
                child = queue.pop(0)
                if isinstance(child,ttk.Notebook) and child.select():
                    queue.insert(0,child.nametowidget(child.select()))
                    continue
                if hasattr(child, "wheel_view"):
                    return scroll_view(child.wheel_view(), event)
                if isinstance(child, (tk.Text, ttk.Treeview)):
                    return scroll_view(child, event)
                queue.extend(child.winfo_children())
        if hasattr(widget, "wheel_view"):
            target = widget.wheel_view()
            if target is not None and target.winfo_ismapped():
                return scroll_view(target, event)
        widget = widget.master
    return "break"


def install_wheel_policy(root):
    if getattr(root, "campus_wheel_policy", False):
        return
    root.campus_wheel_policy = True
    for class_name in ("TCombobox", "TNotebook"):
        for sequence in ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>"):
            root.bind_class(class_name, sequence, route_wheel)
    def background_wheel(event):
        if not isinstance(event.widget, (tk.Text, ttk.Treeview, ttk.Scrollbar)):
            return route_wheel(event)
    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        root.bind_all(sequence, background_wheel, add="+")


class AutoScrollbar(ttk.Scrollbar):
    """Show only while using an overflowing viewport; retain a stable gutter.

    The thumb remains a native scrollbar, including dragging and trough clicks.
    Reserving its narrow gutter prevents show/hide from resizing wrapped text.
    """
    def __init__(self, parent, *, viewport, **kwargs):
        super().__init__(parent, takefocus=False, **kwargs)
        self._timer = None
        self._range = None
        self._overflow = False
        self._hover = self._dragging = False
        self.viewport = viewport
        for sequence in ("<Enter>", "<MouseWheel>", "<Button-4>", "<Button-5>", "<KeyPress>", "<FocusIn>"):
            viewport.bind(sequence, self.reveal, add="+")
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)

    def grid(self, **kwargs):
        super().grid(**kwargs)
        info = self.grid_info()
        if str(self.cget("orient")) == "vertical":
            self.master.columnconfigure(info["column"], minsize=self.winfo_reqwidth())
        else:
            self.master.rowconfigure(info["row"], minsize=self.winfo_reqheight())

    def set(self, first, last):
        values = float(first), float(last)
        self._overflow = values[0] > .00001 or values[1] < .99999
        super().set(first, last)
        if not self._overflow:
            self._hide()
        elif values != self._range:
            self.reveal()
        self._range = values

    def reveal(self, event=None):
        if not self._overflow:
            return
        super().grid()
        if self._timer is not None:
            self.after_cancel(self._timer)
        self._timer = self.after(1100, self._hide)

    def _hide(self):
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None
        if not self._hover and not self._dragging or not self._overflow:
            self.grid_remove()

    def _enter(self, event):
        self._hover = True
        self.reveal()

    def _leave(self, event):
        self._hover = False
        self.reveal()

    def _press(self, event):
        self._dragging = True

    def _release(self, event):
        self._dragging = False
        self.reveal()

    def destroy(self):
        if self._timer is not None:
            self.after_cancel(self._timer)
        super().destroy()
