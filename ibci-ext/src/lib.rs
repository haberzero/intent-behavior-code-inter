//! ibci-ext：IBC-Inter Rust 内核（pyo3 扩展）——双内核协议的 Rust 执行后端。
//!
//! 双内核协议（核心设计裁定）：Python 内核 = 一等实验内核（默认）；Rust 内核 =
//! 生产快路径（显式 opt-in，无静默回退）。两内核共享同一 AST 契约 + contracts
//! 层语义红线。本 crate = Rust 内核的执行体（GIL-free，py.allow_threads 释放
//! GIL）。
//!
//! 当前形态：构建链 + Rust lexer + Rust parser + 反序列化器 + 执行核心
//! （tree-walking 解释器）+ 并发解除（GIL-free 并行执行：run_artifacts_parallel
//! 无状态批处理 + TaskPool 有状态任务池，Rust 线程 py.allow_threads 释放 GIL 真
//! 并行）——执行核心消费 Python 前端产出的序列化 artifact（FlatSerializer JSON）
//! 执行，数据面经差分 harness 与 Python 参考内核逐条比对（34 语料全级差分等价：
//! token/AST/反序列化/数据面 + 符号表/类型表；性能 23–30x；GIL-free 并行 4 线程
//! ≈3.3x）。kernel_info.stage = 4（并发解除就绪），status =
//! "concurrency-core"（并发核心就绪，数据面经 run_artifact + 并行执行经
//! run_artifacts_parallel/TaskPool 可用；run[script 入口]待 Rust 前端[语义层]移植
//! 后升 "ready" 生效）。

mod deserializer;
mod errors;
mod interpreter;
mod plugins;
mod kb;
mod intrinsic_symbols;
mod lexer;
mod node_serializer;
mod parser;
mod scope_serializer;
mod serialization;
mod symbol_resolver;
mod task_pool;
mod type_inference;

