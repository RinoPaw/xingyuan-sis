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

## 4. 工作台职责

```text
tui/app
   ↓
workspace/__init__.py       controller / 生命周期
   ├─ state.py              Workspace / FieldSession / Form / Location
   ├─ events.py             键鼠事件与通用交互意图
   ├─ field_session.py      已有记录的局部字段会话
   ├─ forms.py              新建 / 删除 / 导入等完整事务表单
   ├─ data.py               Catalog、数据快照、权限与关系
   ├─ presentation.py       record projection + display_value
   └─ view.py               工作台布局与 inspector 编排
       ├─ roster.py
       ├─ inspector.py      最终几何、绘制、命中区、导航、滚动
       ├─ detail.py         普通实体内容
       ├─ student_inspector.py  学生档案内容
       ├─ editor.py         完整事务页面
       └─ dashboard.py
```

`Workspace` 保存名册、档案、工具栏等页面状态。`FieldSession` 与 `Form` 是两个不同概念：前者附着在现有档案的一个字段或原子字段组上；后者拥有一整个独立事务页面。已有记录编辑不会创建 `Form(mode="edit")`。

`Catalog` 保存一次读取快照和当前身份可执行的操作；正常重绘不查询数据库。所有写操作最终通过 Service → Repository。

## 5. 一个档案，一套字段身份

`student_inspector.py` 和 `detail.py` 都只生成内容结构，字段在整个生命周期中拥有同一个稳定身份：

```text
field:<field_key>
```

例如：

```text
field:name
field:student_no
field:family · field:branch
...
```

“可以聚焦”和“可以编辑”彼此独立。姓名、学号等只读字段仍属于空间几何；Enter 激活后由权限和字段定义决定是否允许创建 `FieldSession`。

进入字段修改不会把 `field:class_code` 换成 `field:0`，也不会生成另一套编辑 target 图。选项只临时增加：

```text
option:0
option:1
...
```

确认或取消后，字段身份从未发生变化。

## 6. 唯一展示管线

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

格式化器不知道“浏览态 / 编辑态”。同一个值只有一种 label 和格式。修改入学年份不会改变班级、学院等无关字段的展示方式。

学生 `family + branch` 是明确的原子复合字段组，可以共同进入 projection；其他字段不能被顺带复制进会话。

## 7. 最终几何是唯一几何

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

`events.py` 不知道“学生物种”“元素亲和”等页面细节。学生二维复合行和普通实体单列的差异由 `Line` 几何自然表达。

## 8. 已有记录字段修改

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
- 枚举 / 外键确认选项后立即保存；
- Esc 丢弃 FieldSession，不写数据库；
- 不存在已有记录级“保存”按钮；
- 不存在已有记录的 `form.position` 导航；
- 当前字段位置、档案结构与 target 身份不因编辑发生变化；
- `family + branch` 按一个原子 FieldSession 提交。

顶部“编辑”只把档案焦点移动到第一个可编辑的 `field:<key>`，不会打开表单。

## 9. 完整事务 Form

`Form` 只用于真正需要独立事务页面的操作：

- 新建记录；
- 删除确认；
- 密码重置；
- 导入 / 导出；
- seed。

这些操作由 `forms.py + editor.py` 负责，可以拥有自己的字段顺序和显式保存 / 确认。它们不是档案的第二种状态。

## 10. 数据库与数据

`database.py::SCHEMA` 是当前 SQLite 结构的唯一声明。`initialize_database()` 只创建当前结构，不隐式修补历史 schema。

学生出生资料支持 `YYYY-MM-DD`、`YYYY`、`--MM-DD` 和空值。完整生日存在时年龄实时派生；资料不足时可保存独立年龄。

当前项目没有已发布数据库版本兼容承诺。未来若需要迁移，应建立显式版本迁移，而不是把历史条件塞回初始化路径。

## 11. 回归原则

结构性回归至少保护：

- 所有档案字段使用稳定 `field:<key>`；
- 只读字段可聚焦但不可写；
- Enter 从当前 field 创建局部 FieldSession，而非 Form；
- FieldSession 只拥有当前字段或声明的复合组；
- Enter 即时保存、Esc 取消；
- 已有记录没有保存按钮；
- 展示、命中区和方向导航消费同一份最终几何；
- 滚轮与方向键聚焦档案时进入同一导航路径；
- 新建 / 删除等完整事务仍通过 Form；
- 测试保护当前行为，不要求恢复已删除的私有 API。
