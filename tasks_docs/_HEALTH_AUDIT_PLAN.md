# 内核健康 × 异步统一 × 文档健康 三轴盘点（2026-08-09）

> **性质**：只读调查（general subagent ×2 + 主代理交叉核验）后的下一步规划输入。
> **目的**：从"异步内核彻底统一完整性 + 内核健康 + 技术手册健康"三维度，结合真实代码现状，
> 给出值得做的下一步工作清单。

---

## 一、异步内核彻底统一 完整性（真实遗留）

### 已闭环（核实属实）
- 单调度器（TaskScheduler）+ Waitable 阻塞即挂起 + CPS trampoline（UserFunctionCall 压栈）+ 单一权威驱动
  `_drive_loop_gen`；线程体与宿主均收敛。
- `.call` 四类对象变薄包装（M1）、线程体驱动去重（M2）——统一执行模型"地基"闭环成立。

### 真实遗留（任务内同步重入/嵌套调度器，未彻底统一）——**A1-A4 已完成（2026-08-10）**
| # | 路径 | 位置 | 问题 |
|---|------|------|------|
| ~~A1~~ | ~~**内联 `@~` 行为表达式**~~ | ~~`llm_behavior.py:156`~~ | ~~非赋值上下文走同步 `execute_behavior_expression`~~（已切 `execute_behavior_expression_cps`） |
| ~~A2~~ | ~~**意图消解**~~ | ~~`intent.py:59` `resolve_content`~~ | ~~CPS 路径内仍 `vm.run` 同步重入~~（已 CPS 化：`resolve_content_cps`/`IntentResolver.resolve_cps`/`get_resolved_prompt_intents_cps`） |
| ~~A3~~ | ~~**`_SlotUpdateWaitable._drive`**~~ | ~~`comm.py:281-311`~~ | ~~新建嵌套 TaskScheduler~~（已增 `cps_drive` 帧内驱动） |
| ~~A4~~ | ~~**LLM 函数同步阻塞**~~ | ~~`_llm_function.py:202` `_call_llm`~~ | ~~同步阻塞调度线程~~（已 worker 化 + yield LLMFuture） |
| A5 | **类构造** | `ib_class.py:128` 字段 `vm.run`、`:154` `init_method.call` | 用户 `__init__`/字段默认值在 VM 循环内嵌套调度器（语义边界，独立窗口） |
| A6 | **协议方法 `.call`（条件触发）** | `llm_parsing_strategy.py:196/217`、`llm_except_frame.py:183/273` | 用户定义协议方法时在 VM 循环内嵌套调度器（语义边界，独立窗口） |

### 判定
- **主路径（赋值 dispatch_eager）已异步**；A1-A4 四项次要遗留已消除（2026-08-10）。A5/A6 条件触发且涉语义边界。
- "彻底统一"剩余项：A5/A6（类构造/协议方法，语义边界需独立窗口）。见 `PENDING_TASKS.md` PT-DEBT-16。

---

## 二、内核健康

### 深层嵌套（真实存在，PT-AUDIT-2 深链未处理）
| 深度 | 文件 | 位置 | 方向 |
|------|------|------|------|
| **16/17** | `runtime_serializer.py` `_collect_instance` @212 / `_get_instance` @654 | 巨型 elif 类型分派链（~15 分支） | 分派表 |
| **10** | `core_scanner.py` `_scan_complex_access` @649 | 状态机 | 状态表/守卫子句 |
| 9 | `binding_analysis_pass.py` `_analyze_node` @102 | 符号/赋值分析 | 守卫子句 |
| 9 | `scheduler.py` | 导入解析 | — |

### 疑似死同步包装（CPS 孪生为权威）——**已清理（2026-08-10）**
- ~~`_behavior.py:355` `invoke_behavior`、`:331` `execute_behavior_object`（互引成环，无外部调用）~~——已删
- ~~`_llm_function.py:126` `invoke_llm_function`、`:23` `execute_llm_function`（互引成环）~~——已删
- `run_batch`（`_behavior.py:413`）：**保留**（`ai.run_batch` 语言特性消费，原"仅 docstring 引用"标记为误判）
- 同步 `_prepare_behavior_call`/`_evaluate_segments`：**保留**（dispatch_eager/run_batch 后台线程预求值依赖）

