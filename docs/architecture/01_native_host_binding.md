# 原生宿主绑定（Native Host Binding）

> 本文档描述 IBCI 用户层原生绑定 Python 内容的**远期架构**：宿主导入语法、用户 IBCI
> 类型/协议对裸 Python 内容的绑定、插件体系的重构走向，以及内核 IBCI 自举与
> 缓存/JIT 的规划。面向需要理解"抛弃 Python 侧 `_spec.py` 插件思路"这一方向的
> 架构演进的设计者。
>
> 本文档是 `tasks_docs/ROADMAP_NATIVE_BINDING.md` §三【远期愿景】F0-F5 的**设计
> 底稿**（F0 产物）。当前代码状态：F0（地基验证）、F1（宿主导入一等语法 + 用户类
> 持有 native）已完成并合入；F2-F5 未开始。

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

**决策**：复用既有 `import` 关键字，新增"宿主绑定"形态：`import python "pkg" as lib`
（`python` 伪模块 + 字符串模块名）。

理由（对照 design-philosophy / user-principles）：
1. **统一设计语言**：`import` 已承载"引入外部内容"语义，用户认知连续；独立的
   `host`/`bind` 语句与现有 import 形态割裂。
2. **机制同构**：import 已走 parser→scheduler（符号注入）→VM→module_manager 成熟
   管线，宿主绑定只新增 `python` 伪模块分支，复用静态位置约束/依赖扫描/DAG/符号注入。
3. **语义区分**：`python` 伪模块显式标识"宿主空间导入"，字符串模块名表达"任意
   Python 包/模块/对象"，天然支持按需精确导入。
4. **无外部用户**：宿主绑定是全新语法，不破坏既有 .ibci 代码；即便后续调整形态，
   迁移成本为零。风险可控，自主决策（记录于 `tasks_docs/_f0_native_binding.md`）。

### 3.2 宿主导入类型地位（§四裁决点 2）

**一等类型**，复用 `Provenance.EXTERNAL_MODULE` 轴（已存在）。宿主导入的模块/类/函数
以一等值/类型进入 IBCI 类型系统，可被 `impl`/协议引用（F2）。

### 3.3 成员绑定机制（§四裁决点 3）

**显式声明式绑定**（非自动穿透）：用户 IBCI 类/方法声明绑定 native 成员，运行时
经 vtable/whitelist 门控（`IbNativeObject.receive` 强制 vtable，契约外成员
fail-fast）。复用 `loader._validate_and_bind` 的 proxy（unbox→调→box + param_meta）
机制，仅把绑定源从 `_spec.py` metadata 换为用户 IBCI 侧声明。

### 3.4 与 _spec.py 的关系（F3）

既有 `_spec.py` 插件按新绑定统一/废弃/内核原生隔离，**不保留双通道**。F0-F2 期间
既有插件路径保持不动（过渡期并存），F3 收敛为单一。

### 3.5 关键实现落点（已实证）

| 阶段 | 落点 | 机制 |
|---|---|---|
| F1 | parser `core/compiler/parser/components/import_def.py` `parse_import` | 识别 `python` 伪模块 + 字符串模块名 |
| F1 | `core/compiler/parser/parser.py:188` | import 语句入口分发 |
| F1 | scheduler `core/compiler/scheduler.py`（import 符号注入 470-549） | 注入宿主模块符号/成员符号 |
| F1 | `core/runtime/interpreter/module_manager.py` `import_module` | `python` 分支：裸 Python import → 用户侧绑定 |
| F1 | `core/runtime/vm/handlers/declarations.py` `vm_handle_IbImport` | 运行时导入执行 |
| F1 | `loader._validate_and_bind` proxy 机制 | 复用为绑定构造 |
| F2 | `_declaration_visitors.py:86-92` `visit_IbImplDef` | impl 目标 provenance 检查（USER_DEFINED → 允许 EXTERNAL_MODULE） |
| F2 | 协议满足检查（类自身 + impl 并集） | 加入宿主绑定成员 |

**F2 机制细节（已实证）**：
- 协议满足判定是编译期静态 spec 判定（`core/kernel/spec/registry/_protocol.py:154-170`
  `satisfies_protocol` 三级数据驱动）。
- 成员并集无独立合并器：impl 方法直接注入 `spec.members`（`symbol_collection_pass.py`
  346-386），运行期水化进同一 vtable（`interpreter.py:745-781`）——F2 扩展点 =
  `spec.members` 单一汇入点 + 封印前 vtable 注入。
