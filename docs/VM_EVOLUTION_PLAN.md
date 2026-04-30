# IBCI VM 演进总规划（Master Plan）

> **文档性质**：本文档是全部 VM 相关工作的总纲。每一个 Milestone 对应一个独立的 PR，执行前后均保持测试基线绿色。  
> **基准状态**（2026-04-29）：**1011 个测试通过**；Step 1–8 全部完成；**M1 + M2 + M3a + M3b + M3c + M3d + M4 + M5a + M5b + M5c + M6 已完成**；**编译器深度清洁 Phase 1–5（C5/C6/C7/C8/C9/C10/C11/C12/C13/C14）全部完成**（CPS dispatch table 覆盖 43 个 AST 节点类型；所有显式 `fallback_visit()` 调用归零；`_vm_assign_to_target()` CPS generator helper 替代 assign_to_target 递归穿透；`IbLambdaExpr.free_vars` 编译期填充；`cell_captured_symbols` 侧表；Signal→CSE 桥已收缩为单层边界兼容包装；`node_protection` 侧表与 `bypass_protection` 参数链已彻底删除）；**fn/lambda/snapshot 类型系统重设计 D1/D2/D3 全部完成**（声明侧 `TYPE fn NAME` 废弃为 PAR_003，表达式侧 `-> TYPE` 合法化，`fn[(...)→(...)]` callable 签名标注上线；20 个 D3 专项测试）。  
> **剩余技术债**：**无**——所有 C1–C14 / L1–L4 条目已 ✅ DONE 并归档至 `docs/COMPLETED.md` §十七 / §十九 / §二十 / §二十一。`ControlSignalException` 类本体已彻底删除（仅余 `UnhandledSignal` 作为 VM 顶层未消费 Signal 的边界异常）。  
> **奠基进展**（M1 前置）：`IbCell` 原语已先行落地（`core/runtime/objects/cell.py`，纯容器、身份语义、`trace_refs()` GC 钩子就绪），单元测试 18 个，无现有路径行为变化。  
> **不阻塞规则**：每个 Milestone 在其前提 Milestone 合并后即可独立开工，不需要等待其他并行 Milestone。  
> **关联文档**：`docs/PENDING_TASKS_VM.md`（详细设计）、`docs/NEXT_STEPS.md`（近期任务）、`docs/COMPLETED.md`（已完成记录）、`docs/VM_SPEC.md`（正式 VM 规范）。

---

## 一、当前架构现状（代码层事实）

### 1.1 解释器执行模型

`core/runtime/interpreter/interpreter.py` 的 `visit()` 方法（第 755 行）是一个纯 **Python 递归 tree-walker**：

```
visit(node_uid)
  └─ _visitor_cache[node_type](node_uid, node_data)   # 分发到 Handler
       └─ visit(child_uid)   # 递归
            └─ ...
```

控制流全部依赖 Python 异常机制：

| IBCI 控制流 | Python 实现 | 代码位置 |
|-------------|-------------|----------|
| `return v` | `raise ReturnException(v)` | `stmt_handler.py:709` |
| `break` | `raise BreakException()` | `stmt_handler.py:714` |
| `continue` | `raise ContinueException()` | `stmt_handler.py:717` |
| `raise e` | `raise ThrownException(e)` | `stmt_handler.py:720` |
| llmexcept retry | Python try/except + `LLMExceptFrame.restore_snapshot()` | `stmt_handler.py:555–648` |

`LogicalCallStack`（`call_stack.py`）只是 **调试影子栈**，真实调用栈是 Python 递归栈。注释自白（`interpreter.py` 第 14 行）：
> "每一层 IBCI 调用大约消耗 4 层 Python 栈帧；必须确保 max_call_stack * 4 < sys.getrecursionlimit()"

### 1.2 作用域与闭包现状

- `ScopeImpl._parent` 链已实现词法嵌套（公理 SC-1 ✅）
- `IbDeferred`/`IbBehavior` 的自由变量（M2 后）通过 `ScopeImpl.promote_to_cell()` 提升为共享 IbCell，lambda/snapshot 统一通过 `closure: Dict[sym_uid, (name, IbCell)]` 访问  
  → 公理 SC-3/SC-4 **已实现**（M2 ✅）
- `fn`/`lambda`/`snapshot` 支持参数传递（M1 ✅）；`TYPE fn NAME = lambda: EXPR` 声明侧返回类型标注已落地
- lambda 闭包对象可自由作为高阶函数参数传递（M2 ✅）

### 1.3 意图上下文现状

- `IbIntentContext` 已公理化，`fork()/restore()` 机制完整（Step 6 ✅）
- 函数调用时 fork（`kernel.py:767–769`），快照恢复时 restore（`llm_except_frame.py`）

### 1.4 测试基线

