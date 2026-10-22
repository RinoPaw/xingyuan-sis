# Tkinter GUI · 课程覆盖与交付说明

日期：2026-10-22。依据仓库 Word 原文的第二大项目“班级管理信息系统 GUI 实现”，并交叉核对第一大项目的功能要求。原文通过 Word 只读方式提取后检查；没有把其中示例程序的说明当作用户的新指令。

## 课程覆盖表

| 原文条目 | 交付与证据 | 边界 |
| --- | --- | --- |
| 内部任务一：Tkinter 框架、控件、布局、事件 | GUI 使用 Tk/ttk、控件树、grid/pack、command/bind、单 root/mainloop；真实 Tk 测试 | Tk 使用需要 Python 自带 Tcl/Tk |
| 内部任务二：分析 Notepad.py | `examples/notepad/Notepad_original.py` 保留用户原例；该目录 README 分析两类、组件字典、布局和事件 | 与 SiS 主程序独立 |
| 内部任务二：图标、位置、菜单/工具栏图标等 | 修改版 `examples/notepad/Notepad.py`，窗口图标/居中/菜单和工具栏图标；修正原工具按钮错误 | 不能用 SiS 菜单替代这项练习 |
| 内部任务三：原信息系统改为 Tkinter GUI | `xy --gui` 复用原入口；真实菜单、登录、初始化、强制改密、全部业务页 | CLI / Basic / TUI 保留 |
| GUI 菜单系统 | 文件、记录、前往、查看、账户、帮助；权限与选择状态决定可用项 | Windows 菜单外观受原生系统控制 |
| 管理员新增、查询、修改、删除学生 | Service 注册及分配凭据；共享查询筛选；完整草稿；删除显示关联影响 | 学号、姓名创建后不可改 |
| 学生登录与个人信息修改 | Auth 首次强制改密；个人档案只读；仅修改自己密码 | 管理命令在 controller 再次校验身份 |
| 学号与姓名查询 | 名册搜索、学院/班级/状态筛选、列排序；使用共享 query_students | 搜索也支持族系、元素等资料 |
| 班级公告创建、浏览、删除 | 管理员发布多行正文与阅读/删除；学生读取始终传入本人学号 | 学生按当前班级读取；已发布公告不提供编辑，需删除后重发 |
| 学院、专业、班级、族系、课程、选课与成绩 | 对应 GUI 页面、关联名称候选、Service CRUD；成绩留空表示待录入 | 保持现有业务字段与约束 |
| 文件保存 → 数据库保存 | `MemoryRepository` → `JsonRepository` → 原 `Repository`；可运行演示 `examples/storage_stages.py`；最终 GUI 使用 SQLite | 阶段演示是业务资料存储演进，不提供另一套账号登录 UI；账号与会话仍由最终应用 Auth 负责 |
| JSON 文件阶段 | 全部业务集合、学生、选课与公告保存为 JSON；文件阶段能重启读取并继续修改 | CSV 仅作学生交换，不作为完整 JSON 阶段的替代 |
| 数据结构 | 内存阶段用 list/dict 管理记录与关联；文件持久化阶段原子写入 | 指导书的“如链表”作为举例处理，未声称实现自定义链表 |
| 运行环境、开发环境、详细设计与源代码 | README、架构文档、当前设计说明、本报告及源程序 | 项目 Python 最低版本是 3.14，不能因指导书写 Windows 7+ 就承诺当前 Python 支持 Windows 7 |

个人资料示例中的住址、电话、邮件、籍贯、爱好，目前通过联系方式、宿舍与备注对应。没有把这些全部宣称为已存在的独立结构化字段。

## 当前架构

`uv run xy --gui` 仅通过 `xingyuan_sis.gui.app` 启动当前应用；旧占位界面与嵌套源码副本已移除。

GUI → CampusController → Service/Auth → Repository → SQLite。`record_projection.py` 将关联 id 转成公共编号，供 GUI 编辑草稿与 JSON 交换共用。Schema 仍是字段和验证规则来源。GUI 无 SQL，不接触 Service.repository。学生写权限由 controller 集中拒绝，不只隐藏按钮。

