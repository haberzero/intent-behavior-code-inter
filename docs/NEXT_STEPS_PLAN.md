# IBC-Inter MVP 实现计划

> 本文档记录 IBC-Inter 第一版 MVP Demo 的实现计划。
> **[IES 2.2 更新]**: 核心未完成加固任务置顶，历史任务标注完成状态以供追踪。

---

## 🔴 核心未完成加固任务 (Critical Unfinished Tasks)

### 1.1 Mock 机制完善 (P0)
**现状**: `MOCK:FAIL/REPAIR` 前缀逻辑尚未在 `ibci_ai` 中落实。
**影响**: 无法在本地无 API 环境下测试 `llmexcept` 的闭环自愈能力。
**涉及文件**: `ibci_modules/ibci_ai/core.py`

### 1.2 ai.set_retry() 配置生效 (P1)
**现状**: 内核硬编码为 3 次重试，不响应 `ai.set_retry()` 的用户设置。
**涉及文件**: `core/runtime/interpreter/interpreter.py`

---

## 一、MVP 目标声明

### 1.1 什么是 MVP Demo

MVP (Minimum Viable Product) Demo 的目标是：

1. **功能正确** - 不是"编译通过但运行错误"，而是真正工作的核心功能
2. **亮点突出** - 清晰展示 IBC-Inter 的核心创新：behavior、意图系统、llmexcept/retry
3. **可运行** - 用户运行后能直接看到 AI 调用的实际效果

### 1.2 MVP 核心功能清单

| 功能 | 优先级 | 说明 |
|------|--------|------|
| **Behavior** | 🔴 核心 | @~...~ 语法，LLM 调用 |
| **Intent 系统** | 🔴 核心 | @, @+, @-, @! 意图修饰符 |
| **llm 函数** | 🔴 核心 | llm ... __sys__ ... __user__ ... llmend |
| **llmexcept** | 🔴 核心 | AI 逻辑判断模糊时进入 except 分支 |
| **llmretry** | 🔴 核心 | retry 重新发起 LLM 调用 |
| **DynamicHost 最小功能** | 🔴 核心 | 实例隔离、快照保存/恢复 |

### 1.3 排除在 MVP 之外的功能

以下功能在 PENDING_TASKS.md 中被标记为"高级特性"或"架构理想"，不在 MVP 范围内：