### 双维护点——**已合并（2026-08-10）**
- ~~`_drive_loop_gen`（vm_executor.py:204）与 `_drive_generator_loop`（:317）近全同~~——已合并为单一 `_drive_loop_gen(yield_generator_values=True)`，顺带修复生成器体缺 step/cancel 检查。

### 合法保留（不处理）
- `scheduler.py` 宽 except（3 处）为编译器级 fail-fast 重抛，不吞语言级异常。
- 循环打破局部 import L1-L18 基本全存，为谨慎 tradeoff（低优先级，需架构重构）。

---

## 三、技术手册（docs/）健康

### 明确待修（低风险）——**三修已完成（2026-08-10，PT-DOC-3）**
| 级别 | 位置 | 问题 |
|------|------|------|
| ~~**P1**~~ | ~~`01_principles.md:258`~~ | ~~`IsolationPolicy.inherit_intents` 字段已不存在~~（已改写 §6.3 为现状） |
| ~~**P2**~~ | ~~`04_vm_interpreter.md:29`~~ | ~~"唯一路径"把 `.call` 挂在 `run_body` 上~~（已统一表述） |
| ~~**P2**~~ | ~~`docs/README.md` 目录树~~ | ~~`syntax/` 漏列 `15_diagnostics.md`~~（已补条目） |

### 一致性良好（无需动）
- 04/05 执行模型叙事已高度对齐（TaskScheduler/register_wake/trampoline/_drive_loop_gen/线程体复用/.call 变薄均记录）。
- 05_functions §5.8/5.9 yield、KNOWN_LIMITS §一~§二十五 均一致；无断链；索引全覆盖。

### 体系缺口（规划性）
- How-to 层仅 2 篇，生成器/并发/llmexcept/隔离缺操作指南（Reference→How-to 读者旅程断裂）。

---

## 四、建议的下一步（按优先级 + 风险）

### 第一优先（低风险、立即可做、高一致性价值）——**已完成（2026-08-10）**
1. **技术手册三修**：`01_principles.md:258` P1 过时字段、`04_vm_interpreter.md:29` P2 表述、`README` 目录树补 `15_diagnostics.md`。纯文档，零回归。
2. **PT-DEBT-9/10/11 文档残留清理**：NEXT_STEPS.md:50 旧"遗留技术债"表述与根治状态不同步。

### 第二优先（异步统一完整性，中风险，独立分支）——**A1/A3/A4 已完成（2026-08-10，exp/async-unify-a）**
3. **A1 内联 `@~` 表达式接 CPS**：`vm_handle_IbBehaviorExpr` 切 `execute_behavior_expression_cps`（最高价值，消除主缺口）。**已完成**。
4. **A4 LLM 函数 CPS-yield**：`_llm_function.py:202` `_call_llm` 对齐 behavior 路径（PT-FEAT-1 直接项）。**已完成**。
5. **A3 `_SlotUpdateWaitable` 并入当前调度器**：不再新建嵌套 TaskScheduler。**已完成**。
   **剩余**：A2 意图消解（intent.py:59 `vm.run` 重入，与 A1 同性质，可独立窗口续推）。

### 第三优先（内核健康，中风险，独立分支）
6. 删疑似死同步包装（`_behavior.py`/`_llm_function.py` 4 个方法，先核验无接口引用）。
7. 合并 `_drive_loop_gen`/`_drive_generator_loop` 双维护循环。
8. 巨型分派链扁平化（runtime_serializer/core_scanner/binding_analysis）。

### 需你裁决（不自主）
- A5 类构造 CPS 化、A6 协议方法嵌套——涉及语义边界，建议独立窗口。
- PT-FEAT-1 STREAM 流式接收（依赖已封存的多模态，勿动）。
