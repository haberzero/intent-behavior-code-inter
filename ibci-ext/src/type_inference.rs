//! 类型推导（全量 Rust 化·语义层：类型解析 type_uid）。
//!
//! 对齐 IBCI 类型系统：运算符类型推导 = 公理层数据驱动（`resolve_operation_type_name`，
//! 从左操作数类型分派，无兜底——贯彻"一切皆对象"）；方法返回类型 = 公理层声明式方法表
//! （转录，容器方法按类型参数特化）；字面值 → 字面类型；变量引用 → 类型环境（作用域栈）；
//! 二元运算 → 公理 op 表；函数调用 → 函数签名/intrinsic 返回类型/模块成员；下标 → 容器
//! 元素类型；属性 → 方法 bound_method / 模块成员 / 字段。
//!
//! type_uid = `type_root.<类型字符串>`（root 模块）。与 Python 语义层 type_uid 差分等价
//! （确定性语义面等价 + 已裁定偏离白名单[divergence 注册表]）。
//!
//! 对齐基准 = IBCI 公理（core/kernel/axioms/primitives/*.py 的 resolve_operation_type_name
//! + 声明式方法表），非 Python TypeCheckingVisitor 历史实现。
//!
//! 双通道语义（2b-2b-1 裁定实体化）：`infer_type_env` = 节点通道（type checker 对节点的
//! 绑定；meta.eval() 调用 = any[模块属性调用未解析的 checker 绑定]）；`symbol_level_type`
//! = 符号通道（赋值 → scope 符号/type_env；meta.eval() = 声明返回类型 auto）——符号
//! type_uid 优先（scope 符号 43/43 已验证）。

use std::collections::{BTreeMap, BTreeSet};

use crate::parser::{ConstVal, Expr};

/// 类型环境（作用域栈）：每 scope 一个 Name → 类型字符串 map。
pub type TypeEnv = Vec<BTreeMap<String, String>>;
/// 函数签名表：函数名 → 返回类型字符串。
pub type FuncSignatures = BTreeMap<String, String>;
/// 导入模块名集合（`import X` 的模块名——模块成员属性解析）。
pub type ModuleNames = BTreeSet<String>;

/// 推导上下文（单一入口，两 walker[符号/节点]共用——机制同构，无平行实现）。
pub struct InferCtx<'a> {
    pub type_env: &'a TypeEnv,
    pub func_sigs: &'a FuncSignatures,
    pub modules: &'a ModuleNames,
}

/// intrinsic 类型名判定（类型注解 Name → 基本类型）。
pub fn is_intrinsic_type(name: &str) -> bool {
    matches!(
        name,
        "int" | "float" | "str" | "bool" | "None" | "list" | "dict" | "tuple" | "any" | "void"
    )
}

/// 字面值类型（int/float/str/bool/None）。
pub fn literal_type(value: &ConstVal) -> String {
    match value {
        ConstVal::Int(_) => "int".to_string(),
        ConstVal::Float(_) => "float".to_string(),
        ConstVal::Str(_) => "str".to_string(),
        ConstVal::Bool(_) => "bool".to_string(),
        ConstVal::None_ => "None".to_string(),
    }
}

