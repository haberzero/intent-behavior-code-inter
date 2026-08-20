# 规划文档：后续主线与支线任务排布（健康度优先）

> **性质**：临时任务控制文档（排布规划）。供下一 session 交接与执行参考；执行过程中
> 逐项收敛进 `tasks_docs/NEXT_STEPS.md`（候选）/ `tasks_docs/PENDING_TASKS.md`（清单），
> 完成或吸收后按 `GOVERNANCE.md` 删除（git 承载）。
>
> **用户指示（2026-08-19）**：目前更关注**代码健康与架构健康**；真实 LLM 全面试用
> 纳入任务考虑——在健康度/稳定性达到一定层次后重启，把本轮大重构产生的新功能新特性
> 全部重试用一遍；**全面试用优先级不是最高，但后续一定要进行**。
> 微调：A4/A3 交换；B3（PT-DECIDE-2）封存、短期不再考虑启动；B5（PT-DOC-3P2）提到 B3；
> B6（PT-FEAT-6/12）划更远期、近期不处理。

---

## 〇、当前状态基线（交接锚点）

- 分支 `unsafe-vibe-dev`（本地领先 origin，未 push——push 需再获显式授权）；main 未触碰。
- 测试基线：**3082 passed / 1 skipped**（以实跑为准）。
- 技术债收敛 8 阶段已全部完成 + **阶段 A1 主线架构债务落地完成**（G5 意图值栈 + 行为统一装配
  入口收敛，2026-08-20，见 WORKLOG）；`tasks_docs/HANDOFF.md` §2.1 有完成登记。

---

## 一、排布总则

1. **健康度优先**（代码/架构）→ 功能稳健 → 对外能力 → 远期演进 → 真实 LLM 全面试用
   （健康阈值后重启，**非最高优先但必做**）。
2. **同一时刻只推一个 P0**；阶段内按序推进，不并行多线。
3. 每项：全量 pytest 零回归 + 描述性 commit + 同步 NEXT_STEPS/WORKLOG/HANDOFF；
   **禁 push**（除非用户显式授权）；main 不触碰。
4. 破坏性重构授权、工作模式定论（禁 compat shim/胶水/tricky/双通道）、原则优先于行为维持
   全程适用。

---

## 二、阶段 A · 代码/架构健康（当前 P0，最高优先）

| # | 任务 | 内容 | 依据 | 验证门 |
|---|---|---|---|---|
| A1 | ~~主线架构债务落地~~ ✅（2026-08-20 完成） | ~~G5 意图值栈全量重构（意图栈 content:str → 可渲染一等值栈、按值匹配）+ 行为值深程统一装配入口收敛（run_batch/invoke 行为路径收敛到统一装配入口）~~ | 2 项登记架构债；架构统一 | 完成：eager 一等值栈 + `@-` 按值匹配 + `assemble_llm_call_request_cps` 单一装配入口；全量 3082 零回归（见 WORKLOG） |
| A2 | **PT-DEBT-34 变量语义建模显式化**（用户 2026-08-20 新增，置顶） | 变量**引用/拷贝/赋值/传递**值语义建模未显式且合理区分——评估现状语义面→调研主流语言对照→修复语义混乱 + 补齐语法与说明书；用户判定巨大隐患，**排在真实试用前** | 用户裁定；语义地基级隐患 | 评估/调研产出对照结论 + 修复全量 pytest 零回归 + 语义判别测试 + docs 权威契约 |
| A3 | **PT-DEBT-29 生成器消费协作化** | `IbGenerator.generic_next` 对 Waitable 阻塞等待 → Waitable 感知挂起（让出型消费，与 CPS 执行模型同构） | KNOWN_LIMITS §二十四；消除同步阻塞死锁风险 | 全量 pytest 零回归 + 并发/生成器判别测试 |
| A4 | **PT-DEBT-30 + PT-DEBT-33 类型边界闭合** | `yield from` 序列委托编译期生成器/序列区分（§二十五）；KNOWN_LIMITS §十 dict 键下标校验 / 中置星计数偏移 / 跨引擎封印 | 类型地基边界 | 全量 pytest 零回归 + 边界判别测试 |
| A5 | **Tier C 专项审计** | C 类异味 ~25 处需人工判定 + 静默降级补诊断复核（leaf/runtime_serializer/artifact_loader 尽力而为回退）+ for+if 深嵌套可读性（PT-AUDIT-2 收窄项） | 收敛期审计 C 类清单；PT-AUDIT-2 前提复核 | 独立分支或同分支分批；分类定案 + 只修低风险；零回归 |
| A6 | **PT-AUDIT-1/3 周期复核 + quality-maintenance Tier B** | 代码异味核对周期回顾；R 系列复核清单；Tier B 阶段边界批量巡检 | 周期审计；长期质量维护 | 分类 + 只修低风险 + 记录 |

