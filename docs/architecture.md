# 项目结构

项目保留 Python 标准库与 SQLite。CLI、基础菜单和交互工作台共享业务服务；终端布局不参与数据库操作。入口层先检测终端能力，再决定进入即时键盘工作台还是基础菜单。

```text
src/xingyuan_sis/
├── entry.py                  # xy 入口、终端模式选择和全局错误处理
├── terminal_capabilities.py  # TTY / ANSI / 即时输入能力检测
├── cli.py                    # CLI 初始化、分发和统一错误处理
├── cli_schema.py             # argparse 命令树与参数定义
├── commands/                 # CLI 各业务域命令
│   ├── common.py             # 表格、字段输出和交互输入辅助
│   ├── dispatcher.py         # group → 领域 runner 分发
│   ├── student.py
│   ├── academic.py
│   ├── course.py
│   ├── grade.py
│   └── data.py
├── basic_ui.py               # 数字输入的兼容菜单
├── terminal_input.py         # CLI 输入与 TUI 单行编辑器
├── terminal_ui.py            # 基础菜单 / CLI 输出、分页和输入辅助
├── schema.py                 # 字段、规范化、日期和数值契约；不依赖 UI / SQL
├── service.py                # 业务编号解析、关联校验、业务操作
├── repository.py             # SQL 查询与持久化
├── database.py               # Schema、连接和事务
├── reports.py                # 汇总查询
├── csv_io.py                 # CSV 导入 / 导出
├── seed_data.py              # 演示数据
├── student_filters.py        # 学生结构化筛选
└── tui/
    ├── app.py                # 登录后的导航循环、动画调度、工作台入口
    ├── portal.py             # 身份对应的导航和响应式二级菜单
    ├── auth_view.py          # 登录与密码界面
    ├── keys.py               # 键盘与鼠标协议、输入模式恢复
    ├── screen.py             # 字符宽度、点击区域、路径、全屏绘制
    ├── tokens.py             # 唯一颜色映射；无 I/O，单行输入也复用
    ├── theme.py              # 按钮、统一页头、底栏、视图标签
    ├── layout.py             # 渲染与事件共用尺寸、视口和断点
    ├── animation.py          # 首页星球与星光
    ├── workspace.py          # 工作台控制器循环
    ├── workspace_state.py    # Workspace / Form 状态模型
    ├── workspace_events.py   # 键鼠事件状态机与详情导航
    ├── workspace_forms.py    # 表单打开、输入、保存、导入导出
    ├── workspace_data.py     # 集合定义、字段转换、数据快照与关联
    ├── workspace_view.py     # 响应式布局编排
    ├── view_common.py        # Board、值格式化和通用视图原语
    ├── workspace_roster.py   # 名册面板
    ├── workspace_detail.py   # 档案与关联记录面板
    ├── workspace_editor.py   # 编辑器与确认面板
    ├── workspace_dashboard.py # 数据概览
    └── viewer.py             # 共享输出辅助中的只读长文本阅读器
```

## 入口与 CLI

`entry` 负责三种使用方式的分流：无子命令时先检测终端能力；具备 TTY、ANSI 输出和即时按键输入时进入 TUI，否则进入基础菜单。`--tui` 与 `--basic` 可以显式覆盖自动选择。带业务子命令时进入 CLI。

CLI 的参数定义、领域分发和业务执行分开：

`entry → cli → cli_schema + commands/dispatcher → commands/<domain> → service → repository → SQLite`

学院、专业、班级都是一级 CLI 实体，与学生、课程、成绩保持一致：`xy college ...`、`xy major ...`、`xy class ...`。CLI 不保留额外的教务 namespace。

新增 CLI 领域时，在 `commands/` 中增加独立模块，并只在 `dispatcher.py` 注册。跨领域复用的终端输入、表格和字段输出放在 `commands/common.py`；业务规则仍然放在 service 层。

## 工作台的数据流

`app → workspace(controller) → workspace_events / workspace_forms / workspace_state → workspace_data → service → repository → SQLite`

`workspace.py` 只负责工作台生命周期：创建 Catalog 与 Workspace、进入鼠标跟踪、接收事件结果、执行保存/刷新以及统一错误处理。`workspace_events` 管键鼠事件状态机，`workspace_forms` 管草稿、原生文本输入和写操作，`workspace_state` 只保存状态与局部状态转换。

`workspace_view` 只负责窗口尺寸、响应式分栏、顶部导航和底部操作栏，并把具体内容交给 roster/detail/editor/dashboard 面板。各面板根据页面状态和已读取的数据构建 `Board` 内容，由 `screen` 最终绘制；渲染过程中不写数据库，也不执行用户动作。

