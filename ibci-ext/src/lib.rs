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
mod interpreter;
mod intrinsic_symbols;
mod lexer;
mod node_serializer;
mod parser;
mod scope_serializer;
mod serialization;
mod symbol_resolver;
mod task_pool;
mod type_inference;

use pyo3::exceptions::PyNotImplementedError;
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
    let lines = py.allow_threads(|| interpreter::run_artifact(&json_owned, bridge_owned));
    let list = PyList::empty(py);
    for line in lines {
        list.append(line)?;
    }
    Ok(list.unbind())
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
    let results: Vec<Vec<String>> = py.allow_threads(|| {
        let handles: Vec<std::thread::JoinHandle<Vec<Vec<String>>>> = chunks
            .into_iter()
            .map(|chunk| {
                std::thread::spawn(move || {
                    chunk
                        .into_iter()
                        .map(|js| interpreter::run_artifact(&js, None))
                        .collect()
                })
            })
            .collect();
        // 按线程序拼接（chunk 按 artifact 序均分 → 拼接 = artifact 序）
        let mut all: Vec<Vec<String>> = Vec::new();
        for h in handles {
            all.extend(h.join().unwrap());
        }
        all
    });
    // 组装结果：list of list（每项 = 一个 artifact 的 print 输出）
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
    m.add_function(wrap_pyfunction!(run_artifact, m)?)?;
    m.add_function(wrap_pyfunction!(run_artifacts_parallel, m)?)?;
    m.add_function(wrap_pyfunction!(run, m)?)?;
    m.add_class::<task_pool::TaskPool>()?;
    Ok(())
}
