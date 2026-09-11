# 内核接口契约重设计（使命 3 实施蓝图，2026-09-11）

> 本文件 = 使命 3（引擎级重构）的具体接口契约设计——审计结论 D1-D5 落为可实施契约。
> 分支 `kernel-interface-rebuild`（独立隔离分支，零风险确认后 merge unsafe-vibe-dev 即删）。
> 红线：语言语义（公理+contracts 语义错误集）不变；双内核协议（显式态无静默回退）；
> 8129af0a 之前资产（Rust 内核本体/前端/artifact 契约/diff 资产）复用。

---

## 一、新接口总览（engine ↔ kernel 契约面）

```
┌─ Python 侧（engine / kernels）────────────────────────────┐
│ IBCIEngine.execute                                        │
│   → ArtifactView（artifact 特征提取，一次解析）            │
│   → ArtifactRouter.can_execute(view)（能力查询 + 角检测）   │
│        ↓ 数据面源                                         │
│   → kernels.run_artifact_state(artifact, vars)            │
│        → (lines, typed_state, errors)                     │
│   → StateMaterializer（单一物化表：kind+declared→对象）     │
│   → 错误边界：RustRuntimeError（结构化）→ InterpreterError  │
│        （诊断码 = 单一权威 error_code_for_class）          │
├─ Rust 侧（ibci_ext）──────────────────────────────────────┤
│ capability()      → 能力声明（节点/内征/模块/未移植角）     │
│ run_artifact_state→ 唯一执行入口（typed 状态导出）          │
│ RustRuntimeError  → 结构化错误（class/code/line/col/msg）  │
│ call_top_level_function → 宿主 .call 函数值契约（无会话）   │
└───────────────────────────────────────────────────────────┘
```

## 二、契约 1：能力声明表（D1——替代路由谓词堆）

### Rust 侧（新 ibci-ext/src/capability.rs）

```rust
pub struct Capability {
    pub node_types: Vec<&'static str>,        // deserializer 可分发的节点类型（已有 node_types()）
    pub intrinsic_names: Vec<&'static str>,   // call_function 分发表 + 异常类 + meta 面（单一表）
    pub native_modules: Vec<&'static str>,    // Rust 原生承载模块
    pub unported_corners: Vec<CornerDecl>,    // 未移植语义角（Python 宿主）——随移植收缩
}
pub struct CornerDecl { pub feature: &'static str, pub reason: &'static str }
#[pyfunction] fn capability() -> PyResult<String>  // JSON 序列化返回
```

- **intrinsic_names 单一真相**：call_function 从 `match` 臂重构为**分发表**
  `const INTRINSICS: &[(&str, fn(&Interpreter, ...) -> ...)]`——名字列表由分发表派生，
  call_function 经表分发（机制同构，design-philosophy §四）；异常类 =
  `EXCEPTION_CLASSES` 常量数组（is_exception_class 引用同一数组）；meta 面
  （quote/eval）= 模块成员声明表。**消除 rust_intrinsic_names 手工清单与 match 臂
  的双真相（审计 3.4）**。
- **unported_corners 初始集**（Python 宿主语义角，审计三分类证据）：
  tuple_value_materialization / optional_instance_identity / meta_compile /
  kb_vec_payload_materialization / intrinsic_redefinition。随移植推进条目删除
  （消除后即从清单移除，路由自动放行）。

### Python 侧（新 core/runtime/kernels/capability.py）

- `ArtifactView`：artifact dict → 特征提取（一次解析）：`node_types()` /
  `intrinsic_names()`（node_to_symbol intrinsic:* 前缀）/ `imported_modules()` /
  `uses_corner(feature)`（角检测器注册表）。
- `SemanticCorner` 注册表：`{feature: (reason, detector)}`——tuple 物化检测 /
  Optional 实例同一性检测 / meta.compile 检测 / KB-vec 对象身份检测 / 内建名重定义
  检测（现 kernels/__init__.py 的 5 个扫描函数迁入，**注册式**非 if 链）。
- `ArtifactRouter.can_execute(view)` = 单一查询：节点⊆声明集 **且** 内征⊆声明集 **且**
  模块⊆原生集 **且** 无已用角。**零硬编码集合**（RUST_NATIVE_MODULES /
  _DATA_PLANE_EXCLUSIONS / _OBJECT_IDENTITY_INTRINSICS / _INTRINSIC_TYPE_NAMES
  全部入 Rust capability 或角注册表）。
- 新增角 = 注册表一行；移植角 = 删注册行 + Rust 声明集更新（单一变更点）。

## 三、契约 2：类型化错误（D3——替代字符串协议 + 正则 + 映射表）

### Rust 侧（ibci-ext/src/lib.rs / errors.rs）

```rust
#[pyclass(extends=PyException, module="ibci_ext")]
pub struct RustRuntimeError {
    #[pyo3(get)] error_class: String,   // 异常类名（ZeroDivisionError...）
    #[pyo3(get)] code: Option<String>,  // 诊断码（Rust 侧不映射——由 Python 单一权威）
    #[pyo3(get)] line: Option<i64>, #[pyo3(get)] column: Option<i64>,
    #[pyo3(get)] detail: String,
}
// 边界：Thrown{value: Error{class,message}, pos} → RustRuntimeError
//   （不再拼 "IBCI: uncaught exception: ...@line:col" 字符串 + 正则回拆）
```

