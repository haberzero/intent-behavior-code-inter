# IBC-Inter 标准库模块规范 - idbg (v1.0 - 深度架构版)

`idbg` (Intent Debugger) 模块是 IBC-Inter 的内省与调试核心。它允许程序在运行过程中对自身进行快照分析，提供了对变量作用域、LLM 调用流以及解释器环境的全面观测能力。

---

## 1. 架构集成：ServiceContext 钩子

`idbg` 模块通过 IBC-Inter 的模块化注入系统深度嵌入解释器环境。

### 1.1 注入机制 (Injection)
当 `import idbg` 时，`ModuleLoader` 实例化 `IDbgLib` 并在其 `setup()` 阶段注入 `ServiceContext`：
- **`ServiceContext`**: 是一个持有 `Interpreter`、`RuntimeContext` 和 `LLMExecutor` 实例引用的容器。
- **只读钩子**: `idbg` 利用这些引用进行只读的数据提取，不干预原始执行流程。

---

## 2. 核心算法：作用域深度回溯 (Scope Traversal)

`idbg.vars()` 不仅仅返回当前作用域的变量，它依赖于解释器内核实现的变量快照机制。该算法已下沉至内核的 `IStateReader` 接口实现中。

### 2.1 遍历过程 (Traversal Pipeline)
1. **初始化**: 创建一个空的 `all_symbols` 汇总字典。
2. **栈顶开始**: 从 `RuntimeContext.current_scope` 开始向下（向外）遍历父作用域链。
3. **名称冲突处理 (Shadowing)**: 
   - 对于每个作用域，获取当前层级的所有变量。
   - 只有当变量名在汇总字典中**不存在**时，才将其加入。这保证了内层变量（遮蔽者）会优先于外层变量（被遮蔽者）呈现。
4. **终点**: 到达 `global_scope` 后停止回溯。
5. **数据导出**: 按照类型导出矩阵对 Python 对象进行过滤和映射。

---

## 3. 数据映射与边界控制 (Cross-Language Mapping)

由于 `idbg` 运行在 Python 宿主环境与 `ibci` 虚拟机之间，它必须严格管理跨语言边界的数据类型映射，防止底层复杂对象（如 AST 节点、类定义）泄露到语言层导致崩溃。

### 3.1 类型导出矩阵 (Type Export Matrix)
| Python 类型 | 映射到 ibci 类型 | 过滤策略 |
| :--- | :--- | :--- |
| `int` | `int` | 允许 |
| `float` | `float` | 允许 |
| `str` | `str` | 允许 |
| `bool` | `bool` | 允许 |
| `list` | `list` | 允许（递归保留） |
| `dict` | `dict` | 允许（递归保留） |
| `None` | `None` | 允许 |
| `ClassInstance` | `ClassInstance` | **允许** (支持属性内省) |
| `FunctionDef`, `LLMFunctionDef` | N/A | **过滤** (防止执行流混乱) |
| `Module`, `IDbgLib` | N/A | **过滤** (防止循环内省) |
| `Callable` | N/A | **过滤** (防止非法调用) |

---

## 4. 调用流观测设计 (Observability Design)

`idbg.last_llm()` 的数据来源于 `LLMExecutor` 内部的实时捕获器。

### 4.1 捕获器结构 (Last Call Buffer)
每当 LLM 请求完成，`LLMExecutor` 会更新其内部的 `last_call_info` 缓冲区。该缓冲区存储了：
- **Prompt 快照**: 存储的是经过所有变量插值、意图增强、重试修复指令拼接后的**最终文本**。
- **元数据 (Metadata)**: 区分该调用是来自命名的 `LLMFunctionDef` 还是匿名的 `BehaviorExpr`。

---

## 5. 解释器环境快照 (Environment Snapshot)

`idbg.env()` 通过直接访问 `Interpreter` 实例的内省能力来提供环境快照：
- **`instruction_count`**: 每一个 AST 节点的 `visit` 都会触发该计数自增，能够反映真实的逻辑复杂度。
- **`call_stack_depth`**: 当前函数调用的嵌套深度。
- **`active_intents`**: 这是从 `RuntimeContext` 的意图栈中实时提取的，反映了当前 LLM 调用在这一时刻所受到的所有上下文约束。

---

## 6. 对象内省 (Object Introspection)

针对 IBC-Inter 新增的类系统，`idbg` 提供了专用的内省接口。

### 6.1 `idbg.fields(obj)`

该函数允许开发者穿透类实例的封装，直接获取其内部存储的字段。

- **输入**: 任意 `ClassInstance`。
- **返回**: 包含所有属性名称与当前值的 `dict`。
- **用途**: 调试 `__init__` 初始化逻辑或类方法对状态的修改。