- Intent 公理化
- Behavior 公理化
- 零侵入插件注册
- dict key 类型约束
- 多值返回 Tuple
- 意图标签 (#1, #2)
- 进程级隔离

---

## 二、P0 紧急修复任务

> 这些问题在代码审计中被发现，必须在 MVP 之前修复，否则核心功能无法正常工作。

### 2.1 llmexcept 机制修复 [COMPLETED - IES 2.2]
**状态说明**: 已完成。
- **修复内容**: 在 `SideTableManager` 中实现了 `decision_maps` 侧表，并在 `interpreter.py` 中实现了 `_with_unified_fallback` 包装器。
- **验证结果**: `test_new_syntax.ibci` 运行通过。

**问题分析**：
1. **编译器侧元数据缺失 (Decision Maps)**：编译器目前没有生成 `decision_maps` 侧表。该表负责将 AI 的自然语言回复（如 "yes", "no"）映射为机器逻辑值（"1", "0"）。缺失此表导致解释器无法判定 AI 回复是否“模糊”。
2. **场景名称不匹配 (Scene Mismatch)**：编译器为 `if/while` 绑定的场景是 `IbScene.BRANCH/LOOP`，而解释器 `LLMExecutorImpl` 仅在场景名为 `"decision"` 或 `"choice"` 时才执行模糊判定逻辑。
3. **异常链路断裂**：由于上述原因，解释器将 AI 的模糊回复当作普通字符串处理（判定为 True），从未抛出 `LLMUncertaintyError`，导致 `llmexcept` 块永远不会被触发。

**修复方案 (已实施)**：
1. **Compiler**: 在 `SideTableManager` 中实现了 `decision_maps` 侧表，并在 `SemanticAnalyzer` 中为控制流语句绑定 `BRANCH/LOOP` 场景。
2. **Interpreter**: 修正了 `LLMExecutorImpl` 的场景匹配逻辑，增加了基于正则边界的关键词匹配，确保 `BRANCH/LOOP` 场景下匹配失败时抛出 `LLMUncertaintyError`。
3. **Interpreter**: 修改了 `visit_IbIf/While/For` 使用 `_with_unified_fallback` 包装 LLM 调用。
4. **Plugin System**: 按照 IES 2.2 标准重构了插件加载体系，解决了目录名与模块名不一致导致的加载失败问题，并统一了所有内置插件的导出协议。

**验证结果**：
通过 `verify_llmexcept.py` 验证成功，`MOCK:FAIL` 已能正确触发 `llmexcept` 分支。

---

### 2.2 intent_stack 类型修复 [COMPLETED - IES 2.2]
**状态说明**: 已完成。
- **修复内容**: 补齐了 `RuntimeContextImpl.restore_active_intents` 接口，并重构了序列化器以支持拓扑还原。

**问题**：`intent_stack` setter 期望 `IntentNode`，但多处传入 `list`，会导致 `TypeError`

**影响**：
- 运行时可能抛出 TypeError
- 意图栈功能失效

**涉及文件**：
- `core/runtime/interpreter/runtime_context.py`
- `core/runtime/interpreter/handlers/base_handler.py`
- `core/runtime/serialization/runtime_serializer.py`

**修复方案**：
- 将 setter 改为接受 `list` 并转换为 `IntentNode` 链表

---

### 2.3 Mock 机制完善 [PENDING - P0]
**状态**: 见顶部 1.1 章节。

**问题**：MOCK:FAIL/REPAIR 前缀完全未实现，TESTONLY 模式总是返回 "1"

**影响**：
- 无法模拟 AI 判断模糊的场景
- **llmexcept/retry 测试无法进行**

**涉及文件**：
- `ibci_modules/ibci_ai/core.py`

**修复方案**：
1. 实现 `MOCK:FAIL` - 触发 llmexcept
2. 实现 `MOCK:TRUE/FALSE` - 返回固定判定值
3. 实现 `MOCK:REPAIR` - 首次返回模糊值，重试后返回确定值

**验证标准**：
```ibc-inter
# 测试 llmexcept
if @~MOCK:FAIL 测试~:
    print("不会执行")
llmexcept:
    print("应该执行")

# 测试 llmretry
for @~MOCK:REPAIR 请判断~:
    print("循环体")
    break
```

---

## 三、P1 功能完善任务

> 这些问题影响功能正确性，但有 workaround 或仅影响边缘场景。

### 3.1 Symbol.Kind typo 修复 [COMPLETED]
已完成。统一对齐到 `SymbolKind.VARIABLE`。

---

### 3.2 ai.set_retry() 功能实现 [PENDING - P1]
**状态**: 见顶部 1.2 章节。

**问题**：重试次数配置被存储但从未读取，硬编码为 3

**影响**：用户无法通过 API 配置重试次数

**涉及文件**：
- `ibci_modules/ibci_ai/core.py`
- `core/runtime/interpreter/interpreter.py`

**修复方案**：让 `_with_unified_fallback` 读取配置的重试次数

---

## 四、MVP Example 实现

> 这些是 MVP Demo 真正需要运行的 Example。

### 4.1 基础 Behavior 示例

```ibc-inter
# basic_behavior_demo.ibci
# 目标：展示 @~...~ 语法调用 LLM

str response = @~请简单介绍一下自己~
print(response)
```

**预期结果**：调用 LLM，返回自我介绍

---

### 4.2 Intent 修饰符示例

```ibc-inter
# intent_demo.ibci
# 目标：展示 @, @+, @-, @! 意图修饰符

@+ 你是一个严肃的顾问
str advice = @~请给出一个建议~
print(advice)
```

**预期结果**：LLM 收到"严肃顾问"的上下文约束

---

### 4.3 llm 函数定义示例

```ibc-inter
# llm_function_demo.ibci
# 目标：展示 llm ... __sys__ ... __user__ ... llmend 语法

llm 翻译(str 原文, str 目标语言) -> str:
    __sys__
    你是一个专业翻译。
    __user__
    原文: $原文
    目标语言: $目标语言
llmend

str result = 翻译("Hello", "中文")
print(result)
```

**预期结果**：调用 LLM 翻译，返回中文

---

### 4.4 llmexcept + llmretry 示例 🔴 核心亮点

```ibc-inter
# llm_error_handling_demo.ibci
# 目标：展示 llmexcept 和 llmretry 机制
# 这是 IBC-Inter 的核心创新！

print("开始测试 llmexcept...")

if @~MOCK:FAIL 请判断 1+1 是否等于 2~:
    print("条件为真（AI 判断模糊）")
else:
    print("条件为假")

llmexcept:
    print("检测到 AI 判断模糊，正在重试...")
    retry "请直接回答 1 或 0，不要解释"
```

**预期结果**：
1. 第一次 AI 调用返回模糊值
2. 进入 llmexcept 分支
3. 执行 retry，重新发起调用
4. 第二次调用返回确定值

**这是 IBC-Inter 区别于其他编程语言的核心亮点！**

---

### 4.5 DynamicHost 最小功能示例

```ibc-inter
# dynamic_host_demo.ibci
# 目标：展示 DynamicHost 的实例隔离和快照恢复

host.print("主环境开始")

# 启动隔离子环境
host.run_isolated({
    "inherit_plugins": true
}, {
    host.print("子环境开始")
    host.set_var("x", 42)
    host.print("子环境设置 x = " + (str)host.get_var("x"))
})

host.print("主环境恢复")
host.print("子环境的修改没有影响主环境")
```

**预期结果**：子环境的修改被隔离，不影响主环境

---

## 五、MVP 测试验证清单

> MVP 必须通过以下测试验证：

| 测试 | 验证内容 | 通过标准 |
|------|---------|---------|
| T1 | Behavior 语法 | @~...~ 能调用 LLM 并返回结果 |
| T2 | Intent 修饰符 | @+ 能叠加意图上下文 |
| T3 | llm 函数定义 | llm ... llmend 能定义并调用 LLM 函数 |
| T4 | llmexcept 捕获 | AI 判断模糊时进入 except 分支 |
| T5 | llmretry 重试 | retry 能重新发起 LLM 调用 |
| T6 | DynamicHost 隔离 | 子环境修改不影响主环境 |
| T7 | Mock FAIL | MOCK:FAIL 能触发 llmexcept |
| T8 | Mock REPAIR | MOCK:REPAIR 能触发 retry |

---

## 六、MVP 发布检查清单

在发布 MVP Demo 之前，必须确认：

- [ ] P0 所有问题已修复
- [ ] P1 问题已记录或有 workaround
- [ ] Example 4.4 (llmexcept/retry) 能真正工作
- [ ] Mock 机制能模拟 AI 模糊判断
- [ ] DynamicHost 隔离功能正常
- [ ] README 中的快速开始指南能运行成功
- [ ] 没有"编译通过但功能错误"的 Example

---

## 七、MVP 之后

MVP 发布后，以下功能可以在后续版本中迭代：

| 功能 | 优先级 | 说明 |
|------|--------|------|
| Intent 公理化 | 中 | 更优雅的编译期设计 |
| Behavior 公理化 | 中 | 更完整的类型系统 |
| 意图标签 | 低 | 精细化意图控制 |
| 零侵入插件 | 低 | 生产环境特性 |

详见 [PENDING_TASKS.md](PENDING_TASKS.md)

---

*本文档为 IBC-Inter MVP 实现计划*
*最后更新：2026-03-25*
