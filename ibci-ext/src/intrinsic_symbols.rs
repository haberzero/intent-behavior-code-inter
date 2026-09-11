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

/// 19 个 IBC 内置函数（固定集，与 Python 语义层 intrinsic 符号表对齐）。
const BUILTIN_FUNCTIONS: &[&str] = &[
    "all",
    "callable",
    "copy",
    "deepcopy",
    "enumerate",
    "fn",
    "get_self_source",
    "len",
    "max",
    "min",
    "next",
    "print",
    "range",
    "reversed",
    "sorted",
    "sum",
    "type",
    "vec",
    "zip",
];

/// 2 个 IBC 内置模块（固定集，与 Python 语义层 intrinsic 符号表对齐）。
const BUILTIN_MODULES: &[&str] = &["__string_exec__", "module"];

/// 构建单个 intrinsic 符号（uid = `intrinsic:<name>`，type_uid = `type_root.<name>`）。
fn make_intrinsic(name: &str, kind: &str) -> (String, Value) {
    let uid = format!("intrinsic:{}", name);
    let sym_data = Value::Object(serde_json::Map::from_iter([
        ("uid".to_string(), Value::String(uid.clone())),
        ("name".to_string(), Value::String(name.to_string())),
        ("kind".to_string(), Value::String(kind.to_string())),
        ("metadata".to_string(), Value::Object(serde_json::Map::new())),
        ("node_uid".to_string(), Value::Null),
        ("owned_scope_uid".to_string(), Value::Null),
        ("type_uid".to_string(), Value::String(format!("type_root.{}", name))),
    ]));
    (uid, sym_data)
}

/// 构建 intrinsic 符号池（42 内置类型 CLASS 符号）。BTreeMap 保证 uid 序（确定性）。
pub fn builtin_type_symbols() -> BTreeMap<String, Value> {
    let mut symbols = BTreeMap::new();
    for name in BUILTIN_TYPES {
        let (uid, sym_data) = make_intrinsic(name, "CLASS");
        symbols.insert(uid, sym_data);
    }
    symbols
}

/// 构建完整 intrinsic 符号表（42 内置类型 + 19 内置函数 + 2 内置模块 = 63 符号）。
/// BTreeMap 保证 uid 序（确定性）。与 Python 语义层 intrinsic 符号表逐条差分等价。
pub fn builtin_intrinsic_symbols() -> BTreeMap<String, Value> {
    let mut symbols = BTreeMap::new();
    for name in BUILTIN_TYPES {
        let (uid, sym_data) = make_intrinsic(name, "CLASS");
        symbols.insert(uid, sym_data);
    }
    for name in BUILTIN_FUNCTIONS {
        let (uid, sym_data) = make_intrinsic(name, "FUNCTION");
        symbols.insert(uid, sym_data);
    }
    for name in BUILTIN_MODULES {
        let (uid, sym_data) = make_intrinsic(name, "MODULE");
        symbols.insert(uid, sym_data);
    }
    symbols
}

