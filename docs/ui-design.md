# Terminal UI 设计规范

本文档定义星原 SIS 交互式终端界面的视觉语义。规范采用成熟设计系统中的 **semantic / functional token** 思路，再根据终端的 ANSI 颜色、等宽字符和有限交互能力做适配。

## 1. 参考基线

本规范主要参考：

- [GitHub Primer — Color usage](https://primer.style/product/getting-started/foundations/color-usage/)：采用 Base → Functional → Component/Pattern 的 token 分层。布局代码优先使用语义/功能 token，不直接依赖原始色号。
- [IBM Carbon — Color tokens](https://carbondesignsystem.com/elements/color/tokens/)：参考 `text-primary`、`text-secondary`、`border-subtle`、`background` 等按角色命名的颜色体系，以及“标题属于 primary text、标签属于 secondary text”的层级关系。
- [Charm Lip Gloss](https://github.com/charmbracelet/lipgloss)：参考终端环境对 ANSI 16、ANSI 256、TrueColor 和自适应颜色的能力边界。星原 SIS 当前直接输出 ANSI，不依赖 Lip Gloss 本身。

这些系统提供的是设计方法和语义模型。星原 SIS 的具体色号、动画和排版仍属于本项目自己的视觉语言。

## 2. 核心原则

**先决定信息角色，再决定视觉值。**

代码和设计讨论中应使用 `text-primary`、`text-secondary`、`text-accent`、`surface-*`、`border-subtle` 这样的语义角色。`xterm 252`、`xterm 245` 等数字只是当前暗色主题的一种实现，不承担语义。

同一个原始颜色可以服务多个相近角色，但不能因为“看起来差不多”就把不同信息层级合并。反过来，同一个语义 token 将来可以在不同终端能力或主题下映射到不同色值。

## 3. 语义 token

### 文本

| Token | 语义 | 典型内容 |
| --- | --- | --- |
| `text-primary` | 主要信息 | 正文、区块标题、主要字段值 |
| `text-secondary` | 次要/辅助信息 | 字段标签、说明、面包屑、辅助统计标签 |
| `text-accent` | 当前状态、焦点、重要强调 | 当前页面、当前导航项、少量关键统计值 |
| `text-on-selected` | 高亮背景上的文字 | 选中行、选中按钮 |

### 表面与结构

| Token | 语义 | 典型内容 |
| --- | --- | --- |
| `surface-default` | 页面主背景 | 主工作区 |
| `surface-topbar` | 顶栏表面 | 顶部应用栏 |
| `surface-footer` | 底栏表面 | 底部操作栏 |
| `surface-interactive` | 普通可点击表面 | 按钮 |
| `surface-selected` | 当前选择 | 高亮行、选中按钮 |
| `border-subtle` | 弱结构边界 | 分隔线、低强调边框 |

装饰性颜色（例如首页轨道的金色）不属于信息层级 token；它们只能用于视觉装饰，不能代替状态色或正文色。

## 4. 信息层级

从高到低按以下语义处理：

1. **当前页面标题 / 当前导航项**：`text-accent` + 粗体。例：`01 / 学生档案`、当前选中的 `1 学生`。
2. **区块标题**：`text-primary` + 粗体。例：`校园概览`、`档案字段`。
3. **关键值**：默认属于 `text-primary`；确实需要快速扫读的少量统计值可以使用 `text-accent` + 粗体。
4. **普通正文 / 普通导航项**：`text-primary`，通常不额外加粗。
5. **字段标签 / 说明文字 / 次级位置提示**：`text-secondary`。
6. **结构分隔符**：`border-subtle`，不得比字段标签更抢眼。

标题、标签和值是不同角色。尤其禁止仅因为它们位于同一区域，就使用完全相同的样式。

## 5. 首页示例

首页左侧应形成明确的层级：

```text
首页                 ← text-secondary
▌ 1 学生             ← text-accent + bold
  2 教务             ← text-primary
  3 课程
...

校园概览             ← text-primary + bold
学生 100   班级 26   ← 标签 text-secondary；关键数字可 text-accent + bold
课程 20    选课 400
```

因此 `校园概览` 与 `学生 / 班级 / 课程 / 选课` 必须有明显的视觉差异。前者是 section heading，后者是 label。

## 6. 工作区页面

学生、学院、专业、班级、课程、成绩和数据页共享同一套信息层级。

当一个统计数字与某个筛选/视图是一一对应关系时，**数字应直接附着在该交互项上，不再复制一行独立统计摘要**。这样数量既说明当前数据规模，也直接解释“点击这个选项会看到多少条记录”。例如学生页：

```text
学生档案                         ← 当前页面，text-accent + bold
[ 1 全部档案 · 100 ]
[ 2 在读学生 · 92  ]
[ 3 未分班 · 0     ]             ← 数量与对应筛选保持在同一控件中
/ 搜索姓名、编号、班级…

名册                             ← 当前面板焦点可使用 text-accent
姓名  学号  班级                 ← 列标签 text-secondary
林岚  20260001 ...               ← 普通记录 text-primary

档案 / 即时预览                  ← “档案”是 section heading；状态 text-secondary
林岚                             ← 当前记录标题 text-accent + bold
20260001                         ← identifier text-secondary

档案字段                         ← section heading，text-primary + bold
姓名      林岚                   ← label text-secondary；value text-primary
```

课程页和成绩页的视图数量同样直接放进各自筛选项；学院 / 专业 / 班级导航的记录数也与对应导航项绑定。若某项统计没有一一对应的交互目标，例如数据总览中的学生数、课程数和选课数，则可以保留独立统计摘要。

筛选数量应反映当前搜索条件下切换到该视图后实际会得到的记录数。当前面板焦点可以使用强调色，但不能把该面板内部的标题、标签和值全部染成强调色。

## 7. 强调色

强调色用于表达**当前、可操作焦点或真正重要的值**，不能成为“看起来更漂亮”的通用文字颜色。

优先使用场景：

- 当前页面标题；
- 当前导航项；
- 键盘/鼠标焦点；
- 少量需要立即扫读的关键统计值；
- 明确的交互强调。

普通 section heading 使用 `text-primary`，说明文字和字段标签使用 `text-secondary`。如果页面上大面积文字都变成强调色，说明语义层级已经失效。

确认、删除、待录入等状态首先依赖明确文案和结构表达。当前主题没有单独定义 warning/danger token，因此不得借用 decorative gold 冒充状态色；确有需要时应先新增语义 token，再选择色号。

## 8. 当前暗色主题映射

下面是当前实现映射，只属于实现层，可以在不改变上面语义规则的前提下调整：

| Semantic token | 当前实现 |
| --- | --- |
| `surface-default` | xterm 235 (`#262626`) |
| `surface-topbar` | xterm 234 |
| `surface-footer` | xterm 236 |
| `surface-interactive` | xterm 237 |
| `surface-selected` | xterm 238 |
| `text-primary` | xterm 252 |
| `text-secondary` | xterm 245 |
| `text-accent` | xterm 110 |
| `text-on-selected` | xterm 255 |
| `border-subtle` | xterm 239 |
| decorative gold | xterm 180 |

应用只绘制自己的终端单元格，不修改宿主终端客户端的窗口背景、padding 或主题配置。

代码中的对应 token 集中在 `src/xingyuan_sis/tui/screen.py`：

```text
_TEXT_PRIMARY
_TEXT_SECONDARY
_TEXT_ACCENT
_TEXT_ON_SELECTED
_BORDER_SUBTLE
_SURFACE_DEFAULT
_SURFACE_TOPBAR
_SURFACE_FOOTER
_SURFACE_INTERACTIVE
_SURFACE_SELECTED
```

组件和页面不得再定义第二套“看起来差不多”的正文/强调颜色。

## 9. 终端约束

星原 SIS 当前以 ANSI 256 色作为稳定基线。不要假设所有用户都有 TrueColor，也不要要求用户修改 Windows Terminal、Termux 或其他宿主终端的主题。

颜色不能成为唯一的信息载体。当前项同时使用 marker / 粗体等非颜色线索，例如 `▌ 1 学生`；选中态应在无颜色模式下仍然可以理解。

窄屏可以重新排布布局，但语义层级保持不变：页面标题仍高于区块标题，区块标题仍高于字段标签。

## 10. 实现约束

布局代码不得为了临时视觉效果散落新的 ANSI 色号。新增样式时按以下顺序处理：

1. 判断内容的语义角色；
2. 优先复用已有 semantic token；
3. 只有现有角色确实无法表达时才新增 token；
4. 最后为 token 选择 ANSI 映射。

如果一个视觉调整改变了标题、正文、标签、焦点、选中态或关键值之间的层级关系，应同步检查并更新本文档。
