# 架构与模块边界

<<<<<<< HEAD
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
│   ├── __init__.py           # 解析后命令的调度；认证与错误处理归 entry
│   ├── parser.py             # argparse 命令树
│   ├── dispatcher.py         # group → 领域 runner
│   ├── common.py             # CLI 共享输入输出
│   ├── student.py
│   ├── academic.py
│   ├── course.py
│   ├── grade.py
│   ├── notice.py             # 班级公告
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
        ├── inspector.py      # 共享字段、选项、换行、焦点与档案绘制
        ├── detail.py         # 非学生实体的档案内容
        ├── student_inspector.py # 学生档案信息层级
        ├── editor.py         # 新建 / 文件路径 / 确认面板
        └── dashboard.py      # 数据概览
```

## 总体依赖
=======
星原 SIS 使用单向、可解释的依赖结构。三个入口共享同一套业务逻辑和持久化层：
>>>>>>> refs/recovery/main-before-force-20260918

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

核心原则很简单：界面只处理交互，业务规则集中在 Service / Schema，SQL 只进入 Repository。

## 1. 入口

`entry.py` 是唯一程序入口。

- 有业务子命令时进入 CLI；
- 无子命令时检测 TTY、ANSI 输出和即时按键能力；
- 能力满足时进入 TUI；
- 否则进入 Basic UI；
- `--tui` 和 `--basic` 可以显式覆盖自动选择。

Basic UI 是正式支持的低能力终端入口，不是历史兼容层。

## 2. 业务与持久化

### Schema

`schema.py` 定义字段解析、日期、年龄和数值等共享契约。CLI、CSV 和 TUI 不应分别维护一套验证规则。

### Service / Auth

`service.py` 负责业务操作和关系校验；`auth.py` 负责身份、密码和会话业务。

界面层通过业务编号或名称调用 Service，不直接接触 SQL。

### Repository

`repository.py` 是 SQL 数据访问的唯一入口。Repository 不依赖 CLI、Basic UI 或 TUI。

### Database

`database.py::SCHEMA` 是当前 SQLite 结构的唯一声明。`initialize_database()` 只创建当前结构。

当前项目没有已发布数据库版本的兼容承诺；如果未来需要版本迁移，应建立显式迁移机制，而不是在初始化路径中不断追加旧结构判断。

## 3. CLI

CLI 的调用链保持为：

```text
entry → cli/parser + cli/<domain> → service → repository → SQLite
```

<<<<<<< HEAD
基础菜单通过 `entry.main` 执行命令，不能绕过登录和权限检查；CLI 不再提供第二个 `main`。

学院、专业、班级都是一级实体：`xy college`、`xy major`、`xy class`。新增 CLI 领域时，在 `cli/` 中增加对应 runner 并在 `dispatcher.py` 注册；不得复制业务实现。
=======
学院、专业、班级、学生、课程和成绩都是一级业务实体。新增 CLI 功能时，应复用现有 Service，而不是在 CLI 中复制业务实现。
>>>>>>> refs/recovery/main-before-force-20260918

## 4. TUI 门户

登录后的顶层导航由 `tui/app.py` 和 `tui/portal.py` 负责：

```text
app.run → portal
```

`app.py` 管理会话和页面生命周期；`portal.py` 定义首页与一级 / 二级导航。管理员和学生共享同一套导航结构，只根据权限显示不同入口。

## 5. 工作台

记录型页面共享同一工作台框架：

```text
tui/app
   ↓
<<<<<<< HEAD
tui/workspace/__init__        controller
   ├─ state
   ├─ events
   ├─ forms
   ├─ data ───────────────→ service → repository → SQLite
   └─ view
       ├─ roster
       ├─ inspector
       ├─ detail
       ├─ student_inspector
       ├─ editor
       └─ dashboard
=======
tui/workspace/__init__        生命周期 / 控制器
   ├─ state.py                Workspace / Form / Location
   ├─ events.py               键鼠事件与统一交互意图
   ├─ forms.py                输入、选项、保存和完整表单
   ├─ data.py                 UI 数据快照与关系
   ├─ presentation.py         记录投影与字段展示值
   └─ view.py                 当前 inspector 的编排入口
       ├─ roster.py
       ├─ detail.py            普通单列档案
       ├─ student_inspector.py 学生二维档案
       ├─ editor.py            新建 / 确认等完整事务
       └─ dashboard.py
>>>>>>> refs/recovery/main-before-force-20260918
```

`workspace/__init__.py` 只负责生命周期、控制事件、刷新和统一错误处理。

<<<<<<< HEAD
`student_inspector.py` 定义学生特有的“摘要 → 选课与成绩 → 个人信息”；`detail.py` 定义其他实体内容。二者生成相同的分段文本结构，由 `inspector.py` 统一处理字段值、选项展开、中文换行、点击区域、焦点和滚动。浏览与编辑消费同一份内容，表单方向键顺序直接从内容中的字段位置推导，不维护第二份字段布局。

`Catalog` 持有身份、可用操作和数据快照。学生查询、个人档案和本班公告复用工作台，只读状态同时约束可见控件、事件处理与写操作。`Workspace` 保存当前记录和面板焦点，`Form` 保存草稿、字段 / 保存按钮焦点，`Location` 保存关联导航的返回位置。界面重绘不写数据库。

`XingyuanService.register_student` 负责生成初始密码，并将档案和密码散列写入同一条 INSERT。CLI、TUI 和 CSV 导入均调用它。`csv_io.py` 只负责 CSV 解析、序列化和逐行结果汇总，通过传入的注册操作复用业务校验；不再保留第二套关系查询和 INSERT。初始密码仅通过操作结果交给管理员，不进入学生导出数据。
=======
`events.py` 不应知道“学生物种”“课程字段”等页面细节。它接收键盘、鼠标等输入后，只产生通用导航或操作意图。
>>>>>>> refs/recovery/main-before-force-20260918

## 6. 档案导航

档案导航只有一条主路径：

```text
键盘 ↑↓←→ ─┐
鼠标滚轮 ──┼→ events._move_detail_selection()
            │
            ▼
      view.directional_target()
            │
      ┌─────┴─────┐
      ▼           ▼
  detail.py   student_inspector.py
  单列几何       二维几何
