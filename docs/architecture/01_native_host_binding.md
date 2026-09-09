# 原生宿主绑定（Native Host Binding）

> 本文档描述 IBCI 用户层原生绑定 Python 内容的架构：宿主导入语法、用户 IBCI
> 类型/协议对裸 Python 内容的绑定，以及插件体系的扩展唯一边界。面向需要
> 理解"宿主绑定 = 用户扩展唯一边"这一架构形态的设计者。

---

## 一、原生宿主绑定的动机

以 **Python 侧契约插件** 暴露 Python 内容（Python 侧定义实现 + `__ibcext_vtable__()`
契约，IBCI 侧经 `import` 包装为模块）会带来几个结构性限制：

1. **双语言契约割裂**：契约与实现分居两个文件、两种形态，
   用户在 Python 侧维护"给 IBCI 看的接口"，而非在 IBCI 侧声明"我要绑定什么"。
2. **`import` 受限于已注册包**：裸 Python 模块/类/函数无法直接导入并绑定——
   `import X` 只认 InterOp 注册包或 IBCI artifact 模块。
3. **`impl`/协议目标受限**：协议与 retroactive implementation 目标须为本模块
   用户类；宿主导入类型（如 `python.import("pkg")` 得到的类型）无法作为协议/
   `impl` 目标，语言级能力契约无法扩展到宿主内容。

原生宿主绑定的目标：**用户在 IBCI 侧声明式导入裸 Python 内容，并显式绑定到
IBCI 类型/协议/方法**——把"暴露 Python 给 IBCI"从 Python 侧契约改为 IBCI 侧声明。

---

## 二、架构事实

### 2.1 值/宿主边界：`box` 能包装任意 Python 对象

`core/runtime/bootstrapper.py` `box()`（经 `KernelRegistry.box` 委托）：

- `IbObject` 原样返回；`None → get_none()`；`Waitable` 透传（异步句柄不装箱）；
  `__IBCI_UNCERTAIN_LITERAL__ → llm_uncertain`。
- `callable(val)` → `IbNativeFunction(val, unbox_args=True, ib_class=callable)`。
- 其它 → `IbNativeObject(val, ib_class=Object)`（vtable 空，成员对 IBCI 不可见）。

**结论：IBCI 能将任意 Python 对象/可调用对象作为一等值持有与传递。**

### 2.2 成员门控：`IbNativeObject` 强制 vtable/白名单

`core/runtime/objects/kernel/native_module.py`：

- `IbNativeObject(py_obj, ib_class, vtable, whitelist, registry_id)` 显式持
  vtable（`message → (func, param_meta)`）与 whitelist（属性名列表）。
- `receive()`：消息在 vtable → 直接调 vtable 函数；否则协议处理器 + 基类公理。
- `_dispatch_getattr`：vtable 方法 → 包装为 `IbNativeFunction`；白名单属性 →
  `box(getattr(py_obj, name))`；**契约外成员 → AttributeError（fail-fast）**。
- Registry 隔离：`registry_id` 身份校验拒绝跨引擎穿透。

**结论：成员访问强制经声明，无隐式穿透。**

### 2.3 import 解析路径

`core/runtime/interpreter/module_manager.py`：

- `import X`：(a) InterOp 注册包（vtable/whitelist 经 `get_native_contract` 取，
  由 `bind_native_contract` 显式绑定 → `create_native_object` → `create_module`）；
  或 (b) IBCI artifact 模块。
- `from X import y`：InterOp 包 → `getattr`；IBCI 模块 → `scope.get`。
- 编译器：`IbImport`/`IbImportFrom`/`IbAlias`（AST）；parser `import_def.py`；
  scheduler 注入符号（`VariableSymbol(MODULE)` / 成员符号）；VM handler
  `vm_handle_IbImport`/`vm_handle_IbImportFrom` → `module_manager`。

取 Python 包的用户侧唯一通道是宿主绑定
`import python "..." : bind ...`（见 §四/§五）。

