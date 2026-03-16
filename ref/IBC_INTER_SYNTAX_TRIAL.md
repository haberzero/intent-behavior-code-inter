# IBC-Inter 语法组合与边界试用记录 (2026-03-16)

> 本文档专注于 IBC-Inter 常用语法的组合应用测试，探索其语法边界及潜在的解析/运行风险。

---

## 1. 基础类型转换与复杂算术表达式
- **测试脚本**: `syntax_type_arithmetic.ibci`
- **目标**: 验证类型显式转换、操作符优先级、以及 `str + int` 等级联拼接的稳定性。
- **实测结果**:
    - ✅ **隐式提升**: `int + float` 正常产生 `float`。
    - ✅ **显式截断**: `(int)(float)` 正常工作。
    - ❌ **级联拼接崩溃 (重大 Bug)**: `str + (str)float` 报错 `TypeError: Cannot concatenate 'str' and 'float'`。
- **深度分析**:
    - **内核转换逻辑错误**: 发现 `(str)float` 在运行时并未调用 `str` 转换，而是返回了原始的 `IbFloat` 对象。
    - **赋值检查不一致**: 即使使用 `var` 声明变量，运行时 `define_variable` 依然会根据表达式右值的实际类型推断并锁定左值类型，导致后续赋值可能触发 `Type mismatch`。
    - **唯一安全写法**: 必须将所有拼接项分步赋值给 `var` 变量，并确保每一步拼接的左侧都是显式的 `IbString` 对象。

---

## 2. 类 (Class) 与提示词协议 (__to_prompt__) 的深度组合
- **测试脚本**: `syntax_class_protocol.ibci`
- **目标**: 验证嵌套对象在 LLM 插值时的序列化行为。
- **实测结果**:
    - ❌ **协议调用失效 (重大偏差)**: 在 LLM 插值时，对象未按 `__to_prompt__` 协议序列化，而是直接输出了 `<Instance of Book>`。
    - ❌ **解析限制**: 在 `Class` 方法中直接对 `self.member` 进行类型转换（如 `(str)self.author`）会导致编译错误，必须先赋值给局部变量。
- **技术分析**:
    - **插值逻辑缺失**: 深入 [llm_executor.py](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/interpreter/llm_executor.py#L130-131) 发现，虽然代码中尝试调用了 `__to_prompt__`，但由于对象被 `box` 包装后，`hasattr(val, '__to_prompt__')` 可能因为协议未正确穿透到 `IbObject` 而判定为假。
    - **编译器鲁棒性**: 解析器对属性访问后的级联表达式支持极差，无法在单行内处理复杂的成员转换。
- **结论**: `__to_prompt__` 协议在当前版本中并未真正打通 LLM 插件，对象序列化功能不可用。

---

## 3. LLM 函数与变量插值的边界
- **测试脚本**: `syntax_llm_function.ibci`
- **目标**: 验证参数命名冲突（如 `content`）以及多层插值的稳定性。
- **实测结果**:
    - ❌ **严重内核 Bug (String Concat)**: `str + str` 竟然报错 `TypeError: Cannot concatenate 'str' and 'str'`。
    - ❌ **命名冲突**: 参数名为 `content` 时会引发内部逻辑异常，证实了 `LLMExecutor` 内部局部变量污染了用户命名空间。
- **技术分析**:
    - **字符串拼接逻辑自相矛盾**: [builtin_initializer.py](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/bootstrap/builtin_initializer.py#L235) 检查 `other.descriptor is not STR_DESCRIPTOR`。由于内核中可能存在多个 `STR_DESCRIPTOR` 实例（如编译期与运行期未对齐），导致即使两个都是字符串也无法拼接。
    - **LLM 函数插值本质**: LLM 函数内部的插值本质上也是在执行字符串拼接，因此同样受上述拼接 Bug 的影响，导致 LLM 函数几乎无法在包含插值的情况下正常工作。
- **结论**: 字符串系统在当前版本中完全损坏，无法进行任何形式的拼接。

---

## 4. Lambda 化行为与闭包捕获
- **测试脚本**: `syntax_lambda_behavior.ibci`
- **目标**: 验证 `callable` 捕获当前环境意图及延迟执行的一致性。
- **实测结果**:
    - ❌ **命名作用域污染**: 无法在同一脚本中重复定义名为 `behavior` 的变量，即使在不同的作用域逻辑中，编译器也会报 `already defined`。
    - ❌ **闭包执行失败**: 由于行为描述行执行时内部会触发字符串插值（拼接），受限于全局 `str + str` Bug，所有包含变量插值的行为对象在调用时均会崩溃。
- **技术分析**:
    - **静态分析与动态执行脱节**: 编译器虽然识别了闭包捕获，但运行时解释器在处理插值时，由于 `STR_DESCRIPTOR` 不匹配导致拼接失败。
- **结论**: 行为对象作为 IBCI 的核心“Lambda”实现，目前在实际应用中几乎不可用，除非其内容是纯静态字符串。

---

## 5. 集合操作 (List/Dict) 的边界情况
- **测试脚本**: `syntax_collections.ibci`
- **目标**: 验证嵌套访问及非法索引的内核反馈。
- **实测结果**:
    - ❌ **转换接口缺失**: `(str)list` 触发 `AttributeError: Object of type 'list' has no method 'cast_to'`。
    - ❌ **协议不完整**: `List` 和 `Dict` 仅实现了 `__to_prompt__` 用于 LLM 序列化，但未在解释器层面注册 `cast_to` 接口，导致无法通过显式强转转换为字符串供 `print` 使用。
- **技术分析**:
    - **内核注册疏漏**: 在 [builtin_initializer.py](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/bootstrap/builtin_initializer.py) 中，`int`, `float`, `str` 均通过 `__call__` 路由到了 `cast_to` 逻辑，但 `list` 和 `dict` 的注册表里完全没有这个方法。
- **结论**: 集合类型目前是“黑盒”，除了解释器内部逻辑外，无法在脚本层方便地进行打印调试或转换为文本。

---

## 6. 总结
本轮语法组合测试揭示了 `ibc-inter` 在 **基础类型鲁棒性** 上的严重缺失：
1. **字符串拼接完全损坏**：导致 `print`、`llm 函数`、`行为插值` 全部失效。
2. **类型转换逻辑混乱**：`(str)float` 返回 `float`，`(str)list` 报错。
3. **协议打通度极低**：`__to_prompt__` 虽有定义但在插值时未被正确调用。
目前该语言仅能进行极简的纯静态逻辑运算，任何涉及字符串动态生成的语法组合均无法通过实测。
