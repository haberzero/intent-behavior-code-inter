# 协程与迭代器设计

> 本文档记录 IBCI 协程/迭代器相关的架构分析，目前搁置等待多模态功能完善后再推进。面向需要了解协程层设计方向的开发者。当前实现状态以代码为准。

---

## 一、搁置原因

协程相关功能（L3 协程层、async/await/yield）在当前阶段不进行开发。主要原因：

1. `dispatch_eager` + `LLMFuture` 覆盖最主要的异步 LLM 需求，用户无需显式写 async/await
2. 协程层需要 VM 从"单任务调度器"升级为"多任务挂起/恢复"架构，跨五层改动（lexer/parser/semantic/vm/runtime）
3. 缺乏明确的用户需求来源——当前 IBCI 用户脚本都是线性流程 + LLM 调用
4. 当前优先级：多模态功能的完善和定义

---

## 二、现有基础设施分析（可复用）

### 2.1 CPS 风格调度循环

- `VMExecutor`（`core/runtime/vm/vm_executor.py`）：所有语句执行已转为 VM 帧栈驱动，递归 visit 已消除
- 这是协程化的**必要前置**——无 CPS 帧栈则无法实现 yield 点保存/恢复

### 2.2 ControlSignal 枚举

- 位置：`core/runtime/vm/task.py` 的 `ControlSignal` 枚举
- 包含 `break` / `continue` / `return` / `llm_uncertain` 信号类型
- 可扩展：新增 `YIELD` 信号类型用于协程挂起

### 2.3 dispatch_eager + LLMFuture

- 位置：`core/runtime/vm/handlers/` 包中的赋值上下文调度逻辑
- "异步提交 → 延迟解析"模式可行
- 后台 LLM 请求 + 使用点阻塞解引用

---

## 三、协程层（L3）设计维度

### 3.1 调度器架构

- **当前**：`VMExecutor` 是单根任务（`vm.run(uid)` 一次执行完毕）
- **需要**：多任务队列 + `Signal.YIELD` 挂起语义
- **挑战**：如何在 yield 点保存完整的执行上下文（帧栈 + 局部变量 + intent context）

### 3.2 语言层关键字

- `async` / `await` / `yield` 均不在现有 KEYWORDS 表中
- 需设计语法与对应的类型系统支持
- 涉及 lexer token 新增 + parser 语法规则 + semantic pass 处理 + VM handler

### 3.3 快照协议对齐

- **问题**：协程挂起时如何保存 intent_context 栈 + llmexcept 帧栈
- **现状**：`try_deep_clone` 仅服务 llmexcept retry，不覆盖协程 yield 点
- **需要**：设计"协程帧快照"协议，与现有 llmexcept snapshot 兼容

---

## 四、被阻塞的子项

| 编号 | 标题 | 依赖 L3 的原因 |
|------|------|---------------|
| 1 | `host.run_isolated()` 返回值改进 | 当前返回 `IbObject`/`bool`，需要协程句柄才能实现"异步等待子脚本完成" |
| 2 | `ReceiveMode` 枚举演进 | 需要 yield/resume 语义支持流式接收模式 |

---

## 五、迭代器协议扩展方向

### 5.1 当前迭代器实现

- `for x in collection:` 通过 `__iter__` / `__next__` 协议实现
- 内置类型（list、dict、str）通过 axiom 提供迭代能力
- 用户类尚无自定义迭代器支持

### 5.2 未来方向

- **用户类 `__iter__` / `__next__`**：允许用户类实例参与 `for ... in ...` 循环
- **生成器函数（generator function）**：`yield` 关键字使函数变为生成器
- **与协程的关系**：生成器是协程的子集；如果实现了协程，生成器自然可行

### 5.3 与多模态的关系

- 流式多模态响应（如逐帧视频处理）需要 iterator/generator 模式
- 当前决策：多模态采用同步执行语义（完整获取后返回），不依赖流式
- 流式处理属于 L3 协程层功能，搁置

---

## 六、恢复条件

当以下条件满足时，可考虑恢复协程层开发：

1. 多模态子系统稳定实现并通过充分测试
2. 出现明确的用户需求场景（如需要同时等待多个独立 LLM 调用）
3. `dispatch_eager` + `LLMFuture` 模式被证明不足以覆盖需求
4. 团队有足够带宽做跨五层（lexer → runtime）的大规模改动

---

恢复时应先重新核查 §二 中的基础设施现状是否仍有效。