### 2.4 成员绑定机制（可复用的既有实现）

`core/runtime/module_system/loader.py` `_validate_and_bind`：spec 声明成员 →
校验实现对象含该成员 → 构建 proxy（`unbox → 调 Python → box`，含 `param_meta`
与 `**kwargs` 契约）→ 白名单。这个"按声明绑定 native 成员"的机制**完整存在**，
绑定源是用户 IBCI 侧 `bind` 声明（`import python ... : bind ...`）。

### 2.5 协议/impl 限制

- 协议/泛型协议/`impl`（带方法体）受支持；协议满足检查在"类自身 + impl 补充"
  并集上进行。
- **限制**：`impl` 目标须为本模块用户类；泛型类/内置/宿主类型不支持（fail-fast，
  `KNOWN_LIMITS` §二十四）。
- `IbSpec` 有 `provenance` 轴（含 `EXTERNAL_MODULE`）——宿主类型可复用。

---

## 三、设计框架

### 3.1 语法形态

**决策**：复用既有 `import` 关键字，新增"宿主绑定"形态：`import python "pkg" as lib`
（`python` 伪模块 + 字符串模块名）。

理由：
1. **统一设计语言**：`import` 已承载"引入外部内容"语义，用户认知连续；独立的
   `host`/`bind` 语句与现有 import 形态割裂。
2. **机制同构**：import 已走 parser→scheduler（符号注入）→VM→module_manager 成熟
   管线，宿主绑定只新增 `python` 伪模块分支，复用静态位置约束/依赖扫描/DAG/符号注入。
3. **语义区分**：`python` 伪模块显式标识"宿主空间导入"，字符串模块名表达"任意
   Python 包/模块/对象"，天然支持按需精确导入。
4. **无外部用户**：宿主绑定是全新语法，不破坏既有 .ibci 代码；即便后续调整形态，
   迁移成本为零。

### 3.2 宿主导入类型地位

**一等类型**，复用 `Provenance.EXTERNAL_MODULE` 轴。宿主导入的模块/类/函数
以一等值/类型进入 IBCI 类型系统，可被 `impl`/协议引用（见 §五）。

### 3.3 成员绑定机制

**显式声明式绑定**（非自动穿透）：用户 IBCI 类/方法声明绑定 native 成员，运行时
经 vtable/whitelist 门控（`IbNativeObject.receive` 强制 vtable，契约外成员
fail-fast）。复用 `loader._validate_and_bind` 的 proxy（unbox→调→box + param_meta）
机制，绑定源为用户 IBCI 侧声明。

### 3.4 扩展通道收敛（单通道）

扩展通道收敛为单通道，不保留双通道：内置模块契约集中于
`core/runtime/bootstrap/builtin_modules.py` 的 TypeDef 字面量（构造期注册），
用户扩展统一经宿主绑定 `bind`。

### 3.5 关键实现落点

| 环节 | 落点 | 机制 |
|---|---|---|
| 语法解析 | `core/compiler/parser/components/import_def.py` `parse_host_import` | 识别 `python` 伪模块 + 字符串模块名 + bind 块 |
| Import 分发 | `core/compiler/parser/parser.py` | import 语句入口分发（宿主 import 跳过 IBCI 依赖图） |
| 符号注入 | `core/compiler/scheduler.py` | 从 bind 声明合成宿主模块 spec（EXTERNAL_MODULE MODULE）+ 注入 lib 符号 |
| 语义绑定 | `symbol_resolution_pass.py` | `visit_IbHostImport` 绑定符号到节点 |
| 运行时导入 | `core/runtime/interpreter/module_manager.py` `import_host_module` | importlib + 按 bind 构建 vtable/whitelist + create_native_object + create_module |
| VM | `declarations.py` / `dispatch.py` | `vm_handle_IbHostImport` + 注册 |
| 成员绑定 | `loader._validate_and_bind` proxy 机制 | 复用为绑定构造 |
| impl 目标放行 | `_declaration_visitors.py` `visit_IbImplDef` | impl 目标 provenance 检查（USER_DEFINED → 允许 EXTERNAL_MODULE） |
| 协议满足 | `core/kernel/spec/registry/_protocol.py` `satisfies_protocol` | 三级数据驱动；在"bind 声明 + impl 补充"并集上判定 |
| 单一权威源 | `_annotation_utils.py` / `proxy.py` / `base.unbox_for_native_call` | `annotation_to_typeref`（AST→TypeRef）、`create_proxy`（unbox→调→box）、`unbox_for_native_call`（可调用透传 + 拆箱） |

