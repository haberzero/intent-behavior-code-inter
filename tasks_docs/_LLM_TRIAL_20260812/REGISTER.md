# REGISTER — 真实 LLM 全面压力试用结果寄存器

> 2026-08-12。每例一行：用例 / 文档引用 / 期望 vs 实际 / 分类 / 严重级别 / 证据日志 / 备注。
> 分类：PASS | KERNEL_ISSUE | DOC_ISSUE | LLM_BEHAVIOR | LIMIT | BOUNDARY | HARNESS。
> 级别：P0（崩溃/死循环/数据损坏）/ P1（明确缺陷，重要语义错误）/ P2（缺陷，较轻）/ P3（文档/体验）。
> 详细机械记录见 `logs/register.jsonl`；完整运行输出见 `logs/<case_id>.log`。

## 结果总览（截至本 register 收尾）

- **用例总数**：104 个 cases 文件（含 smoke/deadloop 冒烟验证），113 次 harness 运行；全部经死循环保护。
- **PASS**：绝大多数特性（D1 全语法遍历 15 章 + D2 交叉/正交/多文件 + D3 批判场景）。
- **KERNEL_ISSUE（真实缺陷候选，4 项）**：KERNEL-ISSUE-001（global 写访问）/ 002（整模块 import+成员
  访问 INT_INTERNAL_ERROR）/ 003（真实 LLM provider 失败 LLMCallError 逃逸 try/except）/
  004（ai.get_retry 等文档化 API vtable 未注册）。
- **DOC_ISSUE（7 项）**：DOC-ISSUE-001~007（02_variables 示例缺返回标注 / __init__ 返回标注 /
  await thread 示例矛盾 / stream_call 签名缺失 / howto thread_result .value / SEM_INTENT_STATIC_CALL
  警告未现 / __from_prompt__ 契约未注明）。
- **BOUNDARY（5 项）**：BOUNDARY-001~005（for=to_list 物化 / 生成器 await chan 未复现 KNOWN_LIMITS 24 /
  隔离子环境不继承 LLM 配置 / @! 在 run_batch 仅首调用生效 / probe_model 误判推理模型）。
- **A1-A5 重验点全部通过**；B1-B3 已补正式记录；C1-C4 已测。
- **零死循环**：所有用例在 OS 级超时保护下运行，唯一 TIMEOUT-KILLED 为死循环保护冒烟验证本身。

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

## 执行批次 3（D3 批判检测 C1-C3 + 缺陷记录）

| case_id | 文档引用 | 期望 | 实际 | 分类 | 级别 | 证据 | 备注 |
|---------|---------|------|------|------|------|------|------|
| D3-C1-longprompt | 06 §6.6 __to_prompt__ + C1 | 复杂对象进提示词 | summary 正常（模型要原文因数据只有标签） | PASS | - | logs/D3-C1-longprompt.log | |
| D3-C1b-promptcheck | 06 §6.6 | __to_prompt__ 实际注入 | PROMPT_CONTAINS_TITLE/SECTION=True | PASS | - | logs/D3-C1b-promptcheck.log | 注入完整，C1 通过 |
| D3-C2-nondeterminism | C2 | 非确定性多次差异 | t1=1 t2=1 t3=1 b1/b2=True 稳定 | PASS | - | logs/D3-C2-nondeterminism.log | bool/int 解析稳定 |
| D3-C3-timeout | C3 + 11 §11.3 | 超时抛 LLMCallError 可捕获 | LLMCallError 逃逸 try/except，程序崩溃 | KERNEL_ISSUE | P1 | logs/D3-C3-timeout.log | 见 KERNEL-ISSUE-003 |
| D3-C3d-timeout-tryread | C3 + 04 §4.7 | 同上有变量读 | 同样逃逸 | KERNEL_ISSUE | P1 | logs/D3-C3d.log | KERNEL-ISSUE-003 |
| D3-C3e-llmfn-try | C3 + 04 §4.7 | llm 函数路径同样捕获 | 同样逃逸 | KERNEL_ISSUE | P1 | logs/D3-C3e.log | KERNEL-ISSUE-003（两条路径通用） |
| D3-C3c-mock-parsefail | 04 §4.7 | MOCK LLMParseError 捕获 | caught_parse=... | PASS | - | logs/D3-C3c.log | 对照：MOCK 路径正常 |
| D3-C3f-manual-raise | 04 §4.7 | 手动 raise LLMCallError 捕获 | caught=manual fail | PASS | - | logs/D3-C3f.log | 对照：手动路径正常 |

