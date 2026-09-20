from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from ..auth import Identity, clear_session
from ..service import XingyuanService


_ADMIN_NAV = (
    ("overview", "概览"),
    ("students", "学生"),
    ("departments", "学院"),
    ("majors", "专业"),
    ("classes", "班级"),
    ("courses", "课程"),
    ("grades", "成绩"),
    ("data", "数据"),
    ("announcements", "公告"),
)
_STUDENT_NAV = (
    ("overview", "概览"),
    ("students", "学生查询"),
    ("announcements", "班级公告"),
    ("profile", "个人中心"),
)


class MainWindow(ttk.Frame):
    """Modern Tkinter shell; feature pages are mounted into the content area."""

    def __init__(
        self,
        master: tk.Misc,
        db_path: Path | str | None,
        identity: Identity,
        *,
        on_logout: Callable[[], None],
    ) -> None:
        super().__init__(master, style="App.TFrame")
        self.db_path = db_path
        self.identity = identity
        self.on_logout = on_logout
        self.service = XingyuanService(db_path)
        self.current_page = "overview"
        self.nav_buttons: dict[str, ttk.Button] = {}

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._install_menu()
        self._build_sidebar()
        self._build_content()
        self.show_page("overview")

    @property
    def navigation(self) -> tuple[tuple[str, str], ...]:
        return _ADMIN_NAV if self.identity.is_admin else _STUDENT_NAV

    def _install_menu(self) -> None:
        root = self.winfo_toplevel()
        menubar = tk.Menu(root)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="退出登录", command=self._logout)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=root.destroy)
        menubar.add_cascade(label="文件", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="关于星原 SIS", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        root.configure(menu=menubar)

    def _build_sidebar(self) -> None:
        sidebar = ttk.Frame(self, style="Sidebar.TFrame", padding=(18, 22))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(len(self.navigation) + 2, weight=1)

        ttk.Label(sidebar, text="✦ 星原 SIS", style="SidebarTitle.TLabel").grid(
            row=0, column=0, sticky="w", padx=6, pady=(0, 24)
        )
        for row, (key, label) in enumerate(self.navigation, start=1):
            button = ttk.Button(
                sidebar,
                text=label,
                style="Sidebar.TButton",
                command=lambda page=key: self.show_page(page),
            )
            button.grid(row=row, column=0, sticky="ew", pady=2)
            self.nav_buttons[key] = button

        role = "管理员" if self.identity.is_admin else "学生"
        user_text = (
            self.identity.username
            if self.identity.is_admin
            else (self.identity.student_no or self.identity.username)
        )
        footer_row = len(self.navigation) + 3
        ttk.Label(sidebar, text=role, style="SidebarMuted.TLabel").grid(
            row=footer_row, column=0, sticky="w", padx=6, pady=(16, 2)
        )
        ttk.Label(sidebar, text=user_text, style="SidebarMuted.TLabel").grid(
            row=footer_row + 1, column=0, sticky="w", padx=6
        )

    def _build_content(self) -> None:
        self.content = ttk.Frame(self, style="App.TFrame", padding=(34, 28))
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(1, weight=1)

    def show_page(self, key: str) -> None:
        labels = dict(self.navigation)
        if key not in labels:
            return
        self.current_page = key
        for page, button in self.nav_buttons.items():
            button.configure(
                style="SidebarSelected.TButton" if page == key else "Sidebar.TButton"
            )
        for child in self.content.winfo_children():
            child.destroy()
        if key == "overview":
            self._show_overview()
        else:
            self._show_placeholder(labels[key])

    def _show_overview(self) -> None:
        ttk.Label(self.content, text="概览", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        body = ttk.Frame(self.content, style="App.TFrame")
        body.grid(row=1, column=0, sticky="nsew", pady=(28, 0))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        counts = (
            ("学生", len(self.service.list_students())),
            ("班级", len(self.service.list_classes())),
            ("课程", len(self.service.list_courses())),
            (
                "公告",
                len(
                    self.service.list_announcements(
                        self.identity.student_no if self.identity.is_student else None
                    )
                ),
            ),
        )
        for index, (label, value) in enumerate(counts):
            row, column = divmod(index, 2)
            card = ttk.Frame(body, style="Card.TFrame", padding=(22, 18))
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=(0, 10) if column == 0 else (10, 0),
                pady=(0, 20),
            )
            ttk.Label(card, text=str(value), style="CardValue.TLabel").pack(anchor="w")
            ttk.Label(card, text=label, style="CardLabel.TLabel").pack(
                anchor="w", pady=(6, 0)
            )

        ttk.Label(
            body,
            text="Tkinter GUI 已连接现有 Service / Repository / SQLite 主链。",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _show_placeholder(self, title: str) -> None:
        ttk.Label(self.content, text=title, style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        panel = ttk.Frame(self.content, style="Card.TFrame", padding=(24, 22))
        panel.grid(row=1, column=0, sticky="new", pady=(28, 0))
        panel.columnconfigure(0, weight=1)
        ttk.Label(
            panel,
            text=f"{title}页面",
            style="Surface.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            panel,
            text="GUI 主框架已就绪。下一阶段在这里接入现有业务能力，不复制 Service 规则。",
            style="SurfaceMuted.TLabel",
            wraplength=620,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _logout(self) -> None:
        clear_session()
        self.on_logout()

    def _show_about(self) -> None:
        messagebox.showinfo(
            "关于星原 SIS",
            "星原 SIS\nPython + Tkinter/ttk + SQLite\n\nGUI、TUI、Basic UI 与 CLI 共享业务层。",
            parent=self.winfo_toplevel(),
        )
