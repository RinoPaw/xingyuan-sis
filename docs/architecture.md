# 架构与模块边界

星原 SIS 使用单向、可解释的依赖结构。三个入口共享同一套业务逻辑和持久化层：

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

学院、专业、班级、学生、课程和成绩都是一级业务实体。新增 CLI 功能时，应复用现有 Service，而不是在 CLI 中复制业务实现。

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
```

`workspace/__init__.py` 只负责生命周期、控制事件、刷新和统一错误处理。

`events.py` 不应知道“学生物种”“课程字段”等页面细节。它接收键盘、鼠标等输入后，只产生通用导航或操作意图。

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

## 7. 档案展示与字段编辑

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
