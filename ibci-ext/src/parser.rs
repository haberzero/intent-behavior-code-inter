//! ibci-ext Rust parser——IBC token 流 → AST（对齐 Python `core/compiler/parser`）。
//!
//! 移植范围（本增量）：语料面完整语句/表达式 + **位置跟踪对齐**——
//!   语句：Assign / ExprStmt / If[elif 链] / For / FunctionDef[typed args + returns] /
//!         Return / Break / Continue / Pass
//!   表达式：Constant / Name / BinOp[+ - * / // % **] / UnaryOp / Compare / Call /
//!           List / Dict / Attribute / Subscript
//!   位置：每节点 (lineno, col_offset, end_lineno, end_col_offset) 对齐 Python
//!         parser 的 `_loc`（start token 的 line/col + end token 的 end_line/end_col；
//!         合成 token[DEDENT/EOF/NEWLINE/INDENT] end=(0,0)；IbModule end=None）。
//! AST 级差分门：Rust AST 完整形态（含位置）== Python AST 完整形态（`tests/
//! diff_harness/ast_dump.py` include_positions=True 参考）。后续增量 = 语义层 +
//! 剩余语句/表达式（while/try/lambda/三元/复合类型注解/class）。

// AST 类型含后续增量将用的变体/方法
#![allow(dead_code)]

use crate::lexer::{lex, Token, TokenType};

// --------------------------------------------------------------------------- //
// 位置（对齐 Python IbASTNode 的 lineno/col_offset/end_lineno/end_col_offset）
// --------------------------------------------------------------------------- //
#[derive(Debug, Clone, Copy)]
pub struct Pos {
    pub lineno: i64,
    pub col_offset: i64,
    pub end_lineno: Option<i64>,
    pub end_col_offset: Option<i64>,
}

impl Pos {
    /// 从 token 取完整位置（line/col + end_line/end_col）。
    fn from_token(t: &Token) -> Pos {
        Pos {
            lineno: t.line as i64,
            col_offset: t.column as i64,
            end_lineno: Some(t.end_line as i64),
            end_col_offset: Some(t.end_column as i64),
        }
    }
    /// 合成模块位置（IbModule：(0,0,None,None)）。
    pub fn module() -> Pos {
        Pos {
            lineno: 0,
            col_offset: 0,
            end_lineno: None,
            end_col_offset: None,
        }
    }
    /// 起 token 的 line/col + 止 (end_line/end_col) 位置。
    fn from_start_end(start: &Token, end_line: i64, end_col: i64) -> Pos {
        Pos {
            lineno: start.line as i64,
            col_offset: start.column as i64,
            end_lineno: Some(end_line),
            end_col_offset: Some(end_col),
        }
    }
    /// 合成块位置（If/For/FunctionDef：start=keyword，end=DEDENT=(0,0)）。
    fn block(start: &Token) -> Pos {
        Pos {
            lineno: start.line as i64,
            col_offset: start.column as i64,
            end_lineno: Some(0),
            end_col_offset: Some(0),
        }
    }
    /// dumper 位置前缀：`lineno=..., col_offset=..., end_lineno=..., end_col_offset=...`。
    fn prefix(&self) -> String {
        let end_line = match self.end_lineno {
            Some(v) => v.to_string(),
            None => "None".to_string(),
        };
        let end_col = match self.end_col_offset {
            Some(v) => v.to_string(),
            None => "None".to_string(),
        };
        format!(
            "lineno={}, col_offset={}, end_lineno={}, end_col_offset={}",
            self.lineno, self.col_offset, end_line, end_col
        )
    }
}

// --------------------------------------------------------------------------- //
// AST 类型（对齐 core/kernel/ast.py 的节点子集 + 位置）
// --------------------------------------------------------------------------- //
#[derive(Debug, Clone)]
pub enum ConstVal {
    Int(i64),
    Float(f64),
    Str(String),
    Bool(bool),
    None_,
}

impl ConstVal {
    fn dump(&self) -> String {
        match self {
            ConstVal::Int(i) => i.to_string(),
            ConstVal::Float(f) => {
                let fv = *f;
                if fv.fract() == 0.0 {
                    format!("{}.0", fv as i64)
                } else {
                    format!("{}", fv)
                }
            }
            ConstVal::Str(s) => format!("'{}'", s.replace('\'', "\\'")),
            ConstVal::Bool(b) => if *b { "True".into() } else { "False".into() },
            ConstVal::None_ => "None".into(),
        }
    }
}

#[derive(Debug, Clone)]
pub enum Expr {
    Constant { pos: Pos, value: ConstVal },
    Name { pos: Pos, id: String, ctx: String },
    BinOp { pos: Pos, left: Box<Expr>, op: String, right: Box<Expr> },
    UnaryOp { pos: Pos, op: String, operand: Box<Expr> },
    BoolOp { pos: Pos, op: String, values: Vec<Expr> },
    Compare {
        pos: Pos,
        left: Box<Expr>,
        ops: Vec<String>,
        comparators: Vec<Expr>,
    },
    Call { pos: Pos, func: Box<Expr>, args: Vec<Expr> },
    List { pos: Pos, elts: Vec<Expr>, ctx: String },
    Dict { pos: Pos, keys: Vec<Expr>, values: Vec<Expr> },
    Attribute { pos: Pos, value: Box<Expr>, attr: String, ctx: String },
    Subscript { pos: Pos, value: Box<Expr>, slice: Box<Expr>, ctx: String },
    IfExp { pos: Pos, test: Box<Expr>, body: Box<Expr>, orelse: Box<Expr> },
    Lambda {
        pos: Pos,
        params: Vec<Arg>,
        body: Box<Expr>,
        capture_mode: String,
        // Box 断环（Expr::Lambda → Option<Expr> 递归）
        returns: Option<Box<Expr>>,
    },
    Tuple { pos: Pos, elts: Vec<Expr>, ctx: String },
    Slice {
        pos: Pos,
        lower: Option<Box<Expr>>,
        upper: Option<Box<Expr>>,
        step: Option<Box<Expr>>,
    },
    /// 类型注解表达式（声明面：`int x = 1` 的 target = Name(Store) + annotation
    /// = 类型节点；运行时 = 纯赋值，注解仅类型/编译期语义）。
    TypeAnnotatedExpr {
        pos: Pos,
        target: Box<Expr>,
        annotation: Box<Expr>,
    },
}

