//! scope 符号解析 + 类型推导（全量 Rust 化·语义层：用户定义符号 + node 绑定 + type_uid）。
//!
//! 对应 Python 语义层的 scope 符号解析 + 类型解析：遍历 Rust AST，将用户定义名字绑定到
//! scope 符号（`scope_<scope>:<name>`），计算 node_uid（定义节点 UID，经 node_serializer）
//! + type_uid（类型——对齐 IBCI 公理驱动类型推导：类型环境[作用域栈] + 运算符公理表 +
//! 函数签名，经 type_inference）。
//!
//! 类型推导即时进行（遍历中）：赋值右值类型 → 类型环境 + 符号 type_uid；函数 returns /
//! 参数注解 → 签名表 / 类型环境。与 Python 语义层逐条差分等价（34 语料）。

use std::collections::BTreeMap;

use serde_json::Value;

use crate::node_serializer::NodeSerializer;
use crate::parser::{Arg, Expr, Module, Stmt};
use crate::type_inference::{infer_type_env, parse_type_annotation, FuncSignatures, TypeEnv};

/// 默认模块名（Python 语义层的 `__string_exec__`）。
const DEFAULT_MODULE: &str = "__string_exec__";

/// 定义节点（符号绑定到的 AST 节点）。Stmt / Arg 两种。
enum DefNode<'a> {
    Stmt(&'a Stmt),
    Arg(&'a Arg),
}

/// scope 符号解析器：Rust AST → scope 符号池（uid → sym_data，含 node_uid + type_uid）。
/// 生命周期 `'a` 绑定 AST（def_nodes 持有 AST 节点引用）。
pub struct SymbolResolver<'a> {
    /// scope 符号池（uid → sym_data）。BTreeMap 保证 uid 序（确定性）。
    symbols: BTreeMap<String, Value>,
    /// scope 栈（module scope → function scope ...）。
    scope_stack: Vec<String>,
    /// 定义节点（符号 uid → 定义节点）。
    def_nodes: BTreeMap<String, DefNode<'a>>,
    /// 类型环境（作用域栈，与 scope_stack 同步）：每 scope 一个 Name→类型字符串 map。
    type_env: TypeEnv,
    /// 函数签名表：函数名 → 返回类型字符串（returns 注解，intrinsic Name 子集）。
    func_sigs: FuncSignatures,
}

impl<'a> SymbolResolver<'a> {
    pub fn new() -> Self {
        Self {
            symbols: BTreeMap::new(),
            scope_stack: vec![DEFAULT_MODULE.to_string()],
            def_nodes: BTreeMap::new(),
            type_env: vec![BTreeMap::new()],
            func_sigs: BTreeMap::new(),
        }
    }

    /// 当前 scope 串（`__string_exec__` / `__string_exec__/f` / ...）。
    fn current_scope(&self) -> String {
        self.scope_stack.join("/")
    }

    /// push 函数 scope（scope_stack + type_env 同步，单一权威源避免两者漂移）。
    fn push_scope(&mut self, name: &str) {
        self.scope_stack.push(name.to_string());
        self.type_env.push(BTreeMap::new());
    }

    /// pop 函数 scope（scope_stack + type_env 同步）。
    fn pop_scope(&mut self) {
        self.scope_stack.pop();
        self.type_env.pop();
    }

    /// 绑定变量类型：符号 type_uid（type_root.<类型>）+ 类型环境（当前 scope）。
    fn bind_var_type(&mut self, name: &str, type_str: &str) {
        let scope = self.current_scope();
        let uid = format!("scope_{}:{}", scope, name);
        if let Some(sym) = self.symbols.get_mut(&uid) {
            if let Some(map) = sym.as_object_mut() {
                map.insert(
                    "type_uid".to_string(),
                    Value::String(format!("type_root.{}", type_str)),
                );
            }
        }
        if let Some(last) = self.type_env.last_mut() {
            last.insert(name.to_string(), type_str.to_string());
        }
    }

    /// 解析 Module → scope 符号池（含 node_uid + type_uid）。
    pub fn resolve_module(&mut self, module: &'a Module) -> &BTreeMap<String, Value> {
        for stmt in &module.body {
            self.resolve_stmt(stmt);
        }
        // node 绑定：计算每个定义符号的 node_uid（经 node_serializer）。
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
        &self.symbols
    }

