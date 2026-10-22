"""Native, keyboard-operable reading and editing surfaces."""
from __future__ import annotations
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from .controller import COLLECTIONS, fields, readable_error
from .theme import palette, text_options
from .graphics import px
from .interaction import AutoScrollbar, scroll_view

EXPECTED_ERRORS = (ValueError, PermissionError, sqlite3.Error, OSError)


def form_fields(key):
    """Presentation order only; validation and persistence keep using Schema."""
    source = fields(key)
    if key != "students":
        return source
    order = {name: index for index, name in enumerate((
        "student_no", "name", "gender", "birth_date", "age", "enrollment_year", "class_code", "status",
        "family", "branch", "primary_element", "primary_affinity", "contact", "dormitory", "notes"))}
    return tuple(sorted(source, key=lambda field: order.get(field.key, len(order))))


def place_dialog(dialog, width, height, *, minimum=(400, 280)):
    """Keep a modal task over its parent, constrained to the usable screen."""
    parent = dialog.master.winfo_toplevel()
    width = min(px(dialog, width), max(320, dialog.winfo_screenwidth()-48))
    height = min(px(dialog, height), max(240, dialog.winfo_screenheight()-100))
    x = max(0, min(dialog.winfo_screenwidth()-width, parent.winfo_rootx()+(parent.winfo_width()-width)//2))
    y = max(0, min(dialog.winfo_screenheight()-height-48, parent.winfo_rooty()+(parent.winfo_height()-height)//2))
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    dialog.minsize(min(width, px(dialog, minimum[0])), min(height, px(dialog, minimum[1])))


class ScrollArea(ttk.Frame):
    """A scrollable property grid; focus automatically reveals hidden controls."""
    def __init__(self, parent):
        super().__init__(parent, style="Surface.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background=palette(parent).surface, highlightthickness=0, width=1, height=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.wheel_view = lambda: self.canvas
        bar = AutoScrollbar(self, viewport=self.canvas, orient="vertical", command=self.canvas.yview)
        self.scrollbar = bar
        bar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=bar.set)
        self.body = ttk.Frame(self.canvas, style="Surface.TFrame", padding=12)
        self.window = self.canvas.create_window(0, 0, anchor="nw", window=self.body)
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.canvas.bind("<MouseWheel>", self.wheel)

    def watch(self, control):
        control.bind("<FocusIn>", self.reveal, add="+")
        control.bind("<MouseWheel>", self.wheel, add="+")

    def wheel(self, event):
        return scroll_view(self.canvas, event)

    def reveal(self, event):
        top = event.widget.winfo_rooty() - self.body.winfo_rooty()
        visible = self.canvas.canvasy(0)
        if top < visible or top + event.widget.winfo_height() > visible+self.canvas.winfo_height():
            self.canvas.yview_moveto(max(0, top-12)/max(1, self.body.winfo_height()))


class ReadonlyParagraph(tk.Text):
    """Copyable field value that wraps and grows inside its parent's scroll area."""
    def __init__(self, parent, content):
        options = text_options(parent)
        options.update(padx=4, pady=4, borderwidth=0, highlightthickness=0)
        super().__init__(parent, width=1, height=1, wrap="word", takefocus=True, **options)
        self.insert("1.0", content)
        self.configure(state="disabled")
        self.bind("<Configure>", self._fit)
        self.bind("<Map>", self._fit)
        self.bind("<Tab>", lambda e: self._traverse(False))
        self.bind("<Shift-Tab>", lambda e: self._traverse(True))

    def _fit(self, event=None):
        # -update makes Tk recompute wrapped lines after a width change. The
        # containing ScrollArea owns scrolling; this Text never has a hidden tail.
        lines = max(1, int(self.tk.call(self._w, "count", "-update", "-displaylines", "1.0", "end")))
        if int(self.cget("height")) != lines:
            self.configure(height=lines)

    def _traverse(self, backwards):
        target = self.tk_focusPrev() if backwards else self.tk_focusNext()
        if target:
            target.focus_set()
        return "break"


def reading_text(parent, content="", **kwargs):
    frame = ttk.Frame(parent, style="Surface.TFrame")
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    text = tk.Text(frame, wrap="word", width=1, height=1, **text_options(parent), **kwargs)
    bar = AutoScrollbar(frame, viewport=text, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=bar.set)
    text.grid(row=0, column=0, sticky="nsew")
    bar.grid(row=0, column=1, sticky="ns")
    text.insert("1.0", content)
    text.configure(state="disabled")
    return frame, text


class ResultDialog(tk.Toplevel):
    def __init__(self, parent, title, content):
        super().__init__(parent)
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.configure(background=palette(parent).background)
        place_dialog(self, 660, 440)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        # The native window caption already identifies this result; body starts at the reading margin.
        frame, self.text = reading_text(self, content)
        frame.grid(row=0, column=0, sticky="nsew", padx=24, pady=(24, 0))
        ttk.Button(self, text="关闭", command=self.destroy).grid(row=1, column=0, sticky="e", padx=24, pady=16)
        self.bind("<Escape>", lambda e: self.destroy())
        self.text.focus_set()


class RecordDialog(tk.Toplevel):
    def __init__(self, parent, controller, key, original=None, on_saved=None):
        super().__init__(parent)
        self.controller, self.key, self.original = controller, key, original
        self.on_saved = on_saved or (lambda values: None)
        self.vars, self.controls, self.mappings, self.multiline = {}, {}, {}, {}
        self.title(("编辑" if original else "新增") + COLLECTIONS[key].singular)
        self.transient(parent.winfo_toplevel())
        self.configure(background=palette(parent).background)
        place_dialog(self, 620, 720, minimum=(460, 360))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        # The caption carries the task name. Label/control pairs begin at one shared left edge.
        area = ttk.Frame(self)
        area.grid(row=0, column=0, sticky="nsew", padx=24, pady=(24, 0))
        area.columnconfigure(0, weight=1)
        area.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(area, background=palette(parent).background, highlightthickness=0, width=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.wheel_view = lambda: self.canvas
        bar = AutoScrollbar(area, viewport=self.canvas, orient="vertical", command=self.canvas.yview)
        bar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=bar.set)
        self.form = ttk.Frame(self.canvas, padding=(0, 0, 16, 8))
        self.form.columnconfigure(1, weight=1)
        self.window_id = self.canvas.create_window(0, 0, anchor="nw", window=self.form)
        self.form.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window_id, width=e.width))
        values = dict(original or {})
        if key == "branches" and original:
            values["family"] = original["family_name"]
        for row, field in enumerate(form_fields(key)):
            name = field.key
            label = field.label + (" *" if field.required else "")
            # Proximity groups identity, enrollment, species, and living data without extra headings.
            gap = 16 if key == "students" and name in {"enrollment_year", "family", "contact"} else 0
            ttk.Label(self.form, text=label, style="Body.TLabel").grid(row=row*2, column=0, sticky="nw", pady=(gap+8, 14), padx=(0, 18))
            value = values.get(name, field.default)
            variable = tk.StringVar(self, value="" if value is None else str(value))
            self.vars[name] = variable
            options = None if (key == "students" and name == "student_no") else controller.choices(name, values)
            if name in ("body", "notes"):
                control = tk.Text(self.form, height=5 if name == "body" else 3, width=20, wrap="word", undo=True, **text_options(self))
                control.insert("1.0", variable.get())
                p = palette(self)
                control.bind("<FocusIn>", lambda e, p=p: e.widget.configure(
                    background=p.selection, foreground=p.selected_text, insertbackground=p.selected_text,
                    selectbackground=p.surface, selectforeground=p.text))
                control.bind("<FocusOut>", lambda e, p=p: e.widget.configure(
                    background=p.surface, foreground=p.text, insertbackground=p.text,
                    selectbackground=p.selection, selectforeground=p.selected_text))
                self.multiline[name] = control
            elif options is not None:
                control = ttk.Combobox(self.form, textvariable=variable, state="readonly", width=20)
                self.controls[name] = control
                self._set_choices(name, options, value)
            elif name in ("status", "gender", "primary_element", "primary_affinity"):
                suggestions = {"status": ("在读", "休学", "毕业", "退学"), "gender": ("男", "女", "其他", "未说明"),
                    "primary_element": ("风", "火", "水", "土", "光", "暗"), "primary_affinity": ("S", "A", "B", "C", "D")}
                control = ttk.Combobox(self.form, textvariable=variable, values=suggestions[name], width=20)
            else:
                control = ttk.Entry(self.form, textvariable=variable, width=20)
            self.controls[name] = control
            control.grid(row=row*2, column=1, sticky="ew", pady=(gap, 14))
            if original and not field.editable:
                control.configure(state="disabled")
            control.bind("<FocusIn>", self._reveal, add="+")
        if "family" in self.vars and "branch" in self.controls:
            self.controls["family"].bind("<<ComboboxSelected>>", self._family_changed)
        if "birth_date" in self.vars:
            ttk.Label(self.form, text="生日：YYYY-MM-DD、YYYY 或 --MM-DD；* 为必填。", style="Muted.TLabel", wraplength=370).grid(
                row=len(fields(key))*2, column=0, columnspan=2, sticky="w")
        self.error = tk.StringVar(self)
        error_label = ttk.Label(self, textvariable=self.error, style="FormError.TLabel", wraplength=540)
        error_label.grid(row=1, column=0, sticky="ew", padx=24, pady=(8, 0))
        self.bind("<Configure>", lambda e: error_label.configure(wraplength=max(240, e.width-48)) if e.widget is self else None)
        footer = ttk.Frame(self, padding=(24, 12))
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Label(footer, text="Ctrl+S 保存 · Esc 取消", style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="取消", command=self.cancel).pack(side="right")
        ttk.Button(footer, text="保存", style="Accent.TButton", command=self.save).pack(side="right", padx=8)
        self.initial = self.values()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda e: self.cancel())
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<MouseWheel>", self._wheel)
        self.update_idletasks()
        self.grab_set()
        next((c for c in self.controls.values() if str(c.cget("state")) != "disabled"), self).focus_set()

    def _set_choices(self, name, options, value):
        mapping = {label: code for code, label in options}
        field = next(f for f in fields(self.key) if f.key == name)
        if not field.required:
            mapping = {"未指定": "", **mapping}
        self.mappings[name] = mapping
        self.controls[name].configure(values=tuple(mapping))
        label = next((label for label, code in mapping.items() if code == value), None)
        self.vars[name].set(label if label is not None else (str(value) if value else ""))

    def values(self):
        values = {k: self.mappings.get(k, {}).get(v.get(), v.get()) for k, v in self.vars.items()}
        values.update({k: text.get("1.0", "end-1c") for k, text in self.multiline.items()})
        return values

    def _family_changed(self, event=None):
        current = self.values()
        options = self.controller.choices("branch", current)
        value = current["branch"] if current["branch"] in {v for v, _ in options} else ""
        self._set_choices("branch", options, value)

    def _reveal(self, event):
        self.update_idletasks()
        widget = event.widget
        top = widget.winfo_y()
        visible_top = self.canvas.canvasy(0)
        visible_bottom = visible_top + self.canvas.winfo_height()
        if top < visible_top or top + widget.winfo_height() > visible_bottom:
            self.canvas.yview_moveto(max(0, top-24)/max(1, self.form.winfo_height()))

    def _wheel(self, event):
        if isinstance(event.widget, tk.Text):
            return
        return scroll_view(self.canvas, event)

    def save(self):
        try:
            values = {f.key: f.parse(self.values()[f.key]) for f in fields(self.key)}
            result = self.controller.save(self.key, values, self.original)
        except EXPECTED_ERRORS as error:
            self.error.set("无法保存：" + readable_error(error))
            return
        self.destroy()
        self.on_saved(values)
        if result:
            ResultDialog(self.master, "学生账号已创建", result)

    def cancel(self):
        if self.values() != self.initial and not messagebox.askyesno("放弃修改", "当前草稿尚未保存，是否放弃？", parent=self):
            return
        self.destroy()


class PasswordDialog(tk.Toplevel):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.title("修改密码")
        self.transient(parent.winfo_toplevel())
        self.configure(background=palette(parent).background)
        self.columnconfigure(0, weight=1)
        self.password, self.confirm, self.error = (tk.StringVar(self) for _ in range(3))
        controls = []
        for row, (label, var) in enumerate((("新密码", self.password), ("确认密码", self.confirm))):
            ttk.Label(self, text=label, style="Body.TLabel").grid(row=row*2, column=0, sticky="w", padx=24, pady=(16, 4))
            entry = ttk.Entry(self, textvariable=var, show="•", width=32)
            entry.grid(row=row*2+1, column=0, sticky="ew", padx=24)
            controls.append(entry)
        ttk.Label(self, textvariable=self.error, style="FormError.TLabel", wraplength=340).grid(row=4, column=0, padx=24, pady=12)
        ttk.Button(self, text="保存新密码", command=self.save, style="Accent.TButton").grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 24))
        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())
        place_dialog(self, 460, 320)
        self.grab_set()
        controls[0].focus_set()

    def save(self):
        if self.password.get() != self.confirm.get():
            self.error.set("两次密码不一致。")
            return
        try:
            self.controller.change_password(self.password.get())
        except EXPECTED_ERRORS as error:
            self.error.set(readable_error(error))
            return
        parent = self.master
        self.destroy()
        messagebox.showinfo("密码已修改", "下次登录请使用新密码。", parent=parent)
