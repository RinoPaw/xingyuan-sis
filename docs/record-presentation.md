# 档案展示与字段编辑模型

本文档规定记录型工作台的展示值与字段会话。目标不是“让两套页面看起来一样”，而是从模型上保证**不存在两套字段展示逻辑**。

## 1. 唯一展示管线

浏览、文本输入、枚举选择、外键选择都经过：

```text
数据库当前记录
      │
      ├─ 无字段修改 ───────────────┐
      │                           │
      └─ 当前字段临时值 ── overlay │
                                  ▼
                         projected record
                                  │
                                  ▼
                         display_value(...)
                                  │
                                  ▼
                           inspector layout
```

`projected record` 等于已提交记录，加上当前字段会话明确拥有的临时值。

格式化代码不能写成：

```text
if editing:
    使用编辑态格式
else:
    使用浏览态格式
```

## 2. 三种独立概念

档案字段必须区分：

```text
显示值
焦点 target
编辑能力
```

它们彼此独立。

### 显示值

由 `presentation.py` 的 `project_record()` 与 `display_value()` 决定。

### 焦点 target

浏览态每个档案字段都有稳定：

```text
field-target:<field_key>
```

只读字段也必须保留 target，因为它仍然是档案空间的一部分。

### 编辑能力

Enter 激活 target 后，再根据 Schema / Catalog 与当前身份判断字段能否修改。

因此学生姓名、学号可以被选中，但创建后不可编辑；完整出生日期存在时，年龄也可以被选中，但应通过修改出生日期改变派生年龄。

## 3. 字段会话

已有记录的字段修改只拥有：

- 当前字段；
- 当前临时值；
- 必要时的选项列表与选中位置；
- 明确的原子复合字段组。

当前学生 `family + branch` 是复合字段：选择新族系后继续选择支系，最后一次性提交。

字段会话可以改变：

- 当前 target 的样式；
- 选项是否展开；
- Enter / Esc 的局部含义。

它不能改变：

- 未编辑字段的值来源；
- 其他字段格式化方式；
- 档案区块结构；
- 浏览态的稳定 target 身份。

## 4. 完整 Form

完整 Form 只用于天然的多字段或事务操作：

- 新建记录；
- 导入 / 导出；
- 删除确认；
- 密码重置；
- seed。

已有记录不能通过 `open_form(..., "edit")` 再进入一套整条记录编辑页。已有记录只通过当前 `field-target` 打开单字段会话。

## 5. 保存

字段确认后直接沿业务主链：

```text
field session
    ↓
Schema / Service
    ↓
Repository
    ↓
Catalog refresh
    ↓
原 field-target
```

字段编辑期间没有记录级保存按钮。Esc 取消当前字段并保持数据库不变。

## 6. 导航与展示分离

导航使用 inspector 的真实 `Line` 结构，不由字段编辑状态重新生成第二份顺序。

浏览时：

```text
field-target:name
field-target:student_no
field-target:family · field-target:branch
...
```

进入当前字段编辑后，局部控件可暂时使用：

```text
field:0
option:0
option:1
...
```

这些局部 action 只在字段会话期间存在；保存 / 取消后回到原 `field-target:<key>`。

## 7. 回归要求

修改档案或字段编辑时至少验证：

1. 进入字段会话前后，除当前字段临时值与局部控件外，其他文本一致；
2. 同一枚举 / 外键值在浏览和编辑时使用同一 label；
3. 姓名、学号等只读字段仍在焦点图；
4. Enter 不会让只读 target 进入编辑；
5. 编辑字段确认后立即保存并回到原 target；
6. Esc 不写数据库；
7. 字段编辑不存在记录级保存按钮；
8. 复合字段只投影明确拥有的键；
9. 修复某字段不应通过新增页面特判改变其他字段展示。
