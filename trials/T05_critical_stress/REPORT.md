# T05 批判性压力试用报告（2026-08-14）

> 基线：unsafe-vibe-dev 6e68329c（跨模块同名类运行期 module 化根治后，全量
> 2614 passed / 1 skipped）。试用对象：最新内核 + 全部技术文档。
> 方法：40 用例（12 跨模块 + 20 对抗 + 8 真实 LLM）经 harness 死循环保护运行 +
> 文档全量核验（subagent 审计 + 主代理抽查）。**本任务是试用/记录/汇报任务，
> 不做修复**；发现的问题只登记。

## 一、结果总览

| 层 | 用例 | 结果 |
|----|------|------|
| D1 跨模块同名类根治回归 | 12 | **12 PASS**（方法表隔离/嵌套包/泛型继承/序列化/遮蔽全过） |
| D2 对抗组合（挑刺） | 20 | **17 PASS + 1 GUARD + 2 KERNEL_ISSUE** |
| D3 真实 LLM（qwen3.6-35b-a3b） | 8 | **8 PASS**（意图/typed 解析/enum LLM/llmexcept/mock↔真实/长提示全过） |
| D4 文档全量核验 | — | **23 DOC_ISSUE**（P1×4 / P2×11 / P3×8）+ 3 嫌疑点确认 |

**内核核心结论**：跨模块类表 module 化根治在 12 项判别性回归 + 20 项对抗组合下
**零回归、零新缺陷**；并发路径暴露 1 项既有缺陷（线程 worker 内跨模块类不可用），
Optional 判空暴露 1 项文档/语义不一致。文档健康度明显低于代码健康度（23 处问题，
含 3 处 KNOWN_LIMITS 自身不成立）。

## 二、内核发现（KERNEL_ISSUE，只记录 + 粗略根因方向）

### KI-1（P1）线程 worker 内被 import 模块的用户类不可用

- **现象**：`thread(callable=compute)` 内 `geo.Box(5).get()` 抛 `ThreadFailed`（底层
  `Symbol UID missing for name 'v'`）；主上下文同调用正常（405）；入口模块类在 worker
  内正常。**base（main 分支）同现**——既有缺陷，非本次 module 化引入。
- **粗略根因（代码实证）**：线程任务本地 `task_ec.get_side_table` 回调委托
  `interpreter.get_side_table`（coordinator.py:213），后者读 **interpreter 共享的**
  `current_module_name`（interpreter.py:352），忽略 task_ec 任务本地的
  `current_module_name`（coordinator.py:235 有意设为任务本地）。`_vm_call_user_function`
  把 task_ec 切到 "geo"（_shared.py:261），但侧表查询仍按 interpreter 的模块（main）
  查 → imported 方法体的 `node_to_symbol` 查空。入口模块类因 = main/entry 模块恰好命中。
- **修复方向**：`get_side_table` 侧表查询须以**调用方 EC 的 current_module_name** 为准
  （回调改为使用 task_ec 自身模块，或 `get_side_table` 接受调用方模块参数）；对齐
  coordinator 注释"任务本地 current_module"的设计意图。
- **登记**：PENDING_TASKS（KERNEL_ISSUE-CROSSMOD-THREAD-1）。

### KI-2（P2）`Optional[T] a = None; a is None` 返回 False

- **现象**：`Optional[int] a = None; a is None` → False；`any b = None; b is None` →
  True；`a == None` → True；`a.is_none()` 方法不存在。文档 03_operators.md:70 声称
  `x is None 判 None`。
- **粗略根因（代码实证）**：`is` 的 None 分支用 `isinstance(left, IbNone)`
  （leaf.py:269-277）；Optional 空值被 `IbOptional(is_some=False)` 包装（非 IbNone）。
  `IbOptional` docstring 自述"空（payload 为 None，语义上是 None）"——与 `is None`
  False 结果自相矛盾。`OptionalAxiom` 声明了 `is_none`（arch/03_type_system §8）但
  `IbOptional` 未实现。
- **修复方向**：`is None` 对 `IbOptional(is_some=False)` 返回 True（语义一致）；
  或补 `is_none()` 方法并让文档统一判空 API。与 DOC_ISSUE-5/-6 关联。
- **登记**：PENDING_TASKS（KERNEL_ISSUE-OPTIONAL-ISNONE-1）。

## 三、文档发现（23 DOC_ISSUE，完整清单见 REGISTER.md）

### 高价值（P1/P2 精选）

1. **mock 值解析与文档不符**（P1）：`MOCK:STR:hello world` 只返回 `hello`
   （实现 `split()[0]`）；`MOCK:BOOL:1/True` 判真与文档相反（仅 `TRUE` 大写判真）。
   影响 13_mock_testing/guide/07/07_behavior_expressions 四处文档。
