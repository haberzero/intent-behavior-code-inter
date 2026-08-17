# F2 — 协议/impl 扩展到宿主类型（设计文档）

> 临时任务控制文档（governance：完成后删除，决策沉入 docs/architecture/01_native_host_binding.md）。
> 主线：ROADMAP_NATIVE_BINDING.md §三【远期愿景】F2。基于 F1（宿主导入语法）稳定后推进。

## 〇、F2 目标与验证门

- **F2 目标**：宿主导入的**类型**（裸 Python 类）成为 IBCI 一等类型，可作 `impl`
  目标、可被协议引用（语言级能力契约扩展到宿主内容）。
- **验证门**：e2e（`impl SomeProtocol for HostType` 满足协议 + 运行期实例化/方法调用）；
  全量 pytest 零回归。

## 一、现状（F1 已实现 + 机制研究）

- F1：`import python "pkg" as lib: bind ...` 绑定**模块成员**（方法 vtable / 属性
  白名单），`lib` 是 IbNativeObject 模块值。
- F2 要绑定**类型**（裸 Python 类），使其可作 `impl` 目标。
- **impl 目标限制检查点**（已实证，`_declaration_visitors.py:86-92` `visit_IbImplDef`）：
  `class_spec.provenance != USER_DEFINED` → error。解除时允许 `EXTERNAL_MODULE`。
- **宿主类型最少接入点**（研读报告）：TypeDef(CLASS, module_path) 注册 + members
  声明 + 运行期 IbClass +（带方法体时）作用域合成。
- **协议满足**：编译期静态 spec 判定（`satisfies_protocol` 三级数据驱动），不依赖
  运行期 vtable。impl 方法直接注入 `spec.members`（单一汇入点）。

## 二、设计问题（self-grill 后收敛）

### 2.1 宿主类型语法形态

候选：
- (a) 扩展 bind 块：`bind class JSONDecoder -> any` 绑定一个宿主类为类型。
- (b) 独立类型绑定语句：`host type JSONDecoder = python.class("json.JSONDecoder")`。
- (c) 复用 import 形态：`import python "json" as j: bind type JSONDecoder`。

倾向 (a)：与 F1 bind 语法连续（统一设计语言），`bind class X` 把宿主类绑定为
IBCI 类型值 + 类型名。

**问题**：宿主类绑定后，成员如何声明？（决定 impl 协议满足检查能否静态判定）
- F2 最小：宿主类型绑定只声明"类型身份"（类名 + 构造），成员经用户 `impl` 块补充。
  即 `bind class JSONDecoder -> any` 建立类型名，用户随后 `impl MyProto for JSONDecoder:`
  定义/补充成员。
- 或：bind class 内嵌 bind 成员（如 `bind class JSONDecoder: bind decode(...)`）。

倾向 F2 最小：`bind class Name -> any` 只建类型身份；成员由 impl/用户类补充。
（F2 核心是"impl 目标扩展到宿主类型"，成员声明是 impl 的职责。）

### 2.2 impl 目标限制解除

`visit_IbImplDef`：`provenance != USER_DEFINED` → 改为允许 `EXTERNAL_MODULE`
（宿主类型）。需配套：
- 宿主类型必须有 `spec.members`（impl 方法注入点）——从哪来？
  - 方案 A：宿主类型绑定时成员表为空，impl 方法直接注入（与用户类同构）。
  - 方案 B：宿主类型成员表来自 bind class 内嵌成员声明。
- 宿主类型无 AST 作用域（非用户代码定义）——带方法体的 impl 需要 owned_scope 合成。

### 2.3 宿主类型 vs 内置类型

内置类型（int/str/list 等，provenance=KERNEL_NATIVE）**不解除**限制（保持 fail-fast）——
F2 只对 EXTERNAL_MODULE（宿主类型）解除。区分轴：provenance。

### 2.4 运行期宿主类实例化

宿主类绑定后 `JSONDecoder(...)` 调用 → 实例化裸 Python 类 → box 为 IbNativeObject。
成员调用经 vtable/whitelist（impl 补充的成员需进入 vtable——水化扩展点）。

## 三、self-grill 质询

Q1: F2 是否真的需要"宿主类型绑定"语法？还是 impl 直接以模块成员名做目标？
A: impl 目标须是**类型**（`impl X for T` 的 T 是类型名，resolve 到 TypeDef(CLASS)）。
   模块成员是值，不是类型。故需要类型绑定语法。

Q2: 宿主类型成员表为空时，impl 协议满足检查如何工作？
A: 协议满足检查在"类自身 members + impl 补充"并集上进行。宿主类型 members 空 +
   impl 补充成员 → 并集 = impl 成员。协议要求的方法若全部由 impl 提供，则满足。

Q3: 带方法体的 impl（`impl X for HostType: func foo...`）需要 owned_scope 合成，
   "宿主类型无 AST 作用域"如何解决？
A: 研读报告确认：带方法体时需作用域合成。即 impl 块进入一个合成的类作用域，
   其成员注入宿主类型 spec.members（与用户类 impl 同构）。

Q4: 运行期宿主类实例的 vtable 从哪来（impl 补充的方法如何在运行期可调）？
A: 与用户类 impl 同构：impl 方法编译期注入 spec.members → 运行期水化进 IbClass
   vtable（interpreter.py:745-781 现有机制）。宿主类实例需是 IbClass 或持有 vtable
   的 IbNativeObject。

Q5: 边界：宿主类型是否必须是"类"？函数/模块类型呢？
A: F2 最小聚焦"类"（impl 目标）。函数/模块类型不展开（F1 已覆盖模块值绑定）。

## 四、实现落点（预计）

| 环节 | 文件 | 改动 |
|---|---|---|
| 语法 | `import_def.py` | bind 块支持 `bind class Name -> type`（宿主类绑定） |
| AST | `ast.py` | IbHostBinding 扩展 is_class 标记 / 或新节点 |
| Scheduler | `scheduler.py` | `_inject_host_import` 宿主类绑定 → 注册 TypeDef(CLASS, EXTERNAL_MODULE) |
| 语义 | `_declaration_visitors.py` | `visit_IbImplDef` provenance 检查解除（EXTERNAL_MODULE 允许） |
| 语义 | impl 方法注入 | 宿主类型 spec.members 注入（复用现有） |
| 运行时 | `module_manager.py` / factory | 宿主类实例化 + vtable 水化 |

**运行时 hydration 关键**（已实证，interpreter.py:745-781）：impl 方法水化经
`registry.get_class(type_name, module=impl_module)` 找目标类 → 无则 Hydration Leak。
宿主类型需在 STAGE 5 预注册为运行期类（或水化时识别 EXTERNAL_MODULE 类型走宿主类
对象构造），否则 impl 水化找不到目标。F2 需决策宿主类的运行期对象形态（IbClass vs
独立宿主类容器），并接入 `_hydrate` 的"封印前 vtable 注入"扩展点。

## 五、待定

- bind class 语法最终形态（F2 详设后定）。
- 宿主类型实例的运行期对象形态（IbClass vs IbNativeObject + vtable）。
- 宿主类型 STAGE 5 预注册路径（impl hydration 目标查找）。
- 与 F3（废弃 _spec.py）的衔接：宿主类型绑定为 F3 提供"类型级"替代。

## 六、与主线衔接

F2 是 F1 的自然延伸（类型级绑定），F3 依赖 F2 完成（插件体系重构需要宿主类型
一等支持）。