图形层见 [当前视觉设计](gui-punk-design.md)：用户选择 P5R 作为参考后，原年鉴方向已否决。矢量路径绘制章节纸片、斜切标题与兽形校徽；Tk 9 内置 SVG 按当前物理尺寸抗锯齿重绘；标题保持水平排版；实际按钮、表格、输入、文本仍使用 Tk/ttk。未使用 AI 生成图片。

`MemoryRepository` 和 `JsonRepository` 作为存储阶段适配器注入同一个 Service。关系检查、唯一性和删除行为属于 Repository 职责，字段与业务校验仍调用既有 Service/Schema。JSON 导入先在内存阶段完整验证，再由最终 Repository 在一个事务中导入空库；错误不能留下半个校园。

## 运行与演示

```powershell
uv run xy --gui
uv run python examples/notepad/Notepad.py
uv run python -X utf8 examples/storage_stages.py --file .tmp/demo-campus.json --db .tmp/demo-campus.db
```

存储阶段演示路径须为新文件/空数据库；重复运行不会覆盖已有校园。最终 GUI 可在“数据交换”导入/导出学生 CSV、完整校园 JSON，或显式向空库载入虚构校园示例。CSV 逐行报告失败并返回成功账号。

完整 JSON 不带密码或散列，导入与文件阶段重启均重建初始学生凭据；SQLite 导入后初始密码为 `123456`，首次登录必须改密。它是可携带的业务档案，不是保留账号密码和会话的灾难恢复备份。

GUI 键盘：Ctrl+1…7 切换章节；Ctrl+F 搜索；Ctrl+N 新建；Ctrl+E 编辑；F5 刷新。Delete 只在名册聚焦时删除；对话框 Ctrl+S 保存、Esc 取消；Tab/Shift+Tab 使用原生焦点顺序。小窗口/大字号下采用内嵌列表/资料页签，编辑、删除和重置密码沿用记录菜单，保留选中记录。

## 验证与限制

- 上一轮完整回归实际结果：436 项，5 项跳过；无失败或错误。跳过项均为 Windows 上不适用的 POSIX 终端测试。复现命令：`uv run python -X utf8 -m unittest discover -s tests`。先前系统 Python 会加载另一个已安装副本；使用项目环境运行，并确认导入路径指向当前 `src/`。
- 本轮静态版：红色整页、黑白章节签、按内容区分名册/公告/成绩构图，删除重复标题与独立详情窗口；Tk 9 SVG 抗锯齿，并校验缩放及图像释放。最终 GUI 工作流、入口及颜色测试共27项通过。逐控件说明按当前真实控件树重新生成，见[设计决策](gui-control-decisions.md)和[逐控件清单](gui-control-inventory.md)。原生系统对话框的子控件坐标和颜色不由项目控制。
- 字体版增量验证：GUI 工作流及入口共 17 项、Notepad 共 3 项通过；覆盖真实字体族、三个缩放等级下的导航边界、缺字库后备和小窗口列表可读范围。已构建 wheel 并从独立临时目录导入，确认字体资源随包携带、可私有加载。实际 `uv run xy --gui` 确认进入当前 MainWindow，启动前后数据库、管理员与会话文件散列一致。
- 新增测试覆盖：学生权限与公告范围、Schema 不可变字段、真实 Tk 页面/表单/取消/排序/主题/绑定生命周期、完整 JSON 往返与凭据重置、文件损坏与写入失败回滚、SQLite 导入回滚、Notepad 工具栏/剪贴板/布局/UTF-8。
- 原先 Windows 清理错误来自测试中 `with sqlite3.connect` 只提交而不关闭；已用 closing 修复测试资源生命周期，未修改产品的删除策略。
- 已复核七个主要页面、登录三个阶段、编辑/改密/结果窗口的真实 Tk 截图，以及 960×640 / 150% / 深色布局；临时截图不随源码保留。这些检查不能替代读屏器与跨显示器实时 DPI 验证。
- Native Menu/控件渲染在 Windows、macOS、Linux 上会不同；当前主要在 Windows 验证。
- 数据交换仍为同步本地操作，极大文件的长耗时处理尚未加入后台任务进度与取消。
- 课程报告与测试不等同于已完成用户的最终美术验收；角色肖像、学院视觉体系与更完整的页面动效仍可在现有结构上继续迭代，生成图片需先征求用户。
