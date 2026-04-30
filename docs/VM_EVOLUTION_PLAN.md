# IBCI VM 演进总规划（Master Plan）

> **文档性质**：本文档是全部 VM 相关工作的总纲。每一个 Milestone 对应一个独立的 PR，执行前后均保持测试基线绿色。  
> **基准状态**（2026-04-29）：**1011 个测试通过**；Step 1–8 全部完成；**M1 + M2 + M3a + M3b + M3c + M3d + M4 + M5a + M5b + M5c + M6 已完成**；**编译器深度清洁 Phase 1–5（C5/C6/C7/C8/C9/C10/C11/C12/C13/C14）全部完成**（CPS dispatch table 覆盖 43 个 AST 节点类型；所有显式 `fallback_visit()` 调用归零；`_vm_assign_to_target()` CPS generator helper 替代 assign_to_target 递归穿透；`IbLambdaExpr.free_vars` 编译期填充；`cell_captured_symbols` 侧表；Signal→CSE 桥已收缩为单层边界兼容包装；`node_protection` 侧表与 `bypass_protection` 参数链已彻底删除）；**fn/lambda/snapshot 类型系统重设计 D1/D2/D3 全部完成**（声明侧 `TYPE fn NAME` 废弃为 PAR_003，表达式侧 `-> TYPE` 合法化，`fn[(...)→(...)]` callable 签名标注上线；20 个 D3 专项测试）。  
> **剩余技术债**：**无**——所有 C1–C14 / L1–L4 条目已 ✅ DONE 并归档至 `docs/COMPLETED.md` §十七 / §十九 / §二十 / §二十一。`ControlSignalException` 类本体已彻底删除（仅余 `UnhandledSignal` 作为 VM 顶层未消费 Signal 的边界异常）。  
> **奠基进展**（M1 前置）：`IbCell` 原语已先行落地（`core/runtime/objects/cell.py`，纯容器、身份语义、`trace_refs()` GC 钩子就绪），单元测试 18 个，无现有路径行为变化。  
> **不阻塞规则**：每个 Milestone 在其前提 Milestone 合并后即可独立开工，不需要等待其他并行 Milestone。  
> **关联文档**：`docs/PENDING_TASKS_VM.md`（详细设计）、`docs/NEXT_STEPS.md`（近期任务）、`docs/COMPLETED.md`（已完成记录）、`docs/VM_SPEC.md`（正式 VM 规范）。

---

## 一、当前架构现状（代码层事实）

### 1.1 解释器执行模型 ✅ M3a–M3d 已切换主路径至 VMExecutor

`Interpreter.execute_module()` 与 `IbUserFunction.call()` 当前均通过 **VMExecutor.run_body()** 驱动 CPS 调度循环执行（`core/runtime/interpreter/interpreter.py` + `core/runtime/objects/kernel.py`）。CPS dispatch table 覆盖 43 个 AST 节点类型，所有显式 `fallback_visit()` 调用归零，控制流通过 `Signal(kind, value)` 数据对象沿生成器返回值传播。

```
execute_module(uid)
  └─ vm.run_body(body)              # CPS 主路径
       └─ for stmt in body:
            generator = handler(stmt)
            for signal in generator:    # CPS 调度循环
                ...
```

控制流不再依赖 Python 异常传播（C5 落地后 `ControlSignalException` 类已彻底删除，仅余 `UnhandledSignal` 作为 VM 顶层未消费 Signal 的边界异常）：

| IBCI 控制流 | 当前实现 | 代码位置 |
|-------------|----------|----------|
| `return v` / `break` / `continue` | `Signal(kind, value)` 沿生成器返回值传播 | `core/runtime/vm/task.py:Signal` |
| `raise e` | `Signal(THROW, exc)` | 同上 |
| llmexcept retry | `vm_handle_IbLLMExceptionalStmt` 内 CPS 循环 + `LLMExceptFrame.restore_snapshot()` | `handlers.py` |

**剩余 Python 同步路径（非主线债务）**：`IbUserFunction.call()` 内部的参数绑定与 scope push/pop 仍为同步 Python 调用；该路径不参与 IBCI 控制流，对快照/并发语义无影响。早期注释自白（"每一层 IBCI 调用约 4 层 Python 栈帧"）反映的是 M3 之前的状态，当前主路径已不再受递归栈深度直接限制。

### 1.2 作用域与闭包现状

- `ScopeImpl._parent` 链已实现词法嵌套（公理 SC-1 ✅）
- `IbDeferred`/`IbBehavior` 的自由变量（M2 后）通过 `ScopeImpl.promote_to_cell()` 提升为共享 IbCell，lambda/snapshot 统一通过 `closure: Dict[sym_uid, (name, IbCell)]` 访问  
  → 公理 SC-3/SC-4 **已实现**（M2 ✅）
- `fn`/`lambda`/`snapshot` 支持参数传递（M1 ✅）
- D1/D2（2026-04-29）：声明侧 `TYPE fn NAME = lambda: EXPR` 已废弃（产生 PAR_003），表达式侧 `fn f = lambda -> TYPE: EXPR` / `snapshot -> TYPE: EXPR` 合法化
- D3（2026-04-29）：`fn[(int,str)->bool]` callable 签名标注全链路落地（`IbCallableType` AST 节点 + `CallableSigSpec(FuncSpec)` + 解析器/语义匹配）
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
| M1 | fn 参数化 lambda/snapshot 新语法 + IbCell 基础 | §六 |
| M2 | IbCell GC 根集合 + 词法作用域正式化 | §七 |
| M3a | CPS 调度循环骨架 | §十 |
| M3b | 控制信号数据化 (Signal) | §十一 |
| M5a | DDG 编译期分析（BehaviorDependencyAnalyzer） | §十二 |
| M3c | IbLLMExceptionalStmt CPS 调度化 | §十三 |
| M5b | LLMScheduler / LLMFuture | §十四 |
| M3d-prep | 扩展 CPS handler 覆盖 | §十五 |
| M3d + M5c | 主路径切换 + LLM dispatch-before-use | §十六 |
| 轻量代码债务清理（L1/L2 + C1/C2/C3/C4 + C10/C13） | — | §十七 |
| M4 | Layer 2 多 Interpreter 并发 | §十八 |
| M6 + Phase 1 | 可移植性参考实现 + 合规测试套件 + 轻量债务清理 | §十九 |
| 编译器深度清洁 Phase 2–5（C5–C14） | CPS 全链路 + node_protection 侧表删除 | §二十 |
| URGENT_ISSUES / BUG_REPORTS / DEFERRED_CLEANUP 历史归档 | — | §二十一 |
| D1/D2/D3 | fn/lambda/snapshot 类型系统重设计（声明侧→表达式侧反转 + callable 签名） | §二十二 |

**下一步方向**：见 `docs/NEXT_STEPS.md`；中长期待实现任务见 `docs/PENDING_TASKS.md` 与 `docs/PENDING_TASKS_VM.md`（VM 架构长期设想）。
