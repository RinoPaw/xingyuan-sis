# xingyuan-sis

星原大学学生信息管理系统。

这是一个 Python 课程设计项目，使用 SQLite 保存数据，并通过 Textual 提供终端用户界面（TUI）。

## 技术栈

- Python 3.11+
- SQLite / `sqlite3`
- Textual

## 当前功能

- 学生信息新增、查询、修改、删除
- 学院、专业、班级管理
- 课程管理
- 选课与成绩管理
- 学号、姓名、班级、专业、元素亲和等学生信息搜索
- 班级人数统计
- 主元素亲和分布统计
- 课程平均分、最高分、最低分统计
- 学生 CSV 导入与导出

学生档案包括学号、姓名、族系、支系、性别、出生日期、入学年份、班级、学籍状态，以及主/次元素亲和等信息。学院和专业通过班级关系关联，不在学生表中重复保存。

## 运行

```bash
pip install -e .
python -m xingyuan_sis
```

首次运行会在当前目录的 `data/` 下创建 SQLite 数据库。

也可以使用安装后的命令：

```bash
xingyuan-sis
```

## 测试

安装项目后运行：

```bash
python -m unittest discover -s tests
```

测试覆盖数据库初始化、主要 CRUD、成绩统计和学生 CSV 导入导出流程。

## 项目结构

```text
xingyuan-sis/
├── src/xingyuan_sis/
│   ├── __main__.py       # 程序入口
│   ├── app.py            # Textual 主界面与页面导航
│   ├── views.py          # 学生、教务、课程和成绩页面
│   ├── reports_view.py   # 查询统计与 CSV 页面
│   ├── database.py       # SQLite 连接与表结构初始化
│   ├── repository.py     # 数据访问层
│   ├── reports.py        # 统计查询
│   └── csv_io.py         # CSV 导入导出
├── docs/
│   └── data-model.md     # 数据模型说明
├── tests/                # 核心数据流程测试
├── CONTRIBUTING.md
├── pyproject.toml
└── README.md
```
