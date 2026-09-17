# 星原 SIS

一个使用 Python 标准库和 SQLite 实现的本地学生信息系统课程项目。

它同时提供三种使用方式：适合日常操作的终端 TUI、低能力终端下的基础数字菜单，以及适合脚本和精确查询的 CLI。三种入口共享同一套业务服务和数据库，不维护三套业务逻辑。

> 当前定位：课程设计 / 学习项目，不是面向真实学校部署的生产级教务系统。

## 功能概览

- 学生档案：新增、查询、修改、删除
- 学院、专业、班级维护
- 课程维护
- 选课与成绩维护
- 学生模糊搜索与结构化筛选
- table / CSV 输出
- 学生 CSV 导入与导出
- 班级人数、元素分布、成绩进度等统计
- 管理员与学生身份、登录与密码修改
- 可选的“星原大学”演示数据

学生档案支持学号、姓名、族系、支系、性别、年龄、出生资料、入学年份、班级、学籍状态、主元素与亲和等字段。出生资料可以是完整日期 `YYYY-MM-DD`、仅年份 `YYYY` 或仅月日 `--MM-DD`；完整日期存在时年龄实时计算，否则可以保存独立年龄。

## 技术栈

- Python 3.14+
- SQLite / `sqlite3`
- Python 标准库终端交互

没有第三方运行时依赖。

## 快速开始

```bash
git clone https://github.com/RinoPaw/xingyuan-sis.git
cd xingyuan-sis
pip install -e .
xy
```

首次运行会在当前目录的 `data/` 下创建 SQLite 数据库，并引导设置管理员 `Administrator` 的密码。

默认启动时会检测终端能力：支持 TTY、ANSI 和即时按键时进入 TUI，否则自动退回基础数字菜单。也可以显式指定：

```bash
xy --tui
xy --basic
```

临时使用其他数据库：

```bash
xy --db data/demo.db
```

## TUI 使用方式

管理员从“教务”进入学生、学院、专业、班级、课程、成绩和数据工作台。学生账号可以查询学生目录、查看个人数据和修改密码。

宽屏下记录型页面采用“名册 + 档案”双栏；窄屏下仍使用同一个状态机，只改变排布。

常用操作：

- `Tab`：切换名册 / 档案焦点
- `↑ / ↓`：在当前面板移动
- `← / →`：按空间关系移动，或在名册与档案之间切换
- `Enter`：打开当前项 / 编辑当前字段
- `Esc`：取消最内层操作或返回
- `/`：搜索
- `a`：新增
- `e`：把焦点带到第一个可编辑字段
- `d`：删除
- `r`：刷新

已有记录没有单独的“编辑页面”。在档案中选中字段后按 Enter 原地修改，再按 Enter 即时校验并保存；Esc 取消当前字段修改。枚举和外键字段会在原位置展开选项。

学生档案中的“物种（族系 · 支系）”和“元素（主元素 · 亲和）”是二维复合行，因此左右键会在同一行内移动；其他普通档案默认是单列几何。键盘和鼠标滚轮在档案获得焦点后走同一个导航入口。

更完整的交互约定见 [TUI 设计规范](docs/ui-design.md)。

## CLI

CLI 使用业务编号，不要求直接操作数据库内部 ID。

```bash
xy stu ls
xy stu show 20260001
xy stu add
xy stu edit 20260001 --status 休学
xy stu rm 20260001

xy college ls
xy major ls
xy class ls

xy course ls
xy course show ELS101
xy grade ls
xy data stats
```

学生查询支持全字段模糊搜索和结构化过滤：

```bash
xy stu ls --name 林
xy stu ls --branch 牧羊
xy stu ls --major 元素 --year 2026 --status 在读
xy stu ls --element 风 --element 雷 --status 在读
```

同一字段重复时按 OR 组合，不同字段之间按 AND 组合。输出可以选择 table 或 CSV，也可以写入文件：

```bash
xy stu ls --major 元素 --format csv -o students.csv
```

## 演示数据

空数据库可以写入项目自带的演示校园：

```bash
xy data seed
```

当前 seed 包含 4 个学院、10 个专业、26 个班级、114 名学生、20 门课程和 456 条选课 / 成绩记录。

学生角色来自公开作品资料；年龄与出生资料只作为角色资料，不参与入学资格或班级分配。具体来源和记录规则见 [演示数据来源](docs/demo-data-sources.md)。

如果数据库已经存在业务数据，普通 `seed` 会拒绝覆盖。明确需要清空并恢复演示数据时使用：

```bash
xy data seed --reset
```

## 架构

```text
                 ┌─ CLI
entry ───────────┼─ Basic UI
                 └─ TUI
                    │
                    ▼
              Service / Auth
                    │
                    ▼
                Repository
                    │
                    ▼
                  SQLite
```

界面层不直接写 SQL；业务规则集中在 Service / Schema；持久化集中在 Repository。TUI 的键盘和鼠标事件先归一化为统一交互意图，再由当前 inspector 提供自己的空间几何。

详细说明见 [架构文档](docs/architecture.md)。

## 测试

```bash
python -m unittest discover -s tests -v
```

## 文档

- [架构与模块边界](docs/architecture.md)
- [数据模型](docs/data-model.md)
- [TUI 设计规范](docs/ui-design.md)
- [档案展示与字段编辑模型](docs/record-presentation.md)
- [演示数据来源](docs/demo-data-sources.md)
- [设计原则](docs/design-principles.md)
- [参与开发](CONTRIBUTING.md)

## 项目结构

```text
xingyuan-sis/
├── src/xingyuan_sis/
│   ├── cli/                 # CLI 命令
│   ├── tui/                 # 即时键盘终端界面
│   │   └── workspace/       # 工作台状态、事件、表单和面板
│   ├── basic_ui.py          # 基础数字菜单
│   ├── service.py           # 业务服务
│   ├── repository.py        # SQLite 数据访问
│   ├── schema.py            # 字段与校验契约
│   ├── database.py          # 数据库结构与事务
│   ├── csv_io.py            # CSV 导入导出
│   └── seed_data.py         # 演示数据
├── tests/
├── docs/
├── CONTRIBUTING.md
└── pyproject.toml
```
