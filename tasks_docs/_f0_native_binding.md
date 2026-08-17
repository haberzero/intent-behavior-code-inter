# F0 — Native Binding 地基验证（设计底稿）

> 临时任务控制文档（governance：完成后删除，决策沉入 docs/architecture/01_native_host_binding.md）。
> 主线：ROADMAP_NATIVE_BINDING.md §三【远期愿景】F0-F5。本阶段 = F0 地基验证 +
> 设计底稿。

## 〇、目标与验证门

- **F0 目标**：证明 `box`/callable→用户 IBCI 类导出可行，产出宿主绑定机制设计底稿
  （`docs/architecture/01_native_host_binding.md`）。
- **验证门**：全量 pytest 绿；设计文档与代码一致。
- **F0 交付物**：
  1. 现状实证（已核实的事实，下面 §一）。
  2. 设计底稿：宿主绑定机制的完整设计（语法形态裁决、类型系统接入、成员绑定机制、
     安全模型、与 _spec.py 的关系、F1-F5 衔接）。
  3. e2e 验证：证明"用户 IBCI 类绑定裸 Python 模块成员"可行（最低限度原型）。

## 一、现状实证（已逐行核实）

### 1.1 值/宿主边界（box）
- `core/runtime/bootstrapper.py:226 box()`：`IbObject` 原样；`None→get_none`；
  `Waitable` 透传；`__IBCI_UNCERTAIN_LITERAL__→llm_uncertain`；有 boxer 工厂 →
  工厂；`callable(val)→IbNativeFunction(val, unbox_args=True, ib_class=callable)`；
  其它 → `IbNativeObject(val, ib_class=Object)`（vtable 空，成员不可见）。
- `KernelRegistry.box`（core/kernel/registry.py:426）委托 Bootstrapper.box（register_box_func）。

### 1.2 IbNativeObject / 成员门控（native_module.py）
- `IbNativeObject.__init__(py_obj, ib_class, vtable=None, whitelist=None, registry_id=None)`：
  显式持 vtable（message → (func, param_meta)）与 whitelist（属性名列表）。
- `receive`：消息在 vtable → 直接调 vtable[message][0](*args)（vtable 由 loader 完成装箱转换）；
  否则走协议处理器 + 基类公理。
- `_dispatch_getattr`：vtable 方法 → 包装为 IbNativeFunction 导出；白名单属性 →
  box(getattr(py_obj, name))；契约外成员 → AttributeError。
- `IbModule`（同文件 104）：scope 协议分派。

### 1.3 import 解析（module_manager.py）
- `import_module`：1) InterOp 注册包（`interop.get_package(module_name)`）→ 若无
  `receive` 属性则用 `interop.get_native_contract(module_name)` 取 (vtable, whitelist)
  → `object_factory.create_native_object(...)` → `create_module(...)`；2) artifact 模块。
- `import_from`：InterOp 包 → getattr 取成员；IBCI 模块 → scope.get。
- **无"直接导入裸 Python 模块并自动按 IBCI 声明绑定"路径**（必经 _spec.py 契约）。

### 1.4 协议/impl（KNOWN_LIMITS §二十六 / 06_oop §6.8）
- 协议/泛型协议/impl 带方法体均支持；协议满足检查在"类自身方法 + impl 补充方法"并集上。
- **限制**：impl 目标须为本模块用户类；泛型类/内置/宿主类型不支持（fail-fast）。
- Provenance 有 `EXTERNAL_MODULE` 轴（core/base/enums.py:28）——宿主类型可复用。

### 1.5 导入锚点与语法
- `IbImport`/`IbImportFrom`/`IbAlias`（core/kernel/ast.py:316/320/661）；
  parser `import_def.py`（parse_import / parse_from_import）。
- 编译器：`import_def.py` 产出 AST；semantic `symbol_resolution_pass.py:651`
  `visit_IbImportFrom`；VM handler `declarations.py:94 vm_handle_IbImportFrom`。

## 二、设计问题清单（F0 需定）

1. **宿主绑定语法形态**（§四裁决点 1）：一等关键字 `host`/`native` vs 既有 import
   扩展 vs 独立 bind 语句。
2. **宿主导入类型地位**（§四裁决点 2）：一等类型（可被 impl/协议引用）vs 受限 any 子类。
3. **成员绑定机制**：显式声明式绑定（user IBCI 类方法体经 native 句柄调用）vs
   自动穿透（禁止——安全边界 receive 强制 vtable）。
4. **与 _spec.py 的关系**：F3 才废弃 _spec.py；F0-F2 期间既有插件路径保持不动（双通道
   仅在过渡期作为"新路径 + 旧路径并存"——但 F3 必须收敛为单一）。
5. **安全模型**：vtable/whitelist 强制门控保留；用户侧绑定如何声明（新增一类契约声明）。

## 三、待 subagent 报告补全

- _spec.py 契约完整链路（loader._validate_and_bind / InterOp / ibci_sdk）。
- 协议/impl 编译期检查点与成员并集扩展点。
- box object_factory.create_native_object 实现细节。

## 四、F0 验证计划

- 最小 e2e：IBCI 源码 `host` 绑定一个裸 Python 模块（如 stdlib json 或 math），
  在用户 IBCI 类方法中调用其函数，run_ibci 断言输出。→ 证明"用户 IBCI 类导出
  native 成员"可行。
- 写回 docs/architecture/01_native_host_binding.md（设计底稿）。
- 全量 pytest 零回归。

## 四-b、F0 实证结果（已跑通，2026-08-17）

- **内核 API 层实证通过**：`reg.box(json)` → IbNativeObject（to_native 保真）；
  手动构造 vtable（`dumps`/`loads` → (proxy, param_meta)）+ whitelist=[] 后，
  `native_obj.receive("dumps", [reg.box({"a":1})])` → `{"a": 1}`、
  `receive("loads", [box('{"b":2}')])` → dict。proxy 做 unbox→调→box。
