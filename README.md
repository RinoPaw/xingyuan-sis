# xingyuan-sis

星原大学学生信息系统。

这是一个 Python 课程设计项目。数据保存在本地 SQLite 中。默认使用轻量即时键盘菜单；在方向键等终端交互不可靠时，可切换到数字输入的基础菜单；CLI 用于结构化查询、脚本和精确控制。

## 技术栈

- Python 3.14+
- SQLite / `sqlite3`
- Python 标准库终端交互

没有第三方运行时依赖。

## 当前功能

- 学生档案新增、查询、修改、删除
- 学院、专业、班级维护
- 课程维护
- 选课与成绩维护
- 学生全局模糊搜索与结构化字段过滤
- 筛选结果支持 table / CSV 输出
- 班级人数、主元素分布、课程成绩统计
- 学生 CSV 导入与导出
- 可选的星原大学演示数据 seed

学生档案包含学号、姓名、族系、支系、性别、出生日期、入学年份、班级、学籍状态、主元素亲和与等级等信息。学院和专业通过班级关系获得，不在学生表重复保存。

## 安装

```bash
pip install -e .
```

安装后会提供 `xy` 命令。首次运行会在当前目录的 `data/` 下创建 SQLite 数据库。

## 启动

```bash
xy
```

默认进入“星原教务台”即时键盘菜单。首页采用青色球面、金色双环与运动光点组成的动态星球，左侧是编号导航和校园概览。移动选项时，右侧展示对应模块的用途与操作。宽屏顶部显示当前数据库文件名。

```text
✦ 星原 / 教务台

› 1  学生
  2  教务
  3  课程
  4  成绩
  5  数据
  0  退出

↑↓/jk 移动  Enter/Space 打开  1–5 直达  p 暂停  q/0 退出
```

子菜单使用同样的交互方式，顶部显示当前位置；`Esc`、`q`、`0` 或 Backspace 返回，Home / End 跳到首项 / 末项。返回菜单时保留上次选中的位置。首页按 `p` 暂停或播放星轨动画，本次运行中会记住设置；动画随窗口缩放，小窗口保留缩小的星球。快捷栏固定在终端最后一行，按可用宽度精简提示；Termux 缩放时直接读取 PTY 的实际尺寸。高亮使用明确的前景/背景色，逐行重绘时先重置颜色并清除旧内容，避免空白区域残留高亮。

两种菜单都支持以下操作：

- **搜索**：学生菜单可按学号、姓名、班级等查找；成绩菜单可按学生、课程和学期查找。
- **分页阅读**：较长的列表、详情和统计自动分页；Enter / `n` 下一页，`p` 上一页，`q` 返回。长行按终端宽度折行，保留完整内容。CLI 直接输出仍适合重定向和脚本使用。
- **取消操作**：在表单、编号输入和结果页面按 Ctrl+C 返回当前菜单；在子菜单按 Ctrl+C 返回上级，在首页按 Ctrl+C 退出。
- **就地纠错**：编辑年份、学分、课时、成绩时，输入无效数字会提示重填；留空保持原值，成绩可输入 `-` 清空。
- **基础菜单提示**：输入不存在的编号会提示重选，也可以输入 `q` 返回。基础菜单的数据页同样提供演示数据入口。

如果当前终端的方向键、转义序列或即时按键读取不可靠，可以显式使用基础菜单：

```bash
xy --basic
```

基础菜单采用最朴素的 `while True + 清屏 + 输入数字`：

```text
✦ 星原 / 教务台
首页 / 工作区

1. 学生
2. 教务
3. 课程
4. 成绩
5. 数据
0. 退出

输入编号 · q 退出 >
```

`python -m xingyuan_sis` 和旧命令 `xingyuan-sis` 使用同一入口。

## CLI

CLI 使用业务编号，不要求用户接触数据库内部 ID。

```bash
xy stu ls
xy stu show 20260001
xy stu add
xy stu edit 20260001 --status 休学
xy stu rm 20260001

xy acad college ls
xy acad major ls
xy acad class ls

xy course ls
xy course show ELS101
xy course add

xy grade ls
xy grade add 20260001 ELS101 --semester 2026-2027-1 --score 92
xy grade edit 20260001 ELS101 2026-2027-1 --score 95

xy data stats
xy data export data/students.csv
xy data import data/students.csv
```

