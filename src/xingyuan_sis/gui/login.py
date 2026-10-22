from __future__ import annotations

from pathlib import Path
import tkinter as tk
import sqlite3
from tkinter import ttk
from typing import Callable
from .theme import palette
from .graphics import Brandmark, CampusSeal, px

from ..auth import (
    ADMIN_USERNAME,
    Identity,
    authenticate,
    change_password,
    clear_session,
    has_admin,
    initialize_admin,
    write_session,
)


class LoginView(ttk.Frame):
    """Login and first-run credential setup for the Tkinter frontend."""

    def __init__(
        self,
        master: tk.Misc,
        db_path: Path | str | None,
        *,
        on_success: Callable[[Identity], None],
    ) -> None:
        super().__init__(master, style="App.TFrame")
        self.db_path = db_path
        self.on_success = on_success
        self.mode = "setup" if not has_admin() else "login"
        self.pending_identity: Identity | None = None
        self.status_var = tk.StringVar()
        self.username_var = tk.StringVar(value=ADMIN_USERNAME if self.mode == "setup" else "")
        self.password_var = tk.StringVar()
        self.confirm_var = tk.StringVar()

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # A narrow, consistent brand rail anchors the app; the form has a bounded line length.
        self._build_hero()
        work = ttk.Frame(self, style="Surface.TFrame")
        work.grid(row=0, column=1, sticky="nsew")
        work.columnconfigure(0, weight=1)
        work.columnconfigure(2, weight=1)
        work.rowconfigure(0, weight=1)
        work.rowconfigure(2, weight=1)
        self.form = ttk.Frame(work, style="Surface.TFrame", padding=(0, 24))
        self.form.grid(row=1, column=1, sticky="ew")
        self.form.columnconfigure(0, weight=1)
        def fit_form(event):
            width = min(px(self, 440), max(260, event.width-px(self, 48)))
            work.columnconfigure(1, minsize=width)
            for label in self.form.winfo_children():
                if isinstance(label, ttk.Label):
                    label.configure(wraplength=width)
        work.bind("<Configure>", fit_form)
        self._render_form()

    def _build_hero(self) -> None:
        hero = ttk.Frame(self, style="Rail.TFrame", width=px(self, 360))
        hero.grid(row=0, column=0, sticky="nsew")
        hero.pack_propagate(False)
        Brandmark(hero).pack(anchor="nw", fill="x", padx=24, pady=(24,0))
        CampusSeal(hero).pack(fill="both",expand=True,padx=24,pady=(32,48))
        def fit_hero(event):
            hero.configure(width=min(px(self,360),max(150,event.width//3)))
        self.bind("<Configure>",fit_hero)

    def _render_form(self) -> None:
        for child in self.form.winfo_children():
            child.destroy()
        self.status_var.set("")
        self.password_var.set("")
        self.confirm_var.set("")

        if self.mode == "setup":
            self._render_setup()
        elif self.mode == "forced-password":
            self._render_forced_password()
        else:
            self._render_login()

    def _render_setup(self) -> None:
        self._heading("设置管理员密码")
        self._field_label(2, "管理员账号")
        username = ttk.Entry(
            self.form,
            textvariable=self.username_var,
            state="disabled",
            takefocus=False,
        )
        username.grid(row=3, column=0, sticky="ew", pady=(6, 18))
        self._field_label(4, "设置密码")
        password = ttk.Entry(self.form, textvariable=self.password_var, show="•")
        password.grid(row=5, column=0, sticky="ew", pady=(6, 18))
        self._field_label(6, "确认密码")
        confirm = ttk.Entry(self.form, textvariable=self.confirm_var, show="•")
        confirm.grid(row=7, column=0, sticky="ew", pady=(6, 18))
        confirm.bind("<Return>", lambda _event: self._submit_setup())
        self._status(8)
        ttk.Button(
            self.form,
            text="创建管理员",
            style="Accent.TButton",
            command=self._submit_setup,
        ).grid(row=9, column=0, sticky="ew", pady=(8, 0))
        password.focus_set()

    def _render_login(self) -> None:
        self._heading("登录", "输入管理员账号或学生学号。")
        self._field_label(2, "账号")
        username = ttk.Entry(self.form, textvariable=self.username_var)
        username.grid(row=3, column=0, sticky="ew", pady=(6, 18))
        self._field_label(4, "密码")
        password = ttk.Entry(self.form, textvariable=self.password_var, show="•")
        password.grid(row=5, column=0, sticky="ew", pady=(6, 18))
        password.bind("<Return>", lambda _event: self._submit_login())
        self._status(6)
        ttk.Button(
            self.form,
            text="登录",
            style="Accent.TButton",
            command=self._submit_login,
        ).grid(row=7, column=0, sticky="ew", pady=(8, 0))
        (password if self.username_var.get() else username).focus_set()

    def _render_forced_password(self) -> None:
        self._heading("设置新密码", "首次登录需要修改初始密码后才能继续。")
        self._field_label(2, "新密码")
        password = ttk.Entry(self.form, textvariable=self.password_var, show="•")
        password.grid(row=3, column=0, sticky="ew", pady=(6, 18))
        self._field_label(4, "确认密码")
        confirm = ttk.Entry(self.form, textvariable=self.confirm_var, show="•")
        confirm.grid(row=5, column=0, sticky="ew", pady=(6, 18))
        confirm.bind("<Return>", lambda _event: self._submit_forced_password())
        self._status(6)
        ttk.Button(
            self.form,
            text="保存并进入",
            style="Accent.TButton",
            command=self._submit_forced_password,
        ).grid(row=7, column=0, sticky="ew", pady=(8, 0))
        password.focus_set()

    def _heading(self, title: str, subtitle: str | None = None) -> None:
        ttk.Label(self.form, text=title, style="LoginTitle.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 28) if subtitle is None else 0,
        )
        if subtitle is None:
            return
        ttk.Label(
            self.form,
            text=subtitle,
            style="SurfaceMuted.TLabel",
            wraplength=420,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 28))

    def _field_label(self, row: int, text: str) -> None:
        ttk.Label(self.form, text=text, style="Surface.TLabel").grid(
            row=row, column=0, sticky="w"
        )

    def _status(self, row: int) -> None:
        self.status_label = ttk.Label(
            self.form,
            textvariable=self.status_var,
            style="Error.TLabel",
            wraplength=420,
            justify="left",
        )
        self.status_label.grid(row=row, column=0, sticky="w", pady=(0, 4))

    def _set_status(self, message: str, *, error: bool = True) -> None:
        self.status_var.set(message)
        self.status_label.configure(style="Error.TLabel" if error else "Status.TLabel")

    def _submit_setup(self) -> None:
        password = self.password_var.get()
        if password != self.confirm_var.get():
            self._set_status("两次密码不一致。")
            return
        try:
            initialize_admin(password)
        except (ValueError, OSError, sqlite3.Error) as error:
            self._set_status(str(error))
            return
        clear_session()
        self.mode = "login"
        self.username_var.set(ADMIN_USERNAME)
        self._render_form()
        self._set_status("管理员已创建，请登录。", error=False)

    def _submit_login(self) -> None:
        username = self.username_var.get().strip()
        try:
            identity = authenticate(self.db_path, username, self.password_var.get())
        except (ValueError, OSError, sqlite3.Error) as error:
            self._set_status(str(error))
            return
        if identity is None:
            self.password_var.set("")
            self._set_status("账号或密码错误。")
            return
        if identity.must_change_password:
            self.pending_identity = identity
            self.mode = "forced-password"
            self._render_form()
            return
        self._finish(identity)

    def _submit_forced_password(self) -> None:
        identity = self.pending_identity
        if identity is None:
            self.mode = "login"
            self._render_form()
            return
        password = self.password_var.get()
        if password != self.confirm_var.get():
            self._set_status("两次密码不一致。")
            return
        try:
            updated = change_password(self.db_path, identity, password)
        except (ValueError, OSError, sqlite3.Error) as error:
            self._set_status(str(error))
            return
        self.pending_identity = None
        self._finish(updated)

    def _finish(self, identity: Identity) -> None:
        try:
            write_session(identity, self.db_path)
        except OSError as error:
            self._set_status(str(error))
            return
        self.on_success(identity)
