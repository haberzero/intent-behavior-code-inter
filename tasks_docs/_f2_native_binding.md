# F2 — 协议/impl 扩展到宿主类型（设计文档）

> 临时任务控制文档（governance：完成后删除，决策沉入 docs/architecture/01_native_host_binding.md）。
> 主线：ROADMAP_NATIVE_BINDING.md §三【远期愿景】F2。基于 F1（宿主导入语法）稳定后推进。

## 〇、F2 目标与验证门

- **F2 目标**：宿主导入的**类型**（裸 Python 类）成为 IBCI 一等类型，可作 `impl`
  目标、可被协议引用（语言级能力契约扩展到宿主内容）。
- **验证门**：e2e（`bind class Name` 宿主类型绑定 + `impl Proto for Name` 满足协议 +
  运行期实例化/方法调用）；全量 pytest 零回归。

## 一、现状（F1 已实现 + 机制研究）

- F1：`import python "pkg" as lib: bind ...` 绑定**模块成员**（方法 vtable / 属性
  白名单），`lib` 是 IbNativeObject 模块值。
- F2 要绑定**类型**（裸 Python 类），使其可作 `impl` 目标。
- **impl 目标限制检查点**（`_declaration_visitors.py:86-92` `visit_IbImplDef`）：
  `class_spec.provenance != USER_DEFINED` → error。解除时允许 `EXTERNAL_MODULE`。
- **impl target 是裸名**（`IbImplDef.type_name: str`，parser 只 consume 单个
  IDENTIFIER，declaration.py:311）→ 宿主类型必须可**顶层裸名解析**（不能要求
  `j.JSONDecoder` 模块限定形态出现在 impl target）。
- **类型注册路径**（symbol_collection_pass `visit_IbClassDef`）：`factory.create_class`
  → `registry.register(cls_meta)`（键 = `{module}.{name}` 或裸名）→ `TypeSymbol(CLASS)`
  define 进符号表 → 进入类作用域收集成员（owned_scope）。
- **registry.resolve(name)**（`_base.py:112`）：module 限定优先，回落裸名。
  `visit_IbImplDef` 用 `self.registry.resolve(node.type_name)`（语义分析器与 scheduler
  共用同一 registry）。
- **current_module 时序**：`set_current_module` 只在 `analyze()` 开头设置（analyzer.py:57），
  而 scheduler 的 import 注入循环（含 `_inject_host_import`）在 `analyze()` **之前**运行
  → 宿主类型注册时 `current_module` 为 None。故宿主类注册需**显式传入 module_name**
  （S2 类身份统一：所有用户类 module 限定，键 = `{module}.{name}`；裸名注册可回落
  resolve 但运行期键不一致风险高，不采用）。

## 二、F2 语法设计（自裁定稿）

```ibci
import python "json" as j:
    bind class JSONDecoder:
        bind decode(s: str) -> any
        bind raw_decode(s: str) -> any
```

- `bind class Name:` 绑定裸 Python 类为 IBCI 类型 `Name`（顶层类型名，可用作
  `impl X for Name` 目标 / `Name(...)` 构造 / 类型注解）。
- 嵌套 `bind member` 声明原生成员（方法/属性）→ 该类型实例 vtable/whitelist +
  编译期成员表（协议满足判定用）。成员表 = MethodMemberSpec/MemberSpec，复用
  `annotation_to_typeref`。
- `bind class Name -> any` 简写：仅类型身份，无声明成员（成员由 impl 补充）。
- 成员访问经 vtable/whitelist 门控（与 F1 同构，IbNativeObject.receive）。

**为何内嵌 bind 成员（非"仅 impl 补充"）**（对照 design-philosophy）：
- 宿主类自身能力（decode/raw_decode）是类型契约的一部分，应先声明（F1 bind 同构），
  impl 只补充 IBCI 协议所需而宿主没有的方法——职责分离清晰。
- 协议满足判定在"宿主声明成员 + impl 补充"并集上进行，静态可判定。
- 简写 `bind class Name -> any` 覆盖"纯 impl 补充"场景（并集 = impl 成员）。

