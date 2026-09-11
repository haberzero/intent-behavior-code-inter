//! intrinsic 符号表——内置类型（全量 Rust 化·语义层：intrinsic 符号表）。
//!
//! 对应 Python 语义层的 intrinsic 符号表中的内置类型（CLASS 符号）。IBC 语言有固定
//! 的 42 个内置类型（int/float/str/bool/void/any/list/dict/tuple/... 等）。每个内置
//! 类型的 intrinsic 符号：uid = `intrinsic:<name>`，kind = CLASS，type_uid =
//! `type_root.<name>`，node_uid/owned_scope_uid = null，metadata = {}。
//!
//! 与 Python intrinsic 符号表逐条差分等价（34 语料）。内置函数/方法/模块归后续增量
//! （method = sym_anon_*，归类型解析后续）。

use std::collections::BTreeMap;

use serde_json::Value;

/// 42 个 IBC 内置类型（固定集，与 Python 语义层 intrinsic 符号表对齐）。
const BUILTIN_TYPES: &[&str] = &[
    "Enum",
    "Exception",
    "Intent",
    "LLMCallError",
    "LLMError",
    "LLMParseError",
    "LLMRetryExhaustedError",
    "None",
    "Optional",
    "ThreadCancelled",
    "ThreadError",
    "ThreadFailed",
    "any",
    "auto",
    "behavior",
    "bool",
    "bound_method",
    "chan",
    "dict",
    "environment",
    "float",
    "fn_callable",
    "generator",
    "int",
    "intent_context",
    "knowledge",
    "list",
    "llm_call_result",
    "llm_uncertain",
    "memory",
    "narrow_model",
    "quoted",
    "run_result",
    "slice",
    "slot",
    "str",
    "subscriber",
    "thread",
    "thread_result",
    "tuple",
    "vector",
    "void",
];

/// 构建 intrinsic 符号池（42 内置类型 CLASS 符号）。BTreeMap 保证 uid 序（确定性）。
pub fn builtin_type_symbols() -> BTreeMap<String, Value> {
    let mut symbols = BTreeMap::new();
    for name in BUILTIN_TYPES {
        let uid = format!("intrinsic:{}", name);
        let sym_data = Value::Object(serde_json::Map::from_iter([
            ("uid".to_string(), Value::String(uid.clone())),
            ("name".to_string(), Value::String(name.to_string())),
            ("kind".to_string(), Value::String("CLASS".to_string())),
            ("metadata".to_string(), Value::Object(serde_json::Map::new())),
            ("node_uid".to_string(), Value::Null),
            ("owned_scope_uid".to_string(), Value::Null),
            ("type_uid".to_string(), Value::String(format!("type_root.{}", name))),
        ]));
        symbols.insert(uid, sym_data);
    }
    symbols
}
