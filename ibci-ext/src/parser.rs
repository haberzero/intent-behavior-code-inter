//! ibci-ext Rust parser——IBC token 流 → AST（对齐 Python `core/compiler/parser`）。
//!
//! 移植范围（本增量）：语料面完整语句/表达式——
//!   语句：Assign / ExprStmt / If[elif 链] / For / FunctionDef[typed args + returns] /
//!         Return / Break / Continue / Pass
//!   表达式：Constant[int/str/bool/None] / Name / BinOp[+ - * / // % **] / UnaryOp[- +] /
//!           Compare[> < >= <= == !=] / Call[func(args)] / List / Dict / Attribute / Subscript
//! AST 级差分门：Rust AST structure 规范形态 == Python AST structure 规范形态
//! （`tests/diff_harness/ast_dump.py` include_positions=False 参考）。后续增量 = 完整
//! 语义层 + 位置跟踪对齐 + 剩余语句/表达式（while/try/lambda/三元/类型注解复合）。

// AST 类型含后续增量将用的变体/方法
#![allow(dead_code)]

use crate::lexer::{lex, Token, TokenType};

// --------------------------------------------------------------------------- //
// AST 类型（对齐 core/kernel/ast.py 的节点子集）
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
    /// 标量规范形态（对齐 Python repr）。
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
    Constant { value: ConstVal },
    Name { id: String, ctx: String },
    BinOp { left: Box<Expr>, op: String, right: Box<Expr> },
    UnaryOp { op: String, operand: Box<Expr> },
    Compare { left: Box<Expr>, ops: Vec<String>, comparators: Vec<Expr> },
    Call { func: Box<Expr>, args: Vec<Expr> },
    List { elts: Vec<Expr>, ctx: String },
    Dict { keys: Vec<Expr>, values: Vec<Expr> },
    Attribute { value: Box<Expr>, attr: String, ctx: String },
    Subscript { value: Box<Expr>, slice: Box<Expr>, ctx: String },
}

impl Expr {
    /// structure 规范形态（对齐 Python ast_dump include_positions=False）。
    fn dump(&self) -> String {
        match self {
            Expr::Constant { value } => format!("IbConstant(value={})", value.dump()),
            Expr::Name { id, ctx } => format!("IbName(id='{}', ctx='{}')", id, ctx),
            Expr::BinOp { left, op, right } => {
                format!("IbBinOp(left={}, op='{}', right={})", left.dump(), op, right.dump())
            }
            Expr::UnaryOp { op, operand } => {
                format!("IbUnaryOp(op='{}', operand={})", op, operand.dump())
            }
            Expr::Compare { left, ops, comparators } => {
                let ops_str: Vec<String> = ops.iter().map(|o| format!("'{}'", o)).collect();
                let comp_str: Vec<String> = comparators.iter().map(|c| c.dump()).collect();
                format!(
                    "IbCompare(left={}, ops=[{}], comparators=[{}])",
                    left.dump(),
                    ops_str.join(", "),
                    comp_str.join(", ")
                )
            }
            Expr::Call { func, args } => {
                let args_str: Vec<String> = args.iter().map(|a| a.dump()).collect();
                format!(
                    "IbCall(func={}, args=[{}], keywords=[])",
                    func.dump(),
                    args_str.join(", ")
                )
            }
            Expr::List { elts, ctx } => {
                let elts_str: Vec<String> = elts.iter().map(|e| e.dump()).collect();
                format!("IbListExpr(elts=[{}], ctx='{}')", elts_str.join(", "), ctx)
            }
            Expr::Dict { keys, values } => {
                let keys_str: Vec<String> = keys.iter().map(|k| k.dump()).collect();
                let vals_str: Vec<String> = values.iter().map(|v| v.dump()).collect();
                format!(
                    "IbDict(keys=[{}], values=[{}])",
                    keys_str.join(", "),
                    vals_str.join(", ")
                )
            }
            Expr::Attribute { value, attr, ctx } => {
                format!(
                    "IbAttribute(value={}, attr='{}', ctx='{}')",
                    value.dump(), attr, ctx
                )
            }
            Expr::Subscript { value, slice, ctx } => {
                format!(
                    "IbSubscript(value={}, slice={}, ctx='{}')",
                    value.dump(), slice.dump(), ctx
                )
            }
        }
    }
}

