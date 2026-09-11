# Contributing

这个项目按 GitHub Issue 分工。第一次接触 Git / GitHub 时，只需要掌握下面这套流程。

## 开始一个任务

```bash
git switch main
git pull
git switch -c issue/<编号>-<简短名称>
```

例如处理 Issue #13：

```bash
git switch -c issue/13-student-fields
```

## 完成修改

```bash
git status
git add .
git commit -m "feat: ..."
git push -u origin issue/<编号>-<简短名称>
```

然后在 GitHub 上创建 Pull Request，请求合并到 `main`。

## 约定

- 不直接在 `main` 上开发。
- 一个分支尽量只处理一个 Issue。
- 开始新任务前先更新 `main`。
- 不对共享分支使用 `git push --force`。
- 不确定怎么处理冲突时先停下，不要随意删除别人的代码。

Issue 的描述里会写清需要修改的范围和完成标准，优先按 Issue 做，不需要先理解整个项目。
