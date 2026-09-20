from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk
from typing import Callable

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

        self.columnconfigure(0, weight=4)
        self.columnconfigure(1, weight=5)
        self.rowconfigure(0, weight=1)

        self._build_hero()
        self.form = ttk.Frame(self, style="Surface.TFrame", padding=(64, 56))
        self.form.grid(row=0, column=1, sticky="nsew")
        self.form.columnconfigure(0, weight=1)
        self._render_form()

    def _build_hero(self) -> None:
        hero = ttk.Frame(self, style="Sidebar.TFrame", padding=(56, 56))
        hero.grid(row=0, column=0, sticky="nsew")
        hero.columnconfigure(0, weight=1)
        hero.rowconfigure(4, weight=1)

        ttk.Label(hero, text="✦", style="LoginHeroTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(hero, text="星原 SIS", style="LoginHeroTitle.TLabel").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Label(hero, text="学生信息系统", style="LoginHeroBody.TLabel").grid(
            row=2, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Label(
            hero,
            text="本地数据 · SQLite · Python",
            style="LoginHeroBody.TLabel",
        ).grid(row=3, column=0, sticky="w", pady=(28, 0))
        ttk.Label(
            hero,
            text="GUI 与终端界面共享同一套业务与数据层。",
            style="LoginHeroBody.TLabel",
            wraplength=300,
            justify="left",
        ).grid(row=5, column=0, sticky="sw")

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
        self._heading("首次使用", "先为 Administrator 设置管理员密码。")
        self._field_label(2, "管理员账号")
        username = ttk.Entry(self.form, textvariable=self.username_var, state="readonly")
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
        self._heading("登录", "使用管理员账号或学生学号进入星原 SIS。")
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

    def _heading(self, title: str, subtitle: str) -> None:
        ttk.Label(self.form, text=title, style="LoginTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
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
        except ValueError as error:
            self._set_status(str(error))
            return
        clear_session()
        self.mode = "login"
        self.username_var.set(ADMIN_USERNAME)
        self._render_form()
        self._set_status("管理员已创建，请登录。", error=False)

    def _submit_login(self) -> None:
        username = self.username_var.get().strip()
        identity = authenticate(self.db_path, username, self.password_var.get())
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
        except ValueError as error:
            self._set_status(str(error))
            return
        self.pending_identity = None
        self._finish(updated)

    def _finish(self, identity: Identity) -> None:
        write_session(identity, self.db_path)
        self.on_success(identity)