impl Expr {
    fn dump(&self) -> String {
        match self {
            Expr::Constant { pos, value } => {
                format!("IbConstant({}, value={})", pos.prefix(), value.dump())
            }
            Expr::Name { pos, id, ctx } => {
                format!("IbName({}, id='{}', ctx='{}')", pos.prefix(), id, ctx)
            }
            Expr::TypeAnnotatedExpr { pos, target, annotation } => {
                format!(
                    "IbTypeAnnotatedExpr({}, target={}, annotation={})",
                    pos.prefix(),
                    target.dump(),
                    annotation.dump()
                )
            }
            Expr::BinOp { pos, left, op, right } => format!(
                "IbBinOp({}, left={}, op='{}', right={})",
                pos.prefix(),
                left.dump(),
                op,
                right.dump()
            ),
            Expr::UnaryOp { pos, op, operand } => {
                format!("IbUnaryOp({}, op='{}', operand={})", pos.prefix(), op, operand.dump())
            }
            Expr::BoolOp { pos, op, values } => {
                let vals: Vec<String> = values.iter().map(|v| v.dump()).collect();
                format!(
                    "IbBoolOp({}, op='{}', values=[{}])",
                    pos.prefix(),
                    op,
                    vals.join(", ")
                )
            }
            Expr::Compare { pos, left, ops, comparators } => {
                let ops_str: Vec<String> = ops.iter().map(|o| format!("'{}'", o)).collect();
                let comp_str: Vec<String> = comparators.iter().map(|c| c.dump()).collect();
                format!(
                    "IbCompare({}, left={}, ops=[{}], comparators=[{}])",
                    pos.prefix(),
                    left.dump(),
                    ops_str.join(", "),
                    comp_str.join(", ")
                )
            }
            Expr::Call { pos, func, args } => {
                let args_str: Vec<String> = args.iter().map(|a| a.dump()).collect();
                format!(
                    "IbCall({}, func={}, args=[{}], keywords=[])",
                    pos.prefix(),
                    func.dump(),
                    args_str.join(", ")
                )
            }
            Expr::List { pos, elts, ctx } => {
                let elts_str: Vec<String> = elts.iter().map(|e| e.dump()).collect();
                format!(
                    "IbListExpr({}, elts=[{}], ctx='{}')",
                    pos.prefix(),
                    elts_str.join(", "),
                    ctx
                )
            }
            Expr::Dict { pos, keys, values } => {
                let keys_str: Vec<String> = keys.iter().map(|k| k.dump()).collect();
                let vals_str: Vec<String> = values.iter().map(|v| v.dump()).collect();
                format!(
                    "IbDict({}, keys=[{}], values=[{}])",
                    pos.prefix(),
                    keys_str.join(", "),
                    vals_str.join(", ")
                )
            }
            Expr::Attribute { pos, value, attr, ctx } => {
                format!(
                    "IbAttribute({}, value={}, attr='{}', ctx='{}')",
                    pos.prefix(),
                    value.dump(),
                    attr,
                    ctx
                )
            }
            Expr::Subscript { pos, value, slice, ctx } => {
                format!(
                    "IbSubscript({}, value={}, slice={}, ctx='{}')",
                    pos.prefix(),
                    value.dump(),
                    slice.dump(),
                    ctx
                )
            }
            Expr::IfExp { pos, test, body, orelse } => {
                format!(
                    "IbIfExp({}, test={}, body={}, orelse={})",
                    pos.prefix(),
                    test.dump(),
                    body.dump(),
                    orelse.dump()
                )
            }
            Expr::Lambda { pos, params, body, capture_mode, returns } => {
                let p: Vec<String> = params.iter().map(|a| a.dump()).collect();
                let r = match returns {
                    Some(r) => r.dump(),
                    None => "None".to_string(),
                };
                format!(
                    "IbLambdaExpr({}, params=[{}], body={}, capture_mode='{}', \
                     returns={}, free_vars=[])",
                    pos.prefix(),
                    p.join(", "),
                    body.dump(),
                    capture_mode,
                    r
                )
            }
            Expr::Tuple { pos, elts, ctx } => {
                let e: Vec<String> = elts.iter().map(|x| x.dump()).collect();
                format!("IbTuple({}, elts=[{}], ctx='{}')", pos.prefix(), e.join(", "), ctx)
            }
            Expr::Slice { pos, lower, upper, step } => {
                let l = lower.as_ref().map(|x| x.dump()).unwrap_or_else(|| "None".into());
                let u = upper.as_ref().map(|x| x.dump()).unwrap_or_else(|| "None".into());
                let s = step.as_ref().map(|x| x.dump()).unwrap_or_else(|| "None".into());
                format!("IbSlice({}, lower={}, upper={}, step={})", pos.prefix(), l, u, s)
            }
        }
    }
}

#[derive(Debug, Clone)]
pub struct Arg {
    pub pos: Pos,
    pub arg: String,
    // Box 断环（Expr::Lambda → Vec<Arg> → Option<Expr> 递归）
    pub annotation: Option<Box<Expr>>,
    pub default: Option<Box<Expr>>,
    pub kind: String,
}

impl Arg {
    fn dump(&self) -> String {
        let ann = match &self.annotation {
            Some(a) => a.dump(),
            None => "None".to_string(),
        };
        let def = match &self.default {
            Some(d) => d.dump(),
            None => "None".to_string(),
        };
        format!(
            "IbArg({}, arg='{}', annotation={}, default={}, kind='{}')",
            self.pos.prefix(),
            self.arg,
            ann,
            def,
            self.kind
        )
    }
}

#[derive(Debug, Clone)]
pub struct Alias {
    pub pos: Pos,
    pub name: String,
    pub asname: Option<String>,
}

impl Alias {
    fn dump(&self) -> String {
        let asname = match &self.asname {
            Some(a) => format!("'{}'", a),
            None => "None".to_string(),
        };
        format!(
            "IbAlias({}, name='{}', asname={})",
            self.pos.prefix(),
            self.name,
            asname
        )
    }
}

#[derive(Debug, Clone)]
pub enum Stmt {
    Assign { pos: Pos, targets: Vec<Expr>, value: Option<Expr> },
    AugAssign { pos: Pos, target: Expr, op: String, value: Expr },
    ExprStmt { pos: Pos, value: Expr },
    If { pos: Pos, test: Expr, body: Vec<Stmt>, orelse: Vec<Stmt> },
    For { pos: Pos, target: Expr, iter: Expr, body: Vec<Stmt>, orelse: Vec<Stmt> },
    FunctionDef {
        pos: Pos,
        name: String,
        args: Vec<Arg>,
        body: Vec<Stmt>,
        returns: Option<Expr>,
    },
    Return { pos: Pos, value: Option<Expr> },
    Break { pos: Pos },
    Continue { pos: Pos },
    Pass { pos: Pos },
    Import { pos: Pos, names: Vec<Alias> },
    FromImport { pos: Pos, module: String, names: Vec<Alias> },
    While { pos: Pos, test: Expr, body: Vec<Stmt>, orelse: Vec<Stmt> },
    Try {
        pos: Pos,
        body: Vec<Stmt>,
        handlers: Vec<ExceptHandler>,
        orelse: Vec<Stmt>,
        finalbody: Vec<Stmt>,
    },
    ClassDef {
        pos: Pos,
        name: String,
        body: Vec<Stmt>,
        fields: Vec<Stmt>,
        methods: Vec<Stmt>,
    },
    Global { pos: Pos, names: Vec<String> },
    Nonlocal { pos: Pos, names: Vec<String> },
    Raise { pos: Pos, exc: Option<Expr> },
    Switch { pos: Pos, test: Expr, cases: Vec<Case> },
}

/// switch 的 case 块（对齐 IbCase：pattern[None = default] / body）。
#[derive(Debug, Clone)]
pub struct Case {
    pub pos: Pos,
    pub pattern: Option<Expr>,
    pub body: Vec<Stmt>,
}

/// try 的 except 处理块（对齐 IbExceptHandler：type / name / body）。
#[derive(Debug, Clone)]
pub struct ExceptHandler {
    pub pos: Pos,
    pub exc_type: Option<Expr>,
    pub name: Option<String>,
    pub body: Vec<Stmt>,
}

impl ExceptHandler {
    fn dump(&self) -> String {
        let ty = match &self.exc_type {
            Some(t) => t.dump(),
            None => "None".to_string(),
        };
        let nm = match &self.name {
            Some(n) => format!("'{}'", n),
            None => "None".to_string(),
        };
        let b: Vec<String> = self.body.iter().map(|s| s.dump()).collect();
        format!(
            "IbExceptHandler({}, type={}, name={}, body=[{}])",
            self.pos.prefix(),
            ty,
            nm,
            b.join(", ")
        )
    }
}

