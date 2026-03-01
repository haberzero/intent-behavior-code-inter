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

为了实现自然语言与程序逻辑的精确对齐，`ai` 模块引入了“场景”概念。解释器在执行不同语法节点时，会向 `ai` 模块传递特定的场景标识：

| 场景标识 (Scene) | 触发语法节点 | 默认行为逻辑 | 期望输出 |
| :--- | :--- | :--- | :--- |
| `general` | `llm` 函数调用 | 自由对话，执行复杂自然语言任务 | 字符串 |
| `branch` | `if`, `elif` 中的 `@~` | 逻辑判定，分析内容是否符合条件 | `1` 或 `0` |
| `loop` | `for`, `while` 中的 `@~` | 循环控制，判断是否应继续迭代 | `1` 或 `0` |

---

## 3. 提示词合成流水线 (Prompt Synthesis Pipeline)

当解释器请求一次 LLM 调用时，`ai` 模块会启动一套结构化的提示词合成流水线，最终生成发送给模型的 `System Prompt`：

### 3.1 系统提示词组合算法
$$Prompt_{final} = Prompt_{scene} + Intent_{active} + Hint_{retry} + Prompt_{type\_constraint}$$

1. **场景基础 (`Prompt_{scene}`)**: 根据当前是分支、循环还是普通函数，选择对应的 `ai.set_xxx_prompt` 配置。
2. **意图增强 (`Intent_{active}`)**: 如果当前代码块被 `@ 意图内容` 装饰，解释器会从 `IntentStack` 中提取内容并注入。
3. **动态修复 (`Hint_{retry}`)**: 如果是在 `llmexcept` 后的 `retry` 流程中，会注入 `ai.set_retry_hint` 的内容。
4. **类型约束 (`Prompt_{type_constraint}`)**: 如果是 `llm` 函数且定义了 `-> int/list/dict` 等返回类型，会追加格式化指令。

---

## 4. 状态管理与重试逻辑 (State & Retry)

`ai` 模块维护了一个临时的“故障上下文”：
- **Retry Hint**: 当程序捕获 `llmexcept` 并设置提示词后，该状态会保存在模块内，直到下一次 LLM 调用成功后被清除。
- **温度自适应**: 
  - 对于 `branch` 和 `loop` 场景，`temperature` 固定为 `0.1` 以确保判定的确定性。
  - 对于 `general` 场景，`temperature` 默认为 `0.7` 以保持回复的灵活性。

---

## 5. Mock 仿真引擎实现

在 `url` 为 `"TESTONLY"` 时，`ai` 模块会激活其内部的仿真引擎，该引擎通过对 `user_prompt` 的模式匹配来模拟 LLM 行为：
- **`MOCK:RESPONSE:<content>`**: 强制返回指定的字符串内容（支持 JSON 格式字符串）。
- **`MOCK:TRUE/FALSE`**: 在判定场景下强制返回 `1` 或 `0`。
- **`MOCK:FAIL`**: 模拟返回不明确的结果，触发 `llmexcept`。
- **修复验证**: 检测到 `MOCK:REPAIR` 且存在 `retry_hint` 时，自动返回成功结果，用于测试重试链路。
