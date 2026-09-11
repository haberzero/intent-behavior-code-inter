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

use crate::parser::{Case, ConstVal, Expr, Module, Pos, Stmt};
use crate::serialization;
use crate::type_inference::{
    bound_method_rewrite, infer_type_env, parse_type_annotation, symbol_level_type,
    FuncSignatures, InferCtx,
    ModuleNames, TypeEnv,
};

/// 侧表记录模式（位置语义显式分派，非能力探测）：
/// - `Full` = 值/表达式位置：node_to_type + node_to_symbol 均记录；
/// - `TypeOnly` = 返回注解位置：仅 node_to_type（Python 实证：返回注解 Name 绑定
///   类型 7/7、符号 0/7）；
/// - `None` = 参数注解位置：均不记录（Python 实证 6/6）。
#[derive(Clone, Copy, PartialEq)]
enum RecordMode {
    Full,
    TypeOnly,
    None,
}

/// 节点序列化器：Rust AST → 节点池（uid → node_data）。
pub struct NodeSerializer {
    node_pool: HashMap<String, Value>,
    // 统一遍历：scope 栈 + type_env + user_defined + func_sigs + modules（复用
    // SymbolResolver 逻辑）+ node_to_type[node_uid → type_uid，type_inference 完整节点
    // 规则推导] + node_to_symbol[node_uid → symbol uid，scope 链/intrinsic 解析]。
    scope_stack: Vec<String>,
    type_env: TypeEnv,
    /// 用户定义名字标记层（与 scope_stack/type_env 同步 push/pop）：每 scope 一个
    /// Name 集——区分"用户顶层定义"与"顶层 intrinsic 固有绑定"（node_to_symbol 的
    /// scope uid vs intrinsic uid 解析依据）。
    user_defined: Vec<BTreeMap<String, String>>,
    /// intrinsic 63 名字固定集（node_to_symbol：固有名字 → intrinsic:<name>）。
    intrinsic_names: BTreeSet<String>,
    func_sigs: FuncSignatures,
    modules: ModuleNames,
    node_to_type: BTreeMap<String, String>,
    node_to_symbol: BTreeMap<String, String>,
    /// 定义节点（符号 uid → 定义节点 uid，首次定义优先）——统一遍历中在 scope 上下文
    /// 内记录（供 scope 符号 node_uid 绑定；非事后重序列化——嵌套函数 free_vars 等
    /// scope 相关节点内容只在定义处上下文可正确产出）。
    def_node_uids: BTreeMap<String, String>,
    /// 顶层用户函数名（__string_exec__ 模块类型成员 kind = method 的判定依据——
    /// Python 实证：用户顶层函数 = method 成员，变量/模块/类 = field 成员）。
    top_functions: BTreeSet<String>,
    /// 用户函数类型条目（name → ([参数类型名], 返回类型名)）——types 池
    /// USER_DEFINED function 条目（全深度函数定义 + from-import 函数绑定；
    /// Python 实证：USER_DEFINED + IMPORT_GATED + 注解签名）。
    user_functions: BTreeMap<String, (Vec<String>, String)>,
    /// 模块属性调用的函数名（`meta.X(...)` 的 X）——types 池 IMPORT_GATED 函数
    /// 类型条件包含规则（Python 实证：quote/eval 仅在模块属性调用时进池；
    /// from-import 裸名调用只产 USER_DEFINED 条目）。
    called_module_functions: BTreeSet<String>,
    /// bound_method 共享类型最后改写（last-wins）——types 池 bound_method 条目
    /// (param_type_names, return_type_name)：每个方法属性访问（bound_method 判定
    /// 命中）改写共享 bound_method TypeDef 的特化签名（params + ret；Python 实证：
    /// last-wins + 属性访问即改写；受控实验 strip/keys 顺序敏感）。
    bound_method_sig: Option<(Vec<String>, String)>,
    /// 方法调用返回类型全集（泛型闭包种子——types 池泛型条目：d.keys() →
    /// list[str] 等特化返回类型也进池）。
    method_returns: BTreeSet<String>,
}

