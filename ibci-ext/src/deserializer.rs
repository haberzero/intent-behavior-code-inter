//! ibci-ext Rust artifact 反序列化器——序列化 CompilationArtifact（FlatSerializer
//! 的 JSON dict）→ Rust AST（执行核心的输入契约）。
//!
//! 移植范围（本增量）：nodes 池（AST 节点，UID 引用）→ Rust AST（复用 parser 的
//! Expr/Stmt 类型 + dumper）。语料面 19 种节点类型。执行核心（阶段③）经此消费
//! Python 前端产出的 artifact（含语义层输出），逐步 Rust 化。后续增量 = 符号池/
//! 类型池/侧表 + 执行（对象模型 + CPS 分发）。
//!
//! 差分门：反序列化 AST 完整形态（含位置）== Python AST 完整形态（`tests/
//! diff_harness/ast_dump.py` include_positions=True 参考）——验证 Rust 侧可消费
//! 序列化 artifact（执行核心的输入契约）。

use crate::parser::{Alias, Arg, ConstVal, Expr, Module, Pos, Stmt};
use serde_json::Value;

// --------------------------------------------------------------------------- //
// 位置 + 标量解析
// --------------------------------------------------------------------------- //
fn pos_of(v: &Value) -> Pos {
    Pos {
        lineno: v["lineno"].as_i64().unwrap_or(0),
        col_offset: v["col_offset"].as_i64().unwrap_or(0),
        end_lineno: v["end_lineno"].as_i64(),
        end_col_offset: v["end_col_offset"].as_i64(),
    }
}

fn const_of(v: &Value) -> ConstVal {
    if v.is_null() {
        return ConstVal::None_;
    }
    if let Some(b) = v.as_bool() {
        return ConstVal::Bool(b);
    }
    if let Some(i) = v.as_i64() {
        return ConstVal::Int(i);
    }
    if let Some(f) = v.as_f64() {
        return ConstVal::Float(f);
    }
    if let Some(s) = v.as_str() {
        return ConstVal::Str(s.to_string());
    }
    ConstVal::None_
}

fn str_of(v: &Value) -> String {
    v.as_str().unwrap_or("").to_string()
}

// --------------------------------------------------------------------------- //
// 节点重构（UID → Rust AST；nodes 池为 uid → 节点 dict）
// --------------------------------------------------------------------------- //
type NodeMap = std::collections::HashMap<String, Value>;

/// 节点统一形态（Stmt 或 Expr）。
enum Node {
    Stmt(Stmt),
    Expr(Expr),
}

fn uid_of(v: &Value) -> String {
    v.as_str().unwrap_or("").to_string()
}