## 执行批次 4（D2 交叉/正交/多文件 + D3 批判检测补充）

| case_id | 文档引用 | 期望 | 实际 | 分类 | 级别 | 证据 | 备注 |
|---------|---------|------|------|------|------|------|------|
| D2-01-gen-intent-llmexcept | D2 交叉 | 生成器+意图+llmexcept | yield=1/2/3 | PASS | - | logs/D2-01.log | |
| D2-02-thread-chan-batch | D2 交叉 | 线程+chan+run_batch | t1/t2/t3 正确 batch=4 | PASS | - | logs/D2-02.log | |
| D2-03-class-llm-slot | D2 正交 | 类内 LLM+slot | c1=中 shared=2 | PASS | - | logs/D2-03.log | |
| D2-10-edgecases | D2 边界 | 边界值/空/除零 | big/neg/empty/div0_caught | PASS | - | logs/D2-10.log | |
| D2-11-shadow-type | 12 §12.1 | 类型名遮蔽拒绝 | 编译错误 | PASS | - | logs/D2-11.log | |
| D2-12-shadow-builtin | 12 §12.1 | 内建直接赋值拒绝 | SEM_TYPE_MISMATCH | PASS | - | logs/D2-12.log | |
| D2-20-circular-a | KNOWN_LIMITS 18 | 循环导入 | DEP_CIRCULAR_IMPORT | PASS | - | logs/D2-20.log | |
| D2-21-plugin | 11 §11.9 | 插件加载调用 | add=30 mul=25 version=2.0.0 | PASS | - | logs/D2-21.log | |
| D2-30-subclass-init | KNOWN_LIMITS 6 | auto-init 不含父字段 | breed=Husky name_null=True | PASS | - | logs/D2-30.log | |
| D2-31-ref-generator-break | KNOWN_LIMITS 5 + 05 §5.8 | 引用共享/break | a_len=4 GEN_FINISHED consumed=3 | PASS | P3注 | logs/D2-31.log | BOUNDARY-001 |
| D2-32/32b-gen-await | KNOWN_LIMITS 24 | await chan 预期异常 | x=42 正常（未复现文档错误） | BOUNDARY | P3 | logs/D2-32.log | BOUNDARY-002 |
| D2-33-llmexcept-write | 10 §10.3 | retry 写参与变量拦截 | SEM_LLMEXCEPT_BODY_WRITE | PASS | - | logs/D2-33.log | |
| D2-34-llmparse | 04 §4.7 | 裸 LLM 解析失败 | n=大数（可解析） | PASS | - | logs/D2-34.log | |
| D2-35-stream | 11 §11.3 | stream_call 流式 | stream=Python 是... | PASS | P3注 | logs/D2-35.log | DOC-ISSUE-004 |
| D2-36-filewrite-llmexcept | 10 §10.3 + KNOWN_LIMITS 20 | retry 内 file.write 拦截 | SEM_LLMEXCEPT_FILE_WRITE | PASS | - | logs/D2-36.log | |
| D2-40-snap-vs-lambda | 07 §7.4 | 意图冻结 vs 敏感 | snap_len=4 lam_len=64 | PASS | - | logs/D2-40.log | |
| D2-41-higher-order-lambda | 05 §5.6 + 07 §7.4 | 高阶 lambda 调用点意图 | r=你好 | PASS | - | logs/D2-41.log | |
| D2-42/42b/42c-threadresult | 14 §14.7 vs howto | 成员形态 | .value=bound_method .value()=42 | PASS | P3注 | logs/D2-42*.log | DOC-ISSUE-005 |
| D2-50-isolation-llm | 11 §11.6 | 隔离+LLM 链 | 子环境需自带 api_config.json | BOUNDARY | P3 | logs/D2-50.log | BOUNDARY-003 |
| D2-60-closure-generator | 05 §5.4/§5.8 | 闭包+生成器+LLM | x=QQ版 x=QQ版 | PASS | - | logs/D2-60.log | |
| D2-61-llm-chain | 08 §8.1 | LLM 函数三级链 | s1/s2/s3 连贯 | PASS | - | logs/D2-61.log | |
| D2-70-loop-llm | KNOWN_LIMITS 15 + 10 §10.1 | 循环体 LLM+llmexcept | score=4/8/3 | PASS | - | logs/D2-70.log | |
| D2-71-str-bool-edge | KNOWN_LIMITS 21 | str '0' 判真/bool 判假 | str_truthy=True bool_truthy=False | PASS | - | logs/D2-71.log | LIMIT 符合文档 |
| D2-80-batch-persistent | 09 §9.2 | @+ 意图跨 run_batch | 甜/日（一字） | PASS | - | logs/D2-80.log | |
| D2-81-two-batch | C4 | 双批并发 | ra=2 rb=3 无竞态 | PASS | - | logs/D2-81.log | |
| D3-C4-concurrency | C4 | 8路batch+4线程 | batch8=8 thread4=... | PASS | - | logs/D3-C4.log | |
| D3-20-exhaustion | 10 §10 | retry 收敛 | n=1（hint 生效） | PASS | - | logs/D3-20.log | |
| D3-21-exhaustion-hard | 10 §10 + 04 §4.7 | 耗尽捕获 | n=0（模型仍收敛） | PASS | - | logs/D3-21.log | 真实模型服从性好 |
| D3-22-mock-exhaust | 10 §10.3 + 13 | MOCK 耗尽 | exhausted + max_retry=2 | PASS | - | logs/D3-22.log | |
| D3-30-global-intent | 09 §9.1 + 11 §11.3 | 全局意图/标签移除 | r1=注：... r2=正常 a1/a2 差异 | PASS | - | logs/D3-30.log | |
| D3-31-concurrent-llmexcept | 10 + 14 | 线程内 llmexcept+slot | r1=3 r2=8 retry=0 | PASS | - | logs/D3-31.log | |
| D3-40-batch-intent | REPORT §7.0 + A1 | @! + run_batch | 首项 UNKNOWN 次项正常 | BOUNDARY | P3 | logs/D3-40.log | BOUNDARY-004 |
| D3-50/51/51b-ai-api | 11 §11.3 | ai API 可达性 | get_retry/is_auto 不可调用 | KERNEL_ISSUE | P1 | logs/D3-50*.log | KERNEL-ISSUE-004 |
| D3-50c-ai-probe | 11 §11.3 | probe_model | 误判强制推理模型 | BOUNDARY | P3 | logs/D3-50c.log | BOUNDARY-005 |
| D3-60-intent-static | KNOWN_LIMITS 12 | 静态 push 静默无效 | 行为符合；警告未出现 | DOC_ISSUE | P3 | logs/D3-60.log | DOC-ISSUE-006 |
| D3-61-idbg | 11 §11.5 | fields/env/show_all | 正常 | PASS | - | logs/D3-61.log | |
| D3-70-fromprompt | 06 §6.6 | 用户类 __from_prompt__ | mood=开心（需 (bool,实例)） | PASS | P3注 | logs/D3-70.log | DOC-ISSUE-007 |
| D3-80/81-mask | 11 §11.3 | mask/ret_type_prompt | void API 正常；get 正常 | PASS | - | logs/D3-80*.log | |
| D1-15-001-diagnostics | 15_diagnostics | 诊断码说明/修复 | SEM_MISSING_RETURN_ANNOTATION + 说明/修复段 | PASS | - | logs/D1-15-001.log | catalog 集成生效 |

