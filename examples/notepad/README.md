# 内部任务二 · Notepad.py 分析与修改

## 来源

原例由用户提供。仓库保留未修改的原始副本，以便与课程要求的修改版对照。
仓库保存字节不变的副本 `Notepad_original.py`，SHA-256：
`21cacb55ff642f9dd6c131286feefb73525936e05ac77f6a70f5741ba5f65841`。

修改版 `Notepad.py` 继承原例的两个类，保留组件字典、三种布局、快捷键、Text 编辑与查找等结构；需要修正的行为通过方法覆盖完成。不是另写一个无关示例代替原作业。

## 原例分析

`LoginApp` 建立账号输入、登录和注册按钮，使用 JSON 用户字典。原登录页通过 place 固定坐标；验证成功后销毁根窗口，再创建第二个 Tk 和 mainloop。`NotepadApp` 建立 main_frame，通过 components 保存菜单、工具栏、文本区和状态栏。`apply_layout` 先移除几何管理，再用 pack 建立默认、紧凑、垂直布局。菜单 command、按钮 command、root.bind 和 lambda 将事件连接到方法；Text 虚拟事件完成剪切、复制与粘贴。mainloop 负责事件分发。

原工具栏把“新建”等中文标签转为 `新建_file` 之类的方法名，类里没有这些方法，故点击报错。剪切、复制、粘贴的真实方法是 cut/copy/paste。find_text 方法存在，但原菜单没有查找入口。文本读写使用平台默认编码，且新建、打开和关闭均不检查未保存内容。

## 修改覆盖

| 课程要求或问题 | 修改版证据 |
| --- | --- |
| 程序图标 | `make_icons` 使用标准 PhotoImage 绘制图标，窗口调用 iconphoto |
| 窗口位置 | `center` 按屏幕居中并约束可见范围；记事本允许调整尺寸 |
| 菜单与工具栏图标 | 文件/编辑菜单及六个工具按钮使用同一组图标与文字，保留图片引用 |
| 布局与事件 | 仍保留三个布局；垂直模式将按钮逐个纵排；菜单和工具按钮显式映射真实方法 |
| 登录生命周期 | 一个 Tk、一个 mainloop；登录后切换组件，不嵌套事件循环 |
| 文件与反馈 | UTF-8、另存为、状态栏光标位置；未保存提示有保存/放弃/取消三条路径 |
| 键盘 | Ctrl+N/O/S/F、Ctrl+Shift+S；原生 Text 剪贴板与撤销 |
| 账号文件 | 独立注册，使用项目已有 PBKDF2 函数保存散列；原子的 JSON 文件写入；不共享 SiS 账号 |

## 运行

在仓库根目录：

```powershell
uv run python examples/notepad/Notepad.py
```

初次运行先注册独立记事本账号，密码至少 8 字符。账号文件位于本目录 `data/users.json`（已忽略）；可用 `XINGYUAN_NOTEPAD_HOME` 改到演示目录。

测试 `test_notepad_exercise.py` 用真实 Tk 验证六个按钮的关键路径、菜单与工具栏图标、三种布局、剪贴板、UTF-8 保存/打开及放弃新建的取消路径。