- RecursionError 边界：class="RecursionError" 的结构化字段 → Python 侧直接判定
  （删字符串 contains 特判，审计 3.3）。

### Python 侧（core/engine.py + core/base/diagnostics）

- **诊断码单一权威**：`core/base/diagnostics/codes.py` 增
  `error_code_for_class(class_name: str) -> Optional[str]`（TypeError→RUN_TYPE_MISMATCH /
  ZeroDivisionError→RUN_DIVISION_BY_ZERO / IndexError|KeyError→RUN_INDEX_ERROR /
  AttributeError→RUN_ATTRIBUTE_ERROR / PermissionError→RUN_PERMISSION_ERROR）——
  functions.py `_runtime_error_code_for` 与 engine 边界**同源委托**（删 engine
  `_RUST_ERROR_CODES`，消除第二真相，审计 3.3）。
- engine 错误边界：捕获 RustRuntimeError → 读结构化字段 → InterpreterError(code,
  location=Location(file_path, line, column))；**零正则**。
- diff_harness 错误断言（消息子串）随使命 2 阶段 A 迁移至诊断码断言。

## 四、契约 3：typed 状态通道 + 单一物化（D2——替代镜像双路径 + repr 降级）

### Rust 侧（ibci-ext/src/lib.rs ibvalue_to_typed_json）

状态导出 = **typed value**（含类型标签，非 repr 字符串降级）：

```json
{"x": {"kind": "int", "value": 5},
 "f": {"kind": "function", "value": {"name": "f", "param_types": ["int"], "ret": "int"}},
 "q": {"kind": "quoted", "value": "1 + 2"},
 "v": {"kind": "vector", "value": [1.0, 2.0]},
 "k": {"kind": "knowledge", "value": null}}
```

- kinds：int/float/str/bool/none/list/dict/function/quoted/vector/knowledge/error。
- **消除 N1**（repr 字符串类型信息丢失 + 镜像再水化特判）：类型标签显式携带，
  Python 侧按 kind 物化，不再按 declared_type 猜形态。

### Python 侧（core/runtime/kernels/materialize.py）

- `StateMaterializer`：`MATERIALIZERS: dict[str, Callable[[value, declared_type], Any]]`
  数据驱动转换表——int/float/str/bool/none/list/dict = 原生直通；function =
  RustHostCallable（契约 4）；quoted = IbQuoted(source)；vector = IbVector；
  knowledge = IbKnowledge。**engine 零语义判断**（删 declared 白名单双路径 /
  quoted 特判 / _bind_container_specialization 复刻[容器特化绑定归物化表特化条目]）。
- `materialize_variable` 旁路删除（统一走物化表 + 正常 define 路径；物化后
  define_variable 的 _check_type 面 = 执行核心语义，Rust 侧移植后镜像检查面退役）。

## 五、契约 4：宿主 callable 统一协议（D4/D5——替代 WIP 会话 API）

- **删除**：open_session / session_call / session_release / SESSIONS 注册表 /
  RawSessionPtr / RustFunctionProxy / engine 第三分支（审计 3.6 全删）。
- **run_artifact_state = 唯一执行入口**（D5）。
- **函数值宿主调用**（新 `call_top_level_function(artifact_json, name, args_json)`）：
  无状态执行——反序列化 artifact → 执行模块（fresh）→ 调顶层函数 → 返回
  (result_json, output)。函数值物化 = `RustHostCallable(artifact_json, name)` 代理，
  `.call(receiver, args)` 委托该入口。
- **语义边界**（登记 divergence.py 注册表 DIVERGENCE）：宿主 .call 数据面函数值 =
  纯函数契约（现有契约测试 = 纯函数，审计实证）；闭包/模块可变态跨调用状态 =
  未支持角（corner: host_call_closure_state，涉及源路由 Python——与 Python VM
  语义一致）。跨调用状态若为必需契约 = 后续按 typed 通道 + 协议显式设计，不重开
  会话通道。

## 六、实施顺序（分支内增量，每步门 = 受影响子集 + smoke + diff 零差异 + commit）

1. **E1（D3 先行，最小自洽）**：Rust RustRuntimeError pyclass + 边界结构化 +
   engine 结构化消费 + error_code_for_class 单一权威 + 删 _RUST_ERROR_CODES/正则/
   contains 特判。
2. **E2（D1）**：Rust capability() + INTRINSICS 分发表 + EXCEPTION_CLASSES +
   Python ArtifactView/角注册表/ArtifactRouter + 删 8 谓词/4 集合。
3. **E3（D2）**：Rust ibvalue_to_typed_json + Python StateMaterializer +
   删镜像双路径/旁路/特判。
4. **E4（D4/D5）**：删会话 API + call_top_level_function + RustHostCallable +
   divergence 登记。
5. **E5（收束）**：全量 pytest 零回归（4306/2/1 基线——2 failed 须转为 pass 或
   按新契约处理）+ 复核放行 + merge unsafe-vibe-dev 删分支 + 使命 2 阶段 A 启动。

## 七、验证与红线

- 每步：`bash scripts/build_rust_ext.sh`（pin CARGO）→ 受影响子集 + smoke
  （tests/contracts+tests/compiler）→ diff_harness 全绿 → commit（描述性中文）。
- 差分等价门：34 语料四级差分 + 五池 artifact 面零差异（Rust 执行语义不变）。
- 禁 push；main 永不触碰；大范围破坏性重构走本隔离分支。