## 缺陷记录

### DOC-ISSUE-001 — `02_variables.md §2.6` 示例缺返回标注
- **复现**：`func increment():` 无 `-> TYPE` → `SEM_MISSING_RETURN_ANNOTATION` 编译错误。
- **文档**：docs/syntax/02_variables.md §2.6 示例（与 05_functions.md §5.1 强制标注矛盾）。
- **实际**：示例直接照抄会编译失败。
- **级别**：P3（文档）。
- **处置**：本 trial 用例按 05_functions 正确用法补 `-> void` 后继续。

### DOC-ISSUE-002 — 4 个文档文件 9 处 `func __init__(...)` 缺返回标注
- **复现**：按文档示例直接书写 `func __init__(self, ...):` → `SEM_MISSING_RETURN_ANNOTATION`
  编译错误（编译器对 `__init__` 同样要求 `-> TYPE`；tests 用 `-> auto`/`-> void`）。
- **文档**：docs/syntax/06_oop.md（§6.1/§6.3/§6.4 共 4 处）、docs/syntax/04_control_flow.md
  （§4.7.2 自定义异常 2 处）、docs/KNOWN_LIMITS.md（§六 2 处）、docs/subsystems/03_callable_fn.md
  （1 处）——**共 9 处**无返回标注。
- **实际**：文档示例与编译器要求（05_functions §5.1 强制标注）系统性不一致。
- **级别**：P3（文档）。
- **处置**：本 trial 用例按正确用法补 `-> auto`；文档待治理窗口批量修正。
- **证据**：grep `func __init__\(self[^)]*\):$\s*$`（docs 9 处）+ cases/D1-04-002-switch-exc.ibci。

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