use pyo3::exceptions::{PyNotImplementedError, PyRuntimeError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use pyo3::Py;

/// crate 版本（构建链自检面）。
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// IBC 源码 → token 流（Rust lexer；对齐 Python `core/compiler/lexer`）。
///
/// 返回 list of dict（每项 = {type, value, line, column, end_line,
/// end_column, is_at_line_start}）——差分 harness 经此与 Python lexer token
/// 流逐条比对（type 名 + value + line/column 等价）。
#[pyfunction]
fn lex(script: &str, py: Python<'_>) -> PyResult<Py<PyList>> {
    let tokens = lexer::lex(script);
    let list = PyList::empty(py);
    for t in tokens {
        let d = PyDict::new(py);
        d.set_item("type", t.type_.name())?;
        d.set_item("value", t.value)?;
        d.set_item("line", t.line)?;
        d.set_item("column", t.column)?;
        d.set_item("end_line", t.end_line)?;
        d.set_item("end_column", t.end_column)?;
        d.set_item("is_at_line_start", t.is_at_line_start)?;
        list.append(d)?;
    }
    Ok(list.unbind())
}

/// IBC 源码 → AST structure 规范形态（Rust parser；对齐 Python parser 的 AST
/// structure）。AST 级差分门：经此与 Python `ast_dump(include_positions=False)`
/// 逐字节比对。
#[pyfunction]
fn parse_struct(script: &str) -> String {
    parser::parse_struct(script)
}

/// 序列化 artifact（JSON dict 字符串）→ 反序列化 AST 完整形态（含位置）。
/// 执行核心的输入契约：Rust 侧消费 Python 前端产出的 artifact（含语义层输出）。
#[pyfunction]
fn deserialize_struct(artifact_json: &str) -> String {
    deserializer::deserialize_struct(artifact_json)
}

/// artifact JSON → 符号表规范表示（node → symbol 解析，按 node_uid 排序）。
/// 消费完整 artifact 的 symbols 池 + node_to_symbol 侧表（执行核心的完整 artifact
/// 消费——不止 nodes 池）。
#[pyfunction]
fn symbol_table(artifact_json: &str) -> String {
    deserializer::symbol_table(artifact_json).unwrap_or_default()
}

/// artifact JSON → 类型表规范表示（node → type 解析，按 node_uid 排序）。
/// 消费完整 artifact 的 types 池 + node_to_type 侧表（执行核心的完整 artifact
/// 消费——语义层类型输出）。
#[pyfunction]
fn type_table(artifact_json: &str) -> String {
    deserializer::type_table(artifact_json).unwrap_or_default()
}

/// CPS dispatch table：执行核心分发的节点类型（反序列化 match 覆盖的 AST 节点）。
/// 差分 harness 经此与 Python VM dispatch table（53 节点）比对覆盖差（优化目标：
/// 对齐全量节点分发）。
#[pyfunction]
fn node_types(py: Python<'_>) -> PyResult<Py<PyList>> {
    let list = PyList::empty(py);
    for nt in deserializer::node_types() {
        list.append(nt)?;
    }
    Ok(list.unbind())
}

/// 序列化 UID（全量 Rust 化·序列化面）：node_uid = `node_<sha256[:16]>`（内容
/// 确定性，AST 节点 UID）；与 Python core/base/uid.py 的 node_uid 逐条差分等价。
#[pyfunction]
fn node_uid(content: &str) -> String {
    serialization::node_uid(content)
}

/// 类型 UID：`type_<module>.<name>`（root 模块退化 `type_root.<name>`）；与 Python
/// type_uid 差分等价。参数序（name 必需在前，module_path Option 在后）适配 pyo3
/// （Option 后不可跟必需参数）；Python type_uid(module_path, name) 经差分 harness
/// 按此序调用。
#[pyfunction]
fn type_uid(name: &str, module_path: Option<&str>) -> String {
    serialization::type_uid(module_path, name)
}

/// 文本资产 UID：`asset_<sha256[:16]>`（内容确定性）；与 Python asset_uid 差分等价。
#[pyfunction]
fn asset_uid(text: &str) -> String {
    serialization::asset_uid(text)
}

/// 节点数据序列化（全量 Rust 化·序列化面）：IBC 源码 → Rust AST → 节点池（uid →
/// node_data）。返回 (root_uid, node_pool_json)——node_pool_json = 节点池的 JSON 串
/// （serde_json）。差分 harness 经此与 Python FlatSerializer 节点池逐条比对。
#[pyfunction]
fn serialize_nodes(source: &str) -> PyResult<(String, String)> {
    let module = parser::parse_to_module(source);
    let mut serializer = node_serializer::NodeSerializer::new();
    let (root_uid, node_pool) = serializer.serialize_module(&module);
    let pool_json = serde_json::to_string(&node_pool)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok((root_uid, pool_json))
}

/// scope 符号解析（全量 Rust 化·语义层启动）：IBC 源码 → Rust AST → scope 符号池
/// （uid → sym_data，用户定义符号[scope_<module>:<name>]）。返回符号池 JSON 串。差分
/// harness 经此与 Python 语义层 scope 符号逐条比对（区别于 intrinsic 符号[内置类型/
/// 方法]——归语义层 intrinsic 符号表 Rust 移植后续）。
#[pyfunction]
fn resolve_symbols(source: &str) -> PyResult<String> {
    let module = parser::parse_to_module(source);
    let mut resolver = symbol_resolver::SymbolResolver::new();
    let symbols = resolver.resolve_module(&module);
    serde_json::to_string(symbols)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

/// intrinsic 符号表——内置类型（全量 Rust 化·语义层）：返回 42 个 IBC 内置类型的
/// intrinsic 符号池（uid → sym_data，CLASS 符号）。差分 harness 经此与 Python intrinsic
/// 符号表内置类型逐条比对（内置函数/方法/模块归后续增量）。
#[pyfunction]
fn intrinsic_type_symbols() -> PyResult<String> {
    let symbols = intrinsic_symbols::builtin_type_symbols();
    serde_json::to_string(&symbols)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

/// intrinsic 符号表完整（全量 Rust 化·语义层）：返回 63 个 intrinsic 符号池
/// （42 内置类型 CLASS + 19 内置函数 FUNCTION + 2 内置模块 MODULE，uid → sym_data）。
/// 差分 harness 经此与 Python intrinsic 符号表逐条比对（method = sym_anon_* 归类型解析
/// 后续）。
#[pyfunction]
fn intrinsic_symbol_table() -> PyResult<String> {
    let symbols = intrinsic_symbols::builtin_intrinsic_symbols();
    serde_json::to_string(&symbols)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

/// intrinsic 类型池（66 non-generic KERNEL_NATIVE 类型基础字段）——Rust 静态表（对齐
/// Python registry/prelude 固有类型集）。差分 harness 经此与 Python types 池比对。
#[pyfunction]
fn intrinsic_type_pool() -> PyResult<String> {
    let types = intrinsic_symbols::builtin_intrinsic_types();
    serde_json::to_string(&types)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

/// scope 池（全量 Rust 化·artifact 产出：scopes 池）——顶层[63 intrinsic + 用户顶层] +
/// 函数 scope[用户内符号，parent = 定义处 scope]。差分 harness 经此与 Python scopes 池
/// 比对（Rust ⊆ Python）。
#[pyfunction]
fn scope_pool(source: &str) -> PyResult<String> {
    let scopes = scope_serializer::scope_pool(source);
    serde_json::to_string(&scopes)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

/// node_to_loc 侧表（全量 Rust 化·artifact 产出：位置侧表）：node_uid →
/// {file_path: null, line, column}。file_path=null（Rust 无临时文件，架构自然）。
#[pyfunction]
fn node_to_loc(source: &str) -> PyResult<String> {
    serde_json::to_string(&node_serializer::node_to_loc(source))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

/// node_to_type 侧表（全量 Rust 化·artifact 产出：节点级 type_uid）——统一遍历产出
/// （复用 type_inference：node_uid → type_uid）。差分 harness 经此与 Python node_to_type 比对。
#[pyfunction]
fn node_to_type(source: &str) -> PyResult<String> {
    let module = parser::parse_to_module(source);
    let mut serializer = node_serializer::NodeSerializer::new();
    let (_root, _nodes) = serializer.serialize_module(&module);
    serde_json::to_string(&serializer.node_to_type_map())
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

/// node_to_symbol 侧表（全量 Rust 化·artifact 产出：节点级符号 uid）——统一遍历产出
/// （node_uid → symbol uid：Name 引用[scope 链用户定义 / intrinsic 63 固定集] +
/// IbAssign/IbFunctionDef/IbArg/IbAlias/for 目标 定义节点）。差分 harness 经此与
/// Python node_to_symbol 比对。
#[pyfunction]
fn node_to_symbol(source: &str) -> PyResult<String> {
    let module = parser::parse_to_module(source);
    let mut serializer = node_serializer::NodeSerializer::new();
    let (_root, _nodes) = serializer.serialize_module(&module);
    serde_json::to_string(&serializer.node_to_symbol_map())
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

/// 完整 artifact（全量 Rust 化·artifact 产出：Rust 独立完整 artifact 闭环）——
/// source → 完整 artifact JSON（顶层形态与 Python FlatSerializer.serialize_artifact
/// 同构：entry_module / global_symbols / modules / pools[nodes/symbols/scopes/
/// types/assets]）。组装：NodeSerializer 统一遍历[nodes + node_to_type/symbol +
/// 泛型类型 + 用户函数类型 + __string_exec__ 用户模块类型] + scope_serializer
/// [scopes 池] + SymbolResolver[scope 符号] + intrinsic_symbols[63 intrinsic 符号 +
/// 66 固定类型条目 + 泛型条目 + 成员符号]。差分 harness 经此与 Python 完整 artifact
/// 全池比对。
#[pyfunction]
/// Rust artifact 组装（source → artifact JSON——纯 CPU 面；full_artifact
/// pyfunction 与 rust_run_source 全管线共享单一权威源）。
fn assemble_artifact_json(source: &str) -> String {
    use serde_json::Map as JMap;
    use serde_json::Value;
    let module = parser::parse_to_module(source);

    // 1) NodeSerializer 统一遍历：nodes + 侧表 + 泛型/用户面
    let mut ns = node_serializer::NodeSerializer::new();
    let (root_uid, nodes) = ns.serialize_module(&module);
    // 泛型闭包先取（种子含 node_to_type 值——node_to_type_map 为 mem::take 取走
    // 语义，顺序敏感）
    let generics = ns.generic_type_names();
    let node_to_type = ns.node_to_type_map();
    let node_to_symbol = ns.node_to_symbol_map();
    let module_type = ns.entry_module_type_entry();
    let module_member_kinds = ns.entry_module_member_kinds();
    let user_function_types = ns.user_function_entries();

    // 2) scopes 池 + scope 符号
    let scopes = scope_serializer::scope_pool(source);
    let mut sr = symbol_resolver::SymbolResolver::new();
    let scope_symbols: JMap<String, Value> = sr
        .resolve_module(&module)
        .iter()
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();

    // 3) types 池：66 固定[全字段，IMPORT_GATED 条件包含：eval/quote 仅模块属性
    //    调用时进池，meta 仅 import 时进池——Python 实证] + 泛型[payload + 继承
    //    成员表] + 用户函数 + __string_exec__[用户顶层符号成员]
    // types 池键 = 类型 uid（type_root.<name>——Python types 池键形态）
    let called_mf = ns.called_module_functions();
    let imported = ns.imported_modules();
    let mut types: JMap<String, Value> = intrinsic_symbols::builtin_intrinsic_types()
        .into_iter()
        .filter(|(k, _)| match k.as_str() {
            "eval" | "quote" => called_mf.contains(k),
            "meta" => imported.contains(k),
            _ => true,
        })
        .map(|(name, entry)| (format!("type_root.{}", name), entry))
        .collect();
    for name in &generics {
        if let Some(e) = intrinsic_symbols::generic_type_entry(name) {
            types.insert(format!("type_root.{}", name), e);
        }
    }
    for (name, entry) in user_function_types {
        types.insert(format!("type_root.{}", name), entry);
    }
    types.insert("type_root.__string_exec__".to_string(), module_type);
    // bound_method 共享类型 last-wins 改写（无方法属性访问 = 默认 ([], void)）
    if let Some((params, ret)) = ns.bound_method_sig() {
        if let Some(bm) = types.get_mut("type_root.bound_method") {
            bm["param_type_names"] =
                Value::Array(params.into_iter().map(Value::String).collect());
            bm["return_type_name"] = Value::String(ret);
        }
    }

    // 4) node_to_loc 侧表（节点池位置字段——全节点，file_path=null）
    let mut node_to_loc: JMap<String, Value> = JMap::new();
    for (uid, nd) in nodes.iter() {
        let mut loc = JMap::new();
        loc.insert("file_path".into(), Value::Null);
        loc.insert(
            "line".into(),
            nd.get("lineno").cloned().unwrap_or(Value::Null),
        );
        loc.insert(
            "column".into(),
            nd.get("col_offset").cloned().unwrap_or(Value::Null),
        );
        node_to_loc.insert(uid.clone(), Value::Object(loc));
    }

    // 5) symbols 池：63 intrinsic + scope 符号 + 成员符号（canonical 内容条目）
    let mut symbols: JMap<String, Value> = intrinsic_symbols::builtin_intrinsic_symbols()
        .into_iter()
        .collect();
    for (uid, sym) in scope_symbols.iter() {
        symbols.insert(uid.clone(), sym.clone());
    }
    let mut module_kinds: std::collections::BTreeMap<String, String> = module_member_kinds
        .into_iter()
        .map(|(n, k)| (n, k))
        .collect();
    for (tname, tval) in types.iter() {
        if let Some(members) = tval.get("members_uids").and_then(|m| m.as_object()) {
            for (mname, muid) in members {
                let kind = if tname == "type_root.__string_exec__" {
                    module_kinds.get(mname).cloned().unwrap_or_else(|| "field".to_string())
                } else {
                    // 固定/泛型成员：基类成员表 kind（泛型继承基类表；基类名 = 条目
                    // name 字段[键 = 类型 uid type_root.<name>]）
                    let entry_name = tval
                        .get("name")
                        .and_then(|v| v.as_str())
                        .unwrap_or(tname);
                    let base = crate::type_inference::parse_container(entry_name).0;
                    crate::intrinsic_symbols::METHOD_MEMBERS
                        .iter()
                        .find(|(t, _)| *t == base)
                        .and_then(|(_, ms)| ms.iter().find(|(n, _)| *n == mname))
                        .map(|(_, k)| k.to_string())
                        .unwrap_or_else(|| "method".to_string())
                };
                let mut m = JMap::new();
                m.insert("uid".into(), muid.clone());
                m.insert("name".into(), Value::String(mname.clone()));
                m.insert("kind".into(), Value::String(kind));
                m.insert("type_uid".into(), Value::Null);
                m.insert("node_uid".into(), Value::Null);
                m.insert("owned_scope_uid".into(), Value::Null);
                m.insert("metadata".into(), Value::Object(JMap::new()));
                symbols.insert(muid.as_str().unwrap().to_string(), Value::Object(m));
            }
        }
    }

    // 6) 池 + module 条目 + 顶层
    let pools: JMap<String, Value> = JMap::from_iter([
        ("nodes".into(), Value::Object(nodes.into_iter().collect())),
        ("symbols".into(), Value::Object(symbols.clone())),
        ("scopes".into(), Value::Object(scopes.into_iter().collect())),
        ("types".into(), Value::Object(types.clone())),
        ("assets".into(), Value::Object(JMap::new())),
    ]);
    let side_tables: JMap<String, Value> = JMap::from_iter([
        (
            "node_to_symbol".into(),
            Value::Object(
                node_to_symbol
                    .into_iter()
                    .map(|(k, v)| (k, Value::String(v)))
                    .collect(),
            ),
        ),
        (
            "node_to_type".into(),
            Value::Object(
                node_to_type
                    .into_iter()
                    .map(|(k, v)| (k, Value::String(v)))
                    .collect(),
            ),
        ),
        ("node_to_loc".into(), Value::Object(node_to_loc.into_iter().collect())),
    ]);
    let module_entry: JMap<String, Value> = JMap::from_iter([
        ("import_star_members".into(), Value::Object(JMap::new())),
        ("pools".into(), Value::Object(pools.clone())),
        ("root_node_uid".into(), Value::String(root_uid)),
        ("root_scope_uid".into(), Value::String("scope___string_exec__".to_string())),
        ("side_tables".into(), Value::Object(side_tables)),
    ]);
    let modules: JMap<String, Value> =
        JMap::from_iter([("__string_exec__".to_string(), Value::Object(module_entry))]);
    let artifact: JMap<String, Value> = JMap::from_iter([
        ("entry_module".into(), Value::String("__string_exec__".to_string())),
        ("global_symbols".into(), Value::Object(JMap::new())),
        ("modules".into(), Value::Object(modules)),
        ("pools".into(), Value::Object(pools)),
    ]);
    // serde_json::to_string 对本 Value（有限整数/字符串/结构）实质不可失败
    // （仅非有限浮点序列化报错——值域无浮点条目）
    serde_json::to_string(&Value::Object(artifact)).unwrap()
}

#[pyfunction]
fn full_artifact(source: &str) -> PyResult<String> {
    Ok(assemble_artifact_json(source))
}

/// 全 Rust 管线（主线 ⑦"全量转向 Rust"闭环——源 → 执行）：IBC 源 → Rust
/// lexer/parser → Rust artifact 组装（assemble_artifact_json）→ Rust 反序列化
/// → Rust 解释器执行。全程不消费 Python 前端（消除"消费 Python 前端 JSON"
/// 输入边界——双内核输入面收敛为 Rust 单通道）；桥接 = 仅 LLM/意图 IO 边界。
/// 差分门：数据面与 Python 参考内核逐字节等价（34 语料 + 全探针面）。
#[pyfunction]
fn rust_run_source(
    source: &str,
    bridge: Option<Bound<'_, PyAny>>,
    py: Python<'_>,
) -> PyResult<Py<PyList>> {
    let bridge_owned = bridge.map(|b| b.unbind());
    let source_owned = source.to_string();
    // 全 CPU 面（Rust 前端 + Rust 执行）释放 GIL
    let artifact_json = assemble_artifact_json(&source_owned);
    let result = py.allow_threads(|| {
        interpreter::run_artifact(&artifact_json, bridge_owned)
    });
    let lines = match result {
        Ok(l) => l,
        Err(payload) => return Err(payload.to_pyerr()),
    };
    let list = PyList::empty(py);
    for line in lines {
        list.append(line)?;
    }
    Ok(list.unbind())
}

/// 内核元数据（name / stage / status）——差分 harness 的接入点：harness 经此
/// 探明 Rust 内核状态。stage = 当前阶段（4 = 并发解除[GIL-free 并行执行 + 任务池]）；
/// status = 就绪门（"concurrency-core" = 并发核心就绪[GIL-free 并行执行
/// [run_artifacts_parallel + TaskPool] + 数据面经 run_artifact 可用]；"ready" =
/// 全量内核就绪[run script 入口生效，待 Rust 前端[语义层]移植]）。
#[pyfunction]
fn kernel_info(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("name", "rust")?;
    dict.set_item("stage", 4u32)?;
    dict.set_item("status", "concurrency-core")?;
    Ok(dict)
}

/// 执行 IBCI 源码（Rust 内核全量入口：script → 数据面）。
///
/// 执行核心已落地（经 run_artifact 消费 artifact 执行），但全量 script 入口需
/// Rust 前端（lexer + parser + 语义层）——语义层移植未落地，故 script 入口
/// **显式 NotImplemented（无静默回退）**。双内核协议：Rust 内核全量入口未就绪
/// = 显式报错，不悄悄切 Python 内核（kernel_info.status == "ready" 前 run 恒
/// NotImplemented；执行核心就绪面经 run_artifact 单独验证）。
#[pyfunction]
fn run(_script: &str) -> PyResult<String> {
    Err(PyNotImplementedError::new_err(
        "ibci_ext.run: Rust 内核全量 script 入口待前端（语义层）移植；执行核心就绪面 \
         经 ibci_ext.run_artifact 验证（双内核协议 = 无静默回退）",
    ))
}

/// 执行核心入口：序列化 artifact（JSON）→ 执行 → 数据面（print 输出列表）。
/// 消费 Python 前端产出的 artifact（含语义层输出）；迁移期策略（执行核心 Rust
/// + 前端 Python）。Rust 语义层移植后 = 全量 Rust 前端 + 执行核心。
/// bridge = host service 桥接（KB 操作经此委托；None = 无宿主服务，非 KB 面）。
///
/// **CPU+IO 真并行（GIL-free）**：解释执行（CPU 工作）经 `py.allow_threads`
/// 释放 GIL——多执行核心可真正并行（非协作式轮转）；IO 工作（宿主服务）经
/// `Python::with_gil` 重取 GIL 协作式推进。纯 CPU artifact（无 bridge）全程 GIL
/// 释放；含宿主服务的 artifact 仅在宿主操作时重取 GIL。
#[pyfunction]
fn run_artifact(
    artifact_json: &str,
    bridge: Option<Bound<'_, PyAny>>,
    py: Python<'_>,
) -> PyResult<Py<PyList>> {
    let bridge_owned = bridge.map(|b| b.unbind());
    // 持有 JSON 所有权（不跨 GIL 释放借用 Python 内存）
    let json_owned = artifact_json.to_string();
    // CPU 工作（解释执行）释放 GIL——CPU+IO 真并行地基
    let lines = match py
        .allow_threads(|| interpreter::run_artifact(&json_owned, bridge_owned))
    {
        Ok(l) => l,
        Err(payload) => return Err(payload.to_pyerr()),
    };
    let list = PyList::empty(py);
    for line in lines {
        list.append(line)?;
    }
    Ok(list.unbind())
}

/// Python 对象 → JSON（⑦ 切换门变量注入面 GIL 侧：原生数据值 = 原生 JSON
/// 形态[int→整数 number / float→浮点 number / str / bool[先于 int 检查] /
/// None→null / list+tuple→array / dict→object]；非数据值 = 显示形态字符串
/// [边界值——str() 契约]）。
fn py_to_json(v: &Bound<'_, PyAny>) -> PyResult<serde_json::Value> {
    use serde_json::Value;
    if v.is_none() {
        return Ok(Value::Null);
    }
    if v.is_instance_of::<pyo3::types::PyBool>() {
        return Ok(Value::Bool(v.extract::<bool>()?));
    }
    if let Ok(i) = v.extract::<i64>() {
        return Ok(Value::from(i)); // PyInt（bool 已先检查）
    }
    if let Ok(f) = v.extract::<f64>() {
        return Ok(Value::from(f));
    }
    if let Ok(s) = v.extract::<String>() {
        return Ok(Value::String(s));
    }
    if v.is_instance_of::<PyDict>() {
        let d = v.downcast::<PyDict>().unwrap();
        let mut obj = serde_json::Map::new();
        for (k, val) in d {
            // JSON 对象键 = 字符串：str 键原生，其余键 = 显示形态
            let key = match k.extract::<String>() {
                Ok(s) => s,
                Err(_) => k.str()?.to_string_lossy().into_owned(),
            };
            obj.insert(key, py_to_json(&val)?);
        }
        return Ok(Value::Object(obj));
    }
    if v.is_instance_of::<PyList>() || v.is_instance_of::<pyo3::types::PyTuple>() {
        let mut arr = Vec::new();
        for item in v.try_iter()? {
            arr.push(py_to_json(&item?)?);
        }
        return Ok(Value::Array(arr));
    }
    // 边界值 = 显示形态（str() 契约——初始变量面 = 原生数据值，非数据值
    // 此路径不出现[登记]）
    Ok(Value::String(v.str()?.to_string_lossy().into_owned()))
}

/// JSON → IbValue（⑦ 切换门变量注入面线程侧：整数 number→Int / 浮点
/// number→Float / str→Str / bool / null / array→List / object→Dict[str
/// 键]——纯 CPU 面，Send 安全）。
fn json_to_ibvalue(v: &serde_json::Value) -> interpreter::IbValue {
    use interpreter::IbValue;
    match v {
        serde_json::Value::Null => IbValue::None_,
        serde_json::Value::Bool(b) => IbValue::Bool(*b),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                IbValue::Int(i)
            } else {
                IbValue::Float(n.as_f64().unwrap_or(0.0))
            }
        }
        serde_json::Value::String(s) => IbValue::Str(s.clone()),
        serde_json::Value::Array(arr) => {
            let items: Vec<IbValue> = arr.iter().map(json_to_ibvalue).collect();
            IbValue::list_new(items)
        }
        serde_json::Value::Object(obj) => {
            let pairs: Vec<(IbValue, IbValue)> = obj
                .iter()
                .map(|(k, val)| (IbValue::Str(k.clone()), json_to_ibvalue(val)))
                .collect();
            IbValue::dict_new(pairs)
        }
    }
}

// --------------------------------------------------------------------------- //
/// Python 对象 → PluginValue（pyo3 边界直接提取——无序列化层；P2 typed 精神：
/// 值面 = 标量 int/float/bool/None；嵌套容器 = 显式错误[R6-1 值面]）。
fn py_to_plugin_value(obj: &Bound<'_, PyAny>) -> PyResult<ibci_sdk::PluginValue> {
    use ibci_sdk::PluginValue;
    if obj.is_none() {
        return Ok(PluginValue::None_);
    }
    if let Ok(b) = obj.extract::<bool>() {
        return Ok(PluginValue::Bool(b));
    }
    if let Ok(i) = obj.extract::<i64>() {
        return Ok(PluginValue::Int(i));
    }
    if let Ok(f) = obj.extract::<f64>() {
        return Ok(PluginValue::Float(f));
    }
    Err(pyo3::exceptions::PyValueError::new_err(
        "插件实参须为标量（int/float/bool/null）——嵌套容器后续增量",
    ))
}

/// PluginValue（标量结果）→ Python 对象（pyo3 边界直接构造）。
fn plugin_value_to_py(py: Python<'_>, v: &ibci_sdk::PluginValue) -> PyObject {
    use ibci_sdk::PluginValue;
    use pyo3::IntoPy;
    match v {
        PluginValue::None_ => py.None(),
        PluginValue::Bool(b) => b.into_py(py),
        PluginValue::Int(i) => i.into_py(py),
        PluginValue::Float(f) => f.into_py(py),
        // 结果面后续增量（Str/List 所有权纪律未定前不开放）
        PluginValue::Str(..) | PluginValue::List(..) => py.None(),
    }
}

/// 加载外部 Rust 插件（cdylib，ibci-sdk 协议）——注册其函数入内核插件注册表。
#[pyfunction]
fn load_plugin(path: &str) -> PyResult<usize> {
    plugins::load(path).map_err(PyRuntimeError::new_err)
}

/// 调用已注册插件函数（args = 原生标量列表——直接提取，无序列化层）。
#[pyfunction]
fn call_plugin(py: Python<'_>, name: &str, args: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let items = args.downcast::<pyo3::types::PyList>()?;
    let mut pv_args: Vec<ibci_sdk::PluginValue> = Vec::with_capacity(items.len());
    for item in items.iter() {
        pv_args.push(py_to_plugin_value(&item)?);
    }
    let result = plugins::call(name, &pv_args).map_err(PyRuntimeError::new_err)?;
    Ok(plugin_value_to_py(py, &result))
}

#[pyfunction]
fn rust_intrinsic_names(py: Python<'_>) -> PyResult<Py<PyList>> {
    // 派生自 interpreter 内征分发表（INTRINSICS + EXCEPTION_CLASSES + meta
    // 面）——单一权威源，杜绝"清单 vs 分发臂"双真相漂移（审计 3.4）
    let names = interpreter::intrinsic_names();
    let list = PyList::empty(py);
    for n in names {
        list.append(n)?;
    }
    Ok(list.unbind())
}

/// 内核能力声明（P1 协议——架构 v2 R0 §三）：node_types / intrinsic_names /
/// native_modules / unported_corners[{feature, reason}] JSON。路由判定 =
/// 本声明的查询结果（Python 侧零谓词堆零硬编码集合）；unported_corners 随
/// 宿主 .call 契约入口（P4 协议）：顶层函数值无状态调用——反序列化 →
/// 执行模块[fresh] → 按名调用（纯函数契约；DIVERGENCE 登记
/// host_call_closure_state）。
#[pyfunction]
fn call_top_level_function(
    artifact_json: &str,
    name: &str,
    args_json: &str,
    py: Python<'_>,
) -> PyResult<(Py<PyAny>, Py<PyList>)> {
    // 宿主 .call 契约（无会话通道）：反序列化 → 执行模块[fresh] → 按名调用
    // 顶层函数（纯函数契约——DIVERGENCE 登记 host_call_closure_state）。
    let json_owned = artifact_json.to_string();
    let name_owned = name.to_string();
    let args_owned = args_json.to_string();
    let (result_json, out): (String, Vec<String>) = match py.allow_threads(
        || -> Result<(String, Vec<String>), errors::ErrorPayload> {
            let module = match deserializer::deserialize_module(&json_owned) {
                Some(m) => m,
                None => {
                    return Err(errors::ErrorPayload {
                        class: "ArtifactDeserializeError".to_string(),
                        detail: "artifact 反序列化失败".to_string(),
                        pos: None,
            code: None,
                    })
                }
            };
            let interp = interpreter::Interpreter::new();
            let args: Vec<interpreter::IbValue> =
                match serde_json::from_str::<serde_json::Value>(&args_owned) {
                    Ok(serde_json::Value::Array(arr)) => {
                        arr.iter().map(json_to_ibvalue).collect()
                    }
                    Ok(_) => {
                        return Err(errors::ErrorPayload {
                            class: "TypeError".to_string(),
                            detail: "args 须为 JSON 数组".to_string(),
                            pos: None,
            code: None,
                        })
                    }
                    Err(_) => Vec::new(),
                };
            let (result, out) = interp
                .run_module_call_function(&module, &name_owned, args)
                .map_err(errors::ErrorPayload::from_thrown)?;
            Ok((interpreter::ibvalue_to_json(&result).to_string(), out))
        },
    ) {
        Ok(r) => r,
        Err(payload) => return Err(payload.to_pyerr()),
    };
    let result_py: Py<PyAny> = pyo3::types::PyString::new(py, &result_json).into_py(py);
    let list = PyList::empty(py);
    for line in out {
        list.append(line)?;
    }
    Ok((result_py, list.unbind()))
}

#[pyfunction]
fn capability() -> PyResult<String> {
    // node_types = 反序列化器可处理集 − 对象系统执行排除集（IbClassDef/
    // IbLambdaExpr——Python 宿主承载；审计 3.1 _DATA_PLANE_EXCLUSIONS 入清单）
    let mut node_types: Vec<&str> = deserializer::node_types();
    node_types.retain(|t| *t != "IbClassDef" && *t != "IbLambdaExpr");
    let cap = serde_json::json!({
        "node_types": node_types,
        "intrinsic_names": interpreter::intrinsic_names(),
        // 内建符号全集（42 类型 + 19 函数 + 2 模块）——内建名重定义角检测用
        "intrinsic_symbol_names": intrinsic_symbols::intrinsic_names(),
        "native_modules": ["meta"],
        "unported_corners": [
            {
                "feature": "meta_compile",
                "reason": "meta.compile 属性调用（编译器访问面）——Python 宿主",
            },
        ],
    });
    Ok(serde_json::to_string(&cap).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(e.to_string())
    })?)
}

/// 执行核心（带变量面）：artifact + 初始变量（Python dict）→ （print 输出
/// 列表, 最终状态 dict）。⑦ 切换门变量面契约：初始变量 = 模块顶层环境
/// 预置（原生数据值）；最终状态 = 顶层环境全条目（原生数据值 = 原生 Python
/// 形态；非数据值 = 显示形态字符串——repr 契约）。
#[pyfunction]
fn run_artifact_state(
    artifact_json: &str,
    bridge: Option<Bound<'_, PyAny>>,
    initial_vars: Option<Bound<'_, PyDict>>,
    py: Python<'_>,
) -> PyResult<(Py<PyList>, Py<PyDict>)> {
    let bridge_owned = bridge.map(|b| b.unbind());
    // GIL 侧：初始变量 → JSON（Send 安全；IbValue 含 Rc 非 Send——转换于
    // 线程内经 json_to_ibvalue 完成）
    let initial_json: Vec<(String, serde_json::Value)> = match initial_vars {
        Some(d) => d
            .iter()
            .map(|(k, v)| -> PyResult<(String, serde_json::Value)> {
                Ok((k.extract::<String>()?, py_to_json(&v)?))
            })
            .collect::<PyResult<Vec<_>>>()?,
        None => Vec::new(),
    };
    let json_owned = artifact_json.to_string();
    // GIL 释放：反序列化 + 执行 + 状态 → JSON（纯 CPU 面）
    let (lines, state_json): (Vec<String>, Vec<(String, serde_json::Value)>) =
        match py
            .allow_threads(|| -> Result<(Vec<String>, Vec<(String, serde_json::Value)>), errors::ErrorPayload> {
            let module = match deserializer::deserialize_module(&json_owned) {
                Some(m) => m,
                // R2-2 静默清零：反序列化失败 = 显式错误（fail-fast，旧 = 空输出）
                None => {
                    return Err(errors::ErrorPayload {
                        class: "ArtifactDeserializeError".to_string(),
                        detail: "artifact 反序列化失败（非良构输入）".to_string(),
                        pos: None,
            code: None,
                    })
                }
            };
            let interp = match bridge_owned {
                Some(b) => interpreter::Interpreter::with_bridge(b),
                None => interpreter::Interpreter::new(),
            };
            let initial: Vec<(String, interpreter::IbValue)> = initial_json
                .into_iter()
                .map(|(k, v)| (k, json_to_ibvalue(&v)))
                .collect();
            let (output, state) = interp
                .run_module_with_state(&module, &initial)
                .map_err(errors::ErrorPayload::from_thrown)?;
            let state_json: Vec<(String, serde_json::Value)> = state
                .into_iter()
                .map(|(k, v)| (k, interpreter::ibvalue_to_typed_json(&v)))
                .collect();
            Ok((output, state_json))
            })
        {
            Ok(r) => r,
            Err(payload) => return Err(payload.to_pyerr()),
        };
    // GIL 侧：组装返回（输出列表 + 状态 dict）
    let list = PyList::empty(py);
    for line in lines {
        list.append(line)?;
    }
    let state_dict = PyDict::new(py);
    for (k, v) in state_json {
        state_dict.set_item(k, json_to_py(py, &v)?)?;
    }
    Ok((list.unbind(), state_dict.unbind()))
}

/// JSON → Python 对象（状态导出的 GIL 侧还原：number→int[整数形态]/
/// float / string→str / bool / null→None / array→list / object→dict）。
fn json_to_py(
    py: Python<'_>,
    v: &serde_json::Value,
) -> PyResult<pyo3::PyObject> {
    match v {
        serde_json::Value::Null => Ok(py.None()),
        serde_json::Value::Bool(b) => {
            let obj: pyo3::Py<pyo3::PyAny> = pyo3::types::PyBool::new(py, *b).into_py(py);
            Ok(obj)
        }
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.into_pyobject(py).unwrap().unbind().into())
            } else {
                Ok(n.as_f64().unwrap_or(0.0).into_pyobject(py).unwrap().unbind().into())
            }
        }
        serde_json::Value::String(s) => {
            let obj: pyo3::Py<pyo3::PyAny> = pyo3::types::PyString::new(py, s).into_py(py);
            Ok(obj)
        }
        serde_json::Value::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr {
                list.append(json_to_py(py, item)?)?;
            }
            Ok(list.into())
        }
        serde_json::Value::Object(obj) => {
            let dict = PyDict::new(py);
            for (k, val) in obj {
                dict.set_item(k, json_to_py(py, val)?)?;
            }
            Ok(dict.into())
        }
    }
}

/// 并行执行 API（task_scheduler GIL-free 集成地基）：多 artifact（JSON 列表）经
/// Rust 线程（std::thread）**GIL-free 真并行**执行——每线程分配一批 artifact，纯
/// CPU（无宿主服务）全程 GIL 释放。返回 list of list（每项 = 一个 artifact 的
/// print 输出列表）。workers = 并行线程数（纯 CPU 面；含宿主服务的 artifact 由
/// 单线程 run_artifact 经桥接处理）。
#[pyfunction]
fn run_artifacts_parallel(
    artifact_jsons: Vec<String>,
    workers: u32,
    py: Python<'_>,
) -> PyResult<Py<PyList>> {
    let n = artifact_jsons.len();
    let w = (workers as usize).max(1).min(n.max(1));
    // 均分：每线程 per 个 artifact（余数并入末批）
    let per = n.div_ceil(w);
    let chunks: Vec<Vec<String>> = (0..w)
        .map(|wi| {
            let lo = wi * per;
            let hi = (lo + per).min(n);
            artifact_jsons[lo..hi].to_vec()
        })
        .filter(|c| !c.is_empty())
        .collect();
    // GIL-free 真并行：释放 GIL，Rust 线程各执行一批（纯 CPU 无宿主服务）。每线程
    // 返回 Vec<Vec<String>>（每 artifact 一个 print 输出列表）
    let results: Result<Vec<Vec<String>>, errors::ErrorPayload> = py.allow_threads(|| {
        let handles: Vec<std::thread::JoinHandle<Result<Vec<Vec<String>>, errors::ErrorPayload>>> =
            chunks
                .into_iter()
                .map(|chunk| {
                    std::thread::spawn(move || {
                        let mut out = Vec::new();
                        for js in chunk {
                            out.push(interpreter::run_artifact(&js, None)?);
                        }
                        Ok(out)
                    })
                })
                .collect();
        // 按线程序拼接（chunk 按 artifact 序均分 → 拼接 = artifact 序）
        let mut all: Vec<Vec<String>> = Vec::new();
        for h in handles {
            let r = h.join().unwrap();
            if let Err(e) = r {
                return Err(e);
            }
            all.extend(r.unwrap());
        }
        Ok(all)
    });
    // 组装结果：list of list（每项 = 一个 artifact 的 print 输出）
    let results = match results {
        Ok(r) => r,
        Err(payload) => return Err(payload.to_pyerr()),
    };
    let list = PyList::empty(py);
    for artifact_results in results {
        let inner = PyList::empty(py);
        for line in artifact_results {
            inner.append(line)?;
        }
        list.append(inner)?;
    }
    Ok(list.unbind())
}

#[pymodule]
fn ibci_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(kernel_info, m)?)?;
    m.add_function(wrap_pyfunction!(lex, m)?)?;
    m.add_function(wrap_pyfunction!(parse_struct, m)?)?;
    m.add_function(wrap_pyfunction!(deserialize_struct, m)?)?;
    m.add_function(wrap_pyfunction!(symbol_table, m)?)?;
    m.add_function(wrap_pyfunction!(type_table, m)?)?;
    m.add_function(wrap_pyfunction!(node_types, m)?)?;
    m.add_function(wrap_pyfunction!(node_uid, m)?)?;
    m.add_function(wrap_pyfunction!(type_uid, m)?)?;
    m.add_function(wrap_pyfunction!(asset_uid, m)?)?;
    m.add_function(wrap_pyfunction!(serialize_nodes, m)?)?;
    m.add_function(wrap_pyfunction!(resolve_symbols, m)?)?;
    m.add_function(wrap_pyfunction!(intrinsic_type_symbols, m)?)?;
    m.add_function(wrap_pyfunction!(intrinsic_symbol_table, m)?)?;
    m.add_function(wrap_pyfunction!(intrinsic_type_pool, m)?)?;
    m.add_function(wrap_pyfunction!(scope_pool, m)?)?;
    m.add_function(wrap_pyfunction!(node_to_loc, m)?)?;
    m.add_function(wrap_pyfunction!(node_to_type, m)?)?;
    m.add_function(wrap_pyfunction!(node_to_symbol, m)?)?;
    m.add_function(wrap_pyfunction!(full_artifact, m)?)?;
    m.add_function(wrap_pyfunction!(rust_run_source, m)?)?;
    m.add_function(wrap_pyfunction!(run_artifact_state, m)?)?;
    m.add_function(wrap_pyfunction!(rust_intrinsic_names, m)?)?;
    m.add_function(wrap_pyfunction!(capability, m)?)?;
    m.add_function(wrap_pyfunction!(call_top_level_function, m)?)?;
    m.add_function(wrap_pyfunction!(load_plugin, m)?)?;
    m.add_function(wrap_pyfunction!(call_plugin, m)?)?;
    m.add_function(wrap_pyfunction!(run_artifact, m)?)?;
    m.add_function(wrap_pyfunction!(run_artifacts_parallel, m)?)?;
    m.add_function(wrap_pyfunction!(run, m)?)?;
    m.add_class::<errors::RustRuntimeError>()?;
    m.add_class::<task_pool::TaskPool>()?;
    Ok(())
}
