# 架构与模块边界

星原 SIS 保持单向、可解释的依赖：界面负责交互，业务集中在 Service / Schema，持久化集中在 Repository，SQLite 位于最底层。目录只表达当前真实边界，不为历史路径保留兼容层。

结构性修改同时受 [设计原则](design-principles.md) 约束。

```text
src/xingyuan_sis/
├── entry.py
├── schema.py
├── service.py
├── auth.py
├── reports.py
├── student_filters.py
├── student_query.py
├── database.py
├── repository.py
├── csv_io.py
├── seed_data.py
├── cli/
├── basic_ui.py
├── terminal_input.py
├── terminal_ui.py
└── tui/
    ├── app.py
    ├── portal.py
    ├── auth_view.py
    ├── keys.py
    ├── commands.py
    ├── screen.py
    ├── text_edit.py
    ├── tokens.py
    ├── theme.py
    ├── layout.py
    ├── animation.py
    ├── view_common.py
    ├── viewer.py
    └── workspace/
        ├── __init__.py
        ├── state.py
        ├── events.py
        ├── commands.py
        ├── field_session.py
        ├── forms.py
        ├── data.py
        ├── presentation.py
        ├── view.py
        ├── roster.py
        ├── inspector.py
        ├── detail.py
        ├── student_inspector.py
        ├── editor.py
        └── dashboard.py
```

## 1. 总体依赖

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

UI 不直接写 SQL；Repository 不依赖界面；Schema 不依赖 Service、Repository 或 UI；跨层能力沿既有方向扩展，不通过反向 import 或旁路解决。

`entry.py` 是唯一程序入口。带业务子命令时进入 CLI；无子命令时检测终端能力，满足条件进入 TUI，否则进入 Basic UI。

## 2. CLI / Basic UI

主调用链只有：

```text
entry → cli/parser + cli/<domain> → service → repository → SQLite
```

学院、专业、班级、学生、课程、成绩、公告都是一级业务实体。CLI 和 Basic UI 只负责参数、输入输出与身份检查，不复制 Service 的规则。

## 3. TUI 门户

登录后顶层路径由 `tui/app.py + tui/portal.py` 唯一负责：

```text
app.run → portal
```

管理员和学生共享门户结构，只根据身份与权限显示不同入口。学生查询、个人档案和班级公告继续复用同一套工作台。

## 4. 输入与 Command

`tui/keys.py` 是纯终端输入解码层。它只识别物理输入：方向键、Enter、Esc、Tab、Home / End、PageUp / PageDown，以及原始可打印字符；它不知道“增加”“删除”“导入”等业务动作。

业务快捷键由 `tui/commands.py::Command` 描述：

```text
physical key
    ↓
keys.py
    ↓
key event / printable character
    ↓
当前上下文 Command 集合
    ↓
action
```

Command 是按钮、鼠标点击、快捷键和底栏提示的共同来源，不维护平行键位表。通用交互语义只有：方向键 / Tab 导航、Enter 激活、Esc 撤销。Space、`q`、`0`、Backspace 不作为第二套确认或返回键。`J / K` 只作为 `↓ / ↑` 的便利物理别名。

`Shift+Tab` 不进入工作台语义层；Tab 是唯一的区域焦点循环键。

## 5. Workspace 状态与焦点

键盘焦点只有一个枚举：

```text
FocusArea.ROSTER
FocusArea.INSPECTOR
FocusArea.TOOLBAR
FocusArea.DASHBOARD
```

记录型页面的 Tab 循环固定为：

```text
ROSTER → INSPECTOR → TOOLBAR → ROSTER
```

窄屏当前展示哪一块内容由独立的 `ContentPanel.ROSTER / INSPECTOR` 表示：

```text
focus         → 键盘现在操作哪里
content_panel → 单面板布局现在显示哪一面
```

因此工具栏获得焦点时，窄屏仍保持进入工具栏前的名册或档案内容；宽屏始终同时绘制名册和档案。`Location` 保存并恢复这两个状态。