## 三、阶段 B · 功能稳健与对外能力

| # | 任务 | 内容 | 维度 |
|---|---|---|---|
| B1 | **PT-TEST-2 覆盖缺口补测** | COVERAGE_MATRIX 剩余 ~12 处 🔶缺失（含 5 处 TRUE_GAP 与模块缓存/循环 import/重载/switch 控制流等） | 功能稳健 |
| B2 | **PT-DECIDE-3 项②④** | ② `__validate_prompt__` 是否扩展至内置类型（评估内置解析器统一走协议）；④ prompt 协议异常回退可观测性复核 | 语义完整性 |
| B3 | **PT-DOC-3P2 how-to 读者旅程补齐**（原 B5 提前） | Reference→How-to 读者旅程断裂；生成器/并发/llmexcept/隔离等场景操作指南 | 对外可用性 |
| B4 | **PT-FEAT-5 CI/CD 可靠化** | CI/CD 可靠化/实用化设计后重新启用（真实 LLM e2e / 跨平台 / 发布产物）；前三项已落地 | 工程稳健/对外 |

**已封存**：PT-DECIDE-2（供应商思考禁用）——用户裁定短期不再考虑启动；出现多供应商思考
模式部署需求时评估解封。

**划远期（近期不处理）**：PT-FEAT-6（CompilationResult 字段精简）、PT-FEAT-12（AST UID 编译期
可见）——工具链项，排入更远期。

## 四、阶段 C · 真实 LLM 全面试用重启（VISION-3）

- **触发阈值**：阶段 A 健康攻坚（含 **PT-DEBT-34 变量语义建模显式化**完成）+ 阶段 B 稳健巩固
  完成后，健康度/稳定性达标。
- **目标**：对**五大地基重构后全部新特性重试用**（一次全面覆盖，非渐进追加）：
  - llm 可调用类（直接调用 `f(args)` / 装配 dict / `__intent__` 三层改写 / `__retry__` 高阶化）
  - stream 流式（`stream_call` / `stream_channel`）、run_batch 批量（逐项参数化）
  - 覆层机制（`impl overlay` / `with overlay` 作用域）
  - prompt 协议族五成员（to_prompt / from_prompt / output_hint / payload_prompt / validate_prompt）
  - 意图一等值嵌入（行为/可调用值经 `__to_prompt__` 嵌入意图）、snapshot 意图冻结
  - `fs` 模块（原 file→fs 迁移后）、Optional/容器解析、overlay 跨根并发
- **方式**：真实 qwen3.6 非思考模式全量回归 + 压力维度扩展（>4k token / 多轮长对话 /
  批量并发上限 / 多模块交叉）；缺陷→根因修复→回归核销循环（trials INDEX 生命周期状态机）。
- **优先级**：非最高，但**必做**（用户明确）。

## 五、阶段 D · 主线远期演进（试用稳定后）

1. VISION-4 · P7 类型理论加固（ADT/模式匹配/联合类型/枚举实例化评估）——依赖类型地基（A3）+ 试用验证。
2. VISION-5 · P8 函数式地基（协议化组合子 / 柯拉化）——依赖协议化地基稳定。
3. VISION-1 · 二层 IR（概念验证）。
4. PT-SEALED-1（media 多模态）保持封存；PT-SEALED-2（PT-DECIDE-2 思考禁用）保持封存。

---

## 六、持续背景

- quality-maintenance：Tier A（随主线顺带）+ Tier B（阶段边界）；aimless-review 低密度背景。
- PT-DEBT-5（文件命名清理，shelved）保持；PT-DEBT-31（已核实 done）保持。
- 文档体系持续治理（P9 收尾，docs 红线/漂移随改随清）。

## 七、执行纪律（勿忘）

- 测试唯一命令 `~/miniconda3/envs/ibci/bin/python -m pytest tests/`；基线以实跑为准。
- 全程本地 commit；**禁 push**（除非用户显式授权——本排布写入时的 push 授权不自动延续到后续）。
- 工作模式定论（NEXT_STEPS ⛔）全程适用；注释纪律（禁任务代号/历史叙述，规范编号保留）。
- goal 配置习惯：`max_auto_turns` = 7；objective 按 HANDOFF §1.3 模板。
