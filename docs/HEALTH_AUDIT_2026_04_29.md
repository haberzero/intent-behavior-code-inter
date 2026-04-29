# IBC-Inter 代码仓库健康体检报告

**体检日期**：2026-04-29  
**基线**：989 测试全部通过  
**代码规模**：`core` 30,097 行 / `tests` 12,085 行 / `ibci_modules` 30 个 .py  
**体检范围**：架构地基、内核公理层、编译器、运行时 VM、测试覆盖、死代码、注释健康度、跨层耦合

---

## 总体结论

**内核稳定性：高。**

公理化（Axiom）层、SpecRegistry、KernelRegistry seal 机制都已达到生产成熟度。C1–C14 / L1–L4 等技术债全部清零，VM CPS 主路径切换完成、控制信号已完全数据化、`ControlSignalException` 类彻底删除，`node_protection` 侧表 + `bypass_protection` 参数链全链路消除。

但仍有若干隐患值得在"内核健康优先"的优先级下尽快处理。下面按"严重度 × 修复成本"分级。

---

## 🔴 优先级 1：内核稳定性隐患（建议本周内处理）

### Issue K1 — `KernelRegistry.clone()` 漏拷 `_builtin_instances` 字典

**位置**：`core/kernel/registry.py:382–403`

`clone()` 拷贝了 `_classes` / `_boxers` / `_metadata_registry` 等 13 个字段，但**遗漏了 `_int_cache` 和 `_builtin_instances`**（`__init__` 第 25/48 行定义）。

`_builtin_instances` 持有 `IntentStack` 单例（`builtin_initializer.py:407` 注册，`interpreter.py:338` 读取）。一旦 `IsolationLevel != NONE` 走 `rt_scheduler.py:84` 的 `clone()` 路径，子解释器拿到的是**空 `_builtin_instances`**，再去 `get_builtin_instance("IntentStack")` 会得到 `None`——下游若不做 None 检查就会 NPE。

`_int_cache` 是性能缓存（小整数驻留），缺失只是性能退化，不是正确性问题。

> **说明**：M4 的 `spawn_isolated` 走的是新建独立 `IBCIEngine` 路径（`engine.py:491`），不经 `clone()`，所以 M4 测试没暴露此 bug。但 isolation 子解释器路径（`rt_scheduler.spawn(isolation=ISOLATED)`）会触发。

**建议**：在 `clone()` 中补 `new_registry._builtin_instances = dict(self._builtin_instances)` 与 `new_registry._int_cache = dict(self._int_cache)`（或显式注释说明 `_int_cache` 故意不拷以避免内存倍增）。

---

### Issue K2 — `SpecRegistry.is_assignable()` 类继承链无防环递归

**位置**：`core/kernel/spec/registry.py:680–684`

```python
if isinstance(src, ClassSpec) and src.parent_name:
    parent = self.resolve(src.parent_name, src.parent_module)
    if parent and parent is not src:
        return self.is_assignable(parent, target)
```

只防"自指"（`parent is not src`），不防"A → B → A"的多步循环。artifact rehydration 阶段如果 `parent_name` 数据被损坏（或多模块命名冲突），会触发栈溢出。

**建议**：加最大深度限制（如 64）或 `visited: Set[str]`，深度超限时报内部错误而不是栈溢出。

---

### Issue K3 — `register_builtin_instance` token 形同虚设

**位置**：`core/kernel/registry.py:175–182`

```python
def register_builtin_instance(self, name: str, instance: Any, token: Any = None):
    if self._is_structure_sealed:
        raise PermissionError("...")
    self._builtin_instances[name] = instance
```

签名带了 `token: Any = None`，但**完全没调用 `_verify_kernel(token)`**。其他注册方法都会校验 token。这是设计意图与实现的不一致：要么删掉 `token` 参数（明示"sealed 之前任何代码都能注册"），要么补上 `_verify_kernel`。

**建议**：补 `_verify_kernel(token)`，`builtin_initializer.py:407` 调用方相应传入 kernel token。

---

### Issue K4 — `LLMUncertainAxiom.is_compatible` / `can_convert_from` 语义自相矛盾

**位置**：`core/kernel/axioms/primitives.py:886–889`

- `is_compatible(other_name)` → 永远 `True`（uncertain 可赋给任何类型）  
- `can_convert_from(source_type_name)` → 仅当 `source_type_name == "llm_uncertain"`

两个方法都属于"类型可达性"询问，结果方向却完全不同。生产路径只用了 `is_compatible`（`SpecRegistry.is_assignable` 第 673 行）所以暂时无害，但这是一个长期会绊倒阅读代码者的设计陷阱。

**建议**：两个方法对齐到同一个语义，或者在 docstring 里**明确说明这是故意的不对称（一个是"赋值方向"，另一个是"显式转换方向"）**。

