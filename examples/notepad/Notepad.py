"""Internal task 2: modifications of the user's Notepad_original.py.

Run: python examples/notepad/Notepad.py
Uses one Tk/mainloop; never shares account files with the SiS application.
"""
from pathlib import Path
import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from xingyuan_sis.auth import hash_password, verify_password
from xingyuan_sis.file_storage import write_json_atomic
from Notepad_original import LoginApp as OriginalLoginApp, NotepadApp as OriginalNotepadApp


def center(master, width, height):
    width = min(width, master.winfo_screenwidth()-80)
    height = min(height, master.winfo_screenheight()-120)
    master.geometry(f"{width}x{height}+{max(0,(master.winfo_screenwidth()-width)//2)}+{max(0,(master.winfo_screenheight()-height)//2)}")


def make_icons(master):
    # Tiny code-defined glyphs; PhotoImage references are retained by the app.
    shapes = {
        "新建": ((4, 2, 12, 3), (4, 3, 5, 14), (11, 3, 12, 14), (4, 13, 12, 14)),
        "打开": ((2, 5, 14, 6), (2, 6, 3, 13), (3, 12, 14, 13), (13, 6, 14, 13), (3, 3, 8, 5)),
        "保存": ((2, 2, 14, 4), (2, 4, 4, 14), (12, 4, 14, 14), (4, 12, 12, 14), (6, 3, 10, 8)),
        "剪切": ((3, 3, 5, 6), (10, 3, 12, 6), (5, 6, 7, 9), (8, 6, 10, 9), (7, 9, 9, 12), (5, 12, 7, 15), (9, 12, 11, 15)),
        "复制": ((2, 2, 11, 3), (2, 3, 3, 12), (5, 5, 14, 6), (5, 6, 6, 15), (13, 6, 14, 15), (6, 14, 13, 15)),
        "粘贴": ((4, 2, 11, 5), (2, 4, 4, 15), (11, 4, 13, 15), (4, 13, 11, 15), (5, 7, 10, 8), (5, 10, 10, 11)),
    }
    result = {}
    for name, rectangles in shapes.items():
        icon = tk.PhotoImage(master=master, width=16, height=16)
        for box in rectangles:
            icon.put("#29475a", to=box)
        result[name] = icon
    return result


class LoginApp(OriginalLoginApp):
    def __init__(self, master):
        self.master = master
        folder = Path(os.environ.get("XINGYUAN_NOTEPAD_HOME", Path(__file__).parent / "data"))
        self.users_file = folder / "users.json"
        self.load_users()
        master.title("记事本练习 · 登录")
        center(master, 400, 300)
        master.minsize(360, 280)
        self.icons = make_icons(master)
        master.iconphoto(True, self.icons["新建"].zoom(2))
        frame = ttk.Frame(master, padding=24)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="记事本 · 课程练习", font=("Microsoft YaHei UI", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 20))
        for row, (label, name, show) in enumerate((("用户名", "username_entry", ""), ("密码", "password_entry", "•")), 1):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=8)
            entry = ttk.Entry(frame, show=show)
            entry.grid(row=row, column=1, sticky="ew", pady=8)
            setattr(self, name, entry)
        ttk.Button(frame, text="登录", command=self.login).grid(row=3, column=0, sticky="ew", pady=12, padx=(0, 8))
        ttk.Button(frame, text="注册", command=self.register).grid(row=3, column=1, sticky="ew", pady=12)
        ttk.Label(frame, text="初次运行请注册，密码至少 8 个字符。").grid(row=4, column=0, columnspan=2, sticky="w")
        master.bind("<Return>", lambda e: self.login())
        self.username_entry.focus_set()

    def load_users(self):
        self.users = {}
        if self.users_file.exists():
            self.users = json.loads(self.users_file.read_text(encoding="utf-8"))
            if not isinstance(self.users, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in self.users.items()):
                raise ValueError("记事本账号文件格式错误")

    def save_users(self):
        write_json_atomic(self.users_file, self.users)

    def register(self):
        username, password = self.username_entry.get().strip(), self.password_entry.get()
        if not username:
            messagebox.showerror("无法注册", "请填写用户名。", parent=self.master)
            return
        if username in self.users:
            messagebox.showerror("无法注册", "用户名已存在。", parent=self.master)
            return
        try:
            encoded = hash_password(password)
            self.users[username] = encoded
            self.save_users()
        except (ValueError, OSError) as error:
            self.users.pop(username, None)
            messagebox.showerror("无法注册", str(error), parent=self.master)
            return
        messagebox.showinfo("注册完成", "请使用刚注册的账号登录。", parent=self.master)

    def login(self):
        if not verify_password(self.password_entry.get(), self.users.get(self.username_entry.get().strip())):
            messagebox.showerror("无法登录", "用户名或密码错误。", parent=self.master)
            return
        self.master.unbind("<Return>")
        for child in self.master.winfo_children():
            child.destroy()
        self.master.notepad = NotepadApp(self.master)