fn build_node(uid: &str, nodes: &NodeMap) -> Node {
    let n = nodes.get(uid).unwrap();
    match n["_type"].as_str().unwrap_or("") {
        // ---- 语句 ---- //
        "IbAssign" => Node::Stmt(Stmt::Assign {
            pos: pos_of(n),
            targets: uids_of(&n["targets"]).iter().map(|u| expr_of(u, nodes)).collect(),
            value: opt_uid(n.get("value")).map(|u| expr_of(&u, nodes)),
        }),
        "IbAugAssign" => Node::Stmt(Stmt::AugAssign {
            pos: pos_of(n),
            target: expr_of(&uid_of(&n["target"]), nodes),
            op: str_of(&n["op"]),
            value: expr_of(&uid_of(&n["value"]), nodes),
        }),
        "IbExprStmt" => Node::Stmt(Stmt::ExprStmt {
            pos: pos_of(n),
            value: expr_of(&uid_of(&n["value"]), nodes),
        }),
        "IbIf" => Node::Stmt(Stmt::If {
            pos: pos_of(n),
            test: expr_of(&uid_of(&n["test"]), nodes),
            body: uids_of(&n["body"]).iter().map(|u| stmt_of(u, nodes)).collect(),
            orelse: uids_of(&n["orelse"]).iter().map(|u| stmt_of(u, nodes)).collect(),
        }),
        "IbFor" => Node::Stmt(Stmt::For {
            pos: pos_of(n),
            target: expr_of(&uid_of(&n["target"]), nodes),
            iter: expr_of(&uid_of(&n["iter"]), nodes),
            body: uids_of(&n["body"]).iter().map(|u| stmt_of(u, nodes)).collect(),
            orelse: uids_of(&n["orelse"]).iter().map(|u| stmt_of(u, nodes)).collect(),
        }),
        "IbWhile" => Node::Stmt(Stmt::While {
            pos: pos_of(n),
            test: expr_of(&uid_of(&n["test"]), nodes),
            body: uids_of(&n["body"]).iter().map(|u| stmt_of(u, nodes)).collect(),
            orelse: uids_of(&n["orelse"]).iter().map(|u| stmt_of(u, nodes)).collect(),
        }),
        "IbFunctionDef" => {
            let args: Vec<Arg> = uids_of(&n["args"])
                .iter()
                .map(|u| arg_of(u, nodes))
                .collect();
            let returns = opt_uid(n.get("returns")).map(|u| expr_of(&u, nodes));
            Node::Stmt(Stmt::FunctionDef {
                pos: pos_of(n),
                name: str_of(&n["name"]),
                args,
                body: uids_of(&n["body"]).iter().map(|u| stmt_of(u, nodes)).collect(),
                returns,
            })
        }
        "IbReturn" => Node::Stmt(Stmt::Return {
            pos: pos_of(n),
            value: opt_uid(n.get("value")).map(|u| expr_of(&u, nodes)),
        }),
        "IbBreak" => Node::Stmt(Stmt::Break { pos: pos_of(n) }),
        "IbContinue" => Node::Stmt(Stmt::Continue { pos: pos_of(n) }),
        "IbPass" => Node::Stmt(Stmt::Pass { pos: pos_of(n) }),
        "IbImport" => {
            // names = IbAlias uid 数组；每个 alias = {name, asname, 位置}
            let names: Vec<Alias> = uids_of(&n["names"])
                .iter()
                .map(|u| {
                    let alias = &nodes[u];
                    Alias {
                        pos: pos_of(alias),
                        name: str_of(&alias["name"]),
                        asname: alias["asname"].as_str().map(|s| s.to_string()),
                    }
                })
                .collect();
            Node::Stmt(Stmt::Import { pos: pos_of(n), names })
        }
        "IbImportFrom" => {
            // from X import Y [as Z]：module + names（IbAlias 数组）
            let names: Vec<Alias> = uids_of(&n["names"])
                .iter()
                .map(|u| {
                    let alias = &nodes[u];
                    Alias {
                        pos: pos_of(alias),
                        name: str_of(&alias["name"]),
                        asname: alias["asname"].as_str().map(|s| s.to_string()),
                    }
                })
                .collect();
            Node::Stmt(Stmt::FromImport {
                pos: pos_of(n),
                module: str_of(&n["module"]),
                names,
            })
        }
        "IbTry" => {
            let handlers = uids_of(&n["handlers"])
                .iter()
                .map(|u| except_handler_of(u, nodes))
                .collect();
            Node::Stmt(Stmt::Try {
                pos: pos_of(n),
                body: uids_of(&n["body"]).iter().map(|u| stmt_of(u, nodes)).collect(),
                handlers,
                orelse: uids_of(&n["orelse"]).iter().map(|u| stmt_of(u, nodes)).collect(),
                finalbody: uids_of(&n["finalbody"])
                    .iter()
                    .map(|u| stmt_of(u, nodes))
                    .collect(),
            })
        }
        "IbClassDef" => {
            let body: Vec<Stmt> = uids_of(&n["body"]).iter().map(|u| stmt_of(u, nodes)).collect();
            let fields: Vec<Stmt> = body
                .iter()
                .filter(|s| matches!(s, Stmt::Assign { .. }))
                .cloned()
                .collect();
            let methods: Vec<Stmt> = body
                .iter()
                .filter(|s| matches!(s, Stmt::FunctionDef { .. }))
                .cloned()
                .collect();
            Node::Stmt(Stmt::ClassDef {
                pos: pos_of(n),
                name: str_of(&n["name"]),
                body,
                fields,
                methods,
            })
        }
        "IbGlobalStmt" => {
            // global x[, y]：names = 裸名字串数组（非节点引用）
            Node::Stmt(Stmt::Global {
                pos: pos_of(n),
                names: names_of(&n["names"]),
            })
        }
        "IbNonlocalStmt" => {
            Node::Stmt(Stmt::Nonlocal {
                pos: pos_of(n),
                names: names_of(&n["names"]),
            })
        }
        "IbRaise" => Node::Stmt(Stmt::Raise {
            pos: pos_of(n),
            exc: opt_uid(n.get("exc")).map(|u| expr_of(&u, nodes)),
        }),
        "IbSwitch" => {
            // test + cases（IbCase 节点 uid 数组）；llmexcept_handler = LLM 面
            // （null 语料面，执行面不消费）
            Node::Stmt(Stmt::Switch {
                pos: pos_of(n),
                test: expr_of(&uid_of(&n["test"]), nodes),
                cases: uids_of(&n["cases"])
                    .iter()
                    .map(|u| case_of(u, nodes))
                    .collect(),
            })
        }
        // ---- 表达式 ---- //
        "IbTypeAnnotatedExpr" => {
            // 声明面 target（target Name + annotation 类型节点）
            Node::Expr(Expr::TypeAnnotatedExpr {
                pos: pos_of(n),
                target: Box::new(expr_of(&uid_of(&n["target"]), nodes)),
                annotation: Box::new(expr_of(&uid_of(&n["annotation"]), nodes)),
            })
        }
        "IbConstant" => Node::Expr(Expr::Constant {
            pos: pos_of(n),
            value: const_of(&n["value"]),
        }),
        "IbName" => Node::Expr(Expr::Name {
            pos: pos_of(n),
            id: str_of(&n["id"]),
            ctx: str_of(&n["ctx"]),
        }),
        "IbBinOp" => Node::Expr(Expr::BinOp {
            pos: pos_of(n),
            left: Box::new(expr_of(&uid_of(&n["left"]), nodes)),
            op: str_of(&n["op"]),
            right: Box::new(expr_of(&uid_of(&n["right"]), nodes)),
        }),
        "IbUnaryOp" => Node::Expr(Expr::UnaryOp {
            pos: pos_of(n),
            op: str_of(&n["op"]),
            operand: Box::new(expr_of(&uid_of(&n["operand"]), nodes)),
        }),
        "IbBoolOp" => Node::Expr(Expr::BoolOp {
            pos: pos_of(n),
            op: str_of(&n["op"]),
            values: uids_of(&n["values"]).iter().map(|u| expr_of(u, nodes)).collect(),
        }),
        "IbCompare" => {
            let ops: Vec<String> = n["ops"]
                .as_array()
                .map(|a| a.iter().map(|v| str_of(v)).collect())
                .unwrap_or_default();
            Node::Expr(Expr::Compare {
                pos: pos_of(n),
                left: Box::new(expr_of(&uid_of(&n["left"]), nodes)),
                ops,
                comparators: uids_of(&n["comparators"])
                    .iter()
                    .map(|u| expr_of(u, nodes))
                    .collect(),
            })
        }
        "IbCall" => Node::Expr(Expr::Call {
            pos: pos_of(n),
            func: Box::new(expr_of(&uid_of(&n["func"]), nodes)),
            args: uids_of(&n["args"]).iter().map(|u| expr_of(u, nodes)).collect(),
        }),
        "IbListExpr" => Node::Expr(Expr::List {
            pos: pos_of(n),
            elts: uids_of(&n["elts"]).iter().map(|u| expr_of(u, nodes)).collect(),
            ctx: str_of(&n["ctx"]),
        }),
        "IbDict" => Node::Expr(Expr::Dict {
            pos: pos_of(n),
            keys: uids_of(&n["keys"]).iter().map(|u| expr_of(u, nodes)).collect(),
            values: uids_of(&n["values"]).iter().map(|u| expr_of(u, nodes)).collect(),
        }),
        "IbAttribute" => Node::Expr(Expr::Attribute {
            pos: pos_of(n),
            value: Box::new(expr_of(&uid_of(&n["value"]), nodes)),
            attr: str_of(&n["attr"]),
            ctx: str_of(&n["ctx"]),
        }),
        "IbSubscript" => Node::Expr(Expr::Subscript {
            pos: pos_of(n),
            value: Box::new(expr_of(&uid_of(&n["value"]), nodes)),
            slice: Box::new(expr_of(&uid_of(&n["slice"]), nodes)),
            ctx: str_of(&n["ctx"]),
        }),
        "IbIfExp" => Node::Expr(Expr::IfExp {
            pos: pos_of(n),
            test: Box::new(expr_of(&uid_of(&n["test"]), nodes)),
            body: Box::new(expr_of(&uid_of(&n["body"]), nodes)),
            orelse: Box::new(expr_of(&uid_of(&n["orelse"]), nodes)),
        }),
        "IbTuple" => Node::Expr(Expr::Tuple {
            pos: pos_of(n),
            elts: uids_of(&n["elts"]).iter().map(|u| expr_of(u, nodes)).collect(),
            ctx: str_of(&n["ctx"]),
        }),
        "IbSlice" => Node::Expr(Expr::Slice {
            pos: pos_of(n),
            lower: opt_uid(n.get("lower")).map(|u| Box::new(expr_of(&u, nodes))),
            upper: opt_uid(n.get("upper")).map(|u| Box::new(expr_of(&u, nodes))),
            step: opt_uid(n.get("step")).map(|u| Box::new(expr_of(&u, nodes))),
        }),
        "IbLambdaExpr" => {
            let params: Vec<Arg> = uids_of(&n["params"])
                .iter()
                .map(|u| arg_of(u, nodes))
                .collect();
            Node::Expr(Expr::Lambda {
                pos: pos_of(n),
                params,
                body: Box::new(expr_of(&uid_of(&n["body"]), nodes)),
                capture_mode: str_of(&n["capture_mode"]),
                returns: opt_uid(n.get("returns")).map(|u| Box::new(expr_of(&u, nodes))),
            })
        }
        _ => Node::Expr(Expr::Constant {
            pos: pos_of(n),
            value: ConstVal::None_,
        }),
    }
}