/// 函数参数（对齐 IbArg：arg / annotation / default / kind）。
#[derive(Debug, Clone)]
pub struct Arg {
    pub arg: String,
    pub annotation: Option<Expr>,
    pub default: Option<Expr>,
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
            "IbArg(arg='{}', annotation={}, default={}, kind='{}')",
            self.arg, ann, def, self.kind
        )
    }
}

#[derive(Debug, Clone)]
pub enum Stmt {
    Assign { targets: Vec<Expr>, value: Option<Expr> },
    ExprStmt { value: Expr },
    If { test: Expr, body: Vec<Stmt>, orelse: Vec<Stmt> },
    For { target: Expr, iter: Expr, body: Vec<Stmt>, orelse: Vec<Stmt> },
    FunctionDef {
        name: String,
        args: Vec<Arg>,
        body: Vec<Stmt>,
        returns: Option<Expr>,
    },
    Return { value: Option<Expr> },
    Break,
    Continue,
    Pass,
}

impl Stmt {
    /// structure 规范形态（对齐 Python ast_dump include_positions=False）。
    fn dump(&self) -> String {
        match self {
            Stmt::Assign { targets, value } => {
                let t: Vec<String> = targets.iter().map(|x| x.dump()).collect();
                let v = match value {
                    Some(v) => v.dump(),
                    None => "None".to_string(),
                };
                format!(
                    "IbAssign(targets=[{}], value={}, llmexcept_handler=None)",
                    t.join(", "),
                    v
                )
            }
            Stmt::ExprStmt { value } => {
                format!("IbExprStmt(value={}, llmexcept_handler=None)", value.dump())
            }
            Stmt::If { test, body, orelse } => {
                let b: Vec<String> = body.iter().map(|s| s.dump()).collect();
                let o: Vec<String> = orelse.iter().map(|s| s.dump()).collect();
                format!(
                    "IbIf(test={}, body=[{}], orelse=[{}], llmexcept_handler=None)",
                    test.dump(),
                    b.join(", "),
                    o.join(", ")
                )
            }
            Stmt::For { target, iter, body, orelse } => {
                let b: Vec<String> = body.iter().map(|s| s.dump()).collect();
                let o: Vec<String> = orelse.iter().map(|s| s.dump()).collect();
                format!(
                    "IbFor(target={}, iter={}, body=[{}], orelse=[{}], llmexcept_handler=None)",
                    target.dump(),
                    iter.dump(),
                    b.join(", "),
                    o.join(", ")
                )
            }
            Stmt::FunctionDef { name, args, body, returns } => {
                let a: Vec<String> = args.iter().map(|x| x.dump()).collect();
                let b: Vec<String> = body.iter().map(|s| s.dump()).collect();
                let r = match returns {
                    Some(r) => r.dump(),
                    None => "None".to_string(),
                };
                format!(
                    "IbFunctionDef(name='{}', args=[{}], body=[{}], returns={}, \
                     type_params=[], type_param_bounds={{}}, free_vars=[], \
                     is_generator=False, type_param_uids=[])",
                    name,
                    a.join(", "),
                    b.join(", "),
                    r
                )
            }
            Stmt::Return { value } => {
                let v = match value {
                    Some(v) => v.dump(),
                    None => "None".to_string(),
                };
                format!("IbReturn(value={})", v)
            }
            Stmt::Break => "IbBreak()".to_string(),
            Stmt::Continue => "IbContinue()".to_string(),
            Stmt::Pass => "IbPass()".to_string(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct Module {
    pub body: Vec<Stmt>,
}

impl Module {
    pub fn dump(&self) -> String {
        let b: Vec<String> = self.body.iter().map(|s| s.dump()).collect();
        format!("IbModule(body=[{}], file_path=None)", b.join(", "))
    }
}

// --------------------------------------------------------------------------- //
// Parser（递归下降——语料面完整语句/表达式 + INDENT/DEDENT body）
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
        Module { body }
    }

    fn parse_stmt(&mut self) -> Stmt {
        match self.peek().type_ {
            TokenType::If => self.parse_if(),
            TokenType::For => self.parse_for(),
            TokenType::Func => self.parse_function_def(),
            TokenType::Return => {
                self.advance();
                let value = if self.is_stmt_end() {
                    None
                } else {
                    Some(self.parse_expr())
                };
                Stmt::Return { value }
            }
            TokenType::Break => {
                self.advance();
                Stmt::Break
            }
            TokenType::Continue => {
                self.advance();
                Stmt::Continue
            }
            TokenType::Pass => {
                self.advance();
                Stmt::Pass
            }
            TokenType::Identifier => {
                // 回退式前瞻：解析 target（Name 或 Subscript/Attribute），若后随
                // ASSIGN = Assign；否则回退按 ExprStmt 解析。
                let save = self.pos;
                let target = self.parse_assign_target();
                if self.at(TokenType::Assign) {
                    self.advance(); // =
                    let value = self.parse_expr();
                    return Stmt::Assign {
                        targets: vec![target],
                        value: Some(value),
                    };
                }
                self.pos = save; // 非 Assign → ExprStmt
                let value = self.parse_expr();
                Stmt::ExprStmt { value }
            }
            _ => {
                let value = self.parse_expr();
                Stmt::ExprStmt { value }
            }
        }
    }

    /// Assign target：Name 或 Subscript（d['c']）/ Attribute（obj.attr）。
    fn parse_assign_target(&mut self) -> Expr {
        let name_id = self.advance().value; // IDENTIFIER
        let base = Expr::Name {
            id: name_id,
            ctx: "Load".to_string(),
        };
        if self.at(TokenType::Lbracket) {
            self.advance(); // [
            let slice = self.parse_expr();
            self.expect(TokenType::Rbracket);
            Expr::Subscript {
                value: Box::new(base),
                slice: Box::new(slice),
                ctx: "Load".to_string(),
            }
        } else if self.at(TokenType::Dot) {
            self.advance(); // .
            let attr = self.advance().value;
            Expr::Attribute {
                value: Box::new(base),
                attr,
                ctx: "Load".to_string(),
            }
        } else {
            base
        }
    }

    fn parse_if(&mut self) -> Stmt {
        self.advance(); // IF 或 ELIF
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
        Stmt::If { test, body, orelse }
    }

    fn parse_for(&mut self) -> Stmt {
        self.advance(); // FOR
        let target = Expr::Name {
            id: self.advance().value,
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
        Stmt::For { target, iter, body, orelse }
    }

    fn parse_function_def(&mut self) -> Stmt {
        self.advance(); // FUNC
        let name = self.advance().value; // IDENTIFIER
        self.expect(TokenType::Lparen);
        let mut args: Vec<Arg> = Vec::new();
        if !self.at(TokenType::Rparen) {
            loop {
                // annotation（IDENTIFIER → Name）+ arg name（IDENTIFIER）
                let annotation = Expr::Name {
                    id: self.advance().value,
                    ctx: "Load".to_string(),
                };
                let arg_name = self.advance().value;
                let default = if self.at(TokenType::Assign) {
                    self.advance();
                    Some(self.parse_expr())
                } else {
                    None
                };
                args.push(Arg {
                    arg: arg_name,
                    annotation: Some(annotation),
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
        // 返回类型（ARROW + type）
        let returns = if self.at(TokenType::Arrow) {
            self.advance();
            Some(Expr::Name {
                id: self.advance().value,
                ctx: "Load".to_string(),
            })
        } else {
            None
        };
        self.expect(TokenType::Colon);
        self.skip_newlines();
        let body = self.parse_body();
        Stmt::FunctionDef { name, args, body, returns }
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

    // ---- 表达式（递归下降 + 优先级）---- //

    /// 最低优先级：比较。
    fn parse_expr(&mut self) -> Expr {
        let left = self.parse_additive();
        // 比较链（> < >= <= == !=）
        let (ops, comparators) = self.parse_compare_chain();
        if ops.is_empty() {
            left
        } else {
            Expr::Compare {
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

    /// 加/减。
    fn parse_additive(&mut self) -> Expr {
        let mut left = self.parse_term();
        while matches!(
            self.peek().type_,
            TokenType::Plus | TokenType::Minus
        ) {
            let op = self.advance().value;
            let right = self.parse_term();
            left = Expr::BinOp {
                left: Box::new(left),
                op,
                right: Box::new(right),
            };
        }
        left
    }

    /// 乘/除/整除/取模。
    fn parse_term(&mut self) -> Expr {
        let mut left = self.parse_power();
        while matches!(
            self.peek().type_,
            TokenType::Star
                | TokenType::Slash
                | TokenType::FloorDiv
                | TokenType::Percent
        ) {
            let op = self.advance().value;
            let right = self.parse_power();
            left = Expr::BinOp {
                left: Box::new(left),
                op,
                right: Box::new(right),
            };
        }
        left
    }

    /// 幂（右结合）。
    fn parse_power(&mut self) -> Expr {
        let left = self.parse_unary();
        if self.at(TokenType::StarStar) {
            let op = self.advance().value;
            let right = Box::new(self.parse_power()); // 右结合递归
            return Expr::BinOp { left: Box::new(left), op, right };
        }
        left
    }

    /// 一元（- / +）。
    fn parse_unary(&mut self) -> Expr {
        if matches!(self.peek().type_, TokenType::Minus | TokenType::Plus) {
            let op = self.advance().value;
            let operand = Box::new(self.parse_unary());
            return Expr::UnaryOp { op, operand };
        }
        self.parse_postfix()
    }

    /// postfix（call / attribute / subscript）。
    fn parse_postfix(&mut self) -> Expr {
        let mut expr = self.parse_primary();
        loop {
            match self.peek().type_ {
                TokenType::Lparen => {
                    self.advance();
                    let mut args: Vec<Expr> = Vec::new();
                    if !self.at(TokenType::Rparen) {
                        args.push(self.parse_expr());
                        while self.at(TokenType::Comma) {
                            self.advance();
                            args.push(self.parse_expr());
                        }
                    }
                    self.expect(TokenType::Rparen);
                    expr = Expr::Call {
                        func: Box::new(expr),
                        args,
                    };
                }
                TokenType::Dot => {
                    self.advance();
                    let attr = self.advance().value; // IDENTIFIER
                    expr = Expr::Attribute {
                        value: Box::new(expr),
                        attr,
                        ctx: "Load".to_string(),
                    };
                }
                TokenType::Lbracket => {
                    self.advance();
                    let slice = self.parse_expr();
                    self.expect(TokenType::Rbracket);
                    expr = Expr::Subscript {
                        value: Box::new(expr),
                        slice: Box::new(slice),
                        ctx: "Load".to_string(),
                    };
                }
                _ => break,
            }
        }
        expr
    }

    /// primary（literal / name / list / dict / paren）。
    fn parse_primary(&mut self) -> Expr {
        let cur_type = self.peek().type_;
        let cur_value = self.peek().value.clone();
        match cur_type {
            TokenType::Number => {
                self.advance();
                let value = match cur_value.parse::<i64>() {
                    Ok(i) => ConstVal::Int(i),
                    Err(_) => match cur_value.parse::<f64>() {
                        Ok(f) => ConstVal::Float(f),
                        Err(_) => ConstVal::Str(cur_value),
                    },
                };
                Expr::Constant { value }
            }
            TokenType::String => {
                self.advance();
                Expr::Constant {
                    value: ConstVal::Str(cur_value),
                }
            }
            TokenType::True => {
                self.advance();
                Expr::Constant { value: ConstVal::Bool(true) }
            }
            TokenType::False => {
                self.advance();
                Expr::Constant { value: ConstVal::Bool(false) }
            }
            TokenType::None => {
                self.advance();
                Expr::Constant { value: ConstVal::None_ }
            }
            TokenType::Lbracket => {
                self.advance();
                let mut elts: Vec<Expr> = Vec::new();
                if !self.at(TokenType::Rbracket) {
                    elts.push(self.parse_expr());
                    while self.at(TokenType::Comma) {
                        self.advance();
                        elts.push(self.parse_expr());
                    }
                }
                self.expect(TokenType::Rbracket);
                Expr::List { elts, ctx: "Load".to_string() }
            }
            TokenType::Lbrace => {
                self.advance();
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
                self.expect(TokenType::Rbrace);
                Expr::Dict { keys, values }
            }
            TokenType::Lparen => {
                self.advance();
                let inner = self.parse_expr();
                self.expect(TokenType::Rparen);
                inner
            }
            TokenType::Identifier => {
                self.advance();
                Expr::Name {
                    id: cur_value,
                    ctx: "Load".to_string(),
                }
            }
            _ => {
                self.advance();
                Expr::Name {
                    id: cur_value,
                    ctx: "Load".to_string(),
                }
            }
        }
    }
}

/// 入口：IBC 源码 → AST structure 规范形态（AST 级差分参考）。
pub fn parse_struct(source: &str) -> String {
    let tokens = lex(source);
    let mut parser = Parser::new(tokens);
    let module = parser.parse_module();
    module.dump()
}
