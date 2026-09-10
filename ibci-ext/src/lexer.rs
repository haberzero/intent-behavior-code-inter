//! ibci-ext Rust lexer——IBC 源码 → token 流（对齐 Python `core/compiler/lexer`）。
//!
//! 移植范围（本增量）：normal 模式核心 token 化（数字/标识符/关键字/字符串/
//! 运算符/括号/点/冒号/逗号/注释/换行）+ 行处理 + 缩进（INDENT/DEDENT）——
//! 覆盖差分 harness 语料面。行为块（@~...~）/意图（@...）/三引号串/raw 串/
//! 变量引用（$x）等子状态 = 后续增量（语料未用）。
//!
//! 差分等价门：Rust token 流 == Python token 流（type/value/line/column 逐条
//! 等价）——见 tests/diff_harness。

use std::collections::HashMap;

// --------------------------------------------------------------------------- //
// TokenType（对齐 core/compiler/common/tokens.py 的 core 子集）
// --------------------------------------------------------------------------- //
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TokenType {
    Indent,
    Dedent,
    Newline,
    Eof,
    Import,
    From,
    Func,
    Return,
    Lambda,
    If,
    Elif,
    Else,
    For,
    While,
    In,
    Auto,
    Fn,
    Global,
    Nonlocal,
    Pass,
    Break,
    Continue,
    As,
    And,
    Or,
    Not,
    Is,
    Try,
    Except,
    Finally,
    Raise,
    Class,
    None,
    True,
    False,
    Identifier,
    Number,
    String,
    Assign,
    Arrow,
    Plus,
    Minus,
    Star,
    StarStar,
    Slash,
    FloorDiv,
    Percent,
    PlusAssign,
    MinusAssign,
    StarAssign,
    StarStarAssign,
    SlashAssign,
    FloorDivAssign,
    PercentAssign,
    Lparen,
    Rparen,
    Lbracket,
    Rbracket,
    Lbrace,
    Rbrace,
    Colon,
    Question,
    Comma,
    Dot,
    Eq,
    Ne,
    Gt,
    Lt,
    Ge,
    Le,
}

impl TokenType {
    /// 序列化名（与 Python TokenType 成员名一致——差分比对用）。
    pub fn name(self) -> &'static str {
        use TokenType::*;
        match self {
            Indent => "INDENT",
            Dedent => "DEDENT",
            Newline => "NEWLINE",
            Eof => "EOF",
            Import => "IMPORT",
            From => "FROM",
            Func => "FUNC",
            Return => "RETURN",
            Lambda => "LAMBDA",
            If => "IF",
            Elif => "ELIF",
            Else => "ELSE",
            For => "FOR",
            While => "WHILE",
            In => "IN",
            Auto => "AUTO",
            Fn => "FN",
            Global => "GLOBAL",
            Nonlocal => "NONLOCAL",
            Pass => "PASS",
            Break => "BREAK",
            Continue => "CONTINUE",
            As => "AS",
            And => "AND",
            Or => "OR",
            Not => "NOT",
            Is => "IS",
            Try => "TRY",
            Except => "EXCEPT",
            Finally => "FINALLY",
            Raise => "RAISE",
            Class => "CLASS",
            None => "NONE",
            True => "TRUE",
            False => "FALSE",
            Identifier => "IDENTIFIER",
            Number => "NUMBER",
            String => "STRING",
            Assign => "ASSIGN",
            Arrow => "ARROW",
            Plus => "PLUS",
            Minus => "MINUS",
            Star => "STAR",
            StarStar => "STAR_STAR",
            Slash => "SLASH",
            FloorDiv => "FLOOR_DIV",
            Percent => "PERCENT",
            PlusAssign => "PLUS_ASSIGN",
            MinusAssign => "MINUS_ASSIGN",
            StarAssign => "STAR_ASSIGN",
            StarStarAssign => "STAR_STAR_ASSIGN",
            SlashAssign => "SLASH_ASSIGN",
            FloorDivAssign => "FLOOR_DIV_ASSIGN",
            PercentAssign => "PERCENT_ASSIGN",
            Lparen => "LPAREN",
            Rparen => "RPAREN",
            Lbracket => "LBRACKET",
            Rbracket => "RBRACKET",
            Lbrace => "LBRACE",
            Rbrace => "RBRACE",
            Colon => "COLON",
            Question => "QUESTION",
            Comma => "COMMA",
            Dot => "DOT",
            Eq => "EQ",
            Ne => "NE",
            Gt => "GT",
            Lt => "LT",
            Ge => "GE",
            Le => "LE",
        }
    }
}