- 宿主类型最少接入：TypeDef(CLASS, module_path) 注册 + members 声明 + 运行期 IbClass
  +（带方法体时）作用域合成；TypeRef `(head, args, module)` 三级解析
  （`core/kernel/spec/type_ref/_base.py:112-134`）。

---

## 四、F0 验证结论

- **内核 API 层实证通过**：`box(json)` → IbNativeObject；手动 vtable（dumps/loads）
  后 `receive` 调用成功（unbox→调→box）。证明"绑定裸 Python 模块成员"内核层可行。
- **验证门**：全量 pytest 绿（未改代码）；本设计文档与代码一致。

---

## 五、F1 落地（宿主导入一等语法 + 用户类持有 native）

**语法（已实现）**：

```ibci
import python "math" as m:
    bind sqrt(x: float) -> float
    bind pi -> float
```

- `python` 伪模块关键字（非保留字）+ 字符串模块名；`bind` 声明成员。
- `bind name(params) -> ret`：方法成员（IBCI 签名 → 编译期类型检查 + 运行时 proxy
  vtable）；`bind name -> type`：属性成员（白名单）。
- **显式声明式绑定**：成员访问强制经 vtable/whitelist 门控（`IbNativeObject.receive`），
  契约外成员 fail-fast（AttributeError）；bind 声明但宿主缺失成员 → 绑定期报错。
- 用户 IBCI 类 / `any` 字段可持 `lib`（IbNativeObject），方法内 `lib.member(...)` 调用。

**为何 bind 块而非 from-import 简化**（设计取舍，对照 design-philosophy）：
- 满足"显式绑定到 IBCI 声明方法"——bind 声明方法签名，编译期可做成员类型检查
  （调用 `m.sqrt(16.0)` 校验实参类型，宿主类型检查一致）。
- from-import 简化（`from python "math" import sqrt`）丢失签名信息，成员类型退化为
  any/动态——不符合"绑定到声明方法"的类型安全意图。
- bind 块与 `protocol`/`impl` 方法签名形态一致（统一设计语言）。

**实现落点（已落地）**：

| 环节 | 文件 | 落地内容 |
|---|---|---|
| AST | `core/kernel/ast.py` | `IbHostImport` / `IbHostBinding` / `IbHostBindingParam` |
| Lexer/Token | `core/compiler/common/tokens.py` + `core_scanner.py` | `bind` 关键字（TokenType.BIND） |
| Parser | `core/compiler/parser/components/import_def.py` | `parse_host_import` + bind 块解析 |
| 依赖扫描 | `core/compiler/parser/parser.py` + `dependencies.py` | `ImportType.HOST_IMPORT`；宿主 import 跳过 IBCI 依赖图 |
| Scheduler | `core/compiler/scheduler.py` | `_inject_host_import`：从 bind 声明合成宿主模块 spec（EXTERNAL_MODULE MODULE）+ 注入 lib 符号 |
| 语义 | `symbol_resolution_pass.py` | `visit_IbHostImport` 绑定符号到节点 |
| 运行时 | `core/runtime/interpreter/module_manager.py` | `import_host_module`：importlib + 按 bind 构建 vtable/whitelist + create_native_object + create_module |
| VM | `declarations.py` / `dispatch.py` | `vm_handle_IbHostImport` + 注册 |
| 单一权威源 | `_annotation_utils.py` / `proxy.py` | `annotation_to_typeref`（AST→TypeRef）、`create_proxy`（unbox→调→box）从既有实现提取共用 |

**验证门**：e2e（`m.sqrt(16.0)=4.0`、`m.pi`、`m.pow(2,10)=1024.0`、用户类 `Calculator`
持 native 调 `sqrt=5.0`、无 asname `math.sqrt=4.0`、磁盘文件 rehydrate 后执行、
跨模块导入 `hsqrt(49.0)=7.0`）；负样本（未声明成员 fail-fast、绑定缺失成员报错、
编译期类型检查 `SEM_TYPE_MISMATCH`、重复 bind `SEM_REDEFINITION`、`import python` 无字符串
回落普通路径）；全量 pytest 3041 passed / 1 skipped（含新增 `tests/runtime/test_host_binding.py`
10 项）零回归。

---

## 深入指引

- 主线路线图与阶段切分：`tasks_docs/ROADMAP_NATIVE_BINDING.md`
- 近期 provider 分离（已完成的近期主线）：`docs/architecture/01_principles.md` §3.7
- 内核原生模块边界：`docs/architecture/07_kernel_native_modules.md`
- 模块系统语法：`docs/syntax/11_modules.md`