class NotepadApp(OriginalNotepadApp):
    def __init__(self, master):
        self.icons = make_icons(master)
        self.modified = False
        super().__init__(master)
        master.iconphoto(True, self.icons["新建"].zoom(2))
        center(master, 960, 700)
        master.minsize(540, 380)
        master.protocol("WM_DELETE_WINDOW", self.close)
        self.text = self.components["text_area"]
        self.text.configure(font=("Microsoft YaHei UI", 11), padx=16, pady=12)
        self.text.bind("<<Modified>>", self.on_modified)
        self.text.bind("<KeyRelease>", lambda e: self.position(), add="+")
        self.text.bind("<ButtonRelease-1>", lambda e: self.position(), add="+")
        master.bind("<Control-Shift-S>", lambda e: self.save_as_file())
        master.bind("<Control-f>", lambda e: self.find_text())
        self._clean()

    def create_menu_items(self):
        bar = self.components["menu_bar"]
        file = tk.Menu(bar, tearoff=False)
        for label, shortcut, command in (("新建", "Ctrl+N", self.new_file), ("打开", "Ctrl+O", self.open_file), ("保存", "Ctrl+S", self.save_file)):
            file.add_command(label=label, accelerator=shortcut, image=self.icons[label], compound="left", command=command)
        file.add_command(label="另存为…", accelerator="Ctrl+Shift+S", command=self.save_as_file)
        file.add_separator()
        file.add_command(label="退出", command=self.close)
        edit = tk.Menu(bar, tearoff=False)
        for label, command in (("剪切", self.cut), ("复制", self.copy), ("粘贴", self.paste)):
            edit.add_command(label=label, image=self.icons[label], compound="left", command=command)
        edit.add_command(label="查找…", accelerator="Ctrl+F", command=self.find_text)
        layout = tk.Menu(bar, tearoff=False)
        for label, value in (("默认布局", "default"), ("紧凑布局", "compact"), ("垂直工具栏", "vertical")):
            layout.add_command(label=label, command=lambda v=value: self.apply_layout(v))
        bar.add_cascade(label="文件", menu=file)
        bar.add_cascade(label="编辑", menu=edit)
        bar.add_cascade(label="布局", menu=layout)

    def create_tool_items(self):
        self.tool_buttons = []
        for name, command in (("新建", self.new_file), ("打开", self.open_file), ("保存", self.save_file),
                              ("剪切", self.cut), ("复制", self.copy), ("粘贴", self.paste)):
            button = ttk.Button(self.components["toolbar"], text=name, image=self.icons[name], compound="left", command=command)
            self.tool_buttons.append(button)

    def apply_layout(self, layout_name):
        # Preserve the original three layout choices and their container tree.
        super().apply_layout(layout_name)
        for button in self.tool_buttons:
            button.pack_forget()
            button.pack(side="top" if layout_name == "vertical" else "left", padx=3, pady=3,
                        fill="x" if layout_name == "vertical" else "none")

    def on_modified(self, event=None):
        if self.text.edit_modified():
            self.modified = True
            self.text.edit_modified(False)
            self._title()

    def _title(self):
        name = Path(self.current_file).name if self.current_file else "无标题"
        self.master.title(("* " if self.modified else "") + name + " — 星原记事本练习")

    def _clean(self):
        self.modified = False
        self.text.edit_modified(False)
        self._title()

    def confirm_saved(self):
        # edit_modified covers edits that have not yet delivered <<Modified>>.
        if not self.modified and not self.text.edit_modified():
            return True
        result = messagebox.askyesnocancel("尚未保存", "保存当前文档的修改吗？", parent=self.master)
        return self.save_file() if result is True else result is False

    def new_file(self):
        if not self.confirm_saved():
            return
        self.text.delete("1.0", "end")
        self.current_file = None
        self.text.edit_reset()
        self._clean()

    def open_file(self):
        if not self.confirm_saved():
            return
        path = filedialog.askopenfilename(parent=self.master, filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            messagebox.showerror("无法打开", str(error), parent=self.master)
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.current_file = path
        self.text.edit_reset()
        self._clean()
        self.update_status("已打开：" + path)

    def save_file(self):
        return self._save(self.current_file) if self.current_file else self.save_as_file()

    def save_as_file(self):
        path = filedialog.asksaveasfilename(parent=self.master, defaultextension=".txt", filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        return self._save(path) if path else False

    def _save(self, path):
        try:
            Path(path).write_text(self.text.get("1.0", "end-1c"), encoding="utf-8")
        except (OSError, UnicodeError) as error:
            messagebox.showerror("无法保存", str(error), parent=self.master)
            return False
        self.current_file = path
        self._clean()
        self.update_status("已保存：" + str(path))
        return True

    def position(self):
        line, column = self.text.index("insert").split(".")
        self.update_status(f"第 {line} 行，第 {int(column)+1} 列 · UTF-8")

    def close(self):
        if self.confirm_saved():
            self.master.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        LoginApp(root)
        root.mainloop()
    except (ValueError, OSError) as error:
        messagebox.showerror("无法启动记事本", str(error), parent=root)
        root.destroy()