fn stmt_of(uid: &str, nodes: &NodeMap) -> Stmt {
    match build_node(uid, nodes) {
        Node::Stmt(s) => s,
        Node::Expr(e) => Stmt::ExprStmt {
            pos: expr_pos(&e),
            value: e,
        },
    }
}

/// 裸名字串数组（global/nonlocal 的 names 字段——非节点引用）。
fn names_of(v: &Value) -> Vec<String> {
    match v {
        Value::Array(a) => a
            .iter()
            .filter_map(|x| x.as_str().map(String::from))
            .collect(),
        _ => vec![],
    }
}

/// IbCase 节点（switch 的 case 块：pattern[null = default] + body 语句 uid）。
fn case_of(uid: &str, nodes: &NodeMap) -> crate::parser::Case {
    let n = &nodes[uid];
    crate::parser::Case {
        pos: pos_of(n),
        pattern: opt_uid(n.get("pattern")).map(|u| expr_of(&u, nodes)),
        body: uids_of(&n["body"])
            .iter()
            .map(|u| stmt_of(u, nodes))
            .collect(),
    }
}

fn expr_of(uid: &str, nodes: &NodeMap) -> Expr {
    match build_node(uid, nodes) {
        Node::Expr(e) => e,
        Node::Stmt(_) => Expr::Constant {
            pos: Pos::module(),
            value: ConstVal::None_,
        },
    }
}

