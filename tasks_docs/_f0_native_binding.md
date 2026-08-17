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
（待 F2 详设，F0 仅记录方向：倾向一等类型，复用 Provenance.EXTERNAL_MODULE 轴）

### 裁决点 3：成员绑定机制
- 显式声明式绑定（user IBCI 类方法体经 native 句柄调用）——符合安全模型（receive 强制
  vtable 门控）。禁止自动穿透。

