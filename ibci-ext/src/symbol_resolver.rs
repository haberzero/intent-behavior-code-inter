//! scope 符号解析（全量 Rust 化·语义层启动：用户定义符号解析 + node 绑定）。
//!
//! 对应 Python 语义层的 scope 符号解析（binding user-defined names to scope symbols）：
//! 遍历 Rust AST，将用户定义的名字（赋值目标 / 函数名 / 参数 / for 目标 / import 绑定）
//! 绑定到 scope 符号（`scope_<scope>:<name>`）。scope 符号 = 用户定义符号（区别于
//! intrinsic 符号[内置类型/函数/模块，语义层 intrinsic 符号表产出]）。
//!
//! scope 符号 UID = `scope_<scope>:<name>`（scope = scope 栈串）。node 绑定 = 符号的
//! 定义节点 UID（node_uid，经 node_serializer 计算）：赋值目标 → IbAssign / 函数名 →
//! IbFunctionDef / 参数 → IbArg / for 目标 → IbFor / import 绑定 → IbImport。与 Python
//! 语义层的 scope 符号逐条差分等价（34 语料）。

use std::collections::BTreeMap;

use serde_json::Value;

use crate::node_serializer::NodeSerializer;
use crate::parser::{Arg, Expr, Module, Stmt};
use crate::type_inference;

/// 默认模块名（Python 语义层的 `__string_exec__`）。
const DEFAULT_MODULE: &str = "__string_exec__";

/// 定义节点（符号绑定到的 AST 节点）。Stmt / Arg 两种。
enum DefNode<'a> {
    Stmt(&'a Stmt),
    Arg(&'a Arg),
}

/// scope 符号解析器：Rust AST → scope 符号池（uid → sym_data，含 node_uid）。
/// 生命周期 `'a` 绑定 AST（def_nodes 持有 AST 节点引用）。
pub struct SymbolResolver<'a> {
    /// scope 符号池（uid → sym_data）。BTreeMap 保证 uid 序（确定性）。
    symbols: BTreeMap<String, Value>,
    /// scope 栈（module scope → function scope ...）。
    scope_stack: Vec<String>,
    /// 定义节点（符号 uid → 定义节点）。
    def_nodes: BTreeMap<String, DefNode<'a>>,
    /// 值表达式（VARIABLE 符号 uid → 赋值右值表达式，供类型解析）。
    value_exprs: BTreeMap<String, &'a Expr>,
}

impl<'a> SymbolResolver<'a> {
    pub fn new() -> Self {
        Self {
            symbols: BTreeMap::new(),
            scope_stack: vec![DEFAULT_MODULE.to_string()],
            def_nodes: BTreeMap::new(),
            value_exprs: BTreeMap::new(),
        }
    }

    /// 当前 scope 串（`__string_exec__` / `__string_exec__/f` / ...）。
    fn current_scope(&self) -> String {
        self.scope_stack.join("/")
    }

    /// 解析 Module → scope 符号池（含 node_uid）。
    pub fn resolve_module(&mut self, module: &'a Module) -> &BTreeMap<String, Value> {
        for stmt in &module.body {
            self.resolve_stmt(stmt);
        }
        // node 绑定：计算每个定义符号的 node_uid（经 node_serializer）
        let mut serializer = NodeSerializer::new();
        serializer.serialize_module(module);
        for (uid, def_node) in &self.def_nodes {
            let node_uid = match def_node {
                DefNode::Stmt(stmt) => serializer.serialize_stmt(stmt),
                DefNode::Arg(arg) => serializer.serialize_arg(arg),
            };
            if let Some(sym) = self.symbols.get_mut(uid) {
                if let Some(map) = sym.as_object_mut() {
                    map.insert("node_uid".to_string(), Value::String(node_uid));
                }
            }
        }
        // 类型解析：计算 VARIABLE 符号的 type_uid（经 type_inference，字面值可推断子集）
        for (uid, value_expr) in &self.value_exprs {
            if let Some(type_str) = type_inference::infer_type(value_expr) {
                if let Some(sym) = self.symbols.get_mut(uid) {
                    if let Some(map) = sym.as_object_mut() {
                        map.insert(
                            "type_uid".to_string(),
                            Value::String(format!("type_root.{}", type_str)),
                        );
                    }
                }
            }
        }
        &self.symbols
    }

