# xingyuan-sis

星原大学学生信息系统。

这是一个 Python 课程设计项目。数据保存在本地 SQLite 中，交互分为三层：CLI 是稳定的基础接口，Textual TUI 是默认主界面，基础菜单界面用于不适合运行完整 TUI 的终端。

## 技术栈

- Python 3.11+
- SQLite / `sqlite3`
- Textual

## 当前功能

- 学生档案新增、查询、修改、删除
- 学院、专业、班级维护
- 课程维护
- 选课与成绩维护
- 学生全局模糊搜索与结构化字段过滤
- 筛选结果直接输出为 CSV
- 班级人数、主元素分布、课程成绩统计
- 学生 CSV 导入与导出
- CLI / TUI / Basic UI 三种终端交互方式
- 可选的星原大学演示数据 seed

学生档案包含学号、姓名、族系、支系、性别、出生日期、入学年份、班级、学籍状态、主元素亲和与等级等信息。学院和专业通过班级关系获得，不在学生表重复保存。

## 安装

```bash
pip install -e .
```

安装后会提供 `xy` 命令。首次运行会在当前目录的 `data/` 下创建 SQLite 数据库。

## 启动方式

```bash
xy
```

默认启动 Textual TUI。在不适合运行完整 TUI 的交互终端中，会进入基础菜单界面。

也可以显式选择：

```bash
xy --tui
xy --basic
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

筛选结果默认以终端表格显示。指定 `-o / --output` 时会直接写入 CSV 文件：

```bash
xy stu ls --major 元素 -o students.csv
xy stu ls --major 元素 --year 2026 --status 在读 -o element_2026.csv
```

需要把 CSV 输出到 stdout 时使用 `--csv`：

```bash
xy stu ls --major 元素 --csv
xy stu ls --major 元素 --csv > students.csv
```

文件输出使用 UTF-8 with BOM，并沿用 `xy data export` 的学生字段格式，因此可以继续交给 `xy data import` 使用。

不带完整参数执行 `xy stu add`、`xy course add`、`xy grade add` 等命令时，会进入逐项输入模式。

需要临时使用其他数据库时：

```bash
xy --db data/demo.db stu ls
```

## 演示数据

空数据库可以一次写入项目自带的基础数据：

```bash
xy data seed
```

当前 seed 包含 4 个学院、10 个专业、11 个班级、12 名学生、11 门课程和 16 条选课/成绩记录。它用于填充 TUI、CLI 和统计页面，数据关系完整，并包含一名休学学生和一条尚未录入成绩的选课记录。

如果数据库已经存在任何业务数据，普通 `seed` 会拒绝执行，避免覆盖真实内容。需要明确清空并恢复为默认演示数据时才使用：

```bash
xy data seed --reset
```

`--reset` 会删除当前学院、专业、班级、学生、课程和选课数据，然后重新生成整套演示数据。

## 界面层次

```text
CLI ───────┐
TUI ───────┼── XingyuanService ── Repository ── SQLite
Basic UI ──┘
```

TUI 和 Basic UI 都不会通过子进程执行数据库操作。业务编号解析和跨界面共享的操作集中在 `XingyuanService`；Repository 只负责 SQLite 数据访问。学生结构化查询由独立的 `student_filters` 查询层处理，便于 CLI 和未来的 TUI 筛选器共享。

## 测试

```bash
python -m unittest discover -s tests
```

## 项目结构

```text
xingyuan-sis/
├── src/xingyuan_sis/
│   ├── __main__.py       # python -m 入口
│   ├── entry.py          # 统一命令入口与结构化查询分流
│   ├── cli.py            # CLI 命令实现与界面分流
│   ├── student_filters.py# 学生结构化过滤
│   ├── basic_ui.py       # while True + 清屏的备用界面
│   ├── app.py            # Textual 主界面
│   ├── workspace.py      # 总览、学生与学生详情
│   ├── academics.py      # 学院、专业、班级
│   ├── courses.py        # 课程
│   ├── grades.py         # 成绩
│   ├── data_workspace.py # 数据与 CSV
│   ├── seed_data.py      # 默认演示数据
│   ├── service.py        # 跨界面业务接口
│   ├── repository.py     # SQLite 数据访问层
│   ├── database.py       # 连接与表结构初始化
│   ├── reports.py        # 统计查询
│   └── csv_io.py         # CSV 导入导出
├── docs/
│   └── data-model.md
├── tests/
├── CONTRIBUTING.md
├── pyproject.toml
└── README.md
```