- **结论**：内核完全支持"box 裸 Python 模块 + vtable 绑定成员 + receive 调用"。
  缺的只是"用户 IBCI 代码按声明导出成员"的语言机制（= F1）。
- loader._validate_and_bind 的 create_proxy（unbox→调→box + param_meta）机制可复用
  为用户侧绑定（目前绑定源是 _spec.py metadata）。

## 五、裁决记录（本阶段自主决策）

### 裁决点 1：宿主绑定语法形态（F0 定稿：选 (b) `import python "pkg" as lib`）

候选：
- (a) `host lib = python.import("pkg")`——路线图 F1 示例；一等 host 关键字 + 表达式调用
- (b) `import python "pkg" as lib`——复用 import 关键字 + 伪模块 `python` + 字符串模块名
- (c) 独立 `bind` 语句

**决策：选 (b)**。理由（对照 design-philosophy / user-principles）：
1. **统一设计语言**：`import` 已承载"引入外部内容"语义，用户认知连续；(a) 的赋值语句
   形态与现有 import 语句割裂，(c) 引入全新语句类别。
2. **机制同构**：import 已走 parser→scheduler（符号注入 MODULE）→VM→module_manager
   成熟管线；(b) 只新增 `python` 伪模块分支，复用静态位置约束/依赖扫描/DAG/符号注入。
3. **语义区分**：`python` 伪模块显式标识"这是宿主空间导入"，与普通模块 import 区分；
   字符串模块名表达"任意 Python 包/模块/对象"，天然支持按需精确导入。
4. **无外部用户**：项目仍在内部开发，宿主绑定是全新语法，不破坏既有 .ibci 代码；
   即便后续调整形态，迁移成本为零（无既有使用者）。风险可控，自主决策。
5. 路线图示例 (a) 属"机制"非"原则"，按 user-principles §一.2 用现代对照重新判断；
   方向（宿主导入）不变，具体语法以设计统一性为准。

**实施要点（F1）**：parser import_def.py 识别 `python` 伪模块 + 字符串模块名；
scheduler 注入宿主模块符号；module_manager.import_module 加 `python` 分支（裸
Python import → IbNativeObject/类型 + 用户侧绑定声明）。


### 裁决点 2：宿主导入类型地位

**倾向：一等类型**，复用 `Provenance.EXTERNAL_MODULE` 轴（core/base/enums.py:28 已存在）。
F2 详设；关键落点已实证：`_declaration_visitors.py:86-92 visit_IbImplDef` 的 impl 目标
限制检查（`class_spec.provenance != USER_DEFINED` → error），解除时允许
`EXTERNAL_MODULE`（宿主类型）并配套成员表/方法体支持。

**F2 机制细节（subagent 研读报告补充，已实证）**：
- 协议满足判定是**编译期静态 spec 判定**（不看运行期 vtable）：`_protocol.py:154-170`
  `satisfies_protocol` 三级数据驱动判定（spec 声明）。
- **成员并集**：无独立合并器——impl 方法直接注入目标类同一张 `spec.members`
  （`symbol_collection_pass.py:346-386`），运行期水化进同一 vtable
  （`interpreter.py:745-781`）。F2 宿主绑定的扩展点 = `spec.members` 单一汇入点 +
  封印前 vtable 注入。
- impl 目标限制检查点（10 个，管线各阶段）：parser 单标识符
  `declaration.py:311`；TypePhase 三连拒 `_declaration_visitors.py:79-99`；
  收集期 SEM_REDEFINITION `symbol_collection_pass.py:372-380`；owned_scope 隐形硬阻塞。
- 内置类型 fail-fast 根因：provenance 检查 + 无 AST 作用域 + IbNativeFunction/
  IbUserFunction vtable 契约差异。
- 宿主类型最少接入点（b）：TypeDef(CLASS, module_path) 注册 + members 声明 +
  运行期 IbClass + （带方法体时）作用域合成。
- TypeRef `(head, args, module)` 三级解析（`_base.py:112-134`），宿主表达 =
  `TypeRef("JSONDecoder", module="json")`。
- F2 落地配套清单 7 项：解除 provenance 限制、members 注入、owned_scope 合成、
  水化目标模块键修正、self 语义、llm func 复用、协议检查零改动。

### 裁决点 3：成员绑定机制
- 显式声明式绑定（user IBCI 类方法体经 native 句柄调用）——符合安全模型（receive 强制
  vtable 门控）。禁止自动穿透。

### F1 设计问题（待定，随推进补记）

1. **宿主模块对象的 vtable 来源**：裸 Python 模块无 _spec.py 契约。F1 需要"用户侧声明
   绑定"——`import python "pkg" as lib` 后 `lib.member` 如何获得 vtable 条目？
   - 候选 (i)：import 后跟绑定声明块（如 `{ bind: member1, member2 }`）
   - 候选 (ii)：用户 IBCI 类方法内显式调用 `lib.member(...)`，首次访问惰性绑定
   - 候选 (iii)：复用 impl/协议（F2 方向）
   - 倾向：需满足"显式声明绑定、非自动穿透"。F1 最小可行 = import 时**显式声明**
     要暴露的成员（白名单式），而非自动暴露全部。
2. **语法形态落点**：`import python "pkg" as lib` 中 `lib` 是 IbNativeObject（模块级
   变量）还是 IbModule？（与现有 `import json` → IbModule 形态对齐 vs 直接 IbNativeObject）
3. **用户类持有**：`any` 字段/局部变量持 IbNativeObject（KNOWN_LIMITS 已支持），
   方法内 `lib.member(...)` 经 vtable 调用。

