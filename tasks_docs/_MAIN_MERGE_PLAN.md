# _MAIN_MERGE_PLAN — unsafe-vibe-dev 合并取代 main 规划

> 目标（用户 2026-08-11 裁定）：在经历**真实 LLM 试用**与**真实高强度全语法特性试用检测**后，
> `unsafe-vibe-dev` 完全可合并并**取代现有 `main`**。`unsafe-vibe-dev` 保留作为未来开发分支；
> `main` 应尽量保持稳定性。前置条件见 `_REAL_LLM_E2E_PLAN.md`。

## 一、背景与现状
- **分支现状**：`unsafe-vibe-dev` 领先 `origin/unsafe-vibe-dev` 约 160+ commit，是全部近期工作的唯一活动分支；
  `main` 长期未触碰（永不触碰主干原则——但合并动作本身由用户显式授权后执行）。
- **工程状态**：全量 **2137 passed / 1 skipped**；异步统一闭环（A1-A5）、run_batch CPS、UID 统一、
  序列化重构、诊断体系等已全部落地。
- **合并条件（必须全部满足）**：真实 LLM e2e 检测通过（无 P0 阻断缺陷）+ 全量 pytest 零回归 +
  文档/README 就绪 + 用户显式授权 push/合并。

## 二、合并时机与进度
| 阶段 | 触发条件 | 动作 |
|------|---------|------|
| **阶段 0（当前）** | 本文档 + _REAL_LLM_E2E_PLAN 落档 | 完成规划与交接；CI 已停用 |
| **阶段 1（下一 session）** | 本地 LLM 服务就绪 | 真实 LLM 全面试用 + e2e 批判检测，产出验证报告 |
| **阶段 2（检测通过后）** | 无 P0 阻断缺陷 | 修复暴露问题 + 文档/README 最终化 + 版本评估 |
| **阶段 3（合并）** | 用户显式授权 | `git merge unsafe-vibe-dev → main`（或按用户指定方式）；`main` 标记稳定 |
| **阶段 4（合并后）** | 合并完成 | `unsafe-vibe-dev` 保留继续开发；`main` 只接受稳定改进/修复 |

## 三、合并前必备的文档/README 更新（"最基本的"）
1. **根 README**：已具备对外 README（核心特性/快速开始/免责声明/API 配置）。合并前核验：
   - 快速开始是否含**本地 LLM 服务**选项（当前只写阿里云百炼；补 Ollama/LM Studio 本地端点）
   - "实验性/demo 定位"表述清晰（已具备）；demo 定位升级为"真实 LLM 驱动"
2. **`docs/README.md` / `GETTING_STARTED.md`**：核验与最终分支状态一致；文档健康问题（`_DOC_HEALTH_20260811.md`）
   在合并前清完（P0/P1 红线必清，P2 尽量）
3. **`pyproject.toml`**：版本评估（`0.1.0` → 是否升 `0.2.0`）；`readme = "README.md"` 已正确
4. **`LICENSE`**：已具备（MIT，© 2026 Nan Shi）
5. **`docs/KNOWN_LIMITS.md` / `SYNTAX_REFERENCE.md`**：与最终代码一致（尤其 A5 类构造 CPS、run_batch 非阻塞）
6. **examples/**：核验 3 个示例（01/02/03）在真实 LLM 下可跑通

## 四、合并执行细则（阶段 3）
- **合并方向**：`unsafe-vibe-dev` → `main`（合并后 main 内容 = 当前 unsafe-vibe-dev）。
- **push 授权**：涉及远程 push/合并，**必须用户显式授权**（硬原则），不在自主范围。
- **main 稳定性**：合并后 `main` 为稳定基线；日常开发仍基于 `unsafe-vibe-dev`；`main` 只收稳定改进/修复
  （可复用"零风险直接合并"判定）。
- **保留**：`unsafe-vibe-dev` 不删除，继续作为未来开发主线。

## 五、风险提示
- 真实 LLM 检测可能发现 MOCK 未覆盖的语义缺陷 → 属预期（这正是检测目的），修复后再合并，不赶进度。
- 本地 LLM 能力/模型质量影响试用结果：用足够强的非思考指令模型，避免"模型太弱 → 误判为语言缺陷"。
