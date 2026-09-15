# 项目结构

星原 SIS 保持单向、可解释的依赖：界面只负责交互，业务集中在 service / schema，持久化集中在 repository，SQLite 位于最底层。目录只表达当前真实边界，不为历史路径保留兼容层。

结构性修改同时受 [设计原则](design-principles.md) 约束；该文档定义单一事实来源、抽象准入、迁移策略和测试边界。

```text
src/xingyuan_sis/
├── __init__.py
├── __main__.py
├── entry.py                  # 唯一程序入口与模式选择
│
├── schema.py                 # 字段、日期和数值契约
├── service.py                # 业务操作与关联校验
├── auth.py                   # 身份、密码与会话业务
├── reports.py                # 汇总查询
├── student_filters.py        # 学生结构化筛选
├── student_query.py          # 学生查询语法
│
├── database.py               # 当前 SQLite schema、连接和事务
├── repository.py             # SQL 查询与持久化
├── csv_io.py                 # 学生 CSV 导入 / 导出
├── seed_data.py              # 演示数据
│
├── cli/
│   ├── __init__.py           # CLI 入口与统一错误处理
│   ├── parser.py             # argparse 命令树
│   ├── dispatcher.py         # group → 领域 runner
│   ├── common.py             # CLI 共享输入输出
│   ├── student.py
│   ├── academic.py
│   ├── course.py
│   ├── grade.py
│   └── data.py
│
├── basic_ui.py               # 终端能力不足时的数字菜单
├── terminal_input.py         # 普通输入与 TUI 单行编辑
├── terminal_ui.py            # 基础菜单 / CLI 的输出与分页
│
└── tui/
    ├── app.py                # 登录后的顶层导航循环
    ├── portal.py             # 唯一首页 renderer 与身份导航模型
    ├── auth_view.py          # 登录与修改密码界面
    ├── keys.py               # 键盘、鼠标协议
    ├── screen.py             # 终端绘制与点击区域
    ├── text_edit.py          # TextBuffer 与原始输入事件
    ├── tokens.py             # 唯一语义颜色 token 表
    ├── theme.py              # 页头、按钮、底栏等视觉原语
    ├── layout.py             # 响应式布局与可见区计算
    ├── animation.py          # 首页动画
    ├── view_common.py        # Board 与通用视图原语
    ├── viewer.py             # 只读长文本阅读器
    │
    └── workspace/
        ├── __init__.py       # 工作台控制器生命周期
        ├── state.py          # Workspace / Form / Location 状态
        ├── events.py         # 键鼠事件状态机
        ├── forms.py          # 表单打开、输入与保存
        ├── data.py           # 集合定义、数据快照与关联
        ├── view.py           # 响应式工作台编排
        ├── roster.py         # 名册面板
        ├── detail.py         # 非学生通用实体档案
        ├── student_inspector.py # 学生档案唯一实现
        ├── editor.py         # 非学生独立编辑器 / 确认面板
        └── dashboard.py      # 数据概览
```

## 总体依赖

```text
                 ┌─ CLI
entry ───────────┼─ Basic UI
                 └─ TUI
                    │
                    ▼
              Service / Auth
                    │
                    ▼
                Repository
                    │
                    ▼
                  SQLite
```

界面层不得直接写 SQL。Repository 不依赖 CLI、Basic UI 或 TUI。Schema 不依赖 Service、Repository 或界面。

`entry.py` 负责三种正式入口的分流：带业务子命令时进入 CLI；无子命令时检测 TTY、ANSI 与即时按键能力，满足条件进入 TUI，否则进入 Basic UI。`--tui` 与 `--basic` 可以显式覆盖自动选择。Basic UI 是受支持的低能力终端入口，不属于历史兼容层。

## CLI

CLI 的唯一调用链为：

```text
entry → cli/parser + cli/<domain> → service → repository → SQLite
```

学院、专业、班级都是一级实体：`xy college`、`xy major`、`xy class`。新增 CLI 领域时，在 `cli/` 中增加对应 runner 并在 `dispatcher.py` 注册；不得复制业务实现。

## TUI 门户

登录后的首页只有一条生产路径：

```text
app.run → app._portal_home → portal.frame
```

