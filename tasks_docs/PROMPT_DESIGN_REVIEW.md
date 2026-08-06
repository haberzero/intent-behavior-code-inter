# PROMPT_DESIGN_REVIEW — `__prompt__` 协议家族已知问题与待决策项

> 迁自 `docs/KNOWN_LIMITS.md` §十六（2026-08-06）。本节内容是**设计待决项**，属设计阶段内容，
> 依 `AGENTS.md` 设计阶段文档放置规则放于 tasks_docs/。决策落地后收敛入技术手册。
> **状态**：下列项均未决策，仍为当前已知问题。

---

## 一、用户类 `__from_prompt__` 返回的实例字段访问风险

**现象**：用户自定义类实现 `__from_prompt__` 时，在特定条件下返回实例的 `.field` 访问可能返回 `None` 而非实际赋值内容。

**当前行为**：`VTableParsingStrategy` 加入 `is_instance_of_target` 类身份检查——当 `__from_prompt__` 返回目标类的正确实例时跳过 auto-boxing。但若类身份比对失败（如跨模块加载导致类对象不同一），仍可能触发二次封装覆写字段。

**待决策**：
- 是否应该在 `__from_prompt__` 返回的对象类型已匹配目标类时，完全跳过 auto-boxing？
- 是否需要强制要求 `__from_prompt__` 返回的第二元素必须是目标类的实例？

## 二、`__validate_prompt__` 协议的执行时机语义

**问题**：`__validate_prompt__` 在 `VTableParsingStrategy` 中执行时，仅覆盖通过用户类 vtable 路径解析的类型。对于 axiom 内置类型（`int`/`float`/`bool`/`str`/`list`/`dict`/`enum`），pre-flight 校验走的是 axiom 自身的 `from_prompt` 内部逻辑，不经过 `__validate_prompt__`。

**待决策**：
- 是否应该为内置类型也提供 `__validate_prompt__` 扩展点？
- 当前设计是否足够——内置类型的 `from_prompt` 已含校验逻辑（返回 `(False, hint)` 时即触发 retry）？

## 三、`__to_prompt__` 的异常处理（已加可观测性）

**现状**：`LLMExecutorImpl._obj_to_prompt_str()` 统一了 prompt 序列化路径，内部 `try/except` 在 `__to_prompt__()` 抛异常时回退到 `str(val)` / `str(val.to_native())`。降级行为保留（LLM 调用不因 prompt 序列化失败而中断）。

静默吞异常已改为 `core_debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, ...)` 日志——用户实现的 `__to_prompt__` 若抛异常（如字段未初始化的 AttributeError），开启调试（默认 NONE 级，零开销）即可观测。同样的处理应用于 `__payload_prompt__` / `to_native` 回退链。

## 四、协议签名校验（SEM_PROTOCOL_SIGNATURE）的强度选择

**问题**：`SEM_PROTOCOL_SIGNATURE` 是 warning 而非 error——用户可以声明签名不匹配协议约定的 `__from_prompt__`（如 0 个参数），编译仍通过。运行时如果 axiom 路径命中就不会调用 vtable，但如果确实调用到 vtable 则会在运行时失败。

**待决策**：
- 是否将 SEM_PROTOCOL_SIGNATURE 从 warning 提升为 error（阻止编译）？
- 或保持 warning——鉴于协议方法签名本身属于 `_OVERRIDE_SIGNATURE_FREE`（允许自由修改签名以适配不同场景）？
