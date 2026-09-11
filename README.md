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
- 学号、姓名、班级、专业、元素亲和等学生信息搜索
- 班级人数、主元素分布、课程成绩统计
- 学生 CSV 导入与导出
- CLI / TUI / Basic UI 三种终端交互方式

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
xy course show ELM101
xy course add

xy grade ls
xy grade add 20260001 ELM101 --semester 2026-2027-1 --score 92
xy grade edit 20260001 ELM101 2026-2027-1 --score 95

xy data stats
xy data export data/students.csv
xy data import data/students.csv
```

不带完整参数执行 `xy stu add`、`xy course add`、`xy grade add` 等命令时，会进入逐项输入模式。

需要临时使用其他数据库时：

```bash
xy --db data/demo.db stu ls
```

## 界面层次

```text
CLI ───────┐
TUI ───────┼── XingyuanService ── Repository ── SQLite
Basic UI ──┘
```

TUI 和 Basic UI 都不会通过子进程执行数据库操作。业务编号解析和跨界面共享的操作集中在 `XingyuanService`；Repository 只负责 SQLite 数据访问。

## 测试

```bash
python -m unittest discover -s tests
```

## 项目结构

```text
xingyuan-sis/
├── src/xingyuan_sis/
│   ├── __main__.py       # python -m 入口
│   ├── cli.py            # xy 命令与界面分流
│   ├── basic_ui.py       # while True + 清屏的备用界面
│   ├── app.py            # Textual 主界面
│   ├── workspace.py      # 总览、学生与学生详情
│   ├── academics.py      # 学院、专业、班级
│   ├── courses.py        # 课程
│   ├── grades.py         # 成绩
│   ├── data_workspace.py # 数据与 CSV
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