    fn resolve_stmt(&mut self, stmt: &'a Stmt) {
        match stmt {
            Stmt::Assign { targets, value, .. } => {
                // 赋值目标 → scope 符号（VARIABLE）+ 即时类型解析（类型环境 + 函数签名）。
                let type_str: Option<String> = value
                    .as_ref()
                    .and_then(|v| infer_type_env(v, &self.type_env, &self.func_sigs));
                for target in targets {
                    if let Expr::Name { id, .. } = target {
                        self.bind_symbol(id, "VARIABLE", Some(DefNode::Stmt(stmt)));
                        if let Some(ts) = &type_str {
                            self.bind_var_type(id, ts);
                        }
                    }
                }
            }
            Stmt::AugAssign { target, .. } => {
                // 增赋值目标 → scope 符号（VARIABLE，定义节点 = IbAugAssign）。
                if let Expr::Name { id, .. } = target {
                    self.bind_symbol(id, "VARIABLE", Some(DefNode::Stmt(stmt)));
                }
            }
            Stmt::FunctionDef { name, args, body, returns, .. } => {
                // 函数名 → 外层 scope 符号。顶层函数 = FUNCTION；嵌套函数 = VARIABLE
                //（Python 语义层：嵌套函数名是持有函数的变量，非顶层函数定义）。
                let is_top = self.scope_stack.len() == 1;
                let kind = if is_top { "FUNCTION" } else { "VARIABLE" };
                let def_scope = self.current_scope();
                self.bind_symbol(name, kind, Some(DefNode::Stmt(stmt)));
                // 嵌套函数名 = 函数类型（type_root.<name>）—— 持有函数的变量类型。
                if !is_top {
                    self.bind_var_type(name, name);
                }
                // 函数返回类型 → 签名表（returns 注解，intrinsic Name 子集）。
                if let Some(rt) = returns {
                    if let Some(ts) = parse_type_annotation(rt) {
                        self.func_sigs.insert(name.clone(), ts);
                    }
                }
                // 进入函数 scope（绑定参数 + 递归函数体）。
                self.push_scope(name);
                // 函数符号 owned_scope_uid = 函数体 scope 的 UID（scope_<函数体 scope 串>）。
                let func_uid = format!("scope_{}:{}", def_scope, name);
                let owned = format!("scope_{}", self.current_scope());
                if let Some(sym) = self.symbols.get_mut(&func_uid) {
                    if let Some(map) = sym.as_object_mut() {
                        map.insert("owned_scope_uid".to_string(), Value::String(owned));
                    }
                }
                for arg in args {
                    // 参数 → scope 符号（VARIABLE）+ 注解类型。
                    self.bind_symbol(&arg.arg, "VARIABLE", Some(DefNode::Arg(arg)));
                    if let Some(ann) = &arg.annotation {
                        if let Some(ts) = parse_type_annotation(ann) {
                            self.bind_var_type(&arg.arg, &ts);
                        }
                    }
                }
                for s in body {
                    self.resolve_stmt(s);
                }
                self.pop_scope();
            }
            Stmt::For { target, body, orelse, .. } => {
                // for 循环目标 → scope 符号（VARIABLE）+ 类型 = any（IBCI：iter 类型不推断）。
                if let Expr::Name { id, .. } = target {
                    self.bind_symbol(id, "VARIABLE", Some(DefNode::Stmt(stmt)));
                    self.bind_var_type(id, "any");
                }
                for s in body.iter().chain(orelse) {
                    self.resolve_stmt(s);
                }
            }
            Stmt::Import { names, .. } => {
                // import X → scope 符号（MODULE）。import 模块绑定无定义节点（node_uid=null）。
                for alias in names {
                    let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
                    self.bind_symbol(&binding, "MODULE", None);
                }
            }
            Stmt::FromImport { module, names, .. } => {
                // from-import 绑定 → scope 符号（FUNCTION）。无定义节点（node_uid=null）。
                for alias in names {
                    let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
                    let _ = module;
                    self.bind_symbol(&binding, "FUNCTION", None);
                }
            }
            Stmt::ClassDef { name, body, .. } => {
                // 类名 → scope 符号（CLASS，定义节点 = IbClassDef）。
                self.bind_symbol(name, "CLASS", Some(DefNode::Stmt(stmt)));
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
    fn bind_symbol(&mut self, name: &str, kind: &str, def_node: Option<DefNode<'a>>) {
        let scope = self.current_scope();
        let uid = format!("scope_{}:{}", scope, name);
        if self.symbols.contains_key(&uid) {
            return; // 已绑定（复用）
        }
        if let Some(def) = def_node {
            self.def_nodes.insert(uid.clone(), def);
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
