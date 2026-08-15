# 设计：retroactive implementation 推进——声明式 → 可为已有类型补充方法

> 临时设计文档（落地后删除）。任务：exp/protocol-kernel 分支，协议化内核大重构批次。
> 承接交接文档第 3.5 项："将 retroactive implementation 从'声明式'推进到'可为已有类型补充方法'"。

## 一、目标

`impl SomeProtocol for SomeType:` 目前是纯声明式（编译期校验类型已满足协议 + 记录 implements），
不支持补充缺失方法。本设计使其可携带**方法定义体**：为既有用户类补上协议所需方法，
不改动原类定义（retroactive 语义），协议满足检查在"类自身方法 + impl 补充方法"并集上进行。

## 二、语法

```
impl SomeProtocol for SomeType:
    func method_a(self, ...) -> Ret:
        ...body...
    func method_b(...) -> Ret:
        ...body...
```

- body 可选：空 body（仅声明，向后兼容现有用例）与带方法块二选一。
- v1 仅允许 `func` 方法定义；字段赋值 / 其它语句 → 编译期错误（fail-fast，明示 v1 边界）。

## 三、AST 与 Parser

- `IbImplDef` 新增 `body: List[IbStmt] = field(default_factory=list)`（仅函数定义）。
  （`docs/architecture/02_metadata_ast.md` 落地时补记。）
- Parser `impl_declaration`：冒号后若为行尾 → 空 body（现状）；若为缩进块 → 解析方法定义列表
  （复用 `function_declaration` 逐条解析，循环至块结束）。

## 四、编译期语义（四个 pass 全部镜像 visit_IbClassDef 的类上下文机制）

统一模式：impl 块 = "进入目标类的成员上下文，收集/解析/精化方法，恢复"。

1. **symbol_collection.visit_IbImplDef**：
   - 解析目标类符号（`self.symbol_table.resolve(type_name)`，当前模块作用域），要求
     `SymbolKind.CLASS` + `spec.kind == CLASS` + `Provenance.USER_DEFINED`（内置/泛型 → error）。
   - 推入目标类 `owned_scope`（类收集阶段已建），设 `current_class = 目标 spec`，visit body
     （方法 → FunctionSymbol + `_define` 成员同步 → 目标类 members 增 MethodMemberSpec）。
   - **冲突检测（单一权威）**：方法名已在目标类 owned_scope（类自身或先前 impl 定义）
     → `SEM_REDEFINITION` error 并跳过定义（类型检查阶段不再重复报）。
2. **symbol_resolution.visit_IbImplDef**：设 `current_class_symbol = 目标类符号`，推入目标
   owned_scope，visit body（方法 def 获得 self/super 注入 + 参数注册 + 函数体解析——
   复用 visit_IbFunctionDef 既有逻辑，node_to_symbol 映射与类方法同构）。
3. **type_resolution.resolve_IbImplDef**：推目标类 type_params 栈（v1 非泛型目标，恒空），resolve body。
4. **_declaration_visitors.visit_IbImplDef**（重写）：
   - 目标类 / 协议校验（沿用现状 resolve + kind 检查）；body 语句类型由 parser 保证
     （func / llm func），语义层不再重复检查。
   - 进入类上下文（current_class = 目标 spec、in_class_def=True、push owned_scope）
     → visit body 方法（复用 visit_IbFunctionDef：self 插入、签名精化、_sync_class_member）。
   - **协议校验后置**：required ⊆ 目标类 members（自身 + impl 补充）→ 满足才 append implements。
5. **binding_analysis**：`_analyze_node` / `_validate_node` 增加 IbImplDef 分支 → 递归 body
   （方法体内 llmexcept 绑定 / 意图注解校验与类方法一致）。

## 五、序列化与运行期水化

- `IbImplDef.body` 随模块语句通用序列化（语句 UID 列表）。
- **artifact_loader**：扫描模块根 body 的 `IbImplDef`（有 body）→ `impl_blocks` 列表
  （`(impl_stmt_uid, module_name)`）加入 `LoadedArtifact`。
