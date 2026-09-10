//! ibci-ext：IBC-Inter Rust 内核（pyo3 扩展）——双内核协议的 Rust 执行后端。
//!
//! 双内核协议（核心设计裁定）：Python 内核 = 一等实验内核（默认）；Rust 内核 =
//! 生产快路径（显式 opt-in，无静默回退）。两内核共享同一 AST 契约 + contracts
//! 层语义红线。本 crate = Rust 内核的执行体（GIL-free，py.allow_threads 释放
//! GIL）。
//!
//! 当前形态：构建链 + Rust lexer + Rust parser + 反序列化器 + 执行核心
//! （tree-walking 解释器）——执行核心消费 Python 前端产出的序列化 artifact
//! （FlatSerializer JSON）执行，数据面经差分 harness 与 Python 参考内核逐条
//! 比对（30 语料全级差分等价：token/AST/反序列化/数据面 + 符号表/类型表；
//! 性能 23–30x）。kernel_info.stage = 3（执行核心就绪），status =
//! "execution-core"（执行核心就绪，数据面经 run_artifact 可用；run[script 入口]
//! 待 Rust 前端[语义层]移植后升 "ready" 生效）。

mod deserializer;
mod interpreter;
mod lexer;
mod parser;

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

/// 内核元数据（name / stage / status）——差分 harness 的接入点：harness 经此
/// 探明 Rust 内核状态。stage = 当前阶段（3 = 执行核心）；status = 就绪门
/// （"execution-core" = 执行核心就绪[数据面经 run_artifact 可用]；"ready" =
/// 全量内核就绪[run script 入口生效，待 Rust 前端移植]）。
#[pyfunction]
fn kernel_info(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("name", "rust")?;
    dict.set_item("stage", 3u32)?;
    dict.set_item("status", "execution-core")?;
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
#[pyfunction]
fn run_artifact(
    artifact_json: &str,
    bridge: Option<Bound<'_, PyAny>>,
    py: Python<'_>,
) -> PyResult<Py<PyList>> {
    let bridge_owned = bridge.map(|b| b.unbind());
    let lines = interpreter::run_artifact(artifact_json, bridge_owned);
    let list = PyList::empty(py);
    for line in lines {
        list.append(line)?;
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
    m.add_function(wrap_pyfunction!(run_artifact, m)?)?;
    m.add_function(wrap_pyfunction!(run, m)?)?;
    Ok(())
}