// --------------------------------------------------------------------------- //
// Token（对齐 core/compiler/common/tokens.py 的 Token dataclass）
// --------------------------------------------------------------------------- //
#[derive(Debug, Clone)]
pub struct Token {
    pub type_: TokenType,
    pub value: String,
    pub line: usize,
    pub column: usize,
    pub end_line: usize,
    pub end_column: usize,
    pub is_at_line_start: bool,
}

impl Token {
    fn at(type_: TokenType, value: String, line: usize, column: usize) -> Self {
        Token {
            type_,
            value,
            line,
            column,
            end_line: line,
            end_column: column,
            is_at_line_start: false,
        }
    }
}

// --------------------------------------------------------------------------- //
// StrStream（对齐 core/compiler/lexer/str_stream.py）
// --------------------------------------------------------------------------- //
struct StrStream {
    source: Vec<char>,
    length: usize,
    pos: usize,
    line: usize,
    col: usize,
    start_pos: usize,
    start_line: usize,
    start_col: usize,
}

impl StrStream {
    fn new(source: &str) -> Self {
        let source: Vec<char> = source.chars().collect();
        StrStream {
            length: source.len(),
            pos: 0,
            line: 1,
            col: 1,
            source,
            start_pos: 0,
            start_line: 1,
            start_col: 1,
        }
    }
    fn peek(&self, offset: usize) -> char {
        if self.pos + offset >= self.length {
            '\0'
        } else {
            self.source[self.pos + offset]
        }
    }
    fn advance(&mut self) -> char {
        if self.is_at_end() {
            return '\0';
        }
        let c = self.source[self.pos];
        self.pos += 1;
        if c == '\n' {
            self.line += 1;
            self.col = 1;
        } else {
            self.col += 1;
        }
        c
    }
    fn match_char(&mut self, expected: char) -> bool {
        if self.is_at_end() || self.source[self.pos] != expected {
            return false;
        }
        self.advance();
        true
    }
    fn is_at_end(&self) -> bool {
        self.pos >= self.length
    }
    fn start_token(&mut self) {
        self.start_pos = self.pos;
        self.start_line = self.line;
        self.start_col = self.col;
    }
    fn create_token(&self, type_: TokenType, value: Option<String>) -> Token {
        let value = match value {
            Some(v) => v,
            None => self.source[self.start_pos..self.pos].iter().collect(),
        };
        Token {
            type_,
            value,
            line: self.start_line,
            column: self.start_col,
            end_line: self.line,
            end_column: self.col,
            is_at_line_start: false,
        }
    }
}

// --------------------------------------------------------------------------- //
// Lexer（对齐 core/compiler/lexer/lexer.py 行循环 + core_scanner.py normal 核心
// + indent_processor.py 缩进）
// --------------------------------------------------------------------------- //
pub struct Lexer {
    scanner: StrStream,
    paren_stack: Vec<(usize, usize)>,
    continuation_mode: bool,
    in_string: bool,
    quote_char: char,
    current_string_val: String,
    keywords: HashMap<String, TokenType>,
    indent_stack: Vec<usize>,
    is_new_line: bool,
}

