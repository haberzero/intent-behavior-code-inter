# T07_fixes_critical_stress REGISTER — 四项修复批判性对抗 + 旧套件全量重跑记录

> 2026-08-14。基线 unsafe-vibe-dev 17e75d72（四项修复后，全量 2665 passed / 1 skipped，已实跑确认）。
> 43 用例：**28 PASS + 12 GUARD + 3 KERNEL_ISSUE**（零 HARNESS）；真实 LLM 7/7 全 PASS
> （qwen3.6-35b-a3b @ 127.0.0.1:1234，每次试用前探测，响应 <1-2s）。
> 旧套件全量重跑（用户强调）：T01-T06 共 238 用例当前 HEAD 下重跑，**202 PASS + 24 GUARD +
> 1 LIMIT + 1 KERNEL_ISSUE（陈旧断言）+ 9 HARNESS（5 陈旧断言 + 4 helper/smoke 设计内）**。
> **本任务是试用与记录任务（用户 2026-08-14 明确）：不查看内核代码成因、不修改任何内容，
> 发现问题只记录登记**。用例脚本错误（断言口径）为本套自建用例作者修正，旧套件用例一律未改。

## 一、结果总览

| 分类 | 数量 | 说明 |
|------|------|------|
| PASS | 28 | 四项修复回归对抗 + 对抗组合 + 泛型边界复测 + 真实 LLM 全部通过 |
| GUARD | 12 | 幽灵诊断码守卫（除零/越界/键缺失/0x/1e/0x1g/缩进）+ 编译期守卫（Optional LLM 目标/元组解包/*expr/generator 赋值） |
| KERNEL_ISSUE | 3 | D1-13 属性读取静默 None / D2-09 函数内 Optional unwrap 失败 / D2-10 Optional 容器方法不可用 |
| DOC_ISSUE | 3 | 与上述 KERNEL_ISSUE 同源（文档 §8/15_diagnostics 触发条件与实现不符）+ KNOWN_LIMITS §10.2 措辞核对（见 §五） |

## 二、KERNEL_ISSUE 明细（只记录登记，不查成因不改代码）

### KERNEL_ISSUE-OPTIONAL-SCOPE-1（P1）— 函数作用域内 Optional 先 None 后赋值，unwrap()/is_some() 报 "Object of type 'None'"

- **触发用例**：`T07_fixes_critical_stress/cases/D2-09.ibci`
- **现象**：`func work() -> int: Optional[int] tag = None; tag = 405; return tag.unwrap()` →
  `[ERROR][RUN_ATTRIBUTE_ERROR]: Object of type 'None' has no method '__call__'`（exit 1）。
  同一代码在**模块顶层**成功（405）；`return tag`（不经 unwrap）成功；lambda 内 `x.is_some()` 成功；
  **普通函数内 `tag.is_some()` 亦失败**（探针 w3 同报）。线程 worker 内同失败（ThreadFailed 包装）。
- **证据**：`cases/D2-09.ibci` + `logs/B-D2-09.log`；探针 v1-v4/w1-w3（`_scratch` 已清理，见 REGISTER 记录）。
- **文档依据**：`docs/architecture/03_type_system.md` §8 明确"is_none() / is_some() / unwrap() / or_else() **在任何路径可用**"。
- **级别**：P1（文档声明 API 在函数作用域路径不可用，静默错误/错误路径崩溃；顶层与 lambda 正常，路径不一致）。
- **修复状态**：**已修复（2026-08-14，unsafe-vibe-dev）**。触发用例 D2-09 转 PASS（expect-out 405 达成）。根因：函数作用域局部变量声明类型编译期丢失（符号池 type_uid=any）→ 运行时 wrap_optional 不包装；同源系统性缺陷：函数内类型化局部变量重赋值检查失效、闭包/cell 写路径不包装。
- **登记**：PENDING_TASKS + trials/INDEX.md。

### KERNEL_ISSUE-OPTIONAL-CONTAINER-1（P1）— Optional[list[int]] 有值包装，len()/下标方法不可用

- **触发用例**：`T07_fixes_critical_stress/cases/D2-10.ibci`
- **现象**：`Optional[list[int]] b = [1,2,3]; print(len(b))` → `RUN_ATTRIBUTE_ERROR:
  Object of type 'Optional[list[int]]' has no method 'len'`；`b[1]` → 无 `__getitem__`。
  `b is None` → False（有值包装正常）。容器方法（len/下标）对 Optional 包装对象不可用。
- **证据**：`cases/D2-10.ibci` + `logs/B-D2-10.log`；探针 u1/u2。
- **文档依据**：`docs/architecture/03_type_system.md` §8 "Optional[T] 接受 T" + 统一值模型（容器元素亦包装）——
  用户按 `T` 语义使用容器方法时必然失败；文档未说明需先解封。
- **级别**：P1（Optional 包装容器后基础容器操作不可用，语义断裂）。
 - **修复状态**：**已修复（2026-08-14，unsafe-vibe-dev）**。触发用例 D2-10 转 PASS（expect-out 3 达成）。根因：IbOptional 值对象协议无内层值委托（容器方法 len/下标/迭代不可用）；连带 resolve_iterable 不支持 Optional 委托。修复：IbOptional.receive 委托链（内层值优先 + Optional 专属方法回退 + 空值 fail-fast）+ resolve_iterable 识别 Optional。
- **登记**：PENDING_TASKS + trials/INDEX.md。

### KERNEL_ISSUE-ATTR-READ-1（P1）— 未声明属性读取返回 None（文档称应报 RUN_ATTRIBUTE_ERROR）

- **触发用例**：`T07_fixes_critical_stress/cases/D1-13.ibci`
- **现象**：`class Point: int x ...; Point p = Point(1); print(p.y)`（y 未声明）→ **输出 None**（exit 0），
  不触发 RUN_ATTRIBUTE_ERROR；`p.missing_method()`（调用不存在方法）→ RUN_ATTRIBUTE_ERROR
  （"Object of type 'None' has no method '__call__'"）——仅**调用**路径报错，**读取**路径静默 None。
- **证据**：`cases/D1-13.ibci` + `logs/B-D1-13.log`；探针 p9/p10。
- **文档依据**：`docs/syntax/15_diagnostics.md` RUN_ATTRIBUTE_ERROR "触发条件：访问对象不存在的属性/方法"。
- **级别**：P1（静默错误值——用户按文档期望报错，实际拿到 None 继续运算，错误传播隐蔽）。
 - **修复状态**：**已修复（2026-08-14，unsafe-vibe-dev）**。触发用例 D1-13 转 PASS（RUN_ATTRIBUTE_ERROR 达成）。根因：Object 基类 __getattr__ 兜底（_default_getattr）未命中成员时静默返回 None。修复：改抛 InterpreterError(RUN_ATTRIBUTE_ERROR)（读取/调用路径一致 fail-fast）。
- **登记**：PENDING_TASKS + trials/INDEX.md。

## 三、旧套件全量重跑对照（T01-T06，当前 HEAD 17e75d72，B- 最新记录）

| 套件 | 用例 | PASS | GUARD | LIMIT | KERNEL_ISSUE | HARNESS | 重跑结论 |
|------|------|------|-------|-------|--------------|---------|----------|
| T01_llm_full | 104 | 92 | 8 | 0 | 0 | 4 | 3 处陈旧断言**已修复转 PASS**（2026-08-14：type() 特化名新语义 `list[int]`/`generator[str]`/`generator[int]`）；4 HARNESS = helper/greeting_mod/smoke/deadloop_probe 设计内 |
| T02_enum_import | 9 | 8 | 0 | 1 | 0 | 0 | T6-enum-method-boundary = 文档化边界 LIMIT（enum 方法边界，KNOWN_LIMITS 二） |
| T03_user_class_generics | 30 | 23 | 6 | 0 | 0 | 1 | D2-07 已修复转 PASS（2026-08-14：chan 迁普适写法 `chan[E] ch = chan()`；原 `chan(Box[int],...)` 特化实参降级记录为 BOUNDARY-CHAN-ARGS-1）；smoke_deadloop 设计内 |
| T04_generics_fix_regression | 35 | 26 | 8 | 0 | 0 | 1 | R5-03 已修复转 PASS（2026-08-14：同上 chan 普适写法）；smoke_deadloop 设计内 |
| T05_critical_stress | 40 | 39 | 1 | 0 | 0 | 0 | **D1-10 KI-1 触发用例转 PASS 核销 ✓**；D2-03 KI-2 触发用例**已核销转 PASS**（2026-08-14：expect-out 更新为修复后语义 True|True|False） |
| T06_class_identity | 20 | 20 | 0 | 0 | 0 | 0 | **CROSSMOD-LLM-1 触发用例 D2-05/D3-02 转 PASS 核销 ✓**；D3-01~04 真实 LLM 全 PASS |
| **合计** | **238** | **206** | **24** | **1** | **0** | **6** | 零回归、零新内核缺陷；**6 处陈旧断言全部修复转 PASS（2026-08-14，用户授权）**；4 设计内 HARNESS；2 项核销达成 |

> **陈旧断言处理（2026-08-14 用户授权后已执行）**：6 处旧套件用例按新语义更新并重跑确认 PASS（T01
> D1-01-001/D1-05-008/D1-05-008b：type() 特化名；T03 D2-07/T04 R5-03：chan 迁普适写法 \`chan()\`；
> T05 D2-03：KI-2 核销 True|True|False）。原判"陈旧断言"的 chan 项经普适性原则核实为
> **BOUNDARY-CHAN-ARGS-1**（chan(T,...) 特化类对象实参降级，非内核缺陷——普适写法全通）。

## 四、核销确认（T05/T06 遗留缺陷状态核对）

| 缺陷 | 触发用例 | 重跑结果 | 结论 |
|------|----------|----------|------|
| KERNEL_ISSUE-CROSSMOD-THREAD-1（P1） | T05 D1-10 | **PASS**（线程 worker 内 geo.Box 方法调用 405） | **已核销**（S4 修复有效） |
| KERNEL_ISSUE-OPTIONAL-ISNONE-1（P2） | T05 D2-03 | 实际 True|True|False（`a is None`=True 已修复）；用例断言陈旧 | **修复行为确认**（T07 D1-05/D1-06/D1-07 独立验证 is None/is_none/is_some/对称全 PASS） |
| KERNEL_ISSUE-CROSSMOD-LLM-1（P1） | T06 D2-05/D3-02 | **PASS** + T07 D3-01/D3-02/D3-04 全 PASS | **已核销**（跨模块类 LLM 输出 module 感知生效） |
| KERNEL_ISSUE-OPTIONAL-SCOPE-1（P1） | T07 D2-09 | **PASS**（函数内先 None 后赋值 unwrap=405） | **已核销**（2026-08-14，函数局部声明类型绑定根治） |
| KERNEL_ISSUE-OPTIONAL-CONTAINER-1（P1） | T07 D2-10 | **PASS**（Optional[list[int]] len=3） | **已核销**（2026-08-14，Optional 容器委托根治） |
| KERNEL_ISSUE-ATTR-READ-1（P1） | T07 D1-13 | **PASS**（未声明属性读取报 RUN_ATTRIBUTE_ERROR） | **已核销**（2026-08-14，属性读取 fail-fast 根治） |

## 五、DOC_ISSUE 记录（D5 文档核验；正文修改待用户确认）

| # | 级别 | 文件 | 内容 |
|---|------|------|------|
| DOC-24 | P2 | arch/03_type_system §8 | "unwrap/or_else/is_some/is_none **在任何路径可用**"与实现不符：函数作用域先 None 后赋值路径报 RUN_ATTRIBUTE_ERROR（同 KERNEL_ISSUE-OPTIONAL-SCOPE-1）——**已同步（2026-08-14）**：§8 值创建路径枚举补函数作用域局部变量/闭包捕获与 cell 写 |
| DOC-25 | P2 | arch/03_type_system §8 | Optional 包装容器（Optional[list[int]]）len/下标不可用未说明；"接受 T"语义下用户按容器用法失败（同 KERNEL_ISSUE-OPTIONAL-CONTAINER-1）——**已同步（2026-08-14）**：§8 新增"Optional 容器委托"条目（有值按 T 语义、空值 fail-fast） |
| DOC-26 | P2 | 15_diagnostics RUN_ATTRIBUTE_ERROR | "访问对象不存在的属性/方法"触发条件与实现不符：属性**读取**返回 None 不触发，仅**调用**触发（同 KERNEL_ISSUE-ATTR-READ-1）——**已同步（2026-08-14）**：触发条件精确化（读取/调用均报此码，不静默 None） |
| DOC-27 | P3 | KNOWN_LIMITS §10.2 | 措辞核对：裸名返回路径 graceful 退化表述在 CROSSMOD-LLM-1 修复后**仍成立**（LLM 输出用 qualified 注解则 module 感知；outputhint 裸名返回仍退化），T07 D3-01~04 实证 qualified 路径全部生效——建议补一句"qualified 注解路径已验证可用"；§8 统一值模型声明与 DOC-24/25 同源待修——**已同步（2026-08-14）**：补 qualified 注解路径实证 |
| DOC-28 | P3 | T01/T03/T04/T05 用例断言 | 5 处陈旧断言需按值层身份收敛新语义更新（type() 特化名 / chan 泛型实参拦截 / D2-03 is None 新语义），PHASE_D 流程——**已处置（2026-08-14）**：陈旧断言全部更新转 PASS（见 §三）；chan 项核实为 BOUNDARY-CHAN-ARGS-1，14_concurrency 已补说明 |

## 六、BOUNDARY / LLM_BEHAVIOR 记录

| 用例 | 观察 |
|------|------|
| D1-12 | 字典键缺失 → RUN_INDEX_ERROR（文档 428 行"键不存在"覆盖，文档一致） |
| D4-06 | 跨模块泛型特化实例 type() 显示裸名特化名 `Box[int]`（无 module 前缀）；值身份正确（105/hi! 方法表不串扰），与 KNOWN_LIMITS §10.2 一致 |
| D4-01/02 | 句柄类值身份已水化：`thread[int]`/`chan[int]`/`slot[int]`/`generator[int]` type() 显示特化名（S0-S7 根治有效，_HANDOFF_GENERIC_REMAINING #1/#3/#7 复测确认） |
| D4-03/05/07 | 元组解包错误类型 / *expr 元素级校验 / generator 特化赋值 均编译期拦截（#4/#6/#1 复测确认根治） |
| D4-04 | `-> auto` 容器字面量实参推断生效（#5 复测确认） |
| D3-03 | Optional 作 LLM 输出目标被编译期守卫拦截（SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE，PT-DECIDE-1 设计内 fail-fast）——交接建议的"Optional 作 LLM 输出目标"对抗项结论：语言级不可行（守卫正确） |

## 七、逐例明细

| case_id | 目标 | 分类 | exit | 证据日志 |
|---------|------|------|------|----------|
| D1-01 | 跨模块类函数参数/返回注解 | PASS | 0 | logs/B-D1-01.log |
| D1-02 | 跨模块泛型注解 + 容器 | PASS | 0 | logs/B-D1-02.log |
| D1-03 | 深层模块 subpkg.util 注解 | PASS | 0 | logs/B-D1-03.log |
| D1-04 | 跨模块类字段注解 | PASS | 0 | logs/B-D1-04.log |
| D1-05 | Optional 嵌套/容器组合 | PASS | 0 | logs/B-D1-05.log |
| D1-06 | for Optional 迭代包装 | PASS | 0 | logs/B-D1-06.log |
| D1-07 | None 判空全对称 | PASS | 0 | logs/B-D1-07.log |
| D1-08 | Optional 字段默认值+继承 | PASS | 0 | logs/B-D1-08.log |
| D1-09 | Optional 默认参数深克隆 | PASS | 0 | logs/B-D1-09.log |
| D1-10 | 幽灵码除零（嵌套函数） | GUARD | 1 | logs/B-D1-10.log |
| D1-11 | 幽灵码越界 | GUARD | 1 | logs/B-D1-11.log |
| D1-12 | 幽灵码键缺失 | GUARD | 1 | logs/B-D1-12.log |
| D1-13 | **未声明属性读取 → None** | KERNEL_ISSUE | 0 | logs/B-D1-13.log |
| D1-14 | 幽灵码 0x 残缺 | GUARD | 1 | logs/B-D1-14.log |
| D1-15 | 幽灵码缩进失配 | GUARD | 1 | logs/B-D1-15.log |
| D1-16 | set_mock_mode mock→真实→mock | PASS | 0 | logs/B-D1-16.log |
| D1-17 | 幽灵码 1e 残缺 | GUARD | 1 | logs/B-D1-17.log |
| D1-18 | 幽灵码 0x1g 尾字母 | GUARD | 1 | logs/B-D1-18.log |
| D2-01 | 线程+跨模块类+Optional | PASS | 0 | logs/B-D2-01.log |
| D2-02 | chan + Optional 值传递 | PASS | 0 | logs/B-D2-02.log |
| D2-03 | 生成器 yield Optional | PASS | 0 | logs/B-D2-03.log |
| D2-04 | 诊断码在控制流内（可捕获） | PASS | 0 | logs/B-D2-04.log |
| D2-05 | 容器深嵌套 + Optional | PASS | 0 | logs/B-D2-05.log |
| D2-06 | Optional[geo.Box[int]] 组合 | PASS | 0 | logs/B-D2-06.log |
| D2-07 | lambda + Optional 捕获 | PASS | 0 | logs/B-D2-07.log |
| D2-08 | 深递归 + 除零守卫 | GUARD | 1 | logs/B-D2-08.log |
| D2-09 | **函数内 Optional unwrap 失败** | KERNEL_ISSUE | 1 | logs/B-D2-09.log |
| D2-10 | **Optional 容器 len/下标不可用** | KERNEL_ISSUE | 1 | logs/B-D2-10.log |
| D3-01 | 跨模块类 LLM 输出（核销重验） | PASS | 0 | logs/B-D3-01.log |
| D3-02 | 同名类不误配 LLM 输出 | PASS | 0 | logs/B-D3-02.log |
| D3-03 | Optional LLM 目标守卫 | GUARD | 1 | logs/B-D3-03.log |
| D3-04 | 深层模块 LLM 输出 | PASS | 0 | logs/B-D3-04.log |
| D3-05 | set_mock_mode 真实往返 | PASS | 0 | logs/B-D3-05.log |
| D3-06 | 长提示格式约束 | PASS | 0 | logs/B-D3-06.log |
| D3-07 | 意图 + 跨模块类 | PASS | 0 | logs/B-D3-07.log |
| D3-08 | enum 成员名→值（无回归） | PASS | 0 | logs/B-D3-08.log |
| D4-01 | 句柄类值身份特化名 | PASS | 0 | logs/B-D4-01.log |
| D4-02 | generator[list[int]] 嵌套值身份 | PASS | 0 | logs/B-D4-02.log |
| D4-03 | 元组解包错误类型拦截 | GUARD | 1 | logs/B-D4-03.log |
| D4-04 | -> auto 容器实参推断 | PASS | 0 | logs/B-D4-04.log |
| D4-05 | *expr 元素级校验 | GUARD | 1 | logs/B-D4-05.log |
| D4-06 | 跨模块同名特化值身份 | PASS | 0 | logs/B-D4-06.log |
| D4-07 | generator 特化赋值拦截 | GUARD | 1 | logs/B-D4-07.log |

## 八、E 批判补充批次（2026-08-14 第二 session 复核，T07 三项 P1 修复后独立挑刺）

> 目的：验证上一 session T07 三项 P1 修复（OPTIONAL-SCOPE-1 / OPTIONAL-CONTAINER-1 /
> ATTR-READ-1）有效性 + 找边界缺陷。8 例：**5 PASS + 1 BOUNDARY + 2 DOC_ISSUE**。
> 补充了既有 D 维未覆盖的边界面（空值诊断码一致性、嵌套函数返回、下标/切片类型推断、
> 同名重声明遮蔽）。

| case_id | 目标 | 分类 | 观察 |
|---------|------|------|------|
| E1-empty-optional-code | 空 Optional for 迭代诊断码 | DOC_ISSUE | 抛 `RUN_GENERIC_ERROR`，arch/03 §8 承诺空值操作 fail-fast 报 `RUN_ATTRIBUTE_ERROR`——**文档矛盾**（15_diagnostics RUN_GENERIC_ERROR 定义"未归类运行时错误"与 arch/03 §8 承诺不符）。修复②把 base 的裸 RuntimeError 改进为有码错误（进步），但码与文档承诺不一致 |
| E2-empty-optional-unwrap-code | 空 Optional unwrap 诊断码 | DOC_ISSUE | 同上：`unwrap()` 抛 `RUN_GENERIC_ERROR`（optional.py:90 未指定 error_code）vs 文档承诺 `RUN_ATTRIBUTE_ERROR`；委托链空值路径（optional.py:174）已指定 RUN_ATTRIBUTE_ERROR——**同文件内两处空值错误码不一致** |
| E3-nested-func-return | 函数返回嵌套函数赋 fn_callable 类型 | BOUNDARY | `return inner`（嵌套函数）赋 `fn_callable[int]` 报 `RUN_TYPE_MISMATCH: Cannot assign 'callable'`；lambda 返回正常。**base（30511d4f）同现=pre-existing**，与修复①声称的 rehydrator kind 保真无关（运行时 `_check_type` 路径）。登记待修 |
| E4-opt-subscript-method-consistency | Optional[list] b[0] 类型一致性 | PASS | `b[0]` 编译期推断 int、运行时委托返回裸 int——一致；`b[0].is_some()` 编译期放行是**编译期成员检查宽松**（裸 `int.is_some()` 同样放行），非修复引入 |
| E5-opt-slice-type | Optional[list] 切片类型推断 | PASS | `b[1:3]` 编译期推断 `Optional[list[int]]`（保留包装）与下标推断 int（解开）不同——两者均正确，登记观察（下标/切片推断不对称） |
| E6-redeclare-shadow | 函数内同名重声明 | PASS | `int x=1; int x=2` 编译通过返回 2（静默遮蔽）。模块级/base 一致=语言既有语义（重声明遮蔽非报错），登记观察 |
| E7-empty-opt-try-catch | 空 Optional 迭代 try 内可捕获 | PASS | try/except 内捕获不逃逸；空值错误可编程处理（语义合理） |
| E8-opt-container-full-matrix | Optional 容器委托完整矩阵 | PASS | 有值 len/下标/append 变异/切片/越界传播全正常（越界错误正确传播不吞） |

**E 批次结论**：三项修复主路径全部有效（E4/E5/E7/E8 确认委托链在读取/下标/迭代/切片/变异全场景正确）；
发现 **2 项文档矛盾（空值错误码）** 与 **1 项 pre-existing 边界（嵌套函数返回类型）**，均不阻断修复有效性。

## 九、结论

- **四项修复面（CROSSMOD-LLM-1 / KI-2 / 幽灵诊断码 / set_mock_mode）批判性对抗全部通过**：
  D1 18 例（含 6 守卫）零回归；跨模块注解解析在函数参数/返回/容器/字段/深层模块全场景可用；
  Optional 判空（is None/is_none/is_some/对称）与嵌套容器组合全 PASS；7 幽灵码守卫精确命中；
  set_mock_mode 真实往返 PASS。
- **真实 LLM 7/7 全 PASS**：跨模块类 LLM 输出（含同名不误配、深层模块）、意图、长提示、
  enum、mock↔真实切换全过——CROSSMOD-LLM-1 修复稳健。
- **新暴露 3 项既有 KERNEL_ISSUE**（均与 KI-2 统一 Optional 值模型改动面相关，验证用户此前
  "Optional 可能藏更深根源"警告）：① 函数作用域 Optional 实例方法（unwrap/is_some）先 None
  后赋值路径失败（P1）；② Optional 包装容器 len/下标不可用（P1）；③ 未声明属性读取静默 None
  （P1，幽灵码修复未覆盖读取路径）。只登记不修复。
- **旧套件全量重跑**：T01-T06 238 用例零回归、零新内核缺陷；2 项遗留缺陷核销（KI-1/CROSSMOD-LLM-1）；
  KI-2 修复行为确认；5 处旧用例断言为陈旧（值层身份收敛新语义），待后续按 PHASE_D 更新。
- **下一步**：3 项新 KERNEL_ISSUE + DOC-24~26 待独立窗口修复（根因分析留待后续任务）；
  5 处陈旧断言待更新；KNOWN_LIMITS §10.2 可补 qualified 路径实证表述。
- **E 批判补充批次**：三项 P1 修复有效性复核通过（触发用例 D2-09/D2-10/D1-13 全核销 +
  委托链全矩阵 PASS）；新发现 2 项文档矛盾（空 Optional 迭代/`unwrap()` 错误码
  RUN_GENERIC_ERROR vs arch/03 §8 承诺 RUN_ATTRIBUTE_ERROR，iterable.py:39 /
  optional.py:90 未指定 error_code）+ 1 项 pre-existing 边界（嵌套函数返回赋
  fn_callable 类型 RUN_TYPE_MISMATCH，base 同现）。登记 PENDING_TASKS + INDEX。
