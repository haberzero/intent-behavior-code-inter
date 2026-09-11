//! 节点数据序列化（全量 Rust 化·序列化面：Rust AST → node_data dict）。
//!
//! 对应 Python FlatSerializer._collect_node：AST 节点 → node_data dict（_type + 基类
//! 位置字段[lineno/col_offset/end_lineno/end_col_offset] + 节点字段 + 节点引用[UID]）
//! → content_str[json.dumps(node_data, sort_keys=True)] → node_uid[sha256[:16]] →
//! 节点池[uid → node_data]。Rust 化后与 Python 节点池逐条差分等价（34 语料）。
//!
//! 关键：content_str 的 JSON 格式须匹配 Python json.dumps[node_data, sort_keys=True]
//! ——键字母序 + `": "` 分隔 + `", "` 对间分隔 + 值格式[string 带引号 JSON 转义 / int
//! 原样 / null / list[", " 分隔]]。自定义 JSON 序列化器实现该格式（serde_json::to_
//! string 用 `","`/`":"` 无空格，不匹配）。

use std::collections::{BTreeMap, BTreeSet, HashMap};

use serde_json::{Map, Value};

use crate::parser::{ConstVal, Expr, Module, Pos, Stmt};
use crate::serialization;
use crate::type_inference::{
    infer_type_env, parse_type_annotation, symbol_level_type, FuncSignatures, InferCtx,
    ModuleNames, TypeEnv,
};

/// 节点序列化器：Rust AST → 节点池（uid → node_data）。
pub struct NodeSerializer {
    node_pool: HashMap<String, Value>,
    // 统一遍历：scope 栈 + type_env + func_sigs + modules（复用 SymbolResolver 逻辑）
    // + node_to_type 侧表[node_uid → type_uid，复用 type_inference 完整节点规则推导]。
    scope_stack: Vec<String>,
    type_env: TypeEnv,
    func_sigs: FuncSignatures,
    modules: ModuleNames,
    node_to_type: BTreeMap<String, String>,
}

