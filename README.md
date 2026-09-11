# xingyuan-sis

星原大学学生信息管理系统。

这是一个 Python 课程设计项目，目标是实现一个基于终端用户界面（TUI）的本地学生信息管理系统。

## 技术栈

- Python 3.11+
- SQLite：本地数据持久化
- `sqlite3`：数据库访问
- Textual：终端用户界面（TUI）

## 计划功能

- 学生基本信息管理：新增、查看、修改、删除
- 学院、专业与班级信息管理
- 课程与成绩管理
- 按学号、姓名、班级、专业等条件查询
- 学生列表筛选与排序
- 班级人数、成绩等基础统计
- CSV 数据导入与导出

## 学生信息

学生档案计划包含学号、姓名、族系、支系、性别、出生日期、学院、专业、班级、入学年份、学籍状态，以及主元素亲和等信息。

## 运行

```bash
pip install -e .
python -m xingyuan_sis
```

## 项目结构

```text
xingyuan-sis/
├── src/xingyuan_sis/
│   ├── __main__.py      # 程序入口
│   ├── app.py           # Textual 主界面
│   └── database.py      # SQLite 连接与初始化
├── CONTRIBUTING.md      # 小组协作流程
├── pyproject.toml
└── README.md
```

当前已经完成基础框架，具体数据模型和业务功能将通过 Issues 逐步实现。