## 三、编译期设计（已确认）

1. scheduler `_inject_host_import` 扩展（需把 module_name 传入）：
   - 对每个 `bind class`：
     - `cls_meta = registry.factory.create_class(name=Name, module=模块名,
       provenance=EXTERNAL_MODULE)`。
     - `cls_meta.members` = 嵌套 bind 声明成员（MethodMemberSpec/MemberSpec，
       复用 annotation_to_typeref + ParamDescriptor type_ref 同步）。
     - `registry.register(cls_meta)` → `registry.resolve("Name")` 可用。
     - `TypeSymbol(name=Name, CLASS, spec=cls_meta, provenance=EXTERNAL_MODULE)`
       define 进模块符号表（用户代码 `Name(...)` / 类型注解可解析）。
     - 合成 `owned_scope`（SymbolTable，parent=模块表）供 impl 方法注入。
   - `bind class` 与 F1 `bind member` 共存于同一 bind 块（语法上 class 绑定与
     成员绑定并列）。
2. `visit_IbImplDef` 限制解除：`provenance != USER_DEFINED` → 允许 `EXTERNAL_MODULE`
   （宿主类型）；仍拒绝 `KERNEL_NATIVE`（内置类型保持 fail-fast）。
3. impl 方法注入复用现有机制（symbol_collection_pass `visit_IbImplDef` 用
   `sym.owned_scope` + `spec.members`）——宿主类有 owned_scope + members 即可复用。
4. 协议满足判定：编译期静态 spec 判定（`satisfies_protocol` 三级数据驱动），
   在"类自身 members + impl 补充"并集上进行，宿主类型无需特殊处理。

## 四、运行期设计（研究 subagent 报告后确认并已落地）

- **宿主类运行期形态**：`HostClassBinding(IbClass)`（core/runtime/objects/kernel/
  host_class.py）——包装裸 Python 类为一等 IBCI 类型。`_dispatch_call` 恒走
  `instantiate`（覆写默认 _ClassInstantiateDrive CPS 驱动——宿主类型无 IBCI
  字段/__init__）。实例 = IbNativeObject + per-instance vtable（bind 方法 =
  F1 create_proxy 绑定方法）+ whitelist（bind 属性）。
- **impl 方法可达**：不并入 vtable；经 `IbNativeObject._dispatch_getattr` 类方法
  回落（lookup_method → IbBoundMethod 注入 receiver，与用户对象方法同构）。
- **返回宿主实例重包装**：bind 方法返回 py_class 实例时重新包装为宿主实例
  （一等类型语义：Python datetime 就是 IBCI datetime，契约随返回对象延续）。
- **STAGE 5 预注册**（interpreter._hydrate_host_classes）：扫描模块根 body 的
  IbHostImport，导入裸 Python 模块，校验宿主类/成员存在性（fail-fast），创建
  HostClassBinding + `registry.register_class`（须先于 impl 水化，供其
  `get_class(type_name, module=impl_module)` 命中）。封印（STAGE 7 seal）前完成。
- **类名作用域绑定**：vm_handle_IbHostImport 对 bind class 绑定类对象到模块作用域
  （类型符号 UID = `scope_{module}:{name}`，与 vm_handle_IbClassDef 同构），
  使 `Name(...)` 可解析；不重复注册（运行期注册职责在 STAGE 5）。
- 协议满足判定纯编译期静态 spec 判定（bind 声明 + impl 补充并集），运行期零改动。

## 五、决策记录（全部已落地，无待定）

- 宿主类水化目标形态：HostClassBinding(IbClass)（非"类容器 + 每实例 vtable"分离式）。
- 宿主类型运行期预注册路径：interpreter STAGE 5 扫描 IbHostImport（复用 ArtifactLoader
  枚举 impl 块同构模式）。
- impl 补充方法经 IbNativeObject 类方法回落（IbBoundMethod），非并入实例 vtable。
- 已知边界：bind 方法返回 py_class 实例经重包装保持一等类型；跨模块宿主类型、
  宿主类型继承（bind class 嵌套继承）为后续 F 段扩展点。

