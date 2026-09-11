//! scope 符号解析 + 类型推导（全量 Rust 化·语义层：用户定义符号 + node 绑定 + type_uid）。
//!
//! 对应 Python 语义层的 scope 符号解析 + 类型解析：遍历 Rust AST，将用户定义名字绑定到
//! scope 符号（`scope_<scope>:<name>`），计算 node_uid（定义节点 UID，经 node_serializer）
//! + type_uid（类型——对齐 IBCI 公理驱动类型推导：类型环境[作用域栈] + 运算符公理表 +
//! 函数签名，经 type_inference）。
//!
//! 类型推导即时进行（遍历中）：赋值右值类型 → 类型环境 + 符号 type_uid；函数 returns /
//! 参数注解 → 签名表 / 类型环境。与 Python 语义层逐条差分等价（34 语料）。

use std::collections::{BTreeMap, BTreeSet};

use serde_json::Value;

use crate::node_serializer::NodeSerializer;
use crate::parser::{Expr, Module, Stmt};
use crate::type_inference::{
    parse_type_annotation, symbol_level_type, FuncSignatures, InferCtx, ModuleNames, TypeEnv,
};

/// 默认模块名（Python 语义层的 `__string_exec__`）。
const DEFAULT_MODULE: &str = "__string_exec__";

/// scope 符号解析器：Rust AST → scope 符号池（uid → sym_data，含 node_uid + type_uid）。
/// node_uid = 定义节点 UID，经 NodeSerializer 统一遍历在 scope 上下文内产出
/// （def_node_uids——非事后重序列化：嵌套函数 free_vars 等 scope 相关节点内容只在
/// 定义处上下文可正确产出）。
pub struct SymbolResolver {
    /// scope 符号池（uid → sym_data）。BTreeMap 保证 uid 序（确定性）。
    symbols: BTreeMap<String, Value>,
    /// scope 栈（module scope → function scope ...）。
    scope_stack: Vec<String>,
    /// 类型环境（作用域栈，与 scope_stack 同步）：每 scope 一个 Name→类型字符串 map。
    type_env: TypeEnv,
    /// 函数签名表：函数名 → 返回类型字符串（returns 注解，intrinsic Name 子集）。
    func_sigs: FuncSignatures,
    /// 导入模块名集合（`import X` 的绑定名——模块成员属性解析，type_inference 共用）。
    modules: ModuleNames,
}

impl SymbolResolver {
    pub fn new() -> Self {
        Self {
            symbols: BTreeMap::new(),
            scope_stack: vec![DEFAULT_MODULE.to_string()],
            type_env: vec![BTreeMap::new()],
            func_sigs: BTreeMap::new(),
            modules: BTreeSet::new(),
        }
    }