### BOUNDARY-001 — 生成器 `for` 消费是 to_list 物化，break 后生成器仍已跑完
- **复现**：D2-31 `for x in gen(10)` 中 `count==3` 时 break，但生成器体的 `print("GEN_FINISHED")`
  仍执行（生成器已被完全驱动）。
- **文档**：05_functions §5.8 "消费者 break 提前终止（生成器不再推进）" vs §5.9
  "`for` 消费经 `to_list` 一次性物化（与 yield 生成器一致）"——两者张力。
- **实际**：`for` 消费 = `to_list` 物化（生成器在进入循环前已跑完），break 只终止对物化列表的迭代。
  "惰性"在 `next()`/`to_list` 层成立，在 `for` 层不成立。
- **级别**：P3（文档张力/行为边界，非明确缺陷）。
- **证据**：cases/D2-31-ref-generator-break.ibci + logs/D2-31-ref-generator-break.log。

### BOUNDARY-002 — 生成器体内 `await chan.recv()` 未触发 KNOWN_LIMITS §二十四 所述错误
- **复现**：D2-32/32b 生成器 `take()` 内 `int v = await c.recv()`（数据未就绪 + 生产者线程）
  → 正常输出 x=42，未报 "generator driver yielded unexpected event"。
- **文档**：KNOWN_LIMITS §二十四 声称生成器消费路径不承载显式 await 真异步 Waitable。
- **实际**：两种形状（数据已就绪/未就绪含生产者线程）均正常完成，未复现文档描述的 RuntimeError。
- **级别**：P3（文档可能过时，或该测试形状未触达缺陷路径——须内核层复核，不在本任务）。
- **证据**：cases/D2-32/b-gen-await*.ibci + logs/D2-32/b-gen-await*.log。

### DOC-ISSUE-004 — `11_modules.md §11.3` stream_call/stream_channel 仅列名未列签名
- **复现**：文档只写 "`stream_call()`、`stream_channel()` 等"，无签名/用法示例；
  初试按 fn 传入报 `SEM_TYPE_MISMATCH: Argument 'sys_prompt' type mismatch: expected 'str'`。
- **实际**：正确用法 `ai.stream_call(sys_prompt:str, user_prompt:str) -> Waitable`（tests/runtime/
  test_streaming.py 佐证）；`str full = await ai.stream_call("sys","user")` 正常。
- **级别**：P3（文档签名缺失）。
- **证据**：cases/D2-35-stream.ibci + logs/D2-35-stream.log。

### DOC-ISSUE-005 — `howto/write_concurrent_tasks.md` thread_result `.value` 属性形态错误
- **复现**：howto 多处写 `cons.join().value`（期望取到 int 值），且 `print((str)r.value)` 示例；
  实测 `r.value`（属性）返回 **bound method 对象**（`<Instance of bound_method>`），
  正确写法是方法 `r.value()`（返回 42）。