---

## 🟡 优先级 2：架构清洁度问题（中期处理）

### Issue A1 — `core/runtime/async/llm_tasks.py` 是完全孤立的死代码

**254 行**，自述"内部草稿"＋"已知问题：`execution_context=None` NPE 风险"＋"无真正并发能力"。M5b 的真正 `dispatch_eager / resolve` 已在 `LLMExecutorImpl` 落地，且经全仓库搜索，**整个 `core.runtime.async.*` 命名空间在 production / tests / sdk / ibci_modules 中零引用**。

**建议**：直接删除 `core/runtime/async/` 整个目录。这是一份能让未来 agent 误以为"已经在做异步"的有害文档。

---

### Issue A2 — 旧递归 visit 路径中三个控制流 handler 是死代码

**位置**：`core/runtime/interpreter/handlers/stmt_handler.py:706–715`

用 `sys.settrace` 仪器化跑完整 989 测试集，旧 `visit_X` handler 中只有 5 个真正被触发：

| Handler | 触发次数 |
|---|---|
| `visit_IbName` | 121 |
| `visit_IbBinOp` | 78 |
| `visit_IbConstant` | 60 |
| `visit_IbCompare` | 4 |
| `visit_IbCall` | 2 |

`visit_IbReturn` / `visit_IbBreak` / `visit_IbContinue` **零触发**。它们是 C5/C6 完成后的遗孤——VM CPS 路径的 `vm_handle_IbReturn/Break/Continue` 已 100% 接管。

配套的"兼容性保留"dead branch：
- `interpreter.py:598–600`：`except (ReturnException, BreakException, ContinueException):` 块
- `kernel.py:844–846`：`except ReturnException as e:  # 兼容性保留` 块

**建议**：三步走（每步独立 PR + 测试）：
1. 删除 `stmt_handler.visit_IbReturn/IbBreak/IbContinue`，让旧 visit 派发表的对应槽位为 None
2. 删除 `interpreter.py:598–600`、`kernel.py:844–846` 的兼容 except 块
3. 评估能否从 `core/runtime/exceptions.py` 删除 `ReturnException/BreakException/ContinueException` 类本身（`ThrownException` 用于用户 `raise` 语句，需保留）

---

### Issue A3 — VM 接口与子包头部 docstring 全部停留在"M3a 阶段"

多处过时 docstring 把已过去的 M3b/M3c/M3d 写成未来时态：

| 文件 | 问题行 | 过时内容 |
|---|---|---|
| `core/runtime/vm/__init__.py` | 16–27 | "M3a 阶段实现采用…M3b 将…M3c 将…M3d 将…VMExecutor 是…并行路径，未实现节点回退…（M3a 范围内）" |
| `core/runtime/vm/vm_executor.py` | 1–29 | "VM 调度循环主类（M3a + M3b）" / "M3d 阶段才把全部节点纳入 CPS" |
| `core/base/interfaces.py` | 172, 183, 199–200 | "M3a 骨架；M3b/M3c/M3d 将逐步扩展" / "M3d 阶段会把 Interpreter.visit() 主路径改为本协议驱动" |

代码已是 Phase 5 完成状态（CPS dispatch 覆盖 43 节点），但接口注释还停留在 M3a。新人读到会被严重误导——以为代码处于"原型并行运行期"，实际上已完全成熟。

**建议**：一次性清扫这 3 个文件的头部注释，反映"VM CPS 是主路径；旧递归 visit 仅在子表达式求值 / IntentTemplate / LLMExceptFrame 重试 driver 等收敛清单上保留"的事实。可以列出哪些场景仍走旧 visit，让边界清晰。

---

### Issue A4 — `str + llm_uncertain` 显式放行是已知设计债，但无主归属

**位置**：`core/runtime/objects/builtins.py:326` + `core/kernel/axioms/primitives.py:400`

两处对称的 `# TODO(future): 当 IBCI 完善 try/except 机制后...`——这是 `docs/KNOWN_LIMITS.md` §八已记录的过渡期妥协（避免 `print("结果: " + r)` 在 LLM 失败后立刻崩溃）。

不是 bug，但应当跟 `docs/NEXT_STEPS.md` "选项 1：try/except 与 IBCI 错误模型对齐" 绑定为同一里程碑的子任务，免得它在代码里"无主漂流"。

**建议**：在 `docs/NEXT_STEPS.md` 选项 1 下显式列出这两处 TODO 作为关联交付项，让它有明确归属。

---

### Issue A5 — `SpecRegistry.resolve_specialization()` 不缓存返回值

**位置**：`core/kernel/spec/registry.py:695–737`