fn arg_of(uid: &str, nodes: &NodeMap) -> Arg {
    let n = nodes.get(uid).unwrap();
    Arg {
        pos: pos_of(n),
        arg: str_of(&n["arg"]),
        annotation: opt_uid(n.get("annotation")).map(|u| Box::new(expr_of(&u, nodes))),
        default: opt_uid(n.get("default")).map(|u| Box::new(expr_of(&u, nodes))),
        kind: str_of(&n["kind"]),
    }
}

fn except_handler_of(uid: &str, nodes: &NodeMap) -> crate::parser::ExceptHandler {
    let n = nodes.get(uid).unwrap();
    crate::parser::ExceptHandler {
        pos: pos_of(n),
        exc_type: opt_uid(n.get("type")).map(|u| expr_of(&u, nodes)),
        name: n["name"].as_str().map(|s| s.to_string()),
        body: uids_of(&n["body"]).iter().map(|u| stmt_of(u, nodes)).collect(),
    }
}

/// 子引用 UID 列表（值可能是单个 uid 或 uid 列表）。
fn uids_of(v: &Value) -> Vec<String> {
    match v {
        Value::Array(a) => a.iter().map(uid_of).collect(),
        Value::String(s) => vec![s.clone()],
        _ => vec![],
    }
}

/// 可选子引用（None/null → None；否则 uid）。
fn opt_uid(v: Option<&Value>) -> Option<String> {
    match v {
        Some(Value::String(s)) if !s.is_empty() => Some(s.clone()),
        _ => None,
    }
}