**成员并集机制**：
- 协议满足判定是编译期静态 spec 判定（`satisfies_protocol` 三级数据驱动）。
- 成员并集无独立合并器：impl 方法直接注入 `spec.members`（`symbol_collection_pass.py`
  346-386），运行期水化进同一 vtable（`interpreter.py:745-781`）——扩展点 =
  `spec.members` 单一汇入点 + 封印前 vtable 注入。
- 宿主类型最少接入：TypeDef(CLASS, module_path) 注册 + members 声明 + 运行期 IbClass
  +（带方法体时）作用域合成；TypeRef `(head, args, module)` 三级解析
  （`core/kernel/spec/type_ref/_base.py:112-134`）。

---

## 四、宿主导入一等语法（bind 模块成员）

**语法**：

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

**为何 bind 块而非 from-import 简化**（设计取舍）：
- 满足"显式绑定到 IBCI 声明方法"——bind 声明方法签名，编译期可做成员类型检查
  （调用 `m.sqrt(16.0)` 校验实参类型，宿主类型检查一致）。
- from-import 简化（`from python "math" import sqrt`）丢失签名信息，成员类型退化为
  any/动态——不符合"绑定到声明方法"的类型安全意图。
- bind 块与 `protocol`/`impl` 方法签名形态一致（统一设计语言）。

**实现落点**：

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

---

## 五、宿主类型绑定（bind class）

**语法**——两种形态：

```ibci
import python "json" as j:
    bind class JSONDecoder:
        bind decode(s: str) -> any

import python "json" as j2:
    bind class JSONEncoder -> any   # 简写：仅类型身份，成员由 impl 补充
```

- `bind class Name: <嵌套 bind 成员>`：把裸 Python 类绑定为一等 IBCI 类型。嵌套成员
  声明规则与模块成员一致（方法 `bind f(params) -> ret` / 属性 `bind x -> type`）。
- `bind class Name -> any` 简写：仅建立类型身份，能力由 `impl` 补充（纯 impl 场景）。
- **成员表 = 宿主声明 + impl 补充并集**：bind 声明是宿主类自身能力契约；`impl` 只补充
  IBCI 协议所需而宿主没有的方法（`visit_IbImplDef` provenance 放行 EXTERNAL_MODULE 与
  KERNEL_NATIVE 内置具体值类型——内置 impl 的完整语义见 `docs/KNOWN_LIMITS.md` §二十四）。
- **编译期冲突 fail-fast（SEM_REDEFINITION）**：impl 方法不得与 bind 声明成员同名
  （冲突判定以权威成员面 spec.members 为准）；同一 bind class 块内不得重复绑定同名成员。
- **协议满足 = 编译期静态 spec 判定**：在"bind 声明 + impl 补充"并集上判定，运行期零改动。

**运行期机制**：

- 宿主类 = `HostClassBinding(IbClass)`：`__call__` 恒走 `instantiate`（调用裸 Python 类
  构造实例）。实例 = `IbNativeObject` + per-instance vtable（bind 方法 = `create_proxy`
  绑定方法）+ whitelist（bind 属性）。
