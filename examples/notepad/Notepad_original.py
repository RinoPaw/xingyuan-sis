import tkinter as tk
from tkinter import ttk,messagebox, filedialog, simpledialog

import json
import os

class LoginApp:
    def __init__(self, master):
        self.master = master
        ### 此处可对根窗口的属性进行修改 ###
        master.title("登录")
        master.geometry("300x200")
        
        # 用户数据文件
        self.users_file = "users.json"
        self.load_users()
        ### 按屏幕坐标进行布局 ###
        # 登录界面组件
        tk.Label(master, text="用户名:").place(x=50, y=50)
        self.username_entry = tk.Entry(master)
        self.username_entry.place(x=120, y=50)
        
        tk.Label(master, text="密码:").place(x=50, y=80)
        self.password_entry = tk.Entry(master, show="*")
        self.password_entry.place(x=120, y=80)
        ### 按屏幕坐标进行布局：水平方向排列按钮 ###
        tk.Button(master, text="登录", command=self.login).place(x=120, y=120)
        tk.Button(master, text="注册", command=self.register).place(x=180, y=120)
    
    def load_users(self):
        """加载用户数据"""
        try:
            with open(self.users_file, 'r') as f:
                self.users = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.users = {"admin": "admin"}  # 默认管理员账户
    
    def save_users(self):
        """保存用户数据"""
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f)
    
    def login(self):
        """登录验证"""
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if username in self.users and self.users[username] == password:
            self.master.destroy()  # 关闭登录窗口
            root = tk.Tk()
            NotepadApp(root)  # 打开记事本主界面
            root.mainloop()
        else:
            messagebox.showerror("错误", "用户名或密码错误")
    
    def register(self):
        """注册新用户"""
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if not username or not password:
            messagebox.showerror("错误", "用户名和密码不能为空")
            return
        
        if username in self.users:
            messagebox.showerror("错误", "用户名已存在")
        else:
            self.users[username] = password
            self.save_users()
            messagebox.showinfo("成功", "注册成功")



