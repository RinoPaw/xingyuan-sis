"""The campus book: native menus, chapter navigation and live record inspectors."""
from __future__ import annotations
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from ..auth import clear_session
from ..schema import age_from_birth_date
from .controller import CampusController, COLLECTIONS, fields, readable_error, record_key
from .theme import configure_styles, palette
from .widgets import EXPECTED_ERRORS, PasswordDialog, RecordDialog, ResultDialog, ScrollArea, ReadonlyParagraph, reading_text
from .graphics import Brandmark, CutNavigation, RecordBanner, ChapterHeading, CampusSeal, ScoreSlip, NoticeHeading, px
from .interaction import AutoScrollbar

ADMIN_NAV = (("overview", "校园"), ("students", "学生名册"), ("academics", "学院与班级"),
    ("courses", "课程目录"), ("grades", "选课与成绩"), ("announcements", "班级公告"), ("data", "数据交换"))
STUDENT_NAV = (("overview", "校园"), ("students", "学生名册"), ("announcements", "班级公告"), ("profile", "我的档案"))
ACADEMICS = ("departments", "majors", "classes", "families", "branches")
DELETE_IMPACT = {"students": "此学生的选课、成绩和登录账号将一并删除。",
    "courses": "此课程的所有选课和成绩将一并删除。", "classes": "学生将变为未分班；该班公告将一并删除。",
    "departments": "若仍有关联专业，将无法删除；课程的学院关联将清空。",
    "majors": "若仍有关联班级，将无法删除。", "families": "仍被支系或学生引用时无法删除。",
    "branches": "仍被学生引用时无法删除。", "grades": "将删除此选课及其成绩。", "announcements": "班内学生将无法再阅读此公告。"}