/// intrinsic 类型池（66 non-generic KERNEL_NATIVE 类型基础字段）——Rust 静态表（对齐
/// Python registry/prelude 固有类型集，迁移期差分基准）。uid = type_root.<name>
/// （module_path=None），provenance=KERNEL_NATIVE，storage_model=MEMORY_BACKED。
/// members_uids[方法 sym_anon] / 用户类 / 泛型实例 = 后续（需统一 artifact 产出）。
/// IMPORT_GATED：eval/quote（from meta import）+ meta（import meta）。
const INTRINSIC_TYPES: &[(&str, &str, &str)] = &[
    // (name, kind, visibility)
    ("int", "primitive", "PRELUDE_VISIBLE"),
    ("float", "primitive", "PRELUDE_VISIBLE"),
    ("str", "primitive", "PRELUDE_VISIBLE"),
    ("bool", "primitive", "PRELUDE_VISIBLE"),
    ("void", "primitive", "PRELUDE_VISIBLE"),
    ("any", "primitive", "PRELUDE_VISIBLE"),
    ("auto", "primitive", "PRELUDE_VISIBLE"),
    ("None", "primitive", "PRELUDE_VISIBLE"),
    ("slice", "primitive", "PRELUDE_VISIBLE"),
    ("vector", "primitive", "PRELUDE_VISIBLE"),
    ("behavior", "callable_instance", "PRELUDE_VISIBLE"),
    ("fn_callable", "callable_instance", "PRELUDE_VISIBLE"),
    ("Exception", "class", "PRELUDE_VISIBLE"),
    ("Enum", "class", "PRELUDE_VISIBLE"),
    ("Intent", "class", "PRELUDE_VISIBLE"),
    ("LLMCallError", "class", "PRELUDE_VISIBLE"),
    ("LLMError", "class", "PRELUDE_VISIBLE"),
    ("LLMParseError", "class", "PRELUDE_VISIBLE"),
    ("LLMRetryExhaustedError", "class", "PRELUDE_VISIBLE"),
    ("ThreadCancelled", "class", "PRELUDE_VISIBLE"),
    ("ThreadError", "class", "PRELUDE_VISIBLE"),
    ("ThreadFailed", "class", "PRELUDE_VISIBLE"),
    ("environment", "class", "PRELUDE_VISIBLE"),
    ("intent_context", "class", "PRELUDE_VISIBLE"),
    ("knowledge", "class", "PRELUDE_VISIBLE"),
    ("llm_call_result", "class", "PRELUDE_VISIBLE"),
    ("llm_uncertain", "class", "PRELUDE_VISIBLE"),
    ("memory", "class", "PRELUDE_VISIBLE"),
    ("narrow_model", "class", "PRELUDE_VISIBLE"),
    ("quoted", "class", "PRELUDE_VISIBLE"),
    ("run_result", "class", "PRELUDE_VISIBLE"),
    ("Optional", "optional", "PRELUDE_VISIBLE"),
    ("bound_method", "bound_method", "PRELUDE_VISIBLE"),
    ("list", "list", "PRELUDE_VISIBLE"),
    ("tuple", "tuple", "PRELUDE_VISIBLE"),
    ("dict", "dict", "PRELUDE_VISIBLE"),
    ("chan", "channel", "PRELUDE_VISIBLE"),
    ("slot", "slot", "PRELUDE_VISIBLE"),
    ("subscriber", "subscriber", "PRELUDE_VISIBLE"),
    ("thread", "thread", "PRELUDE_VISIBLE"),
    ("thread_result", "thread_result", "PRELUDE_VISIBLE"),
    ("generator", "generator", "PRELUDE_VISIBLE"),
    ("all", "function", "PRELUDE_VISIBLE"),
    ("callable", "function", "PRELUDE_VISIBLE"),
    ("copy", "function", "PRELUDE_VISIBLE"),
    ("deepcopy", "function", "PRELUDE_VISIBLE"),
    ("enumerate", "function", "PRELUDE_VISIBLE"),
    ("eval", "function", "IMPORT_GATED"),
    ("fn", "function", "PRELUDE_VISIBLE"),
    ("get_self_source", "function", "PRELUDE_VISIBLE"),
    ("len", "function", "PRELUDE_VISIBLE"),
    ("max", "function", "PRELUDE_VISIBLE"),
    ("min", "function", "PRELUDE_VISIBLE"),
    ("next", "function", "PRELUDE_VISIBLE"),
    ("print", "function", "PRELUDE_VISIBLE"),
    ("quote", "function", "IMPORT_GATED"),
    ("range", "function", "PRELUDE_VISIBLE"),
    ("reversed", "function", "PRELUDE_VISIBLE"),
    ("sorted", "function", "PRELUDE_VISIBLE"),
    ("sum", "function", "PRELUDE_VISIBLE"),
    ("type", "function", "PRELUDE_VISIBLE"),
    ("vec", "function", "PRELUDE_VISIBLE"),
    ("zip", "function", "PRELUDE_VISIBLE"),
    ("__string_exec__", "module", "PRELUDE_VISIBLE"),
    ("meta", "module", "IMPORT_GATED"),
    ("module", "module", "PRELUDE_VISIBLE"),
];

/// 构建 intrinsic 类型池（66 non-generic KERNEL_NATIVE 类型基础字段）。BTreeMap 按
/// name 序（确定性）。与 Python types 池的 KERNEL_NATIVE non-generic 子集差分等价。
pub fn builtin_intrinsic_types() -> BTreeMap<String, Value> {
    let mut types = BTreeMap::new();
    for (name, kind, visibility) in INTRINSIC_TYPES {
        let uid = format!("type_root.{}", name);
        let type_data = Value::Object(serde_json::Map::from_iter([
            ("uid".to_string(), Value::String(uid)),
            ("kind".to_string(), Value::String((*kind).to_string())),
            ("name".to_string(), Value::String((*name).to_string())),
            ("module_path".to_string(), Value::Null),
            ("provenance".to_string(), Value::String("KERNEL_NATIVE".to_string())),
            ("visibility".to_string(), Value::String((*visibility).to_string())),
            ("storage_model".to_string(), Value::String("MEMORY_BACKED".to_string())),
        ]));
        types.insert((*name).to_string(), type_data);
    }
    types
}
