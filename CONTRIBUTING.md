# Contributing

欢迎一起完善星原 SIS。这个项目以 GitHub Issue / Pull Request 为主要协作方式；不要求先理解整个代码库，但修改应尊重现有模块边界。

## 开始开发

```bash
git clone https://github.com/RinoPaw/xingyuan-sis.git
cd xingyuan-sis
pip install -e .
```

从最新 `main` 创建自己的分支：

```bash
git switch main
git pull
git switch -c issue/<编号>-<简短名称>
```

例如：

```bash
git switch -c issue/13-student-fields
```

完成后提交并推送：

```bash
git status
git add .
git commit -m "feat: ..."
git push -u origin issue/<编号>-<简短名称>
```

然后创建 Pull Request 合并到 `main`。

## 先看这些边界

项目的主依赖方向是：

```text
CLI / Basic UI / TUI
          ↓
     Service / Auth
          ↓
      Repository
          ↓
        SQLite
```

因此：

- UI 不直接写 SQL；
- Repository 不依赖 UI；
- 新业务规则优先放进 Service / Schema；
- 新 SQL 只进入 Repository；
- CLI、Basic UI、TUI 应复用同一业务实现；
- 已有记录的编辑发生在当前档案中，不另建第二套“编辑页面”；
- 工作台事件层只处理统一交互意图，页面自己的空间导航由 inspector 几何决定。

完整说明见 [架构文档](docs/architecture.md) 和 [设计原则](docs/design-principles.md)。涉及 TUI 时再看 [TUI 设计规范](docs/ui-design.md)。

## 测试

优先运行与你修改范围直接相关的测试。跨模块重构、数据库 / Service / Repository 主链修改或核心交互状态机修改，再运行完整测试：

```bash
python -m unittest discover -s tests -v
```

测试保护当前稳定行为，不应为了保留已经退出生产路径的私有函数或旧实现而增加兼容层。

## 协作约定

- 不直接在 `main` 上开发；
- 一个分支尽量只处理一个 Issue；
- 开始新任务前先更新 `main`；
- 不对共享分支使用 `git push --force`；
- 不确定冲突如何处理时先停下确认，不随意删除别人的代码；
- 不把一次性的演示数据要求升级成永久业务规则；
- 不为了“看起来更架构化”增加没有实际职责的接口、注册表或包装层；
- 修改文档时描述当前真实行为，不保留已经淘汰的路径说明。

如果 Issue 已经给出了修改范围和完成标准，优先按 Issue 完成，不需要先重构无关代码。
