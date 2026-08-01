# .opencode/skills 编写公约

> 本文件是本仓库 skill 的编写规范。**非 `SKILL.md`，不会被 opencode 自动加载。**
> 面向新增或修改 `.opencode/skills/<name>/SKILL.md` 的写作者。

## skill 的定位

skill 是 opencode **按需加载**的操作流程指南。agent 平时仅看到每个 skill 的 `name` + `description`（路由键），仅在需要时才加载完整 body。因此：

- **description 决定是否被加载**：须覆盖"做什么 + 何时触发"，前置触发关键词，必要时用 `Use ONLY when...` 收窄。它是路由键，写具体路径/关键词是对的。
- **body 决定加载后的效果**：应是聚焦的操作流程，不是百科全书。body 越长，越挤占 agent 注意力、越容易与项目文档漂移。

## 四条设计原则

1. **流程优先于事实**：写"怎么做"（阶段、决策纪律、检验门），不写"项目有什么"（文件布局、诊断码清单、架构分层）。领域事实让 agent 从源头文档读，不预消化进 skill。
2. **指向而非复制**：需要 agent 查项目事实时，一行指向权威文档（如"对照 `docs/KNOWN_LIMITS.md`"），绝不重述其内容。skill 不得成为项目文档的第二份副本--部分复制必然漂移（改一处忘另一处）。
3. **通用优先于具体**：示例用泛化表述（"加 setter 但留死分支=半修复"）。禁止历史叙事（"某次 _intent_ctx 22 处穿透修复"）--历史属于 git，不属于 skill。
4. **精简 body**：目标 60-120 行，上限 150。每个阶段用"输入/关键动作/输出"三段式，不展开可从文档读到的细节。

## 禁止写入 skill body 的内容

| 禁止 | 原因 |
|------|------|
| 项目文件路径布局（如 `core/compiler/` 罗列） | 易变，应让 agent 自行 grep/glob 探查 |
| 诊断码/公理码清单 | 项目事实，属 `docs` 与 `codes.py` |
| 历史修复案例与代号 | 历史叙事，属 git |
| 从 `docs/` 复制的规则表/速查表 | 违反单点真理，必漂移 |
| 写死项目专属 token 的 grep pattern | 应从权威文档红线派生 |

> 例外：`description` 中可含项目路径/关键词（路由需要）。原则约束的是 **body**。

## 格式规范（opencode 强制）

- 路径：`.opencode/skills/<name>/SKILL.md`，目录名须与 `name` 一致。
- frontmatter 只认：`name`（必填，1-64 字符，小写连字符，匹配目录名）、`description`（必填，1-1024 字符）、`license`/`compatibility`/`metadata`（可选）。其余字段被忽略。
- body 为 markdown。

## 当前 skill 清单

| skill | 职责 | 触发场景 |
|-------|------|---------|
| `doc-governance` | 文档体系治理流程 | 文档审计/治理/检查 |
| `code-workflow` | 代码任务实现流程 | 实现/修复/重构 |
| `code-review` | 缺陷复核与验证流程 | 复核/验证/批量变更核验 |
| `code-health` | 代码子系统健康诊断流程 | 体检/残留扫描/历史痕迹排查 |
| `code-quality` | 代码质量底线与处置准则 | 兜底/兼容层/历史包袱/双通道/双写真相判定 |

新增 skill 前，先回答：这是**稳定流程**，还是**易变事实**？是前者才值得建 skill；是后者应写入 `docs/` 或 `AGENTS.md`。