每次 `list[int]` / `dict[str,int]` 等参数化类型解析都创建一个**新的 spec 对象**，不写回 `_specs` 缓存。同一程序中同一个泛型实例化出现 N 次，就会有 N 个不相等的 spec 对象实例。

影响：
1. 大型程序中内存持续增长（spec 实例不被复用）
2. 任何依赖 `is` 比较 spec 的优化都失效
3. 与 `GENERICS_CONTAINER_ISSUES.md` §2 已记录的 "axiom 方法引导不全" 形成耦合——每次新建都要再次 bootstrap

**建议**：把 `resolve_specialization` 改为 "lookup-or-create"——成功创建后立刻 `self.register(result)`，下次同名查 `_specs` 直接命中。这同时也修复 `GENERICS_CONTAINER_ISSUES.md` §2。

---

## 🟢 优先级 3：低优清理与跟踪项

### Issue L1 — `llm_except_frame.py` 两处 TODO 无主挂起

**位置**：`core/runtime/interpreter/llm_except_frame.py:368, 413`

- 第 368 行（中优）：`reset_for_retry` 是否清 `last_error`（追踪重试历史）
- 第 413 行（低优）：`LLMExceptFrameStack` 是否要最大嵌套深度限制

都是 nice-to-have，不影响核心路径正确性。

**建议**：要么实现，要么把它们从代码里搬到 `docs/PENDING_TASKS.md`，避免代码里"漂着"无主 TODO。

---

### Issue L2 — `idbg/core.py:267` 等待内核暴露 side_table 接口

**位置**：`ibci_modules/ibci_idbg/core.py:267`

`# TODO: 需要内核暴露 side_table 接口后实现`——这是 idbg 模块的能力缺口。

**建议**：在 `docs/PENDING_TASKS.md` 加一条"扩展 idbg：暴露 side_table 接口"。

---

### Issue L3 — `compiler/scheduler.py:470` 显式引入原则的临时妥协

**位置**：`core/compiler/scheduler.py:470`

注释明确说"临时妥协：允许未 import 时使用 `ai.xxx`"，这是显式引入原则 Phase 1 的遗留例外。

**建议**：与 `docs/NEXT_STEPS.md` 选项 4（Plugin 系统 Phase 3/4）绑定，一同处理。

---

### Issue L4 — `docs/COMPLETED.md` §16.3 等历史描述已不准确

`docs/COMPLETED.md:964` 描述 "Signal vs Exception 分层" 时仍说 "包装成 `ControlSignalException` 跨越 Python 调用栈"。Phase 5 完成后 CSE 类已删除，包装的实际是 `UnhandledSignal`。

**建议**：保留原文（历史档案不应篡改），在该段落末尾追加一行"（2026-04-29 后：CSE 已被 `UnhandledSignal` 完全取代）"小提示即可。

---

## 📋 可执行任务总清单

| # | 任务 | 风险 | 工作量 | 类别 |
|---|------|------|-------|------|
| 1 | 修复 `KernelRegistry.clone()` 漏拷 `_builtin_instances` | 低 | 5 行代码 + 1 测试 | 🔴 K1 |
| 2 | `SpecRegistry.is_assignable` 加深度限制或 visited set | 低 | 3 行代码 + 1 测试 | 🔴 K2 |
| 3 | `register_builtin_instance` 补 `_verify_kernel(token)` | 低 | 1 行 + 1 处调用方更新 | 🔴 K3 |
| 4 | `LLMUncertainAxiom` 两个方法对齐（或 docstring 明确不对称） | 极低 | 注释或代码二选一 | 🔴 K4 |
| 5 | 删除 `core/runtime/async/` 整个孤立目录 | 极低 | 删除 + 跑测试 | 🟡 A1 |
| 6 | 删除 `stmt_handler.visit_IbReturn/IbBreak/IbContinue` 三个 dead handler | 低（仪器化已确认零调用）| 三步 PR | 🟡 A2 |
| 7 | 清扫 `vm/__init__.py` / `vm_executor.py` / `base/interfaces.py` 头部 M3a 过时 docstring | 极低 | 纯注释更新 | 🟡 A3 |
| 8 | `str + llm_uncertain` TODO 与 NEXT_STEPS 选项 1 显式绑定 | 极低 | 纯文档 | 🟡 A4 |
| 9 | `resolve_specialization` 改为 lookup-or-create + 写回 `_specs` | 中（需要回归 e2e）| ~10 行 + 测试 | 🟡 A5 |
| 10 | `llm_except_frame.py` 两处 TODO：实现或迁出代码 | 极低 | 决策即可 | 🟢 L1 |
| 11 | `idbg:267` TODO 迁到 PENDING_TASKS.md | 极低 | 纯文档 | 🟢 L2 |
| 12 | `scheduler.py:470` 临时妥协与 Plugin Phase 3/4 绑定 | 极低 | 纯文档 | 🟢 L3 |