impl Lexer {
    fn new(source: &str) -> Self {
        let mut keywords = HashMap::new();
        let map: &[(&str, TokenType)] = &[
            ("import", TokenType::Import),
            ("from", TokenType::From),
            ("func", TokenType::Func),
            ("return", TokenType::Return),
            ("lambda", TokenType::Lambda),
            ("if", TokenType::If),
            ("elif", TokenType::Elif),
            ("else", TokenType::Else),
            ("for", TokenType::For),
            ("while", TokenType::While),
            ("in", TokenType::In),
            ("auto", TokenType::Auto),
            ("fn", TokenType::Fn),
            ("global", TokenType::Global),
            ("nonlocal", TokenType::Nonlocal),
            ("pass", TokenType::Pass),
            ("break", TokenType::Break),
            ("continue", TokenType::Continue),
            ("as", TokenType::As),
            ("and", TokenType::And),
            ("or", TokenType::Or),
            ("not", TokenType::Not),
            ("is", TokenType::Is),
            ("try", TokenType::Try),
            ("except", TokenType::Except),
            ("finally", TokenType::Finally),
            ("raise", TokenType::Raise),
            ("class", TokenType::Class),
            ("None", TokenType::None),
            ("True", TokenType::True),
            ("False", TokenType::False),
        ];
        for (k, v) in map {
            keywords.insert(k.to_string(), *v);
        }
        Lexer {
            scanner: StrStream::new(source),
            paren_stack: Vec::new(),
            continuation_mode: false,
            in_string: false,
            quote_char: '"',
            current_string_val: String::new(),
            keywords,
            indent_stack: vec![0],
            is_new_line: true,
        }
    }

    fn paren_level(&self) -> usize {
        self.paren_stack.len()
    }

    /// 行循环（对齐 lexer.py tokenize + _process_line）。
    pub fn tokenize(mut self) -> Vec<Token> {
        let mut tokens: Vec<Token> = Vec::new();
        while !self.scanner.is_at_end() {
            self.process_line(&mut tokens);
        }
        // EOF 回退缩进（对齐 indent_processor.handle_eof：column=0）
        while self.indent_stack.len() > 1 {
            self.indent_stack.pop();
            tokens.push(Token::at(
                TokenType::Dedent,
                String::new(),
                self.scanner.line,
                0,
            ));
        }
        tokens.push(Token::at(TokenType::Eof, String::new(), self.scanner.line, 0));
        tokens
    }

    fn process_line(&mut self, tokens: &mut Vec<Token>) {
        let should_indent = !self.continuation_mode
            && self.paren_level() == 0
            && !self.in_string
            && self.is_new_line;
        if should_indent {
            let (has_content, indent_tokens) = self.process_indent();
            tokens.extend(indent_tokens);
            if !has_content {
                // 空行/注释行：换行已由 process_indent 消费
                self.is_new_line = true;
                return;
            }
        } else {
            // 续行：跳过空白
            while self.scanner.peek(0) == ' ' || self.scanner.peek(0) == '\t' {
                self.scanner.advance();
            }
            self.continuation_mode = false;
        }
        let (line_tokens, newline_done) = self.scan_line();
        tokens.extend(line_tokens);
        self.is_new_line = newline_done;
    }

