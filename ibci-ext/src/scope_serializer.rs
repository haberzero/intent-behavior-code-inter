//! scope 池（全量 Rust 化·artifact 产出：scopes 池）。
//!
//! 顶层 scope[`scope___string_exec__`] = intrinsic 符号[固定 63，`intrinsic:<name>`] +
//! 用户顶层符号；函数 scope[`scope___string_exec__/f`] = 用户函数内符号，parent =
//! 定义处 scope。global_refs = []（当前语料空）。与 Python 语义层 scopes 池差分等价
//! （Rust ⊆ Python：每个 scope uid/parent_uid + 每个 symbol name→uid 相等；允许
//! Python 多 IMPORT_GATED 符号——intrinsic 固定 63 不含按需引入的 meta/quote/eval）。

use std::collections::BTreeMap;

use serde_json::Value;

use crate::intrinsic_symbols;
use crate::parser;
use crate::symbol_resolver::SymbolResolver;

const TOP_SCOPE: &str = "__string_exec__";

/// scope 池（uid → scope_data）：顶层[intrinsic 63 + 用户顶层] + 函数 scope[用户内符号]。
pub fn scope_pool(source: &str) -> BTreeMap<String, Value> {
    let module = parser::parse_to_module(source);
    let mut resolver = SymbolResolver::new();
    let symbols = resolver.resolve_module(&module);

    // 按 scope 分组用户符号（uid = `scope_<scope串>:<name>`）。
    let mut by_scope: BTreeMap<String, BTreeMap<String, String>> = BTreeMap::new();
    for (uid, sym) in symbols {
        let after = uid.strip_prefix("scope_").unwrap_or(uid.as_str());
        let colon = after.rfind(':').unwrap_or(0);
        let scope_str = after[..colon].to_string();
        let name = sym
            .get("name")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        by_scope.entry(scope_str).or_default().insert(name, uid.clone());
    }

    let mut scopes: BTreeMap<String, Value> = BTreeMap::new();

    // 顶层 scope：intrinsic 63 + 用户顶层符号。
    let mut top_syms: BTreeMap<String, String> = BTreeMap::new();
    for name in intrinsic_symbols::intrinsic_names() {
        top_syms.insert(name.clone(), format!("intrinsic:{}", name));
    }
    if let Some(user_top) = by_scope.get(TOP_SCOPE) {
        for (name, uid) in user_top {
            top_syms.insert(name.clone(), uid.clone());
        }
    }
    scopes.insert(
        format!("scope_{}", TOP_SCOPE),
        scope_value(TOP_SCOPE, None, top_syms),
    );

    // 函数 scope：用户内符号，parent = 定义处 scope（scope 串去最后一段）。
    for (scope_str, syms) in &by_scope {
        if scope_str == TOP_SCOPE {
            continue;
        }
        let parent = parent_scope_str(scope_str);
        scopes.insert(
            format!("scope_{}", scope_str),
            scope_value(scope_str, parent, syms.clone()),
        );
    }
    scopes
}

/// 父 scope 串：`__string_exec__/f` → `__string_exec__`；`__string_exec__/a/b` →
/// `__string_exec__/a`；顶层/无父 → None。
fn parent_scope_str(scope_str: &str) -> Option<String> {
    let parts: Vec<&str> = scope_str.split('/').collect();
    if parts.len() <= 1 {
        return None;
    }
    Some(parts[..parts.len() - 1].join("/"))
}

fn scope_value(
    scope_str: &str,
    parent: Option<String>,
    symbols: BTreeMap<String, String>,
) -> Value {
    let uid = format!("scope_{}", scope_str);
    Value::Object(serde_json::Map::from_iter([
        ("uid".to_string(), Value::String(uid)),
        (
            "parent_uid".to_string(),
            parent
                .map(|p| Value::String(format!("scope_{}", p)))
                .unwrap_or(Value::Null),
        ),
        (
            "symbols".to_string(),
            Value::Object(serde_json::Map::from_iter(
                symbols.into_iter().map(|(k, v)| (k, Value::String(v))),
            )),
        ),
        ("global_refs".to_string(), Value::Array(Vec::new())),
    ]))
}
