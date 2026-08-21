# 阶段 C 恶意试用起点：已知边界与推测风险面清单（临时）

> **性质**：临时任务控制文档（`.dsh` 治理惯例 `_` 前缀）。本清单是**恶意试用的起点参考**，
> **不是全部**——恶意试用必须以本清单为底，自行扩展边界，穷尽我未列出的场景。
>
> **用户指令（2026-08-20）**：试用不仅测试文档宣称/我们认为可用的功能，还要**带着恶意测试
> IBCI 的边界**：可能存在缺陷的逻辑、可能存在问题的逻辑、开发者没有考虑到的场景。本清单记录
> 我（接手者，已完成阶段 A/B 深度代码工作）已知的 / 推测中可能存在的问题，供下一 session
> 恶意试用参考。
>
> **免责声明**：本清单条目多数为**推测**（基于代码阅读与工作观察，未经逐个实证）；标记
> `[已知]` 的为已记录于 KNOWN_LIMITS 或已实证确认，其余为 `[推测]` 待恶意试用验证。
> 每条给"怎么测"——恶意试用按此设计对抗性用例，发现即按 INDEX 生命周期登记分类。

---

## 一、意图系统（优先级高，最近重写多）

1. **[推测] `intent_context.resolve()` 的"消费"语义边界**：`_ic_resolve` 用 `get_active_intents()`
   （只读持久栈），**不消费 smear/override**；而 LLM 解析路径 `resolve_to_prompts` 会
   `consume_smear`/`consume_override`。同一上下文上先 `ctx.resolve()` 再触发 LLM 调用，行为是否
   一致？恶意测：`@+ "A"` + `@ "smear"` 后 `ctx.resolve()` 看 smear 是否出现；再 LLM 调用看是否
   重复/丢失。文档 `09_intent_system.md` 的"resolve 只读视图"契约是否与实际一致。
2. **[推测] `render_text()` 的 `strip()` 会剥离意图值前后空格**：`"".join(...).strip()` ——若用户
   `@+ " 带空格的意图 "` 意图是保留空格（如"两端留白"），strip 会改变语义；`@- " 带空格的意图 "`
   按值匹配时是否因 strip 而失配。恶意测：含前导/尾随空格的意图 push→resolve→remove 全链路。
3. **[推测] `@-` 无参弹栈 vs 按值移除的歧义**：`@-`（无参）弹栈顶，`@- "值"` 按值移除。若栈顶
   意图渲染文本恰为某字面量，两条路径是否会混淆？恶意测：`@+ "A"` + `@- "A"`（字面量与栈顶同值）
   与 `@-` 无参的差异；`@-` 后意图栈顺序。
4. **[推测] `@!` override 与 smear 并存时的丢弃顺序**：`resolve_to_prompts` 在 override 激活时
   `consume_smear()` 丢弃 smear。若用户先 `@! "排他"` 再 `@ "涂抹"`，涂抹被丢；反之先涂抹再排他
   （同一语句窗口内连续两个 one-shot，后者覆盖前者，KNOWN_LIMITS §十三 #2）——两个 one-shot
   叠加的边界是否清晰、有无静默丢意图。
5. **[推测] run_batch 内 one-shot 注入批内每一个调用**（KNOWN_LIMITS §十三 #6 已记录）：恶意测
   批内部分调用想排除意图时是否无解（文档建议拆分语句）；`__intent__` 三层改写与 one-shot 叠加
   时的优先级。
6. **[推测] snapshot 意图冻结 vs lambda 调用点 live 的边界**：`test_snapshot_intent_freeze`
   覆盖了纯 snapshot lambda 与 lambda 对照，但"snapshot 内嵌 LLM 调用 + 调用点意图"交叉场景
   （如 snapshot 函数体内再调 llm 可调用类）未穷尽。恶意测：snapshot 定义在 `@+` 后、调用在
   `@-` 后，意图是否泄漏/丢失。
7. **[已知] `intent_context` 类静态调用"静默无效"**（KNOWN_LIMITS §十二）：`intent_context.push()`
   在类对象上调用编译期警告但运行时无效。恶意测：`intent_context.get_current()` 返回快照后直接
   `push`（不经 `use`）是否产生"以为生效实则无效"的静默状态。

