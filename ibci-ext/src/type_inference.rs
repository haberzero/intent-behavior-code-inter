//! 类型推导（全量 Rust 化·语义层：类型解析 type_uid）。
//!
//! 对齐 IBCI 类型系统：运算符类型推导 = 公理层数据驱动（`resolve_operation_type_name`，
//! 从左操作数类型分派，无兜底——贯彻"一切皆对象"）。字面值 → 字面类型；变量引用 →
//! 类型环境（作用域栈）；二元运算 → 公理 op 表；函数调用 → 函数签名返回类型；类型注解
//! （returns / 参数）→ intrinsic Name 子集。
//!
//! type_uid = `type_root.<类型字符串>`（root 模块）。与 Python 语义层 type_uid 差分等价
//! （确定性语义面等价 + 已裁定偏离白名单[divergence 注册表]）。
//!
//! 对齐基准 = IBCI 公理（core/kernel/axioms/primitives/{numeric,sequences}.py 的
//! resolve_operation_type_name），非 Python TypeCheckingVisitor 历史实现。

use std::collections::BTreeMap;

use crate::parser::{ConstVal, Expr};

/// 类型环境（作用域栈）：每 scope 一个 Name → 类型字符串 map。
pub type TypeEnv = Vec<BTreeMap<String, String>>;
/// 函数签名表：函数名 → 返回类型字符串。
pub type FuncSignatures = BTreeMap<String, String>;

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

/// 字面值类型推断（int/str/bool/float/None/list/dict/tuple）。非字面值返回 None。
/// = `infer_type_env` 的空环境/空签名特例（单一实现，无重复）。
pub fn infer_type(expr: &Expr) -> Option<String> {
    let empty_env: TypeEnv = Vec::new();
    let empty_sigs: FuncSignatures = BTreeMap::new();
    infer_type_env(expr, &empty_env, &empty_sigs)
}

/// 带类型环境 + 函数签名的类型推导（Name/BinOp/Call/容器/字面值）。
/// UnaryOp/BoolOp/Compare 等 → None（gap，归后续增量）。
pub fn infer_type_env(
    expr: &Expr,
    type_env: &TypeEnv,
    func_sigs: &FuncSignatures,
) -> Option<String> {
    match expr {
        Expr::Constant { value, .. } => Some(literal_type(value)),
        Expr::Name { id, .. } => lookup_type(type_env, id),
        Expr::List { elts, .. } => {
            if elts.is_empty() {
                Some("list[any]".to_string())
            } else {
                infer_type_env(&elts[0], type_env, func_sigs)
                    .map(|t| format!("list[{}]", t))
            }
        }
        Expr::Dict { keys, values, .. } => {
            if keys.is_empty() {
                Some("dict[any,any]".to_string())
            } else {
                let k = infer_type_env(&keys[0], type_env, func_sigs)?;
                let v = infer_type_env(&values[0], type_env, func_sigs)?;
                Some(format!("dict[{},{}]", k, v))
            }
        }
        Expr::Tuple { elts, .. } => {
            if elts.is_empty() {
                Some("tuple[]".to_string())
            } else {
                let mut types = Vec::new();
                for e in elts {
                    types.push(infer_type_env(e, type_env, func_sigs)?);
                }
                Some(format!("tuple[{}]", types.join(",")))
            }
        }
        Expr::BinOp { left, op, right, .. } => {
            let l = infer_type_env(left, type_env, func_sigs)?;
            let r = infer_type_env(right, type_env, func_sigs)?;
            resolve_op(&l, op, &r)
        }
        Expr::Call { func, .. } => {
            // 用户函数签名优先，再内置调用类型表（intrinsic）
            let from_sigs = match func.as_ref() {
                Expr::Name { id, .. } => func_sigs.get(id).cloned(),
                _ => None,
            };
            from_sigs.or_else(|| intrinsic_call_type(func))
        }
        Expr::IfExp { body, .. } => {
            // 三元表达式类型 = body 类型（IBCI：假设 body/orelse 同类型，取 body）
            infer_type_env(body, type_env, func_sigs)
        }
        // UnaryOp/BoolOp/Compare/Attribute/Subscript/Lambda 等 → None（gap）
        _ => None,
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

/// 二元运算符类型（IBCI 公理层数据驱动：从左操作数类型分派，无兜底）。
/// 移植 core/kernel/axioms/primitives/{numeric,sequences}.py 的
/// `resolve_operation_type_name`（int/float/bool/str）。
pub fn resolve_op(left: &str, op: &str, right: &str) -> Option<String> {
    match left {
        "int" => int_op(op, right),
        "float" => float_op(op, right),
        "bool" => bool_op(op, right),
        "str" => str_op(op, right),
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

/// 内置调用类型表（构造函数/特殊函数 → 返回类型，IBCI 一等值类型/内置类型）。
/// 对齐 IBCI：knowledge() → knowledge / quote → quoted / meta.eval → auto。
pub fn intrinsic_call_type(func: &Expr) -> Option<String> {
    match func {
        Expr::Name { id, .. } => match id.as_str() {
            "knowledge" => Some("knowledge".to_string()),
            "quote" => Some("quoted".to_string()),
            "print" => Some("void".to_string()),
            "range" => Some("list".to_string()),
            "len" => Some("int".to_string()),
            _ => None,
        },
        Expr::Attribute { attr, .. } => match attr.as_str() {
            "quote" => Some("quoted".to_string()),
            // meta.eval → auto：对齐 scope 符号 type_uid（`y = meta.eval(x)` 的 y 符号
            // type_uid = auto，Python 43/43）。node_to_type 的 meta.eval() 调用返回 any
            // 属节点级偏离（已排除 Attribute callee，gap）——符号 type_uid 优先。
            "eval" => Some("auto".to_string()),
            _ => None,
        },
        _ => None,
    }
}