/// 完整节点级类型推导（节点通道）：字面值/Name[类型环境]/容器[裸+泛型]/二元运算[公理
/// op 表 + any 传播]/一元[not→bool, ±→操作数类型]/布尔逻辑[bool]/比较[any 传播]/
/// 调用[intrinsic 返回类型表 + 用户签名 + 方法表 + 模块成员]/三元[body 类型]/
/// 下标[容器元素类型]/属性[bound_method/模块成员/字段]。
/// Slice 不绑定（Python type checker 不产 Slice 节点绑定，语料实证 0 bound）→ None。
pub fn infer_type_env(expr: &Expr, ctx: &InferCtx) -> Option<String> {
    match expr {
        Expr::Constant { value, .. } => Some(literal_type(value)),
        Expr::Name { id, .. } => lookup_type(ctx.type_env, id),
        Expr::List { elts, .. } => {
            if elts.is_empty() {
                // 空列表字面量 = 裸 list（Python 实证：无特化身份，不产 list[any]）。
                Some("list".to_string())
            } else {
                infer_type_env(&elts[0], ctx)
                    .map(|t| format!("list[{}]", t))
            }
        }
        Expr::Dict { keys, values, .. } => {
            if keys.is_empty() {
                Some("dict".to_string())
            } else {
                let k = infer_type_env(&keys[0], ctx)?;
                let v = infer_type_env(&values[0], ctx)?;
                Some(format!("dict[{},{}]", k, v))
            }
        }
        Expr::Tuple { elts, .. } => {
            if elts.is_empty() {
                Some("tuple".to_string())
            } else {
                let mut types = Vec::new();
                for e in elts {
                    types.push(infer_type_env(e, ctx)?);
                }
                Some(format!("tuple[{}]", types.join(",")))
            }
        }
        Expr::BinOp { left, op, right, .. } => {
            let l = infer_type_env(left, ctx)?;
            let r = infer_type_env(right, ctx)?;
            resolve_op(&l, op, &r)
        }
        Expr::UnaryOp { op, operand, .. } => {
            if op == "not" {
                Some("bool".to_string())
            } else {
                // +/- 一元：结果 = 操作数类型（int/float；any 传播；不可解析 → any）
                match infer_type_env(operand, ctx).as_deref() {
                    Some(t) if matches!(t, "int" | "float" | "any" | "auto") => Some(t.to_string()),
                    _ => Some("any".to_string()),
                }
            }
        }
        Expr::BoolOp { .. } => Some("bool".to_string()),
        Expr::Compare { left, comparators, .. } => {
            // 比较 → bool；任一操作数为动态类型（any/auto）→ any（IBCI 动态类型
            // 比较结果不可静态判定，语料实证 i == 3 → any）。
            let mut operands = vec![infer_type_env(left, ctx)?];
            for c in comparators {
                operands.push(infer_type_env(c, ctx)?);
            }
            if operands.iter().any(|t| matches!(t.as_str(), "any" | "auto")) {
                Some("any".to_string())
            } else {
                Some("bool".to_string())
            }
        }
        Expr::Call { func, .. } => call_node_type(func, ctx),
        Expr::IfExp { body, .. } => {
            // 三元表达式类型 = body 类型（IBCI：假设 body/orelse 同类型，取 body）
            infer_type_env(body, ctx)
        }
        Expr::Subscript { value, slice, .. } => subscript_type(value, slice, ctx),
        Expr::Attribute { value, attr, .. } => attribute_type(value, attr, ctx),
        // Slice 节点不绑定（Python 实证）/ Lambda（语料面不含）
        _ => None,
    }
}

/// 符号通道类型（赋值 RHS → scope 符号 / type_env 绑定）：= 节点通道，唯一差异 =
/// meta.eval() 调用 = 声明返回类型 auto（节点通道为 any——checker 绑定回退 vs 符号
/// 声明，2b-2b-1 裁定：符号 type_uid 优先[scope 符号 43/43]）。
pub fn symbol_level_type(expr: &Expr, ctx: &InferCtx) -> Option<String> {
    if let Expr::Call { func, .. } = expr {
        if let Expr::Attribute { value, attr, .. } = func.as_ref() {
            if attr == "eval" {
                if let Expr::Name { id, .. } = value.as_ref() {
                    if ctx.modules.contains(id) {
                        return Some("auto".to_string());
                    }
                }
            }
        }
    }
    infer_type_env(expr, ctx)
}

/// 方法签名特化（public core 的泛型成员特化协议转录——core/kernel/spec/generic.py
/// 的 resolve_member 回调）：list[T] 的 pop/__getitem__ → T；append/insert/
/// __setitem__ 末参 → T；dict[K,V] 的 get/pop → V、values → list[V]、keys → list[K]；
/// Optional[T] 的 unwrap/or_else → T（or_else 首参 → T）。
pub fn method_signature_specialized(base: &str, attr: &str) -> Option<(Vec<String>, String)> {
    let (kind, params) = parse_container(base);
    let elem = params.first().map(|s| s.as_str());
    let (declared_params, _declared_ret) =
        crate::intrinsic_symbols::method_signature(kind, attr)?;
    let mut p = declared_params;
    let r = method_call_return(base, attr).unwrap_or_else(|| _declared_ret.to_string());
    match kind {
        "list" => {
            if let Some(e) = elem {
                if e != "any"
                    && matches!(attr, "append" | "insert" | "__setitem__")
                    && !p.is_empty()
                {
                    *p.last_mut().unwrap() = e.to_string();
                }
            }
        }
        "Optional" => {
            if let Some(w) = elem {
                if w != "any" && attr == "or_else" && !p.is_empty() {
                    p[0] = w.to_string();
                }
            }
        }
        _ => {}
    }
    Some((p, r))
}

