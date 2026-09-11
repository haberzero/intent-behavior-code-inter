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

/// 成员符号 canonical uid（与 Python FlatSerializer._collect_symbol 匿名符号内容哈希
/// 同构）：canonical JSON（**键字母序**——owned_scope_uid < owner_type_uid[d<r] +
/// compact 分隔）=
/// {"kind","metadata":{},"name","node_uid":null,"owned_scope_uid":null,
/// "owner_type_uid","type_uid":null} → sha256[:16] → sym_anon_<hash>。metadata = {}
/// （成员符号固定空 metadata，全语料实证）。
pub fn anon_member_uid(member_name: &str, kind: &str, owner_type_uid: &str) -> String {
    let content = format!(
        "{{\"kind\":\"{}\",\"metadata\":{{}},\"name\":\"{}\",\"node_uid\":null,\"owned_scope_uid\":null,\"owner_type_uid\":\"{}\",\"type_uid\":null}}",
        kind, member_name, owner_type_uid
    );
    crate::serialization::anon_symbol_uid(&crate::serialization::hash_prefix(&content))
}

/// 构建 intrinsic 类型池（66 non-generic KERNEL_NATIVE 类型：基础字段 +
/// members_uids[35 类型成员静态表，泛型条目继承基类表]）。BTreeMap 按 name 序
/// （确定性）。与 Python types 池的 KERNEL_NATIVE non-generic 子集差分等价。
pub fn builtin_intrinsic_types() -> BTreeMap<String, Value> {
    let mut types = BTreeMap::new();
    for (name, kind, visibility) in INTRINSIC_TYPES {
        let uid = format!("type_root.{}", name);
        let mut type_data = Value::Object(serde_json::Map::from_iter([
            ("uid".to_string(), Value::String(uid.clone())),
            ("kind".to_string(), Value::String((*kind).to_string())),
            ("name".to_string(), Value::String((*name).to_string())),
            ("module_path".to_string(), Value::Null),
            ("provenance".to_string(), Value::String("KERNEL_NATIVE".to_string())),
            ("visibility".to_string(), Value::String((*visibility).to_string())),
            ("storage_model".to_string(), Value::String("MEMORY_BACKED".to_string())),
        ]));
        // members_uids（成员名 → 成员符号 canonical uid；成员静态表覆盖的类型）。
        if let Some((_, members)) = METHOD_MEMBERS.iter().find(|(t, _)| *t == *name) {
            let mut members_uids = serde_json::Map::new();
            for (mn, mk) in *members {
                members_uids.insert(mn.to_string(), Value::String(anon_member_uid(mn, mk, &uid)));
            }
            type_data
                .as_object_mut()
                .unwrap()
                .insert("members_uids".to_string(), Value::Object(members_uids));
        }
        types.insert((*name).to_string(), type_data);
    }
    types
}

/// intrinsic 符号 name 全集（42 类型 + 19 函数 + 2 模块 = 63）——顶层 scope 的固有符号。
pub fn intrinsic_names() -> Vec<String> {
    let mut names = Vec::new();
    for n in BUILTIN_TYPES {
        names.push(n.to_string());
    }
    for n in BUILTIN_FUNCTIONS {
        names.push(n.to_string());
    }
    for n in BUILTIN_MODULES {
        names.push(n.to_string());
    }
    names
}