class MainWindow(ttk.Frame):
    def __init__(self, master, db_path, identity, *, on_logout):
        super().__init__(master, style="Stage.TFrame")
        self.controller = CampusController(db_path, identity)
        self.identity, self.on_logout = identity, on_logout
        self.current_page, self.collection = "overview", None
        self.wheel_view = lambda: self.tree if self.collection is not None else None
        self.academic_key = "departments"
        self.search = tk.StringVar(self)
        self.status = tk.StringVar(self, value="校园档案已就绪")
        self.row_map, self.bindings, self.nav_buttons = {}, {}, {}
        self.sort_key, self.sort_reverse = None, False
        self.selected_key = None
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_header()
        # One page heading sits directly above its controls; the rail owns branding.
        self.content = ttk.Frame(self, style="Stage.TFrame", padding=(12, 12, 20, 12))
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(3, weight=1)
        footer = ttk.Frame(self, style="Stage.TFrame", padding=(16, 8))
        footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        status_label = ttk.Label(footer, textvariable=self.status, style="StageMeta.TLabel", wraplength=800)
        status_label.pack(anchor="w", fill="x")
        footer.bind("<Configure>", lambda e: status_label.configure(wraplength=max(240, e.width-32)))
        self._install_menu()
        actions = {"<Control-f>": self.focus_search, "<Control-n>": self.new_record,
            "<Control-e>": self.edit_record, "<F5>": self.refresh}
        for index, (page, _) in enumerate(self.navigation, 1):
            actions[f"<Control-Key-{index}>"] = lambda p=page: self.show_page(p)
        for sequence, action in actions.items():
            self.bindings[sequence] = self.winfo_toplevel().bind(sequence, self._event(action), add="+")
        self.show_page("overview")

    @property
    def navigation(self):
        return ADMIN_NAV if self.identity.is_admin else STUDENT_NAV

    def _event(self, action):
        def callback(event):
            if event.widget.winfo_toplevel() is self.winfo_toplevel():
                action()
            return "break"
        return callback

    def _build_header(self):
        self.sidebar = ttk.Frame(self, style="Rail.TFrame")
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.rowconfigure(1, weight=1)
        Brandmark(self.sidebar).grid(row=0, column=0, sticky="ew")
        rail = ScrollArea(self.sidebar)
        self.nav_rail = rail
        rail.configure(style="Rail.TFrame")
        rail.scrollbar.configure(style="Rail.Vertical.TScrollbar")
        rail.grid(row=1, column=0, sticky="ns")
        rail.canvas.configure(background=palette(self).rail, width=px(self, 222))
        nav = rail.body
        nav.configure(style="Rail.TFrame", padding=(4, 0))
        for index, (key, label) in enumerate(self.navigation, 1):
            button = CutNavigation(nav, index, label, lambda k=key: self.show_page(k))
            button.pack(fill="x", pady=(0, 2))
            rail.watch(button.button)
            self.nav_buttons[key] = button
        # Identity stays below navigation; profile is already in the student rail.
        ttk.Label(self.sidebar, text="管理员" if self.identity.is_admin else self.identity.username,
            style="RailMuted.TLabel", justify="left").grid(row=2, column=0, sticky="w", padx=20, pady=20)

    def _install_menu(self):
        root, p = self.winfo_toplevel(), palette(self)
        if hasattr(self, "menubar") and self.menubar.winfo_exists():
            self.menubar.destroy()
        self.menubar = tk.Menu(root, tearoff=False)
        def menu(label):
            result = tk.Menu(self.menubar, tearoff=False, background=p.surface, foreground=p.text,
                activebackground=p.selection, activeforeground=p.selected_text,
                disabledforeground=p.disabled_text, selectcolor=p.text)
            self.menubar.add_cascade(label=label, menu=result)
            return result
        file = menu("文件(F)")
        file.add_command(label="导入学生 CSV…", command=self.import_csv, state="normal" if self.identity.is_admin else "disabled")
        file.add_command(label="导出学生 CSV…", command=self.export_csv, state="normal" if self.identity.is_admin else "disabled")
        file.add_separator()
        file.add_command(label="退出登录", command=self._logout)
        file.add_command(label="退出", command=root.destroy)
        self.record_menu = menu("记录(R)")
        self.record_menu.add_command(label="新增…", accelerator="Ctrl+N", command=self.new_record)
        self.record_menu.add_command(label="编辑…", accelerator="Ctrl+E", command=self.edit_record)
        self.record_menu.add_command(label="删除…", command=self.delete_record)
        self.record_menu.add_command(label="重置学生密码…", command=self.reset_password)
        go = menu("前往(G)")
        for index, (key, label) in enumerate(self.navigation, 1):
            go.add_command(label=label, accelerator=f"Ctrl+{index}", command=lambda k=key: self.show_page(k))
        view = menu("查看(V)")
        view.add_command(label="搜索", accelerator="Ctrl+F", command=self.focus_search)
        view.add_command(label="刷新", accelerator="F5", command=self.refresh)
        view.add_separator()
        self.theme_var = tk.StringVar(self, value=getattr(root, "campus_theme", "rebel"))
        for name, label in (("rebel", "浅色"), ("afterhours", "深色")):
            view.add_radiobutton(label=label, variable=self.theme_var, value=name, command=self.change_theme)
        view.add_separator()
        self.zoom_var = tk.DoubleVar(self, value=getattr(root, "campus_zoom", 1.0))
        for zoom in (1.0, 1.25, 1.5):
            view.add_radiobutton(label=f"字号 {zoom:.0%}", variable=self.zoom_var, value=zoom, command=self.change_theme)
        account = menu("账户(A)")
        account.add_command(label="修改密码…", command=lambda: PasswordDialog(self, self.controller))
        help_menu = menu("帮助(H)")
        help_menu.add_command(label="操作手册", command=lambda: ResultDialog(self, "操作手册",
            "选择章节后搜索并选择记录，在右侧阅读资料。表格列标题可排序，分隔线可拖动。\n\n"
            "Ctrl+F 搜索；Ctrl+N 新建；Ctrl+E 编辑；F5 刷新；Ctrl+数字切换章节。\n表格聚焦时 Delete 删除。窄窗口用列表与资料页签切换阅读。\n"
            "表单使用 Tab / Shift+Tab 移动，Ctrl+S 保存，Escape 取消。\n\n"
            "查看菜单提供昼夜主题和字号。学生只能修改自己的密码。\n\n"
            "数据交换可导入 CSV，逐行报告失败与新账号。示例数据只可写入空库。\n"
            "学院、族系等关联资料需要先创建，再新增学生。"))
        help_menu.add_command(label="关于星原", command=lambda: ResultDialog(self, "关于星原",
            "星原 SiS\n\n学生信息、课程、成绩与班级公告。"))
        root.configure(menu=self.menubar)

    def _update_actions(self):
        admin = self.identity.is_admin and self.collection is not None
        selected = self.current_record() is not None
        states = (admin, admin and selected and self.collection != "announcements", admin and selected,
            admin and selected and self.collection == "students")
        for i, enabled in enumerate(states):
            self.record_menu.entryconfigure(i, state="normal" if enabled else "disabled")
        for name, button in getattr(self, "record_buttons", {}).items():
            enabled = {"edit": states[1], "delete": states[2], "reset": states[3]}[name]
            button.state(["!disabled"] if enabled else ["disabled"])

    def show_page(self, key):
        if key not in dict(self.navigation) and key != "profile":
            return
        if not self.controller.allow_page(key):
            return
        self.current_page, self.collection = key, None
        self.status.set("")
        self.row_map, self.record_buttons = {}, {}
        self.search.set("")
        self.sort_key, self.sort_reverse, self.selected_key = None, False, None
        for page, button in self.nav_buttons.items():
            button.set_selected(page == key)
        for child in self.content.winfo_children():
            child.destroy()
        if key == "overview":
            self._show_overview()
        elif key == "data":
            self._show_data()
        elif key == "profile":
            self._show_profile()
        else:
            if key == "academics":
                key = self.academic_key
            self._show_collection(key)
        self._update_actions()

    def _academic_page(self, key):
        if key not in ACADEMICS:
            return
        if self.current_page == "academics" and self.collection == key:
            return
        self.academic_key = key
        if self.current_page != "academics":
            self.show_page("academics")
            return
        # These categories share one layout. Keep the heading, tabs, query and
        # panes mapped; replacing the entire page exposed a blank red frame.
        self.collection = key
        self.search.set("")
        self.sort_key, self.sort_reverse, self.selected_key = None, False, None
        for subkey, button in self.academic_buttons.items():
            button.configure(style="TabSelected.TButton" if subkey == key else "StageNav.TButton")
        if self.identity.is_admin:
            self.new_button.configure(text="新增" + COLLECTIONS[key].singular + "…")
        self._configure_columns(key)
        self.reload_rows()
        self._update_actions()

    def _configure_columns(self, key):
        self.tree.configure(columns=[c[0] for c in COLLECTIONS[key].columns])
        for name, label, width in COLLECTIONS[key].columns:
            self.tree.heading(name, text=label + " ↕", command=lambda n=name: self.sort(n))
            self.tree.column(name, width=px(self, width), minwidth=px(self, 70), stretch=True,
                anchor="e" if name in {"credits", "hours", "score", "enrollment_year"} else "w")

    def _heading(self, title, subtitle, row=0):
        frame = ChapterHeading(self.content, title)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        if subtitle:
            caption = ttk.Label(frame, text=subtitle, style="StageMeta.TLabel")
            caption.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
            frame.bind("<Configure>", lambda e: caption.configure(wraplength=max(180,e.width-12)))
        return frame

    def _show_overview(self):
        students = self.controller.rows("students")
        families = len({row["family"] for row in students})
        self._heading("校园", "")
        tools = ttk.Frame(self.content, style="Stage.TFrame")
        tools.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        ttk.Button(tools, text="学生名册", command=lambda: self.show_page("students")).pack(side="left")
        ttk.Button(tools, text="全部公告", command=lambda: self.show_page("announcements")).pack(side="left", padx=8)
        if self.identity.is_admin:
            def publish():
                self.show_page("announcements")
                self.new_record()
            ttk.Button(tools, text="发布公告…", style="Accent.TButton", command=publish).pack(side="right")
            if not students:
                ttk.Button(tools, text="载入示例数据…", command=self.seed_demo).pack(side="left", padx=8)
        # Announcements are the page content; counts above are factual context, not a hero.
        notices = self.controller.rows("announcements")
        spread = ttk.Frame(self.content, style="Stage.TFrame")
        spread.grid(row=3,column=0,sticky="nsew")
        spread.columnconfigure(0,weight=3);spread.columnconfigure(1,weight=4)
        spread.rowconfigure(0,weight=1)
        seal = CampusSeal(spread)
        seal.grid(row=0,column=0,sticky="nsew",padx=(0,16))
        body = ttk.Frame(spread, style="Surface.TFrame", padding=24)
        body.grid(row=0,column=1,sticky="nsew")
        def adapt_spread(event):
            if event.width < px(self,680): seal.grid_remove();spread.columnconfigure(0,weight=0)
            else: seal.grid();spread.columnconfigure(0,weight=3)
        spread.bind("<Configure>",adapt_spread)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)
        ttk.Label(body, text="近期公告", style="NoticeTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 12))
        content = "\n\n".join(f"{r['title']}\n{r['class_name']} · {r['created_at']}\n\n{r['body']}" for r in notices[:3]) or "暂无公告。"
        frame, _ = reading_text(body, content)
        frame.grid(row=1, column=0, sticky="nsew")
        self.status.set(f"学生 {len(students)} 人 · 族系 {families} 类")

    def _show_collection(self, key):
        self.collection = key
        title = COLLECTIONS[key].title
        subtitle = ""
        title = "学院与班级" if self.current_page == "academics" else title
        heading = self._heading(title, subtitle)
        if self.identity.is_admin:
            self.new_button = ttk.Button(heading, text="新增" + COLLECTIONS[key].singular + "…", command=self.new_record, style="Accent.TButton")
            self.new_button.grid(row=0, column=2, sticky="e", padx=(8, 0))
        if self.current_page == "academics":
            # Title → subcategory → query → table also follows keyboard construction order.
            tabs = ttk.Frame(self.content, style="Stage.TFrame")
            tabs.grid(row=1, column=0, sticky="ew", pady=(0, 12))
            self.academic_buttons = {}
            for subkey in ACADEMICS:
                button = ttk.Button(tabs, text=COLLECTIONS[subkey].title,
                    style="TabSelected.TButton" if subkey == self.academic_key else "StageNav.TButton",
                    command=lambda k=subkey: self._academic_page(k))
                button.pack(side="left", padx=(0, 6))
                self.academic_buttons[subkey] = button
        tools = ttk.Frame(self.content, style="Stage.TFrame")
        tools.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        tools.columnconfigure(1, weight=1)
        ttk.Label(tools, text="搜索", style="StageMeta.TLabel").grid(row=0, column=0, padx=(0, 8))
        self.search_entry = ttk.Entry(tools, textvariable=self.search, width=22)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_entry.bind("<KeyRelease>", lambda e: self.reload_rows())
        self.search_entry.bind("<Escape>", lambda e: self.clear_search())
        self.filter_vars, self.filter_maps = {}, {}
        if key == "students":
            s = self.controller.service
            choices = (("college_codes", "全部学院", [(r["code"], r["name"]) for r in s.list_departments()]),
                ("class_codes", "全部班级", [(r["code"], r["name"]) for r in s.list_classes()]),
                ("statuses", "全部学籍", [(v, v) for v in sorted({r['status'] for r in s.list_students()})]))
            filter_controls = []
            for column, (filter_key, label, options) in enumerate(choices, 2):
                mapping = {label: "", **{f"{name} · {code}" if name != code else name: code for code, name in options}}
                variable = tk.StringVar(self, value=label)
                self.filter_vars[filter_key], self.filter_maps[filter_key] = variable, mapping
                combo = ttk.Combobox(tools, textvariable=variable, values=tuple(mapping), state="readonly", width=13)
                combo.grid(row=0, column=column, padx=(8, 0))
                combo.bind("<<ComboboxSelected>>", lambda e: self.reload_rows())
                filter_controls.append(combo)
            wrapped = [None]
            # Measure the expanded row once. Measuring the narrowed controls
            # again would make intermediate widths oscillate between two rows.
            required = self.search_entry.winfo_reqwidth() + sum(c.winfo_reqwidth()+8 for c in filter_controls) + 48
            def wrap_filters(event):
                wrap = event.width < required
                if wrapped[0] == wrap:
                    return
                wrapped[0] = wrap
                self.search_entry.grid_configure(columnspan=3 if wrap else 1)
                for index, control in enumerate(filter_controls):
                    control.configure(width=10 if wrap else 13)
                    control.grid_configure(row=1 if wrap else 0, column=index+1 if wrap else index+2,
                        pady=(8, 0) if wrap else 0)
            tools.bind("<Configure>", wrap_filters)
        workspace = ttk.Frame(self.content, style="Stage.TFrame")
        workspace.grid(row=3, column=0, sticky="nsew")
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(0, weight=1)
        panes = ttk.Panedwindow(workspace, orient="vertical" if key == "grades" else "horizontal", style="Stage.TPanedwindow")
        panes.grid(row=0, column=0, sticky="nsew")
        # Sibling frames can be managed by either container without recreating
        # the table, selection, column widths or detail fields on every resize.
        self.compact_tabs = ttk.Notebook(workspace)
        table = ttk.Frame(workspace, style="Ink.TFrame")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table, style="Roster.Treeview", columns=[c[0] for c in COLLECTIONS[key].columns], show="headings", selectmode="browse")
        self._configure_columns(key)
        self.tree.grid(row=0, column=0, sticky="nsew")
        # Fit the initial column proportions to the reading space, while allowing
        # manual resizing until the window/pane itself changes size again.
        last_fit = [None]
        def fit_columns(event):
            # A pane can receive several Configure events at the same width.
            # Avoid reassigning every Treeview column and restarting geometry.
            signature = (self.collection, event.width)
            if last_fit[0] == signature:
                return
            last_fit[0] = signature
            columns = [c for c in COLLECTIONS[self.collection].columns if self.collection != "announcements" or c[0] == "title"]
            available = max(1, event.width - 4)
            minimum = px(self, 70)
            total = sum(c[2] for c in columns)
            for name, _, width in columns:
                self.tree.column(name, width=max(minimum, int(available * width / total)))
        self.tree.bind("<Configure>", fit_columns)
        for orientation, row, column, sticky in (("vertical", 0, 1, "ns"), ("horizontal", 1, 0, "ew")):
            bar = AutoScrollbar(table, viewport=self.tree, orient=orientation, style=f"Ink.{orientation.title()}.TScrollbar",
                command=self.tree.yview if orientation == "vertical" else self.tree.xview)
            bar.grid(row=row, column=column, sticky=sticky)
            self.tree.configure(**{"yscrollcommand" if orientation == "vertical" else "xscrollcommand": bar.set})
        self.inspector = ttk.Frame(workspace, style="Surface.TFrame", padding=16,
            width=px(self,560 if key == "announcements" else 390), height=px(self,200))
        if key == "announcements":
            self.tree.configure(displaycolumns=("title",))
        table.configure(width=px(self,280 if key == "announcements" else 510))
        table.grid_propagate(False)
        self.inspector.grid_propagate(False)
        self.inspector.columnconfigure(0, weight=1)
        self.inspector.rowconfigure(2, weight=1)
        if key == "grades":
            panes.add(self.inspector,weight=0);panes.add(table,weight=1)
        else:
            panes.add(table,weight=1 if key == "announcements" else 3)
            panes.add(self.inspector,weight=3 if key == "announcements" else 2)
        self.compact_inspector = False
        query_hidden = [False]
        def adapt_query(event=None):
            hidden = self.compact_inspector and self.compact_tabs.select() == str(self.inspector)
            if hidden == query_hidden[0]:
                return
            query_hidden[0] = hidden
            if hidden:
                tools.grid_remove()
            else:
                tools.grid()
        self.compact_tabs.bind("<<NotebookTabChanged>>", adapt_query)
        def adapt(event):
            # Hiding search on the reading tab frees room for fields. Decide
            # compactness against the list's height to avoid a layout cycle.
            list_height = event.height - (tools.winfo_reqheight()+12 if query_hidden[0] else 0)
            compact = event.width < px(self, 760) or list_height < px(self, 430)
            if compact == self.compact_inspector:
                return
            self.compact_inspector = compact
            if compact:
                panes.forget(table)
                panes.forget(self.inspector)
                panes.grid_remove()
                self.compact_tabs.add(table, text="列表")
                self.compact_tabs.add(self.inspector, text="资料")
                self.compact_tabs.grid(row=0, column=0, sticky="nsew")
            else:
                self.compact_tabs.forget(table)
                self.compact_tabs.forget(self.inspector)
                self.compact_tabs.grid_remove()
                if key == "grades":
                    panes.add(self.inspector,weight=0);panes.add(table,weight=1)
                else:
                    panes.add(table,weight=1 if key == "announcements" else 3)
                    panes.add(self.inspector,weight=3 if key == "announcements" else 2)
                panes.grid()
            adapt_query()
            self.inspect()
        workspace.bind("<Configure>", adapt)
        self.tree.tag_configure("alternate", background=palette(self).roster_alt)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.inspect())
        self.tree.bind("<Delete>", lambda e: self.delete_record())
        self.reload_rows()

    def reload_rows(self, select=None):
        if self.collection is None:
            return
        old = select or (self.tree.selection()[0] if self.tree.selection() else self.selected_key)
        filters = {k: [code] for k, variable in self.filter_vars.items() if (code := self.filter_maps[k].get(variable.get()))}
        try:
            rows = self.controller.rows(self.collection, self.search.get(), **filters)
        except EXPECTED_ERRORS as error:
            self.status.set(readable_error(error))
            return
        if self.sort_key:
            def order(row):
                value = row.get(self.sort_key)
                return (value is None, value if isinstance(value, (int, float)) else str(value or "").casefold())
            rows.sort(key=order, reverse=self.sort_reverse)
        self.row_map = {record_key(self.collection, row): row for row in rows}
        self.tree.delete(*self.tree.get_children())
        for index, (identity, row) in enumerate(self.row_map.items()):
            self.tree.insert("", "end", iid=identity, tags=("alternate",) if index % 2 else (), values=["—" if row.get(c[0]) is None else row[c[0]] for c in COLLECTIONS[self.collection].columns])
        if old in self.row_map:
            self.tree.selection_set(old)
            self.tree.see(old)
        elif rows:
            self.tree.selection_set(next(iter(self.row_map)))
        else:
            self.selected_key = None
        self.status.set(f"{len(rows)} 条记录" + (" · 无匹配结果" if not rows else ""))
        self.inspect()

    def sort(self, name):
        self.sort_reverse = not self.sort_reverse if self.sort_key == name else False
        self.sort_key = name
        self.reload_rows()

    def current_record(self):
        if self.collection is None or not hasattr(self, "tree") or not self.tree.winfo_exists():
            return None
        selection = self.tree.selection()
        return self.row_map.get(selection[0]) if selection else None

    def _record_context(self, row):
        if self.collection == "students":
            return f"{row['family']} · {row.get('branch') or '未指定支系'}"
        return next((str(row[key]) for key in ("family_name", "department_name", "college_name",
            "major_name", "class_name", "semester") if row.get(key)), "")

    def inspect(self):
        row = self.current_record()
        state = (str(self.inspector), self.collection, self.compact_inspector, dict(row) if row else None)
        if getattr(self, "_inspection_state", None) == state:
            return
        self._inspection_state = state
        for widget in self.inspector.winfo_children():
            widget.destroy()
        self.record_buttons = {}
        if row is None:
            ttk.Label(self.inspector, text="选择记录以查看详情", style="SurfaceMuted.TLabel").grid(row=0, column=0, sticky="w")
            self._update_actions()
            return
        self.selected_key = record_key(self.collection, row)
        name = row.get("name") or row.get("title") or row.get("student_name") or "档案"
        eyebrow = self._record_context(row)
        if self.collection == "grades":
            banner = ScoreSlip(self.inspector,row)
        elif self.collection == "announcements":
            banner = NoticeHeading(self.inspector,row)
        elif self.compact_inspector:
            banner = ttk.Frame(self.inspector, style="Surface.TFrame")
            banner.columnconfigure(0, weight=1)
            label = ttk.Label(banner, text=name, style="InspectorTitle.TLabel")
            label.grid(row=0, column=0, sticky="ew")
            label.bind("<Configure>", lambda e, target=label: target.configure(wraplength=max(1,e.width)))
            number = row.get("student_no") or row.get("course_code") or row.get("code") or str(row.get("id", ""))
            ttk.Label(banner, text=number, style="SurfaceMuted.TLabel").grid(row=0, column=1, padx=(12,0))
        else:
            banner = RecordBanner(self.inspector, name,
                row.get("student_no") or row.get("course_code") or row.get("code") or str(row.get("id", "")), eyebrow,
                row.get("primary_element"), row.get("primary_affinity"))
        banner.grid(row=0,column=0,sticky="ew",pady=(0,10))
        lines = []
        for field in fields(self.collection):
            value = row.get(field.key)
            if field.key == "family" and self.collection == "branches":
                value = row.get("family_name")
            if self.collection == "students" and field.key == "age":
                value = age_from_birth_date(row.get("birth_date")) if age_from_birth_date(row.get("birth_date")) is not None else value
            if field.key in ("name", "title"):
                continue
            lines.append(f"{field.label}　{value if value is not None else '未指定'}")
        if self.collection == "students":
            lines += ["", f"学院　{row.get('college_name') or '未分配'}", f"专业　{row.get('major_name') or '未分配'}", f"班级　{row.get('class_name') or '未分班'}"]
        if self.collection == "students":
            frame = self._student_details(self.inspector, row)
        elif self.collection == "announcements":
            frame, self.detail_text = reading_text(self.inspector,row.get("body", ""))
        elif self.collection == "grades":
            frame = ttk.Frame(self.inspector,style="Surface.TFrame")
        else:
            frame, self.detail_text = reading_text(self.inspector, "\n\n".join(lines))
        frame.grid(row=2, column=0, sticky="nsew")
        tools = ttk.Frame(self.inspector, style="Surface.TFrame")
        tools.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        if self.identity.is_admin and not self.compact_inspector:
            for action, label, command in (("edit", "编辑…", self.edit_record), ("delete", "删除…", self.delete_record)):
                if action == "edit" and self.collection == "announcements":
                    continue
                button = ttk.Button(tools, text=label, command=command, style="Danger.TButton" if action == "delete" else "TButton")
                button.pack(side="right" if action == "delete" else "left", padx=(0, 6) if action == "edit" else 0)
                self.record_buttons[action] = button
        if self.collection == "students":
            if self.identity.is_admin and not self.compact_inspector:
                button = ttk.Button(tools, text="重置密码…", command=self.reset_password)
                button.pack(side="left")
                self.record_buttons["reset"] = button
            if self.identity.is_admin or row["student_no"] == self.identity.student_no:
                ttk.Button(self.inspector, text="选课与成绩…", command=lambda no=row["student_no"]: self.show_student_grades(no)).grid(row=4, column=0, sticky="w", pady=(8, 0))
        self._update_actions()

    def _student_details(self, parent, row):
        tabs = ttk.Notebook(parent)
        birthday = row.get("birth_date")
        if birthday and birthday.startswith("--"):
            birthday = f"{int(birthday[2:4])}月{int(birthday[5:7])}日"
        age = age_from_birth_date(row.get("birth_date"))
        groups = (("学籍", (("学院", row.get("college_name")), ("专业", row.get("major_name")),
            ("班级", row.get("class_name")), ("入学", row.get("enrollment_year")), ("状态", row.get("status")),
            ("性别", row.get("gender")), ("生日", birthday), ("年龄", age if age is not None else row.get("age")))),
            ("族系与元素", (("族系", row.get("family")), ("支系", row.get("branch")),
                ("主元素", row.get("primary_element")), ("亲和", row.get("primary_affinity")))),
            ("生活资料", (("联系方式", row.get("contact") or "未指定"),
                ("宿舍", row.get("dormitory") or "未指定"), ("备注", row.get("notes") or "未登记"))))
        areas, label_width = [], 0
        for title, pairs in groups:
            area = ScrollArea(tabs)
            areas.append(area)
            group = area.body
            group.columnconfigure(1, weight=1)
            for index, (label, value) in enumerate(pairs):
                caption = ttk.Label(group, text=label, style="SurfaceMuted.TLabel")
                label_width = max(label_width, caption.winfo_reqwidth()+12)
                caption.grid(
                    row=index, column=0, sticky="nw", padx=(0, 12), pady=(6, 2))
                content = str(value) if value is not None else "未指定"
                if title == "生活资料":
                    control = ReadonlyParagraph(group, content)
                else:
                    control = ttk.Entry(group, style="Read.TEntry", width=12)
                    control.insert(0, content)
                    control.configure(state="readonly")
                control.grid(row=index, column=1, sticky="ew", pady=2)
                area.watch(control)
            tabs.add(area, text=title)
        for area in areas:
            area.body.columnconfigure(0, minsize=label_width)
        return tabs

    def _guard(self, action):
        try:
            return action()
        except EXPECTED_ERRORS as error:
            messagebox.showerror("操作未完成", readable_error(error), parent=self)

    def new_record(self):
        if self.collection is None:
            return
        def action():
            self.controller.require_admin()
            return RecordDialog(self, self.controller, self.collection, on_saved=lambda values: self._saved(values, created=True))
        return self._guard(action)

    def edit_record(self):
        row = self.current_record()
        if not row or self.collection == "announcements":
            return
        def action():
            self.controller.require_admin()
            return RecordDialog(self, self.controller, self.collection, row, self._saved)
        return self._guard(action)

    def _saved(self, values, created=False):
        key = self.selected_key
        if self.collection == "students":
            key = values["student_no"]
        elif created:
            identity_fields = {"courses": ("course_code",), "grades": ("student_no", "course_code", "semester"),
                "families": ("name",), "branches": ("name", "family"), "announcements": ("title", "class_code")}
            names = identity_fields.get(self.collection, ("code",))
            candidates = [row for row in self.controller.rows(self.collection) if all(
                row.get("family_name" if name == "family" else name) == values[name] for name in names)]
            key = str(max(candidates, key=lambda row: row["id"])["id"]) if candidates else None
        self.reload_rows(select=key)
        self.status.set("已保存 / " + ("记录不符合当前筛选条件" if key and key not in self.row_map else self.status.get()))

    def delete_record(self):
        row = self.current_record()
        if row is None:
            return
        def action():
            self.controller.require_admin()
            target = row.get("name") or row.get("title") or row.get("student_name")
            code = row.get("student_no") or row.get("course_code") or row.get("code") or row.get("id")
            if not messagebox.askyesno("确认删除", f"删除 {target} / {code}？\n\n{DELETE_IMPACT[self.collection]}\n\n此操作无法撤销。", parent=self, default="no"):
                return
            self.controller.delete(self.collection, row)
            self.selected_key = None
            self.reload_rows()
            self.status.set("记录已删除")
        self._guard(action)

    def reset_password(self):
        row = self.current_record()
        if not row or self.collection != "students":
            return
        def action():
            self.controller.require_admin()
            if messagebox.askyesno("重置密码", f"重置 {row['name']} / {row['student_no']} 的密码？\n学生下次登录必须改密。", parent=self, default="no"):
                password = self.controller.reset_password(row["student_no"])
                ResultDialog(self, "密码已重置", f"学号：{row['student_no']}\n初始密码：{password}\n首次登录需设置新密码。")
        self._guard(action)

    def show_student_grades(self, no):
        rows = self.controller.student_grades(no)
        ResultDialog(self, "选课与成绩 / " + no, "\n\n".join(f"{r['course_name']} / {r['course_code']}\n{r['semester']}　成绩：{r['score'] if r['score'] is not None else '待录入'}" for r in rows) or "尚无选课记录。")

    def _show_profile(self):
        heading = self._heading("我的档案", "")
        ttk.Button(heading,text="修改密码…",command=lambda:PasswordDialog(self,self.controller),
            style="Accent.TButton").grid(row=0,column=2,sticky="e")
        no = self.identity.student_no
        row = next((r for r in self.controller.rows("students",no) if r["student_no"] == no),None) if no else None
        if row is None:
            frame,_ = reading_text(self.content,f"账号：{self.identity.username}\n\n身份：管理员")
            frame.grid(row=3,column=0,sticky="nsew")
            return
        spread=ttk.Frame(self.content,style="Stage.TFrame")
        spread.grid(row=3,column=0,sticky="nsew")
        spread.columnconfigure(1,weight=1);spread.rowconfigure(0,weight=1)
        identity=ttk.Frame(spread,style="Stage.TFrame",width=px(self,330))
        identity.grid(row=0,column=0,sticky="ns",padx=(0,16));identity.pack_propagate(False)
        RecordBanner(identity,row["name"],row["student_no"],f"{row['family']} · {row.get('branch') or '未指定支系'}",
            row.get("primary_element"),row.get("primary_affinity")).pack(fill="x")
        ttk.Button(identity,text="选课与成绩…",command=lambda:self.show_student_grades(no)).pack(anchor="w",pady=16)
        details=self._student_details(spread,row)
        details.grid(row=0,column=1,sticky="nsew")
        compact_bar=ttk.Frame(spread,style="Stage.TFrame")
        ttk.Label(compact_bar,text=row["name"],style="StageMeta.TLabel").pack(side="left")
        ttk.Button(compact_bar,text="选课与成绩…",command=lambda:self.show_student_grades(no)).pack(side="right")
        def fit_profile(event):
            compact=event.width < px(self,700)
            if compact:
                identity.grid_remove();compact_bar.grid(row=0,column=0,columnspan=2,sticky="ew",pady=(0,12))
                details.grid_configure(row=1,column=0,columnspan=2)
                spread.rowconfigure(0,weight=0);spread.rowconfigure(1,weight=1)
            else:
                compact_bar.grid_remove();identity.grid()
                details.grid_configure(row=0,column=1,columnspan=1)
                spread.rowconfigure(0,weight=1);spread.rowconfigure(1,weight=0)
        spread.bind("<Configure>",fit_profile)
        self.status.set("个人资料只读。")

    def _show_data(self):
        self._heading("数据交换", "")
        tools = ttk.Frame(self.content, style="Stage.TFrame")
        tools.grid(row=2, column=0, sticky="ew", pady=(0, 18))
        buttons = []
        for label, action in (("导入学生 CSV…", self.import_csv), ("导出学生 CSV…", self.export_csv), ("导出完整 JSON…", self.export_json), ("空库导入 JSON…", self.import_json), ("空库载入校园示例…", self.seed_demo)):
            buttons.append(ttk.Button(tools, text=label, command=action))
        action_grid = {}
        def wrap_actions(event):
            row = column = used = 0
            for button in buttons:
                width = button.winfo_reqwidth()+8
                if column and used+width > event.width:
                    row, column, used = row+1, 0, 0
                position = (row, column)
                if action_grid.get(button) != position:
                    button.grid(row=row, column=column, sticky="w", padx=(0, 8), pady=(0, 8))
                    action_grid[button] = position
                column, used = column+1, used+width
        tools.bind("<Configure>", wrap_actions)
        frame, _ = reading_text(self.content, "学生 CSV\n用于交换学生资料。导入结果逐行报告错误，并列出已创建的账号；导出不包含密码。\n\n"
            "校园 JSON\n包含学院、专业、班级、族系、支系、学生、课程、选课与公告。仅限导入空库；失败时完整回滚。导入后学生密码恢复为初始密码，首次登录必须修改。\n\n"
            "示例数据\n仅向空库载入虚构校园资料；已有档案时拒绝执行。")
        frame.grid(row=3, column=0, sticky="nsew")

    def import_csv(self):
        def action():
            self.controller.require_admin()
            path = filedialog.askopenfilename(parent=self, title="导入学生 CSV", filetypes=[("CSV", "*.csv")])
            if not path:
                return
            result = self.controller.import_csv(path)
            self.refresh()
            report = f"成功导入：{result.imported} 条\n失败：{len(result.errors)} 条\n\n" + "\n".join(result.errors)
            if result.credentials:
                report += "\n\n已创建账号 / 初始密码（首次登录需改密）\n" + "\n".join(f"{no} / {password}" for no, password in result.credentials)
            ResultDialog(self, "导入结果", report)
        self._guard(action)

    def export_csv(self):
        def action():
            self.controller.require_admin()
            path = filedialog.asksaveasfilename(parent=self, title="导出全部学生 CSV", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if path:
                count = self.controller.export_csv(path)
                self.status.set(f"已导出全部 {count} 位学生 / {path}")
        self._guard(action)

    def export_json(self):
        def action():
            self.controller.require_admin()
            path = filedialog.asksaveasfilename(parent=self, title="导出完整校园 JSON", defaultextension=".json", filetypes=[("JSON", "*.json")])
            if path:
                self.controller.service.export_archive(path)
                self.status.set("完整校园 JSON 已保存 / " + path)
        self._guard(action)

    def import_json(self):
        def action():
            self.controller.require_admin()
            path = filedialog.askopenfilename(parent=self, title="空库导入校园 JSON", filetypes=[("JSON", "*.json")])
            if path and messagebox.askyesno("导入完整校园", "仅向空库导入。学生密码将恢复为初始密码，首次登录必须改密。继续？", parent=self, default="no"):
                self.controller.service.import_archive(path)
                self.refresh()
                ResultDialog(self, "校园档案已导入", "学生初始密码：123456\n首次登录必须改密。请将初始账号交付给对应学生。")
        self._guard(action)

    def seed_demo(self):
        def action():
            self.controller.require_admin()
            if messagebox.askyesno("载入校园示例", "向空库写入虚构校园与学生示例？\n已有资料时会拒绝执行。", parent=self, default="no"):
                self.controller.seed()
                self.refresh()
                ResultDialog(self, "校园示例已载入", "示例学生以学号登录。\n初始密码：123456\n首次登录必须修改密码。")
        self._guard(action)

    def focus_search(self):
        if self.collection is not None:
            if self.compact_inspector:
                self.compact_tabs.select(0)
                self.update_idletasks()
            self.search_entry.focus_set()
            self.search_entry.selection_range(0, "end")

    def clear_search(self):
        self.search.set("")
        self.reload_rows()

    def refresh(self):
        if self.collection is not None:
            self.reload_rows()
        else:
            self.show_page(self.current_page)

    def change_theme(self):
        if any(isinstance(child, tk.Toplevel) for child in self.winfo_children()):
            return
        configure_styles(self.winfo_toplevel(), self.theme_var.get(), self.zoom_var.get())
        selected, search = self.selected_key, self.search.get()
        filters = {k: v.get() for k, v in getattr(self, "filter_vars", {}).items()}
        page = self.current_page
        self.sidebar.destroy()
        self.nav_buttons.clear()
        self._build_header()
        self._install_menu()
        self.show_page(page)
        if self.collection:
            self.search.set(search)
            for key, value in filters.items():
                if key in self.filter_vars:
                    self.filter_vars[key].set(value)
            self.reload_rows(select=selected)

    def _logout(self):
        clear_session()
        self.on_logout()

    def destroy(self):
        root = self.winfo_toplevel()
        for sequence, binding in self.bindings.items():
            root.unbind(sequence, binding)
        if self.menubar.winfo_exists():
            self.menubar.destroy()
        for child in self.winfo_children():
            if isinstance(child, tk.Toplevel):
                child.destroy()
        super().destroy()