    /// 推导上下文（type_env + func_sigs + modules——type_inference 单一入口）。
    fn ctx(&self) -> InferCtx<'_> {
        InferCtx {
            type_env: &self.type_env,
            func_sigs: &self.func_sigs,
            modules: &self.modules,
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
    pub fn resolve_module(&mut self, module: &Module) -> &BTreeMap<String, Value> {
        for stmt in &module.body {
            self.resolve_stmt(stmt);
        }
        // node 绑定：定义符号的 node_uid = 统一遍历（NodeSerializer）在 scope 上下文
        // 内记录的 def_node_uids（首次定义优先）。
        let mut serializer = NodeSerializer::new();
        let (_root, _pool) = serializer.serialize_module(module);
        let def_uids = serializer.def_node_uids_map();
        for (uid, sym) in &mut self.symbols {
            if let Some(node_uid) = def_uids.get(uid) {
                if let Some(map) = sym.as_object_mut() {
                    map.insert("node_uid".to_string(), Value::String(node_uid.clone()));
                }
            }
        }
        &self.symbols
    }

    fn resolve_stmt(&mut self, stmt: &Stmt) {
        match stmt {
            Stmt::Assign { targets, value, .. } => {
                // 赋值目标 → scope 符号（VARIABLE）+ 即时类型解析（符号通道：类型环境 +
                // 函数签名 + 声明返回类型——meta.eval() = auto，与节点通道 any 分离）。
                // 首次绑定优先：符号已有 type_uid 不覆盖（IBCI 变量类型 = 首次声明定型；
                // 语料实证 arithmetic_loop：total = total + i 保持 int，不经 any 传播退化）。
                let type_str: Option<String> =
                    value.as_ref().and_then(|v| symbol_level_type(v, &self.ctx()));
                for target in targets {
                    match target {
                        Expr::Name { id, .. } => {
                            self.bind_symbol(id, "VARIABLE");
                            let scope = self.current_scope();
                            let uid = format!("scope_{}:{}", scope, id);
                            let has_type = self
                                .symbols
                                .get(&uid)
                                .and_then(|s| s.get("type_uid"))
                                .and_then(|v| v.as_str())
                                .is_some();
                            if !has_type {
                                if let Some(ts) = &type_str {
                                    self.bind_var_type(id, ts);
                                }
                            }
                        }
                        // 声明面（TypeAnnotatedExpr target）：声明类型优先
                        // （auto = 值推导符号通道类型）
                        Expr::TypeAnnotatedExpr {
                            target: inner,
                            annotation,
                            ..
                        } => {
                            if let Expr::Name { id, .. } = inner.as_ref() {
                                self.bind_symbol(id, "VARIABLE");
                                let scope = self.current_scope();
                                let uid = format!("scope_{}:{}", scope, id);
                                let has_type = self
                                    .symbols
                                    .get(&uid)
                                    .and_then(|s| s.get("type_uid"))
                                    .and_then(|v| v.as_str())
                                    .is_some();
                                if !has_type {
                                    let ann = crate::node_serializer::annotation_type_str(
                                        annotation,
                                    );
                                    // auto / fn 可调用声明 = 值推导
                                    let ts = if ann == "auto" || ann == "fn" {
                                        type_str.clone()
                                    } else {
                                        Some(ann)
                                    };
                                    if let Some(ts) = ts {
                                        self.bind_var_type(id, &ts);
                                    }
                                }
                            }
                        }
                        // 元组解包声明 target（逐分量绑定；定义节点 = Assign 节点
                        // 经 def_node_uids 统一记录）
                        Expr::Tuple { elts, .. } => {
                            for e in elts {
                                if let Expr::TypeAnnotatedExpr {
                                    target: inner,
                                    annotation,
                                    ..
                                } = e
                                {
                                    if let Expr::Name { id, .. } = inner.as_ref() {
                                        self.bind_symbol(id, "VARIABLE");
                                        let scope = self.current_scope();
                                        let uid = format!("scope_{}:{}", scope, id);
                                        let has_type = self
                                            .symbols
                                            .get(&uid)
                                            .and_then(|s| s.get("type_uid"))
                                            .and_then(|v| v.as_str())
                                            .is_some();
                                        if !has_type {
                                            let ann = crate::node_serializer::annotation_type_str(
                                                annotation,
                                            );
                                            // auto / fn 可调用声明 = 值推导
                                            let ts =
                                                if ann == "auto" || ann == "fn" {
                                                    type_str.clone()
                                                } else {
                                                    Some(ann)
                                                };
                                            if let Some(ts) = ts {
                                                self.bind_var_type(id, &ts);
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        _ => {}
                    }
                }
            }
            Stmt::AugAssign { target, .. } => {
                // 增赋值目标 → scope 符号（VARIABLE，定义节点 = IbAugAssign）。
                if let Expr::Name { id, .. } = target {
                    self.bind_symbol(id, "VARIABLE");
                }
            }
            Stmt::FunctionDef { name, args, body, returns, .. } => {
                // 函数名 → 外层 scope 符号。顶层函数 = FUNCTION；嵌套函数 = VARIABLE
                //（Python 语义层：嵌套函数名是持有函数的变量，非顶层函数定义）。
                let is_top = self.scope_stack.len() == 1;
                let kind = if is_top { "FUNCTION" } else { "VARIABLE" };
                let def_scope = self.current_scope();
                self.bind_symbol(name, kind);
                // 函数名符号 type_uid = 函数类型（type_root.<name>）——顶层 FUNCTION
                // 与嵌套（VARIABLE 持有函数的变量）同语义（Python 实证：scope 符号
                // type_uid = type_root.<name>）。
                self.bind_var_type(name, name);
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
                    self.bind_symbol(&arg.arg, "VARIABLE");
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
                    self.bind_symbol(id, "VARIABLE");
                    self.bind_var_type(id, "any");
                }
                for s in body.iter().chain(orelse) {
                    self.resolve_stmt(s);
                }
            }
            Stmt::Import { names, .. } => {
                // import X → scope 符号（MODULE）+ modules 集（模块成员属性解析依据）。
                // import 模块绑定无定义节点（node_uid=null）。
                for alias in names {
                    let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
                    self.modules.insert(binding.clone());
                    self.bind_symbol(&binding, "MODULE");
                    // MODULE 符号 type_uid = 模块类型（type_root.<name>，Python 实证）
                    self.bind_var_type(&binding, &binding);
                }
            }
            Stmt::FromImport { module, names, .. } => {
                // from-import 绑定 → scope 符号（FUNCTION）。无定义节点（node_uid=null）。
                for alias in names {
                    let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
                    let _ = module;
                    self.bind_symbol(&binding, "FUNCTION");
                    // from-import FUNCTION 符号 type_uid = 函数类型（Python 实证：
                    // scope___string_exec__:quote → type_root.quote）
                    self.bind_var_type(&binding, &binding);
                }
            }
            Stmt::ClassDef { name, body, .. } => {
                // 类名 → scope 符号（CLASS）+ type_uid = 类类型（type_root.<name>）。
                self.bind_symbol(name, "CLASS");
                self.bind_var_type(name, name);
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
                handlers,
                orelse,
                finalbody,
                ..
            } => {
                for s in body.iter().chain(orelse).chain(finalbody) {
                    self.resolve_stmt(s);
                }
                for h in handlers {
                    // except 变量 = 全局 scope 符号（Python 实证：runtime_context
                    // 全局面——越 try 块可见；type = any）
                    if let Some(name) = &h.name {
                        let top = self.scope_stack.first().cloned().unwrap_or_else(|| self.current_scope());
                        let uid = format!("scope_{}:{}", top, name);
                        if !self.symbols.contains_key(&uid) {
                            let sym_data = Value::Object(serde_json::Map::from_iter([
                                ("uid".to_string(), Value::String(uid.clone())),
                                ("name".to_string(), Value::String(name.clone())),
                                ("kind".to_string(), Value::String("VARIABLE".to_string())),
                                ("metadata".to_string(), Value::Object(serde_json::Map::new())),
                                ("node_uid".to_string(), Value::Null),
                                ("owned_scope_uid".to_string(), Value::Null),
                                ("type_uid".to_string(), Value::String("type_root.any".to_string())),
                            ]));
                            self.symbols.insert(uid, sym_data);
                        }
                    }
                    for s in &h.body {
                        self.resolve_stmt(s);
                    }
                }
            }
            // 其他语句（Return/Break/Continue/Pass/ExprStmt）无绑定
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