## 6. 工作台职责

```text
tui/app
   ↓
workspace/__init__.py       controller / 生命周期
   ├─ state.py              Workspace / FocusArea / ContentPanel / FieldSession / Form / Location
   ├─ events.py             键鼠事件与通用交互意图
   ├─ commands.py           当前工作台 Command 集合
   ├─ field_session.py      所有局部字段编辑
   ├─ forms.py              完整事务生命周期 / 提交 / 搜索
   ├─ data.py               Catalog、数据快照、权限、关系与 TUI 语义字段
   ├─ presentation.py       value projection + display_value
   └─ view.py               工作台布局与 inspector 编排
       ├─ roster.py
       ├─ inspector.py      最终几何、绘制、命中区、导航、滚动
       ├─ detail.py         普通实体内容
       ├─ student_inspector.py  学生档案内容
       ├─ editor.py         完整事务草稿的展示
       └─ dashboard.py
```

`FieldSession` 与 `Form` 是两个不同概念：

- `FieldSession` 只拥有当前字段或声明的原子字段组；
- `Form` 拥有完整事务草稿、字段顺序和最终提交；
- Form 字段进入编辑后也使用同一个 FieldSession；
- `FieldSessionOwner.RECORD` 确认后写业务层，`FieldSessionOwner.FORM` 确认后只写回 Form 草稿；
- Form 不拥有平行的 `options / option_index / 字段输入` 状态；
- 已有记录编辑不会创建 `Form(mode="edit")`。

`Catalog` 保存工作台需要的数据快照、权限、关系和语义字段映射，不拥有界面命令表。正常重绘不查询数据库，所有持久化写操作最终通过 Service → Repository。

## 7. 一套字段身份

记录字段使用语义身份：

```text
field:<field_key>
```

学生档案的复合行是：

```text
物种  field:family          · field:branch
班级  field:major_code      · field:class_number
元素  field:primary_element · field:primary_affinity
```

三行都由两个真实 target 构成。左右键在行内移动，纵向导航由同一份最终几何自然得出。

“可以聚焦”和“可以编辑”彼此独立。姓名、学号、学院等只读字段仍属于空间几何；Enter 激活后由权限和字段定义决定是否允许创建 FieldSession。

已有档案不会生成 `field:<index>` 或编辑专用 target 图；新建 Form 同样使用字段 key 作为用户可见 action。索引只用于 Form 内部顺序。

选项只在 FieldSession 中临时增加：

```text
option:0
option:1
...
```

## 8. 唯一展示与关系投影

`presentation.py` 提供唯一字段展示管线：

```text
base values
   +
当前 FieldSession 拥有的临时值（若有）
   ↓
projected values
   ↓
display_value(...)
```

`base values` 可以是数据库记录或 Form 草稿。格式化器不知道“浏览 / 新建 / 编辑”状态，同一个值只有一种 label 和格式。

学生三组复合关系共用同一个字段组机制：

```text
family → branch
major_code → class_number
primary_element → primary_affinity
```

进入父项时 FieldSession 同时拥有声明的两项，按相同流程推进到第二项并原子确认；直接进入子项时只拥有子项。数据来源不同不能产生另一套交互。

班级的持久化事实仍是 `class_id / class_code`。TUI 不把内部编码当作第三个可见字段；`Catalog` 在交互边界把 `major_code + class_number` 解析成真实班级。

## 9. 最终几何是唯一几何

档案内容生成后只做一次布局：

```text
content Line[]
    ↓
wrap + compact layout
    ↓
final Line[]
    ├─ render
    ├─ hit regions
    ├─ action targets
    └─ directional navigation
```

绘制、鼠标命中和方向键不得分别维护不同的“逻辑行”。窄窗口换行以后，导航看到的就是用户真正看到的行。

`events.py` 不知道“物种”“班级”“元素”等页面细节。学生二维复合行和普通实体单列的差异由 `Line` 几何自然表达。

