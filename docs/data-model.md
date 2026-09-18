# 数据模型

当前第一版使用 SQLite，实体关系保持简单，优先满足课程设计中的增删改查、查询和统计。

## 学院 departments

- `id`：内部主键
- `code`：学院编号，唯一
- `name`：学院名称，唯一

## 专业 majors

- `id`：内部主键
- `code`：专业编号，唯一
- `name`：专业名称
- `department_id`：所属学院

同一学院内专业名称不能重复。

## 班级 classes

- `id`：内部主键
- `code`：班级编号，唯一
- `name`：班级名称
- `major_id`：所属专业
- `enrollment_year`：入学年份

同一专业、同一入学年份下班级名称不能重复。

## 学生 students

- `id`：内部主键
- `student_no`：学号，只含 `0–9` 的非空字符串，保留前导零，唯一，创建后不可修改
- `name`：姓名，创建后不可修改
- `species_branch_id`：种族支系外键；`family`、`branch` 由支系与族系关联查询得到
- `gender`：性别，可空
- `birth_date`：出生日期，ISO 日期字符串，可空
- `enrollment_year`：入学年份
- `class_id`：所属班级，可空
- `status`：学籍状态，默认“在读”
- `primary_element`：主元素亲和，可空
- `primary_affinity`：主亲和等级，可空
- `contact`：联系方式，可空
- `dormitory`：宿舍，可空
- `notes`：备注，可空
- `password_hash`：登录密码散列，不参与档案查询或 CSV 导出
- `must_change_password`：首次登录 / 重置后要求改密

学院和专业不在学生表重复保存，通过班级 → 专业 → 学院关系获得。

## 课程 courses

- `id`：内部主键
- `course_code`：课程编号，唯一
- `name`：课程名称
- `department_id`：开课学院，可空
- `credits`：学分，非负
- `hours`：课时，非负

## 选课与成绩 enrollments

- `id`：内部主键
- `student_id`：学生
- `course_id`：课程
- `semester`：学期，例如 `2026-2027-1`
- `score`：百分制成绩，可空；为空表示尚未录入成绩

同一学生、同一课程、同一学期只能存在一条记录。

## 班级公告 announcements

- `id`：公告编号
- `title`、`body`：必填标题与正文，正文可包含换行
- `class_id`：所属班级，必填
- `created_at`：UTC 发布时间，ISO 格式

按发布时间和编号倒序显示。学生根据当前 `class_id` 查询本班公告，未分班时没有可见公告；转班后随班级关系切换。管理员可发布、阅读、删除，发布后的内容不原地修改。

## 元素亲和

第一版只在学生档案保存主元素亲和及等级，用于展示、筛选和统计。若以后需要记录多元素适性或历次测定结果，再增加独立测定表。

## 删除规则

- 已被专业引用的学院不能直接删除。
- 已被班级引用的专业不能直接删除。
- 删除班级时，学生的 `class_id` 置空，该班公告级联删除。
- 删除学生或课程时，对应选课记录级联删除。

这些规则由 SQLite 外键约束保证。