- impl 方法不并入 vtable——经 `IbNativeObject._dispatch_getattr` 类方法回落导出为
  `IbBoundMethod`（注入 receiver，与用户对象方法同构）。回落仅限宿主类实例
  （`isinstance(ib_class, HostClassBinding)` 门控，避免击穿契约门禁）。
- bind 方法返回裸 `py_class` 实例时重新包装为宿主实例（一等类型语义：Python
  `datetime` 就是 IBCI `datetime`，契约随返回对象延续）。
- STAGE 5 预注册：`_hydrate_host_classes` 扫描模块根 IbHostImport，导入裸 Python 模块、
  校验宿主类/成员存在性（方法类级校验；实例属性走访问期契约）、注册 HostClassBinding
  （须先于 impl 水化）。类名绑定到模块作用域（`Name(...)` 可解析）。

**单一权威源**：`base.unbox_for_native_call`（可调用实例透传 + IbObject 拆箱，proxy 与
宿主类实例化共用）；`module_manager.import_host_py_module`（STAGE 5 与 VM 宿主 import
共用导入入口，统一错误类型）。

---

## 六、内核契约自举（工具契约源）

**形态**：内核自身的工具模块契约（`math` / `json` / `time` / `schema`）用与用户侧
**同一 bind 声明形态**表达——契约源文件
`core/runtime/bootstrap/contracts/<module>.ibci`：

```ibci
import python "ibci_modules.ibci_math" as math:
    bind sqrt(x: float) -> float
    bind pi -> float
    ...
```

Engine 构造期经 `kernel_contracts.load_tool_contracts` 处理契约源：parse（声明域，
非声明形态 fail-fast）→ 成员 spec 合成（与 §四 用户侧宿主绑定**共用同一合成逻辑**）→
注册 → 既有构造期严格绑定（spec ↔ 实现成员/签名校验，`docs/subsystems/04_plugin_system.md`
§2）。工具模块的 spec provenance = `EXTERNAL_MODULE`，与用户侧 bind 派生同构。

**设计理由**：

1. **契约单一权威源**：工具契约（成员面 + 签名）此前是 Python 字面量中对实现签名的
   手写重复（双写真相，人工维护漂移）。迁移后契约以 IBCI 声明表达，实现面
   （模块级函数）与契约面经构造期严格绑定对账——漂移即启动失败。
2. **设计语言统一**：内核与用户使用同一声明形态描述宿主成员契约；"绑定声明即契约"
   的语义不因声明者是用户还是内核而分叉。
3. **机制同构**：不新增运行期机制——spec 合成、严格绑定、运行期消费全部复用宿主
   绑定既有通道；构造期仅新增"处理声明源"一步（parse + 合成 + 注册）。

**边界（哪些契约不表达为 bind 声明，及原因）**：

| 契约面 | 维持形态 | 原因 |
|--------|---------|------|
| `net` | 宿主侧字面量 | 8 个方法的 `headers` 参数带默认值（`has_default`）——bind 声明无默认值语法；且 per-engine 可变状态需实例形态 |
| `ai` / `ihost` / `meta` / `idbg` / `isys` / `iruntime` / `file` | 宿主侧字面量 | 构造期 lifecycle / LLM 服务通道 / 引擎内部服务（子环境 spawn、编译门）/ 内核值类型导出（`file_handle` 等）——bind 是运行期用户侧机制，无对应表达面 |

**bind 默认值语法**（`net` 契约源化的前置）为语言级设计项，独立立项评估——默认值
放置位置（bind 声明内 vs 包装层）与既有"默认值放 .ibci 包装层"裁定的关系须一并裁定。

---

## 深入指引

- 宿主绑定用户 howto：`docs/howto/extend_with_host_binding.md`
- 内置模块系统与宿主绑定：`docs/subsystems/04_plugin_system.md`
- 模块系统语法：`docs/syntax/11_modules.md`
- LLM provider 自定义（宿主绑定通道）：`docs/howto/modify_llm_provider.md` + `docs/architecture/01_principles.md` §3.7