impl Stmt {
    fn dump(&self) -> String {
        match self {
            Stmt::Assign { pos, targets, value } => {
                let t: Vec<String> = targets.iter().map(|x| x.dump()).collect();
                let v = match value {
                    Some(v) => v.dump(),
                    None => "None".to_string(),
                };
                format!(
                    "IbAssign({}, targets=[{}], value={}, llmexcept_handler=None)",
                    pos.prefix(),
                    t.join(", "),
                    v
                )
            }
            Stmt::AugAssign { pos, target, op, value } => {
                format!(
                    "IbAugAssign({}, target={}, op='{}', value={})",
                    pos.prefix(),
                    target.dump(),
                    op,
                    value.dump()
                )
            }
            Stmt::ExprStmt { pos, value } => {
                format!(
                    "IbExprStmt({}, value={}, llmexcept_handler=None)",
                    pos.prefix(),
                    value.dump()
                )
            }
            Stmt::If { pos, test, body, orelse } => {
                let b: Vec<String> = body.iter().map(|s| s.dump()).collect();
                let o: Vec<String> = orelse.iter().map(|s| s.dump()).collect();
                format!(
                    "IbIf({}, test={}, body=[{}], orelse=[{}], llmexcept_handler=None)",
                    pos.prefix(),
                    test.dump(),
                    b.join(", "),
                    o.join(", ")
                )
            }
            Stmt::For { pos, target, iter, body, orelse } => {
                let b: Vec<String> = body.iter().map(|s| s.dump()).collect();
                let o: Vec<String> = orelse.iter().map(|s| s.dump()).collect();
                format!(
                    "IbFor({}, target={}, iter={}, body=[{}], orelse=[{}], \
                     llmexcept_handler=None)",
                    pos.prefix(),
                    target.dump(),
                    iter.dump(),
                    b.join(", "),
                    o.join(", ")
                )
            }
            Stmt::FunctionDef { pos, name, args, body, returns } => {
                let a: Vec<String> = args.iter().map(|x| x.dump()).collect();
                let b: Vec<String> = body.iter().map(|s| s.dump()).collect();
                let r = match returns {
                    Some(r) => r.dump(),
                    None => "None".to_string(),
                };
                format!(
                    "IbFunctionDef({}, name='{}', args=[{}], body=[{}], returns={}, \
                     type_params=[], type_param_bounds={{}}, free_vars=[], \
                     is_generator=False, type_param_uids=[])",
                    pos.prefix(),
                    name,
                    a.join(", "),
                    b.join(", "),
                    r
                )
            }
            Stmt::Return { pos, value } => {
                let v = match value {
                    Some(v) => v.dump(),
                    None => "None".to_string(),
                };
                format!("IbReturn({}, value={})", pos.prefix(), v)
            }
            Stmt::Break { pos } => format!("IbBreak({})", pos.prefix()),
            Stmt::Continue { pos } => format!("IbContinue({})", pos.prefix()),
            Stmt::Pass { pos } => format!("IbPass({})", pos.prefix()),
            Stmt::Import { pos, names } => {
                let names_str: Vec<String> = names.iter().map(|n| n.dump()).collect();
                format!("IbImport({}, names=[{}])", pos.prefix(), names_str.join(", "))
            }
            Stmt::FromImport { pos, module, names } => {
                let names_str: Vec<String> = names.iter().map(|n| n.dump()).collect();
                format!(
                    "IbImportFrom({}, module='{}', names=[{}], level=0)",
                    pos.prefix(),
                    module,
                    names_str.join(", ")
                )
            }
            Stmt::While { pos, test, body, orelse } => {
                let b: Vec<String> = body.iter().map(|s| s.dump()).collect();
                let o: Vec<String> = orelse.iter().map(|s| s.dump()).collect();
                format!(
                    "IbWhile({}, test={}, body=[{}], orelse=[{}], \
                     llmexcept_handler=None)",
                    pos.prefix(),
                    test.dump(),
                    b.join(", "),
                    o.join(", ")
                )
            }
            Stmt::Try { pos, body, handlers, orelse, finalbody } => {
                let b: Vec<String> = body.iter().map(|s| s.dump()).collect();
                let h: Vec<String> = handlers.iter().map(|x| x.dump()).collect();
                let o: Vec<String> = orelse.iter().map(|s| s.dump()).collect();
                let f: Vec<String> = finalbody.iter().map(|s| s.dump()).collect();
                format!(
                    "IbTry({}, body=[{}], handlers=[{}], orelse=[{}], \
                     finalbody=[{}])",
                    pos.prefix(),
                    b.join(", "),
                    h.join(", "),
                    o.join(", "),
                    f.join(", ")
                )
            }
            Stmt::ClassDef { pos, name, body, fields, methods } => {
                let b: Vec<String> = body.iter().map(|s| s.dump()).collect();
                let f: Vec<String> = fields.iter().map(|s| s.dump()).collect();
                let m: Vec<String> = methods.iter().map(|s| s.dump()).collect();
                format!(
                    "IbClassDef({}, name='{}', body=[{}], parent=None, \
                     parent_args=[], type_params=[], type_param_bounds={{}}, \
                     implements=[], implements_args={{}}, methods=[{}], \
                     fields=[{}])",
                    pos.prefix(),
                    name,
                    b.join(", "),
                    m.join(", "),
                    f.join(", ")
                )
            }
            Stmt::Global { pos, names } => {
                let n: Vec<String> = names.iter().map(|x| format!("'{}'", x)).collect();
                format!("IbGlobalStmt({}, names=[{}])", pos.prefix(), n.join(", "))
            }
            Stmt::Nonlocal { pos, names } => {
                let n: Vec<String> = names.iter().map(|x| format!("'{}'", x)).collect();
                format!("IbNonlocalStmt({}, names=[{}])", pos.prefix(), n.join(", "))
            }
            Stmt::Raise { pos, exc } => {
                let e = match exc {
                    Some(e) => e.dump(),
                    None => "None".to_string(),
                };
                format!("IbRaise({}, exc={})", pos.prefix(), e)
            }
            Stmt::Switch { pos, test, cases } => {
                let c: Vec<String> = cases.iter().map(case_dump).collect();
                format!(
                    "IbSwitch({}, test={}, cases=[{}], llmexcept_handler=None)",
                    pos.prefix(),
                    test.dump(),
                    c.join(", ")
                )
            }
        }
    }
}

/// IbCase 节点 dump（AST 差分面——同 Python AST dump 约定）。
fn case_dump(c: &Case) -> String {
    let p = match &c.pattern {
        Some(p) => p.dump(),
        None => "None".to_string(),
    };
    let b: Vec<String> = c.body.iter().map(|s| s.dump()).collect();
    format!(
        "IbCase({}, pattern={}, body=[{}])",
        c.pos.prefix(),
        p,
        b.join(", ")
    )
}

#[derive(Debug, Clone)]
pub struct Module {
    pub pos: Pos,
    pub body: Vec<Stmt>,
}

impl Module {
    pub fn dump(&self) -> String {
        let b: Vec<String> = self.body.iter().map(|s| s.dump()).collect();
        format!(
            "IbModule({}, body=[{}], file_path=None)",
            self.pos.prefix(),
            b.join(", ")
        )
    }
}

// --------------------------------------------------------------------------- //
// Parser（递归下降——语料面完整语句/表达式 + 位置跟踪）
// --------------------------------------------------------------------------- //
struct Parser {
    tokens: Vec<Token>,
    pos: usize,
}

impl Parser {
    fn new(tokens: Vec<Token>) -> Self {
        Parser { tokens, pos: 0 }
    }
    fn peek(&self) -> &Token {
        if self.pos < self.tokens.len() {
            &self.tokens[self.pos]
        } else {
            self.tokens.last().unwrap()
        }
    }
    fn at(&self, ty: TokenType) -> bool {
        self.peek().type_ == ty
    }
    fn advance(&mut self) -> Token {
        let t = self.peek().clone();
        if self.pos < self.tokens.len() {
            self.pos += 1;
        }
        t
    }
    fn expect(&mut self, ty: TokenType) {
        if self.at(ty) {
            self.advance();
        }
    }
    fn skip_newlines(&mut self) {
        while self.at(TokenType::Newline) {
            self.advance();
        }
    }

    fn parse_module(&mut self) -> Module {
        let mut body: Vec<Stmt> = Vec::new();
        self.skip_newlines();
        while !self.at(TokenType::Eof) {
            let stmt = self.parse_stmt();
            body.push(stmt);
            self.skip_newlines();
        }
        Module {
            pos: Pos::module(),
            body,
        }
    }

