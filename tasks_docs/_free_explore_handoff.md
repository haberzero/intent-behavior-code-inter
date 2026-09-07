# _free_explore_handoff — free-explore 分支状态交接快照（暂停点 2026-09-06）

> **临时交接文档**：本 session 暂停点的全量状态记录（用户指令：暂停前处理好紧急记录与
> 状态评估/分析）。恢复工作时按 §六 速查接手；任务队列动态化（goal 授权），本文档为
> **快照**非权威——权威以 tasks_docs 各常驻文档 + trials/INDEX.md + git log 为准。

## 一、本 session 使命与授权

- 用户指令（2026-09-06）：自由探索 + 超长期无人值守；**所有工作只在独立分支
  `free-explore`**（不污染 main / unsafe-vibe-dev）；不请求任何权限（用户不在场）；
  35B 小模型端点（`TEMP-35B-LLM-GUIDE.md`，根目录，gitignored）可自由使用。
- **goal**：`goal-0756d638-e10e-4ca4-b9fd-cdd25dfe355d`（宽主线版 rev 2：主线自主权 +
  动态任务队列 + 每轮自主决断；max_goal_rounds=200）——**暂停点已置 pause**；
  用户请求继续时 `update_goal action resume` 重新武装。
- 分支：`free-explore` @ `origin/unsafe-vibe-dev` 尖端 b89fdc39 起步（基线全量
  pytest 3198/1 已验证）；**禁 push**（用户硬原则）。
- skills 已加载（固定组合）：code-workflow / code-quality / user-principles /
  design-philosophy；其余按任务类型在恢复后按需加载。

## 二、已完成工作（暂停点已 commit 部分见 git log）

### 2.1 环境基建

| 项 | 状态 |
|----|------|
| `.venv`（规范 recipe：`python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`） | ✅ 本机唯一运行环境（无 conda ibci env） |
| `api_config.json`（仓库根单源，gitignored） | ✅ 35B 端点 + default/qwen35 双命名 + probe OK |
| `AGENTS.local.md`（本机事实层，gitignored） | ✅ 解释器 / 端点 / 密钥通道 / 探测命令 |
| 35B 端点实证 | ✅ 双字段思考抑制有效（reasoning_tokens=0）/ probe 184ms |

### 2.2 阶段 C 残留：全量真实 LLM 回归复跑（10 套件 122 llm 用例，35B 共享端点）

**分类汇总**（自动判定，batch_result.jsonl 在各套件 logs/）：

| 套件 | llm 例 | 结果 |
|------|--------|------|
| T01_llm_full | 57 | 52 PASS + GUARD×3（D2-33/D2-36/D3-60 预期守卫）+ LLM_BEHAVIOR×1（D3-40）+ HARNESS×1（D1-07-006，端点泄漏） |
| T02_enum_import | 3 | 3 PASS |
| T07_fixes_critical_stress | 7 | 7 PASS |
| T08_llm_pressure | 37 | 27 PASS + LLM_BEHAVIOR×4（D3-03/04/06/07）+ GUARD×1（D5-04）+ BOUNDARY×1（D5-08，已登记 BOUNDARY-LLM-2 域）+ LIMIT×1（D6-06，已登记）+ **D5-02 SIGSEGV→STREAM-1** + D1-02 首跑 HARNESS（复跑 PASS=LLM_BEHAVIOR）+ D5-03 HARNESS（端点泄漏） |
| T09/T10/T11/T12/T13/T15 | 6/4/2/1/2/3 | 全 PASS |

**分诊结论**：
- LLM_BEHAVIOR 项（6 例）= 35B 共享端点输出非确定（D1-02 手动重跑 PASS 实证）——
  **非内核缺陷**；断言稳健性属既有设计（expect-out 取稳定可判部分）。
- **HARNESS 端点泄漏（待修）**：T01 `D1-07-006-namedmodel` / T08 `D5-03-named-model`
  在 **tracked 用例文件内硬编码 `http://localhost:8001/v1`**（旧本机端点机器特定值
  泄漏入库，与 T1 配置单源收敛方向相悖）。修复方向（已定案未实施）：端点 URL 走
  环境变量通道（与 `IBCI_TRIAL_LLM_KEY` 同构，新增 `IBCI_TRIAL_LLM_URL`），
  两用例改读 env；`LLM_SERVICE.md` §五 同步；AGENTS.local.md 补导出行。
- GUARD / BOUNDARY / LIMIT 项 = 已登记预期分类，无新发现。
- **覆盖缺口**：T06（7 llm 用例，子目录布局）run_batch 不收集（只收 `cases/*.ibci`
  顶层）——历史 T09 回归已覆盖 T06，严格复跑有缺口；恢复时手工经 harness 跑或
  扩展 run_batch 收集策略（后者涉 harness 变更，需评估）。

### 2.3 KERNEL_ISSUE-STREAM-1（流句柄退出段错误）——发现 → 修复 → 验证