2. **KNOWN_LIMITS 自身 3 处不成立**（P2）：§七 any→用户类恒 RUN_TYPE_MISMATCH
   （普通 any 值不报）、§八 `auto x = mixed[0]` 编译失败（实测锁定 int）、§十三
   连续/悬空 one-shot 报 SEM_INTENT_PLACEMENT（实测不拦）。
3. **诊断码文档与实现脱节**（P2）：15_diagnostics 的 8 个码（RUN_DIVISION_BY_ZERO/
   RUN_ATTRIBUTE_ERROR/RUN_INDEX_ERROR/RUN_PERMISSION_ERROR/RUN_LLMEXCEPT_SNAPSHOT_
   VIOLATION/LEX_INVALID_NUMBER/PAR_INDENTATION_ERROR/PAR_MULTIPLE_INTENTS）在
   core/ 全仓零引用（从未发射）；快照篡改警告（RUN_LLMEXCEPT_SNAPSHOT_VIOLATION）
   实为静默恢复。
4. **Optional 判空误导**（P2）：03_operators `is None` + arch/03_type_system
   `is_none()` 缺失（关联 KI-2）。
5. **示例不能编译**（P1×2）：guide/06 lambda 多行语句体、01_types cast_to 覆盖。
6. **文档间自相矛盾**（P2）：09_intent_system §9.3 缺 `use(ctx)`（与 KNOWN_LIMITS
   §十二矛盾）；howto/use_generators 惰性 for 与 05_functions §5.8 急物化矛盾；
   14_concurrency §14.1"共享只读类型定义"与 KI-1 矛盾。
7. **语义不精确**（P3）：`auto nums=[1,2]` 注释、`find_last` 索引、`behavior[(auto)
   ->str]` 形态、`set_mock_mode()` 单向性未说明、TESTONLY 遗留术语、2 个诊断码
   严重级别标注错误。

## 四、批判性评价

**代码/内核**：
- 跨模块类表 module 化在判别性 + 对抗 + 真实 LLM 三层下**稳健**（40 例 37P+1G）。
  泛型/类/容器/并发/生成器/运算符重载/import 等对抗场景无回归，遮蔽/守卫/类型安全
  边界表现符合预期（D2-04 any 守卫、D2-02 遮蔽守卫、D2-16 泛型运算符）。
- **主要风险面在并发**：线程 worker 的模块上下文隔离设计（任务本地 current_module
  与共享侧表回调）存在既有裂缝（KI-1），且 `14_concurrency` 文档给出相反承诺。
  这是"任务本地状态 + 共享只读回调"模式的系统性脆弱点，值得专项审计。
- **Optional 语义**：`is None`/`is_none()`/`== None` 三套判空路径不一致，是类型
  系统文档/实现对齐的典型薄弱点（KI-2 + DOC-5/-6）。
- **诊断码卫生**：8 个"幽灵码"（文档声称可触发、实现从未发射）说明诊断码目录的
  可发射性校验缺失（CAT-6 只校验码集合一致性，不校验发射）。

**文档**：健康度显著低于代码。23 处问题中 P1×4（示例不能运行/结果不符）、
P2×11（语义误导/自相矛盾/与实现脱节），**KNOWN_LIMITS 自身 3 条不成立**——文档
既是人类手册也是缺陷线索库，其失真是系统性风险（doc-governance 应纳入常态化）。

**环境**：本机 LLM 服务响应 <1s/调用且 reasoning_tokens=0，与 LLM_SERVICE.md §二.1
记录的 10-30s 思考耗时明显不符（环境事实，疑为快速模式/缓存）；不影响 D3 结论。

## 五、建议方向（供后续独立窗口参考，非本任务执行）

1. **KI-1**：线程 worker 侧表查询以调用方 EC 的 current_module_name 为准 + 并发
   专项审计（任务本地状态 vs 共享回调的裂缝面）。
2. **KI-2 + DOC-5/-6**：统一 Optional 判空语义（`is None` 对空 Optional 为 True +
   实现 `is_none()`），文档同步。
3. **DOC 批次**：mock STR/BOOL 值语义（修实现或修文档，取实现为准）、KNOWN_LIMITS
   §七/§八/§十三 三条实证修正、15_diagnostics 8 个死码（删除或实现发射）、
   2 处 P1 示例修正、`set_mock_mode` 单向性补说明。
4. **诊断码可发射性契约**：catalog 码应校验"有发射点"（杜绝幽灵码）。
5. **并发边界登记**：KNOWN_LIMITS 补"线程 worker 内跨模块类不可用"。
