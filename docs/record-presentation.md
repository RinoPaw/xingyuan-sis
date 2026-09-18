# 档案展示与字段会话模型

本文档规定记录型工作台的展示、字段身份和已有记录修改。目标不是让“浏览页”和“编辑页”长得一样，而是从模型上保证**根本不存在第二套已有记录页面**。

## 1. 唯一展示管线

所有已有记录都经过：

```text
数据库当前记录
      │
      ├─ 无 FieldSession ──────────┐
      │                           │
      └─ FieldSession 临时值 ─ overlay
                                  ▼
                         projected record
                                  │
                                  ▼
                         display_value(...)
                                  │
                                  ▼
                           archive content
```

`projected record` 等于已提交记录加上当前 FieldSession 明确拥有的临时值。格式化函数不知道值来自数据库还是临时输入，因此不能出现 browse/edit 两套格式化分支。

关系型展示也遵循同一投影。学生班级在 TUI 中的语义是“专业 + 班号”，数据库内部仍可使用稳定的 `class_code / class_id`；内部关联方式不能泄漏成第二种用户交互。

## 2. 稳定字段身份

每个档案字段从浏览到修改始终使用：

```text
field:<field_key>
```

例如：

```text
field:name
field:student_no
field:family · field:branch
field:major_code · field:class_number
field:primary_element · field:primary_affinity
...
```

只读字段也有稳定 field target。`focusable` 与 `editable` 是独立属性。

进入已有记录修改后，当前字段仍然叫同一个 `field:<key>`；不会变成 `field:<index>`，也不存在 `field-target:<key>` 这一套平行身份。

## 3. FieldSession 与复合字段

已有记录的局部修改由 `FieldSession` 独立建模。它只拥有：

- 当前字段或明确声明的原子字段组；
- 这些字段的临时值；
- 原记录；
- 当前子字段（复合组时）；
- 必要的选项列表与选中位置。

普通字段会话只有一个 key。学生有两类存在父子约束的原子字段组：

```text
family → branch
major_code → class_number
```

选择族系后再选择支系，选择专业后再选择班号，最后各自只提交一次。直接选择 `branch` 或 `class_number` 时，则只修改当前父项下的这个子字段。

元素行同样使用两个独立 target：`primary_element · primary_affinity`。它们没有父子数据约束，因此分别保存；这种业务差异不改变它们与另外两行相同的复合几何和导航语义。

FieldSession 不拥有整条记录，不拥有页面级保存按钮，也不承担新建表单的字段循环。

## 4. Form 与 FieldSession 不是 mode

完整 `Form` 只用于真正的独立事务：

- 新建记录；
- 删除确认；
- 密码重置；
- 导入 / 导出；
- seed。

已有记录修改不通过 `Form(mode="edit")` 表示，也不通过 `mode` 在同一个大状态类型里分叉。两个概念拥有不同生命周期，因此使用不同模型。

学生新建 Form 使用与档案相同的语义字段：`family + branch`、`major_code + class_number`、`primary_element + primary_affinity`。其中班级二元组只在提交边界转换为内部 `class_code`，Form 本身不重新暴露一套“完整班级编号”控件。

## 5. 焦点不是页面状态

记录型工作台只有一个键盘焦点 `FocusArea`：名册、档案或操作栏。Tab 单向循环：

```text
ROSTER → INSPECTOR → TOOLBAR → ROSTER
```

窄屏当前展示哪一面由独立 `ContentPanel` 表示。焦点进入操作栏时，当前名册或档案内容仍保持可见；宽屏则始终同时绘制名册和档案。

因此不存在“进入档案模式”或“进入操作栏模式”。焦点只决定键盘输入交给谁，布局只决定哪些内容可见。

## 6. 保存与取消

已有记录修改路径：

```text
field:<key>
   │ Enter
   ▼
FieldSession
   │
   ├─ 自由文本 / 数字 / 日期输入
   └─ option 列表
   │ Enter
   ▼
Schema / Service
   ↓
Repository
   ↓
Catalog refresh
   ↓
同一个 field:<key>
```

Enter 确认后立即保存；Esc 丢弃 FieldSession，数据库保持原值。字段会话期间没有记录级“保存”按钮。

## 7. 选项是字段的临时子结构

枚举和关系字段展开后临时增加：

```text
field:major_code
  option:0
  option:1
  option:2
```

选择专业后，同一 FieldSession 可继续到：

```text
field:class_number
  option:0
  option:1
  ...
```

`option:*` 只在选项展开期间存在。它不是第二套档案导航，也不会替换当前 `field:<key>` 的身份。

## 8. 最终几何只有一份

档案结构进入 `inspector.py` 后先完成真实终端布局：

```text
content Line[]
    ↓
wrap + compact layout
    ↓
final Line[]
```

同一份 `final Line[]` 同时用于：

- 屏幕绘制；
- 鼠标 HitRegion；
- target 提取；
- `↑↓←→` 空间导航；
- 当前焦点可见性和滚动。

因此窄屏发生换行后，方向键按照用户实际看到的位置移动，而不是按照换行前的隐藏逻辑行移动。

学生的三个复合行都只是普通 `Line` 几何：

```text
物种  family · branch
班级  major  · class_number
元素  element · affinity
```

它们不在 `events.py` 中拥有各自的导航特判。

名册同样从 `WorkspaceLayout.roster_capacity()` 得到真实可见记录数；列标题占用的行只在这里扣除，渲染和 PageUp / PageDown 不维护第二份容量算法。

## 9. 派生信息

未被 FieldSession 拥有的信息继续使用已提交记录。例如修改学生“入学年份”期间，班级仍保持 `专业 · 班号` 的同一二元结构，学院、学籍、元素、选课和个人信息不会因为存在 FieldSession 而改变展示语义。

修改班级专业时，`Catalog.project()` 只重算这次关系投影真正影响的专业、学院和可选班号；不会把整条记录复制进会话。保存时再把 `major_code + class_number` 解析到真实班级并转换成内部 `class_code`。

## 10. 回归要求

至少验证：

1. 字段进入 / 退出 FieldSession 前后 action 身份不变；
2. 未编辑字段文本不因 FieldSession 存在而变化；
3. 同一枚举 / 关系值始终使用同一 label；
4. 只读字段仍在焦点图，但 Enter 不产生 FieldSession；
5. FieldSession 不创建 `Form`；
6. Enter 即时保存，Esc 不写数据库；
7. 已有记录没有保存按钮；
8. 复合字段只投影明确拥有的键；
9. 物种、班级、元素三行都由两个独立 `field:<key>` target 组成；
10. `family → branch` 与 `major_code → class_number` 使用同一原子组机制；
11. 学生新建 Form 不重新暴露 `class_code`，而使用与档案一致的专业 + 班号字段；
12. 绘制、点击和方向导航消费同一份最终几何；
13. 工作台只存在一个 `FocusArea`，不存在 `details + action_focus` 组合焦点；
14. Tab 单向循环名册、档案和操作栏，Shift+Tab 不建立第二条导航路径；
15. 名册渲染与分页使用同一个可见记录容量。