    fn parse_stmt(&mut self) -> Stmt {
        match self.peek().type_ {
            TokenType::If => self.parse_if(),
            TokenType::For => self.parse_for(),
            TokenType::Func => self.parse_function_def(),
            TokenType::While => self.parse_while(),
            TokenType::Try => self.parse_try(),
            TokenType::Class => self.parse_class(),
            TokenType::Return => {
                let kw = self.advance(); // RETURN
                let value = if self.is_stmt_end() {
                    None
                } else {
                    Some(self.parse_expr())
                };
                Stmt::Return {
                    pos: Pos::from_token(&kw),
                    value,
                }
            }
            TokenType::Break => {
                let kw = self.advance();
                Stmt::Break { pos: Pos::from_token(&kw) }
            }
            TokenType::Continue => {
                let kw = self.advance();
                Stmt::Continue { pos: Pos::from_token(&kw) }
            }
            TokenType::Pass => {
                let kw = self.advance();
                Stmt::Pass { pos: Pos::from_token(&kw) }
            }
            TokenType::Import => {
                // import X [as Y]：Alias{name, asname}（位置 = name 起 → asname/name 止）
                let kw = self.advance(); // IMPORT
                let mut names = Vec::new();
                loop {
                    let name_tok = self.advance(); // Identifier
                    let (asname, end_tok) = if self.at(TokenType::As) {
                        self.advance(); // AS
                        let a = self.advance(); // asname Identifier
                        (Some(a.value.clone()), a)
                    } else {
                        (None, name_tok.clone())
                    };
                    names.push(Alias {
                        pos: Pos {
                            lineno: name_tok.line as i64,
                            col_offset: name_tok.column as i64,
                            end_lineno: Some(end_tok.end_line as i64),
                            end_col_offset: Some(end_tok.end_column as i64),
                        },
                        name: name_tok.value,
                        asname,
                    });
                    // 多模块（import a, b）
                    if self.at(TokenType::Comma) {
                        self.advance();
                        continue;
                    }
                    break;
                }
                Stmt::Import { pos: Pos::from_token(&kw), names }
            }
            TokenType::From => {
                // from X import Y [as Z], ...
                let kw = self.advance(); // FROM
                let module = self.advance().value; // X（module 名）
                self.advance(); // IMPORT
                let mut names = Vec::new();
                loop {
                    let name_tok = self.advance(); // Y（Identifier）
                    let (asname, end_tok) = if self.at(TokenType::As) {
                        self.advance(); // AS
                        let a = self.advance(); // Z
                        (Some(a.value.clone()), a)
                    } else {
                        (None, name_tok.clone())
                    };
                    names.push(Alias {
                        pos: Pos {
                            lineno: name_tok.line as i64,
                            col_offset: name_tok.column as i64,
                            end_lineno: Some(end_tok.end_line as i64),
                            end_col_offset: Some(end_tok.end_column as i64),
                        },
                        name: name_tok.value,
                        asname,
                    });
                    if self.at(TokenType::Comma) {
                        self.advance();
                        continue;
                    }
                    break;
                }
                Stmt::FromImport { pos: Pos::from_token(&kw), module, names }
            }
            TokenType::Global | TokenType::Nonlocal => {
                // global/nonlocal x[, y]（编译期语义——运行时 no-op）
                let kw = self.advance();
                let is_global = kw.type_ == TokenType::Global;
                let mut names = Vec::new();
                loop {
                    let t = self.advance(); // Identifier
                    names.push(t.value);
                    if !self.at(TokenType::Comma) {
                        break;
                    }
                    self.advance();
                }
                if is_global {
                    Stmt::Global { pos: Pos::from_token(&kw), names }
                } else {
                    Stmt::Nonlocal { pos: Pos::from_token(&kw), names }
                }
            }
            TokenType::Raise => {
                // raise <exc>（IBCI：exc 必在——裸 raise = 编译错误[Python
                // 实证]；位置 = raise 关键字[含 end]——Python 位置约定实证）
                let kw = self.advance();
                let exc = if self.is_stmt_end() {
                    None
                } else {
                    Some(self.parse_expr())
                };
                Stmt::Raise { pos: Pos::from_token(&kw), exc }
            }
            TokenType::Switch => self.parse_switch(),
            TokenType::Auto => {
                // auto x = v（类型推导声明——annotation = Name(auto)）
                self.parse_declaration_auto()
            }
            TokenType::Fn => {
                // fn f = v（可调用声明——annotation = Name(fn)；符号/绑定语义同
                // auto[值推导]；可调用签名 fn[(...) -> ...] = IbCallableType
                // [登记缺口——语料面不含]）
                let kw = self.advance();
                let kw_pos = Pos::from_token(&kw);
                let annotation = Expr::Name {
                    pos: kw_pos.clone(),
                    id: "fn".to_string(),
                    ctx: "Load".to_string(),
                };
                self.finish_declaration(kw_pos, annotation)
            }
            TokenType::Lparen => {
                // 括号元组解包声明：(int x, int y) = t（否则 = 元组表达式语句）
                if self.is_typed_tuple_declaration() {
                    return self.parse_tuple_declaration();
                }
                let value = self.parse_expr();
                Stmt::ExprStmt {
                    pos: expr_pos(&value),
                    value,
                }
            }
            TokenType::Identifier => {
                // 声明面前瞻：TYPE x = v / TYPE x: TYPE2 = v（TYPE = 标识符[可带
                // 泛型括号]，后随变量名 + = / :）
                if self.is_var_declaration() {
                    return self.parse_declaration_identifier();
                }
                // 回退式前瞻：解析 target（Name 或 Subscript/Attribute），若后随
                // ASSIGN = Assign；AUG（+= / -=）= AugAssign；否则回退按 ExprStmt。
                let save = self.pos;
                let target = self.parse_assign_target();
                if self.at(TokenType::Assign) {
                    self.advance(); // =
                    let value = self.parse_expr();
                    // IbAssign 位置 = target 的起/止（对齐 Python——end = target.end）
                    let tpos = expr_pos(&target);
                    return Stmt::Assign {
                        pos: tpos,
                        targets: vec![target],
                        value: Some(value),
                    };
                }
                // 复合赋值（x += 1 / x -= 1）
                if let (true, op) =
                    (matches!(self.peek().type_, TokenType::PlusAssign | TokenType::MinusAssign),
                     match self.peek().type_ {
                         TokenType::PlusAssign => "+=",
                         TokenType::MinusAssign => "-=",
                         _ => "",
                     })
                {
                    self.advance(); // += / -=
                    let value = self.parse_expr();
                    let tpos = expr_pos(&target);
                    return Stmt::AugAssign {
                        pos: tpos,
                        target,
                        op: op.to_string(),
                        value,
                    };
                }
                self.pos = save; // 非 Assign/AugAssign → ExprStmt
                let value = self.parse_expr();
                Stmt::ExprStmt {
                    pos: expr_pos(&value),
                    value,
                }
            }
            _ => {
                let value = self.parse_expr();
                Stmt::ExprStmt {
                    pos: expr_pos(&value),
                    value,
                }
            }
        }
    }

    /// 声明面前瞻：TYPE [ [ typeargs ] ] x (= | :)（TYPE = 标识符[可带泛型
    /// 括号]；后随变量名 + Assign/Colon = 变量声明；否则 = 普通语句形态）。
    fn is_var_declaration(&mut self) -> bool {
        if !self.at(TokenType::Identifier) {
            return false;
        }
        let save = self.pos;
        self.advance(); // 类型名
        if self.at(TokenType::Lbracket) {
            // 泛型：消费至匹配 Rbracket
            let mut depth = 0;
            loop {
                match self.peek().type_ {
                    TokenType::Eof => {
                        self.pos = save;
                        return false;
                    }
                    TokenType::Lbracket => {
                        depth += 1;
                        self.advance();
                    }
                    TokenType::Rbracket => {
                        depth -= 1;
                        self.advance();
                        if depth == 0 {
                            break;
                        }
                    }
                    _ => {
                        self.advance();
                    }
                }
            }
        }
        // 变量名
        if !self.at(TokenType::Identifier) {
            self.pos = save;
            return false;
        }
        self.advance();
        // = / :（单声明）/ ,（裸列元组解包 int a, int b = t）
        let ok = self.at(TokenType::Assign)
            || self.at(TokenType::Colon)
            || self.at(TokenType::Comma);
        self.pos = save;
        ok
    }

    /// 类型注解（IDENT [ . IDENT ]* [ [ typearg, ... ] ]；多参 = IbTuple[ctx
    /// Load]；位置 = 类型名 token——泛型节点 end = 类型名 end，非括号跨度；点分
    /// 类型 = Attribute 链[mod.Type]）。
    fn parse_type_annotation(&mut self) -> Expr {
        let tok = self.advance(); // 类型名
        let ty_pos = Pos::from_token(&tok);
        let base = Expr::Name {
            pos: ty_pos.clone(),
            id: tok.value,
            ctx: "Load".to_string(),
        };
        // 点分类型：mod.Type
        let base = if self.at(TokenType::Dot) {
            let mut cur = Box::new(base);
            while self.at(TokenType::Dot) {
                self.advance();
                let m_tok = self.advance(); // 成员名
                cur = Box::new(Expr::Attribute {
                    pos: ty_pos.clone(),
                    value: cur,
                    attr: m_tok.value,
                    ctx: "Load".to_string(),
                });
            }
            *cur
        } else {
            base
        };
        self.parse_generic_annotation(base)
    }

    /// 既有类型名 token 后续接泛型括号（位置 = 类型名 token）。
    fn parse_generic_annotation(&mut self, base: Expr) -> Expr {
        let ty_pos = match &base {
            Expr::Name { pos, .. } => pos.clone(),
            _ => Pos::module(),
        };
        if !self.at(TokenType::Lbracket) {
            return base;
        }
        self.advance(); // [
        let mut elts = vec![self.parse_type_annotation()];
        while self.at(TokenType::Comma) {
            self.advance();
            elts.push(self.parse_type_annotation());
        }
        self.advance(); // ]
        let slice = if elts.len() == 1 {
            elts.pop().unwrap()
        } else {
            Expr::Tuple {
                pos: ty_pos.clone(),
                elts,
                ctx: "Load".to_string(),
            }
        };
        Expr::Subscript {
            pos: ty_pos,
            value: Box::new(base),
            slice: Box::new(slice),
            ctx: "Load".to_string(),
        }
    }