/// bound_method 共享类型改写（last-wins）：方法属性访问（attribute_type 判定
/// bound_method）→ 该方法特化签名 (params, ret)（单一权威源：声明表 + 泛型特化 +
/// 方法返回表，无重复判定）；非方法属性（模块成员/字段/任意 any 属性）= None。
pub fn bound_method_rewrite(value: &Expr, attr: &str, ctx: &InferCtx) -> Option<(Vec<String>, String)> {
    if attribute_type(value, attr, ctx).as_deref() == Some("bound_method") {
        let base = infer_type_env(value, ctx)?;
        method_signature_specialized(&base, attr)
    } else {
        None
    }
}

/// 变量类型查找（从内层 scope 往外——closure/global 链）。
fn lookup_type(type_env: &TypeEnv, name: &str) -> Option<String> {
    for scope in type_env.iter().rev() {
        if let Some(t) = scope.get(name) {
            return Some(t.clone());
        }
    }
    None
}

/// 容器类型解析：`list[int]` → ("list", ["int"]) / `dict[str,list[int]]` →
/// ("dict", ["str", "list[int]"]) / `tuple[int,int]` → ("tuple", [...]) /
/// `int` → ("int", [])。顶层逗号分割（括号深度感知，嵌套泛型不拆散）。
pub fn parse_container(t: &str) -> (&str, Vec<String>) {
    match t.find('[') {
        Some(open) => {
            let close = t.rfind(']').unwrap_or(t.len());
            let kind = &t[..open];
            let inner = &t[open + 1..close];
            (kind, split_top_level(inner))
        }
        None => (t, Vec::new()),
    }
}

/// 顶层逗号分割（深度感知）。
fn split_top_level(s: &str) -> Vec<String> {
    let mut parts = Vec::new();
    let mut depth = 0usize;
    let mut cur = String::new();
    for ch in s.chars() {
        match ch {
            '[' => {
                depth += 1;
                cur.push(ch);
            }
            ']' => {
                depth = depth.saturating_sub(1);
                cur.push(ch);
            }
            ',' if depth == 0 => {
                parts.push(cur.trim().to_string());
                cur = String::new();
            }
            _ => cur.push(ch),
        }
    }
    if !cur.trim().is_empty() {
        parts.push(cur.trim().to_string());
    }
    parts
}

/// 二元运算符类型（IBCI 公理层数据驱动：从左操作数类型分派，无兜底）。
/// 移植 core/kernel/axioms/primitives/{numeric,sequences}.py 的
/// `resolve_operation_type_name`（int/float/bool/str/list）。动态类型
/// （any/auto）操作数 → any（语料实证：total + i[any] → any）。
pub fn resolve_op(left: &str, op: &str, right: &str) -> Option<String> {
    let (lk, _) = parse_container(left);
    let (rk, _) = parse_container(right);
    if matches!(lk, "any" | "auto") || matches!(rk, "any" | "auto") {
        return Some("any".to_string());
    }
    match lk {
        "int" => int_op(op, rk),
        "float" => float_op(op, rk),
        "bool" => bool_op(op, rk),
        "str" => str_op(op, rk),
        // list + list → list（公理 sequences：list.__add__ ret=list，不特化元素）
        "list" if op == "+" && rk == "list" => Some("list".to_string()),
        _ => None,
    }
}

fn int_op(op: &str, other: &str) -> Option<String> {
    match op {
        "+" | "-" | "*" | "/" | "//" | "%" | "&" | "|" | "^" | "<<" | ">>" => {
            if other == "int" {
                Some("int".to_string())
            } else if other == "float" {
                Some("float".to_string())
            } else if op == "*" && other == "str" {
                // 字符串重复（int * str，运行期合法——Python 同语义）
                Some("str".to_string())
            } else {
                None
            }
        }
        "**" => {
            if other == "int" {
                Some("int".to_string())
            } else if other == "float" {
                Some("float".to_string())
            } else {
                None
            }
        }
        "==" | "!=" => Some("bool".to_string()),
        ">" | ">=" | "<" | "<=" => {
            if other == "int" || other == "float" || other == "bool" {
                Some("bool".to_string())
            } else {
                None
            }
        }
        _ => None,
    }
}

fn float_op(op: &str, other: &str) -> Option<String> {
    match op {
        "+" | "-" | "*" | "/" | "//" | "%" | "**" => {
            if other == "int" || other == "float" {
                Some("float".to_string())
            } else {
                None
            }
        }
        "==" | "!=" => Some("bool".to_string()),
        ">" | ">=" | "<" | "<=" => {
            if other == "int" || other == "float" || other == "bool" {
                Some("bool".to_string())
            } else {
                None
            }
        }
        _ => None,
    }
}