- **文档**：docs/howto/write_concurrent_tasks.md（`r.value` / `join().value` 2 处）vs
  docs/syntax/14_concurrency.md §14.7（`r.value()` 方法形态，正确）。
- **实际**：`.value` 属性 = 绑定方法对象；`.value()` 方法 = 值。
- **级别**：P3（文档错误）。
- **证据**：cases/D2-42b/42c-threadresult*.ibci + logs/D2-42b/42c.log。

### BOUNDARY-003 — 隔离子环境不继承父 LLM 配置，子项目须自带 api_config.json
- **复现**：D2-50 parent 内 `@+ 极简意图` + 真实 LLM 正常；`ihost.run_isolated("../multifile/
  child_llm.ibci", policy)` 的 child 内真实 LLM 调用报
  `RuntimeError: LLM 运行配置缺失`；在 child 所在目录（multifile/）放置 api_config.json 后正常。
- **文档**：11_modules §11.6 "子环境完全独立（独立 Engine 实例、独立插件发现、默认不继承父环境变量）"；
  未明确说明"LLM provider 配置也不继承"。
- **实际**：child 引擎按自身 project_root 加载 api_config.json，不继承 parent 的 ai 配置。
- **级别**：P3（文档边界未明示；行为与"完全独立"一致，非缺陷）。
- **证据**：cases/D2-50-isolation-llm.ibci + multifile/child_llm.ibci + logs/D2-50-isolation-llm.log。

### BOUNDARY-004 — `@!` 排他意图在 run_batch 单条语句多 LLM 调用时仅首个调用生效
  `batch_item=UNKNOWN`，第 2 项 `batch_item=香甜`（正常输出）。
- **文档**：09_intent_system §9.1 "`@!` 仅作用于紧随其后的**一条**含 LLM 调用的语句"；
  §9.2 "意图注入覆盖赋值与表达式路径（dispatch-before-use 一并注入）"。
- **实际**：run_batch 是单条语句但含多个 LLM 调用——`@!` 被第一个调用消费后失效，
  后续调用不受排他约束。文档的"一条语句"粒度 vs 实际"一次 LLM 调用"粒度存在张力。
- **级别**：P3（语义边界，文档粒度未明示）。
- **证据**：cases/D3-40-batch-intent.ibci + logs/D3-40-batch-intent.log。

### KERNEL-ISSUE-003 — 真实 LLM provider 层失败（超时）的 LLMCallError 逃逸 try/except
  在 `try: ... except LLMCallError/LLMError/Exception` 内——异常**未被捕获**，
  以 `ThrownException: <LLMCallError object>` 传播，程序崩溃。
- **文档**：04_control_flow §4.7（LLMCallError 是 LLMError/Exception 子树，except 按继承链匹配；
  表"没有 llmexcept 保护时的 LLM 失败兜底"）；10_robustness §10.3（"LLM provider 层失败
  （网络/鉴权）时立即抛出 LLMCallError"）。
- **对照**：① 手动 `raise LLMCallError("manual fail")` 被正常捕获（D3-C3f PASS）；
  ② MOCK `LLMParseError` 被正常捕获（D3-C3c PASS）——**缺陷限定在 provider 层失败经
  worker/Future 投递的路径**。
- **实际**：provider 失败经 `_call_llm` 抛 `ThrownException(error_obj)`（worker 线程内），
  经 Future/`try_result` 回传，VM 未按 IBCI 异常匹配 try/except，直接冒泡为 Runtime Error。
- **级别**：P1（文档承诺的异常捕获契约在真实 provider 失败路径失效；llmexcept 收敛场景 C3 相关）。
- **证据**：cases/D3-C3/d/e-timeout-try*.ibci + logs/D3-C3/d/e.log；对照 D3-C3c/f。
- **备注**：KNOWN_LIMITS §十六.6（set_timeout 超时行为需真实 LLM 验证）已被此测试触发。