- **现象**：T08 `D5-02-stream-channel` 间歇 SIGSEGV（exit=-11；用例输出完整，崩溃在
  进程退出阶段；2 并发 4/12 复现、单发 0/15；faulthandler：线程死在 C 扩展内）。
- **根因**：`ai.stream_channel` 只把 ChannelCore 交给用户（句柄不可达）；脚本放弃流
  后 daemon 消费线程仍在 C 扩展内消费活 HTTP 流 → 解释器终结不等待 daemon →
  C 扩展状态释放竞态。叠加 provider `_gen()` 无 finally 关 HTTP 流（资源不闭环）。
- **修复（三层单链，`tasks_docs/_stream_segfix.md` 设计文档）**：
  1. `IbStreamHandle.cancel()` 协作式截断——**置标志不碰生成器**（CPython 实测：
     对运行中生成器跨线程 `gen.close()` 抛 `ValueError: generator already executing`
     → **生成器单写者原则**：消费线程在协作点检查标志、finally in-thread close）；
  2. producer 契约 = 生成器（消费入口 fail-fast TypeError；mock 路径 `iter([...])`
     同步改生成器）+ provider `_gen()` `finally: stream_resp.close()`；
  3. atexit live 注册表 drain（cancel + 有界 join 2s；daemon 语义不变：永不阻塞退出）。
- **实施中发现并修复的自伤 bug**：live 登记原在 `thread.start()` 之后——快速流在
  `__init__` 返回前消费完毕 → finally discard 先于 add → 句柄永久残留（注册表泄漏）；
  改为**先登记后启动**。
- **验证**：pytest 新增 7 判别（cancel 截断/首块前取消/幂等/自然完成后 no-op/atexit
  drain/契约违约 fail-fast/零残留）；streaming 16 测全绿；**并发复现门 24/24 零段错误**
  （修复前 4/12）；全量 pytest **3204/1 零回归**（连跑 4 次）。
- **已知角落（记录不修）**：LLM 挂死 >2s 时 atexit join 超时，残留同型竞态窗口
  （设计文档 §五）；彻底消除需 provider 层 C 级协作取消，归 C6 评估。
- **后续项**：① coordinator `SpawnedTask` 同型风险（阻塞外部 I/O 的用户任务）→
  质量维护 Tier C 专项评估；② 用户层显式流截断 API（chan 面）→ C6（批 3）评估。

### 2.4 新发现（未开工，登记备查）

- **LLMParseError 渲染质量**（B1 邻近项）：T08 D1-02 失败日志中运行错误消息为
  `Runtime Error: <LLMParseError object at 0x...>`——Python 对象 repr 直漏，
  无诊断码/无解析细节/无源码位置。归入批 1 B1（运行错误携带 ibci 源码行号）
  统一设计；单独小修也值得（错误对象 `__str__`/渲染链）。

## 三、暂停点待办（按优先级）

1. **T2 语言层环境变量通道 + `idbg.env()` 命名冲突**（阶段 E，设计未开始——
   读 `_next_phase_targets.md` §二 T2 + `core/compiler` 内建面 + design-philosophy
   命名粒度统一）。
2. **恶意边界未测 #15/#17/#19**（探索结论与用例设计见 §四；mock 层，确定性快）。
3. **named-model 端点泄漏修复**（2 用例 + LLM_SERVICE §五 + AGENTS.local.md）。
4. **T5 文档示例验证闭环**（阶段 E 小项：文档代码块与内核对账机制可行性评估）。
5. **BOUNDARY-LLM-5 裁定收敛**（mock call_info 无 sys_prompt 键——INDEX 已有
   2026-09-05 补充实证，待 doc-governance 复核收敛关闭或维持登记）。
6. **#33 `_pending_futures` 长会话内存面**（依赖 LLM-5 同子系统，随其修复后观测）。
7. **批 1 ref P0 语言大项**（C2/C3/C4/B1/A3/A1/B3；C1 embedding 已立项解封
   PT-FEAT-16，设计文档 `tasks_docs/_embedding_design.md` 存在）。

## 四、恶意边界用例设计快照（#15/#17/#19 探索结论，2026-09-06）

**语法/机制实证**（设计依据，全部已核代码）：
- 用户类：auto-构造 `Box[int](42)`（字段按声明序位置参）；字段赋值 `s.value = expr`；
  枚举 `class Color(Enum): str RED = "RED"`，成员 `Color.GREEN`，`==` 身份比较可用。
- `intent_context` 全方法面（公理 `core/kernel/axioms/intent_context.py` +
  原生注册 `primitive_initializer.py` §5.6）：`intent_context()` 空构造 /
  `push(content[, tag])` / `pop()` → 渲染文本 / `fork()` / `resolve()` → **意图
  字符串 list（任意 ctx 实例的状态观测面）** / `merge` / `combine` / `clear` /
  `clear_inherited` / `use(ctx)`（替换当前作用域 = fork(ctx)，非引用）/
  `get_current()` / `__to_prompt__`。
