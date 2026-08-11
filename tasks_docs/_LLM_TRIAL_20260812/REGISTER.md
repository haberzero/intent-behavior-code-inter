# REGISTER — 真实 LLM 全面压力试用结果寄存器

> 2026-08-12。每例一行：用例 / 文档引用 / 期望 vs 实际 / 分类 / 严重级别 / 证据日志 / 备注。
> 分类：PASS | KERNEL_ISSUE | DOC_ISSUE | LLM_BEHAVIOR | LIMIT | BOUNDARY | HARNESS。
> 级别：P0（崩溃/死循环/数据损坏）/ P1（明确缺陷，重要语义错误）/ P2（缺陷，较轻）/ P3（文档/体验）。
> 详细机械记录见 `logs/register.jsonl`；完整运行输出见 `logs/<case_id>.log`。

## 执行批次 1（D1 01-02 章，确定性核心）

| case_id | 文档引用 | 期望 | 实际 | 分类 | 级别 | 证据 | 备注 |
|---------|---------|------|------|------|------|------|------|
| D1-01-001-basetypes | 01_types §1.1 | 基础类型赋值 + type() 规范名 | a_type=int b_type=float c_type=str d_type=bool e_type=list f_type=tuple g_type=dict DONE | PASS | - | logs/D1-01-001-basetypes.log | |
| D1-01-002-containers | 01_types §1.2/§1.3.1 | 泛型容器 + Optional API | first=1 n=b alice=95 or_else=0 unwrap=1 is_some=True DONE | PASS | - | logs/D1-01-002-containers.log | |
| D1-01-003-casts | 01_types §1.4/§1.3 | 类型转换 + None 语义 | 见 log（exit=0 DONE） | PASS | - | logs/D1-01-003-casts.log | |
| D1-02-001-auto | 02_variables §2.2/§2.3 | auto 推断锁定 + 裸赋值 | exit=0 DONE | PASS | - | logs/D1-02-001-auto.log | |
| D1-02-002-unpack | 02_variables §2.4/§2.5 | 元组解包 + 交换 | a=10 b=20 xyz=pqr after_swap 2/1 DONE | PASS | - | logs/D1-02-002-unpack.log | |
| D1-02-003-scope | 02_variables §2.6/§2.7 | global/nonlocal/自动捕获 | 见下 DOC-ISSUE-001 + KERNEL-ISSUE-001 | MIXED | P1 | logs/D1-02-003-scope.log | |
| D1-02-003b-global-min | 02_variables §2.6 | global 最小复现 counter=1 | RUN_UNDEFINED_VARIABLE: `scope_.../bump:counter` is not defined | KERNEL_ISSUE | P1 | logs/D1-02-003b-global-min.log | 确认缺陷，见 KERNEL-ISSUE-001 |

## 执行批次 2（D1 03-14 章，LLM 半 + 并发/模块/内建）