```

普通实体档案是单列几何：`↑ / ↓` 在纵向 target 中移动，`←` 返回名册，`→` 保持在当前档案。

学生档案因为“物种（族系 · 支系）”和“元素（主元素 · 亲和）”存在二维复合行，由 `student_inspector.py` 提供自己的空间几何。

事件层只知道“向上 / 向下 / 向左 / 向右”，不写 `state.key == "students"` 之类的导航特判。

鼠标滚轮在档案未聚焦时可以只滚动预览；档案获得焦点后，滚轮上下和键盘 `↑ / ↓` 进入同一个 target 导航入口。

<<<<<<< HEAD
- portal 在宽 / 窄终端都保持可操作；
- 首页动画、点击区域和底栏不破坏正文；
- 名册选择只在越出可见区后推动视口；
- Tab / Shift+Tab 遍历名册、档案与工具栏，切换区域不改变当前记录；
- 学生档案遵循“摘要 → 选课与成绩 → 个人信息”；
- 文本输入中的普通字符不被全局快捷键吞掉，Esc 取消最内层操作；
- CLI、CSV 与表单共享 schema 校验，非法输入失败时不改变原记录；
- seed 测试验证关系与查询语义，不绑定某一版角色名单。
=======
## 7. 档案展示与字段编辑
>>>>>>> refs/recovery/main-before-force-20260918

已有记录的展示和修改属于同一个档案页面。

```text
当前 target
    │ Enter
    ▼
字段输入 / 选项
    │ Enter
    ▼
校验 → Service → Repository → 刷新
```

已有记录没有整页编辑草稿，也没有记录级“保存”按钮。字段确认前只存在当前字段的临时值；确认后立即保存，Esc 取消当前字段修改。

需要原子联动的字段可以形成一个小字段组。例如修改学生族系后必须继续选择支系，最后一次性提交，避免产生不一致的中间状态。

新建记录、删除确认、导入 / 导出和 seed 属于完整事务，因此仍可以使用独立表单或确认面板。

`presentation.py` 是档案展示值的公共边界。浏览态和字段修改态都先形成 projected record，再经过同一套 `display_value()` 规则格式化；编辑状态只改变临时覆盖值和交互控件，不建立第二套字段展示语义。

## 8. 数据与状态

- 数据在进入页面、手动刷新和保存后更新，不在每次重绘时查询数据库；
- 当前记录使用稳定数据库 ID 保持导航上下文；
- 关联浏览通过 `Location` 保存来源记录、查询、视图、滚动和档案焦点；
- 新建记录的多字段草稿与现有记录的单字段修改是两种不同事务；
- CSV、CLI 和 TUI 共用 Schema 校验。

学生档案中的出生资料支持：

```text
YYYY-MM-DD   完整日期
YYYY         仅年份
--MM-DD      仅月日
```

完整出生日期存在时，年龄按当前日期实时计算；出生资料不完整时，可以使用独立 `age` 作为补充事实。

## 9. UI 基础设施

- `tokens.py`：语义颜色 token；
- `screen.py`：终端 cell、ANSI 绘制和点击区域；
- `text_edit.py::TextBuffer`：文本值、光标和 viewport；
- `terminal_input.py`：普通输入与 TUI 单行输入；
- `layout.py`：响应式工作台几何；
- `view_common.py`：Board 和通用视图原语。

视觉和交互规范见 [TUI 设计规范](ui-design.md)。

## 10. 主要目录

```text
src/xingyuan_sis/
├── entry.py
├── schema.py
├── service.py
├── auth.py
├── repository.py
├── database.py
├── csv_io.py
├── seed_data.py
├── cli/
├── basic_ui.py
└── tui/
    └── workspace/
        ├── state.py
        ├── events.py
        ├── forms.py
        ├── data.py
        ├── presentation.py
        ├── view.py
        ├── roster.py
        ├── detail.py
        ├── student_inspector.py
        ├── editor.py
        └── dashboard.py
```

## 11. 扩展方式

新增能力时优先沿现有边界扩展：

- 新业务规则 → Service / Schema；
- 新 SQL → Repository；
- 新 CLI 命令 → `cli/<domain>`；
- 新工作台实体 → 优先复用 `data + presentation + roster + detail + forms`；
- 只有信息层级或空间交互确实不同，才增加专用 inspector；
- 页面自己的几何规则放在 inspector，不放进全局事件状态机；
- 不为一次性演示数据要求增加永久业务门禁；
- 不为已经退出生产路径的私有 API 或旧数据库结构保留无意义兼容层。

更多原则见 [设计原则](design-principles.md)，档案显示值规则见 [档案展示与字段编辑模型](record-presentation.md)。
