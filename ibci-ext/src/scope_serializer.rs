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

    // 函数 scope：AST 结构枚举（每个函数定义建 scope 条目——Python 实证含空符号
    // scope；符号 = by_scope 分组或空集），parent = 定义处 scope。
    let mut fn_scopes: Vec<String> = Vec::new();
    for s in &module.body {
        collect_function_scopes(s, TOP_SCOPE, &mut fn_scopes);
    }
    for scope_str in fn_scopes {
        let parent = parent_scope_str(&scope_str);
        let syms = by_scope.get(&scope_str).cloned().unwrap_or_default();
        scopes.insert(
            format!("scope_{}", scope_str),
            scope_value(&scope_str, parent, syms),
        );
    }
    scopes
}

/// 函数 scope 串枚举（全深度：函数嵌套 + if/for/while/try/class 体内的函数定义；
/// scope 串 = 定义处 scope 串 + "/" + 函数名）。
fn collect_function_scopes(
    stmt: &crate::parser::Stmt,
    scope_str: &str,
    out: &mut Vec<String>,
) {
    use crate::parser::Stmt;
    match stmt {
        Stmt::FunctionDef { name, body, .. } => {
            let child = format!("{}/{}", scope_str, name);
            for s in body {
                collect_function_scopes(s, &child, out);
            }
            out.push(child);
        }
        Stmt::If { body, orelse, .. }
        | Stmt::For { body, orelse, .. }
        | Stmt::While { body, orelse, .. } => {
            for s in body.iter().chain(orelse.iter()) {
                collect_function_scopes(s, scope_str, out);
            }
        }
        Stmt::Try {
            body,
            handlers,
            orelse,
            finalbody,
            ..
        } => {
            for s in body.iter().chain(orelse.iter()).chain(finalbody.iter()) {
                collect_function_scopes(s, scope_str, out);
            }
            for h in handlers {
                for s in &h.body {
                    collect_function_scopes(s, scope_str, out);
                }
            }
        }
        Stmt::ClassDef { body, .. } => {
            for s in body {
                collect_function_scopes(s, scope_str, out);
            }
        }
        _ => {}
    }
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
