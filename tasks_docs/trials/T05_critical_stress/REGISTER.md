# T05_critical_stress REGISTER — 批判性压力试用记录

> 2026-08-14。基线 unsafe-vibe-dev 6e68329c（全量 2614 passed / 1 skipped）。
> 40 用例：**37 PASS + 1 GUARD + 2 KERNEL_ISSUE**；文档核验产出 **23 DOC_ISSUE**。
> 用例脚本错误（thread args / fn_callable 形态 / llmexcept 结构等）均已修正为合法用法，
> 不含内核问题。
>
> **状态更新（2026-08-14）**：KERNEL_ISSUE-CROSSMOD-THREAD-1 **已修复并核销**（统一
> 类身份模型 S4 + T06 D4-01 回归验证）；KERNEL_ISSUE-OPTIONAL-ISNONE-1 与
> DOC_ISSUE-1~23 待修。

## 一、结果总览

| 分类 | 数量 | 说明 |
|------|------|------|
| PASS | 37 | 跨模块类表隔离/边界 + 对抗组合 + 真实 LLM 全部通过 |
| GUARD | 1 | D2-02 用户函数重定义内置 len → SEM_REDEFINITION |
| KERNEL_ISSUE | 2 | D1-10 线程 worker 内跨模块类方法调用失败；D2-03 Optional-None `is None` 语义 |
| DOC_ISSUE | 23 | 文档核验（subagent 全量审计 + 主代理抽查确认） |

## 二、KERNEL_ISSUE 明细

### KERNEL_ISSUE-CROSSMOD-THREAD-1（P1）— 被 import 模块的用户类在线程 worker 内不可用

- **触发用例**：`T05_critical_stress/cases/D1-10/main.ibci`（`thread(callable=compute)` 内
  `geo.Box(5).get()`）
- **证据**：主上下文 `compute()` = 405 正常；线程 worker 内同调用抛 `ThreadFailed`
  （底层 `Symbol UID missing for name 'v'. Artifact is corrupted or unanalyzed`）。
  入口模块类在 worker 内正常（main2 = 405）。**base（main 分支）同现**——既有缺陷，
  非本次 module 化引入。
- **根因方向（初步）**：线程 worker 的 task 上下文未带出方法体所属模块的 artifact
  上下文/符号侧表——方法体字段符号（`v`）解析失败。worker 的模块解析/作用域链未覆盖
  被 import 模块的方法体。
- **级别**：P1（明确缺陷：跨模块类在并发路径不可用，与 14_concurrency §14.1"共享只读
  类型定义"的承诺矛盾）。
- **登记**：PENDING_TASKS（待独立窗口；本任务不修复）。
- **✅ 已修复（2026-08-14，统一类身份模型 S4）**：`get_side_table` module 参数化 +
  `is_truthy` 任务本地化（见 `_code_class_identity_unify.md` S4）。**T06 D4-01 核销**
  （线程 worker 内 `geo.Box(5).get()` = 405，主/线程一致）；判别性回归
  `test_ibc_file_imports.py::test_imported_module_class_in_thread_worker`。

### KERNEL_ISSUE-OPTIONAL-ISNONE-1（P2）— `Optional[T] a = None; a is None` 返回 False

- **触发用例**：`T05_critical_stress/cases/D2-03.ibci`
- **证据**：`Optional[int] a = None; print(a is None)` → False；`any b = None; b is None`
  → True；`a == None` → True。文档 `03_operators.md:70` 声称 `x is None  # x 是否为 None`。
- **根因方向（初步）**：Optional None 被 `IbOptional(is_some=False)` 包装；`is` 对 None
  分支用 `isinstance(left, IbNone)`（leaf.py），Optional 包装非 IbNone → False。
- **级别**：P2（文档/语义不一致；用户按文档判空会走错分支）。
- **登记**：PENDING_TASKS（与 DOC_ISSUE-5 关联；本任务不修复）。

## 三、DOC_ISSUE 明细（23 条，完整报告见试用报告 §四）