fn expr_pos(e: &Expr) -> Pos {
    match e {
        Expr::Constant { pos, .. }
        | Expr::Name { pos, .. }
        | Expr::BinOp { pos, .. }
        | Expr::UnaryOp { pos, .. }
        | Expr::BoolOp { pos, .. }
        | Expr::Compare { pos, .. }
        | Expr::Call { pos, .. }
        | Expr::List { pos, .. }
        | Expr::Dict { pos, .. }
        | Expr::Attribute { pos, .. }
        | Expr::Subscript { pos, .. }
        | Expr::IfExp { pos, .. }
        | Expr::Lambda { pos, .. }
        | Expr::Tuple { pos, .. }
        | Expr::Slice { pos, .. }
        | Expr::TypeAnnotatedExpr { pos, .. } => *pos,
    }
}

// --------------------------------------------------------------------------- //
// 入口：artifact JSON → 反序列化 AST 完整形态（含位置）
// --------------------------------------------------------------------------- //
/// artifact JSON → 反序列化 Module（AST）。None = 解析失败（artifact 非良构）。
pub fn deserialize_module(artifact_json: &str) -> Option<Module> {
    let root: Value = serde_json::from_str(artifact_json).ok()?;
    let entry = root["entry_module"].as_str()?;
    let module = &root["modules"][entry];
    let nodes_pool = &module["pools"]["nodes"];
    let mut nodes: NodeMap = std::collections::HashMap::new();
    if let Some(obj) = nodes_pool.as_object() {
        for (uid, node) in obj {
            nodes.insert(uid.clone(), node.clone());
        }
    }
    // 资产引用解析（ext_ref 常量 → 资产池内容——长/多行串内容寻址形态；
    // 于加载期就地替换，常量面单一取值路径）
    let assets: NodeMap = module["pools"]
        .get("assets")
        .and_then(|a| a.as_object())
        .map(|m| {
            m.iter()
                .map(|(k, v)| (k.clone(), v.clone()))
                .collect()
        })
        .unwrap_or_default();
    for n in nodes.values_mut() {
        if n.get("_type").and_then(|t| t.as_str()) == Some("IbConstant") {
            let v = n.get("value").cloned();
            if let Some(obj) = v.and_then(|v| v.as_object().cloned()) {
                if obj.get("_type").and_then(|t| t.as_str()) == Some("ext_ref") {
                    if let Some(auid) = obj.get("uid").and_then(|u| u.as_str()) {
                        if let Some(content) = assets.get(auid) {
                            n["value"] = content.clone();
                        }
                    }
                }
            }
        }
    }
    let root_uid = module["root_node_uid"].as_str()?;
    let n = nodes.get(root_uid)?;
    let body: Vec<Stmt> = uids_of(&n["body"]).iter().map(|u| stmt_of(u, &nodes)).collect();
    Some(Module {
        pos: pos_of(n),
        body,
    })
}

/// artifact JSON → 反序列化 AST 完整形态（含位置）。
pub fn deserialize_struct(artifact_json: &str) -> String {
    match deserialize_module(artifact_json) {
        Some(m) => m.dump(),
        None => String::new(),
    }
}

// --------------------------------------------------------------------------- //
// 符号池 + 侧表（node → symbol 解析）
// --------------------------------------------------------------------------- //
/// 符号（语义层输出——变量/函数/方法等，执行核心类型检查/错误报告/分发用）。
#[derive(Debug, Clone)]
pub struct Symbol {
    pub name: String,
    pub kind: String,
    pub type_uid: Option<String>,
}