| case_id | 文档引用 | 期望 | 实际 | 分类 | 级别 | 证据 | 备注 |
|---------|---------|------|------|------|------|------|------|
| D1-03-001-arith | 03_operators §3.1 | 算术含地板除/位运算 | a=13 b=3 c=3.5 ... s=ababab DONE | PASS | - | logs/D1-03-001-arith.log | |
| D1-03-002-cmp | 03_operators §3.2-3.5 | 比较/逻辑/成员/身份/三元 | 全对 DONE | PASS | - | logs/D1-03-002-cmp.log | |
| D1-04-001-flow | 04_control_flow §4.1-4.4 | if/for range/break/continue | 全对 DONE | PASS | - | logs/D1-04-001-flow.log | |
| D1-04-002-switch-exc | 04_control_flow §4.5-4.7 | switch/异常/自定义异常/窄化 | sw_ok caught finally narrowed 503 DONE | PASS | - | logs/D1-04-002-switch-exc.log | 需补 __init__->auto（DOC-ISSUE-002） |
| D1-05-001-funcs | 05_functions §5.1/5.1.1 | 默认值/具名/*args/splat | 全对 DONE | PASS | - | logs/D1-05-001-funcs.log | |
| D1-05-002-recursion | 05_functions §5.3-5.7 | 递归/嵌套/fn/高阶/内省 | fac5=120 sig=fn_callable[...] DONE | PASS | - | logs/D1-05-002-recursion.log | |
| D1-05-003b-deeprec | KNOWN_LIMITS §二十三 | 深递归根因 RecursionError | RecursionError 根因保留（未包装成语义错误）+ 环境限制警告 | PASS | - | logs/D1-05-003b-deeprec.log | KDIAG 行为符合文档 |
| D1-05-006-lambda | 07 §7.4 + 05 §5.5 | lambda 延迟/调用时敏感 | defined_no_call result=2 g_type=str DONE | PASS | - | logs/D1-05-006-lambda.log | |
| D1-05-007-snapshot | 07 §7.4 snapshot | 定义时冻结意图 | reply2 不受调用处 @! 影响（完整回复） | PASS | - | logs/D1-05-007-snapshot.log | snapshot 免疫调用处意图实证 |
| D1-05-008-generator | 05 §5.8 | yield+LLM 组合/to_list | 2 个 LLM 产出 + to_list=3 + gen_type=generator | PASS | - | logs/D1-05-008-generator.log | |
| D1-05-008b-tolist | 05 §5.8 + U1 | to_list/generic_next 显式调用（A3） | to_list_len=4 next_first=0 gen_type=generator | PASS | - | logs/D1-05-008b-tolist.log | A3 重验通过 |
| D1-02-006-shadow | 12 §12.1 + 07 §7.2 | 内建遮蔽 + LLM 初始化（A2） | sum=7 len_shadow=5 | PASS | - | logs/D1-02-006-shadow.log | A2 重验通过 |
| D1-06-001-oop | 06_oop §6.1-6.6 | 类/继承/super/协议/类内 LLM | dist=25.0 speak=Rex says Woof! greet=你好，小明！ | PASS | - | logs/D1-06-001-oop.log | |
| D1-06-003-enum | 06_oop §6.5 + KNOWN_LIMITS §二 | LLM 输出枚举 + switch | chosen=GREEN sw_green | PASS | - | logs/D1-06-003-enum.log | |
| D1-07-001-immediate | 07 §7.1 | 即时 @~ + $插值 | greeting=你好！我是 Alice... joke_len=22 | PASS | - | logs/D1-07-001-immediate.log | |
| D1-07-002-typed | 07 §7.2 | int/bool/float/list 类型约束解析 | answer=2 ok=True pi=3.14 tags_len=3 | PASS | - | logs/D1-07-002-typed.log | 格式服从稳定 |
| D1-07-003-boolctx | 07 §7.3 + KNOWN_LIMITS §二十一 | if/for 布尔上下文 | negative=true count=1/2/3 | PASS | - | logs/D1-07-003-boolctx.log | |
| D1-07-005-runbatch | 07 §7.4 + A5 | run_batch 并发保序 + 观测（A5） | batch_len=3 info_keys 完整 3 项总结 | PASS | - | logs/D1-07-005-runbatch.log | A5 重验通过 |
| D1-07-006-namedmodel | 07 §7.5 | 命名模型路由 | t=炽热 | PASS | - | logs/D1-07-006-namedmodel.log | |
| D1-08-001-llmfunc | 08 §8.1-8.3 | llm 函数 + __llmretry__ | translated=你好，世界 parsed=12 | PASS | - | logs/D1-08-001-llmfunc.log | |
| D1-09-001-intent | 09 §9.1/9.2 + A1 | 意图 @/@!/@+ 真实生效（A1） | r1=收到（冷酷极简）b1=True a1/a2 短 a3 长 | PASS | - | logs/D1-09-001-intent.log | A1 赋值路径重验通过（7339220 实证） |
| D1-09-004-intentctx | 09 §9.3 + KNOWN_LIMITS §十二 | intent_context use 生效 | r1=蔚蓝辽阔高远 r2=详细专业长回复 | PASS | - | logs/D1-09-004-intentctx.log | |
| D1-10-001-llmexcept | 10 §10.1-10.2 | llmexcept/llmretry 收敛 | result=2 res_len=2 | PASS | - | logs/D1-10-001-llmexcept.log | |
| D1-11-001-modules | 11 §11.4-11.5 + A4 | isys/idbg 观测（A4） | info_keys=[sys_prompt,user_prompt,response,raw_response,active_intents,global_intents,merged_intents] | PASS | - | logs/D1-11-001-modules.log | A4 重验通过（dispatch 后立即可观测） |
| D1-11-002-modimport | 11 §11.1 | 整模块 import + 命名导入 | INT_INTERNAL_ERROR | KERNEL_ISSUE | P1 | logs/D1-11-002-modimport.log | 见 KERNEL-ISSUE-002 |
| D1-11-002d/e-modimport-* | 11 §11.1 | 整模块 import 隔离复现 | 函数/变量导出均 INT_INTERNAL_ERROR | KERNEL_ISSUE | P1 | logs/D1-11-002d/e.log | KERNEL-ISSUE-002 确认 |
| D1-11-002g-namedimport | 11 §11.1 | 命名导入对照 | square=36 | PASS | - | logs/D1-11-002g-namedimport.log | 缺陷限定整模块路径 |
| D1-11-005-ihost | 11 §11.6 + B1 | run_isolated 隔离执行 | CHILD_RUNNING result_ok=True | PASS | - | logs/D1-11-005-ihost.log | B1 补记 |
| D1-11-006-filejson | 11 §11.7-11.8 | file 读写/覆盖/json | content=new content parsed_name=Alice DONE | PASS | - | logs/D1-11-006-filejson.log | |
| D1-11-002m-mockreal | 13 §13.1 | MOCK 指令未启用时真实行为 | MOCK: 字样当普通提示词发给真实 LLM | PASS | - | logs/D1-11-002m-mockreal.log | 文档一致（MOCK 需显式启用） |
| D1-12-001-builtins | 12 §12.1-12.5 | 内建转换/序列辅助/方法 | 全对 DONE | PASS | - | logs/D1-12-001-builtins.log | |
| D1-14-001-concurrency | 14 §14.2-14.7 | chan/slot/thread/await | msg=hello pubsub=77 slot=42 cas=11 thread=3 await_thread=30 | PASS | - | logs/D1-14-001-concurrency.log | 需修正 await 返回 thread_result（DOC-ISSUE-003） |

## 缺陷记录

### DOC-ISSUE-001 — `02_variables.md §2.6` 示例缺返回标注
- **复现**：`func increment():` 无 `-> TYPE` → `SEM_MISSING_RETURN_ANNOTATION` 编译错误。
- **文档**：docs/syntax/02_variables.md §2.6 示例（与 05_functions.md §5.1 强制标注矛盾）。
- **实际**：示例直接照抄会编译失败。
- **级别**：P3（文档）。
- **处置**：本 trial 用例按 05_functions 正确用法补 `-> void` 后继续。

### KERNEL-ISSUE-001 — `global` 写访问在函数内运行时未定义变量
- **复现**：`int counter = 0; func bump() -> void: global counter; counter = counter + 1` 调用 `bump()` →
  `[ERROR][RUN_UNDEFINED_VARIABLE]: Variable UID 'scope_cases.../bump:counter' is not defined`。
- **文档**：docs/syntax/02_variables.md §2.6 明确 `global` 应使函数内读写作用于模块级变量。
- **实际**：编译通过但运行时按函数局部作用域查找 UID 失败（UID 前缀含 `bump:` 局部作用域）。
- **级别**：P1（明确语义错误）。
- **证据**：cases/D1-02-003b-global-min.ibci + logs/D1-02-003b-global-min.log。
- **备注**：tests/ 无任何 `global` 关键字覆盖（grep 仅命中 global_intents 无关项）——机制或从未被测试。

### KERNEL-ISSUE-002 — 整模块 `import mod` + 成员访问触发编译器 INT_INTERNAL_ERROR
- **复现**：模块 `greeting_mod.ibci` 导出函数 `func greet() -> str`，主文件 `import greeting_mod` +
  `greeting_mod.greet()` → `INT_INTERNAL_ERROR: 'FunctionSymbol' object has no attribute 'type_ref'`。
  变量导出同样触发（`'VariableSymbol' object has no attribute 'type_ref'`）。
- **文档**：docs/syntax/11_modules.md §11.1（模块导出规则：导出成员含用户定义符号；`import ai` 等
  整模块导入为文档化用法）+ KNOWN_LIMITS §十八（跨模块 import 合法，仅禁循环）。
- **实际**：整模块 `import` + 成员访问在编译期崩溃；`from helper import square` 命名导入**正常**
  （D1-11-002g 通过）——缺陷限定在整模块导入+属性访问路径。
- **级别**：P1（编译器内部错误，正常输入触发）。
- **证据**：cases/D1-11-002d/e-modimport-*.ibci + logs/D1-11-002d/e-modimport-*.log。
- **备注**：tests/runtime/test_ibc_file_imports.py 仅覆盖命名导入与 import-*，无整模块+成员访问覆盖。

### DOC-ISSUE-003 — `14_concurrency.md §14.6` await thread 示例自相矛盾
- **复现**：文档示例 `int v = await t` 但紧跟说明"await thread[T] 的结果类型为 thread_result[T]"；
  编译器实际为 `thread_result[T]`（`int v = await t` 报 SEM_TYPE_MISMATCH）。
- **级别**：P3（文档）。
- **处置**：本 trial 用例按声明语义改 `thread_result[int] av = await t2; av.expect()`。
