# 设计原则

本文档是星原 SIS 的规范性设计约束。`architecture.md` 描述当前结构；本文档约束以后怎样修改。出现冲突时，应修正实现与文档，不增加兼容壳隐藏冲突。

## 1. 目标

项目追求小而完整，而不是层数多。结构判断优先看：

1. 一个概念是否只有一个权威实现；
2. 一个用户行为是否只有一条主要生产路径；
3. 依赖方向是否单向、可解释；
4. 页面上看到的空间是否就是导航使用的空间；
5. 测试是否保护当前行为，而不是冻结历史私有 API。

“以后可能有用”“为了保险”“测试还在调用”都不足以让旧实现继续存在。

## 2. 依赖边界

```text
entry
 ├─ CLI
 ├─ Basic UI
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

UI 不写 SQL；Repository 不依赖 UI；业务校验进入 Service / Schema；SQL 进入 Repository；跨层需求沿现有方向扩展。

## 3. 单一权威实现

| 概念 | 权威实现 |
| --- | --- |
| 登录后门户 | `tui/app.py` + `tui/portal.py` |
| 工作台状态 | `tui/workspace/state.py` |
| 键鼠事件意图 | `tui/workspace/events.py` |
| 已有记录字段会话 | `tui/workspace/field_session.py` |
| 完整事务表单 | `tui/workspace/forms.py` + `editor.py` |
| 档案最终几何 / 绘制 / 导航 | `tui/workspace/inspector.py` |
| 学生档案结构 | `tui/workspace/student_inspector.py` |
| 其他实体档案结构 | `tui/workspace/detail.py` |
| 字段展示值 | `tui/workspace/presentation.py` |
| 工作台外层几何 | `tui/layout.py` |
| 文本输入状态 | `tui/text_edit.py::TextBuffer` |
| UI 颜色语义 | `tui/tokens.py` |
| 当前数据库结构 | `database.py::SCHEMA` |
| 业务写操作 | `service.py` |
| SQL 持久化 | `repository.py` |

出现第二套实现时，默认动作是合并或删除，而不是增加同步代码。

## 4. Field 不因编辑改变身份

档案字段必须区分：

```text
focusable
editable
```

每个字段拥有稳定身份：

```text
field:<key>
```

必须遵守：

- 只读字段仍然属于档案焦点图；
- Enter 是否可写由权限和字段定义决定；
- 进入编辑后 target 仍是同一个 `field:<key>`；
- 禁止使用 `field-target:<key>` / `field:<index>` 两套身份表示同一个已有记录字段；
- 字段会话是 target 的局部状态，不建立第二套导航坐标。

## 5. 已有记录没有编辑页面

已有记录的修改只发生在当前字段：

```text
field:<key>
   │ Enter
   ▼
FieldSession
   │ Enter
   ▼
校验 → Service → Repository → 回到同一 field:<key>
```

要求：

- 文本 / 数字 / 日期确认后立即保存；
- 枚举 / 外键确认后立即保存；
- Esc 取消当前 FieldSession；
- 没有记录级保存按钮；
- 不创建 `Form(mode="edit")`；
- 不复制整条记录形成长期草稿；
- 一个字段会话只拥有当前字段；存在真实一致性约束时才允许小型原子字段组。

学生 `family + branch` 是当前明确的原子字段组。

## 6. Form 只表示完整事务

完整 `Form` 只用于：新建、删除确认、密码重置、导入 / 导出、seed 等真正拥有独立生命周期的事务。

FieldSession 与 Form 不通过 `mode` 区分，而是两个不同类型、两条不同职责。不要为了共享几行代码重新把它们合并成一个“大表单状态”。

## 7. 展示只有一条路径

字段文本统一经过：

```text
committed row + optional FieldSession overlay
              ↓
       projected record
              ↓
       display_value(...)
```

格式化函数不能读取 Workspace、焦点或“是否编辑”。禁止：

```text
if editing:
    编辑态格式
else:
    浏览态格式
```

同一个值在浏览、输入、枚举选择期间必须使用同一套 label / 格式规则。

## 8. 几何只有一份

档案必须先得到最终可见几何，再由所有交互消费：

```text
content
  ↓
wrap / compact layout
  ↓
final Line[]
  ├─ render
  ├─ hit testing
  ├─ target extraction
  └─ directional navigation
```

禁止一边按照“原始逻辑行”导航，一边按照换行后的屏幕行绘制。用户看到的空间就是键盘和鼠标使用的空间。

`events.py` 不硬编码学生物种、元素等页面字段。页面差异由真实内容几何表达。

## 9. 数据事实不等于业务规则

演示数据事实不能自动升级为长期业务限制。例如：当前 seed 没有某物种不代表系统禁止该物种；角色年龄很大不代表学生存在年龄门禁；出生资料不完整不代表生日必须完整。

只有需求明确要求长期约束，并且它属于系统业务语义时，才进入 Schema / Service。

## 10. 新抽象准入

新增模块、helper、wrapper、adapter 前，至少应满足一项：表达稳定可命名的概念；被多个当前生产路径同义复用；切断真实依赖耦合；拥有独立生命周期或状态模型。

以下理由单独出现不成立：“以后可能复用”“看起来更企业级”“为了兼容旧私有函数”“测试还在调用”“只有一行转发，留着更安全”。没有新增语义的薄 wrapper 应删除。

## 11. 兼容与迁移

当前项目没有已发布数据库版本兼容承诺。`initialize_database()` 只创建当前 schema，不隐式修补旧数据库。未来若需要迁移，应显式定义版本边界、迁移步骤、失败行为和删除时机。

源码目录、私有函数、内部 action 名称、颜色 token 同样默认不承诺历史兼容。

## 12. 测试策略

测试保护行为，不保护旧实现形状：

- 不因旧测试调用私有 helper 而恢复废弃入口；
- 交互回归优先走真实 `events.interact()`；
- 已有记录编辑验证 `field:<key> → FieldSession → 保存/取消 → field:<key>`；
- 必须验证只读字段仍可聚焦；
- 必须验证已有记录没有保存按钮和 Form edit；
- 鼠标 / 键盘等价行为比较最终状态；
- 最终几何测试同时约束绘制、命中区和方向导航；
- seed 测试不绑定偶然数据位置。

## 13. CI 原则

优先运行与修改范围直接相关的测试。只有跨模块架构调整、数据库 / Service / Repository 主链修改、核心交互状态机修改，或定向测试暴露系统性不确定性时，才值得跑完整 CI。纯文档、纯数据和局部低风险修改不机械触发完整回归。

## 14. 修改前检查

结构性修改合并前回答：

1. 这是不是已有概念？为什么不能扩展权威实现？
2. 是否产生第二条生产路径？
3. target 身份是否因“编辑”发生变化？
4. FieldSession 是否错误扩大成整条记录 Form？
5. 展示是否出现 browse/edit 两套格式？
6. 导航是否消费和绘制相同的最终几何？
7. 是否为了旧测试保留无语义 wrapper？
8. 是否把演示数据事实写成长期业务限制？
9. 文档是否描述当前真实实现？