    /// 声明收尾（name + [=/: 注解] + 值 → Assign[TypeAnnotatedExpr target]；
    /// IbAssign 位置 = 类型起始 token，end = 0[Python 声明 Assign 位置约定]）。
    fn finish_declaration(
        &mut self,
        ty_pos: Pos,
        default_annotation: Expr,
    ) -> Stmt {
        let name_tok = self.advance(); // 变量名
        let annotation = if self.at(TokenType::Colon) {
            // 显式覆盖：auto x: int = 1（annotation = 冒号后类型）
            self.advance();
            self.parse_type_annotation()
        } else {
            default_annotation
        };
        self.expect(TokenType::Assign); // =
        let value = self.parse_expr();
        let store_name = Expr::Name {
            pos: Pos::from_token(&name_tok),
            id: name_tok.value,
            ctx: "Store".to_string(),
        };
        let annotated = Expr::TypeAnnotatedExpr {
            pos: ty_pos.clone(),
            target: Box::new(store_name),
            annotation: Box::new(annotation),
        };
        let mut apos = ty_pos;
        apos.end_lineno = Some(0);
        apos.end_col_offset = Some(0);
        Stmt::Assign {
            pos: apos,
            targets: vec![annotated],
            value: Some(value),
        }
    }

    /// 显式类型声明：int x = 1 / list[int] xs = ... / 裸列 int a, int b = t
    /// （入口 = is_var_declaration 已确认）。
    fn parse_declaration_identifier(&mut self) -> Stmt {
        let ty_tok = self.advance(); // 类型名
        let ty_pos = Pos::from_token(&ty_tok);
        let base = Expr::Name {
            pos: ty_pos.clone(),
            id: ty_tok.value,
            ctx: "Load".to_string(),
        };
        let first_ann = self.parse_generic_annotation(base);
        let name_tok = self.advance(); // 变量名
        // 裸列元组解包声明：int a, int b = t
        if self.at(TokenType::Comma) {
            let mut elts = vec![self.annotated_component(
                ty_pos.clone(),
                &name_tok,
                first_ann,
            )];
            while self.at(TokenType::Comma) {
                self.advance();
                let e_ty_tok = self.advance();
                let e_ty_pos = Pos::from_token(&e_ty_tok);
                let e_base = Expr::Name {
                    pos: e_ty_pos.clone(),
                    id: e_ty_tok.value,
                    ctx: "Load".to_string(),
                };
                let e_ann = self.parse_generic_annotation(e_base);
                let e_name_tok = self.advance();
                elts.push(self.annotated_component(
                    e_ty_pos,
                    &e_name_tok,
                    e_ann,
                ));
            }
            self.expect(TokenType::Assign);
            let value = self.parse_expr();
            let tuple = Expr::Tuple {
                pos: ty_pos.clone(),
                elts,
                ctx: "Store".to_string(),
            };
            return self.decl_assign(ty_pos, vec![tuple], value);
        }
        // 单变量声明（: TYPE2 显式覆盖 / = 值）
        let annotation = if self.at(TokenType::Colon) {
            self.advance();
            self.parse_type_annotation()
        } else {
            first_ann
        };
        self.expect(TokenType::Assign);
        let value = self.parse_expr();
        let store_name = Expr::Name {
            pos: Pos::from_token(&name_tok),
            id: name_tok.value,
            ctx: "Store".to_string(),
        };
        let annotated = Expr::TypeAnnotatedExpr {
            pos: ty_pos.clone(),
            target: Box::new(store_name),
            annotation: Box::new(annotation),
        };
        self.decl_assign(ty_pos, vec![annotated], value)
    }

    /// 解包分量（annotated 组件：pos = 分量类型 token）。
    fn annotated_component(&mut self, ty_pos: Pos, name_tok: &Token, ann: Expr) -> Expr {
        let store_name = Expr::Name {
            pos: Pos::from_token(name_tok),
            id: name_tok.value.clone(),
            ctx: "Store".to_string(),
        };
        Expr::TypeAnnotatedExpr {
            pos: ty_pos,
            target: Box::new(store_name),
            annotation: Box::new(ann),
        }
    }

    /// 声明 Assign 收尾（位置 = 类型起始 token，end = 0[Python 声明 Assign 位置
    /// 约定]）。
    fn decl_assign(&mut self, ty_pos: Pos, targets: Vec<Expr>, value: Expr) -> Stmt {
        let mut apos = ty_pos;
        apos.end_lineno = Some(0);
        apos.end_col_offset = Some(0);
        Stmt::Assign {
            pos: apos,
            targets,
            value: Some(value),
        }
    }

    /// 括号元组解包声明前瞻：( TYPE x [, TYPE y ...] ) = （组件 = 类型名 +
    /// 可选泛型 + 变量名）。
    fn is_typed_tuple_declaration(&mut self) -> bool {
        if !self.at(TokenType::Lparen) {
            return false;
        }
        let save = self.pos;
        self.advance(); // (
        let mut depth = 0;
        loop {
            if !self.at(TokenType::Identifier) {
                self.pos = save;
                return false;
            }
            self.advance(); // 组件类型名
            if self.at(TokenType::Lbracket) {
                // 泛型括号深度
                self.advance();
                depth = 1;
                while depth > 0 {
                    match self.peek().type_ {
                        TokenType::Eof => {
                            self.pos = save;
                            return false;
                        }
                        TokenType::Lbracket => {
                            depth += 1;
                            self.advance();
                        }
                        TokenType::Rbracket => {
                            depth -= 1;
                            self.advance();
                        }
                        _ => {
                            self.advance();
                        }
                    }
                }
            }
            if !self.at(TokenType::Identifier) {
                self.pos = save;
                return false;
            }
            self.advance(); // 组件变量名
            if self.at(TokenType::Comma) {
                self.advance();
                continue;
            }
            if !self.at(TokenType::Rparen) {
                self.pos = save;
                return false;
            }
            self.advance(); // )
            break;
        }
        let ok = self.at(TokenType::Assign);
        self.pos = save;
        ok
    }

    /// 括号元组解包声明：(int x, int y) = t（目标 IbTuple[ctx Store]，位置 =
    /// LPAREN token；Assign 位置 = LPAREN，end = 0）。
    fn parse_tuple_declaration(&mut self) -> Stmt {
        let lparen = self.advance(); // (
        let lpos = Pos::from_token(&lparen);
        let mut elts = Vec::new();
        loop {
            let ty_tok = self.advance(); // 组件类型名
            let ty_pos = Pos::from_token(&ty_tok);
            let base = Expr::Name {
                pos: ty_pos.clone(),
                id: ty_tok.value,
                ctx: "Load".to_string(),
            };
            let ann = self.parse_generic_annotation(base);
            let name_tok = self.advance(); // 组件变量名
            elts.push(self.annotated_component(ty_pos, &name_tok, ann));
            if self.at(TokenType::Comma) {
                self.advance();
                continue;
            }
            break;
        }
        self.advance(); // )
        self.expect(TokenType::Assign);
        let value = self.parse_expr();
        let tuple = Expr::Tuple {
            pos: lpos.clone(),
            elts,
            ctx: "Store".to_string(),
        };
        self.decl_assign(lpos, vec![tuple], value)
    }

    /// auto x = v（入口 = Auto token；annotation = Name(auto)）。
    fn parse_declaration_auto(&mut self) -> Stmt {
        let kw = self.advance(); // auto
        let kw_pos = Pos::from_token(&kw);
        let annotation = Expr::Name {
            pos: kw_pos.clone(),
            id: "auto".to_string(),
            ctx: "Load".to_string(),
        };
        self.finish_declaration(kw_pos, annotation)
    }