## 二、LLM 可调用类与协议族（五大地基重写面，优先级高）

8. **[推测] `__llm_call__` 装配 dict 键校验边界**：`user_prompt`/`prompt_slots`/`expected_type`
   之外的键是否被忽略/报错？`expected_type` 缺失时按字符串解析（KNOWN_LIMITS §二十五），恶意测
   缺失/类型错/键名拼错时的行为是 fail-fast 还是静默降级。
9. **[推测] `__intent__` 三层改写（active/global/merged）的返回契约**：返回 dict 键为三层任意
   子集，缺失键保持原层，显式空列表清空。恶意测：返回非法键/返回非 dict/返回 None/层键给出
   非列表——是否 fail-fast；`__intent__` 异常是否被吞（对照 B2 的 to_prompt_str KDIAG 修复精神）。
10. **[推测] `__retry__` 高阶化边界**：返回 `{"max_retry": n, "hint": "..."}`，空 dict 合法。
    恶意测：max_retry=0/负/非 int、hint 非 str、返回非 dict、`__retry__` 抛异常——是否 fail-fast
    （对照 `_llm_callable.py:338` 的契约校验）；调用级策略耗尽 + 外层 llmexcept 的叠加轮数。
11. **[推测] prompt 协议族五成员异常路径**：`__to_prompt__`/`__payload_prompt__`/`__outputhint_prompt__`/
    `__from_prompt__`/`__validate_prompt__` 各自抛异常时的行为（B2 已修 to_prompt_str AttributeError
    静默吞并，但其余成员是否仍有静默路径）。恶意测：每个协议方法抛不同类型异常（AttributeError/
    ValueError/RuntimeError/InterpreterError）看是否 KDIAG 发射/回退/传播。
12. **[已知] `__from_prompt__` 单向契约**（PT-DECIDE-3 ①，B 阶段已定）：返回值必须是目标类型实例，
    非实例=契约违约（诊断+uncertain）。恶意测：返回同值不同类型/返回 None/返回 tuple 但形状错/
    抛异常——各路径是否都 fail-fast。
13. **[推测] 直接调用 `f(args)` 参数绑定边界**：`__llm_call__` 非 self 参数按位绑定，恶意测：
    实参数少于/多于声明参数、关键字参数、默认参数、`__llm_call__` 无参但有实参——是否 fail-fast。
14. **[推测] stream_call/stream_channel 错误传播**：流式中途 provider 报错/超时/截断——`await`
    后抛什么？逐块 recv 中错误是否丢失？KNOWN_LIMITS §十五 已记录"流式调用不入 call_info 观测"。
    恶意测：流式 + llmexcept 组合、流式中断后资源清理。

## 三、意图一等值 / 快照 / 序列化

15. **[推测] intent_context 作为类字段的 deep_clone 路径**：`deep_clone.py` 对 IbIntentContext
    用 `fork()` 得值快照。恶意测：类字段含 intent_context 时深拷贝是否独立（改拷贝不影响原）；
    `_ctx` 含复杂意图值时 fork 深拷贝完整度。
16. **[推测] 序列化 round-trip 的 inherited_smear/inherited_override**：`runtime_serializer` 序列化
    6 个槽位含 inherited_smear/override（L203-204）。恶意测：快照→序列化→反序列化后 intent 状态
    是否完全等价（含 inherited 槽）；`get_intent_ctx` 契约访问在 rehydrate 后是否一致（B4 收敛后）。
17. **[推测] 跨引擎序列化/水化边界**：`_rehydrate_type_pool_spec` 跨引擎 rehydrate 特化类（PT-DEBT-33
    封印回落基类已修），恶意测：跨引擎 round-trip 时意图上下文/特化类/枚举身份是否丢失或退化。

## 四、覆层机制（overlay，五大地基新特性）

18. **[推测] `impl overlay` + `with overlay` 作用域边界**：overlay 仅对内置具体值类型有意义
    （KERNEL_NATIVE），恶意测：overlay 目标用用户类/泛型/dotted 名；`with overlay(<T>.<方法>):`
    未启用时告警（SEM_OVERLAY_UNUSED）；嵌套 overlay 计数（test_overlay_concurrency 已测并行根
    隔离，但"嵌套同名 overlay 的恢复顺序"未穷尽）。