- 数据只在进入页面、手动刷新和保存后重新读取，不在每次重绘时查询数据库。
- 学生、课程、成绩、学院、专业、班级共用名册与编辑机制。集合差异集中在 `Collection` / `Field` 定义和服务适配中。
- 草稿独立于数据库记录。字段编辑和关联选择仅更新草稿，点击保存才调用服务；取消会丢弃草稿。
- 外键选择显示名称和业务编号。记录身份使用稳定 ID 保持选中位置，用户无需输入内部 ID。
- 关联浏览通过 `Location` 保存来源状态，返回时按稳定记录 ID 恢复查询、视图、名册视口和档案焦点。修改业务编号引起排序变化后，也不会错选另一条记录。
- `view_common.Board` 只负责按坐标组装文本和点击区域；领域面板不直接操作终端输入模式。
- `workspace_events` 不直接写数据库；需要保存、搜索输入或刷新时返回控制事件给 `workspace.py`。
- 默认 TUI 的文本输入使用标准库实现的单行编辑器：保留 UTF-8/中文输入、粘贴、左右移动、Home/End 和退格，同时由应用直接处理 `Esc`，保证它始终取消最内层输入。Tab 在文本输入中不触发 shell/readline 补全，因此不会把目录列表泄漏到全屏界面。
- 基础菜单与直接 CLI 继续使用普通 `input()`；它们不共享默认 TUI 的即时按键语义。

## 共享契约与依赖方向

字段定义集中在 `schema.FIELDS`。服务写操作在解析关系前调用 `validate_values`；CSV 在原有批次事务中逐行调用同一契约；终端集合仅引用字段定义并补充列、视图等展示配置。局部更新仅规范化实际提供的字段，不会用默认值覆盖未修改的信息。未知字段、空必填项、无效日期和非法数值在写入前报错。

`schema` 不依赖 service、repository 或 TUI；主题 token 不依赖终端生命周期；`WorkspaceLayout` 与 `visible_start` 把窗口断点和可见范围集中计算。渲染器和键盘事件读取相同几何信息，避免各自硬编码阈值造成点击、步长或焦点错位。

`theme.topbar` 统一登录页、首页与工作台的应用标识，元数据保持次级层级。选择标记与颜色同时表达焦点，在 `NO_COLOR` 下仍可操作。视图按钮空间不足时依次简化描述、数量，保留全部可达入口。

## 回归约束

交互层的近期行为由专门测试固定，修改公共渲染或输入代码时必须同时检查：

- 首页动画暂停后从原相位继续，不累计暂停时间；
- 名册选择在仍处于可见窗口内时不带动视口滚动；
- 宽屏双栏用 `Tab` 或 `←/→` 切换焦点，右栏可交互项有明确选中态；
- 焦点在右栏时，左栏当前记录只保留弱上下文选中态；
- 视图数量直接附着在对应筛选项；
- 学生档案遵循“摘要 → 选课与成绩 → 详细信息”，不重复数据库字段，也不出现“即时预览 / 阅读中”；
- 默认 TUI 的返回/取消提示只展示 `Esc`，文本输入中的 `q`、`/` 等始终作为普通字符；
- 学生、学院、专业、班级、课程、成绩、数据页都必须经过同一套工作区回归检查；
- 30～37 列的紧凑导航按单列移动，短窗口中当前选项始终可见；
- 76 列边界的名册点击、短窗口的详情焦点与 Enter 动作必须对应实际显示内容；
- CLI / CSV / 表单必须拒绝非有限成绩、无效日期、空必填项，失败不改变原记录；
- 自动入口必须在终端能力不足时降级到基础菜单，并允许 `--tui` / `--basic` 显式覆盖。

## 后续扩展约定

新增业务操作先落在服务层，再接入 CLI 或工作台。新增页面优先扩展集合、字段与关系定义；确实需要不同交互的页面再添加独立面板。通用绘制、输入协议和业务规则不复制到各个页面。

工作台和 CLI 的主要职责已经拆开。后续最大的结构性模块是 `service.py` 与 `repository.py`；是否继续按业务域拆分，应以领域边界和查询复用情况为依据，避免为了文件变小而制造跨模块循环依赖。

测试按行为覆盖数据写入、取消、关系保持、页面切换、宽度裁剪、缩放、鼠标输入恢复、CLI 命令树和终端能力分流。界面检查使用临时演示数据库，避免修改用户数据。
