# IBC-Inter 标准库模块规范 - ai (v1.0 - 深度架构版)

`ai` 模块不仅是 LLM 配置工具，更是 IBC-Inter 解释器执行“意图流”的核心网关。本手册旨在从架构层面解析 `ai` 模块如何深度嵌入语言执行引擎。

---

## 1. 架构集成：LLMExecutor 接口实现

在 IBC-Inter 的底层设计中，解释器并不直接与 LLM 通信，而是通过 `LLMExecutor` 抽象接口。`ai` 模块的 Python 实现类 `AILib` 在加载时会被注入并接管该接口。

### 1.1 注入机制 (Injection)
当 `.ibci` 代码中出现 `import ai` 时：
1. **模块加载**: `ModuleLoader` 实例化 `AILib`。
2. **Setup 阶段**: 调用 `AILib.setup(executor)`。
3. **接管回调**: `AILib` 将自身设置为 `executor.llm_callback`。
4. **流量闭环**: 之后所有的行为描述行 (`@~`)、`llm` 函数调用、意图分支判定，其底层执行逻辑均路由至 `ai` 模块。

---

## 2. 核心设计概念：执行场景 (Execution Scenes)

... (略) ...

### 2.1 决策映射 (Decision Mapping)
对于 `branch` 和 `loop` 场景，`ai` 模块支持自定义判定词映射。这允许开发者根据不同模型的语言偏好，灵活定义哪些回复被视为“真”或“假”。

**默认映射表：**
- **True**: `1`, `true`, `yes`, `ok`
- **False**: `0`, `false`, `no`, `fail`

---

## 3. 提示词合成与自动特性 (Prompting & Automation)

IBC-Inter 致力于在提供便利的同时，保持对 LLM 调用的绝对控制。

### 3.1 自动注入控制
开发者可以通过 `ai.set_config` 显式控制内核的自动注入行为：

```ibc-inter
import ai
# 显式关闭自动特性以获得完全原始的提示词控制
ai.set_config(url, key, model, 
    auto_type_constraint=False,   # 关闭自动类型约束注入
    auto_intent_injection=False   # 关闭自动意图注释注入
)
```

### 3.2 提示词合成流水线
开发者可以通过 `ai.set_config` 显式控制内核的自动注入行为。当特性开启时，最终的 System Prompt 采用**层级化意图合并**策略：

$$Prompt_{final} = Prompt_{scene} + Merge(Intent_{global}, Intent_{block}, Intent_{call}) + Hint_{retry} + Prompt_{type\_constraint}$$

**意图合并优先级：**
1.  **Global (全局)**: 通过 `ai.set_global_intent()` 设定，长期生效。
2.  **Block (块级)**: 通过 `intent` 关键字定义，作用于代码块。
3.  **Call (调用级)**: 通过 `@` 注释定义，单次生效。

**修饰符合并逻辑：**
-   `@+` (叠加): `Global + Block + Call`
-   `@!` (唯一): 仅 `Call` (忽略 Global 和 Block)
-   `@-` (排除): `(Global + Block) - Call`

---

## 4. API 参考

### `ai.set_config(url, key, model, **kwargs)`
配置 LLM 访问参数及内核自动化行为。
- `url`, `key`, `model`: 基础访问配置。
- `auto_type_constraint`: (bool) 是否允许内核根据变量类型自动追加格式约束。
- `auto_intent_injection`: (bool) 是否允许内核自动注入 `@` 注释。

### `ai.set_global_intent(str intent)`
设定全局意图，后续所有 LLM 调用均会携带。

### `ai.clear_global_intents()`
清空所有全局意图。

### `ai.remove_global_intent(str intent)`
移除特定的全局意图。

### `ai.get_global_intents() -> list`
获取当前生效的所有全局意图列表。

### `ai.get_current_intent_stack() -> list`
获取当前层级合并后的完整意图列表（包含全局和当前作用域的块级意图）。

### `ai.set_decision_map(dict map)`
自定义布尔判定词映射表。
- 示例：`ai.set_decision_map({"pass": "1", "reject": "0"})`

... (略) ...

## 5. Mock 仿真引擎实现

... (略) ...
- **`MOCK:RESPONSE:<content>`**: 强制返回指定的字符串内容。
- **`MOCK:TRUE/FALSE/YES/NO`**: 模拟不同的判定响应，验证决策映射。
- **`MOCK:AMBIGUOUS`**: 返回模糊文本，测试 `llmexcept` 触发。
- **`MOCK:NOISY:<content>`**: 返回带噪声的文本，测试解析器的提取能力。
- **`MOCK:MARKDOWN:<json_content>`**: 返回带代码块的 JSON，测试自动剥离能力。

