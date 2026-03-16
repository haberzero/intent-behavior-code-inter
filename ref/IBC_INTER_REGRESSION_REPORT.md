# IBC-Inter 全量语法回归测试与现状报告 (2026-03-16)

> 本报告详细记录了对 IBC-Inter (V2.3.1) 所有基本语法的覆盖测试结果。

---

## 1. 确定可用的稳定语法 (Confirmed Usable)

这些语法在当前底层 Bug 频发的环境下依然能正常工作，是维修时的“安全区”：

- **基础变量声明**:
  - `int i = 42`
  - `str s = "text"`
  - `list l = [1, 2]`
  - `dict d = {"a": 1}`
- **算术运算 (限同类型)**:
  - `int sum = a + b` (整数加法正常)
- **控制流 (限基本逻辑)**:
  - `if / elif / else` 分支判定。
  - `for item in list` 标准迭代。
  - `while` 循环。
- **类系统基础**:
  - `class` 定义、成员变量初始化。
  - 简单的方法调用 `obj.method()`。
- **配置与 Mock**:
  - `ai.set_config("TESTONLY", ...)` 成功进入测试模式。
- **无插值 LLM 函数**:
  - `llm f(): __user__ text llmend` 能够定义并返回静态文本。

---

## 2. 严重退化与损坏的语法 (Critically Broken)

这些功能在旧版笔记中记录为可用，但在 V2.3.1 中因底层架构冲突已失效：

### 2.1 字符串与类型转换系统 (Identity Mismatch Bug)
- **现象**: `(str)int` 返回的依然是 `int`；`str + str` 报错。
- **根源**: [converters.py](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/support/converters.py) 与 [builtin_initializer.py](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/bootstrap/builtin_initializer.py) 使用 `is STR_DESCRIPTOR` 进行身份判定。由于 IES 2.0 隔离机制，运行时描述符是副本，与全局原型不一致，导致判定全部失效。
- **影响**: 
  - `(str)x` 强制转换失效（返回原值导致 Type mismatch）。
  - 所有字符串拼接 `+` 失效。
  - 所有 `print` 级联调用失效。

### 2.2 AI 交互核心 (级联失效)
- **变量插值 (`$var`)**: 内部依赖字符串拼接逻辑，目前完全无法使用。
- **带参 LLM 函数**: 内部构建 Prompt 时需拼接参数，目前全部崩溃。
- **提示词协议 (`__to_prompt__`)**: 虽有定义，但由于其返回结果在插值时无法被正确识别/拼接，目前不可用。

### 2.3 标准库加载 (Spec Name Mismatch)
- **现象**: `import json`, `import math` 等报错 `Cannot resolve module`。
- **根源**: [discovery.py](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/module_system/discovery.py) 硬编码寻找 `_spec.py`，而标准库文件多命名为 `spec.py`。
- **现状**: 仅 `ai` 和 `idbg` (含 `_spec.py`) 可被导入。

---

## 3. 架构缺陷与边界发现

- **浮点数序关系缺失**: `float` 依然无法进行 `>` 或 `<` 比较。
- **作用域限制**: 不支持在不同逻辑块中重定义同名变量。
- **idbg 崩溃**: `idbg.env()` 调用仍会触发内核属性缺失异常。

---

## 4. 结论
目前 IBC-Inter 的“地基”虽好，但由于 IES 2.0 引入的描述符隔离未在转换层对齐，导致**整个类型转换与字符串系统处于瘫痪状态**。这直接锁死了 90% 的 AI 交互语法。

**下一步行动**: 必须立即按照 [IBC_INTER_FIX_GUIDE.md](file:///d:/Proj/intent-behavior-code-inter-master/IBC_INTER_FIX_GUIDE.md) 中的指引，统一描述符匹配算法，否则无法进行任何有意义的功能闭环。