fn bool_op(op: &str, other: &str) -> Option<String> {
    match op {
        "&" | "|" | "^" => {
            if other == "bool" || other == "int" {
                Some("bool".to_string())
            } else {
                None
            }
        }
        "==" | "!=" => Some("bool".to_string()),
        "+" | "-" | "*" | "//" => {
            if other == "bool" || other == "int" {
                Some("int".to_string())
            } else if other == "float" {
                Some("float".to_string())
            } else if op == "*" && other == "str" {
                Some("str".to_string())
            } else {
                None
            }
        }
        ">" | ">=" | "<" | "<=" => {
            if other == "bool" || other == "int" || other == "float" {
                Some("bool".to_string())
            } else {
                None
            }
        }
        _ => None,
    }
}

fn str_op(op: &str, other: &str) -> Option<String> {
    match op {
        "+" if other == "str" => Some("str".to_string()),
        "==" | "!=" => Some("bool".to_string()),
        ">" | ">=" | "<" | "<=" if other == "str" => Some("bool".to_string()),
        _ => None,
    }
}

/// 类型注解（returns / 参数 annotation）→ 类型字符串（intrinsic Name 子集）。
pub fn parse_type_annotation(expr: &Expr) -> Option<String> {
    match expr {
        Expr::Name { id, .. } if is_intrinsic_type(id) => Some(id.clone()),
        _ => None,
    }
}

/// 调用节点类型（节点通道）：Name callee = 用户签名优先 → intrinsic 函数返回类型表；
/// Attribute callee = 模块成员（import 模块的函数面）→ 方法返回类型表（容器特化）。
/// 未解析 → any（Python type checker generic 绑定 = any，语料实证全覆盖）。
fn call_node_type(func: &Expr, ctx: &InferCtx) -> Option<String> {
    match func {
        Expr::Name { id, .. } => ctx
            .func_sigs
            .get(id)
            .cloned()
            .or_else(|| intrinsic_function_return(id)),
        Expr::Attribute { value, attr, .. } => {
            // 模块成员（import X 的 X.attr）：meta.quote → quoted / meta.eval → any
            //（节点通道；声明 auto 归符号通道 symbol_level_type）。
            if let Expr::Name { id, .. } = value.as_ref() {
                if ctx.modules.contains(id) {
                    return match (id.as_str(), attr.as_str()) {
                        ("meta", "quote") => Some("quoted".to_string()),
                        _ => Some("any".to_string()),
                    };
                }
            }
            let base = infer_type_env(value, ctx)?;
            method_call_return(&base, attr).or_else(|| Some("any".to_string()))
        }
        _ => Some("any".to_string()),
    }
}

/// intrinsic 函数返回类型表（19 内置函数 + knowledge/quote 一等值类型构造，转录自
/// IBCI intrinsic 类型声明；实证探测对齐：all→bool/callable→auto/copy→any/
/// deepcopy→any/len→int/max→any/min→any/print→void/range→list/reversed→list/
/// sorted→list/sum→any/type→str/vec→vector/zip→list）。enumerate/fn/next/
/// get_self_source = 特殊形态（语料面不覆盖，不产条目）。
fn intrinsic_function_return(id: &str) -> Option<String> {
    Some(match id {
        "all" => "bool",
        "callable" => "auto",
        "copy" => "any",
        "deepcopy" => "any",
        "len" => "int",
        "max" => "any",
        "min" => "any",
        "print" => "void",
        "range" => "list",
        "reversed" => "list",
        "sorted" => "list",
        "sum" => "any",
        "type" => "str",
        "vec" => "vector",
        "zip" => "list",
        "knowledge" => "knowledge",
        "quote" => "quoted",
        _ => return None,
    }
    .to_string())
}

