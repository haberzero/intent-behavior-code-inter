//! ibci-ext Rust parser——IBC token 流 → AST（对齐 Python `core/compiler/parser`）。
//!
//! 移植范围（本增量）：最小语句/表达式面——Assign（单 target = Name，value =
//! Expr）/ ExprStmt / 表达式（Constant[int/str/bool/None] / Name / BinOp[+] /
//! Call[func(args)]）。AST 级差分门：Rust AST structure 规范形态 == Python AST
//! structure 规范形态（`tests/diff_harness/ast_dump.py` 参考）。后续增量 = 完整
//! 语句/表达式面 + 位置跟踪对齐 + 语义层。
//!
//! AST structure 规范形态（对齐 Python ast_dump include_positions=False）：
//! `<节点类名>(field1=<val1>, ...)`，子节点递归，标量 repr，列表 `[...]`，
//! None = "None"。

// AST 类型含后续增量将用的变体/方法（Float/name）
#![allow(dead_code)]

use crate::lexer::{Token, TokenType, lex};

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
                // 对齐 Python repr(float)
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
    Call { func: Box<Expr>, args: Vec<Expr> },
}

impl Expr {
    fn name(&self) -> &'static str {
        match self {
            Expr::Constant { .. } => "IbConstant",
            Expr::Name { .. } => "IbName",
            Expr::BinOp { .. } => "IbBinOp",
            Expr::Call { .. } => "IbCall",
        }
    }
    /// structure 规范形态（对齐 Python ast_dump include_positions=False）。
    fn dump(&self) -> String {
        match self {
            Expr::Constant { value } => {
                format!("IbConstant(value={})", value.dump())
            }
            Expr::Name { id, ctx } => {
                format!("IbName(id='{}', ctx='{}')", id, ctx)
            }
            Expr::BinOp { left, op, right } => {
                format!(
                    "IbBinOp(left={}, op='{}', right={})",
                    left.dump(), op, right.dump()
                )
            }
            Expr::Call { func, args } => {
                let args_str: Vec<String> = args.iter().map(|a| a.dump()).collect();
                let kw: Vec<String> = vec![]; // 本增量无具名实参
                format!(
                    "IbCall(func={}, args=[{}], keywords=[{}])",
                    func.dump(),
                    args_str.join(", "),
                    kw.join(", ")
                )
            }
        }
    }
}

#[derive(Debug, Clone)]
pub enum Stmt {
    Assign {
        targets: Vec<Expr>,
        value: Option<Expr>,
    },
    ExprStmt { value: Expr },
}

impl Stmt {
    fn name(&self) -> &'static str {
        match self {
            Stmt::Assign { .. } => "IbAssign",
            Stmt::ExprStmt { .. } => "IbExprStmt",
        }
    }
    /// structure 规范形态。
    fn dump(&self) -> String {
        match self {
            Stmt::Assign { targets, value } => {
                let targets_str: Vec<String> = targets.iter().map(|t| t.dump()).collect();
                let value_str = match value {
                    Some(v) => v.dump(),
                    None => "None".to_string(),
                };
                format!(
                    "IbAssign(targets=[{}], value={}, llmexcept_handler=None)",
                    targets_str.join(", "),
                    value_str
                )
            }
            Stmt::ExprStmt { value } => {
                format!(
                    "IbExprStmt(value={}, llmexcept_handler=None)",
                    value.dump()
                )
            }
        }
    }
}

#[derive(Debug, Clone)]
pub struct Module {
    pub body: Vec<Stmt>,
}

impl Module {
    /// structure 规范形态（对齐 Python ast_dump include_positions=False）。
    pub fn dump(&self) -> String {
        let body_str: Vec<String> = self.body.iter().map(|s| s.dump()).collect();
        format!(
            "IbModule(body=[{}], file_path=None)",
            body_str.join(", ")
        )
    }
}

// --------------------------------------------------------------------------- //
// Parser（递归下降——最小语句/表达式面）
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
        // EOF 后返回末 token（防越界）
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
    fn skip_newlines(&mut self) {
        while self.at(TokenType::Newline) {
            self.advance();
        }
    }

    /// 解析模块（语句序列，NEWLINE 分隔）。
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

    /// 解析单条语句（Assign 或 ExprStmt）。
    fn parse_stmt(&mut self) -> Stmt {
        // 前瞻：IDENTIFIER ASSIGN → Assign；否则 ExprStmt
        if self.at(TokenType::Identifier) {
            let save = self.pos;
            let _name = self.advance();
            if self.at(TokenType::Assign) {
                self.advance(); // 消费 =
                let value = self.parse_expr();
                return Stmt::Assign {
                    targets: vec![Expr::Name {
                        id: _name.value,
                        ctx: "Load".to_string(),
                    }],
                    value: Some(value),
                };
            }
            self.pos = save; // 回退（非 Assign）
        }
        // ExprStmt
        let value = self.parse_expr();
        Stmt::ExprStmt { value }
    }

    /// 解析表达式（最小面：BinOp[+] / Call / primary）。
    fn parse_expr(&mut self) -> Expr {
        let mut left = self.parse_primary();
        // BinOp（+）——右结合非，本增量仅处理 +
        while self.at(TokenType::Plus) {
            let op = self.advance().value;
            let right = self.parse_primary();
            left = Expr::BinOp {
                left: Box::new(left),
                op,
                right: Box::new(right),
            };
        }
        left
    }

    /// 解析 primary（Constant / Name / Call / paren）。
    /// 先拷贝当前 token 的 type + value（不持借用），再 match 并消费。
    fn parse_primary(&mut self) -> Expr {
        let cur_type = self.peek().type_;
        let cur_value = self.peek().value.clone();
        match cur_type {
            TokenType::Number => {
                self.advance();
                // 十进制 int（本增量主面）→ float（次面）；非十进制（hex/bin/oct
                // = 后续增量）保留原串（不静默数值默认——最小面不解释为非十进制数）
                let value = match cur_value.parse::<i64>() {
                    Ok(i) => ConstVal::Int(i),
                    Err(_) => match cur_value.parse::<f64>() {
                        Ok(f) => ConstVal::Float(f),
                        Err(_) => ConstVal::Str(cur_value.clone()),
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
                Expr::Constant {
                    value: ConstVal::Bool(true),
                }
            }
            TokenType::False => {
                self.advance();
                Expr::Constant {
                    value: ConstVal::Bool(false),
                }
            }
            TokenType::None => {
                self.advance();
                Expr::Constant {
                    value: ConstVal::None_,
                }
            }
            TokenType::Identifier => {
                self.advance(); // 消费 IDENTIFIER
                // Call：IDENTIFIER LPAREN ... RPAREN
                if self.at(TokenType::Lparen) {
                    self.advance(); // (
                    let mut args: Vec<Expr> = Vec::new();
                    if !self.at(TokenType::Rparen) {
                        args.push(self.parse_expr());
                        while self.at(TokenType::Comma) {
                            self.advance();
                            args.push(self.parse_expr());
                        }
                    }
                    if self.at(TokenType::Rparen) {
                        self.advance(); // )
                    }
                    Expr::Call {
                        func: Box::new(Expr::Name {
                            id: cur_value,
                            ctx: "Load".to_string(),
                        }),
                        args,
                    }
                } else {
                    Expr::Name {
                        id: cur_value,
                        ctx: "Load".to_string(),
                    }
                }
            }
            TokenType::Lparen => {
                self.advance(); // (
                let inner = self.parse_expr();
                if self.at(TokenType::Rparen) {
                    self.advance(); // )
                }
                inner
            }
            _ => {
                // 未覆盖（本增量）——消费避免死循环
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