`app.py` 管理会话、导航循环和 action dispatch；`portal.py` 定义一级 / 二级导航及响应式渲染。不存在另一套 labels 首页、legacy action 表或仅供测试使用的 home renderer。测试必须直接验证 portal。

## 工作台

```text
tui/app
   ↓
tui/workspace/__init__        controller
   ├─ state
   ├─ events
   ├─ forms
   ├─ data ───────────────→ service → repository → SQLite
   └─ view
       ├─ roster
       ├─ detail
       ├─ student_inspector
       ├─ editor
       └─ dashboard
```

`workspace/__init__.py` 只管理生命周期：创建 Catalog 与 Workspace、接收事件结果、执行保存 / 刷新以及统一错误处理。`events.py` 只改变交互状态并返回控制事件；`forms.py` 管理草稿和写操作；`data.py` 持有一次读取的数据快照与 UI 所需关系；`view.py` 只编排布局。

学生档案因为信息层级与原地编辑模型确实不同，拥有专用 `student_inspector.py`。学生的浏览、编辑、焦点目标与响应式布局都从这一份结构生成；`detail.py` 只处理其他实体。

## 数据库

`database.py::SCHEMA` 是当前数据库结构的唯一声明。`initialize_database()` 只创建当前结构，不检测旧列、不现场补列、不执行隐式历史迁移。

当前项目没有已发布数据库版本的兼容承诺。如果未来需要迁移，按 [设计原则](design-principles.md#6-兼容与迁移策略) 建立显式版本迁移，而不是继续向初始化路径追加条件分支。

Repository 是 SQL 数据访问的唯一入口；service 使用业务名称 / 编号解析关系并调用 repository。

## UI 基础设施

- `tokens.py` 只定义语义 token；不存在 `_ACCENT` / `_DIM` / `_SELECTED` / `_SURFACE` 等历史别名。
- `screen.py` 负责终端 cell、ANSI 绘制、点击区域和 surface 生命周期；它使用同名语义 token，不创造第二套颜色词汇。
- `text_edit.py::TextBuffer` 是文本值、光标与 viewport 的唯一状态模型。
- `terminal_input.py` 直接把 `TextBuffer` 交给绘制函数，不通过临时 chars/cursor wrapper 转换。
- `WorkspaceLayout` 与 `visible_start` 是工作台几何和可见区计算的唯一来源。

## 数据与状态

- 数据仅在进入页面、手动刷新和保存后重新读取，不在每次重绘时查询数据库。
- 草稿独立于数据库记录；字段编辑只修改 Form，保存后才进入 service。
- 外键选择显示名称与业务编号，记录身份使用稳定数据库 ID 保持导航上下文。
- 关联浏览通过 `Location` 保存来源记录、查询、视图、滚动和档案焦点，返回时按稳定 ID 恢复。

## 当前学生档案

```text
摘要
  姓名
  学号
  物种：族系 · 支系
  性别
  年龄
  入学
  学院
  班级
  学籍
  元素：主元素 · 亲和

选课与成绩

个人信息
  出生日期
  联系方式
  宿舍
  备注
```

年龄由出生日期即时计算，不作为独立数据库字段。

## 测试原则

测试保护当前生产路径和稳定行为，不保护退出生产路径的私有函数名。

需要固定的主要交互约束包括：

- portal 在宽 / 窄终端都保持可操作；
- 首页动画、点击区域和底栏不破坏正文；
- 名册选择只在越出可见区后推动视口；
- 宽屏双栏使用 Tab / ← / → 切换焦点，另一栏保留当前记录上下文；
- 学生档案遵循“摘要 → 选课与成绩 → 个人信息”；
- 文本输入中的普通字符不被全局快捷键吞掉，Esc 取消最内层操作；
- CLI、CSV 与表单共享 schema 校验，非法输入失败时不改变原记录；
- seed 测试验证关系与查询语义，不绑定某一版角色名单。

## 扩展原则

优先扩展现有边界，而不是先制造新层级：

- 新业务能力先进入 service，再接 CLI / Basic UI / TUI；
- 新 SQL 只进入 repository；
- 新工作台实体优先复用 `data + roster + detail + forms`；
- 只有交互模型确实不同，才增加专用 inspector / panel；
- 不把一次性数据要求升级成长期业务门禁；
- 不为已放弃的旧目录、旧私有 API、旧数据库结构或旧 token 名称保留转发层。