impl NodeSerializer {
    pub fn new() -> Self {
        // 顶层 scope type_env 绑定全 63 intrinsic 符号名（42 类型 + 19 函数 + 2 模块，
        // 与 scope 池"顶层 scope = intrinsic 63 + 用户顶层"语义同构）：IbName 固有名字
        // → type_root.<name>（函数类型/类类型/模块类型，语料实证对齐 Python）。
        let intrinsic_names: BTreeSet<String> =
            crate::intrinsic_symbols::intrinsic_names().into_iter().collect();
        let top_env: BTreeMap<String, String> = intrinsic_names
            .iter()
            .map(|n| (n.clone(), n.clone()))
            .collect();
        Self {
            node_pool: HashMap::new(),
            scope_stack: vec!["__string_exec__".to_string()],
            type_env: vec![top_env],
            user_defined: vec![BTreeMap::new()],
            intrinsic_names,
            func_sigs: BTreeMap::new(),
            modules: BTreeSet::new(),
            node_to_type: BTreeMap::new(),
            node_to_symbol: BTreeMap::new(),
            def_node_uids: BTreeMap::new(),
            top_functions: BTreeSet::new(),
            user_functions: BTreeMap::new(),
            called_module_functions: BTreeSet::new(),
            bound_method_sig: None,
            method_returns: BTreeSet::new(),
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

    /// push 函数 scope（scope_stack + type_env + user_defined 同步，单一权威源避免漂移）。
    fn push_scope(&mut self, name: &str) {
        self.scope_stack.push(name.to_string());
        self.type_env.push(BTreeMap::new());
        self.user_defined.push(BTreeMap::new());
    }

    /// pop 函数 scope（scope_stack + type_env + user_defined 同步）。
    fn pop_scope(&mut self) {
        self.scope_stack.pop();
        self.type_env.pop();
        self.user_defined.pop();
    }

    /// 当前 scope 的符号 uid（`scope_<scope 串>:<name>`）。
    fn current_scope_symbol_uid(&self, name: &str) -> String {
        format!("scope_{}:{}", self.scope_stack.join("/"), name)
    }

    /// 用户定义名字绑定（当前 scope）：type_env[Name → 类型串，供 infer_type_env 推导]
    /// + user_defined 标记[Name → Name，node_to_symbol 定义 scope 解析依据]——单一
    /// 写入点同步三表，无漂移。
    fn define_name(&mut self, name: &str, type_str: &str) {
        if let Some(scope) = self.type_env.last_mut() {
            scope.insert(name.to_string(), type_str.to_string());
        }
        if let Some(scope) = self.user_defined.last_mut() {
            scope.insert(name.to_string(), name.to_string());
        }
    }

    /// 名字 → 符号 uid 解析（node_to_symbol）：用户定义（scope 链内层→外层，含顶层
    /// 用户定义）优先 → `scope_<定义 scope 串>:<name>`；否则 intrinsic 63 固定集 →
    /// `intrinsic:<name>`（Python：intrinsic 符号 uid 独立，驻顶层 scope 符号表）；
    /// 均未命中 → None（不产条目）。
    fn resolve_symbol_uid(&self, name: &str) -> Option<String> {
        for (i, scope) in self.user_defined.iter().enumerate().rev() {
            if scope.contains_key(name) {
                let scope_str = self.scope_stack[..=i].join("/");
                return Some(format!("scope_{}:{}", scope_str, name));
            }
        }
        if self.intrinsic_names.contains(name) {
            return Some(format!("intrinsic:{}", name));
        }
        None
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

    /// node_to_symbol 侧表（node_uid → symbol uid）——统一遍历产出（scope 链/intrinsic
    /// 解析）。
    pub fn node_to_symbol_map(&mut self) -> BTreeMap<String, String> {
        std::mem::take(&mut self.node_to_symbol)
    }

    /// 定义节点表（符号 uid → 定义节点 uid）——统一遍历产出（scope 上下文内记录）。
    pub fn def_node_uids_map(&mut self) -> BTreeMap<String, String> {
        std::mem::take(&mut self.def_node_uids)
    }

    /// types 池泛型容器类型名（泛型闭包）：种子 = 类型环境值[变量绑定] + 方法调用
    /// 特化返回类型；每个泛型串展开其 payload 实参（dict[str,list[int]] →
    /// list[int] → int），全部泛型串进池（Python 实证：注册表泛型闭包语义）。
    pub fn generic_type_names(&self) -> BTreeSet<String> {
        let mut seeds = self.method_returns.clone();
        for scope in self.type_env.iter() {
            for t in scope.values() {
                seeds.insert(t.clone());
            }
        }
        let mut out = BTreeSet::new();
        let mut stack: Vec<String> = seeds
            .into_iter()
            .filter(|t| t.contains('['))
            .collect();
        while let Some(s) = stack.pop() {
            if out.insert(s.clone()) {
                let (_, params) = crate::type_inference::parse_container(&s);
                for p in params {
                    if p.contains('[') {
                        stack.push(p);
                    }
                }
            }
        }
        out
    }

    /// __string_exec__ 入口模块类型完整条目（基础字段 + 用户顶层符号成员：函数 →
    /// method，变量/模块/类 → field——Python 实证；canonical 成员哈希 owner =
    /// type_root.__string_exec__）。完整 artifact 组装面。
    pub fn entry_module_type_entry(&self) -> Value {
        let mut m = crate::intrinsic_symbols::type_entry(
            "__string_exec__",
            "module",
            "PRELUDE_VISIBLE",
        )
        .as_object()
        .unwrap()
        .clone();
        let top = self.user_defined.first().unwrap();
        let mut members = serde_json::Map::new();
        for name in top.keys() {
            let kind = if self.top_functions.contains(name) { "method" } else { "field" };
            members.insert(
                name.clone(),
                Value::String(crate::intrinsic_symbols::anon_member_uid(
                    name,
                    kind,
                    "type_root.__string_exec__",
                )),
            );
        }
        // 空成员键省略（Python `if t.members:` 语义——空 members_uids 不进条目）
        if !members.is_empty() {
            m.insert("members_uids".into(), Value::Object(members));
        }
        Value::Object(m)
    }

    /// __string_exec__ 用户模块成员 kind 表（name → method/field）——symbols 池成员
    /// 符号条目构建（完整 artifact 组装面）。
    pub fn entry_module_member_kinds(&self) -> Vec<(String, String)> {
        let top = self.user_defined.first().unwrap();
        top
            .keys()
            .map(|name| {
                let kind = if self.top_functions.contains(name) { "method" } else { "field" };
                (name.clone(), kind.to_string())
            })
            .collect()
    }

    /// 模块属性调用的函数名（types 池 IMPORT_GATED 函数类型条件包含）。
    pub fn called_module_functions(&self) -> &BTreeSet<String> {
        &self.called_module_functions
    }

    /// 导入模块名集合（types 池模块类型条件包含：import meta → meta 模块类型）。
    pub fn imported_modules(&self) -> &BTreeSet<String> {
        &self.modules
    }

    /// bound_method 共享类型最后改写特化签名（types 池 bound_method 条目
    /// (param_type_names, return_type_name)；无方法属性访问 = None[默认 ([] , void)]）。
    pub fn bound_method_sig(&self) -> Option<(Vec<String>, String)> {
        self.bound_method_sig.clone()
    }

    /// 用户函数类型条目（types 池 USER_DEFINED function 条目：全深度函数定义 +
    /// from-import 函数绑定；IMPORT_GATED + 注解签名——Python 实证）。
    pub fn user_function_entries(&self) -> BTreeMap<String, Value> {
        let mut out = BTreeMap::new();
        for (name, (params, ret)) in &self.user_functions {
            let mut m = serde_json::Map::new();
            m.insert("uid".into(), Value::String(format!("type_root.{}", name)));
            m.insert("kind".into(), Value::String("function".into()));
            m.insert("name".into(), Value::String(name.clone()));
            m.insert("module_path".into(), Value::Null);
            m.insert("provenance".into(), Value::String("USER_DEFINED".into()));
            m.insert("visibility".into(), Value::String("IMPORT_GATED".into()));
            m.insert("storage_model".into(), Value::String("MEMORY_BACKED".into()));
            m.insert("exported_types".into(), Value::Array(Vec::new()));
            m.insert(
                "param_type_names".into(),
                Value::Array(params.iter().map(|p| Value::String(p.clone())).collect()),
            );
            m.insert("return_type_name".into(), Value::String(ret.clone()));
            out.insert(name.clone(), Value::Object(m));
        }
        out
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
                // 目标序列化（声明面 target = TypeAnnotatedExpr 时内联序列化
                // 注解/target 子节点——uid 需暴露给绑定面）
                let mut t_uids: Vec<String> = Vec::new();
                let mut decl_parts: Option<(String, String, String)> = None;
                for t in targets {
                    match t {
                        Expr::TypeAnnotatedExpr {
                            target,
                            annotation,
                            pos: tpos,
                        } => {
                            // 注解 = ser_annotation（仅顶层节点 node_to_type——
                            // 泛型内层名字不单独绑定，Python 实证）；target name
                            // = Full（Store 节点经 Assign 臂显式绑 symbol）
                            let a_uid = self.ser_annotation(annotation);
                            let n_uid = self.ser(target, RecordMode::Full);
                            let mut nd = base_fields(tpos);
                            nd.insert(
                                "_type".to_string(),
                                Value::String("IbTypeAnnotatedExpr".to_string()),
                            );
                            nd.insert("target".to_string(), Value::String(n_uid.clone()));
                            nd.insert("annotation".to_string(), Value::String(a_uid.clone()));
                            let annotated_uid = self.collect(nd);
                            decl_parts = Some((annotated_uid.clone(), n_uid, a_uid));
                            t_uids.push(annotated_uid);
                        }
                        other => t_uids.push(self.serialize_expr(other)),
                    }
                }
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
                                self.define_name(id, &ts);
                            }
                            if let Some(ts) = existing.or(node_t.clone()) {
                                self.node_to_type.insert(t_uid.clone(), format!("type_root.{}", ts));
                            }
                            // node_to_symbol：target Name 节点 → 定义符号（当前 scope）——
                            // 首次赋值时 target 序列化在先、定义在后，Python 实证 target
                            // Name 节点同样绑定（arithmetic_loop total 4 Name + 2 IbAssign）。
                            self.node_to_symbol
                                .insert(t_uid.clone(), self.current_scope_symbol_uid(id));
                        }
                    }
                }
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbAssign".to_string()));
                node_data.insert("targets".to_string(), Value::Array(t_uids.into_iter().map(Value::String).collect()));
                node_data.insert(
                    "value".to_string(),
                    v_uid.clone().map(Value::String).unwrap_or(Value::Null),
                );
                node_data.insert("llmexcept_handler".to_string(), Value::Null);
                let assign_uid = self.collect(node_data);
                // 声明面绑定（Python 实证：int x = 2 / list[int] ys / auto a）：
                // 注解节点 node_to_type = type_root.<注解串>（含 auto →
                // type_root.auto）；annotated/Assign/值节点 node_to_type = 声明
                // 类型（auto = 值推导符号通道类型）；target name/annotated/
                // Assign/值节点 node_to_symbol → 定义符号；符号 type_uid = 声明
                // 类型（auto = 推导）；定义节点 = Assign 节点（同普通赋值）。
                if let Some((annotated_uid, name_uid, ann_uid)) = decl_parts {
                    if let Some(Expr::TypeAnnotatedExpr { target, annotation, .. }) = targets.first() {
                        if let Expr::Name { id, .. } = &**target {
                            let ctx = self.ctx();
                            let ann_str = annotation_type_str(&**annotation);
                            let declared = if ann_str == "auto" {
                                value.as_ref().and_then(|v| symbol_level_type(v, &ctx))
                            } else {
                                Some(ann_str.clone())
                            };
                            if let Some(ts) = &declared {
                                self.define_name(id, ts);
                            }
                            self.node_to_type.insert(
                                ann_uid.clone(),
                                format!("type_root.{}", ann_str.clone()),
                            );
                            if let Some(d) = declared {
                                let du = format!("type_root.{}", d);
                                self.node_to_type.insert(annotated_uid.clone(), du.clone());
                                // 值节点 = 声明类型（auto = 推导值 ser 已绑，覆盖一致）
                                if let Some(vu) = &v_uid {
                                    self.node_to_type.insert(vu.clone(), du);
                                }
                            }
                            let sym_uid = self.current_scope_symbol_uid(id);
                            self.node_to_symbol.insert(name_uid.clone(), sym_uid.clone());
                            self.node_to_symbol.insert(annotated_uid.clone(), sym_uid.clone());
                            self.node_to_symbol.insert(assign_uid.clone(), sym_uid.clone());
                        }
                    }
                }
                // node_to_symbol：IbAssign 节点 → 目标 VARIABLE scope 符号（定义 scope
                // = 当前 scope——Python 实证 34/34 IbAssign 全绑定）。
                // 定义节点：目标符号 → IbAssign 节点 uid（首次定义优先）。
                if let Some(id) = assign_target_name(targets) {
                    let sym_uid = self.current_scope_symbol_uid(&id);
                    self.node_to_symbol.insert(assign_uid.clone(), sym_uid.clone());
                    self.def_node_uids
                        .entry(sym_uid)
                        .or_insert(assign_uid.clone());
                }
                assign_uid
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
                    self.define_name(&binding, &binding);
                }
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbImport".to_string()));
                node_data.insert("names".to_string(), Value::Array(a_uids.into_iter().map(Value::String).collect()));
                self.collect(node_data)
            }
            Stmt::FromImport { pos, module, names } => {
                let a_uids: Vec<String> = names.iter().map(|a| self.serialize_alias(a)).collect();
                // 统一遍历：from-import 绑定名 → type_env（IbName 绑定名 → 源函数/类型
                // 的 type_root.<name>——语料实证 from meta import quote：quote →
                // type_root.quote）+ from-import 函数绑定 → 用户函数类型条目
                // （签名 = 模块函数声明——types 池 USER_DEFINED function 条目）。
                for alias in names {
                    let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
                    self.define_name(&binding, &binding);
                    if let Some(sig) = crate::intrinsic_symbols::function_sig(&binding) {
                        self.user_functions
                            .insert(binding.clone(), sig.clone());
                        // from-import 函数绑定 = 函数成员（__string_exec__ 成员
                        // kind = method——Python 实证：quote 绑定 → method）
                        self.top_functions.insert(binding.clone());
                    }
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
                // 更新（target IbName = any，define_name 后）+ node_to_symbol（for 目标 →
                // VARIABLE scope 符号，当前 scope——Python 实证 Store Name 全绑定）。
                if let Expr::Name { id, .. } = target {
                    self.define_name(id, "any");
                    self.node_to_type.insert(t_uid.clone(), "type_root.any".to_string());
                    self.node_to_symbol
                        .insert(t_uid.clone(), self.current_scope_symbol_uid(id));
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
                let for_uid = self.collect(node_data);
                // 定义节点：for 目标符号 → IbFor 节点 uid（首次定义优先）。
                if let Expr::Name { id, .. } = target {
                    let sym_uid = self.current_scope_symbol_uid(id);
                    self.def_node_uids
                        .entry(sym_uid)
                        .or_insert(for_uid.clone());
                }
                for_uid
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
                // 顶层函数标记（__string_exec__ 模块成员 kind = method 判定）。
                if self.scope_stack.len() == 1 {
                    self.top_functions.insert(name.clone());
                }
                // 用户函数类型条目（全深度：顶层 + 嵌套——types 池 USER_DEFINED
                // function 条目；from-import 函数绑定另计）。
                let params: Vec<String> = args
                    .iter()
                    .map(|a| match a.annotation.as_ref() {
                        Some(e) => parse_type_annotation(e).unwrap_or_else(|| "any".to_string()),
                        None => "any".to_string(),
                    })
                    .collect();
                let ret = returns
                    .as_ref()
                    .map(|e| parse_type_annotation(e))
                    .flatten()
                    .unwrap_or_else(|| "auto".to_string());
                self.user_functions
                    .insert(name.clone(), (params, ret));
                self.define_name(name, name);
                if let Some(rt) = returns {
                    if let Some(ts) = parse_type_annotation(rt) {
                        self.func_sigs.insert(name.clone(), ts);
                    }
                }
                self.push_scope(name);
                for a in args {
                    if let Some(ann) = &a.annotation {
                        if let Some(ts) = parse_type_annotation(ann) {
                            self.define_name(&a.arg, &ts);
                        } else {
                            self.define_name(&a.arg, "any");
                        }
                    } else {
                        self.define_name(&a.arg, "any");
                    }
                }
                let b_uids: Vec<String> = body.iter().map(|s| self.serialize_stmt(s)).collect();
                // 参数序列化在函数 scope 内（arg 节点 → 参数符号的 scope = 函数体
                // scope——scope___string_exec__/add:a，Python 实证）。
                let arg_uids: Vec<String> = args.iter().map(|a| self.serialize_arg(a)).collect();
                // free_vars（闭包捕获）：函数体引用（不含嵌套函数体——归嵌套函数自身）
                // 减去函数自身 scope 定义（pop 前捕获），命中外层函数 scope（排除顶层=
                // 全局引用非自由变量，Python 实证 closure_top_global 无 free_vars）→
                // [name, 定义符号 uid]（Python 实证 closure_capture：get.free_vars =
                // [['a', 'scope___string_exec__/make:a']]）。
                let own_names: BTreeSet<String> = self
                    .user_defined
                    .last()
                    .map(|m| m.keys().cloned().collect())
                    .unwrap_or_default();
                self.pop_scope();
                let f_idx = self.scope_stack.len();
                let mut refs: BTreeSet<String> = BTreeSet::new();
                collect_refs(body, &mut refs);
                refs.retain(|n| !own_names.contains(n));
                let mut free_vars: Vec<Value> = Vec::new();
                for n in refs {
                    for (i, scope) in self.user_defined[..f_idx].iter().enumerate().rev() {
                        if i == 0 {
                            break; // 顶层 = 全局引用，非闭包捕获
                        }
                        if scope.contains_key(&n) {
                            let scope_str = self.scope_stack[..=i].join("/");
                            free_vars.push(Value::Array(vec![
                                Value::String(n.clone()),
                                Value::String(format!("scope_{}:{}", scope_str, n)),
                            ]));
                            break;
                        }
                    }
                }
                // 返回注解 = 类型位置（有 node_to_type 绑定、无 node_to_symbol 绑定——
                // Python 实证：返回注解 Name 绑定类型 7/7、符号 0/7；参数注解两者皆无）。
                let ret_uid = returns.as_ref().map(|e| self.serialize_expr_type_only(e));
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbFunctionDef".to_string()));
                node_data.insert("name".to_string(), Value::String(name.clone()));
                node_data.insert("args".to_string(), Value::Array(arg_uids.into_iter().map(Value::String).collect()));
                node_data.insert("body".to_string(), Value::Array(b_uids.into_iter().map(Value::String).collect()));
                node_data.insert("returns".to_string(), ret_uid.map(Value::String).unwrap_or(Value::Null));
                node_data.insert("type_params".to_string(), Value::Array(Vec::new()));
                node_data.insert("type_param_uids".to_string(), Value::Array(Vec::new()));
                node_data.insert("type_param_bounds".to_string(), Value::Object(Map::new()));
                node_data.insert("free_vars".to_string(), Value::Array(free_vars));
                node_data.insert("is_generator".to_string(), Value::Bool(false));
                let fd_uid = self.collect(node_data);
                // node_to_symbol：IbFunctionDef 节点 → 函数名 scope 符号（定义 scope =
                // 定义处外层 scope，pop_scope 后当前 scope 即定义处——顶层函数 =
                // scope___string_exec__:add，嵌套函数 = scope___string_exec__/outer:inner，
                // Python 实证 7/7）。
                // 定义节点：函数名符号 → IbFunctionDef 节点 uid（scope 上下文内记录——
                // 嵌套函数节点的 free_vars 只在定义处上下文可正确产出）。
                let sym_uid = self.current_scope_symbol_uid(name);
                self.node_to_symbol.insert(fd_uid.clone(), sym_uid.clone());
                self.def_node_uids.entry(sym_uid).or_insert(fd_uid.clone());
                fd_uid
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
                self.define_name(name, name);
                // IbClassDef（语料面不含；占位：基类位置 + name + body）
                let b_uids: Vec<String> = body.iter().map(|s| self.serialize_stmt(s)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbClassDef".to_string()));
                node_data.insert("name".to_string(), Value::String(name.clone()));
                node_data.insert("body".to_string(), Value::Array(b_uids.into_iter().map(Value::String).collect()));
                let cd_uid = self.collect(node_data);
                // 定义节点：类名符号 → IbClassDef 节点 uid。
                let sym_uid = self.current_scope_symbol_uid(name);
                self.def_node_uids.entry(sym_uid).or_insert(cd_uid.clone());
                cd_uid
            }
            // IbGlobalStmt / IbNonlocalStmt（编译期语义——names 裸名字串）
            Stmt::Global { pos, names } | Stmt::Nonlocal { pos, names } => {
                let ty = if matches!(stmt, Stmt::Global { .. }) {
                    "IbGlobalStmt"
                } else {
                    "IbNonlocalStmt"
                };
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String(ty.to_string()));
                node_data.insert(
                    "names".to_string(),
                    Value::Array(
                        names
                            .iter()
                            .map(|n| Value::String(n.clone()))
                            .collect(),
                    ),
                );
                self.collect(node_data)
            }
            // IbRaise（exc 节点引用；null = 裸 raise）
            Stmt::Raise { pos, exc } => {
                let e_uid = exc.as_ref().map(|e| self.serialize_expr(e));
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbRaise".to_string()));
                node_data.insert(
                    "exc".to_string(),
                    e_uid.map(Value::String).unwrap_or(Value::Null),
                );
                self.collect(node_data)
            }
            // IbSwitch（test + cases 节点 uid + llmexcept_handler=null[LLM 面]；
            // end 位置 = 0——Python 序列化器 switch/case 位置约定，语料实证）
            Stmt::Switch { pos, test, cases } => {
                let t_uid = self.serialize_expr(test);
                let c_uids: Vec<String> =
                    cases.iter().map(|c| self.serialize_case(c)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbSwitch".to_string()));
                node_data.insert("test".to_string(), Value::String(t_uid));
                node_data.insert(
                    "cases".to_string(),
                    Value::Array(c_uids.into_iter().map(Value::String).collect()),
                );
                node_data.insert("llmexcept_handler".to_string(), Value::Null);
                node_data.insert("end_lineno".to_string(), Value::from(0));
                node_data.insert("end_col_offset".to_string(), Value::from(0));
                self.collect(node_data)
            }
        }
    }

    /// IbCase 节点（switch 的 case 块：pattern 节点引用[null = default] + body
    /// 语句 uid；end 位置 = 0——Python 位置约定）。
    fn serialize_case(&mut self, c: &Case) -> String {
        let p_uid = c.pattern.as_ref().map(|p| self.serialize_expr(p));
        let b_uids: Vec<String> = c.body.iter().map(|s| self.serialize_stmt(s)).collect();
        let mut node_data = base_fields(&c.pos);
        node_data.insert("_type".to_string(), Value::String("IbCase".to_string()));
        node_data.insert(
            "pattern".to_string(),
            p_uid.map(Value::String).unwrap_or(Value::Null),
        );
        node_data.insert(
            "body".to_string(),
            Value::Array(b_uids.into_iter().map(Value::String).collect()),
        );
        node_data.insert("end_lineno".to_string(), Value::from(0));
        node_data.insert("end_col_offset".to_string(), Value::from(0));
        self.collect(node_data)
    }

    /// 表达式节点分发（值/表达式位置：node_to_type[node_uid → type_uid，type_inference
    /// 完整节点规则] + node_to_symbol[Name 引用 → 符号 uid] 均记录）。
    pub fn serialize_expr(&mut self, expr: &Expr) -> String {
        self.serialize_expr_recorded(expr, RecordMode::Full)
    }

    /// 仅类型记录变体（返回注解位置——有 node_to_type、无 node_to_symbol，Python 实证）。
    pub fn serialize_expr_type_only(&mut self, expr: &Expr) -> String {
        self.serialize_expr_recorded(expr, RecordMode::TypeOnly)
    }

    /// 声明注解序列化（`int x = 1` 的 annotation）：节点内层 = None 记录
    /// （泛型内层名字不单独绑 node_to_type，Python 实证）；顶层节点
    /// node_to_type = type_root.<注解串>（含 auto / 泛型 list[int]）。
    fn ser_annotation(&mut self, e: &Expr) -> String {
        let uid = self.serialize_expr_impl(e, RecordMode::None);
        self.node_to_type
            .insert(uid.clone(), format!("type_root.{}", annotation_type_str(e)));
        uid
    }

    /// 无记录变体（参数注解位置——Python type checker 不产参数注解 Name 节点的
    /// node_to_type / node_to_symbol 绑定，语料实证 6/6 未绑定；节点仍入节点池）。
    pub fn serialize_expr_no_record(&mut self, expr: &Expr) -> String {
        self.serialize_expr_recorded(expr, RecordMode::None)
    }

    /// 表达式序列化（mode 决定侧表记录——单一递归路径，无平行实现）。
    fn ser(&mut self, e: &Expr, mode: RecordMode) -> String {
        match mode {
            RecordMode::Full => self.serialize_expr(e),
            RecordMode::TypeOnly => self.serialize_expr_type_only(e),
            RecordMode::None => self.serialize_expr_no_record(e),
        }
    }

    /// 表达式节点序列化入口（mode = 位置记录模式，内部递归经 ser[e, mode] 保持一致）。
    fn serialize_expr_recorded(&mut self, expr: &Expr, mode: RecordMode) -> String {
        let uid = self.serialize_expr_impl(expr, mode);
        if mode != RecordMode::None {
            // type_uid = type_root.<类型名>（与符号 type_uid 格式一致；infer_type_env
            // 返回裸类型名，module_path=None → root 前缀）。
            if let Some(type_uid) = infer_type_env(expr, &self.ctx()) {
                self.node_to_type.insert(uid.clone(), format!("type_root.{}", type_uid));
            }
        }
        if mode == RecordMode::Full {
            // node_to_symbol：Name 引用 → 符号 uid（scope 链用户定义优先 / intrinsic
            // 63 固定集；未解析 = 不产条目）。
            if let Expr::Name { id, .. } = expr {
                if let Some(suid) = self.resolve_symbol_uid(id) {
                    self.node_to_symbol.insert(uid.clone(), suid);
                }
            }
        }
        uid
    }

    /// 表达式节点序列化（内部递归经 ser[e, mode] 保持记录态一致）。
    fn serialize_expr_impl(&mut self, expr: &Expr, mode: RecordMode) -> String {
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
                let l_uid = self.ser(left, mode);
                let r_uid = self.ser(right, mode);
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbBinOp".to_string()));
                node_data.insert("left".to_string(), Value::String(l_uid));
                node_data.insert("op".to_string(), Value::String(op.clone()));
                node_data.insert("right".to_string(), Value::String(r_uid));
                self.collect(node_data)
            }
            Expr::UnaryOp { pos, op, operand } => {
                let o_uid = self.ser(operand, mode);
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbUnaryOp".to_string()));
                node_data.insert("op".to_string(), Value::String(op.clone()));
                node_data.insert("operand".to_string(), Value::String(o_uid));
                self.collect(node_data)
            }
            Expr::BoolOp { pos, op, values } => {
                let v_uids: Vec<String> = values.iter().map(|e| self.ser(e, mode)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbBoolOp".to_string()));
                node_data.insert("op".to_string(), Value::String(op.clone()));
                node_data.insert("values".to_string(), Value::Array(v_uids.into_iter().map(Value::String).collect()));
                self.collect(node_data)
            }
            Expr::Compare { pos, left, ops, comparators } => {
                let l_uid = self.ser(left, mode);
                let c_uids: Vec<String> = comparators.iter().map(|e| self.ser(e, mode)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbCompare".to_string()));
                node_data.insert("left".to_string(), Value::String(l_uid));
                node_data.insert("ops".to_string(), Value::Array(ops.iter().map(|o| Value::String(o.clone())).collect()));
                node_data.insert("comparators".to_string(), Value::Array(c_uids.into_iter().map(Value::String).collect()));
                self.collect(node_data)
            }
            Expr::Call { pos, func, args } => {
                // 模块属性调用追踪（meta.X(...) 的 X——types 池 IMPORT_GATED 函数
                // 类型条件包含规则）。
                if let Expr::Attribute { value, attr, .. } = func.as_ref() {
                    if let Expr::Name { id, .. } = value.as_ref() {
                        if self.modules.contains(id) {
                            self.called_module_functions.insert(attr.clone());
                        }
                    }
                }
                let f_uid = self.ser(func, mode);
                let a_uids: Vec<String> = args.iter().map(|e| self.ser(e, mode)).collect();
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
                let e_uids: Vec<String> = elts.iter().map(|e| self.ser(e, mode)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String(ty.to_string()));
                node_data.insert("elts".to_string(), Value::Array(e_uids.into_iter().map(Value::String).collect()));
                node_data.insert("ctx".to_string(), Value::String(ctx.clone()));
                self.collect(node_data)
            }
            Expr::Dict { pos, keys, values } => {
                let k_uids: Vec<String> = keys.iter().map(|e| self.ser(e, mode)).collect();
                let v_uids: Vec<String> = values.iter().map(|e| self.ser(e, mode)).collect();
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbDict".to_string()));
                node_data.insert("keys".to_string(), Value::Array(k_uids.into_iter().map(Value::String).collect()));
                node_data.insert("values".to_string(), Value::Array(v_uids.into_iter().map(Value::String).collect()));
                self.collect(node_data)
            }
            Expr::Attribute { pos, value, attr, ctx } => {
                if mode == RecordMode::Full {
                    // bound_method 共享类型 last-wins 改写（属性访问即触发——types 池
                    // bound_method 条目特化签名；Python 实证顺序敏感）
                    if let Some(sig) = bound_method_rewrite(value, attr, &self.ctx()) {
                        self.bound_method_sig = Some(sig.clone());
                        self.method_returns.insert(sig.1);
                    }
                }
                let v_uid = self.ser(value, mode);
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbAttribute".to_string()));
                node_data.insert("value".to_string(), Value::String(v_uid));
                node_data.insert("attr".to_string(), Value::String(attr.clone()));
                node_data.insert("ctx".to_string(), Value::String(ctx.clone()));
                self.collect(node_data)
            }
            Expr::Subscript { pos, value, slice, ctx } => {
                let v_uid = self.ser(value, mode);
                let s_uid = self.ser(slice, mode);
                let mut node_data = base_fields(pos);
                node_data.insert("_type".to_string(), Value::String("IbSubscript".to_string()));
                node_data.insert("value".to_string(), Value::String(v_uid));
                node_data.insert("slice".to_string(), Value::String(s_uid));
                node_data.insert("ctx".to_string(), Value::String(ctx.clone()));
                self.collect(node_data)
            }
            Expr::IfExp { pos, test, body, orelse } => {
                let t_uid = self.ser(test, mode);
                let b_uid = self.ser(body, mode);
                let o_uid = self.ser(orelse, mode);
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
                let lo = lower.as_ref().map(|e| self.ser(e, mode));
                let up = upper.as_ref().map(|e| self.ser(e, mode));
                let st = step.as_ref().map(|e| self.ser(e, mode));
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
            Expr::TypeAnnotatedExpr {
                pos,
                target,
                annotation,
            } => {
                // IbTypeAnnotatedExpr（声明面 target——位置 = 类型起始 token；
                // Assign 臂内联序列化时已产出，此臂 = 表达式位置完整面）
                let t_uid = self.ser(target, mode);
                let a_uid = self.ser(annotation, mode);
                let mut node_data = base_fields(pos);
                node_data.insert(
                    "_type".to_string(),
                    Value::String("IbTypeAnnotatedExpr".to_string()),
                );
                node_data.insert("target".to_string(), Value::String(t_uid));
                node_data.insert("annotation".to_string(), Value::String(a_uid));
                self.collect(node_data)
            }
        }
    }

    /// Alias 节点（import 名）：{"_type": "IbAlias", 基类位置, name, asname} +
    /// node_to_symbol（IbAlias 节点 → import 绑定符号，当前 scope——Python 实证
    /// 4/4：import meta → scope___string_exec__:meta / from-import quote →
    /// scope___string_exec__:quote）。
    fn serialize_alias(&mut self, alias: &crate::parser::Alias) -> String {
        let mut node_data = base_fields(&alias.pos);
        node_data.insert("_type".to_string(), Value::String("IbAlias".to_string()));
        node_data.insert("name".to_string(), Value::String(alias.name.clone()));
        node_data.insert("asname".to_string(), alias.asname.clone().map(Value::String).unwrap_or(Value::Null));
        let alias_uid = self.collect(node_data);
        let binding = alias.asname.clone().unwrap_or_else(|| alias.name.clone());
        self.node_to_symbol
            .insert(alias_uid.clone(), self.current_scope_symbol_uid(&binding));
        alias_uid
    }

    /// Arg 节点（IbArg）：{"_type": "IbArg", 基类位置, arg, annotation, default, kind}
    /// + node_to_symbol（IbArg 节点 → 参数 VARIABLE scope 符号，当前 scope = 函数体
    /// scope——Python 实证 6/6：scope___string_exec__/add:a）。pub：供符号解析计算
    /// 参数定义节点 UID。
    pub fn serialize_arg(&mut self, arg: &crate::parser::Arg) -> String {
        // 参数注解 = 类型位置（无 node_to_type / node_to_symbol 绑定——Python 实证）；
        // 默认值 = 值位置（正常绑定）。
        let ann = arg.annotation.as_ref().map(|e| self.serialize_expr_no_record(e));
        let def = arg.default.as_ref().map(|e| self.serialize_expr(e));
        let mut node_data = base_fields(&arg.pos);
        node_data.insert("_type".to_string(), Value::String("IbArg".to_string()));
        node_data.insert("arg".to_string(), Value::String(arg.arg.clone()));
        node_data.insert("annotation".to_string(), ann.map(Value::String).unwrap_or(Value::Null));
        node_data.insert("default".to_string(), def.map(Value::String).unwrap_or(Value::Null));
        node_data.insert("kind".to_string(), Value::String(arg.kind.clone()));
        let arg_uid = self.collect(node_data);
        let sym_uid = self.current_scope_symbol_uid(&arg.arg);
        self.node_to_symbol.insert(arg_uid.clone(), sym_uid.clone());
        // 定义节点：参数符号 → IbArg 节点 uid（当前 scope = 函数体 scope）。
        self.def_node_uids.entry(sym_uid).or_insert(arg_uid.clone());
        arg_uid
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

/// Assign 目标变量名（普通 = Name target；声明面 = TypeAnnotatedExpr 内层
/// Name target）。
fn assign_target_name(targets: &[Expr]) -> Option<String> {
    match targets.first() {
        Some(Expr::Name { id, .. }) => Some(id.clone()),
        Some(Expr::TypeAnnotatedExpr { target, .. }) => match target.as_ref() {
            Expr::Name { id, .. } => Some(id.clone()),
            _ => None,
        },
        _ => None,
    }
}

/// 注解类型串（Name = 名字；Subscript = base[args]——多参 IbTuple 逗号连接；
/// 声明面符号/节点绑定面单一权威源）。
pub(crate) fn annotation_type_str(e: &Expr) -> String {
    match e {
        Expr::Name { id, .. } => id.clone(),
        Expr::Subscript { value, slice, .. } => {
            let base = annotation_type_str(value);
            let args = match slice.as_ref() {
                Expr::Tuple { elts, .. } => elts
                    .iter()
                    .map(annotation_type_str)
                    .collect::<Vec<_>>()
                    .join(","),
                other => annotation_type_str(other),
            };
            format!("{base}[{args}]")
        }
        _ => "any".to_string(),
    }
}

/// 收集语句子树引用的名字（free_vars 计算）：不进入嵌套函数体（归嵌套函数自身的
/// free_vars），但收集嵌套函数的参数/返回注解引用（注解在定义处 scope 求值）。
fn collect_refs(stmts: &[Stmt], out: &mut BTreeSet<String>) {
    for s in stmts {
        collect_refs_stmt(s, out);
    }
}

fn collect_refs_stmt(s: &Stmt, out: &mut BTreeSet<String>) {
    match s {
        Stmt::Assign { targets, value, .. } => {
            for t in targets {
                collect_refs_expr(t, out);
            }
            if let Some(v) = value {
                collect_refs_expr(v, out);
            }
        }
        Stmt::AugAssign { target, value, .. } => {
            collect_refs_expr(target, out);
            collect_refs_expr(value, out);
        }
        Stmt::ExprStmt { value, .. } => collect_refs_expr(value, out),
        Stmt::Return { value, .. } => {
            if let Some(v) = value {
                collect_refs_expr(v, out);
            }
        }
        Stmt::If { test, body, orelse, .. }
        | Stmt::While { test, body, orelse, .. } => {
            collect_refs_expr(test, out);
            collect_refs(body, out);
            collect_refs(orelse, out);
        }
        Stmt::For { target, iter, body, orelse, .. } => {
            collect_refs_expr(target, out);
            collect_refs_expr(iter, out);
            collect_refs(body, out);
            collect_refs(orelse, out);
        }
        Stmt::FunctionDef { name, args, body, returns, .. } => {
            // 嵌套函数：名字 = 定义（归外层 own_names）；体 = 嵌套函数自身 free_vars
            // 关切，不收集；参数默认值/返回注解 = 定义处 scope 求值，收集。
            let _ = name;
            for a in args {
                if let Some(d) = &a.default {
                    collect_refs_expr(d, out);
                }
                if let Some(ann) = &a.annotation {
                    collect_refs_expr(ann, out);
                }
            }
            if let Some(r) = returns {
                collect_refs_expr(r, out);
            }
            let _ = body;
        }
        Stmt::ClassDef { name, body, .. } => {
            let _ = name;
            collect_refs(body, out);
        }
        Stmt::Import { names, .. } | Stmt::FromImport { names, .. } => {
            // import 绑定名非 Name 引用
            let _ = names;
        }
        Stmt::Break { .. } | Stmt::Continue { .. } | Stmt::Pass { .. } => {}
        Stmt::Global { .. } | Stmt::Nonlocal { .. } => {
            // 编译期语义——无表达式引用
        }
        Stmt::Raise { exc, .. } => {
            if let Some(e) = exc {
                collect_refs_expr(e, out);
            }
        }
        Stmt::Switch { test, cases, .. } => {
            // test + 各 case pattern/体 = 定义处 scope 求值（同 If test）
            collect_refs_expr(test, out);
            for c in cases {
                if let Some(p) = &c.pattern {
                    collect_refs_expr(p, out);
                }
                collect_refs(&c.body, out);
            }
        }
        Stmt::Try { body, orelse, finalbody, .. } => {
            collect_refs(body, out);
            collect_refs(orelse, out);
            collect_refs(finalbody, out);
        }
    }
}

pub(crate) fn collect_refs_expr(e: &Expr, out: &mut BTreeSet<String>) {
    match e {
        Expr::Name { id, .. } => {
            out.insert(id.clone());
        }
        // 声明面：target 名 = 定义（非 free 引用）；注解 = 类型级名字（非值引用）
        Expr::TypeAnnotatedExpr { .. } => {}
        Expr::BinOp { left, right, .. } => {
            collect_refs_expr(left, out);
            collect_refs_expr(right, out);
        }
        Expr::UnaryOp { operand, .. } => collect_refs_expr(operand, out),
        Expr::BoolOp { values, .. } | Expr::List { elts: values, .. } => {
            for v in values {
                collect_refs_expr(v, out);
            }
        }
        Expr::Tuple { elts, .. } => {
            for v in elts {
                collect_refs_expr(v, out);
            }
        }
        Expr::Compare { left, comparators, .. } => {
            collect_refs_expr(left, out);
            for c in comparators {
                collect_refs_expr(c, out);
            }
        }
        Expr::Call { func, args, .. } => {
            collect_refs_expr(func, out);
            for a in args {
                collect_refs_expr(a, out);
            }
        }
        Expr::Dict { keys, values, .. } => {
            for k in keys {
                collect_refs_expr(k, out);
            }
            for v in values {
                collect_refs_expr(v, out);
            }
        }
        Expr::Attribute { value, .. } => collect_refs_expr(value, out),
        Expr::Subscript { value, slice, .. } => {
            collect_refs_expr(value, out);
            collect_refs_expr(slice, out);
        }
        Expr::IfExp { test, body, orelse, .. } => {
            collect_refs_expr(test, out);
            collect_refs_expr(body, out);
            collect_refs_expr(orelse, out);
        }
        Expr::Slice { lower, upper, step, .. } => {
            for p in [lower, upper, step] {
                if let Some(e) = p {
                    collect_refs_expr(e, out);
                }
            }
        }
        Expr::Constant { .. } | Expr::Lambda { .. } => {}
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