/// 类型成员静态表（35 类型 / 244 成员）——转录自 IBCI 公理层声明式成员表
/// （全语料实证跨语料稳定；泛型条目继承基类成员表[owner uid 区分]）。
/// (type name, [(member name, kind)])，类型名/成员名字母序（BTreeMap 同序）。
pub const METHOD_MEMBERS: &[(&str, &[(&str, &str)])] = &[
    ("Enum", &[("len", "method"), ("to_list", "method")]),
    ("Exception", &[("__to_prompt__", "method"), ("cast_to", "method"), ("message", "field")]),
    ("Intent", &[("get_content", "method"), ("get_mode", "method"), ("get_tag", "method")]),
    ("LLMCallError", &[("__to_prompt__", "method"), ("cast_to", "method"), ("message", "field"), ("provider_error", "field"), ("raw_response", "field")]),
    ("LLMError", &[("__to_prompt__", "method"), ("cast_to", "method"), ("message", "field"), ("raw_response", "field")]),
    ("LLMParseError", &[("__to_prompt__", "method"), ("cast_to", "method"), ("message", "field"), ("raw_response", "field"), ("type_name", "field")]),
    ("LLMRetryExhaustedError", &[("__to_prompt__", "method"), ("cast_to", "method"), ("max_retry", "field"), ("message", "field"), ("raw_response", "field")]),
    ("None", &[("cast_to", "method"), ("to_bool", "method")]),
    ("Optional", &[("__to_prompt__", "method"), ("cast_to", "method"), ("is_none", "method"), ("is_some", "method"), ("or_else", "method"), ("to_bool", "method"), ("unwrap", "method")]),
    ("ThreadCancelled", &[("__to_prompt__", "method"), ("cast_to", "method"), ("message", "field"), ("raw_response", "field")]),
    ("ThreadError", &[("__to_prompt__", "method"), ("cast_to", "method"), ("message", "field"), ("raw_response", "field")]),
    ("ThreadFailed", &[("__to_prompt__", "method"), ("cast_to", "method"), ("message", "field"), ("raw_response", "field")]),
    ("bool", &[("cast_to", "method"), ("to_bool", "method")]),
    ("chan", &[("close", "method"), ("recv", "method"), ("recv_nowait", "method"), ("send", "method"), ("send_nowait", "method"), ("subscribe", "method")]),
    ("dict", &[("__getitem__", "method"), ("__setitem__", "method"), ("cast_to", "method"), ("contains", "method"), ("get", "method"), ("items", "method"), ("keys", "method"), ("len", "method"), ("pop", "method"), ("remove", "method"), ("update", "method"), ("values", "method")]),
    ("environment", &[("clear", "method"), ("contains", "method"), ("fork", "method"), ("get", "method"), ("get_current", "method"), ("keys", "method"), ("len", "method"), ("pop", "method"), ("set", "method"), ("use", "method")]),
    ("float", &[("cast_to", "method"), ("to_bool", "method")]),
    ("generator", &[("generic_next", "method"), ("to_list", "method")]),
    ("int", &[("cast_to", "method"), ("to_bool", "method"), ("to_list", "method")]),
    ("intent_context", &[("__to_prompt__", "method"), ("clear", "method"), ("clear_inherited", "method"), ("combine", "method"), ("fork", "method"), ("get_current", "method"), ("merge", "method"), ("pop", "method"), ("push", "method"), ("resolve", "method"), ("use", "method")]),
    ("knowledge", &[("add_fact", "method"), ("all_in_world", "method"), ("amend", "method"), ("amend_fact", "method"), ("by_source", "method"), ("by_subject", "method"), ("cast_to", "method"), ("compare", "method"), ("contradicts", "method"), ("embed_search", "method"), ("embedding", "method"), ("embedding_dim", "method"), ("exists", "method"), ("expand", "method"), ("export", "method"), ("fact_len", "method"), ("facts", "method"), ("get", "method"), ("get_fact", "method"), ("has_embedding", "method"), ("history", "method"), ("history_fact", "method"), ("keys", "method"), ("len", "method"), ("lookup_pair", "method"), ("register_relation", "method"), ("register_word", "method"), ("register_world", "method"), ("relation", "method"), ("relations", "method"), ("retract", "method"), ("same_word", "method"), ("set_embedding", "method"), ("source", "method"), ("store", "method"), ("to_ibci", "method"), ("transitive", "method"), ("word", "method"), ("words", "method"), ("world", "method"), ("worlds", "method")]),
    ("list", &[("__getitem__", "method"), ("__setitem__", "method"), ("append", "method"), ("cast_to", "method"), ("clear", "method"), ("contains", "method"), ("count", "method"), ("index", "method"), ("insert", "method"), ("len", "method"), ("pop", "method"), ("remove", "method"), ("reverse", "method"), ("sort", "method")]),
    ("llm_uncertain", &[("__eq__", "method"), ("__ne__", "method"), ("__to_prompt__", "method"), ("cast_to", "method"), ("to_bool", "method")]),
    ("memory", &[("cast_to", "method"), ("consolidate", "method"), ("content_hash", "method"), ("corpus", "method"), ("demote", "method"), ("encode", "method"), ("export", "method"), ("keys", "method"), ("len", "method"), ("promote", "method"), ("prune", "method"), ("retrieve", "method"), ("search", "method"), ("set_capacity", "method"), ("snapshot", "method"), ("tier", "method"), ("tier_keys", "method"), ("tier_size", "method"), ("verify", "method")]),
    ("meta", &[("compile", "method"), ("eval", "method"), ("quote", "method")]),
    ("narrow_model", &[("__to_prompt__", "method"), ("architecture", "method"), ("cast_to", "method"), ("content_hash", "method"), ("dim", "method"), ("entities", "method"), ("name", "method"), ("relations", "method"), ("score", "method"), ("topk", "method")]),
    ("quoted", &[("__to_prompt__", "method"), ("cast_to", "method"), ("source", "field")]),
    ("run_result", &[("__to_prompt__", "method"), ("cast_to", "method"), ("exception", "field"), ("exit_status", "field"), ("stdout", "field")]),
    ("slot", &[("get", "method"), ("set", "method"), ("update", "method")]),
    ("str", &[("cast_to", "method"), ("contains", "method"), ("count", "method"), ("endswith", "method"), ("find", "method"), ("format", "method"), ("is_empty", "method"), ("join", "method"), ("len", "method"), ("lower", "method"), ("replace", "method"), ("rfind", "method"), ("split", "method"), ("startswith", "method"), ("strip", "method"), ("to_bool", "method"), ("upper", "method")]),
    ("subscriber", &[("close", "method"), ("recv", "method"), ("recv_nowait", "method")]),
    ("thread", &[("cancel", "method"), ("is_done", "method"), ("join", "method"), ("start", "method")]),
    ("thread_result", &[("error", "method"), ("expect", "method"), ("is_error", "method"), ("is_success", "method"), ("status", "method"), ("unwrap", "method"), ("unwrap_or", "method"), ("value", "method")]),
    ("tuple", &[("__getitem__", "method"), ("cast_to", "method"), ("len", "method")]),
    ("vector", &[("__getitem__", "method"), ("__to_prompt__", "method"), ("add", "method"), ("cast_to", "method"), ("cosine", "method"), ("dim", "method"), ("dot", "method"), ("norm", "method"), ("scale", "method"), ("sub", "method")]),
];