    /// 行首缩进处理（对齐 indent_processor.py process：start_col 消费前记录；
    /// 空格/tab 各计 1；空行/注释行消费换行返回 has_content=false）。
    fn process_indent(&mut self) -> (bool, Vec<Token>) {
        let mut tokens: Vec<Token> = Vec::new();
        let start_col = self.scanner.col;
        let mut spaces = 0usize;
        while self.scanner.peek(0) == ' ' || self.scanner.peek(0) == '\t' {
            self.scanner.advance();
            spaces += 1;
        }
        // 空行（消费换行）
        if self.scanner.peek(0) == '\n' {
            self.scanner.advance();
            return (false, tokens);
        }
        // 注释行（跳注释 + 消费换行）
        if self.scanner.peek(0) == '#' {
            self.skip_comment();
            if self.scanner.peek(0) == '\n' {
                self.scanner.advance();
            }
            return (false, tokens);
        }
        // EOF
        if self.scanner.is_at_end() {
            return (false, tokens);
        }
        let current_indent = spaces;
        let last_indent = *self.indent_stack.last().unwrap();
        if current_indent > last_indent {
            self.indent_stack.push(current_indent);
            tokens.push(Token::at(
                TokenType::Indent,
                String::new(),
                self.scanner.line,
                start_col,
            ));
        } else if current_indent < last_indent {
            while current_indent < *self.indent_stack.last().unwrap() {
                self.indent_stack.pop();
                tokens.push(Token::at(
                    TokenType::Dedent,
                    String::new(),
                    self.scanner.line,
                    start_col,
                ));
            }
        }
        (true, tokens)
    }

    /// 扫描到行末（对齐 core_scanner.py scan_line + _handle_newline）。
    fn scan_line(&mut self) -> (Vec<Token>, bool) {
        let mut tokens: Vec<Token> = Vec::new();
        while !self.scanner.is_at_end() {
            let c = self.scanner.peek(0);
            if c == '\n' {
                let done = self.handle_newline(&mut tokens);
                if done {
                    return (tokens, true);
                }
                continue;
            }
            if self.in_string {
                self.scan_string_char(&mut tokens);
            } else {
                self.scan_normal_char(&mut tokens);
            }
        }
        (tokens, false)
    }

    fn handle_newline(&mut self, tokens: &mut Vec<Token>) -> bool {
        if self.in_string {
            self.scan_string_char(tokens);
            return false;
        }
        if self.paren_level() > 0 {
            self.scanner.advance();
            self.continuation_mode = true;
            return true;
        }
        self.scanner.advance();
        let line = self.scanner.line.saturating_sub(1);
        tokens.push(Token::at(
            TokenType::Newline,
            "\n".to_string(),
            line,
            self.scanner.col,
        ));
        true
    }

    fn scan_normal_char(&mut self, tokens: &mut Vec<Token>) {
        self.scanner.start_token();
        let c = self.scanner.peek(0);
        // 行续行（反斜杠 + 换行）
        if c == '\\' {
            self.scanner.advance();
            if self.scanner.peek(0) == '\n' {
                self.continuation_mode = true;
            }
            return;
        }
        // 空白
        if c == ' ' || c == '\t' {
            self.scanner.advance();
            return;
        }
        // 注释
        if c == '#' {
            self.scanner.advance();
            self.skip_comment();
            return;
        }
        // 字符串（单行 "..." / '...'）
        if c == '"' || c == '\'' {
            let quote = self.scanner.advance();
            self.open_string(quote);
            return;
        }
        // 括号
        match c {
            '(' => {
                self.paren_stack.push((self.scanner.start_line, self.scanner.start_col));
                self.scanner.advance();
                tokens.push(self.scanner.create_token(TokenType::Lparen, None));
                return;
            }
            ')' => {
                if !self.paren_stack.is_empty() {
                    self.paren_stack.pop();
                }
                self.scanner.advance();
                tokens.push(self.scanner.create_token(TokenType::Rparen, None));
                return;
            }
            '[' => {
                self.paren_stack.push((self.scanner.start_line, self.scanner.start_col));
                self.scanner.advance();
                tokens.push(self.scanner.create_token(TokenType::Lbracket, None));
                return;
            }
            ']' => {
                if !self.paren_stack.is_empty() {
                    self.paren_stack.pop();
                }
                self.scanner.advance();
                tokens.push(self.scanner.create_token(TokenType::Rbracket, None));
                return;
            }
            '{' => {
                self.paren_stack.push((self.scanner.start_line, self.scanner.start_col));
                self.scanner.advance();
                tokens.push(self.scanner.create_token(TokenType::Lbrace, None));
                return;
            }
            '}' => {
                if !self.paren_stack.is_empty() {
                    self.paren_stack.pop();
                }
                self.scanner.advance();
                tokens.push(self.scanner.create_token(TokenType::Rbrace, None));
                return;
            }
            _ => {}
        }
        // 分隔符
        match c {
            ',' => {
                self.scanner.advance();
                tokens.push(self.scanner.create_token(TokenType::Comma, None));
                return;
            }
            ':' => {
                self.scanner.advance();
                tokens.push(self.scanner.create_token(TokenType::Colon, None));
                return;
            }
            '?' => {
                self.scanner.advance();
                tokens.push(self.scanner.create_token(TokenType::Question, None));
                return;
            }
            '.' => {
                self.scanner.advance();
                tokens.push(self.scanner.create_token(TokenType::Dot, None));
                return;
            }
            _ => {}
        }
        // 运算符（含两字符）——仅对运算符字符调用（先消费首字符再匹配次字符）
        if matches!(c, '=' | '-' | '+' | '*' | '/' | '%' | '>' | '<' | '!') {
            self.scan_operator(c, tokens);
            return;
        }
        // 标识符 / 数字
        if c.is_ascii_alphabetic() || c == '_' {
            self.scan_identifier(c, tokens);
            return;
        }
        if c.is_ascii_digit() {
            self.scan_number(c, tokens);
            return;
        }
        // 未覆盖字符（语料未用；跳过避免死循环）
        self.scanner.advance();
    }

