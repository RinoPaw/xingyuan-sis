# xingyuan-sis

星原大学学生信息系统。

这是一个 Python 课程设计项目。数据保存在本地 SQLite 中。默认使用轻量即时键盘菜单；启动时会检测终端是否具备 TTY、ANSI 输出和即时按键输入能力，不满足时自动切换到数字输入的基础菜单；CLI 用于结构化查询、脚本和精确控制。

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

默认先检测当前终端能力。支持 TTY、ANSI 输出和即时按键读取时进入“星原教务台”即时键盘菜单；否则自动进入基础菜单。也可以显式指定：

```bash
xy --tui
xy --basic
```

`--tui` 强制进入即时键盘界面，`--basic` 强制进入数字输入菜单。

首次使用会引导设置管理员账号 `Administrator` 的密码。登录后，首页、教务和个人中心共用应用页头、暗色背景、柔和蓝色焦点和统一底栏；数据库文件名显示在页头右侧。

```text
✦ 星原 SIS                                      LOCAL / xingyuan.db

导航                    星原学生信息系统
▌ 首页                  Administrator · 管理员
  教务
  个人中心
  退出登录
```

管理员从“教务”进入学生、学院、专业、班级、课程、成绩和数据工作台。学生账号可以查询学生目录、查看个人数据和修改密码。

- **学生**：名册与档案联动，档案按摘要、选课与成绩、个人信息排列。
- **课程与成绩**：浏览关联记录，切换全部、待录入、已评分等视图；视图数量附在对应选项旁。
- **教务**：在学院、专业、班级之间切换，沿关联记录浏览校园组织。
- **数据**：查看元素分布、班级人数和成绩进度，导入、导出 CSV 或建立演示校园。

宽屏使用名册与档案双栏；窄屏点击记录或按 Enter / Tab 展开档案。短窗口会让当前菜单项、字段或档案操作保持可见。缩小时优先保留所有视图入口，再简化标签。方向键与滚轮浏览，Tab 切换焦点，Home / End 跳到首项 / 末项；`/` 搜索，`a` 新建，`e` 编辑，`d` 删除，`r` 刷新。

`Esc` 统一返回或取消当前层。编辑字段只改变草稿，`s` 保存后生效；关联字段显示名称与业务编号，可从列表选择。删除和演示数据操作需要确认。沿关联记录浏览后返回，会恢复原记录、筛选、滚动位置和档案焦点，即使记录编号已修改。

表单、CLI 和 CSV 共用必填项、日期与数值校验：日期采用有效的 `YYYY-MM-DD`，年份为 1900～9999，成绩为 0～100 或空值；`NaN`、无穷值和非整数课时会明确报错。CSV 保留逐行错误报告，合法行可以正常导入。

首页按 `p` 暂停或播放动画，本次运行会记住设置。应用在独立终端屏幕中运行，退出时恢复原屏幕，不修改宿主终端主题。设置 `NO_COLOR` 可禁用颜色，当前项仍通过 `▌`、`▏`、`›` 等标记区分。

代码结构和扩展边界见 [项目结构](docs/architecture.md)。

基础菜单和共享输出辅助仍支持以下操作：

- **点击与滚轮**：默认键盘菜单支持点击首页导航、路径中的上级页面、名册行和底栏按钮；滚轮可切换菜单选项、滚动查询结果。需要终端发送 SGR 鼠标事件；不支持时仍可使用数字键和方向键。文本输入时关闭鼠标捕获，保留中文输入与粘贴。
- **输入框**：默认键盘菜单的表单使用深灰输入行和浅色文字，使用支持 Esc 取消的单行编辑器；基础菜单和直接 CLI 保留朴素输入。
- **搜索**：学生菜单可按学号、姓名、班级等查找；成绩菜单可按学生、课程和学期查找。
- **分页阅读**：较长的列表、详情和统计自动分页；Enter / `n` 下一页，`p` 上一页，`q` 返回。默认键盘菜单的结果页支持点击底栏翻页、方向键或滚轮逐行滚动；缩放时重新折行并尽量保持阅读位置。CLI 直接输出仍适合重定向和脚本使用。
- **取消操作**：在表单、编号输入和结果页面按 Ctrl+C 返回当前菜单；在工作台浏览时按 Ctrl+C 返回首页，在首页按 Ctrl+C 退出。
- **就地纠错**：编辑年份、学分、课时、成绩时，输入无效数字会提示重填；留空保持原值，成绩可输入 `-` 清空。
- **基础菜单提示**：输入不存在的编号会提示重选，也可以输入 `q` 返回。基础菜单的数据页同样提供演示数据入口。

基础菜单采用最朴素的 `while True + 清屏 + 输入数字`：

```text
✦ 星原 / 教务台
首页

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

CLI 使用业务编号，不要求用户接触数据库内部 ID。学院、专业、班级与学生、课程、成绩一样，都是一级命令：

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
xy --db data/demo.db --tui
xy --db data/demo.db stu ls
```

## 演示数据

空数据库可以一次写入项目自带的基础数据：

```bash
xy data seed
```

当前 seed 包含 4 个学院、10 个专业、26 个班级、88 名学生、20 门课程和 352 条选课/成绩记录。学生角色只要求来源明确；年龄仅作为角色资料，不限制入学，具体来源和年龄处理见 [演示数据来源](docs/demo-data-sources.md)。

如果数据库已经存在任何业务数据，普通 `seed` 会拒绝执行，避免覆盖真实内容。需要明确清空并恢复为默认演示数据时才使用：

```bash
xy data seed --reset
```

`--reset` 会删除当前学院、专业、班级、学生、课程和选课数据，然后重新生成整套演示数据。

## 结构

```text
                 ┌─ CLI
entry ───────────┼─ Basic UI
                 └─ TUI
                    │
                    ▼
              XingyuanService
                    │
                    ▼
                Repository
                    │
                    ▼
                  SQLite
```

CLI、基础菜单和 TUI 只是三个入口，共享同一套业务服务与持久化。CLI 自身收在 `cli/` 子包中；TUI 工作台收在 `tui/workspace/` 子包中，学生档案只有 `student_inspector.py` 一份实现。完整依赖与扩展约定见 [架构文档](docs/architecture.md)。

## 测试

```bash
python -m unittest discover -s tests
```

## 项目结构

```text
xingyuan-sis/
├── src/xingyuan_sis/
│   ├── __main__.py              # python -m 入口
│   ├── entry.py                 # 唯一入口与终端模式选择
│   ├── cli/                     # parser + 各业务域 CLI runner
│   ├── tui/
│   │   └── workspace/           # state / events / forms / data / view / panels
│   ├── basic_ui.py              # 数字输入备用菜单
│   ├── terminal_ui.py           # 基础菜单 / CLI 输出与分页
│   ├── terminal_input.py        # 普通输入与 TUI 单行编辑
│   ├── student_filters.py       # 学生结构化过滤
│   ├── student_query.py         # 学生查询语法
│   ├── seed_data.py             # 默认演示数据
│   ├── schema.py                # 表单、服务与 CSV 共用字段契约
│   ├── service.py               # 业务接口
│   ├── repository.py            # SQLite 数据访问层
│   ├── database.py              # 当前表结构、连接与事务
│   ├── reports.py               # 统计查询
│   └── csv_io.py                # CSV 导入导出
├── docs/
│   ├── architecture.md          # 模块职责、数据流与扩展约定
│   ├── data-model.md
│   └── demo-data-sources.md     # 演示角色、年龄与物种来源
├── tests/
├── CONTRIBUTING.md
├── pyproject.toml
└── README.md
```