> **如果只能挑三件事做，建议：1（K1 clone）、2（K2 防环）、5（A1 删 async/）**。前两个是真正的 latent bug，第三个释放 254 行迷惑性死代码。

---

## 🔬 内核体检亮点（值得肯定的部分）

以下是体检中**特别欣赏**的设计与落地，它们代表了本项目在内核工程质量上的显著优势：

### ✅ 亮点 1：公理化分层极其干净

`primitives.py`（1340 行）涵盖 17 种基础类型，`is_dynamic=False` 的具体类型（`VoidAxiom` / `CallableAxiom` / `DeferredAxiom` / `BehaviorAxiom`）替代了早期 `DynamicAxiom` 妥协。注释中多次强调"非 any 妥协"，说明设计意图清晰、有主见。

### ✅ 亮点 2：CPS 调度的工程纪律

`vm/handlers.py`（1648 行）实现 43 个 generator handler，无显式 fallback；通过 `Signal(kind, value)` 数据对象 + `gen.send` 数据化传递控制流，配合 `IbCell` / `free_vars` / `cell_captured_symbols` 编译期填充，把"运行时作用域链扫描"完全消灭。这是教科书级别的"消除运行时反射"重构。

### ✅ 亮点 3：Token + Seal 两段式安全模型

`KernelRegistry` 用结构封印 + 类封印 + `kernel_token` 三道闸，`spec/registry.py` 在 axiom 注册阶段 `_bootstrap_axiom_methods` 一次性绑定。除上文 K1/K3 两个补丁，整体设计可以承担生产负载。

### ✅ 亮点 4：测试金字塔健康

989 测试覆盖 unit（7 文件）/ e2e（13）/ compliance（3，VM 规范合规），外加用 `sys.settrace` 验证旧路径覆盖度低于预期——这种"自我反省式测试覆盖分析"在多数项目中都没有。

### ✅ 亮点 5：侧表序列化完备性

`CompilationResult` 的 5 个侧表（`node_to_symbol` / `node_to_type` / `node_is_deferred` / `node_deferred_mode` / `node_to_loc`）在 `serializer.py` 全部双向覆盖，artifact 加载后通过 `ec.get_side_table()` 无缝桥接。

### ✅ 亮点 6：VM 合规套件

M6 的 `tests/compliance/`（32 测试）+ `docs/VM_SPEC.md` 是真正的 IBCI 标准化资产——任意第二实现（Rust / Go 后端）都能通过这套测试验证行为合规性。这是非常可观的工程护城河。

---

## 📐 架构层面的长期洞察

### 洞察 1：双轨 visit() 现状已稳定收敛，需要给它一个正式名字

旧递归 `visit()` 路径不会消失——`@~...~` 中 `$var` 字符串内插、`IbIntent.resolve()`、`LLMExceptFrame` 重试 driver、helper 节点 fallback，这几处永远有需求。但它已经从"主执行路径"降级为"子表达式求值路径"。

**建议**：在 `docs/VM_SPEC.md` 里给这个分工命名，例如：
- **VM CPS Path**：处理任何会产生 Signal、跨函数边界、或参与 LLMScheduler 调度的节点
- **Expression Eval Path**：处理同步纯计算子表达式（`IbName` / `IbBinOp` / `IbConstant` 等）

有名字的边界会让未来的贡献者不再困惑"该把新 handler 加到哪一边"。

---

### 洞察 2：内核已经准备好接受 M7（多目标语言后端）的挑战

从公理层 / spec / serialization 的完备度判断，**只要补上前述 K1–K4 四个补丁**，再加上把 `node_protection` 这种私有侧表彻底从公开规范里清掉（已完成），任意第二实现（Rust / Go）都能通过 `compliance/` 套件验证。这是非常可观的工程资产。

---

### 洞察 3：`fn` 重设计是下一个影响用户体验的关键里程碑

从 `docs/KNOWN_LIMITS.md` §三 和 `FUNC_DESIGN_NOTES.md` 的分析来看，`fn` 类型推断在以下路径上有不一致：
- 跨场景调用（fn 持有的对象内部触发 `@~...~`）
- 与 OOP `__call__` 协议解析
- 闭包捕获 + lambda 互通

这不是技术债而是设计欠债——解决它需要在语言规范层先明确 `fn` 与 `callable` / `deferred` 的类型层次，再联动编译器 + 运行时一起改。建议作为"选项 1：Semantic 用户面问题修复"的核心子任务单独设计方案，不要与 `try/except` 重构混在一起做。

---

*体检执行者：Copilot Agent · 体检周期：单次全量 · 下次建议体检时机：M7 或 Semantic 主要问题修复落地后*