    /// 扫描运算符（首字符已 peek；消费首字符后匹配次字符产出两字符/单字符 token）。
    fn scan_operator(&mut self, c: char, tokens: &mut Vec<Token>) {
        use TokenType::*;
        self.scanner.advance(); // 消费首字符
        match c {
            '=' => {
                if self.scanner.match_char('=') {
                    tokens.push(self.scanner.create_token(Eq, Some("==".into())));
                } else {
                    tokens.push(self.scanner.create_token(Assign, Some("=".into())));
                }
            }
            '-' => {
                if self.scanner.match_char('>') {
                    tokens.push(self.scanner.create_token(Arrow, Some("->".into())));
                } else if self.scanner.match_char('=') {
                    tokens.push(self.scanner.create_token(MinusAssign, Some("-=".into())));
                } else {
                    tokens.push(self.scanner.create_token(Minus, Some("-".into())));
                }
            }
            '+' => {
                if self.scanner.match_char('=') {
                    tokens.push(self.scanner.create_token(PlusAssign, Some("+=".into())));
                } else {
                    tokens.push(self.scanner.create_token(Plus, Some("+".into())));
                }
            }
            '*' => {
                if self.scanner.match_char('*') {
                    if self.scanner.match_char('=') {
                        tokens.push(self.scanner.create_token(StarStarAssign, Some("**=".into())));
                    } else {
                        tokens.push(self.scanner.create_token(StarStar, Some("**".into())));
                    }
                } else if self.scanner.match_char('=') {
                    tokens.push(self.scanner.create_token(StarAssign, Some("*=".into())));
                } else {
                    tokens.push(self.scanner.create_token(Star, Some("*".into())));
                }
            }
            '/' => {
                if self.scanner.match_char('/') {
                    if self.scanner.match_char('=') {
                        tokens.push(self.scanner.create_token(FloorDivAssign, Some("//=".into())));
                    } else {
                        tokens.push(self.scanner.create_token(FloorDiv, Some("//".into())));
                    }
                } else if self.scanner.match_char('=') {
                    tokens.push(self.scanner.create_token(SlashAssign, Some("/=".into())));
                } else {
                    tokens.push(self.scanner.create_token(Slash, Some("/".into())));
                }
            }
            '%' => {
                if self.scanner.match_char('=') {
                    tokens.push(self.scanner.create_token(PercentAssign, Some("%=".into())));
                } else {
                    tokens.push(self.scanner.create_token(Percent, Some("%".into())));
                }
            }
            '>' => {
                if self.scanner.match_char('=') {
                    tokens.push(self.scanner.create_token(Ge, Some(">=".into())));
                } else {
                    tokens.push(self.scanner.create_token(Gt, Some(">".into())));
                }
            }
            '<' => {
                if self.scanner.match_char('=') {
                    tokens.push(self.scanner.create_token(Le, Some("<=".into())));
                } else {
                    tokens.push(self.scanner.create_token(Lt, Some("<".into())));
                }
            }
            '!' => {
                if self.scanner.match_char('=') {
                    tokens.push(self.scanner.create_token(Ne, Some("!=".into())));
                } else {
                    tokens.push(self.scanner.create_token(Not, Some("!".into())));
                }
            }
            _ => {}
        }
    }