19. **[推测] overlay 与序列化/snapshot 交互**：overlay 影子条目在 snapshot/retry/序列化时是否被
    保留/重置——恶意测：overlay 作用域内触发 llmexcept retry，恢复快照后 overlay 是否还在。
20. **[推测] overlay 跨根并发隔离**：test_overlay_concurrency 已测并行 roots 不污染；恶意测：
    同一引擎多线程共享执行上下文时 overlay 开关（`_overlay_enabled_in_current_context`）的线程
    隔离边界；overlay 作用域内 spawn 子线程继承与否。

## 五、宿主绑定 / 动态宿主（隔离与安全面）

21. **[已知] 模块可见性隔离而非代码强隔离**（KNOWN_LIMITS §十九）：`sys.modules` 进程级缓存，
    同名模块"先加载者胜"。恶意测：两引擎绑定同名不同内容模块，验证共享状态污染边界；模块级
    可变全局跨引擎共享（无状态约定无强制力）。
22. **[推测] 动态宿主 `collect` 错误传播/超时**：`test_execution_isolation` 已测编译失败传播与
    collect_timeout；恶意测：子环境死循环（OS 超时）、子环境写父环境 project_root 之外、子环境
    LLM 配置继承（KNOWN_LIMITS §11.6 已记录不继承）、同一 handle 重复 collect（幂等已测）。
23. **[推测] 宿主绑定 bind 白名单/vtable 强制**：`native_module.py` 有 registry_id 隔离检查
    （RegistryIsolationError）；恶意测：bind 未声明成员访问、bind 类型不符、跨引擎误用实例、
    bind 的 Python 对象持有模块级可变全局。
24. **[推测] 沙箱/路径越界**：`fs` 沙箱默认禁止越出 project_root（KNOWN_LIMITS §11.7）。恶意测：
    `../` 路径穿越、符号链接逃逸、`fs` 写入绝对路径、`ihost.run_isolated` 子入口越界（B6 验证过
    "子脚本不得超出父 project_root"拒绝）。

## 六、类型系统 / 泛型 / 容器

25. **[已知] 容器 `==` 默认身份比较**（PT-DEBT-34 审计确认，文档化不改行为）：list/dict 未定义
    `__eq__`，`==` 按身份比较。恶意测：两个内容相同不同 list 的 `==`/`!=` 结果；用户类覆写 `__eq__`
    后与容器混用；`list[int] == list[int]` 编译/运行行为。
26. **[推测] 泛型特化边界**（KNOWN_LIMITS §十四 #1 已列 8 项）：恶意测 `Box[T]` 嵌套特化、
    泛型继承 + 覆层、`list[Box[int]]` 元素特化身份、跨模块同裸名特化（geo.Box[int] vs
    graph.Box[int]，T09 已测同模块隔离）。
27. **[推测] Optional[T] 值模型边界**（KNOWN_LIMITS §十五 已记录部分）：Optional[list[int]] 有值
    包装后 len/下标（T07 D2-10 已修核销）；恶意测：Optional 嵌套、Optional 作为类字段/容器元素、
    `or_else` 链式、`unwrap` 空值错误码一致性（DOC-29 已修）。

## 七、控制流 / 异常 / 并发

28. **[推测] llmexcept 快照隔离深边界**：KNOWN_LIMITS §十/§二十 已记录文件写禁与磁盘型浅引用；
    恶意测：retry body 内非 LLM 参与变量的修改（允许）与 LLM 参与变量间接修改（运行时快照违规
    警告 RUN_LLMEXCEPT_SNAPSHOT_VIOLATION 已测）；嵌套 llmexcept 深度上限（128，runtime_context:
    593）；retry 内再触发 LLM 调用。
29. **[推测] 递归深度双上限**（KNOWN_LIMITS §二十三）：trampoline 使调用链不耗 Python 栈，但作用域
    链符号解析仍 Python 递归（~980 层 RecursionError）。恶意测：深递归 + 深作用域嵌套交叉；
    提升 recursionlimit 后行为。