    /// switch <test>:\n    case <pattern>:\n    ...\n    default:\n    ...
    /// （匹配后自动跳出——无 fall-through；case/default = 独立缩进块）
    fn parse_switch(&mut self) -> Stmt {
        let kw = self.advance(); // SWITCH
        let test = self.parse_expr();
        self.expect(TokenType::Colon);
        self.skip_newlines();
        self.expect(TokenType::Indent); // switch 块
        self.skip_newlines();
        let mut cases = Vec::new();
        while self.at(TokenType::Case) || self.at(TokenType::Default) {
            let is_case = self.at(TokenType::Case);
            self.advance(); // CASE 或 DEFAULT
            // case <expr> = 有 pattern；default = 无 pattern
            let pattern = if is_case { Some(self.parse_expr()) } else { None };
            self.expect(TokenType::Colon);
            self.skip_newlines();
            let body = self.parse_body(); // case 体
            // IbCase 位置 = switch 关键字位置（Python 序列化器约定：case 节点
            // 复用 switch start_token，语料实证全部 case 同位置）
            cases.push(Case {
                pos: Pos::from_token(&kw),
                pattern,
                body,
            });
            self.skip_newlines();
        }
        self.expect(TokenType::Dedent); // switch 块结束
        Stmt::Switch {
            pos: Pos::block(&kw),
            test,
            cases,
        }
    }

    fn parse_if(&mut self) -> Stmt {
        let kw = self.advance(); // IF 或 ELIF
        let test = self.parse_expr();
        self.expect(TokenType::Colon);
        self.skip_newlines();
        let body = self.parse_body();
        let orelse = if self.at(TokenType::Elif) {
            vec![self.parse_if()]
        } else if self.at(TokenType::Else) {
            self.advance();
            self.expect(TokenType::Colon);
            self.skip_newlines();
            self.parse_body()
        } else {
            vec![]
        };
        Stmt::If {
            pos: Pos::block(&kw),
            test,
            body,
            orelse,
        }
    }

    fn parse_for(&mut self) -> Stmt {
        let kw = self.advance(); // FOR
        let target_tok = self.advance(); // target IDENTIFIER
        let target = Expr::Name {
            pos: Pos::from_token(&target_tok),
            id: target_tok.value,
            ctx: "Store".to_string(),
        };
        self.expect(TokenType::In);
        let iter = self.parse_expr();
        self.expect(TokenType::Colon);
        self.skip_newlines();
        let body = self.parse_body();
        let orelse = if self.at(TokenType::Else) {
            self.advance();
            self.expect(TokenType::Colon);
            self.skip_newlines();
            self.parse_body()
        } else {
            vec![]
        };
        Stmt::For {
            pos: Pos::block(&kw),
            target,
            iter,
            body,
            orelse,
        }
    }

    fn parse_while(&mut self) -> Stmt {
        let kw = self.advance(); // WHILE
        let test = self.parse_expr();
        self.expect(TokenType::Colon);
        self.skip_newlines();
        let body = self.parse_body();
        let orelse = if self.at(TokenType::Else) {
            self.advance();
            self.expect(TokenType::Colon);
            self.skip_newlines();
            self.parse_body()
        } else {
            vec![]
        };
        Stmt::While {
            pos: Pos::block(&kw),
            test,
            body,
            orelse,
        }
    }

    fn parse_try(&mut self) -> Stmt {
        let kw = self.advance(); // TRY
        self.expect(TokenType::Colon);
        self.skip_newlines();
        let body = self.parse_body();
        let mut handlers: Vec<ExceptHandler> = Vec::new();
        let mut orelse: Vec<Stmt> = Vec::new();
        let mut finalbody: Vec<Stmt> = Vec::new();
        // except / else / finally（同缩进层，DEDENT 后）
        while self.at(TokenType::Except)
            || self.at(TokenType::Else)
            || self.at(TokenType::Finally)
        {
            if self.at(TokenType::Except) {
                let ekw = self.advance(); // EXCEPT
                // 可选异常类型 + as name
                let mut exc_type = None;
                let mut name = None;
                if !self.at(TokenType::Colon) {
                    exc_type = Some(self.parse_expr());
                    if self.at(TokenType::As) {
                        self.advance();
                        name = Some(self.advance().value);
                    }
                }
                self.expect(TokenType::Colon);
                self.skip_newlines();
                let hbody = self.parse_body();
                handlers.push(ExceptHandler {
                    pos: Pos::from_token(&ekw),
                    exc_type,
                    name,
                    body: hbody,
                });
            } else if self.at(TokenType::Else) {
                self.advance();
                self.expect(TokenType::Colon);
                self.skip_newlines();
                orelse = self.parse_body();
            } else {
                self.advance(); // FINALLY
                self.expect(TokenType::Colon);
                self.skip_newlines();
                finalbody = self.parse_body();
            }
        }
        Stmt::Try {
            pos: Pos::from_token(&kw),
            body,
            handlers,
            orelse,
            finalbody,
        }
    }

    fn parse_class(&mut self) -> Stmt {
        let kw = self.advance(); // CLASS
        let name = self.advance().value; // IDENTIFIER
        self.expect(TokenType::Colon);
        self.skip_newlines();
        let body = self.parse_body();
        // fields = Assign 语句（类变量）；methods = FunctionDef 语句
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
        Stmt::ClassDef {
            pos: Pos::block(&kw),
            name,
            body,
            fields,
            methods,
        }
    }

    fn parse_function_def(&mut self) -> Stmt {
        let kw = self.advance(); // FUNC
        let name = self.advance().value; // IDENTIFIER
        self.expect(TokenType::Lparen);
        let mut args: Vec<Arg> = Vec::new();
        if !self.at(TokenType::Rparen) {
            loop {
                let ann_tok = self.advance();
                let annotation = Expr::Name {
                    pos: Pos::from_token(&ann_tok),
                    id: ann_tok.value,
                    ctx: "Load".to_string(),
                };
                let arg_tok = self.advance();
                let arg_name = arg_tok.value.clone();
                let default = if self.at(TokenType::Assign) {
                    self.advance();
                    Some(Box::new(self.parse_expr()))
                } else {
                    None
                };
                // IbArg 位置 = arg name 的起/止（对齐 Python——start = arg name）
                args.push(Arg {
                    pos: Pos::from_token(&arg_tok),
                    arg: arg_name,
                    annotation: Some(Box::new(annotation)),
                    default,
                    kind: "POSITIONAL_OR_KEYWORD".to_string(),
                });
                if self.at(TokenType::Comma) {
                    self.advance();
                } else {
                    break;
                }
            }
        }
        self.expect(TokenType::Rparen);
        let returns = if self.at(TokenType::Arrow) {
            self.advance();
            let ret_tok = self.advance();
            Some(Expr::Name {
                pos: Pos::from_token(&ret_tok),
                id: ret_tok.value,
                ctx: "Load".to_string(),
            })
        } else {
            None
        };
        self.expect(TokenType::Colon);
        self.skip_newlines();
        let body = self.parse_body();
        Stmt::FunctionDef {
            pos: Pos::block(&kw),
            name,
            args,
            body,
            returns,
        }
    }

    /// body：INDENT ... DEDENT（语句序列）。
    fn parse_body(&mut self) -> Vec<Stmt> {
        let mut body: Vec<Stmt> = Vec::new();
        self.expect(TokenType::Indent);
        self.skip_newlines();
        while !self.at(TokenType::Dedent) && !self.at(TokenType::Eof) {
            let stmt = self.parse_stmt();
            body.push(stmt);
            self.skip_newlines();
        }
        self.expect(TokenType::Dedent);
        body
    }

    fn is_stmt_end(&self) -> bool {
        matches!(
            self.peek().type_,
            TokenType::Newline | TokenType::Eof | TokenType::Dedent
        )
    }

    /// Assign target：Name 或 Subscript（d['c']）/ Attribute（obj.attr）。
    fn parse_assign_target(&mut self) -> Expr {
        let tok = self.advance(); // IDENTIFIER
        // 先捕获原始 line/col（避免 tok.value move 后借用 tok）
        let start_line = tok.line as i64;
        let start_col = tok.column as i64;
        let base_pos = Pos {
            lineno: start_line,
            col_offset: start_col,
            end_lineno: Some(tok.end_line as i64),
            end_col_offset: Some(tok.end_column as i64),
        };
        let base = Expr::Name {
            pos: base_pos,
            id: tok.value,
            ctx: "Load".to_string(),
        };
        if self.at(TokenType::Lbracket) {
            self.advance(); // [
            let slice = self.parse_expr();
            let rbr = self.advance(); // ]
            return Expr::Subscript {
                pos: Pos {
                    lineno: start_line,
                    col_offset: start_col,
                    end_lineno: Some(rbr.end_line as i64),
                    end_col_offset: Some(rbr.end_column as i64),
                },
                value: Box::new(base),
                slice: Box::new(slice),
                ctx: "Load".to_string(),
            };
        }
        if self.at(TokenType::Dot) {
            self.advance(); // .
            let attr = self.advance().value;
            return Expr::Attribute {
                pos: base_pos,
                value: Box::new(base),
                attr,
                ctx: "Load".to_string(),
            };
        }
        base
    }

