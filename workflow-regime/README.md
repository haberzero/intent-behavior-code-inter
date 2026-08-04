# Workflow Regime — 工作制度体系（项目无关）

> 一套**与具体项目无关**的智能体工作制度：工作原则、工作流程、skill 体系、任务控制文档机制、goal 机制。
> 从实际协作中沉淀而来，剥离了具体项目绑定，可整体移植到任何项目。

## 这个文件夹是什么

本目录沉淀"如何与一个智能体长期协作完成软件工程"的**方法论层**，包含四部分：

| 部分 | 路径 | 内容 |
|------|------|------|
| **工作原则** | `AGENTS.md` | 智能体开工前必读的通用原则：自主推进、交付纪律、重构授权、上报阈值、日志记录 |
| **流程技能** | `skills/` | 可加载的操作流程：实现、复核、质量、异味、自我质询、质量维护、无目的审视、文档治理、设计哲学 |
| **任务控制文档机制** | `task-control/` | 如何用文档体系管理长期任务：写什么文档、怎么编写、怎么更新、各自负责什么 |
| **goal 机制** | `task-control/07_goal_mechanism.md` | 目标生命周期机制（去插件化）：如何设定、推进、停止、交接 |

## 如何使用（移植到新项目）

1. **复制本目录**到新项目根（或引用为共享子模块）。
2. **新建 `AGENTS.md` 指针**：在项目 `AGENTS.md` 中指向本目录的 `AGENTS.md` 与 `task-control/README.md`，并补充项目专属事实（测试命令、目录结构、语言约定）。
3. **skill 路由**：项目级 `AGENTS.md` 列出本目录 `skills/` 下各 skill 的触发场景（或项目级 skill 目录以符号链接/复制方式引用）。
4. **初始化任务控制文档**：按 `task-control/README.md` 建立项目的 `NEXT_STEPS`、`PENDING_TASKS`、`WORKLOG`、`_HANDOFF` 等。
5. **配置 goal**：按 `task-control/07_goal_mechanism.md` 把目标机制"声明式"写入项目的任务控制文档（无需依赖任何插件）。

## 核心立场

- **质量优先于速度**；原则优先于行为维持；可推翻项目自身设计缺陷（文档化也可推翻）。
- **禁止** compat shim / 胶水 / tricky / 过程式硬编码 / 双通道 / 双写真相。
- **系统性统一**：单一权威源、设计语言统一、机制同构、配合模式统一、一致性先于便利、宏观反思、命名统一。
- 已有代码不因"已在仓库里"而正确。

## 目录细节

```
workflow-regime/
├── AGENTS.md                  # 通用工作原则（自主推进/交付纪律/重构授权/上报阈值/日志）
├── skills/                    # 10 个通用流程技能
│   ├── code-workflow/         # 实现/修复/重构流程
│   ├── code-review/           # 缺陷复核/分类/实施后核验
│   ├── code-quality/          # 质量底线与健康诊断
│   ├── code-odor/             # 异味特征检测 + 工作过程自查
│   ├── self-grill/            # 自我质询（对计划/设计/已完成工作）
│   ├── grilling/              # 对用户的持续质询
│   ├── quality-maintenance/   # 长期质量维护（Tier A/B/C）
│   ├── aimless-review/        # 非目的性审视（潜在参考沉淀）
│   ├── doc-governance/        # 文档体系治理流程
│   └── design-philosophy/     # 系统级设计哲学（统一性八原则）
└── task-control/              # 任务控制文档机制（书写规范）
    ├── README.md              # 体系总览：分类、生命周期、协作图
    ├── 01_worklog.md          # WORKLOG：工作日志怎么编写/更新
    ├── 02_next_steps.md       # NEXT_STEPS：当前最紧要项怎么编写
    ├── 03_pending_tasks.md    # PENDING_TASKS：阻塞/搁置项怎么编写
    ├── 04_decision_record.md  # 决策记录：重大设计决策怎么记录
    ├── 05_temp_task_doc.md    # 临时任务文档：怎么编写与清理
    ├── 06_handoff.md          # 交接文档：要确保什么
    ├── 07_goal_mechanism.md   # goal 机制（去插件化）：目标生命周期
    └── 08_autonomous_loop.md  # 自主工作循环：执行协议
```