| # | 级别 | 文件 | 内容 |
|---|------|------|------|
| DOC-1 | P1 | 13_mock_testing §13.2.1 | `MOCK:STR:hello world` 只返回首个 token（实现 `split()[0]`） |
| DOC-2 | P1 | guide/07_testing:49 | `MOCK:BOOL:1/True` 值语义与实现相反（仅 `TRUE` 判真） |
| DOC-3 | P1 | guide/06_multistep:121 | lambda 多行语句体示例解析失败（lambda 仅单表达式） |
| DOC-4 | P1 | 01_types:77-85 | cast_to 覆盖示例不能编译（参数缺注解 + 类比较） |
| DOC-5 | P2 | 03_operators:70 | `x is None` 对 Optional 误导（与 KERNEL_ISSUE-OPTIONAL 同源） |
| DOC-6 | P2 | arch/03_type_system:434 | `Optional.is_none()` 文档存在、实现缺失 |
| DOC-7 | P2 | KNOWN_LIMITS §十三 | 连续/悬空 one-shot 报 SEM_INTENT_PLACEMENT 不成立（实测不拦） |
| DOC-8 | P2 | 09_intent_system §9.3 | 示例缺 `use(ctx)`，静默无效（与 §十二矛盾） |
| DOC-9 | P2 | KNOWN_LIMITS §八 | `auto x = mixed[0]` 编译失败不成立（实测锁定 int） |
| DOC-10 | P2 | 06_oop §6.5 | 无父类时 `super()` 指向 Object 不成立（运行时错误） |
| DOC-11 | P2 | 15_diagnostics RUN 段 | 8 个诊断码（RUN_*/LEX_*/PAR_*）从未发射，文档声称可触发 |
| DOC-12 | P2 | 10_robustness/arch 04/05 | 快照篡改发 RUN_LLMEXCEPT_SNAPSHOT_VIOLATION 警告不成立（静默恢复） |
| DOC-13 | P2 | 14_concurrency §14.1 | "共享只读类型定义"与线程跨模块类不可用矛盾（同 KERNEL_ISSUE-CROSSMOD） |
| DOC-14 | P2 | KNOWN_LIMITS §七 | any→用户类恒报 RUN_TYPE_MISMATCH 不成立（普通 any 值不报） |
| DOC-15 | P2 | howto/use_generators | for 惰性/break 提前终止与 05_functions §5.8 急物化矛盾 |
| DOC-16 | P3 | 02_variables:21 | `auto nums = [1,2]` 注释"list"应"list[int]" |
| DOC-17 | P3 | 12_builtins:69 | `s.find_last("l")` 索引 9 应 11 |
| DOC-18 | P3 | 15_diagnostics:145 | SEM_IMPORT_CONFLICT 严重级别 ERROR 应 WARNING |
| DOC-19 | P3 | 15_diagnostics:265 | SEM_INTENT_STATIC_CALL 严重级别 ERROR 应 WARNING |
| DOC-20 | P3 | 15_diagnostics:29 | 编译期诊断均 ERROR 的笼统陈述（有 WARNING 例外） |
| DOC-21 | P3 | 多处 | "TESTONLY 模式"术语遗留（实际为 MOCK 模式） |
| DOC-22 | P3 | 05_functions:216 | 签名形态 `behavior[(auto)->str]` 应为 `behavior[()->str]` |
| DOC-23 | P3 | 11_modules/guide 01 | `set_mock_mode()` 单向性未说明（无 off API） |

## 四、真实 LLM 观察（D3，qwen3.6-35b-a3b）

- 意图 @/@!、@~ 类型化解析（int/float/str）、enum 成员名→值、llmexcept 共存、mock↔真实
  切换、长提示格式约束——全部 PASS（8/8）。
- 本机服务响应极快（<1s/调用，reasoning_tokens=0）——疑为 LM Studio 快速模式/缓存，
  与 LLM_SERVICE.md §二.1 记录的 10-30s 思考耗时不符（环境事实，登记）。

## 五、记录与收尾

- 缺陷只登记（PENDING_TASKS），本任务不修复。
- 文档错误同等登记（DOC_ISSUE-1~23），本任务不修文档。
- 全程本地 commit、禁 push。