- **interpreter._hydrate_user_classes**：impl 方法水化置于 **auto-init 第二 pass 之前**
  （impl 补 `__init__` 时 auto-init 经 `'__init__' in ib_cls.methods` 跳过，与"用户显式
  构造器优先"同语义）；运算符 dunder 方法与类方法路径同构显式绑定（`_bind_operator_method`）。
  对 body 每个方法 def：`node_to_symbol` → `_resolve_type_from_symbol` →
  `IbUserFunction(..., owner_class=ib_class)` → `ib_class.register_method(...)`。
  封印前注册（与类方法水化同阶段、同构），运行期方法查找走既有 `lookup_method`（含继承链）。
- `vm_handle_IbImplDef` 保持 no-op（编译期契约 + 水化注册；语句执行序不影响）。

## 六、v1 边界（fail-fast 明示，非静默）

| 边界 | 处置 |
|---|---|
| 目标非类 / 未解析 | error（现状已有） |
| 目标为内置类型（axiom）或非 USER_DEFINED | error |
| 目标为泛型类（type_params 非空） | error（方法体 T 解析与特化成员替换未接线，后续增量） |
| body 含非函数定义语句 | parser 拒绝（PAR_UNEXPECTED_TOKEN） |
| impl 方法名与类自身（或先前 impl）成员冲突 | error（SEM_REDEFINITION，符号收集阶段单一权威） |
| 跨模块目标（dotted name） | v1 不支持（单标识符解析；后续增量） |
| 协议本身缺失 / 非 PROTOCOL | error（现状已有） |
| LLM 方法（`llm func`） | **已支持**（parser 放开，语义/水化与类方法同构） |

## 七、测试计划（判别性）

1. impl 补方法 → 协议满足 + 语言级调用生效（含 self 读取字段、方法链）。
2. 协议方法未补全 → 编译期 error（原有语义保持）。
3. 冲突（类已有同名方法）→ error。
4. 非法目标（内置 int / 泛型类 / 未知名）→ error。
5. body 非方法语句 → error。
6. 空 body 纯声明式向后兼容（现有用例零回归）。
7. 继承链可见：父类 impl 方法对子类实例可用（lookup_method 走 parent）。
8. 序列化 round-trip：真实引擎（artifact 加载）路径下 impl 方法注册生效。
9. 协议 bound 交互：`class Box[T: Proto]` 以 impl 补方法后的类为实参（satisfies_protocol 生效）。
10. 泛型协议 `Container[int]` 特化 impl？——v1 只测非泛型协议；泛型协议目标实参映射
    属于 v1 边界之外（implements_args 无对应语法），明确拒绝或文档化。

## 八、self-grill 质询记录

- **为何 error 而非覆盖同名方法**：静默覆盖违 fail-fast；显式错误让用户选择改类或改 impl。
  继承链同名不冲突：子类新增 own 成员是合法 override 语义。
- **为何运行期注册而非编译期注入类 body**：不改用户 AST 结构；impl 块独立序列化；
  水化期注册与类方法水化同构（机制同构，design-philosophy §四）。
- **为何 v1 限制泛型/内置/跨模块**：目标 spec 可变性与 module 身份解析复杂度随三者上升；
  v1 聚焦"用户类补方法"核心价值；限制全部 fail-fast 明示并登记已知边界，非静默降级。
- **协议满足检查为何后置**：impl 补的方法是满足条件的一部分，先补后查才是正确时序；
  现状（先查后记录）在"纯声明式"下等价，带 body 后必须后置。
- **影响面核对**：class_spec.members 新增条目影响——协议满足检查（期望）、
  artifact spec 序列化/rehydrate（成员表多条目，运行期方法表由水化注册驱动，无冲突）、
  特化成员替换（泛型目标已拒，无波及）。
