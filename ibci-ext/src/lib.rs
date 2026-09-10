//! ibci-ext：IBC-Inter Rust 内核（pyo3 扩展）——双内核协议的 Rust 执行后端。
//!
//! 双内核协议（核心设计裁定）：Python 内核 = 一等实验内核（默认）；Rust 内核 =
//! 生产快路径（显式 opt-in，无静默回退）。两内核共享同一 AST 契约 + contracts
//! 层语义红线。本 crate = Rust 内核的执行体（GIL-free，py.allow_threads 释放
//! GIL）。
//!
//! 当前形态：构建链 + Rust lexer（version / kernel_info / lex / run 显式
//! NotImplemented）——验证构建链 + pyo3 绑定 + 差分 harness 接入点。run 执行
//! 核心待后续扩展落地（kernel_info.status 由 "skeleton" 升 "ready" 后 run 才
//! 生效）。

mod lexer;

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

/// 内核元数据（name / stage / status）——差分 harness 的接入点：harness 经此
/// 探明 Rust 内核状态，决定双内核比对是否就绪（status != "ready" = 未就绪，
/// 仅跑 Python 参考内核）。
#[pyfunction]
fn kernel_info(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("name", "rust")?;
    dict.set_item("stage", 1u32)?;
    dict.set_item("status", "skeleton")?;
    Ok(dict)
}

/// 执行 IBCI 源码（Rust 内核快路径入口）。
///
/// 执行核心未落地——**显式 NotImplemented（无静默回退）**。双内核协议：Rust
/// 内核不可用/未实现 = 显式报错，不悄悄切 Python 内核（kernel_info.status ==
/// "ready" 前 run 恒 NotImplemented）。
#[pyfunction]
fn run(_script: &str) -> PyResult<String> {
    Err(PyNotImplementedError::new_err(
        "ibci_ext.run: Rust 内核执行核心未落地（双内核协议 = 无静默回退）",
    ))
}

#[pymodule]
fn ibci_ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(kernel_info, m)?)?;
    m.add_function(wrap_pyfunction!(lex, m)?)?;
    m.add_function(wrap_pyfunction!(run, m)?)?;
    Ok(())
}