    // ---- 表达式（递归下降 + 优先级 + 位置）---- //

    /// 最低优先级：三元（IbIfExp）——`body if test else orelse`。
    fn parse_expr(&mut self) -> Expr {
        let body = self.parse_or();
        if self.at(TokenType::If) {
            self.advance(); // IF
            let test = self.parse_or();
            self.expect(TokenType::Else);
            let orelse = self.parse_expr(); // 右结合（嵌套三元）
            // IbIfExp 位置 = start=body 的起，end=orelse 的止
            let bpos = expr_pos(&body);
            let opos = expr_pos(&orelse);
            return Expr::IfExp {
                pos: Pos {
                    lineno: bpos.lineno,
                    col_offset: bpos.col_offset,
                    end_lineno: opos.end_lineno,
                    end_col_offset: opos.end_col_offset,
                },
                test: Box::new(test),
                body: Box::new(body),
                orelse: Box::new(orelse),
            };
        }
        body
    }

    /// or 优先级（IbBoolOp op='or'，左结合）。
    fn parse_or(&mut self) -> Expr {
        let mut values = vec![self.parse_and()];
        while self.at(TokenType::Or) {
            self.advance();
            values.push(self.parse_and());
        }
        if values.len() == 1 {
            values.pop().unwrap()
        } else {
            Expr::BoolOp {
                pos: boolop_pos(&values),
                op: "or".to_string(),
                values,
            }
        }
    }

    /// and 优先级（IbBoolOp op='and'，左结合）。
    fn parse_and(&mut self) -> Expr {
        let mut values = vec![self.parse_not()];
        while self.at(TokenType::And) {
            self.advance();
            values.push(self.parse_not());
        }
        if values.len() == 1 {
            values.pop().unwrap()
        } else {
            Expr::BoolOp {
                pos: boolop_pos(&values),
                op: "and".to_string(),
                values,
            }
        }
    }

    /// not 优先级（IbUnaryOp op='not'，右结合）。
    fn parse_not(&mut self) -> Expr {
        if self.at(TokenType::Not) {
            let not_tok = self.advance(); // NOT
            let operand = self.parse_not(); // 右结合（not not x）
            // IbUnaryOp 位置 = op token 的起/止（对齐 Python）
            return Expr::UnaryOp {
                pos: Pos::from_token(&not_tok),
                op: "not".to_string(),
                operand: Box::new(operand),
            };
        }
        self.parse_compare()
    }

    /// 比较优先级。
    fn parse_compare(&mut self) -> Expr {
        let left = self.parse_additive();
        let (ops, comparators) = self.parse_compare_chain();
        if ops.is_empty() {
            left
        } else {
            // IbCompare 位置 = start=left 的起，end=最后一个 comparator 的止
            let lpos = expr_pos(&left);
            let end = match comparators.last() {
                Some(c) => expr_pos(c),
                None => lpos,
            };
            Expr::Compare {
                pos: Pos {
                    lineno: lpos.lineno,
                    col_offset: lpos.col_offset,
                    end_lineno: end.end_lineno,
                    end_col_offset: end.end_col_offset,
                },
                left: Box::new(left),
                ops,
                comparators,
            }
        }
    }

    fn parse_compare_chain(&mut self) -> (Vec<String>, Vec<Expr>) {
        let mut ops: Vec<String> = Vec::new();
        let mut comparators: Vec<Expr> = Vec::new();
        loop {
            let op = match self.peek().type_ {
                TokenType::Gt => ">",
                TokenType::Lt => "<",
                TokenType::Ge => ">=",
                TokenType::Le => "<=",
                TokenType::Eq => "==",
                TokenType::Ne => "!=",
                _ => break,
            };
            self.advance();
            let right = self.parse_additive();
            ops.push(op.to_string());
            comparators.push(right);
        }
        (ops, comparators)
    }

    fn parse_additive(&mut self) -> Expr {
        let mut left = self.parse_term();
        while matches!(self.peek().type_, TokenType::Plus | TokenType::Minus) {
            let op = self.advance();
            let right = self.parse_term();
            left = make_binop(left, op.value, right);
        }
        left
    }

    fn parse_term(&mut self) -> Expr {
        let mut left = self.parse_power();
        while matches!(
            self.peek().type_,
            TokenType::Star | TokenType::Slash | TokenType::FloorDiv | TokenType::Percent
        ) {
            let op = self.advance();
            let right = self.parse_power();
            left = make_binop(left, op.value, right);
        }
        left
    }

    fn parse_power(&mut self) -> Expr {
        let left = self.parse_unary();
        if self.at(TokenType::StarStar) {
            let op = self.advance();
            let right = self.parse_power();
            return make_binop(left, op.value, right);
        }
        left
    }

    fn parse_unary(&mut self) -> Expr {
        if matches!(self.peek().type_, TokenType::Minus | TokenType::Plus) {
            let op_tok = self.advance();
            let operand = Box::new(self.parse_unary());
            // IbUnaryOp 位置 = op token 的起/止（对齐 Python——end = op token.end，
            // 非 operand 的止）
            return Expr::UnaryOp {
                pos: Pos::from_token(&op_tok),
                op: op_tok.value,
                operand,
            };
        }
        self.parse_postfix()
    }

    fn parse_postfix(&mut self) -> Expr {
        let mut expr = self.parse_primary();
        loop {
            match self.peek().type_ {
                TokenType::Lparen => {
                    self.advance(); // (
                    let mut args: Vec<Expr> = Vec::new();
                    if !self.at(TokenType::Rparen) {
                        args.push(self.parse_expr());
                        while self.at(TokenType::Comma) {
                            self.advance();
                            args.push(self.parse_expr());
                        }
                    }
                    let rpar = self.advance(); // )
                    let func = expr;
                    let fpos = expr_pos(&func);
                    expr = Expr::Call {
                        pos: Pos {
                            lineno: fpos.lineno,
                            col_offset: fpos.col_offset,
                            end_lineno: Some(rpar.end_line as i64),
                            end_col_offset: Some(rpar.end_column as i64),
                        },
                        func: Box::new(func),
                        args,
                    };
                }
                TokenType::Dot => {
                    self.advance(); // .
                    let attr = self.advance().value;
                    let value = expr;
                    let vpos = expr_pos(&value);
                    expr = Expr::Attribute {
                        pos: vpos,
                        value: Box::new(value),
                        attr,
                        ctx: "Load".to_string(),
                    };
                }
                TokenType::Lbracket => {
                    self.advance(); // [
                    // lower 可能为空（xs[:2] 直接 ':'）
                    let lower = if self.at(TokenType::Colon) {
                        None
                    } else {
                        Some(self.parse_expr())
                    };
                    if self.at(TokenType::Colon) {
                        // Slice：lower : upper [: step]（Slice 位置 = ':' token）
                        let colon = self.advance(); // :
                        let upper = if self.at(TokenType::Colon) || self.at(TokenType::Rbracket) {
                            None
                        } else {
                            Some(self.parse_expr())
                        };
                        let step = if self.at(TokenType::Colon) {
                            self.advance(); // :
                            if self.at(TokenType::Rbracket) {
                                None
                            } else {
                                Some(self.parse_expr())
                            }
                        } else {
                            None
                        };
                        let rbr = self.advance(); // ]
                        let value = expr;
                        let vpos = expr_pos(&value);
                        let slice = Expr::Slice {
                            pos: Pos::from_token(&colon),
                            lower: lower.map(Box::new),
                            upper: upper.map(Box::new),
                            step: step.map(Box::new),
                        };
                        expr = Expr::Subscript {
                            pos: Pos {
                                lineno: vpos.lineno,
                                col_offset: vpos.col_offset,
                                end_lineno: Some(rbr.end_line as i64),
                                end_col_offset: Some(rbr.end_column as i64),
                            },
                            value: Box::new(value),
                            slice: Box::new(slice),
                            ctx: "Load".to_string(),
                        };
                    } else {
                        // 单表达式下标：x[1]
                        let rbr = self.advance(); // ]
                        let value = expr;
                        let vpos = expr_pos(&value);
                        expr = Expr::Subscript {
                            pos: Pos {
                                lineno: vpos.lineno,
                                col_offset: vpos.col_offset,
                                end_lineno: Some(rbr.end_line as i64),
                                end_col_offset: Some(rbr.end_column as i64),
                            },
                            value: Box::new(value),
                            slice: Box::new(lower.unwrap()),
                            ctx: "Load".to_string(),
                        };
                    }
                }
                _ => break,
            }
        }
        expr
    }