名册由 `WorkspaceLayout.roster_capacity()` 给出实际可见记录数；列标题占用的行统一扣除。渲染与 PageUp / PageDown 共用该容量。

## 10. 已有记录字段修改

已有记录没有编辑页面：

```text
field:<key>
   │ Enter
   ▼
FieldSession(owner=RECORD)
   │
   ├─ 自由输入
   └─ option 列表
   │ Enter
   ▼
校验 → Service → Repository → Catalog.refresh()
   │
   ▼
field:<key>
```

约束：

- 自由文本 / 数字 / 日期确认后立即保存；
- 枚举 / 关系字段确认后立即保存；
- Esc 丢弃 FieldSession，不写数据库；
- 不存在已有记录级保存按钮；
- 当前字段位置、档案结构与 target 身份不因编辑变化；
- 三组复合字段都通过声明的原子 FieldSession 推进；
- 子字段也可以在当前父项约束下单独修改。

## 11. 完整事务 Form

`Form` 只用于真正需要独立事务生命周期的操作：

- 新建记录；
- 删除确认；
- 密码重置；
- 导入 / 导出；
- seed。

带字段的 Form 使用如下状态机：

```text
方向键 / Tab 选择 field
   │ Enter
   ▼
FieldSession(owner=FORM)
   │ Enter
   ▼
写回 Form draft
   │
   ├─ 继续选字段
   └─ S 保存完整事务
```

因此：

- 移动到字段不会自动进入编辑；
- Enter 是唯一字段进入动作；
- FieldSession 中 Enter 确认字段或复合组；
- FieldSession 中 Esc 只取消本字段；
- Form 空闲时 Esc 取消整个事务；
- `S` 只提交完整事务。

学生新建 Form 使用与档案相同的语义字段：

```text
族系 / 支系
专业 / 班号
主元素 / 亲和等级
```

不重新暴露 `class_code`。提交时由 `Catalog` 将专业 + 班号转换为规范化内部班级关联。

## 12. 数据库与数据

`database.py::SCHEMA` 是当前 SQLite 结构的唯一声明。`initialize_database()` 只创建当前结构，不隐式修补历史 schema。

学生出生资料支持 `YYYY-MM-DD`、`YYYY`、`--MM-DD` 和空值。完整生日存在时年龄实时派生；资料不足时可保存独立年龄。

班级数据库仍保存稳定 `code` 和关系 ID；TUI 的“专业 + 班号”是交互语义，不要求反规范化数据库。

当前项目没有已发布数据库版本兼容承诺。未来若需要迁移，应建立显式版本迁移，而不是把历史条件塞回初始化路径。

## 13. 回归原则

结构性回归至少保护：

- 工作台同一时刻只有一个 `FocusArea`；
- `ContentPanel` 只表示窄屏内容，不兼职键盘焦点；
- Tab 单向循环记录页的名册、档案和操作栏；
- Shift+Tab 不存在第二条区域导航路径；
- 用户可见字段使用稳定 `field:<key>`；
- 物种、班级、元素三类复合行都使用两个独立 target；
- 三组复合字段共用字段组机制；
- 学生新建 Form 与档案使用同一套班级语义，不重新暴露 `class_code`；
- 只读字段可聚焦但不可写；
- 已有记录 Enter 从 field 创建局部 FieldSession；
- 新建 Form 中方向键只移动，Enter 才创建 FieldSession；
- FieldSession 只拥有当前字段或声明的复合组；
- Form 不拥有第二套 options 编辑状态；
- FieldSession Esc 与 Form Esc 分属两层撤销；
- `S` 只提交完整 Form；
- 已有记录没有保存按钮或“编辑”Command；
- `keys.py` 不包含业务快捷键；
- Command 同时驱动工具栏、快捷键和快捷键提示；
- PageUp / PageDown 使用与渲染一致的 viewport 容量；
- 展示、命中区和方向导航消费同一份最终几何；
- 滚轮与方向键聚焦档案时进入同一导航路径；
- 测试保护当前行为，不要求恢复已删除的私有 API。