- snapshot 机制（`llm_behavior.py` vm_handle_IbLambdaExpr + `_shared.py`
  `_vm_call_fn_callable`）：定义时自由变量 `try_deep_clone` 深克隆为种子 +
  意图 `fork_intent_snapshot()` 冻结；调用时对种子**再深克隆**一份私有副本；
  `try_deep_clone`（`core/runtime/objects/deep_clone.py`）line 120 有
  `IbIntentContext` → `fork()` 专支（类字段路径 = #15 目标）。
- save/load_state（ihost → 内核 HostService → `runtime_serializer.py`）：
  用户类实例 `_collect_object` + qualified 类名（module 感知）；特化类
  `_hydrate_specialized_class`（type_pool 重建 spec；注册表封印回落基类 +
  KDIAG_RUNTIME_SPECIALIZATION_FALLBACK 诊断，KNOWN_LIMITS §十 契约）；
  intent_context 专用 collector/wrapper；pytest 层（`test_host_save_state.py`）
  只覆盖文件布局，**值保真（特化类/枚举/意图）无覆盖 = #17 真实缺口**。
- overlay：编译期 `_overlay_registry` / binding_analysis 等 pass；T12 mock 层
  基本覆盖（overlay 端到端/嵌套/守卫）；#19 = overlay × (save/load_state /
  snapshot / llmexcept retry) 交互未测。
- 列表方法 `len()` 是 `.len()`（方法非内建）。

**用例设计（T15 新增，mock 层确定性）**：
- **#15 → `T15-E-M29-ctx-classfield-deepclone.ibci`**：`class Holder: intent_context
  ctx`；`Holder h = Holder(base)`（base 含 FROZEN_A）；`fn snap = snapshot -> str:
  h.ctx.use(h.ctx) 后 mock LLM 调用`；定义后 `h.ctx.push("LIVE_B")`；断言
  ① 快照内 merged 含 FROZEN_A ② 不含 LIVE_B（冻结 fork 不泄漏后定义 push）
  ③ 原 h.ctx.resolve() 仍恰 2 项（反向隔离：快照 use 不污染原 ctx）。
- **#17 → `T15-E-M30-state-crossengine-types.ibci`**：save_state → 变更变量 →
  load_state → 三断言（M28 同构模式）：`Box[int](42)` 值+方法保真 /
  `list[Box[int]]` 容器元素保真 / 枚举成员 `==` 身份保真；（意图上下文 M28 已覆盖
  基础，可加 combine/override 变体作对抗加料）。
- **#19 → `T15-E-M31-overlay-serialization-snapshot-retry.ibci`**：overlay 覆层
  类 × save/load_state（覆层状态 round-trip 保真）+ × snapshot（覆层自由变量
  捕获）+ × llmexcept retry（覆层类字段快照隔离）；三子断言合一用例或拆分
  三例，实施时按 T15 命名纪律定。

## 五、状态分析与风险注记

1. **退出期崩溃孤例（未解释，监控中）**：STREAM-1 修复后**首次**全量 pytest
   （后台跑）进程退出期出现 faulthandler 崩溃栈（`pytest/__main__` 入口帧），
   其后 4 次全量 + 24 并发全干净。与修复前流退出竞态同域但无法归因——按
   KERNEL_ISSUE-LLM-5 处置模式（登记观察）：不建投机性修复，复现时 faulthandler
   全套 dump + core 分析。若复现频率上升，优先排查 C 扩展（jiter/pydantic-core）
   终结竞态。
2. **35B 共享端点可用性**：可能随时下线/限流。恢复时先 `probe.py`；失败则
   只跑 mock 组（`--mock-only`），LLM 用例记 HARNESS（环境缺失）不误判缺陷。
3. **分支合并**：free-explore 领先 unsafe-vibe-dev 基线若干提交（本 session
   工作）；用户本次指令"所有工作必须在独立分支，不污染别的分支"→ **merge 动作
   待用户显式决定**（即使满足"确认低风险可直接 merge"细则，也以用户本次指令为准）。
4. **`TEMP-35B-LLM-GUIDE.md`**：含真实 API key（root 目录，未跟踪）——保持
   gitignored/不入库；key 已落入 api_config.json（gitignored）；若仓库外流风险
   顾虑，可后续改 `{env:IBCI_35B_KEY}` 插值形态。

## 六、恢复速查

```bash
cd /home/dsh/proj/intent-behavior-code-inter
git log --oneline -8                      # 确认分支状态（free-explore）
.venv/bin/python -m pytest tests/ 2>&1 | tail -3   # 基线 3204/1（STREAM-1 修复后）
.venv/bin/python trials/_toolkit/probe.py          # 35B 端点活性
# goal: get_goal（goal-0756d638…）→ 用户请求继续时 update_goal action resume
# 任务入口：本文件 §三 待办清单（按优先级）+ tasks_docs/NEXT_STEPS.md
```
