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

约束：

- UI 不直接写 SQL；
- Repository 不依赖 CLI、Basic UI 或 TUI；
- Schema 不依赖 Service、Repository 或 UI；
- 跨层能力沿现有依赖方向扩展，不通过反向 import 或旁路解决。

`entry.py` 是唯一程序入口。带业务子命令时进入 CLI；无子命令时检测 TTY、ANSI 与即时按键能力，满足条件进入 TUI，否则进入 Basic UI。`--tui` 与 `--basic` 可以显式覆盖自动选择。

## 2. CLI / Basic UI

CLI 的主调用链是：

```text
entry → cli/parser + cli/<domain> → service → repository → SQLite
```

学院、专业、班级、学生、课程、成绩、公告都是业务实体。CLI 和 Basic UI 只负责参数、输入输出与身份检查，不复制 Service 的业务规则。

## 3. TUI 门户

登录后的顶层路径由 `tui/app.py` 与 `tui/portal.py` 负责：

```text
app.run → portal
```

管理员和学生共享同一套门户结构，只根据身份与权限显示不同入口。学生查询、个人档案和班级公告继续复用工作台，不建立第二套学生专用页面。

## 4. 工作台

```text
tui/app
   ↓
tui/workspace/__init__.py      controller / 生命周期
   ├─ state.py                 Workspace / Form / Location
   ├─ events.py                键鼠事件与统一交互意图
   ├─ forms.py                 单字段输入、完整表单与保存
   ├─ data.py                  Catalog、数据快照与关系
   ├─ presentation.py          projected record + display_value
   └─ view.py                  工作台布局与 inspector 编排
       ├─ roster.py
       ├─ inspector.py         共享 target、绘制、换行与滚动
       ├─ detail.py            普通实体内容
       ├─ student_inspector.py 学生档案二维内容
       ├─ editor.py            新建 / 确认 / 文件事务
       └─ dashboard.py
```

`workspace/__init__.py` 只管理生命周期：创建 Catalog 与 Workspace、接收控制事件、执行字段保存 / 刷新和统一错误处理。

`Catalog` 保存当前身份、可用操作和读取快照；界面重绘不查询数据库。写操作通过 Service 进入 Repository。

## 5. 档案内容与展示

`student_inspector.py` 定义学生特有的：

```text
摘要 → 选课与成绩 → 个人信息
```

`detail.py` 定义学院、专业、班级、课程、成绩、公告等普通实体内容。

两者都生成同一种 `Line / Segment` 结构，由 `inspector.py` 统一处理：

- 字段 target；
- 选项展开；
- 中文 / 宽字符换行；
- 点击区域；
- 当前焦点；
- 视口滚动。

`presentation.py` 提供唯一字段展示管线：

```text
数据库记录 + 当前字段临时值
            ↓
      projected record
            ↓
      display_value(...)
            ↓
         inspector
```

浏览和字段修改不能各自实现一套值格式化逻辑。

## 6. 焦点 target 与编辑能力

“可以被选中”和“可以被修改”是两个独立概念。

浏览态每个档案字段拥有稳定 target：

```text
field-target:<field_key>
```

因此只读字段也属于档案空间结构。例如学生 `name`、`student_no` 创建后不可修改，但仍能被方向键选中。

按 Enter 后，事件层再查询当前字段是否 `editable`：

- 可编辑：进入单字段编辑；
- 不可编辑：保持当前 target，只提示该字段只读；
- 学生只读身份：所有字段保持可导航，但不会进入写状态。

字段编辑期间，局部编辑控件使用 `field:<index>`；它只属于当前字段会话，不是另一套档案导航图。保存后重新回到同一个 `field-target:<field_key>`。

## 7. 档案导航

档案导航只有一条主路径：

```text
键盘 ↑↓←→ ─┐
鼠标滚轮 ──┼→ events.move_detail_selection()
            │
            ▼
  inspector.directional_target()
            │
            ▼
        当前渲染几何
```

`events.py` 不知道“学生物种”“元素亲和”等页面细节。空间关系直接从当前 inspector 的 `Line` 结构推导。

普通档案是单列几何：

```text
A
↓
B
↓
C
```

学生档案含二维复合行：

```text
姓名
 ↓
学号
 ↓
族系 ← 支系
       ↓
      性别
      ...
      学籍
       ↓
主元素 ← 亲和
```

纵向进入复合行时选择右侧成员；`← / →` 在同一行移动。位于左成员继续按 `←` 时，`directional_target()` 返回 `None`，工作台据此退出档案并回到名册。

右侧档案未获得焦点时，滚轮只滚动预览；档案获得焦点后，滚轮上下与键盘 `↑ / ↓` 调用同一个 target 导航入口。

## 8. 已有记录字段修改

已有记录不存在独立“编辑页面”或整条记录草稿。

```text
field-target:<key>
      │ Enter
      ▼
当前字段输入 / 选项
      │ Enter
      ▼
校验 → Service → Repository → refresh
      │
      ▼
field-target:<key>
```

规则：

- 文本 / 数字 / 日期字段：Enter 输入，第二次 Enter 立即保存；
- 枚举 / 外键字段：Enter 展开选项，确认选项后立即保存；
- Esc 取消当前字段，不写数据库；
- 字段编辑期间没有记录级“保存”按钮；
- 修改一个字段时，不把全部字段复制成第二套 `form.position` 导航。

学生 `family + branch` 是明确的原子复合字段：修改族系后继续选择支系，最后一次性提交，避免产生不一致的中间状态。

新建记录、删除确认、密码重置、导入 / 导出、seed 属于完整事务，仍然使用 `Form` / `editor.py` 和显式保存或确认。`open_form()` 不提供已有记录的 edit 模式。

## 9. 数据库与数据

`database.py::SCHEMA` 是当前 SQLite 结构的唯一声明。`initialize_database()` 只创建当前结构，不检测旧列、不执行隐式历史迁移。

学生 `birth_date` 支持：

```text
YYYY-MM-DD
YYYY
--MM-DD
NULL
```

独立 `age` 只用于出生资料不足以精确计算年龄时。完整出生日期存在时，年龄实时派生，`age` 不重复保存。

当前项目没有已发布数据库版本兼容承诺；未来若需要迁移，应建立显式版本迁移，不向初始化路径堆叠历史条件分支。

## 10. 测试原则

测试保护当前生产行为，而不是保留历史私有 API。

关键交互应通过真实工作台事件链测试：

- Enter / → 从名册进入档案时选中首 target；
- 姓名、学号可聚焦但不可编辑；
- 学生复合行的上下左右几何；
- 滚轮与方向键在已聚焦档案中得到相同结果；
- 单字段 Enter 即时保存，Esc 取消；
- 已有记录编辑不存在保存按钮；
- 新建 / 删除等完整事务仍保留显式保存或确认；
- seed 测试验证关系和数据语义，不绑定偶然学号或班级位置。