30. **[推测] switch/case 边界**（KNOWN_LIMITS §十一）：case 单行不支持、break no-op、continue 透传
    已测；恶意测：switch 嵌套、case 内 return（B1 已补）、case 值重复、Enum 混合类型 case。
31. **[推测] 并发/线程边界**：KNOWN_LIMITS §十五/§二十二 已记录 DDG dispatch 边界与通信原语；
    恶意测：thread 内 LLM 调用 + llmexcept、chan 有界缓冲满阻塞、slot CAS 竞态、`await` 嵌套、
    线程 + overlay 交叉。

## 八、文档/行为一致性（试用应核对）

32. **[推测] 文档宣称 vs 实际行为漂移**：五大地基重构后 `docs/syntax/`（15 章）+ `docs/guide/`
    声明与新语义是否一致（`llm ... llmend` 已删、LLM 可调用类、覆层、prompt 协议族、意图一等值、
    fs、值语义 §2.8/§5.10、KNOWN_LIMITS 编号已变）。试用发现的 DOC_ISSUE 全量登记，阶段 C 后
    统一文档复核更新同步（HANDOFF_SESSION §6.5）。
33. **[推测] 未读变量/死代码路径**：KNOWN_LIMITS §十五 已记录未读取 dispatched 变量残留
    `_pending_futures`；恶意测：`_pending_futures` 在长循环/长会话中的累积（内存泄漏面）。

---

## 九bis、验证状态核对（2026-08-21，阶段 C 恶意试用后）

> 逐条核对起点清单的验证结果。已测项给出套件/用例引用与结论；未测项标注原因
> （LLM 层依赖 / 需专项 / mock 不可确定观测）。**阶段 C 结束时**：确认项吸收进
> `docs/KNOWN_LIMITS.md`，缺陷项吸收进 `trials/INDEX.md`，然后删除本清单。

