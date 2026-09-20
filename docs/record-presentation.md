# 档案展示与字段会话模型

本文档规定记录型工作台的展示、字段身份和局部字段修改。目标不是让“浏览页”“新建页”“编辑页”勉强长得一样，而是让它们在字段层只存在一套交互模型。

## 1. 唯一展示管线

字段展示统一经过：

```text
base values
      │
      ├─ 无 FieldSession ──────────┐
      │                           │
      └─ FieldSession 临时值 ─ overlay
                                  ▼
                         projected values
                                  │
                                  ▼
                         display_value(...)
```

`base values` 可以是数据库当前记录，也可以是完整事务 Form 的草稿。`projected values` 等于基值加上当前 FieldSession 明确拥有的临时值。格式化函数不知道值来自数据库、Form 还是临时输入，因此不能出现 browse/create/edit 三套格式化分支。

关系型展示也遵循同一投影。学生班级在 TUI 中的语义是“专业 + 班号”，数据库内部仍可使用稳定的 `class_code / class_id`；内部关联方式不能泄漏成第二种用户交互。

## 2. 稳定字段身份

用户面对的字段使用语义 key：

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

进入已有记录修改后，当前字段仍然叫同一个 `field:<key>`；新建 Form 也使用字段 key 标识当前项，不使用 `field:<index>` 建一套平行用户身份。索引只允许作为 Form 内部顺序，不成为交互概念。

## 3. FieldSession 与复合字段

所有局部字段修改都由 `FieldSession` 建模。它只拥有：

- 当前字段或明确声明的原子字段组；
- 这些字段的临时值；
- 本次编辑开始时的基值；
- 当前子字段（复合组时）；
- 必要的选项列表与选中位置；
- 确认后写回“已有记录”还是“Form 草稿”的 owner。

学生当前三类复合字段统一使用同一个字段组机制：

```text
family → branch
major_code → class_number
primary_element → primary_affinity
```

选择父项后继续选择同一组的第二项，最后只确认一次原子组。直接进入子字段时，只拥有当前子字段。三组的业务数据来源可以不同，但用户的进入、选择、确认、取消逻辑不能因此分裂。

FieldSession 不拥有整条记录，也不拥有完整事务级保存按钮。

## 4. Form 与 FieldSession 是两个生命周期，不是两套编辑器

完整 `Form` 只用于真正的独立事务：

- 新建记录；
- 删除确认；
- 密码重置；
- 导入 / 导出；
- seed。

Form 拥有整次事务的草稿、字段顺序和最终提交。字段编辑本身仍由 FieldSession 完成：

```text
Form field:<key>
   │ Enter
   ▼
FieldSession(owner=FORM)
   │ Enter
   ▼
写回 Form draft
```

已有记录则是：

```text
archive field:<key>
   │ Enter
   ▼
FieldSession(owner=RECORD)
   │ Enter
   ▼
写入 Service / Repository
```

owner 只决定确认后的目的地，不改变编辑方式。Form 不拥有自己的 `options / option_index / read_value` 字段编辑状态。

学生新建 Form 使用与档案相同的语义字段：`family + branch`、`major_code + class_number`、`primary_element + primary_affinity`。其中班级二元组只在完整事务提交边界转换为内部 `class_code`，Form 不重新暴露“完整班级编号”控件。

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
FieldSession(owner=RECORD)
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

新建事务路径：

```text
Form 中方向键 / Tab 选择字段
   │ Enter
   ▼
FieldSession(owner=FORM)
   │ Enter
   ▼
写回 Form draft
   │
   ├─ 继续选择其他字段
   └─ S 保存完整事务
```

必须遵守：

- 方向键移动到字段不会自动进入编辑；
- Enter 才进入当前字段；
- FieldSession 中 Enter 确认当前字段或原子组；
- FieldSession 中 Esc 只取消当前字段编辑，Form 草稿保持原样；
- 回到 Form 后 Esc 才取消整个新建事务；
- `S` 只负责完整事务保存，不作为字段确认键。

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

`option:*` 只存在于 FieldSession。它不是第二套档案导航，也不会替换当前字段的语义身份；Form 本身不再维护 option 状态。

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

未被 FieldSession 拥有的信息继续使用基值。例如修改学生“入学年份”期间，班级仍保持 `专业 · 班号` 的同一二元结构，学院、学籍、元素、选课和个人信息不会因为存在 FieldSession 而改变展示语义。

修改班级专业时，`Catalog.project()` 只重算这次关系投影真正影响的专业、学院和可选班号；不会把整条记录复制进会话。完整事务保存时再把 `major_code + class_number` 解析到真实班级并转换成内部 `class_code`。

## 10. 回归要求

至少验证：

1. 字段进入 / 退出 FieldSession 前后语义身份不变；
2. 未编辑字段文本不因 FieldSession 存在而变化；
3. 同一枚举 / 关系值始终使用同一 label；
4. 只读字段仍在焦点图，但 Enter 不产生可写 FieldSession；
5. 已有记录 FieldSession 不创建 Form；
6. 已有记录 Enter 即时保存，Esc 不写数据库；
7. 已有记录没有保存按钮；
8. FieldSession 只投影明确拥有的键；
9. 物种、班级、元素三行都由两个独立 `field:<key>` target 组成；
10. 三组复合字段使用同一个字段组推进机制；
11. 学生新建 Form 不重新暴露 `class_code`；
12. 新建 Form 中方向键只移动，Enter 才进入 FieldSession；
13. Form 字段确认只写回草稿，`S` 才提交整条记录；
14. Form 不拥有 `options / option_index` 第二套字段编辑状态；
15. 字段 Esc 与事务 Esc 分属两层生命周期；
16. 绘制、点击和方向导航消费同一份最终几何；
17. 工作台只存在一个 `FocusArea`，不存在 `details + action_focus` 组合焦点；
18. Tab 单向循环名册、档案和操作栏，Shift+Tab 不建立第二条导航路径；
19. 名册渲染与分页使用同一个可见记录容量。
