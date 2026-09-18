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

Command 是按钮、鼠标点击、快捷键和底栏提示的共同来源，不维护平行键位表。`workspace/commands.py` 定义工作台可用命令；门户和 viewer 的局部命令留在自己的上下文中。

通用交互语义只有：方向键 / Tab 导航、Enter 激活、Esc 撤销。Space、`q`、`0`、Backspace 不作为第二套确认或返回键。`J / K` 只作为 `↓ / ↑` 的便利物理别名。

`Shift+Tab` 不再进入工作台语义层；Tab 是唯一的区域焦点循环键。

## 5. Workspace 状态与焦点

`Workspace` 不再用 `details + action_focus` 两个布尔量拼接焦点。键盘焦点只有一个枚举：

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

窄屏当前展示哪一块内容由独立的 `ContentPanel.ROSTER / INSPECTOR` 表示。它和键盘焦点回答不同问题：

```text
focus         → 键盘现在操作哪里
content_panel → 单面板布局现在显示哪一面
```

因此工具栏获得焦点时，窄屏仍保持进入工具栏前的名册或档案内容；宽屏则始终同时绘制名册和档案。`Location` 保存并恢复这两个明确状态，不再保存布尔组合。

## 6. 工作台职责

```text
tui/app
   ↓
workspace/__init__.py       controller / 生命周期
   ├─ state.py              Workspace / FocusArea / ContentPanel / FieldSession / Form / Location
   ├─ events.py             键鼠事件与通用交互意图
   ├─ commands.py           当前工作台 Command 集合
   ├─ field_session.py      已有记录的局部字段会话
   ├─ forms.py              新建 / 删除 / 导入等完整事务表单
   ├─ data.py               Catalog、数据快照、权限、关系与 TUI 语义字段
   ├─ presentation.py       record projection + display_value
   └─ view.py               工作台布局与 inspector 编排
       ├─ roster.py
       ├─ inspector.py      最终几何、绘制、命中区、导航、滚动
       ├─ detail.py         普通实体内容
       ├─ student_inspector.py  学生档案内容
       ├─ editor.py         完整事务页面
       └─ dashboard.py
```

`FieldSession` 与 `Form` 是两个不同概念：前者附着在现有档案的一个字段或原子字段组上；后者拥有一整个独立事务页面。已有记录编辑不会创建 `Form(mode="edit")`。

`Catalog` 保存工作台需要的数据快照、权限、关系和语义字段映射，不拥有界面命令表。正常重绘不查询数据库，所有写操作最终通过 Service → Repository。

## 7. 一个档案，一套字段身份

`student_inspector.py` 和 `detail.py` 都只生成内容结构，字段在整个生命周期中拥有同一个稳定身份：

```text
field:<field_key>
```

学生档案的复合行是：

```text
物种  field:family          · field:branch
班级  field:major_code      · field:class_number
元素  field:primary_element · field:primary_affinity
```

三行都由两个真实 target 构成，而不是把其中一行预先拼成字符串。左右键在行内移动，纵向导航由同一份最终几何自然得出。

“可以聚焦”和“可以编辑”彼此独立。姓名、学号、学院等只读字段仍属于空间几何；Enter 激活后由权限和字段定义决定是否允许创建 `FieldSession`。

进入字段修改不会生成 `field:<index>` 或其他编辑专用 target 图。选项只临时增加：

```text
option:0
option:1
...
```

确认或取消后，字段身份从未发生变化。已有记录也不存在“编辑”Command；用户直接在档案字段上按 Enter 修改。

## 8. 唯一展示与关系投影

`presentation.py` 提供唯一字段展示管线：

```text
数据库记录
   +
当前 FieldSession 拥有的临时值（若有）
   ↓
projected record
   ↓
display_value(...)
   ↓
档案内容
```

格式化器不知道“浏览态 / 编辑态”。同一个值只有一种 label 和格式。

学生有两组父子一致性约束：

```text
family → branch
major_code → class_number
```

它们由同一个语义字段组机制处理：选择父项后再选择合法子项，已有记录最后原子提交一次。`primary_element` 与 `primary_affinity` 没有父子约束，所以独立提交，但仍使用相同的双 target 行结构。

班级的持久化事实仍是 `class_id / class_code`。TUI 不把内部编码当作第三个可见字段；`Catalog` 负责在交互边界把 `major_code + class_number` 解析成真实班级。这样 Repository / Service 保持规范化数据模型，同时用户只面对一套班级语义。

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

名册也由 `WorkspaceLayout.roster_capacity()` 给出实际可见记录数；列标题占用的行在这里统一扣除。渲染与 PageUp / PageDown 共用该容量，不能再各算一份。

PageUp / PageDown 只改变当前 viewport；翻页后若原焦点离开可见范围，再把焦点收回可见 target。它们不承担“跳过 N 条记录”的第二种选择语义。

## 10. 已有记录字段修改

已有记录没有编辑页面：

```text
field:<key>
   │ Enter
   ▼
FieldSession
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
- 枚举 / 关系字段确认选项后立即保存；
- Esc 丢弃 FieldSession，不写数据库；
- 不存在已有记录级“保存”按钮；
- 不存在已有记录的 `form.position` 导航；
- 当前字段位置、档案结构与 target 身份不因编辑发生变化；
- `family + branch` 和 `major_code + class_number` 分别按一个原子 FieldSession 提交；
- 子字段 `branch`、`class_number` 也可以在当前父项约束下单独修改。

## 11. 完整事务 Form

`Form` 只用于真正需要独立事务页面的操作：

- 新建记录；
- 删除确认；
- 密码重置；
- 导入 / 导出；
- seed。

这些操作由 `forms.py + editor.py` 负责，可以拥有自己的字段顺序和显式保存 / 确认。它们不是档案的第二种状态。

学生新建 Form 继续复用同一套学生语义字段，因此同样显示：

```text
族系 / 支系
专业 / 班号
主元素 / 亲和等级
```

而不是另造一个 `class_code` 选择器。提交时由 `Catalog` 将专业 + 班号转换为规范化的内部班级关联。

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
- 所有档案字段使用稳定 `field:<key>`；
- 物种、班级、元素三类复合行都使用两个独立 target；
- `family → branch` 与 `major_code → class_number` 共用字段组机制；
- 学生新建 Form 与档案使用同一套班级语义，不重新暴露 `class_code`；
- 只读字段可聚焦但不可写；
- Enter 从当前 field 创建局部 FieldSession，而非 Form；
- FieldSession 只拥有当前字段或声明的复合组；
- Enter 即时保存、Esc 取消；
- 已有记录没有保存按钮或“编辑”Command；
- `keys.py` 不包含业务快捷键；
- Command 同时驱动工具栏、快捷键和快捷键提示；
- Space / `q` / `0` / Backspace 不是全局返回或激活别名；
- PageUp / PageDown 使用与渲染一致的 viewport 容量；
- 展示、命中区和方向导航消费同一份最终几何；
- 滚轮与方向键聚焦档案时进入同一导航路径；
- 新建 / 删除等完整事务仍通过 Form；
- 测试保护当前行为，不要求恢复已删除的私有 API。
