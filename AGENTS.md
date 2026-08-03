# AGENTS.md

> AI agent 进入本仓库后的**开工前必读**。本文件只放指针与硬规则，不复制其它文档内容（单点真理）。

## 项目定位

IBC-Inter 是实验性意图驱动混合编程语言（Python-style 确定性代码 + LLM 非确定性推理融合）。处于实验性示例阶段，详见 `README.md`。

## 开工前必读（按顺序）

1. `tasks_docs/NEXT_STEPS.md` "⛔ 工作模式定论"--禁止 compat shim / 胶水实现 / tricky 实现，质量优先于速度
2. `docs/README.md` §三 "文档治理纪律"--单点真理、数字纪律、跨文件一致性
3. `docs/WRITING_GUIDE.md`--技术文档书写准则，修改/新增 `docs/` 下技术文档前必读
4. `docs/KNOWN_LIMITS.md`--语言级限制，改公理层或语义错误集前必查
5. `docs/architecture/02_metadata_ast.md`--新增 AST 字段或侧表前必查
6. `.opencode/skills/doc-governance/SKILL.md`--执行文档治理/检查/体系建设前必读，按 Phase 0-8 流程操作
7. `.opencode/skills/code-workflow/SKILL.md`--执行代码任务（实现/修复/重构）前必读，按 Phase 0-5 流程操作，遵守工作模式定论
8. `.opencode/skills/code-review/SKILL.md`--执行缺陷复核/分类决策/实施后核验前必读，按 Phase 0-5 流程操作，遵守验证与分组纪律
9. `.opencode/skills/code-quality/SKILL.md`--执行代码子系统健康/清洁诊断（体检/残留扫描/历史痕迹排查）与质量红线判定前必读，按"健康诊断十查"与分类速查操作（`code-health` 已并入）
10. `.opencode/skills/code-odor/SKILL.md`--执行工作过程自查/异味特征扫描前必读，命中兼容/兜底/快速实现等字样时按自我质询协议审问
11. `.opencode/skills/self-grill/SKILL.md`--交付前对计划/设计/已完成工作自我质询，仅将无法自主决断项反馈用户

## 自主工作循环（工作方式，强制）

> 目标：在约束内最大限度自主推进。每项任务默认走"理解 → 设计质询 → 自主决策 → 实现 → 自反馈验证 → 自主纠错 → 交付自查 → 收尾"闭环，具备自我反馈、自主纠错、自主决策能力；**只把真正需要用户拍板的项上报**。细节按下方 skill 执行。

> **原则优先于行为维持**（硬原则）：当既有代码/行为被确认违反一般性的工程/架构原则（见 "⛔ 工作模式定论" 第 6 条）时，**优先以架构/工程原则为准，不以"保持已有行为"为主**。改前先分析，改后详尽记录变化前后（实现 + 测试 + 文档），供未来追溯。此原则是"上报阈值"中"需裁决冲突"的裁决基准。

1. **理解**：读 `tasks_docs/NEXT_STEPS.md`/`PENDING_TASKS.md` 定位任务、阻塞与硬约束（`code-workflow` P0-P1）。
2. **设计与质询**：方案对照 `NEXT_STEPS.md` "⛔ 工作模式定论" + `self-grill` 自我质询 + `code-odor` 工作过程自查。
3. **自主决策**：能自主决断的自行决断并记录理由；仅触及下方上报阈值的项才向用户陈述（方案 + 推荐 + 理由）。
4. **实现**：按 `code-workflow` P3 卫生纪律执行。
5. **自反馈验证**：`python -m pytest tests/` + 残留扫描 + 自复核（`code-review` P4 精神，subagent 报告不等于做完）。
6. **自主纠错**：验证失败 / 异味命中 → 回到根因阶段修复再验证，循环至干净或需上报；禁止症状层打补丁。
7. **交付自查**：`code-quality` §九 提交前自查 + `self-grill` 未决断项归零。
8. **收尾**：文档同步（单点真理表）、临时文档清理、汇报（`code-workflow` P5 / `doc-governance` P8）。

**上报阈值**（仅以下才向用户确认/请示）：
- 公理层或语义错误集变更（须全量 pytest 评估破坏面）
- 对外契约 / 破坏性变更（API 签名、vtable、序列化格式）
- 跨子系统架构取舍，或需裁决与工作模式定论的冲突
- GATED / SHELVED / 封存任务解封
- 用户意图不明，且代码/文档/测试无法给出确定答案

**默认自主范围**（直接推进不打断）：局部 bug 修复、机械性清理、测试补齐、文档同步、符合既有方向的小型重构。

## 测试

```bash
conda activate ibci
python -m pytest tests/
```

- 这是**唯一命令**。`pytest.ini` 已配 `-q --tb=short --strict-markers`，无需附加 flag。
- **运行环境为 conda env `ibci`**（本机位于 `~/miniconda3/envs/ibci`）。先 `conda activate ibci` 再执行；非交互 shell / 脚本内直接用 `~/miniconda3/envs/ibci/bin/python -m pytest tests/`。系统默认 `python`/`python3` 未安装依赖（如 `openai`），不可用于运行与测试。
- 开新分支前必复跑，把 pass/fail 计数写进 PR 描述。
- 当前基线以实跑为准，不冻结数字（见 `tasks_docs/NEXT_STEPS.md` 顶部锚点）。

## 编码与平台注意

- **文档多为 CRLF**，部分历史文件含非 UTF-8 字节；Edit 工具多行匹配可能失败，改用单行锚点或 PowerShell。
- **Windows 路径大小写不敏感**；`tests/conftest.py` 强制 basetemp 为 `.tmp_pytest/`（跨盘 relpath 兼容）。
- **临时目录导入**需 `importlib.invalidate_caches()`，否则 `FileFinder` 缓存陈旧导致 `import_module` 失败（见 `ibci_sdk/check.py` `_load_module`）。
- 文档引用代码路径时以 `docs/README.md` §四"代码路径约定"为准（多个模块已重构为包）。

## 不要做的事

- 不复制其它文档内容到本文件（单点真理；本文件只放指针）。
- 不在文档中冻结测试通过数字（以实跑为准）。
- 不同时主推多个 P0 阶段（见 `tasks_docs/NEXT_STEPS.md` "工作规则"）。
- 不写 compat shim / 胶水 / tricky 实现（见 `tasks_docs/NEXT_STEPS.md` "⛔ 工作模式定论"）。
- 不在代码注释中使用任务代号/ADR 编号/PT 编号/文档章节指针/历史叙述--注释只注明功能设计与已知问题（详见 `docs/README.md` §三.6）。
- 重大架构决策直接写入 `docs/architecture/` 对应章节，不再使用独立 ADR 文件。
- media Phase 4（多模态）**已彻底封存，短期不考虑实现**；恢复需显式解封并重估（见 `tasks_docs/PENDING_TASKS.md` §六）。
- 执行文档治理前必读 `.opencode/skills/doc-governance/SKILL.md`，按 Phase 0-8 流程操作——禁止凭经验直接修改，必须先审计、做任务规划、交叉核验。
- 执行代码任务前必读 `.opencode/skills/code-workflow/SKILL.md`，按 Phase 0-5 流程操作——禁止未理解代码上下文前动手修改，必须对照工作模式定论检验方案。
