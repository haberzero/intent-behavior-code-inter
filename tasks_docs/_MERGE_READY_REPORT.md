# _MERGE_READY_REPORT — unsafe-vibe-dev 合并就绪报告

> 2026-08-11。本报告供用户显式授权 `_MAIN_MERGE_PLAN.md` 阶段 3（合并动作本身**不在自主范围**，
> 须用户显式授权执行）。

## 一、结论

**unsafe-vibe-dev 全部合并前置条件已满足，可进入合并阶段。**

| 合并条件（`_MAIN_MERGE_PLAN.md` §一） | 状态 | 证据 |
|------|------|------|
| 真实 LLM e2e 检测通过（无 P0 阻断缺陷） | ✅ | `_REAL_LLM_E2E_REPORT.md` §七：9/12 类特性通过；唯一缺陷 generator.to_list 已由 U1 正确架构修复；**本 session examples 真实跑通再确认（11 例全过）** |
| 全量 pytest 零回归 | ✅ | **2209 passed / 1 skipped**（本 session 实跑；U1-U7 + 意图注入 + 配置硬化 + dispatch 观测修复净增 35 契约/回归测试） |
| 文档/README 就绪 | ✅ | 见 §二 |
| 用户显式授权 push/合并 | ⏳ **未授予** | 禁 push 硬原则；合并动作须用户显式授权 |

## 二、文档/README 就绪核验（2026-08-11 本 session 完成）

| 项 | 状态 | 说明 |
|----|------|------|
| 根 README 本地 LLM 快速开始 | ✅ | §"本地 LLM 快速开始（真实 LLM 驱动）"：Ollama/LM Studio/vLLM 端点 + 分层配置 |
| 根 README 实验性/demo 定位 | ✅ | "实验性示例阶段"表述清晰；demo 定位含"真实 LLM 驱动" |
| 根 README 阅读路径 | ✅ | 进一步阅读补 subsystems/howto/诊断码/观测体系指针 |
| `docs/README.md` | ✅ | 目录树 + 阅读路径与最终分支一致（含新 howto 2 篇注册） |
| `_DOC_HEALTH_20260811.md` P1 | ✅ | 16 项全部处置（复核 4 项已修 + 实修 12 项） |
| `_DOC_HEALTH_20260811.md` P2 | ✅ | 12 项全部处置（P2-6 评估维持现状，余全修） |
| `pyproject.toml` | ✅ | 版本 0.2.0；`readme="README.md"` 正确；LICENSE MIT © 2026 Nan Shi |
| `KNOWN_LIMITS.md` / `SYNTAX_REFERENCE.md` 一致 | ✅ | 断链扫描 0；`-> auto` 行为体语义与代码一致；A5 类构造帧内 CPS 已文档化（arch/04 §2.7 + arch/05 公理 EXEC-4）；run_batch 非阻塞已文档化（arch/05 §3.4） |
| examples 真实跑通 | ✅ | 11 例全部通过（详见 §三） |

## 三、examples 真实 LLM 跑通记录（本 session，本地端点 qwen3.6-35b-a3b）

**验收方式**（`_HANDOFF_ISSUES_LLM_E2E.md` P2 决断）：独立项目目录 + `api_config.json` 自动加载，
或 `--root <example_dir>` 显式指定（plugins/isolation demo 以自身目录为 root，`plugins/`/`sub_project/`
相对 root 解析）。

| 示例 | 结果 | 说明 |
|------|------|------|
| 01_getting_started/01_hello_world | ✅ | 真实 LLM：打招呼 + 求和 + LLM 函数翻译 + 意图注释（冷酷极简实证） |
| 01_getting_started/02_intent_demo | ✅ | 意图栈操作 + 真实 LLM 回复 |
| 01_getting_started/03_flow_control_and_behavior | ✅ | 流控 + 行为结合 |
| 01_getting_started/04_mock_and_llmexcept | ✅ | Mock + llmexcept + retry |
| 01_getting_started/05_enum_and_switch | ✅ | Enum + switch + idbg 探查（**依赖本 session dispatch 观测修复**） |
| 01_getting_started/06_enum_switch_with_llm | ✅ | LLM 输出 → Enum + switch（同上依赖） |
| 02_basic_modules/01_file_operations | ✅ | 文件沙箱操作 |
| 02_basic_modules/02_sys_module | ✅ | isys 路径查询 |
| 02_basic_modules/03_config_mock | ✅ | 配置 + mock |
| 03_advanced_features/isolation_demo | ✅ | 父子隔离运行（sub_project 沙箱验证） |
| 03_advanced_features/plugins_demo | ✅ | 用户插件 calc/plugin_info |

**运行命令**：
```bash
# 独立项目目录方式（README 标准）：
mkdir test_target_proj && cp examples/01_getting_started/01_hello_world.ibci test_target_proj/
# 在 test_target_proj/ 放 api_config.json（见 README 快速开始）
python main.py run test_target_proj/01_hello_world.ibci

# --root 显式指定方式（仓库内示例）：
python main.py run examples/01_getting_started/01_hello_world.ibci --root /path/to/proj_with_api_config
python main.py run examples/03_advanced_features/plugins_demo/main.ibci \
  --root examples/03_advanced_features/plugins_demo
python main.py run examples/03_advanced_features/isolation_demo/parent.ibci \
  --root examples/03_advanced_features/isolation_demo
```

## 四、合并执行建议（阶段 3，供用户授权时直接执行）

1. `git merge unsafe-vibe-dev → main`（或用户指定方式）。
2. `main` 标记稳定基线；`unsafe-vibe-dev` 保留继续开发，只收稳定改进/修复。
3. 合并后发布产物如需，另行评估（当前无已发布 artifact，`0.2.0` 为首个可发布版本号）。
4. **CI/CD**：GitHub 侧自动触发已停用（`workflow_dispatch`），合并后如需重新启用须单独设计"可靠化/实用化"。

## 五、风险与遗留（不阻断合并）

- **test_mock_service 偶发 flaky**（HTTP 时序，`total_requests` 断言偶发；单独跑通过，与功能无关）。
- **PT-AUDIT-3 双路径分裂专项审计**（PENDING_TASKS §〇 P2）：规划中，不阻断合并（合并条件以检测/工程维度满足为准）。
- **PT-DEBT-24**（call_intent 死机制清理）、**F9**（import ai 配置副作用评估）：低风险遗留，独立窗口。
- **PT-DEBT-4** `file` 重命名（破坏性变更独立窗口）。
- 意图效果最终取决于模型服从性（类型约束稳定；风格类意图对低服从性模型弱效，已文档化）。