```
python3 -m pytest tests/ -q --tb=short   # 1011 passed（2026-04-29，D1/D2/D3 fn/lambda callable 签名标注全链路落地後）
```

每个 Milestone 完成后必须以此命令验证测试不退化。

历史快照：
- 867 passed（2026-04-28，M3b + M5a 完成后）
- 926 passed（2026-04-28，M3d-prep 完成后）
- 964 passed（2026-04-29，M4 完成后）
- 996 passed（2026-04-29，M6 + Phase 1–4 完成后）
- 989 passed（2026-04-29，Phase 5 / C11/P3 完成后；3 个 TestProtectionRedirect 死代码测试删除）
- 991 passed（2026-04-29，D1/D2 完成后）
- 1011 passed（2026-04-29，D3 fn[(...)→(...)] callable 签名标注完成后）

---

## 二、总体演进路线图

```
已完成（Step 1–8 + M1 + M2 + M3a–M3d + M4 + M5a–M5c + M6 + Phase 1–5 编译器深度清洁 C5–C14）
  └─── 当前状态（基准：989 tests）
         │
         ├─── ✅ M1：fn 新语法 + IbCell（Step 12.5）                  [已完成 2026-04-28]
         │      │
         │      └─── ✅ M2：IbCell GC 根集合 + 词法作用域正式化（Step 13）[已完成 2026-04-28]
         │
         ├─── ✅ M3a：CPS 调度循环骨架（Step 9a）                      [已完成 2026-04-28]
         │      │
         │      ├─── ✅ M3b：return/break/continue 迁移到 Signal（Step 9b）[已完成 2026-04-28]
         │      │      │
         │      │      └─── ✅ M3c：llmexcept retry + intent fork 调度化（Step 9c）[已完成 2026-04-28]
         │      │
         │      └─── ✅ M3d：主执行路径切换至 VMExecutor（Step 9d）    [已完成 2026-04-28]
         │
         ├─── ✅ M4：Layer 2 多 Interpreter 并发（Step 11）            [已完成 2026-04-29]
         │
         ├─── ✅ M5a：DDG 编译器分析                                  [已完成 2026-04-28]
         ├─── ✅ M5b：LLMScheduler                                    [已完成 2026-04-28]
         └─── ✅ M5c：dispatch-before-use                             [已完成 2026-04-29]
                │
                └─── ✅ M6：可移植性参考实现 + 合规测试套件（Step 12） [已完成 2026-04-29]
                       │
                       └─── ✅ 编译器深度清洁 Phase 1–5（C5–C14）     [已完成 2026-04-29]
                              │
                              └─── ⏳ 下一功能里程碑（见下方详细规范）
```

**当前优先路径**：编译器债务清洁 Phase 1–5 全部完成（2026-04-29）。CPS dispatch table 覆盖 **43 个 AST 节点类型**，所有显式 `fallback_visit()` 调用已归零，`_vm_assign_to_target()` CPS generator helper 完全替代旧递归穿透路径，`node_protection` 侧表与 `bypass_protection` 参数链已彻底删除。VM 主路径已真正脱离 Python 递归栈依赖（除 `IbUserFunction.call()` 内部参数绑定/scope push 部分仍使用同步调用外）。

剩余暂缓项：**无**——所有清理条目已 ✅ DONE 并归档至 `docs/COMPLETED.md`。`ControlSignalException` 类本体已彻底从 `core/runtime/vm/task.py` 中删除（仅余 `UnhandledSignal`）。

---

## 三、Milestone 详细规范（已完成，见 COMPLETED.md）

所有 Milestone（M1–M6）的详细设计规范、落地的文件清单、出口契约及测试验证均已记录至 `docs/COMPLETED.md` 相关章节：

| Milestone | 内容 | COMPLETED.md 章节 |
|-----------|------|------------------|
| M1 | fn 参数化 lambda/snapshot 新语法 + IbCell 基础 | §五、§七b |
| M2 | IbCell GC 根集合 + 词法作用域正式化 | §七a |
| M3a–M3d | CPS 调度循环骨架 → 主路径切换至 VMExecutor | §十、§十一、§十二 |
| M4 | Layer 2 多 Interpreter 并发 | §十三 |
| M5a–M5c | DDG 编译器分析 + LLMScheduler + dispatch-before-use | §十四、§十五 |
| M6 | 可移植性参考实现 + 合规测试套件 + 编译器深度清洁 Phase 1–5 | §十六 |
| D1/D2/D3 | fn/lambda/snapshot 类型系统重设计 | §二十二 |

**下一步方向**：见 `docs/NEXT_STEPS.md`；中长期待实现任务见 `docs/PENDING_TASKS.md` 与 `docs/PENDING_TASKS_VM.md`（VM 架构长期设想）。