## 五之二、F2 独立复核整改决策记录（b228d4fd 报告，已全部处理）

**B1（阻塞，实证为误诊但仍保留机制隔离）**：复核称类方法回落击穿 F1 契约门禁
（F1 模块对象 `j.toString` 契约外成员静默通过）。实证：在 pre-F2 父提交 56cf2ead 上
`j.toString` 同样返回 `["<Module 'json'>"]`（经 IbModule._dispatch_getattr →
scope 失败 → base Object 公理路径，与 F2 回落无关）——Object 公理
（toString/to_bool/to_native 等）是对象模型固有表面，非模块契约成员；真实 F1
契约（非公理名如 m.cos）由 test_unbound_member_fails 保证且通过。**裁决**：
"F2 引入回归"不成立，无需新增 F1 回归测试；但回落已加
`isinstance(self.ib_class, HostClassBinding)` 门控作为机制隔离（impl 回落仅
宿主类实例，按构造收敛），保留。

**M1（中，已修）**：bind 方法与 impl 方法同名编译期未拦截（宿主类合成
owned_scope 为空表，冲突检查只查符号表；impl 静默遮蔽 bind 成员且 _define 覆写
spec.members 签名——双写真相漂移）。修复：
1. symbol_collection_pass.visit_IbImplDef 冲突判定改为以权威成员面
   `target_spec.members` 为准（`stmt.name in symbols or stmt.name in members`），
   普通类与宿主类一致收敛，SEM_REDEFINITION fail-fast，并阻止 _define 覆写。
2. scheduler._inject_host_class bind 块内重复绑定同名成员 → SEM_REDEFINITION
   （与 F1 模块成员重复 bind 检查同构）。
新增 3 个回归测试（test_host_binding.py TestHostClassBindingCompileTimeConflict：
bind方法vs-impl方法 / bind属性vs-impl方法 / 块内重复绑定）。

**M2（中，已修）**：HostClassBinding.instantiate 内联
`getattr(a,"to_native",None)` 拆箱（绕开 unbox 单一权威）且缺可调用实例透传。
修复：base.py 新增 `is_callable_object` + `unbox_for_native_call`（可调用实例
原样透传 + unbox 拆箱单一入口），proxy.py `_unbox` 与 host_class.instantiate 共用
——消除双轨拆箱写法。

**L1（已修）**：declarations.py 宿主类符号 UID 内联拼接 → 复用 uid.py
`symbol_uid(scope_uid(module), name)`（值不变，遵守"禁止调用方内联字符串"）。

**L2（已修）**：STAGE 5 水化与 VM 宿主 import 的 import+ImportError 包装重复且
错误类型漂移（RuntimeError vs InterpreterError）。修复：module_manager 抽
`import_host_py_module` 单一导入入口（统一 InterpreterError，与插件 loader
错误类型同构），两阶段共用。STAGE 5 的类成员存在性校验仍留 RuntimeError
（该文件 STAGE 5 惯用类型）。

**L3（已修）**：host_class 返回重包装用 `getattr(boxed,"py_obj",None)` 能力探测 →
改 `isinstance(boxed, IbNativeObject)` 协议化判别（native_module 顶层不 import
host_class，无循环）。

**L4（复核时已修，保留）**：属性成员类级 hasattr 误拒实例属性（__init__ 中
self.x=... 类上不可见）→ 仅方法做类级校验，属性走访问期契约（getattr(实例,name)
缺失 fail-fast），新增 queue.Queue 实例属性回归测试。

**L5（记录已知限制）**："POSITIONAL_OR_KEYWORD" 魔法字符串第三处散落
（interpreter.py 水化 param_meta），沿 F1 既有模式，随 F3 统一绑定面时收敛。

## 六、与主线衔接

F2 是 F1 的自然延伸（类型级绑定），F3 依赖 F2 完成（插件体系重构需要宿主类型
一等支持）。