    fn resolve_stmt(&mut self, stmt: &'a Stmt) {
        match stmt {
            Stmt::Assign { targets, value, .. } => {
                // 赋值目标 → scope 符号（VARIABLE，定义节点 = IbAssign，值表达式供类型解析）
                let v_expr = value.as_ref();
                for target in targets {
                    if let Expr::Name { id, .. } = target {
                        self.bind_symbol(id, "VARIABLE", Some(DefNode::Stmt(stmt)), v_expr);
                    }
                }
            }
            Stmt::AugAssign { target, .. } => {
                // 增赋值目标 → scope 符号（VARIABLE，定义节点 = IbAugAssign）
                if let Expr::Name { id, .. } = target {
                    self.bind_symbol(id, "VARIABLE", Some(DefNode::Stmt(stmt)), None);
                }
            }
            Stmt::FunctionDef { name, args, body, .. } => {
                // 函数名 → 外层 scope 符号。顶层函数 = FUNCTION；嵌套函数 = VARIABLE
                //（Python 语义层：嵌套函数名是持有函数的变量，非顶层函数定义）。
                // 定义节点 = IbFunctionDef。
                let is_top = self.scope_stack.len() == 1;
                let kind = if is_top { "FUNCTION" } else { "VARIABLE" };
                self.bind_symbol(name, kind, Some(DefNode::Stmt(stmt)), None);
                // 进入函数 scope（绑定参数 + 递归函数体）
                self.scope_stack.push(name.clone());
                for arg in args {
                    // 参数 → scope 符号（VARIABLE，定义节点 = IbArg）
                    self.bind_symbol(&arg.arg, "VARIABLE", Some(DefNode::Arg(arg)), None);
                }
                for s in body {
                    self.resolve_stmt(s);
                }
                self.scope_stack.pop();
            }
            Stmt::For { target, body, orelse, .. } => {
                // for 循环目标 → scope 符号（VARIABLE，定义节点 = IbFor）
                if let Expr::Name { id, .. } = target {
                    self.bind_symbol(id, "VARIABLE", Some(DefNode::Stmt(stmt)), None);
                }
                for s in body.iter().chain(orelse) {
                    self.resolve_stmt(s);
                }
            }
            Stmt::Import { names, .. } => {
                // import X → scope 符号（MODULE）。Python 语义层：import 模块绑定无
                // 定义节点（node_uid = null），故不传定义节点。
                for alias in names {
                    let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
                    self.bind_symbol(&binding, "MODULE", None, None);
                }
            }
            Stmt::FromImport { module, names, .. } => {
                // from-import 绑定 → scope 符号（FUNCTION）。Python 语义层：from-import
                // 绑定无定义节点（node_uid = null），故不传定义节点。
                for alias in names {
                    let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
                    let _ = module; // module 名（import 绑定用 asname/name）
                    self.bind_symbol(&binding, "FUNCTION", None, None);
                }
            }
            Stmt::ClassDef { name, body, .. } => {
                // 类名 → scope 符号（CLASS，定义节点 = IbClassDef）
                self.bind_symbol(name, "CLASS", Some(DefNode::Stmt(stmt)), None);
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
            // 其他语句（Return/Break/Continue/Pass/ExprStmt）无绑定
            _ => {}
        }
    }

    /// 绑定符号：scope 符号 UID = `scope_<scope>:<name>`（scope = scope 栈串）。
    /// `value_expr` = 赋值右值表达式（VARIABLE 符号，供类型解析）。
    fn bind_symbol(
        &mut self,
        name: &str,
        kind: &str,
        def_node: Option<DefNode<'a>>,
        value_expr: Option<&'a Expr>,
    ) {
        let scope = self.current_scope();
        let uid = format!("scope_{}:{}", scope, name);
        if self.symbols.contains_key(&uid) {
            return; // 已绑定（复用）
        }
        if let Some(def) = def_node {
            self.def_nodes.insert(uid.clone(), def);
        }
        if let Some(v) = value_expr {
            self.value_exprs.insert(uid.clone(), v);
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
