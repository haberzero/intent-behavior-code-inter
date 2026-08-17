# 原生宿主绑定（Native Host Binding）

> 本文档描述 IBCI 用户层原生绑定 Python 内容的**远期架构**：宿主导入语法、用户 IBCI
> 类型/协议对裸 Python 内容的绑定、插件体系的重构走向，以及内核 IBCI 自举与
> 缓存/JIT 的规划。面向需要理解"抛弃 Python 侧 `_spec.py` 插件思路"这一方向的
> 架构演进的设计者。
>
> 本文档是 `tasks_docs/ROADMAP_NATIVE_BINDING.md` §三【远期愿景】F0-F5 的**设计
> 底稿**（F0 产物）。当前代码状态对应 R 期（近期主线）已完成、F 段尚未开始。

---

## 一、为什么需要原生宿主绑定

当前 IBCI 暴露 Python 内容给用户的方式是 **Python 侧手写 `_spec.py` 插件**：
用户在 Python 侧定义实现 + `__ibcext_vtable__()` 契约，IBCI 侧经 `import` 包装为
模块。这带来几个结构性限制：

1. **双语言契约割裂**：契约（`_spec.py`）与实现（`.py`）分居两个文件、两种形态，
   用户在 Python 侧维护"给 IBCI 看的接口"，而非在 IBCI 侧声明"我要绑定什么"。
2. **`import` 受限于已注册包**：裸 Python 模块/类/函数无法直接导入并绑定——
   `import X` 只认 InterOp 注册包（需 `_spec.py`）或 IBCI artifact 模块。
3. **`impl`/协议目标受限**：协议与 retroactive implementation 目标须为本模块
   用户类；宿主导入类型（如 `python.import("pkg")` 得到的类型）无法作为协议/
   `impl` 目标，语言级能力契约无法扩展到宿主内容。

原生宿主绑定的目标：**用户在 IBCI 侧声明式导入裸 Python 内容，并显式绑定到
IBCI 类型/协议/方法**——把"暴露 Python 给 IBCI"从 Python 侧契约改为 IBCI 侧声明。

---

## 二、现状实证（已核实的架构事实）

### 2.1 值/宿主边界：`box` 已能包装任意 Python 对象

`core/runtime/bootstrapper.py` `box()`（经 `KernelRegistry.box` 委托）：

- `IbObject` 原样返回；`None → get_none()`；`Waitable` 透传（异步句柄不装箱）；
  `__IBCI_UNCERTAIN_LITERAL__ → llm_uncertain`。
- `callable(val)` → `IbNativeFunction(val, unbox_args=True, ib_class=callable)`。
- 其它 → `IbNativeObject(val, ib_class=Object)`（vtable 空，成员对 IBCI 不可见）。

**结论：IBCI 已能将任意 Python 对象/可调用对象作为一等值持有与传递。**

### 2.2 成员门控：`IbNativeObject` 强制 vtable/白名单

`core/runtime/objects/kernel/native_module.py`：

- `IbNativeObject(py_obj, ib_class, vtable, whitelist, registry_id)` 显式持
  vtable（`message → (func, param_meta)`）与 whitelist（属性名列表）。
- `receive()`：消息在 vtable → 直接调 vtable 函数；否则协议处理器 + 基类公理。
- `_dispatch_getattr`：vtable 方法 → 包装为 `IbNativeFunction`；白名单属性 →
  `box(getattr(py_obj, name))`；**契约外成员 → AttributeError（fail-fast）**。
- Registry 隔离：`registry_id` 身份校验拒绝跨引擎穿透。

**结论：成员访问强制经声明，无隐式穿透。缺"让用户 IBCI 代码按声明导出 native
成员"的干净机制（正是本方向要新增的）。**

### 2.3 import 解析路径（当前）

`core/runtime/interpreter/module_manager.py`：

- `import X`：(a) InterOp 注册包（需 `_spec.py` 契约，经 `get_native_contract` 取
  (vtable, whitelist) → `create_native_object` → `create_module`）；或 (b) IBCI
  artifact 模块。
- `from X import y`：InterOp 包 → `getattr`；IBCI 模块 → `scope.get`。
- 编译器：`IbImport`/`IbImportFrom`/`IbAlias`（AST）；parser `import_def.py`；
  scheduler 注入符号（`VariableSymbol(MODULE)` / 成员符号）；VM handler
  `vm_handle_IbImport`/`vm_handle_IbImportFrom` → `module_manager`。

**结论：没有"直接导入裸 Python 模块并自动按 IBCI 声明绑定成员"的路径；当前取
Python 包必经 `_spec.py`（即本方向要推翻的）。**

### 2.4 成员绑定机制（可复用的既有实现）

`core/runtime/module_system/loader.py` `_validate_and_bind`：spec 声明成员 →
校验实现对象含该成员 → 构建 proxy（`unbox → 调 Python → box`，含 `param_meta`
与 `**kwargs` 契约）→ 白名单。这个"按声明绑定 native 成员"的机制**完整存在**，
只是当前绑定源是 `_spec.py` metadata（discovery 从 `__ibcext_vtable__()` 构建）。

**结论：F1 的"用户侧声明绑定"可复用该 proxy/param_meta 机制，仅需把绑定源从
`_spec.py` 换为用户 IBCI 侧声明。**

### 2.5 协议/impl 限制

- 协议/泛型协议/`impl`（带方法体）已支持；协议满足检查在"类自身 + impl 补充"
  并集上进行。
- **限制**：`impl` 目标须为本模块用户类；泛型类/内置/宿主类型不支持（fail-fast，
  `KNOWN_LIMITS` §二十六）。
- `IbSpec` 有 `provenance` 轴（`EXTERNAL_MODULE` 已存在）——宿主类型可复用。

---

## 三、设计框架（F0 定稿方向）

### 3.1 语法形态（§四裁决点 1）

**倾向**：复用既有 `import` 关键字，新增"宿主绑定"形态（区别于普通模块 import）。

候选与裁决见 `tasks_docs/_f0_native_binding.md` §五.裁决点 1。核心考量：统一设计
语言（`import` 已承载"引入外部内容"）vs 语义区分（宿主绑定 = 裸 Python + 用户侧
声明绑定）。

### 3.2 宿主导入类型地位（§四裁决点 2）

**倾向**：一等类型（可被 `impl`/协议引用），复用 `Provenance.EXTERNAL_MODULE`。
F2 详设。

### 3.3 成员绑定机制（§四裁决点 3）

**显式声明式绑定**（非自动穿透）：用户 IBCI 类/方法声明绑定 native 成员，运行时
经 vtable/whitelist 门控。复用 `loader._validate_and_bind` 的 proxy 机制。

### 3.4 与 _spec.py 的关系（F3）

既有 `_spec.py` 插件按新绑定统一/废弃/内核原生隔离，**不保留双通道**。F0-F2 期间
既有插件路径保持不动（过渡期并存，F3 收敛为单一）。

---

## 四、F0 验证结论

- **内核 API 层实证通过**：`box(json)` → IbNativeObject；手动 vtable（dumps/loads）
  后 `receive` 调用成功（unbox→调→box）。证明"绑定裸 Python 模块成员"内核层可行。
- **验证门**：全量 pytest 绿（未改代码）；本设计文档与代码一致。

---

## 深入指引

- 主线路线图与阶段切分：`tasks_docs/ROADMAP_NATIVE_BINDING.md`
- 近期 provider 分离（已完成的近期主线）：`docs/architecture/01_principles.md` §3.7
- 内核原生模块边界：`docs/architecture/07_kernel_native_modules.md`
- 模块系统语法：`docs/syntax/11_modules.md`
