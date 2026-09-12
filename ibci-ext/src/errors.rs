//! 类型化错误契约（P3 协议——Rust → Python 结构化异常）。
//!
//! 替代旧的非类型化字符串协议（"IBCI: uncaught exception: {class}: {msg}@{l}:{c}"
//! + engine 正则回拆 + _RUST_ERROR_CODES 双真相映射）：跨边界错误 = 结构化字段
//! （error_class / code / line / column / detail），Python 侧直接读字段，零正则
//! 零字符串解析（架构 v2 裁定 R0 §三 P3）。
//!
//! - `RustRuntimeError`：pyo3 异常子类（extends PyRuntimeError——engine 既有
//!   `except RuntimeError` 面自动捕获），结构化字段经 getter 读取。
//! - `ErrorPayload`：Send 安全载荷（Thrown 含 Rc 非 Send——跨 `py.allow_threads`
//!   释放边界时先降级为纯字符串载荷，GIL 侧再转 PyErr；PyErr::new 惰性构造）。
//! - 诊断码不在 Rust 侧映射——Python 侧单一权威 `error_code_for_class` 派生
//!   （core/base/diagnostics/codes.py，functions.py 同源委托，消除双真相）。

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use crate::interpreter::{IbValue, Thrown};

/// Rust 内核执行错误的类型化边界（engine 侧捕获后读结构化字段）。
#[pyclass(extends=PyRuntimeError, module="ibci_ext")]
#[derive(Debug, Clone)]
pub struct RustRuntimeError {
    /// 异常类名（ZeroDivisionError / TypeError / ...；非 Error 值 = repr 形态）。
    #[pyo3(get)]
    pub error_class: String,
    /// 诊断码（None = Python 侧经单一权威 error_code_for_class 派生）。
    #[pyo3(get)]
    pub code: Option<String>,
    /// 错误现场行（1-based；无位置 = None）。
    #[pyo3(get)]
    pub line: Option<i64>,
    /// 错误现场列（1-based；无位置 = None）。
    #[pyo3(get)]
    pub column: Option<i64>,
    /// 详情消息（无 message = 空串）。
    #[pyo3(get)]
    pub detail: String,
}

#[pymethods]
impl RustRuntimeError {
    #[new]
    #[pyo3(signature = (message, error_class, code=None, line=None, column=None, detail=None))]
    fn new(
        message: String,
        error_class: String,
        code: Option<String>,
        line: Option<i64>,
        column: Option<i64>,
        detail: Option<String>,
    ) -> Self {
        // message 承载于 BaseException args 面；结构化字段经 getter 读取
        let _ = message;
        RustRuntimeError {
            error_class,
            code,
            line,
            column,
            detail: detail.unwrap_or_default(),
        }
    }
}

/// Send 安全错误载荷（GIL 释放边界中间形态）。
#[derive(Debug, Clone)]
pub(crate) struct ErrorPayload {
    pub class: String,
    pub detail: String,
    pub pos: Option<(i64, i64)>,
    /// 语义诊断码（EMB_/KNW_ 等——Thrown.code 承载；None = engine 派生 RUN_*）。
    pub code: Option<String>,
}

impl ErrorPayload {
    pub(crate) fn from_thrown(t: Thrown) -> Self {
        let (class, detail) = match &t.value {
            IbValue::Error { class, message } => (class.clone(), message.clone()),
            other => (other.repr(), other.repr()),
        };
        ErrorPayload {
            class,
            detail,
            pos: t.pos,
            code: t.code,
        }
    }

    /// → 类型化 PyErr（PyErr::new 惰性构造——无需 GIL 持有）。
    pub(crate) fn to_pyerr(&self) -> PyErr {
        let message = if self.detail.is_empty() {
            self.class.clone()
        } else {
            format!("{}: {}", self.class, self.detail)
        };
        let (line, column): (Option<i64>, Option<i64>) = match self.pos {
            Some((l, c)) => (Some(l), Some(c)),
            None => (None, None),
        };
        PyErr::new::<RustRuntimeError, _>((
            message,
            self.class.clone(),
            self.code.clone(),
            line,
            column,
            Some(self.detail.clone()),
        ))
    }
}

