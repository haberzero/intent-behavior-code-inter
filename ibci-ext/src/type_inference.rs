//! 字面值类型推断（全量 Rust 化·语义层：类型解析 type_uid）。
//!
//! 对应 Python 语义层的类型解析（type resolution）中的字面值类型推断：遍历 Rust AST
//! 表达式，推断字面值的类型（int/str/bool/float/list/dict/tuple）。类型字符串格式：
//! `int` / `float` / `str` / `bool` / `None` / `list[<元素类型>]` /
//! `dict[<键类型>,<值类型>]` / `tuple[<元素类型列表>]`。
//!
//! type_uid = `type_root.<类型字符串>`（root 模块）。与 Python 语义层的 type_uid 差分
//! 等价（34 语料，字面值可推断子集）。非字面值[变量引用/函数调用/二元运算等，需类型
//! 环境 + 函数签名]归类型解析后续。

use crate::parser::{ConstVal, Expr};

/// 字面值类型推断。返回类型字符串（如 `int`、`list[int]`、`dict[str,int]`、
/// `tuple[int,int,int]`）。非字面值返回 None。
pub fn infer_type(expr: &Expr) -> Option<String> {
    match expr {
        Expr::Constant { value, .. } => Some(match value {
            ConstVal::Int(_) => "int".to_string(),
            ConstVal::Float(_) => "float".to_string(),
            ConstVal::Str(_) => "str".to_string(),
            ConstVal::Bool(_) => "bool".to_string(),
            ConstVal::None_ => "None".to_string(),
        }),
        Expr::List { elts, .. } => {
            if elts.is_empty() {
                Some("list[any]".to_string())
            } else {
                infer_type(&elts[0]).map(|t| format!("list[{}]", t))
            }
        }
        Expr::Dict { keys, values, .. } => {
            if keys.is_empty() {
                Some("dict[any,any]".to_string())
            } else {
                let k = infer_type(&keys[0])?;
                let v = infer_type(&values[0])?;
                Some(format!("dict[{},{}]", k, v))
            }
        }
        Expr::Tuple { elts, .. } => {
            if elts.is_empty() {
                Some("tuple[]".to_string())
            } else {
                let mut types = Vec::new();
                for e in elts {
                    types.push(infer_type(e)?);
                }
                Some(format!("tuple[{}]", types.join(",")))
            }
        }
        _ => None,
    }
}