impl NodeSerializer {
    pub fn new() -> Self {
        // 顶层 scope type_env 绑定全 63 intrinsic 符号名（42 类型 + 19 函数 + 2 模块，
        // 与 scope 池"顶层 scope = intrinsic 63 + 用户顶层"语义同构）：IbName 固有名字
        // → type_root.<name>（函数类型/类类型/模块类型，语料实证对齐 Python）。
        let top_env: BTreeMap<String, String> = crate::intrinsic_symbols::intrinsic_names()
            .into_iter()
            .map(|n| (n.clone(), n))
            .collect();
        Self {
            node_pool: HashMap::new(),
            scope_stack: vec!["__string_exec__".to_string()],
            type_env: vec![top_env],
            func_sigs: BTreeMap::new(),
            modules: BTreeSet::new(),
            node_to_type: BTreeMap::new(),
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

    /// push 函数 scope（scope_stack + type_env 同步，单一权威源避免漂移）。
    fn push_scope(&mut self, name: &str) {
        self.scope_stack.push(name.to_string());
        self.type_env.push(BTreeMap::new());
    }

    /// pop 函数 scope（scope_stack + type_env 同步）。
    fn pop_scope(&mut self) {
        self.scope_stack.pop();
        self.type_env.pop();
    }

    /// 类型环境绑定（当前 scope 的 Name → 类型串）——供 infer_type_env 推导。
    fn bind_type_env(&mut self, name: &str, type_str: &str) {
        if let Some(scope) = self.type_env.last_mut() {
            scope.insert(name.to_string(), type_str.to_string());
        }
    }

    /// 序列化 Module → 根节点 UID + 节点池。
    pub fn serialize_module(&mut self, module: &Module) -> (String, HashMap<String, Value>) {
        let root_uid = self.serialize_module_node(module);
        (root_uid, std::mem::take(&mut self.node_pool))
    }

    /// node_to_type 侧表（node_uid → type_uid）——统一遍历产出（复用 type_inference）。
    pub fn node_to_type_map(&mut self) -> BTreeMap<String, String> {
        std::mem::take(&mut self.node_to_type)
    }

    /// Module 节点：{"_type": "IbModule", 基类位置, body: [UIDs], file_path: null}。
    fn serialize_module_node(&mut self, module: &Module) -> String {
        let body: Vec<String> = module.body.iter().map(|s| self.serialize_stmt(s)).collect();
        let mut node_data = base_fields(&module.pos);
        node_data.insert("_type".to_string(), Value::String("IbModule".to_string()));
        node_data.insert("body".to_string(), Value::Array(body.into_iter().map(Value::String).collect()));
        node_data.insert("file_path".to_string(), Value::Null);
        self.collect(node_data)
    }

    /// 语句节点分发（pub：供符号解析计算定义节点 UID）。
    pub fn serialize_stmt(&mut self, stmt: &Stmt) -> String {
        match stmt {
            Stmt::Assign { pos, targets, value } => {
                let t_uids: Vec<String> = targets.iter().map(|e| self.serialize_expr(e)).collect();
                let v_uid = value.as_ref().map(|e| self.serialize_expr(e));
                // 统一遍历：双通道（type_inference 裁定语义）+ 首次绑定优先——
                // target 节点 node_to_type / type_env 绑定：变量当前 scope 已有类型 =
                // 保持既有（语料实证 arithmetic_loop：total = total + i 的 target 节点与
                // 符号 = int，非右值节点通道 any）；新变量 = 值节点通道类型（target
                // 节点）/ 符号通道类型（type_env，meta.eval() = 声明 auto，与节点通道
                // any 分离）。
                if let Some(v) = value {
                    let ctx = self.ctx();
                    let node_t = infer_type_env(v, &ctx);
                    let sym_t = symbol_level_type(v, &ctx);
                    for (t, t_uid) in targets.iter().zip(t_uids.iter()) {
                        if let Expr::Name { id, .. } = t {
                            let existing = self
                                .type_env
                                .last()
                                .and_then(|s| s.get(id))
                                .cloned();
                            if let Some(ts) = existing.clone().or(sym_t.clone()) {
                                self.bind_type_env(id, &ts);
                            }
                            if let Some(ts) = existing.or(node_t.clone()) {
                                self.node_to_type.insert(t_uid.clone(), format!("type_root.{}", ts));
                            }
                        }
                    }
                }
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbAssign".to_string()));
                node_data.insert("targets".to_string(), Value::Array(t_uids.into_iter().map(Value::String).collect()));
                node_data.insert("value".to_string(), v_uid.map(Value::String).unwrap_or(Value::Null));
                node_data.insert("llmexcept_handler".to_string(), Value::Null);
                self.collect(node_data)
            }
            Stmt::AugAssign { pos, target, op, value } => {
                let t_uid = self.serialize_expr(target);
                let v_uid = self.serialize_expr(value);
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbAugAssign".to_string()));
                node_data.insert("target".to_string(), Value::String(t_uid));
                node_data.insert("op".to_string(), Value::String(op.clone()));
                node_data.insert("value".to_string(), Value::String(v_uid));
                self.collect(node_data)
            }
            Stmt::ExprStmt { pos, value } => {
                let v_uid = self.serialize_expr(value);
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbExprStmt".to_string()));
                node_data.insert("value".to_string(), Value::String(v_uid));
                node_data.insert("llmexcept_handler".to_string(), Value::Null);
                self.collect(node_data)
            }
            Stmt::Import { pos, names } => {
                let a_uids: Vec<String> = names.iter().map(|a| self.serialize_alias(a)).collect();
                // 统一遍历：import 模块名 → modules 集 + type_env 绑定（IbName 模块名 →
                // type_root.<name>；模块成员属性解析依据——语料实证 meta → type_root.meta）。
                for alias in names {
                    let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
                    self.modules.insert(binding.clone());
                    self.bind_type_env(&binding, &binding);
                }
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbImport".to_string()));
                node_data.insert("names".to_string(), Value::Array(a_uids.into_iter().map(Value::String).collect()));
                self.collect(node_data)
            }
            Stmt::FromImport { pos, module, names } => {
                let a_uids: Vec<String> = names.iter().map(|a| self.serialize_alias(a)).collect();
                // 统一遍历：from-import 绑定名 → type_env（IbName 绑定名 → 源函数/类型
                // 的 type_root.<name>——语料实证 from meta import quote：quote → type_root.quote）。
                for alias in names {
                    let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
                    self.bind_type_env(&binding, &binding);
                }
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbImportFrom".to_string()));
                node_data.insert("module".to_string(), Value::String(module.clone()));
                node_data.insert("names".to_string(), Value::Array(a_uids.into_iter().map(Value::String).collect()));
                // Python IbImportFrom.level = 0（Rust parser 未承载 level，对齐默认值）
                node_data.insert("level".to_string(), Value::from(0));
                self.collect(node_data)
            }
            Stmt::If { pos, test, body, orelse } => {
                let t_uid = self.serialize_expr(test);
                let b_uids: Vec<String> = body.iter().map(|s| self.serialize_stmt(s)).collect();
                let o_uids: Vec<String> = orelse.iter().map(|s| self.serialize_stmt(s)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbIf".to_string()));
                node_data.insert("test".to_string(), Value::String(t_uid));
                node_data.insert("body".to_string(), Value::Array(b_uids.into_iter().map(Value::String).collect()));
                node_data.insert("orelse".to_string(), Value::Array(o_uids.into_iter().map(Value::String).collect()));
                node_data.insert("llmexcept_handler".to_string(), Value::Null);
                self.collect(node_data)
            }
            Stmt::For { pos, target, iter, body, orelse } => {
                let t_uid = self.serialize_expr(target);
                let i_uid = self.serialize_expr(iter);
                // 统一遍历：for 目标 type_env = any（IBCI：iter 类型不推断）+ node_to_type
                // 更新（target IbName = any，bind_type_env 后）。
                if let Expr::Name { id, .. } = target {
                    self.bind_type_env(id, "any");
                    self.node_to_type.insert(t_uid.clone(), "type_root.any".to_string());
                }
                let b_uids: Vec<String> = body.iter().map(|s| self.serialize_stmt(s)).collect();
                let o_uids: Vec<String> = orelse.iter().map(|s| self.serialize_stmt(s)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbFor".to_string()));
                node_data.insert("target".to_string(), Value::String(t_uid));
                node_data.insert("iter".to_string(), Value::String(i_uid));
                node_data.insert("body".to_string(), Value::Array(b_uids.into_iter().map(Value::String).collect()));
                node_data.insert("orelse".to_string(), Value::Array(o_uids.into_iter().map(Value::String).collect()));
                node_data.insert("llmexcept_handler".to_string(), Value::Null);
                self.collect(node_data)
            }
            Stmt::While { pos, test, body, orelse } => {
                let t_uid = self.serialize_expr(test);
                let b_uids: Vec<String> = body.iter().map(|s| self.serialize_stmt(s)).collect();
                let o_uids: Vec<String> = orelse.iter().map(|s| self.serialize_stmt(s)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbWhile".to_string()));
                node_data.insert("test".to_string(), Value::String(t_uid));
                node_data.insert("body".to_string(), Value::Array(b_uids.into_iter().map(Value::String).collect()));
                node_data.insert("orelse".to_string(), Value::Array(o_uids.into_iter().map(Value::String).collect()));
                node_data.insert("llmexcept_handler".to_string(), Value::Null);
                self.collect(node_data)
            }
            Stmt::FunctionDef { pos, name, args, body, returns } => {
                // 统一遍历：函数名 type_env[含顶层函数，IbName 函数名 → 函数类型
                // type_root.<name>] + func_sigs（returns）+ push_scope + 参数 type_env。
                self.bind_type_env(name, name);
                if let Some(rt) = returns {
                    if let Some(ts) = parse_type_annotation(rt) {
                        self.func_sigs.insert(name.clone(), ts);
                    }
                }
                self.push_scope(name);
                for a in args {
                    if let Some(ann) = &a.annotation {
                        if let Some(ts) = parse_type_annotation(ann) {
                            self.bind_type_env(&a.arg, &ts);
                        } else {
                            self.bind_type_env(&a.arg, "any");
                        }
                    } else {
                        self.bind_type_env(&a.arg, "any");
                    }
                }
                let b_uids: Vec<String> = body.iter().map(|s| self.serialize_stmt(s)).collect();
                self.pop_scope();
                let arg_uids: Vec<String> = args.iter().map(|a| self.serialize_arg(a)).collect();
                let ret_uid = returns.as_ref().map(|e| self.serialize_expr(e));
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbFunctionDef".to_string()));
                node_data.insert("name".to_string(), Value::String(name.clone()));
                node_data.insert("args".to_string(), Value::Array(arg_uids.into_iter().map(Value::String).collect()));
                node_data.insert("body".to_string(), Value::Array(b_uids.into_iter().map(Value::String).collect()));
                node_data.insert("returns".to_string(), ret_uid.map(Value::String).unwrap_or(Value::Null));
                node_data.insert("type_params".to_string(), Value::Array(Vec::new()));
                node_data.insert("type_param_uids".to_string(), Value::Array(Vec::new()));
                node_data.insert("type_param_bounds".to_string(), Value::Object(Map::new()));
                node_data.insert("free_vars".to_string(), Value::Array(Vec::new()));
                node_data.insert("is_generator".to_string(), Value::Bool(false));
                self.collect(node_data)
            }
            Stmt::Return { pos, value } => {
                let v_uid = value.as_ref().map(|e| self.serialize_expr(e));
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbReturn".to_string()));
                node_data.insert("value".to_string(), v_uid.map(Value::String).unwrap_or(Value::Null));
                self.collect(node_data)
            }
            Stmt::Break { pos } | Stmt::Continue { pos } => {
                let ty = if matches!(stmt, Stmt::Break { .. }) { "IbBreak" } else { "IbContinue" };
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String(ty.to_string()));
                self.collect(node_data)
            }
            Stmt::Pass { pos } => {
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbPass".to_string()));
                self.collect(node_data)
            }
            Stmt::Try { pos, body, orelse, finalbody, .. } => {
                // IbTry（语料面不含；占位：基类位置 + body/orelse/finalbody，handlers 归后续）
                let b_uids: Vec<String> = body.iter().map(|s| self.serialize_stmt(s)).collect();
                let o_uids: Vec<String> = orelse.iter().map(|s| self.serialize_stmt(s)).collect();
                let f_uids: Vec<String> = finalbody.iter().map(|s| self.serialize_stmt(s)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbTry".to_string()));
                node_data.insert("body".to_string(), Value::Array(b_uids.into_iter().map(Value::String).collect()));
                node_data.insert("handlers".to_string(), Value::Array(Vec::new()));
                node_data.insert("orelse".to_string(), Value::Array(o_uids.into_iter().map(Value::String).collect()));
                node_data.insert("finalbody".to_string(), Value::Array(f_uids.into_iter().map(Value::String).collect()));
                self.collect(node_data)
            }
            Stmt::ClassDef { pos, name, body, .. } => {
                // 统一遍历：类名 → type_env 绑定（IbName 类名 → type_root.<name>，
                // 用户类固有名字语义同 intrinsic 类型名）。
                self.bind_type_env(name, name);
                // IbClassDef（语料面不含；占位：基类位置 + name + body）
                let b_uids: Vec<String> = body.iter().map(|s| self.serialize_stmt(s)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbClassDef".to_string()));
                node_data.insert("name".to_string(), Value::String(name.clone()));
                node_data.insert("body".to_string(), Value::Array(b_uids.into_iter().map(Value::String).collect()));
                self.collect(node_data)
            }
        }
    }

    /// 表达式节点分发（统一遍历：委托 serialize_expr_impl[record=true] + infer_type_env
    /// 记录 node_to_type[node_uid → type_uid，type_inference 完整节点规则]）。
    pub fn serialize_expr(&mut self, expr: &Expr) -> String {
        let uid = self.serialize_expr_impl(expr, true);
        // type_uid = type_root.<类型名>（与符号 type_uid 格式一致；infer_type_env 返回
        // 裸类型名，module_path=None → root 前缀）。
        if let Some(type_uid) = infer_type_env(expr, &self.ctx()) {
            self.node_to_type.insert(uid.clone(), format!("type_root.{}", type_uid));
        }
        uid
    }

    /// 无记录变体（参数注解位置——Python type checker 不产参数注解 Name 节点的
    /// node_to_type 绑定，语料实证 6/6 未绑定；节点仍入节点池）。
    pub fn serialize_expr_no_record(&mut self, expr: &Expr) -> String {
        self.serialize_expr_impl(expr, false)
    }

    /// 子表达式序列化（record = 是否记录 node_to_type——单一递归路径，无平行实现）。
    fn ser(&mut self, e: &Expr, record: bool) -> String {
        if record {
            self.serialize_expr(e)
        } else {
            self.serialize_expr_no_record(e)
        }
    }

    /// 表达式节点序列化（内部递归经 ser[e, record] 保持记录态一致）。
    fn serialize_expr_impl(&mut self, expr: &Expr, record: bool) -> String {
        match expr {
            Expr::Constant { pos, value } => {
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbConstant".to_string()));
                node_data.insert("value".to_string(), const_value(value));
                self.collect(node_data)
            }
            Expr::Name { pos, id, ctx } => {
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbName".to_string()));
                node_data.insert("id".to_string(), Value::String(id.clone()));
                node_data.insert("ctx".to_string(), Value::String(ctx.clone()));
                self.collect(node_data)
            }
            Expr::BinOp { pos, left, op, right } => {
                let l_uid = self.ser(left, record);
                let r_uid = self.ser(right, record);
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbBinOp".to_string()));
                node_data.insert("left".to_string(), Value::String(l_uid));
                node_data.insert("op".to_string(), Value::String(op.clone()));
                node_data.insert("right".to_string(), Value::String(r_uid));
                self.collect(node_data)
            }
            Expr::UnaryOp { pos, op, operand } => {
                let o_uid = self.ser(operand, record);
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbUnaryOp".to_string()));
                node_data.insert("op".to_string(), Value::String(op.clone()));
                node_data.insert("operand".to_string(), Value::String(o_uid));
                self.collect(node_data)
            }
            Expr::BoolOp { pos, op, values } => {
                let v_uids: Vec<String> = values.iter().map(|e| self.ser(e, record)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbBoolOp".to_string()));
                node_data.insert("op".to_string(), Value::String(op.clone()));
                node_data.insert("values".to_string(), Value::Array(v_uids.into_iter().map(Value::String).collect()));
                self.collect(node_data)
            }
            Expr::Compare { pos, left, ops, comparators } => {
                let l_uid = self.ser(left, record);
                let c_uids: Vec<String> = comparators.iter().map(|e| self.ser(e, record)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbCompare".to_string()));
                node_data.insert("left".to_string(), Value::String(l_uid));
                node_data.insert("ops".to_string(), Value::Array(ops.iter().map(|o| Value::String(o.clone())).collect()));
                node_data.insert("comparators".to_string(), Value::Array(c_uids.into_iter().map(Value::String).collect()));
                self.collect(node_data)
            }
            Expr::Call { pos, func, args } => {
                let f_uid = self.ser(func, record);
                let a_uids: Vec<String> = args.iter().map(|e| self.ser(e, record)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbCall".to_string()));
                node_data.insert("func".to_string(), Value::String(f_uid));
                node_data.insert("args".to_string(), Value::Array(a_uids.into_iter().map(Value::String).collect()));
                // Python IbCall.keywords = []（语料面不含关键字参数，对齐空列表）
                node_data.insert("keywords".to_string(), Value::Array(Vec::new()));
                self.collect(node_data)
            }
            Expr::List { pos, elts, ctx } | Expr::Tuple { pos, elts, ctx } => {
                let ty = if matches!(expr, Expr::List { .. }) { "IbListExpr" } else { "IbTuple" };
                let e_uids: Vec<String> = elts.iter().map(|e| self.ser(e, record)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String(ty.to_string()));
                node_data.insert("elts".to_string(), Value::Array(e_uids.into_iter().map(Value::String).collect()));
                node_data.insert("ctx".to_string(), Value::String(ctx.clone()));
                self.collect(node_data)
            }
            Expr::Dict { pos, keys, values } => {
                let k_uids: Vec<String> = keys.iter().map(|e| self.ser(e, record)).collect();
                let v_uids: Vec<String> = values.iter().map(|e| self.ser(e, record)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbDict".to_string()));
                node_data.insert("keys".to_string(), Value::Array(k_uids.into_iter().map(Value::String).collect()));
                node_data.insert("values".to_string(), Value::Array(v_uids.into_iter().map(Value::String).collect()));
                self.collect(node_data)
            }
            Expr::Attribute { pos, value, attr, ctx } => {
                let v_uid = self.ser(value, record);
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbAttribute".to_string()));
                node_data.insert("value".to_string(), Value::String(v_uid));
                node_data.insert("attr".to_string(), Value::String(attr.clone()));
                node_data.insert("ctx".to_string(), Value::String(ctx.clone()));
                self.collect(node_data)
            }
            Expr::Subscript { pos, value, slice, ctx } => {
                let v_uid = self.ser(value, record);
                let s_uid = self.ser(slice, record);
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbSubscript".to_string()));
                node_data.insert("value".to_string(), Value::String(v_uid));
                node_data.insert("slice".to_string(), Value::String(s_uid));
                node_data.insert("ctx".to_string(), Value::String(ctx.clone()));
                self.collect(node_data)
            }
            Expr::IfExp { pos, test, body, orelse } => {
                let t_uid = self.ser(test, record);
                let b_uid = self.ser(body, record);
                let o_uid = self.ser(orelse, record);
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbIfExp".to_string()));
                node_data.insert("test".to_string(), Value::String(t_uid));
                node_data.insert("body".to_string(), Value::String(b_uid));
                node_data.insert("orelse".to_string(), Value::String(o_uid));
                self.collect(node_data)
            }
            Expr::Slice { pos, lower, upper, step } => {
                // Slice 子表达式保持记录态（Slice 自身节点 infer_type_env = None 不产
                // 绑定——Python 实证；其内层值表达式如 xs[1:3] 的 1/3 正常绑定）。
                let lo = lower.as_ref().map(|e| self.ser(e, record));
                let up = upper.as_ref().map(|e| self.ser(e, record));
                let st = step.as_ref().map(|e| self.ser(e, record));
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbSlice".to_string()));
                node_data.insert("lower".to_string(), lo.map(Value::String).unwrap_or(Value::Null));
                node_data.insert("upper".to_string(), up.map(Value::String).unwrap_or(Value::Null));
                node_data.insert("step".to_string(), st.map(Value::String).unwrap_or(Value::Null));
                self.collect(node_data)
            }
            Expr::Lambda { pos, .. } => {
                // IbLambda（语料面低频；基类位置 + 占位）
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbLambda".to_string()));
                self.collect(node_data)
            }
        }
    }

    /// Alias 节点（import 名）：{"_type": "IbAlias", 基类位置, name, asname}。
    fn serialize_alias(&mut self, alias: &crate::parser::Alias) -> String {
        let mut node_data = base_fields(&alias.pos);
        node_data.insert("_type".to_string(), Value::String("IbAlias".to_string()));
        node_data.insert("name".to_string(), Value::String(alias.name.clone()));
        node_data.insert("asname".to_string(), alias.asname.clone().map(Value::String).unwrap_or(Value::Null));
        self.collect(node_data)
    }

    /// Arg 节点（IbArg）：{"_type": "IbArg", 基类位置, arg, annotation, default, kind}。
    /// Arg 节点（pub：供符号解析计算参数定义节点 UID）。
    pub fn serialize_arg(&mut self, arg: &crate::parser::Arg) -> String {
        // 参数注解 = 类型位置（无 node_to_type 绑定——Python 实证）；默认值 = 值位置
        // （正常绑定）。
        let ann = arg.annotation.as_ref().map(|e| self.serialize_expr_no_record(e));
        let def = arg.default.as_ref().map(|e| self.serialize_expr(e));
        let mut node_data = base_fields(&arg.pos);
        node_data.insert("_type".to_string(), Value::String("IbArg".to_string()));
        node_data.insert("arg".to_string(), Value::String(arg.arg.clone()));
        node_data.insert("annotation".to_string(), ann.map(Value::String).unwrap_or(Value::Null));
        node_data.insert("default".to_string(), def.map(Value::String).unwrap_or(Value::Null));
        node_data.insert("kind".to_string(), Value::String(arg.kind.clone()));
        self.collect(node_data)
    }

    /// 收集节点：content_str[自定义 JSON 序列化，匹配 Python json.dumps sort_keys] →
    /// node_uid → 节点池。
    fn collect(&mut self, node_data: HashMap<String, Value>) -> String {
        let map: Map<String, Value> = node_data.into_iter().collect();
        let content = json_serialize_map(&map);
        let uid = serialization::node_uid(&content);
        self.node_pool.insert(uid.clone(), Value::Object(map));
        uid
    }
}

/// 基类位置字段（lineno/col_offset/end_lineno/end_col_offset）。
fn base_fields(pos: &Pos) -> HashMap<String, Value> {
    let mut m = HashMap::new();
    m.insert("lineno".to_string(), Value::from(pos.lineno));
    m.insert("col_offset".to_string(), Value::from(pos.col_offset));
    m.insert("end_lineno".to_string(), pos.end_lineno.map(Value::from).unwrap_or(Value::Null));
    m.insert("end_col_offset".to_string(), pos.end_col_offset.map(Value::from).unwrap_or(Value::Null));
    m
}

/// node_to_loc 侧表（全量 Rust 化·artifact 产出：位置侧表）：node_uid →
/// {file_path: null, line: lineno, column: col_offset}。file_path=null（Rust 无临时
/// 文件，source 直接输入；Python 的 file_path 是编译临时 .ibci 文件的副产物，非
/// artifact 语义——Rust 架构自然，非对齐偏离）。line/column 与 Python node_to_loc
/// 对齐（节点位置，1-based）。
pub fn node_to_loc(source: &str) -> std::collections::BTreeMap<String, Value> {
    let module = crate::parser::parse_to_module(source);
    let mut serializer = NodeSerializer::new();
    let (_root, node_pool) = serializer.serialize_module(&module);
    let mut loc: std::collections::BTreeMap<String, Value> =
        std::collections::BTreeMap::new();
    for (uid, nd) in node_pool {
        let line = nd.get("lineno").cloned().unwrap_or(Value::Null);
        let column = nd.get("col_offset").cloned().unwrap_or(Value::Null);
        loc.insert(
            uid,
            Value::Object(serde_json::Map::from_iter([
                ("file_path".to_string(), Value::Null),
                ("line".to_string(), line),
                ("column".to_string(), column),
            ])),
        );
    }
    loc
}

/// 常量值（ConstVal → Value）。
fn const_value(v: &ConstVal) -> Value {
    match v {
        ConstVal::Int(i) => Value::from(*i),
        ConstVal::Float(f) => serde_json::Number::from_f64(*f).map(Value::Number).unwrap_or(Value::Null),
        ConstVal::Str(s) => Value::String(s.clone()),
        ConstVal::Bool(b) => Value::Bool(*b),
        ConstVal::None_ => Value::Null,
    }
}

/// 自定义 JSON 序列化（匹配 Python json.dumps[sort_keys=True] 格式）：键字母序 +
/// `": "` 分隔 + `", "` 对间分隔 + 值格式[string 带引号 JSON 转义 / int / float /
/// null / list[", " 分隔]]。
fn json_serialize_map(m: &Map<String, Value>) -> String {
    let mut items: Vec<(&String, &Value)> = m.iter().collect();
    items.sort_by(|a, b| a.0.cmp(b.0));
    let inner: Vec<String> = items
        .iter()
        .map(|(k, v)| format!("{}: {}", json_escape_string(k), json_serialize(v)))
        .collect();
    format!("{{{}}}", inner.join(", "))
}

fn json_serialize(v: &Value) -> String {
    match v {
        Value::Object(map) => json_serialize_map(map),
        Value::Array(arr) => {
            let inner: Vec<String> = arr.iter().map(json_serialize).collect();
            format!("[{}]", inner.join(", "))
        }
        Value::String(s) => json_escape_string(s),
        Value::Number(n) => {
            // 整数原样；浮点 = Python repr（整值浮点 = 4.0）
            if let Some(i) = n.as_i64() {
                i.to_string()
            } else if let Some(u) = n.as_u64() {
                u.to_string()
            } else if let Some(f) = n.as_f64() {
                py_float_repr(f)
            } else {
                n.to_string()
            }
        }
        Value::Null => "null".to_string(),
        Value::Bool(true) => "true".to_string(),
        Value::Bool(false) => "false".to_string(),
    }
}

/// 浮点 repr（匹配 Python：整值浮点 = "4.0"，非整值 = 标准十进制）。
fn py_float_repr(f: f64) -> String {
    if f.fract() == 0.0 && f.abs() < 1e16 {
        format!("{}.0", f as i64)
    } else {
        // Python repr（最短表示）≈ Rust {}（但 Rust 用最短表示，匹配 Python 常见情形）
        format!("{}", f)
    }
}

/// JSON 字符串转义（带引号，匹配 Python json.dumps[ensure_ascii=True]）：处理 " 和 \
/// 和控制字符 + 非 ASCII → \uXXXX（Python ensure_ascii 默认转义非 ASCII）。
fn json_escape_string(s: &str) -> String {
    let escaped: String = s
        .chars()
        .map(|c| match c {
            '"' => "\\\"".to_string(),
            '\\' => "\\\\".to_string(),
            '\n' => "\\n".to_string(),
            '\t' => "\\t".to_string(),
            '\r' => "\\r".to_string(),
            '\u{8}' => "\\b".to_string(),
            '\u{c}' => "\\f".to_string(),
            other if (other as u32) < 0x20 => format!("\\u{:04x}", other as u32),
            other if (other as u32) > 0x7e => format!("\\u{:04x}", other as u32),
            other => other.to_string(),
        })
        .collect();
    format!("\"{}\"", escaped)
}
