# IBC-Inter 试用测试记录 (2026-03-16)

> 本文档记录新一轮对 IBC-Inter 的试用测试过程、结果及新发现的问题。

---

## 1. 浮点数比较逻辑专项测试
- **测试脚本**: `trial_float_compare.ibci`
- **测试环境**: 本地解释器 (IBCI V2.3.1)
- **测试目标**: 验证 `float` 类型的比较运算符支持情况。
- **实测结果**:
    - ✅ `==` (相等) 与 `!=` (不等) 正常工作。
    - ❌ `>` (大于) 触发运行时错误：`AttributeError: Object of type 'float' has no method '__gt__'`。
- **发现与结论**:
    - 在 `core/runtime/bootstrap/builtin_initializer.py` 中，`float_class` 仅显式注册了 `__eq__` 和 `__ne__`。
    - 缺失 `__lt__`, `__le__`, `__gt__`, `__ge__` 的注册，导致无法进行大小比较。
    - 浮点数目前仅能进行相等性判断，无法进行序关系比较。

---

## 2. 意图修饰符与 idbg 模块测试
- **测试脚本**: `trial_intent_modifiers.ibci`
- **实测结果**:
    - ❌ **内核崩溃**: 调用 `idbg.env()` 时抛出 `AttributeError: 'IDbgPlugin' object has no attribute '_capabilities'`。
    - ❌ **修饰符失效 (验证成功)**:
        - `@!` (排他) 之后，全局意图依然存在于意图栈中。
        - `@-` (删除) 之后，指定内容被当作普通意图压栈，而非执行删除操作。
- **技术分析**:
    - **Bug 1 (idbg)**: `IDbgPlugin` 在 `setup` 阶段未正确初始化 `_capabilities` 或访问了不存在的属性。
    - **Bug 2 (Parser/AST)**: 
        - [statement.py](file:///d:/Proj/intent-behavior-code-inter-master/core/compiler/parser/components/statement.py#L131) 将模式解析为 `"override"` / `"remove"`。
        - [ast.py](file:///d:/Proj/intent-behavior-code-inter-master/core/domain/ast.py#L108) 却在属性检查中使用 `self.mode == "!"` / `self.mode == "-"`。
        - 这种字符串字面量的不一致导致运行时逻辑分支失效。
- **结论**: 意图系统的叠加、排他、删除功能在当前版本中完全不可用。

---

## 3. IbBehavior 对象存储与打印测试
- **测试脚本**: `trial_behavior_repr.ibci`
- **实测结果**:
    - ❌ **运行时崩溃**: 当 `IbBehavior` 对象（延迟执行的行为）存入 `dict` 并尝试 `print(dict)` 时，抛出 `RuntimeError: Behavior is not executed.`。
- **技术分析**:
    - [builtins.py](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/objects/builtins.py#L297-300) 中的 `receive` 方法在 `_cache` 为空时（即未执行前）会直接抛出异常，拒绝处理任何消息。
    - 然而，[builtin_initializer.py](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/bootstrap/builtin_initializer.py#L252) 中 `dict` 的 `__to_prompt__` 逻辑会递归调用成员的 `receive("__to_prompt__", [])`。
    - 即使 `IbBehavior` 自身实现了 `__to_prompt__` 方法，由于解释器调度通常走 `receive` 接口，导致在未执行时无法安全地对包含行为对象的集合进行打印或序列化。
- **结论**: 在将行为对象存入集合前，必须显式执行它（如 `callable res = @~...~; str s = res(); dict d = {"key": s}`），否则会导致整个集合无法打印。

---

## 4. Mock 模式功能测试
- **测试脚本**: `trial_mock_mode.ibci`
- **实测结果**:
    - ❌ **核心功能缺失 (重大偏差)**:
        - `MOCK:TRUE` -> 返回 1 (正常)。
        - `MOCK:FALSE` -> **依然返回 1** (错误)。
        - `MOCK:FAIL` -> **依然返回 1** (错误，未触发 `llmexcept`)。
- **技术分析**:
    - 在 [ai/core.py](file:///d:/Proj/intent-behavior-code-inter-master/ibc_modules/ai/core.py#L169-177) 中，Mock 逻辑被硬编码为：在 `branch` 或 `loop` 场景下，无论输入内容为何，始终返回 `"1"`。
    - 这与 `IBC_INTER_LEARNING_SUMMARY.md` 及官方示例 `04_mock_advanced.ibci` 中宣称的“高级 Mock 指令 (MOCK:TRUE/FALSE/FAIL/REPAIR)”**严重不符**。
- **结论**: 学习总结报告中提到的 Mock 测试“功能完善”可能基于旧版本或尚未合并的代码分支。当前主线代码中的 Mock 机制仅为极简实现，无法用于模拟复杂的分支判断和异常处理流程。

---

## 5. 使用真实 API (Qwen 3.5) 进行业务逻辑试用
- **测试脚本**: `trial_real_llm.ibci`
- **实测结果**:
    - ❌ **核心功能空缺 (重大发现)**: 调用 AI 时始终返回 `[REAL_LLM_NOT_IMPLEMENTED_IN_CORE]`。
    - ❌ **类型转换 Bug**: `print("循环第 " + (str)count + " 次...")` 依然报 `TypeError: Cannot concatenate 'str' and 'int'`，暗示 `(str)count` 可能未正确产生 `IbString` 或 `+` 运算符在处理级联拼接时存在问题。
- **技术分析**:
    - **核心漏洞**: 深入审查 [ibc_modules/ai/core.py](file:///d:/Proj/intent-behavior-code-inter-master/ibc_modules/ai/core.py) 发现，其 `__call__` 方法虽然初始化了 `OpenAI` 客户端，但在实际执行逻辑中却直接返回了硬编码的占位字符串（第 180 行）。这意味着当前仓库中的 `ai` 模块**根本不具备真实的 LLM 调用能力**。
    - **类型转换问题**: 尽管 `builtin_initializer.py` 定义了 `str(x)` 转换逻辑，但在级联拼接（`str + str + str`）时，由于 `+` 的左结合律，第一个 `+` 返回的结果可能由于某种原因（如 `box` 后的描述符未正确对齐）导致第二个 `+` 判定失败。
- **结论**: 当前 `ibc-inter` 的主线工程是一个“空壳”，最重要的 LLM 调用能力在核心插件中仅有框架而无实现。这导致所有依赖真实 AI 的业务场景（意图驱动循环、语义判定等）在当前环境下均无法正常运行。

---

## 6. 总结与建议
- **架构成熟度**: 解释器框架、符号表、池化存储等底层设施已基本就绪。
- **功能完整度**: **极低**。关键的意图修饰符、高级 Mock 机制、真实 LLM 调用、基础类型（float）运算等核心功能均存在重大缺陷或完全缺失。
- **建议**: 
    1. 修复 `ai` 模块的 `__call__` 实现，接入真实的 OpenAI 接口。
    2. 修复解析器中 `mode` 字符串映射（`override` vs `!` 等）导致的意图系统失效。
    3. 补全 `IbFloat` 的比较运算符实现。
    4. 修正 `idbg` 模块的初始化逻辑以支持调试。