/// 方法返回类型表（转录自 IBCI 公理层声明式方法表 core/kernel/axioms/primitives/
/// *.py；容器方法按类型参数特化：list.pop → 元素 T / dict.get → 值 V / dict.keys →
/// list[K] / dict.values → list[V]；裸容器无实参 → any/list）。
pub fn method_call_return(base: &str, attr: &str) -> Option<String> {
    let (kind, params) = parse_container(base);
    let first = || params.first().cloned().unwrap_or_else(|| "any".to_string());
    let second = || params.get(1).cloned().unwrap_or_else(|| "any".to_string());
    Some(match (kind, attr) {
        // str
        ("str", "upper" | "lower" | "strip" | "replace" | "join" | "format") => "str",
        ("str", "split") => "list",
        ("str", "find" | "rfind" | "count") => "int",
        ("str", "startswith" | "endswith" | "contains" | "is_empty" | "to_bool") => "bool",
        ("str", "len") => "int",
        ("str", "cast_to") => "any",
        // list
        ("list", "append" | "insert" | "remove" | "sort" | "reverse" | "clear") => "void",
        ("list", "index" | "count" | "len") => "int",
        ("list", "contains" | "is_empty" | "to_bool") => "bool",
        // list.pop → 元素类型（公理声明 any；checker 按容器实参特化，语料实证
        // list[int].pop → int；裸 list → any）。
        ("list", "pop") => return Some(first()),
        ("list", "cast_to") => "any",
        // dict
        // dict.get → 值类型（公理声明 any；checker 特化，语料实证 dict[str,int].get → int）。
        ("dict", "get") => return Some(second()),
        // dict.keys/values → 键/值类型的 list（语料实证 dict[str,int].keys → list[str]）。
        ("dict", "keys") => {
            return Some(if params.is_empty() {
                "list".to_string()
            } else {
                format!("list[{}]", first())
            });
        }
        ("dict", "values") => {
            return Some(if params.is_empty() {
                "list".to_string()
            } else {
                format!("list[{}]", second())
            });
        }
        ("dict", "items") => "list",
        ("dict", "update") => "void",
        ("dict", "len") => "int",
        ("dict", "contains") => "bool",
        ("dict", "cast_to") => "any",
        // tuple
        ("tuple", "len") => "int",
        ("tuple", "contains") => "bool",
        ("tuple", "cast_to") => "any",
        // 数值族
        ("int" | "float" | "bool", "to_bool") => "bool",
        ("int" | "float" | "bool", "to_list") => "list",
        ("int" | "float" | "bool", "cast_to") => "any",
        // vector
        ("vector", "dim") => "int",
        ("vector", "dot" | "norm" | "cosine") => "float",
        ("vector", "scale" | "add" | "sub") => "vector",
        ("vector", "cast_to") => "any",
        // quoted（公理方法表）
        ("quoted", "cast_to") => "any",
        // knowledge（公理声明式方法表全量）
        ("knowledge", "store" | "amend" | "register_word" | "register_relation"
        | "register_world" | "retract" | "amend_fact" | "set_embedding") => "void",
        ("knowledge", "history" | "keys" | "words" | "relations" | "worlds" | "facts"
        | "all_in_world" | "by_source" | "by_subject" | "transitive" | "history_fact"
        | "embed_search" | "lookup_pair") => "list",
        ("knowledge", "len" | "fact_len" | "embedding_dim") => "int",
        ("knowledge", "exists" | "contradicts" | "same_word" | "has_embedding") => "bool",
        ("knowledge", "export" | "expand" | "compare") => "dict",
        ("knowledge", "add_fact" | "source" | "to_ibci") => "str",
        ("knowledge", "embedding") => "vector",
        ("knowledge", "get" | "word" | "relation" | "world" | "get_fact" | "cast_to") => "any",
        _ => return None,
    }
    .to_string())
}

/// 下标类型：list[T] 切片 → list[T] / 索引 → T；dict[K,V] → V；tuple 索引 → 首元素；
/// vector → float（公理 __getitem__）；裸容器/不可解析 → any（语料实证全覆盖）。
fn subscript_type(value: &Expr, slice: &Expr, ctx: &InferCtx) -> Option<String> {
    let base = infer_type_env(value, ctx)?;
    let (kind, params) = parse_container(&base);
    let is_slice = matches!(slice, Expr::Slice { .. });
    let first = params.first().cloned();
    let second = params.get(1).cloned();
    Some(match kind {
        "list" => {
            if is_slice {
                match first {
                    Some(t) => format!("list[{}]", t),
                    None => "list".to_string(),
                }
            } else {
                first.unwrap_or_else(|| "any".to_string())
            }
        }
        "dict" => second.unwrap_or_else(|| "any".to_string()),
        "tuple" => first.unwrap_or_else(|| "any".to_string()),
        "vector" => "float".to_string(),
        _ => "any".to_string(),
    })
}

/// 属性节点类型：模块成员（import 模块 X 的 X.attr）→ 成员类型（type_root.<attr>，
/// 语料实证 meta.quote → quote / meta.eval → eval）；方法访问 → bound_method
/// （公理方法表判定）；字段访问（quoted.source = str，语料实证）；其余 → any。
pub fn attribute_type(value: &Expr, attr: &str, ctx: &InferCtx) -> Option<String> {
    if let Expr::Name { id, .. } = value {
        if ctx.modules.contains(id) {
            return Some(attr.to_string());
        }
    }
    let base = infer_type_env(value, ctx)?;
    // 字段访问（非方法成员）：quoted 的 source 字段 = str。
    if base == "quoted" && attr == "source" {
        return Some("str".to_string());
    }
    if method_call_return(&base, attr).is_some() {
        return Some("bound_method".to_string());
    }
    Some("any".to_string())
}