    fn parse_primary(&mut self) -> Expr {
        let cur_type = self.peek().type_;
        let cur_value = self.peek().value.clone();
        match cur_type {
            TokenType::Number => {
                let tok = self.advance();
                let value = match cur_value.parse::<i64>() {
                    Ok(i) => ConstVal::Int(i),
                    Err(_) => match cur_value.parse::<f64>() {
                        Ok(f) => ConstVal::Float(f),
                        Err(_) => ConstVal::Str(cur_value),
                    },
                };
                Expr::Constant {
                    pos: Pos::from_token(&tok),
                    value,
                }
            }
            TokenType::String => {
                let tok = self.advance();
                Expr::Constant {
                    pos: Pos::from_token(&tok),
                    value: ConstVal::Str(cur_value),
                }
            }
            TokenType::True => {
                let tok = self.advance();
                Expr::Constant {
                    pos: Pos::from_token(&tok),
                    value: ConstVal::Bool(true),
                }
            }
            TokenType::False => {
                let tok = self.advance();
                Expr::Constant {
                    pos: Pos::from_token(&tok),
                    value: ConstVal::Bool(false),
                }
            }
            TokenType::None => {
                let tok = self.advance();
                Expr::Constant {
                    pos: Pos::from_token(&tok),
                    value: ConstVal::None_,
                }
            }
            TokenType::Lbracket => {
                let lbr = self.advance();
                let mut elts: Vec<Expr> = Vec::new();
                if !self.at(TokenType::Rbracket) {
                    elts.push(self.parse_expr());
                    while self.at(TokenType::Comma) {
                        self.advance();
                        elts.push(self.parse_expr());
                    }
                }
                let rbr = self.advance();
                // IbListExpr 位置 = start=LBRACKET 的起，end=RBRACKET 的止
                Expr::List {
                    pos: Pos {
                        lineno: lbr.line as i64,
                        col_offset: lbr.column as i64,
                        end_lineno: Some(rbr.end_line as i64),
                        end_col_offset: Some(rbr.end_column as i64),
                    },
                    elts,
                    ctx: "Load".to_string(),
                }
            }
            TokenType::Lbrace => {
                let lbrace = self.advance();
                let mut keys: Vec<Expr> = Vec::new();
                let mut values: Vec<Expr> = Vec::new();
                if !self.at(TokenType::Rbrace) {
                    loop {
                        keys.push(self.parse_expr());
                        self.expect(TokenType::Colon);
                        values.push(self.parse_expr());
                        if self.at(TokenType::Comma) {
                            self.advance();
                        } else {
                            break;
                        }
                    }
                }
                let rbrace = self.advance();
                Expr::Dict {
                    pos: Pos {
                        lineno: lbrace.line as i64,
                        col_offset: lbrace.column as i64,
                        end_lineno: Some(rbrace.end_line as i64),
                        end_col_offset: Some(rbrace.end_column as i64),
                    },
                    keys,
                    values,
                }
            }
            TokenType::Lparen => {
                self.advance(); // (
                let first = self.parse_expr();
                if self.at(TokenType::Comma) {
                    // Tuple：(e1, e2, ...)
                    let mut elts = vec![first];
                    while self.at(TokenType::Comma) {
                        self.advance();
                        if self.at(TokenType::Rparen) {
                            break; // 尾逗号：(e1, e2,)
                        }
                        elts.push(self.parse_expr());
                    }
                    self.advance(); // )
                    // IbTuple 位置 = 首元素起 → 末元素止（不含括号）
                    let fp = expr_pos(&elts[0]);
                    let lp = expr_pos(elts.last().unwrap());
                    Expr::Tuple {
                        pos: Pos {
                            lineno: fp.lineno,
                            col_offset: fp.col_offset,
                            end_lineno: lp.end_lineno,
                            end_col_offset: lp.end_col_offset,
                        },
                        elts,
                        ctx: "Load".to_string(),
                    }
                } else {
                    // 括号表达式（分组）
                    self.expect(TokenType::Rparen);
                    first
                }
            }
            TokenType::Lambda => self.parse_lambda(),
            TokenType::Identifier => {
                let tok = self.advance();
                Expr::Name {
                    pos: Pos::from_token(&tok),
                    id: cur_value,
                    ctx: "Load".to_string(),
                }
            }
            _ => {
                let tok = self.advance();
                Expr::Name {
                    pos: Pos::from_token(&tok),
                    id: cur_value,
                    ctx: "Load".to_string(),
                }
            }
        }
    }

    /// lambda：`lambda [(typed params)][: or -> TYPE:] body_expr`。
    fn parse_lambda(&mut self) -> Expr {
        let kw = self.advance(); // LAMBDA
        let mut params: Vec<Arg> = Vec::new();
        if self.at(TokenType::Lparen) {
            self.advance(); // (
            if !self.at(TokenType::Rparen) {
                loop {
                    let ann_tok = self.advance();
                    let annotation = Expr::Name {
                        pos: Pos::from_token(&ann_tok),
                        id: ann_tok.value,
                        ctx: "Load".to_string(),
                    };
                    let arg_tok = self.advance();
                    let arg_name = arg_tok.value.clone();
                    let default = if self.at(TokenType::Assign) {
                        self.advance();
                        Some(Box::new(self.parse_expr()))
                    } else {
                        None
                    };
                    params.push(Arg {
                        pos: Pos::from_token(&arg_tok),
                        arg: arg_name,
                        annotation: Some(Box::new(annotation)),
                        default,
                        kind: "POSITIONAL_OR_KEYWORD".to_string(),
                    });
                    if self.at(TokenType::Comma) {
                        self.advance();
                    } else {
                        break;
                    }
                }
            }
            self.expect(TokenType::Rparen);
        }
        let returns = if self.at(TokenType::Arrow) {
            self.advance();
            let ret_tok = self.advance();
            Some(Box::new(Expr::Name {
                pos: Pos::from_token(&ret_tok),
                id: ret_tok.value,
                ctx: "Load".to_string(),
            }))
        } else {
            None
        };
        self.expect(TokenType::Colon);
        let body = self.parse_expr();
        // IbLambdaExpr 位置 = start=LAMBDA 的起，end=body 的止
        let bpos = expr_pos(&body);
        Expr::Lambda {
            pos: Pos {
                lineno: kw.line as i64,
                col_offset: kw.column as i64,
                end_lineno: bpos.end_lineno,
                end_col_offset: bpos.end_col_offset,
            },
            params,
            body: Box::new(body),
            capture_mode: "lambda".to_string(),
            returns,
        }
    }
}

/// BinOp 位置 = start=left 的起，end=right 的止。
fn make_binop(left: Expr, op: String, right: Expr) -> Expr {
    let lpos = expr_pos(&left);
    let rpos = expr_pos(&right);
    Expr::BinOp {
        pos: Pos {
            lineno: lpos.lineno,
            col_offset: lpos.col_offset,
            end_lineno: rpos.end_lineno,
            end_col_offset: rpos.end_col_offset,
        },
        left: Box::new(left),
        op,
        right: Box::new(right),
    }
}

/// BoolOp 位置 = start=首个 value 的起，end=末个 value 的止。
fn boolop_pos(values: &[Expr]) -> Pos {
    let first = expr_pos(&values[0]);
    let last = expr_pos(values.last().unwrap());
    Pos {
        lineno: first.lineno,
        col_offset: first.col_offset,
        end_lineno: last.end_lineno,
        end_col_offset: last.end_col_offset,
    }
}

/// 取 Expr 的位置（起 line/col + 止 end_line/end_col）。
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

/// 入口：IBC 源码 → AST 完整形态（含位置，AST 级差分参考）。
pub fn parse_struct(source: &str) -> String {
    let tokens = lex(source);
    let mut parser = Parser::new(tokens);
    let module = parser.parse_module();
    module.dump()
}

/// 解析 IBCI 源码 → Rust AST（Module）——供节点数据序列化消费。
pub fn parse_to_module(source: &str) -> Module {
    let tokens = lex(source);
    let mut parser = Parser::new(tokens);
    parser.parse_module()
}