### KERNEL-ISSUE-004 — 文档化 ai 模块 API `get_retry()` / `is_auto_intent_injection_enabled()` 不可调用
- **复现**：`ai.get_retry()` → `RuntimeError: VM: Call failed: Object of type 'None' has no method '__call__'`；
  `ai.is_auto_intent_injection_enabled()` 同样失败。对照 `ai.get_retry_count` 返回 None
  （`RUN_TYPE_MISMATCH: Cannot assign 'None' to 'int'`）。
- **文档**：docs/syntax/11_modules.md §11.3 明确列出 `get_retry()`、`is_auto_intent_injection_enabled()` 为可用函数。
- **对照**：`ai.has_api_key()` ✅、`ai.probe_model()` ✅、`ai.get_current_intent_stack()` ✅、
  `ai.get_global_intents()` ✅、`ai.get_return_type_prompt()` ✅、`ai.mask()`（void）✅ 均正常——
  仅这两个文档化 API 失效。
- **根因定位（内核阅读，仅此一次）**：Python 实现存在（`ibci_modules/ibci_ai/core.py:380/383`），
  但 **`ibci_modules/ibci_ai/_spec.py` vtable 未注册**这两个函数（仅注册 has_api_key/
  get_current_call_info 等）→ IBCI 侧取到模块命名空间的 None，不可调用。
- **级别**：P1（文档化 API 契约失效；vtable 与文档/实现三方漂移）。
- **证据**：cases/D3-50/51/51b-ai-*.ibci + logs/D3-50/51/51b.log + `_spec.py` vtable 清单。
- **备注**：与 PT-DEBT-24（call_intent 死机制）同类"注册表/契约漂移"模式。

### BOUNDARY-005 — `ai.probe_model()` 将 reasoning:false 的非推理模型误判为"强制推理模型"
- **复现**：D3-50c 配置 `reasoning:false`（qwen3.6-35b-a3b 非思考模型），`ai.probe_model()`
  输出 "[AI Probe] ... 探测到专用 reasoning 字段，判定为 [强制推理模型]"。
- **文档**：11_modules §11.3 `probe_model()`（探测模型响应特征）。
- **实际**：本地端点返回流未含 reasoning 字段，但探测判定为强制推理模型——判据或为
  响应中出现了模型自述/字段猜测，需内核层复核（不在本任务）。
- **级别**：P3（工具误判，不影响主路径；但可能误导 reasoning:true 自动注入决策）。
- **证据**：cases/D3-50c-ai-probe.ibci + logs/D3-50c-ai-probe.log。

### DOC-ISSUE-006 — KNOWN_LIMITS §十二 声称的 `SEM_INTENT_STATIC_CALL` 警告未观察到
- **复现**：`intent_context.push("这条不会生效")` 类静态调用 + 后续 `@~...~`——行为符合文档
  （push 静默无效，回复不受影响），但**未见任何 SEM_INTENT_STATIC_CALL 警告输出**
  （stdout+stderr 均无）。
- **文档**：KNOWN_LIMITS §十二 声称 TypeCheckingPass 对此发出 SEM_INTENT_STATIC_CALL warning。
- **实际**：警告未出现（或需特定启用条件/展示通道）。
- **级别**：P3（文档行为未复现）。
- **证据**：cases/D3-60-intent-static.ibci + logs/D3-60-intent-static.log。

### DOC-ISSUE-007 — `06_oop.md §6.6` `__from_prompt__` 契约未注明返回 `(bool, instance)` 元组
- **复现**：按文档"从文本解析为当前类型实例"实现 `func __from_prompt__(self, str raw) -> auto:
  return Mood(t)` → 运行时报 `LLMParseError: type_name="unknown"`（解析结果被当不确定）。
  按 tests/e2e/test_prompt_protocol_e2e.py 改为 `return (True, Mood(t))` → 正常解析
  （mood=开心）。
- **文档**：06_oop §6.6 协议表仅一句"从文本解析为当前类型实例"，未注明必须返回
  `(bool, 实例)` 元组（成功标志 + 值）。
- **实际**：契约 = `(bool, instance)`；返回裸实例被当作不确定失败。
- **级别**：P3（文档契约缺失）。
- **证据**：cases/D3-70-fromprompt.ibci + logs/D3-70-fromprompt.log。
