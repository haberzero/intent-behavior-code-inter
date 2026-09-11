//! 纯 AST 辅助（生产面——从差分转录组件手术提取）：类型注解字符串化
//! （annotation_type_str）+ 语句子树引用名收集（collect_refs 族——free_vars
//! 计算 / 闭包捕获）。零转录依赖（仅 AST 类型）。

use std::collections::BTreeSet;

use crate::parser::{Expr, Stmt};

/// 类型注解字符串化（声明面类型文本——`list[int]` / `mod.Type` 等）。
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
        // 点分类型：mod.Type
        Expr::Attribute { value, attr, .. } => {
            format!("{}.{}", annotation_type_str(value), attr)
        }
        _ => "any".to_string(),
    }
}

/// 收集语句子树引用的名字（free_vars 计算）：不进入嵌套函数体（归嵌套函数自身的
/// free_vars），但收集嵌套函数的参数/返回注解引用（注解在定义处 scope 求值）。
pub(crate) fn collect_refs(stmts: &[Stmt], out: &mut BTreeSet<String>) {
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

/// 容器类型解析（"list[int]" → ("list", ["int"])——intrinsic 符号生产面）。
pub(crate) fn parse_container(t: &str) -> (&str, Vec<String>) {
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

/// 收集表达式引用的名字（free_vars——闭包捕获面）。
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