/// artifact JSON → 符号表规范表示（node → symbol 解析，按 node_uid 排序）。
/// 消费完整 artifact 的 symbols 池 + node_to_symbol 侧表（执行核心的完整 artifact
/// 消费——不止 nodes 池）。None = 解析失败。
pub fn symbol_table(artifact_json: &str) -> Option<String> {
    let root: Value = serde_json::from_str(artifact_json).ok()?;
    let entry = root["entry_module"].as_str()?;
    let module = &root["modules"][entry];
    // symbols 池：uid → {name, kind, type_uid}
    let symbols_pool = &module["pools"]["symbols"];
    let mut symbols: std::collections::HashMap<String, Symbol> = std::collections::HashMap::new();
    if let Some(obj) = symbols_pool.as_object() {
        for (uid, s) in obj {
            symbols.insert(
                uid.clone(),
                Symbol {
                    name: s["name"].as_str().unwrap_or("").to_string(),
                    kind: s["kind"].as_str().unwrap_or("").to_string(),
                    type_uid: s["type_uid"].as_str().map(|s| s.to_string()),
                },
            );
        }
    }
    // node_to_symbol 侧表：node_uid → symbol_uid
    let nts = &module["side_tables"]["node_to_symbol"];
    let mut pairs: Vec<(String, String)> = Vec::new();
    if let Some(obj) = nts.as_object() {
        for (node_uid, sym_uid) in obj {
            if let Some(su) = sym_uid.as_str() {
                if let Some(sym) = symbols.get(su) {
                    pairs.push((node_uid.clone(), sym.name.clone()));
                }
            }
        }
    }
    pairs.sort();
    Some(
        pairs
            .iter()
            .map(|(n, s)| format!("{} -> {}", n, s))
            .collect::<Vec<_>>()
            .join("\n"),
    )
}

/// artifact JSON → 类型表规范表示（node → type 解析，按 node_uid 排序）。
/// 消费完整 artifact 的 types 池 + node_to_type 侧表（执行核心的完整 artifact
/// 消费——语义层类型输出）。None = 解析失败。
pub fn type_table(artifact_json: &str) -> Option<String> {
    let root: Value = serde_json::from_str(artifact_json).ok()?;
    let entry = root["entry_module"].as_str()?;
    let module = &root["modules"][entry];
    // types 池：uid → name
    let types_pool = &module["pools"]["types"];
    let mut types: std::collections::HashMap<String, String> = std::collections::HashMap::new();
    if let Some(obj) = types_pool.as_object() {
        for (uid, t) in obj {
            types.insert(uid.clone(), t["name"].as_str().unwrap_or("").to_string());
        }
    }
    // node_to_type 侧表：node_uid → type_uid
    let ntt = &module["side_tables"]["node_to_type"];
    let mut pairs: Vec<(String, String)> = Vec::new();
    if let Some(obj) = ntt.as_object() {
        for (node_uid, type_uid) in obj {
            if let Some(tu) = type_uid.as_str() {
                if let Some(tname) = types.get(tu) {
                    pairs.push((node_uid.clone(), tname.clone()));
                }
            }
        }
    }
    pairs.sort();
    Some(
        pairs
            .iter()
            .map(|(n, t)| format!("{} -> {}", n, t))
            .collect::<Vec<_>>()
            .join("\n"),
    )
}

/// 反序列化器处理的节点类型全集（⑦ 切换门路由判定面单一真相源：artifact
/// 节点类型 ⊆ 本集 = 数据面源[Rust 可执行]；LLM 面 15 节点不在此集 =
/// Python 语义宿主）。含 build_node 分发表节点 + arg/alias 内联消费节点
/// [IbArg/IbAlias——FunctionDef args / ImportFrom names 经独立 builder 消费，
/// 池内节点不经 build_node]。
pub fn node_types() -> Vec<&'static str> {
    vec![
        // 语句
        "IbAssign", "IbAugAssign", "IbExprStmt", "IbIf", "IbFor", "IbFunctionDef",
        "IbReturn", "IbBreak", "IbContinue", "IbPass", "IbImport", "IbImportFrom",
        "IbWhile", "IbTry", "IbClassDef", "IbGlobalStmt", "IbNonlocalStmt",
        "IbRaise", "IbSwitch", "IbCase",
        // 内联消费（池节点——arg_of / alias 字段 builder）
        "IbArg", "IbAlias",
        // 表达式
        "IbConstant", "IbName", "IbBinOp", "IbUnaryOp", "IbBoolOp", "IbCompare",
        "IbCall", "IbListExpr", "IbTuple", "IbDict", "IbAttribute", "IbSubscript",
        "IbSlice", "IbIfExp", "IbLambdaExpr", "IbTypeAnnotatedExpr",
        // 容器/根
        "IbModule",
    ]
}