class NotepadApp:
    def __init__(self, master):
        self.master = master
        master.title("动态布局记事本")
        master.geometry("800x600")
        self.current_file = None
        
        # 主容器框架
        self.main_frame = ttk.Frame(master)
        self.main_frame.pack(expand=True, fill=tk.BOTH)
        
        # 组件存储字典
        self.components = {
            'menu_bar': None,
            'toolbar': None,
            'text_area': None,
            'status_bar': None
        }
        
        # 初始化组件
        self.init_components()
        
        # 应用默认布局
        self.apply_layout('default')
        self.bind_shortcuts()

    def init_components(self):
        """初始化所有界面组件"""
        # 菜单栏（固定到窗口）
        self.components['menu_bar'] = tk.Menu(self.master)
        self.master.config(menu=self.components['menu_bar'])
        
        # 工具栏
        self.components['toolbar'] = ttk.Frame(self.main_frame)
        
        # 文本区
        self.components['text_area'] = tk.Text(
            self.main_frame,
            wrap="word",
            undo=True
        )
        
        # 状态栏
        self.components['status_bar'] = ttk.Label(
            self.main_frame,
            text="就绪",
            relief=tk.SUNKEN
        )
        
        # 添加菜单和工具项
        self.create_menu_items()
        self.create_tool_items()

    def apply_layout(self, layout_name):
        """应用指定布局方案"""
        # 清除现有布局
        for widget in self.main_frame.winfo_children():
            widget.pack_forget()
            widget.grid_forget()

        # 应用新布局
        if layout_name == 'default':
            self.components['toolbar'].pack(side=tk.TOP, fill=tk.X)
            self.components['text_area'].pack(expand=True, fill=tk.BOTH)
            self.components['status_bar'].pack(side=tk.BOTTOM, fill=tk.X)
        elif layout_name == 'compact':
            self.components['text_area'].pack(expand=True, fill=tk.BOTH)
            self.components['toolbar'].pack(side=tk.BOTTOM, fill=tk.X)
        elif layout_name == 'vertical':
            self.components['toolbar'].pack(side=tk.LEFT, fill=tk.Y)
            self.components['text_area'].pack(expand=True, fill=tk.BOTH)
            self.components['status_bar'].pack(side=tk.BOTTOM, fill=tk.X)

    def create_menu_items(self):
        """创建菜单项"""
        # 文件菜单
        file_menu = tk.Menu(self.components['menu_bar'], tearoff=0)
        file_menu.add_command(label="新建", command=self.new_file)
        file_menu.add_command(label="打开", command=self.open_file)
        file_menu.add_command(label="保存", command=self.save_file)
        
        # 布局菜单
        layout_menu = tk.Menu(self.components['menu_bar'], tearoff=0)
        layout_menu.add_command(
            label="默认布局",
            command=lambda: self.apply_layout('default')
        )
        layout_menu.add_command(
            label="紧凑布局",
            command=lambda: self.apply_layout('compact')
        )
        layout_menu.add_command(
            label="垂直工具栏",
            command=lambda: self.apply_layout('vertical')
        )
        
        self.components['menu_bar'].add_cascade(label="文件", menu=file_menu)
        self.components['menu_bar'].add_cascade(label="布局", menu=layout_menu)

    def create_tool_items(self):
        """创建工具栏按钮"""
        tools = ["新建", "打开", "保存", "剪切", "复制", "粘贴"]
        for tool in tools:
            btn = ttk.Button(
                self.components['toolbar'],
                text=tool,
                command=lambda t=tool: getattr(self, f"{t.lower()}_file")()
            )
            btn.pack(side=tk.LEFT, padx=2)

    def bind_shortcuts(self):
        """绑定快捷键"""
        self.master.bind("<Control-n>", lambda e: self.new_file())
        self.master.bind("<Control-o>", lambda e: self.open_file())
        self.master.bind("<Control-s>", lambda e: self.save_file())
    
    def new_file(self):
        """新建文件"""
        self.components['text_area'].delete(1.0, tk.END)
        self.current_file = None
        self.master.title("记事本 - 无标题")
    
    def open_file(self):
        """打开文件"""
        filepath = filedialog.askopenfilename(
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        
        if filepath:
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                    self.components['text_area'].delete(1.0, tk.END)
                    self.components['text_area'].insert(1.0, content)
                
                self.current_file = filepath
                self.master.title(f"记事本 - {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("错误", f"无法打开文件:\n{e}")
    
    def save_file(self):
        """保存文件"""
        if self.current_file:
            try:
                with open(self.current_file, 'w') as f:
                    f.write(self.components['text_area'].get(1.0, tk.END))
                messagebox.showinfo("成功", "文件保存成功")
                self.update_status(f"已保存: {self.current_file}")
            except Exception as e:
                messagebox.showerror("错误", f"保存文件失败:\n{e}")
        else:
            self.save_as_file()
    
    def save_as_file(self):
        """另存为文件"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    f.write(self.components['text_area'].get(1.0, tk.END))
                
                self.current_file = filepath
                self.master.title(f"记事本 - {os.path.basename(filepath)}")
                messagebox.showinfo("成功", "文件保存成功")
                self.update_status(f"已保存: {self.current_file}")
            except Exception as e:
                messagebox.showerror("错误", f"保存文件失败:\n{e}")

    def update_status(self, message):
        """更新状态栏"""
        self.components['status_bar'].config(text=message)
   
    def cut(self):
        """剪切文本"""
        self.components['text_area'].event_generate("<<Cut>>")
    
    def copy(self):
        """复制文本"""
        self.components['text_area'].event_generate("<<Copy>>")
    
    def paste(self):
        """粘贴文本"""
        self.components['text_area'].event_generate("<<Paste>>")
    
    def find_text(self):
        """查找文本"""
        find_str = simpledialog.askstring("查找", "输入查找内容:")
        if find_str:
            content = self.components['text_area'].get(1.0, tk.END)
            if find_str in content:
                messagebox.showinfo("查找结果", f"找到 '{find_str}'")
            else:
                messagebox.showinfo("查找结果", f"未找到 '{find_str}'")

if __name__ == "__main__":
    root = tk.Tk()
    app = LoginApp(root)
    root.mainloop()

