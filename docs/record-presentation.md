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
field:gender
...
```

只读字段也有稳定 field target。`focusable` 与 `editable` 是独立属性。

进入已有记录修改后，当前字段仍然叫同一个 `field:<key>`；不会变成 `field:<index>`，也不存在 `field-target:<key>` 这一套平行身份。

## 3. FieldSession

已有记录的局部修改由 `FieldSession` 独立建模。它只拥有：

- 当前字段或明确声明的原子字段组；
- 这些字段的临时值；
- 原记录；
- 当前子字段（复合组时）；
- 必要的选项列表与选中位置。

普通字段会话只有一个 key。学生 `family + branch` 因为存在一致性约束，作为一个原子字段组：先选族系，再选支系，最后一次提交。

FieldSession 不拥有整条记录，不拥有页面级保存按钮，也不承担新建表单的字段循环。

## 4. Form 与 FieldSession 不是 mode

完整 `Form` 只用于真正的独立事务：

- 新建记录；
- 删除确认；
- 密码重置；
- 导入 / 导出；
- seed。

已有记录修改不通过 `Form(mode="edit")` 表示，也不通过 `mode` 在同一个大状态类型里分叉。两个概念拥有不同生命周期，因此使用不同模型。

## 5. 保存与取消

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

## 6. 选项是字段的临时子结构

枚举和外键展开后临时增加：

```text
field:class_code
  option:0
  option:1
  option:2
```

`option:*` 只在选项展开期间存在。它不是第二套档案导航，也不会替换 `field:class_code` 的身份。

## 7. 最终几何只有一份

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

## 8. 派生信息

未被 FieldSession 拥有的信息继续使用已提交记录。例如修改学生“入学年份”期间：

- 入学年份可显示当前临时值；
- 班级仍使用同一 `display_value()` 展示“班级名称 · 编号”；
- 学院、学籍、元素、选课和个人信息不改变展示语义。

只有保存成功并刷新 Catalog 后，真正依赖被修改数据的派生信息才随数据库事实更新。

## 9. 回归要求

至少验证：

1. 字段进入 / 退出 FieldSession 前后 action 身份不变；
2. 未编辑字段文本不因 FieldSession 存在而变化；
3. 同一枚举 / 外键值始终使用同一 label；
4. 只读字段仍在焦点图，但 Enter 不产生 FieldSession；
5. FieldSession 不创建 `Form`；
6. Enter 即时保存，Esc 不写数据库；
7. 已有记录没有保存按钮；
8. 复合字段只投影明确拥有的键；
9. 绘制、点击和方向导航消费同一份最终几何；
10. 修复一个字段不能通过页面特判改变其他字段结构或展示。