`xy stu ls` 保留 `-s / --search` 作为全字段模糊搜索，同时支持结构化过滤：

```bash
xy stu ls --branch 牧羊
xy stu ls --class 2601
xy stu ls --major 元素 --year 2026 --status 在读
xy stu ls --college 工程 --element 风
xy stu ls --affinity A
xy stu ls --name 林
xy stu ls --major 元素 -s 岚
```

可用字段包括 `--no`、`--name`、`--family`、`--branch`、`--class`、`--major`、`--college`（也可写 `--department`）、`--year`、`--status`、`--element` 和 `--affinity`。

文本字段使用包含匹配；`--class`、`--major` 和 `--college` 会同时匹配对应的业务编号和名称。`--no` 与 `--year` 保持精确匹配。不同字段之间按 AND 组合；同一个字段可以重复，此时按 OR 组合。例如：

```bash
xy stu ls --element 风 --element 雷 --status 在读
```

表示“主元素包含风或雷，并且状态包含在读”。

输出格式和输出位置彼此独立。`--format` 指定表示格式，默认使用适合命令行阅读的 `table`；`-o / --output` 指定输出文件，省略时写到 stdout：

```bash
xy stu ls --major 元素
xy stu ls --major 元素 --format csv
xy stu ls --major 元素 -o students.txt
xy stu ls --major 元素 --format csv -o students.csv
```

`--format csv` 沿用 `xy data export` 的学生字段格式，因此可以继续交给 `xy data import` 使用。CSV 文件输出使用 UTF-8 with BOM；table 文件使用 UTF-8。

不带完整参数执行 `xy stu add`、`xy course add`、`xy grade add` 等命令时，会进入逐项输入模式。

需要临时使用其他数据库时：

```bash
xy --db data/demo.db
xy --db data/demo.db --basic
xy --db data/demo.db stu ls
```

## 演示数据

空数据库可以一次写入项目自带的基础数据：

```bash
xy data seed
```

当前 seed 包含 4 个学院、10 个专业、11 个班级、12 名学生、11 门课程和 16 条选课/成绩记录。它用于填充菜单、CLI 和统计查询，数据关系完整，并包含一名休学学生和一条尚未录入成绩的选课记录。

如果数据库已经存在任何业务数据，普通 `seed` 会拒绝执行，避免覆盖真实内容。需要明确清空并恢复为默认演示数据时才使用：

```bash
xy data seed --reset
```

`--reset` 会删除当前学院、专业、班级、学生、课程和选课数据，然后重新生成整套演示数据。

## 结构

```text
Keyboard Menu ─┐
Basic Menu ─────┼── XingyuanService ── Repository ── SQLite
CLI ────────────┘
```

两个菜单都不会启动子进程；它们只是把用户操作转换成项目本身的 CLI / service 调用。学生结构化查询由独立的 `student_filters` 查询层处理。

## 测试

```bash
python -m unittest discover -s tests
```

## 项目结构

```text
xingyuan-sis/
├── src/xingyuan_sis/
│   ├── __main__.py        # python -m 入口
│   ├── entry.py           # 统一入口与学生结构化查询分流
│   ├── menu.py            # ↑↓ + Space 的默认即时键盘菜单
│   ├── basic_ui.py        # while True + 清屏 + 数字输入备用菜单
│   ├── terminal_ui.py     # 两种菜单共用的分页、搜索与输入辅助
│   ├── cli.py             # CLI 命令实现
│   ├── student_filters.py # 学生结构化过滤
│   ├── seed_data.py       # 默认演示数据
│   ├── service.py         # 业务接口
│   ├── repository.py      # SQLite 数据访问层
│   ├── database.py        # 连接与表结构初始化
│   ├── reports.py         # 统计查询
│   └── csv_io.py          # CSV 导入导出
├── docs/
│   └── data-model.md
├── tests/
├── CONTRIBUTING.md
├── pyproject.toml
└── README.md
```