| # | 状态 | 验证结论（套件/用例） |
|---|------|------------------------|
| 1 | ✅ 已测 | T15-E-M11：ctx.resolve() 只读持久栈视图，不消费（PASS，文档 §9.3 一致） |
| 2 | ✅ 已测 | T15-E-M2：意图值空格 strip/子串（PASS） |
| 3 | ✅ 已测 | T15-E-M3：@- 无参 vs 按值移除（PASS） |
| 4 | ✅ 已测 | T15-E-M4：@! override 丢弃 smear = 后者覆盖前者（PASS，KNOWN_LIMITS §十三 #2 一致） |
| 5 | ✅ 已测 | T08 D3-03/04/06/07：run_batch 批内每个调用注入 one-shot（LLM_BEHAVIOR/已文档化） |
| 6 | ⏸ 部分 | T13-I-M3 覆盖 snapshot 冻结 vs lambda live；snapshot 内嵌 LLM 调用交叉未穷尽（LLM 层） |
| 7 | ✅ 已测 | T15-E-M9：intent_context 类静态调用静默无效（现为 fail-fast，KNOWN_LIMITS §十二 已修正） |
| 8 | ✅ 已测 | T15-E-M5：装配 dict 未知键静默忽略（08 §8.1 已补文档） |
| 9 | ✅ 已测 | T15-E-M12 + T10-G4：__intent__ 返回契约违约 fail-fast（PASS/GUARD） |
| 10 | ✅ 已测 | T15-E-M13 + T10-G3：__retry__ max_retry=0/签名违约 fail-fast（GUARD） |
| 11 | ✅ 已测 | T15-E-M7 + T12-P-G1：协议族异常路径传播/形状违约（GUARD） |
| 12 | ✅ 已测 | T12-P-G1：__from_prompt__ 单向契约（LLMParseError，PT-DECIDE-3 ① 一致） |
| 13 | ✅ 已测 | T15-E-M6/M14/M16 + T10：直接调用参数数量违约 fail-fast（GUARD） |
| 14 | ⏸ 部分 | T11 流式正常路径；流式中断/llmexcept 组合 LLM 层待补 |
| 15 | ⏸ 未测 | intent_context 类字段 deep_clone 路径（专项） |
| 16 | ⏸ 未测 | 序列化 round-trip inherited 槽（专项，snapshot 序列化） |
| 17 | ⏸ 未测 | 跨引擎序列化/水化（专项，多引擎） |
| 18 | ✅ 已测 | T12-O-M1/M2/M3 + O-G1/G2：overlay 作用域/默认不生效/嵌套/守卫（PASS+GUARD） |
| 19 | ⏸ 未测 | overlay 与序列化/snapshot/retry 交互（专项） |
| 20 | ✅ 已测 | T12 跨根并发隔离（内核判别测试 test_overlay_concurrency 承载） |
| 21 | ✅ 已测 | T05 D2-17 + T15-PR4：模块可见性隔离/跨模块（PASS） |
| 22 | ⏸ 未测 | 动态宿主 collect 错误/超时（专项，ihost） |
| 23 | ⏸ 未测 | bind 白名单/vtable 强制（专项，宿主绑定） |
| 24 | ✅ 已测 | T14-FS-M5：沙箱越界写拒绝 RUN_PERMISSION_ERROR（无漏洞） |
| 25 | ✅ 已测 | T15-E-M1：容器 == 身份比较（KNOWN_LIMITS/PT-DEBT-34 一致） |
| 26 | ✅ 已测 | T15-E-M15：泛型嵌套特化 Box[Box[int]]（PASS） |
| 27 | ✅ 已测 | T14-OPT-M1/M2：Optional 值模型/容器元素（PASS） |
| 28 | ✅ 已测 | T15-E-M17/M19：retry 体内文件写编译期禁 + 快照隔离告警/恢复（GUARD/PASS） |
| 29 | ✅ 已测 | T15-E-M8：深递归 RecursionError（KNOWN_LIMITS §二十三 一致，LIMIT） |
| 30 | ✅ 已测 | T15-E-M10 + T01：switch 边界（重复 case/嵌套/return，PASS） |
| 31 | ✅ 已测 | T15-E-M18：线程内 LLM + try/except（PASS） |
| 32 | 🔄 处理中 | 文档/行为一致性：doc-review 进行中（KNOWN_LIMITS §十二已修/overlay 章节已补/装配未知键已明） |
| 33 | ⏸ 未测 | _pending_futures 长会话累积（内存面，专项） |

**未测项汇总**（专项/LLM 层）：#6 交叉、#14 流式错误、#15 deep_clone、#16/#17 序列化/跨引擎、#19 overlay 序列化交互、#22 动态宿主、#23 bind 强制、#33 内存累积。

## 九、使用方式（对下一 session 的明确说明）

1. **本清单是起点，不是穷尽**：以上 33 项为接手者基于代码工作的观察，**标记 `[推测]` 的未逐个
   实证**。恶意试用必须**自行扩展**：每个特性域都要问"这里会不会坏？开发者没想过什么？"。
2. **每项给对抗性用例**：按 §一到§八 逐条设计 `.ibci` 用例，放新试用地基（`T<nn>_<主题>`，
   遵循 `trials/_toolkit/CLASSIFICATION.md`），头部 `expect-class` 断言，harness 自动判定。
3. **分类与闭环**：发现 → 按 INDEX 生命周期分类（KERNEL_ISSUE/BOUNDARY/DOC_ISSUE/LLM_BEHAVIOR/
   LIMIT/GUARD/HARNESS）→ 登记 → （修复阶段）根因修复 + tests/ 补回归 → 触发用例核销。
4. **原则**：只记录不修复（优先确定性记录可溯源）；不为规避缺陷改套件（缺陷触发用例保留）；
   每个试用加死循环保护（run_batch harness OS 级硬超时）。
5. **服务前置**：真实 LLM 试用前先 `curl -s -m 5 http://127.0.0.1:1234/v1/models` 探测；失败则
   mock 层先行，LLM 用例标 HARNESS 不误判缺陷。
6. **本清单在阶段 C 结束时**：逐条核对验证结果，吸收进 `docs/KNOWN_LIMITS.md`（确认项）或
   `trials/INDEX.md`（缺陷项），然后删除本临时文档（git 承载历史）。
