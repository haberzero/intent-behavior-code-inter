//! scope 符号解析（全量 Rust 化·语义层启动：用户定义符号解析）。
//!
//! 对应 Python 语义层的 scope 符号解析（binding user-defined names to scope symbols）：
//! 遍历 Rust AST，将用户定义的名字（赋值目标 / 函数名）绑定到 scope 符号
//! （`scope_<module>:<name>`）。scope 符号 = 用户定义符号（区别于 intrinsic 符号
//! [内置类型/方法，语义层 intrinsic 符号表产出]）。
//!
//! scope 符号 UID = `scope_<module>:<name>`（module = `__string_exec__`[默认模块名]，
//! name = 用户定义名字）。与 Python 语义层的 scope 符号逐条差分等价（34 语料）。

use std::collections::BTreeMap;

use serde_json::Value;

use crate::parser::{Expr, Module, Stmt};

/// 默认模块名（Python 语义层的 `__string_exec__`）。
const DEFAULT_MODULE: &str = "__string_exec__";

/// scope 符号解析器：Rust AST → scope 符号池（uid → sym_data）。
pub struct SymbolResolver {
    /// scope 符号池（uid → sym_data）。BTreeMap 保证 uid 序（确定性）。
    symbols: BTreeMap<String, Value>,
    /// scope 栈（module scope → function scope ...）。
    scope_stack: Vec<String>,
}

impl SymbolResolver {
    pub fn new() -> Self {
        Self {
            symbols: BTreeMap::new(),
            scope_stack: vec![DEFAULT_MODULE.to_string()],
        }
    }

    /// 当前 scope 串（`__string_exec__` / `__string_exec__/f` / ...）。
    fn current_scope(&self) -> String {
        self.scope_stack.join("/")
    }

    /// 解析 Module → scope 符号池。
    pub fn resolve_module(&mut self, module: &Module) -> &BTreeMap<String, Value> {
        for stmt in &module.body {
            self.resolve_stmt(stmt);
        }
        &self.symbols
    }

    fn resolve_stmt(&mut self, stmt: &Stmt) {
        match stmt {
            Stmt::Assign { targets, .. } => {
                // 赋值目标 → scope 符号（VARIABLE）
                for target in targets {
                    if let Expr::Name { id, .. } = target {
                        self.bind_symbol(id, "VARIABLE");
                    }
                }
                // 递归遍历值（嵌套定义）
                // （赋值目标/函数名绑定在顶层；嵌套经子语句递归）
            }
            Stmt::AugAssign { target, .. } => {
                // 增赋值目标 → scope 符号（VARIABLE，若已绑定则复用）
                if let Expr::Name { id, .. } = target {
                    self.bind_symbol(id, "VARIABLE");
                }
            }
            Stmt::FunctionDef { name, args, body, .. } => {
                // 函数名 → 外层 scope 符号。顶层函数 = FUNCTION；嵌套函数 = VARIABLE
                //（Python 语义层：嵌套函数名是持有函数的变量，非顶层函数定义）。
                let is_top = self.scope_stack.len() == 1;
                let kind = if is_top { "FUNCTION" } else { "VARIABLE" };
                self.bind_symbol(name, kind);
                // 进入函数 scope（绑定参数 + 递归函数体）
                self.scope_stack.push(name.clone());
                for arg in args {
                    self.bind_symbol(&arg.arg, "VARIABLE");
                }
                for s in body {
                    self.resolve_stmt(s);
                }
                self.scope_stack.pop();
            }
            Stmt::For { target, body, orelse, .. } => {
                // for 循环目标 → scope 符号（VARIABLE）
                if let Expr::Name { id, .. } = target {
                    self.bind_symbol(id, "VARIABLE");
                }
                for s in body.iter().chain(orelse) {
                    self.resolve_stmt(s);
                }
            }
            Stmt::Import { names, .. } => {
                // import X → scope 符号（MODULE，导入模块）
                for alias in names {
                    let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
                    self.bind_symbol(&binding, "MODULE");
                }
            }
            Stmt::FromImport { module, names, .. } => {
                // from-import 绑定 → scope 符号（FUNCTION，导入名 = 模块属性[函数/值]）
                for alias in names {
                    let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
                    let _ = module; // module 名（import 绑定用 asname/name）
                    self.bind_symbol(&binding, "FUNCTION");
                }
            }
            Stmt::ClassDef { name, body, .. } => {
                // 类名 → scope 符号（CLASS）
                self.bind_symbol(name, "CLASS");
                for s in body {
                    self.resolve_stmt(s);
                }
            }
            Stmt::If { body, orelse, .. } | Stmt::While { body, orelse, .. } => {
                for s in body {
                    self.resolve_stmt(s);
                }
                for s in orelse {
                    self.resolve_stmt(s);
                }
            }
            Stmt::Try {
                body,
                orelse,
                finalbody,
                ..
            } => {
                for s in body.iter().chain(orelse).chain(finalbody) {
                    self.resolve_stmt(s);
                }
            }
            // 其他语句（Return/Break/Continue/Pass/Import/FromImport/ExprStmt）无绑定
            _ => {}
        }
    }

    /// 绑定符号：scope 符号 UID = `scope_<scope>:<name>`（scope = scope 栈串）。
    fn bind_symbol(&mut self, name: &str, kind: &str) {
        let scope = self.current_scope();
        let uid = format!("scope_{}:{}", scope, name);
        if self.symbols.contains_key(&uid) {
            return; // 已绑定（复用）
        }
        let sym_data = Value::Object(serde_json::Map::from_iter([
            ("uid".to_string(), Value::String(uid.clone())),
            ("name".to_string(), Value::String(name.to_string())),
            ("kind".to_string(), Value::String(kind.to_string())),
            ("metadata".to_string(), Value::Object(serde_json::Map::new())),
            ("node_uid".to_string(), Value::Null),
            ("owned_scope_uid".to_string(), Value::Null),
            ("type_uid".to_string(), Value::Null),
        ]));
        self.symbols.insert(uid, sym_data);
    }
}