    fn open_string(&mut self, quote: char) {
        self.in_string = true;
        self.quote_char = quote;
        self.current_string_val.clear();
    }

    fn scan_string_char(&mut self, tokens: &mut Vec<Token>) {
        let c = self.scanner.advance();
        if c == '\n' {
            return;
        }
        if c == '\\' {
            self.apply_string_escape();
            return;
        }
        if c == self.quote_char {
            tokens.push(self.scanner.create_token(
                TokenType::String,
                Some(self.current_string_val.clone()),
            ));
            self.in_string = false;
        } else {
            self.current_string_val.push(c);
        }
    }

    fn apply_string_escape(&mut self) {
        if self.scanner.peek(0) == '\n' {
            self.scanner.advance();
            return;
        }
        let next = self.scanner.advance();
        match next {
            'n' => self.current_string_val.push('\n'),
            't' => self.current_string_val.push('\t'),
            'r' => self.current_string_val.push('\r'),
            '\\' => self.current_string_val.push('\\'),
            '"' => self.current_string_val.push('"'),
            '\'' => self.current_string_val.push('\''),
            'b' => self.current_string_val.push('\u{8}'),
            'f' => self.current_string_val.push('\u{c}'),
            other => {
                self.current_string_val.push('\\');
                self.current_string_val.push(other);
            }
        }
    }

    fn skip_comment(&mut self) {
        while self.scanner.peek(0) != '\n' && !self.scanner.is_at_end() {
            self.scanner.advance();
        }
    }

    fn scan_identifier(&mut self, first_char: char, tokens: &mut Vec<Token>) {
        let mut value = String::new();
        value.push(first_char);
        self.scanner.advance();
        while !self.scanner.is_at_end() {
            let c = self.scanner.peek(0);
            if c.is_ascii_alphanumeric() || c == '_' {
                value.push(c);
                self.scanner.advance();
            } else {
                break;
            }
        }
        let ty = self
            .keywords
            .get(&value)
            .copied()
            .unwrap_or(TokenType::Identifier);
        tokens.push(self.scanner.create_token(ty, Some(value)));
    }

    fn scan_number(&mut self, first_char: char, tokens: &mut Vec<Token>) {
        let mut value = String::new();
        value.push(first_char);
        self.scanner.advance();
        // 十进制/浮点（语料面；hex/bin/oct 前缀 = 后续增量）
        while !self.scanner.is_at_end() && self.scanner.peek(0).is_ascii_digit() {
            value.push(self.scanner.peek(0));
            self.scanner.advance();
        }
        if self.scanner.peek(0) == '.' && self.scanner.peek(1).is_ascii_digit() {
            value.push('.');
            self.scanner.advance();
            while !self.scanner.is_at_end() && self.scanner.peek(0).is_ascii_digit() {
                value.push(self.scanner.peek(0));
                self.scanner.advance();
            }
        }
        tokens.push(self.scanner.create_token(TokenType::Number, Some(value)));
    }
}

/// 入口：IBC 源码 → token 流。
pub fn lex(source: &str) -> Vec<Token> {
    Lexer::new(source).tokenize()
}
