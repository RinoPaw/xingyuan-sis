# 项目结构

星原 SIS 保持一个简单的依赖方向：界面只负责交互，业务集中在 service，持久化集中在 repository，SQLite 位于最底层。目录用于表达真实边界，不为历史路径保留兼容层。

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
    ├── app.py                # 登录后的顶层导航
    ├── portal.py             # 首页与身份对应导航
    ├── auth_view.py          # 登录与修改密码界面
    ├── keys.py               # 键盘、鼠标协议
    ├── screen.py             # 终端绘制与点击区域
    ├── text_edit.py          # 文本缓冲区
    ├── tokens.py             # 语义颜色 token
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
        ├── detail.py         # 通用实体档案
        ├── student_inspector.py # 学生档案唯一实现
        ├── editor.py         # 非学生独立编辑器/确认面板
        └── dashboard.py      # 数据概览
```

## 总体依赖

三个用户入口共享同一套业务层：

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

`entry.py` 负责选择使用方式：带业务子命令时进入 CLI；无子命令时检测 TTY、ANSI 与即时按键能力，满足条件进入 TUI，否则进入 Basic UI。`--tui` 与 `--basic` 可以显式覆盖自动选择。

## CLI

CLI 是一个完整子系统，因此命令树与各领域 runner 放在同一个 `cli/` 包中：

```text
entry → cli/parser + cli/<domain> → service → repository → SQLite
```

学院、专业、班级都是一级实体：`xy college`、`xy major`、`xy class`。新增 CLI 领域时，在 `cli/` 中增加对应模块并在 `dispatcher.py` 注册；不额外建立第二套业务实现。

## 工作台

工作台本身也是一个完整子系统：

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

`workspace/__init__.py` 只管理生命周期：创建 Catalog 与 Workspace、接收事件结果、执行保存/刷新以及统一错误处理。`events.py` 只改变交互状态并返回控制事件；`forms.py` 管理草稿和写操作；`data.py` 持有一次读取的数据快照与 UI 所需关系；`view.py` 只编排布局。

学生档案需要不同的信息层级与原地编辑，因此拥有一个专门的 `student_inspector.py`。学生的浏览、编辑、焦点目标与响应式布局都从这一份结构生成；`detail.py` 不再保留另一套学生实现。

## 数据与状态

- 数据仅在进入页面、手动刷新和保存后重新读取，不在每次重绘时查询数据库。
- 草稿独立于数据库记录；字段编辑只修改 Form，保存后才进入 service。
- 外键选择显示名称与业务编号，记录身份使用稳定数据库 ID 保持导航上下文。
- 关联浏览通过 `Location` 保存来源记录、查询、视图、滚动和档案焦点，返回时按稳定 ID 恢复。
- `WorkspaceLayout` 和 `visible_start` 是布局几何与视口计算的唯一来源，渲染和事件不各自维护断点。

## 当前学生档案

学生档案只有一个渲染模型，层级为：

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

测试应针对当前真实路径，不测试已经退出生产路径的私有旧实现。尤其是学生档案测试直接使用 `workspace/student_inspector.py`，不通过通用档案伪造第二份学生界面。

需要固定的主要交互约束包括：

- 首页动画暂停后恢复原相位；
- 名册选择只在越出可见区后推动视口；
- 宽屏双栏使用 Tab / ← / → 切换焦点，当前记录在另一栏聚焦时保留弱选中态；
- 学生档案遵循“摘要 → 选课与成绩 → 个人信息”；
- 文本输入中的普通字符不被全局快捷键吞掉，Esc 统一取消最内层操作；
- 紧凑布局中的鼠标区域、键盘目标和实际显示内容一致；
- CLI、CSV 与表单共享 schema 校验，非法输入失败时不改变原记录。

## 扩展原则

优先扩展现有边界，而不是先制造新层级：

- 新业务能力先进入 service，再接 CLI / Basic UI / TUI；
- 新 SQL 只进入 repository；
- 新工作台实体优先复用 `data + roster + detail + forms`；
- 只有交互模型确实不同，才增加专用 inspector/panel；
- 不为一次性需求新增长期业务门禁；
- 不为已放弃的旧目录或旧私有 API 保留兼容转发文件。
