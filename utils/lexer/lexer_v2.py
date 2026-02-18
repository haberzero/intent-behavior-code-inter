from typing import List, Optional
from typedef.lexer_types import TokenType, Token, LexerMode, SubState
from .scanner import Scanner
from typedef.exception_types import LexerError

class LexerV2:
    """
    IBC-Inter 词法分析器 (Lexer V2)
    改进版：移除硬编码的容器类型，使其能被识别为标识符，从而支持更灵活的类型系统。
    """
    def __init__(self, source_code: str):
        self.scanner = Scanner(source_code)
        self.tokens: List[Token] = []
        
        # 状态管理
        self.mode_stack: List[LexerMode] = [LexerMode.NORMAL]
        self.indent_stack: List[int] = [0]
        self.sub_state = SubState.NORMAL
        self.paren_level = 0
        self.continuation_mode = False
        self.current_line_has_llm_def = False
        
        # 关键字映射
        self.KEYWORDS = {
            'import': TokenType.IMPORT, 'from': TokenType.FROM,
            'func': TokenType.FUNC, 'return': TokenType.RETURN,
            'if': TokenType.IF, 'elif': TokenType.ELIF, 'else': TokenType.ELSE,
            'for': TokenType.FOR, 'while': TokenType.WHILE, 'in': TokenType.IN,
            'var': TokenType.VAR, 'pass': TokenType.PASS,
            'break': TokenType.BREAK, 'continue': TokenType.CONTINUE,
            'as': TokenType.AS,
            'and': TokenType.AND, 'or': TokenType.OR, 'not': TokenType.NOT, 'is': TokenType.IS,
            'llm': TokenType.LLM_DEF, 'llmend': TokenType.LLM_END,
            '__sys__': TokenType.LLM_SYS, '__user__': TokenType.LLM_USER,
            'True': TokenType.BOOL, 'False': TokenType.BOOL
        }
        
        # V2 Change: Removed 'list', 'dict' from TYPES. 
        # They will be tokenized as IDENTIFIER, allowing the Parser to handle them as types or variables.
        # Added 'bool', 'void', 'Any' for completeness.
        self.TYPES = {'int', 'float', 'str', 'bool', 'void', 'Any', 'None'}
        self.is_new_line = True

    def tokenize(self) -> List[Token]:
        while not self.scanner.is_at_end():
            self._process_line()
            
        # 检查残留状态（防御性检查）
        if self.sub_state == SubState.IN_STRING:
            raise LexerError("Unexpected EOF while scanning string literal", self.scanner.line, self.scanner.col)
        if self.sub_state == SubState.IN_BEHAVIOR:
            raise LexerError("Unexpected EOF while scanning behavior description", self.scanner.line, self.scanner.col)
        
        # 处理文件末尾的剩余缩进
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.append(Token(TokenType.DEDENT, "", self.scanner.line, 0))
            
        self.tokens.append(Token(TokenType.EOF, "", self.scanner.line, 0))
        return self.tokens

    # ==========================
    # 行处理器
    # ==========================

    def _process_line(self):
        """处理单行内容，包括缩进和模式分发。"""
        self.current_line_has_llm_def = False
        current_mode = self.mode_stack[-1]
        
        # 1. 处理缩进
        should_handle_indent = (
            current_mode == LexerMode.NORMAL and 
            not self.continuation_mode and 
            self.paren_level == 0 and 
            self.sub_state == SubState.NORMAL and
            self.is_new_line
        )

        if should_handle_indent:
            indent = self._handle_indentation()
            if indent is None:
                return 
        else:
            if current_mode == LexerMode.NORMAL:
                self._skip_whitespace()
                if self.continuation_mode:
                    self.continuation_mode = False

        # 2. 委托内容扫描
        if current_mode == LexerMode.NORMAL:
            self._scan_code_chunk()
        elif current_mode == LexerMode.LLM_BLOCK:
            self._scan_llm_chunk()

    def _handle_indentation(self) -> Optional[int]:
        """计算并生成 INDENT/DEDENT Token。空行或注释行返回 None。"""
        start_col = self.scanner.col
        spaces = 0
        
        while self.scanner.peek() in ' \t':
            self.scanner.advance()
            spaces += 1
            
        if self.scanner.peek() == '\n':
            self.scanner.advance()
            return None
        if self.scanner.peek() == '#':
            self._skip_comment()
            if self.scanner.peek() == '\n':
                self.scanner.advance()
            return None
        if self.scanner.is_at_end():
            return None

        current_indent = spaces
        last_indent = self.indent_stack[-1]
        
        if current_indent > last_indent:
            self.indent_stack.append(current_indent)
            self.tokens.append(Token(TokenType.INDENT, "", self.scanner.line, start_col))
        elif current_indent < last_indent:
            while current_indent < self.indent_stack[-1]:
                self.indent_stack.pop()
                self.tokens.append(Token(TokenType.DEDENT, "", self.scanner.line, start_col))
            
            if current_indent != self.indent_stack[-1]:
                raise LexerError("Unindent does not match any outer indentation level", self.scanner.line, start_col)
        
        self.is_new_line = True
        return current_indent

    def _skip_whitespace(self):
        """跳过空格和制表符，但不包括换行符。"""
        while self.scanner.peek() in ' \t':
            self.scanner.advance()

    def _skip_comment(self):
        """跳过注释直到行尾（不消耗换行符）。"""
        while self.scanner.peek() != '\n' and not self.scanner.is_at_end():
            self.scanner.advance()

    # ==========================
    # 第二层：Token 扫描器
    # ==========================

    def _scan_code_chunk(self):
        """扫描代码内容直到行尾。"""
        
        while not self.scanner.is_at_end():
            char = self.scanner.peek()
            
            # 1. 处理换行符
            if char == '\n':
                should_return = self._handle_newline()
                if should_return:
                    return
                continue

            # 2. 基于子状态分发
            if self.sub_state == SubState.NORMAL:
                self._scan_normal_char()
            elif self.sub_state == SubState.IN_STRING:
                self._scan_string_char()
            elif self.sub_state == SubState.IN_BEHAVIOR:
                self._scan_behavior_char()

    def _handle_newline(self) -> bool:
        """
        处理换行符。
        :return: True 表示行处理结束，False 表示换行符已被消耗（如在字符串中）。
        """
        # 情况 1：在字符串中
        if self.sub_state == SubState.IN_STRING:
            self._scan_string_char()
            return False
        
        # 情况 2：在行为描述中
        elif self.sub_state == SubState.IN_BEHAVIOR:
            # 允许跨行，将换行符作为 RAW_TEXT
            self.tokens.append(Token(TokenType.RAW_TEXT, "\n", self.scanner.line, self.scanner.col))
            self.scanner.advance()
            return False

        # 情况 3：隐式延续（括号内）
        elif self.paren_level > 0:
            self.scanner.advance()
            self.continuation_mode = True
            return True

        # 情况 4：显式延续（反斜杠）
        elif self.continuation_mode:
            self.scanner.advance()
            return True

        # 情况 5：实际行结束
        else:
            self.scanner.advance()
            self.tokens.append(Token(TokenType.NEWLINE, "\n", self.scanner.line - 1, self.scanner.col))
            self.is_new_line = True
            return True

    def _scan_normal_char(self):
        self.scanner.start_token()
        char = self.scanner.advance()
        
        # 1. 显式行延续
        if char == '\\':
            if self.scanner.peek() == '\n':
                self.continuation_mode = True
                return
            else:
                raise LexerError(f"Unexpected character '\\' or invalid escape sequence", self.scanner.line, self.scanner.col)

        # 2. 空白字符
        if char in ' \t':
            return

        # 3. 注释
        if char == '#':
            self._skip_comment() 
            return

        # 4. Raw String Prefix (r"..." or r'...')
        if char == 'r' and (self.scanner.peek() == '"' or self.scanner.peek() == "'"):
            quote = self.scanner.advance()
            self.sub_state = SubState.IN_STRING
            self.quote_char = quote
            self.current_string_val = ""
            self.is_raw_string = True  # New flag for raw strings
            return

        # 5. 字符串字面量
        if char == '"' or char == "'":
            self.sub_state = SubState.IN_STRING
            self.quote_char = char
            self.current_string_val = ""
            self.is_raw_string = False
            return

        # 6. 意图注释
        if char == '@':
            content = ""
            while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
                content += self.scanner.advance()
            self.tokens.append(self.scanner.create_token(TokenType.INTENT, content))
            return

        # 7. 行为描述与位运算符
        if char == '~':
            # 检查是否为双波浪号 ~~
            if self.scanner.peek() == '~':
                self.scanner.advance()
                self.sub_state = SubState.IN_BEHAVIOR
                self.tokens.append(self.scanner.create_token(TokenType.BEHAVIOR_MARKER, "~~"))
                return
            else:
                # 单波浪号 -> 位非运算符
                self.tokens.append(self.scanner.create_token(TokenType.BIT_NOT, "~"))
                return

        # 8. 符号
        if char == '(': 
            self.paren_level += 1
            self.tokens.append(self.scanner.create_token(TokenType.LPAREN))
            return
        elif char == ')':
            self.paren_level = max(0, self.paren_level - 1)
            self.tokens.append(self.scanner.create_token(TokenType.RPAREN))
            return
        elif char == '[': 
            self.paren_level += 1
            self.tokens.append(self.scanner.create_token(TokenType.LBRACKET))
            return
        elif char == ']':
            self.paren_level = max(0, self.paren_level - 1)
            self.tokens.append(self.scanner.create_token(TokenType.RBRACKET))
            return
        elif char == '{': 
            self.paren_level += 1
            self.tokens.append(self.scanner.create_token(TokenType.LBRACE))
            return
        elif char == '}':
            self.paren_level = max(0, self.paren_level - 1)
            self.tokens.append(self.scanner.create_token(TokenType.RBRACE))
            return
        
        if char == ',':
            self.tokens.append(self.scanner.create_token(TokenType.COMMA))
            return
        if char == ':':
            self.tokens.append(self.scanner.create_token(TokenType.COLON))
            if self.current_line_has_llm_def:
                self.mode_stack.append(LexerMode.LLM_BLOCK)
            return
            
        if char == '=':
            if self.scanner.match('='): self.tokens.append(self.scanner.create_token(TokenType.EQ, "=="))
            else: self.tokens.append(self.scanner.create_token(TokenType.ASSIGN, "="))
            return
            
        if char == '-':
            if self.scanner.match('>'): self.tokens.append(self.scanner.create_token(TokenType.ARROW, "->"))
            elif self.scanner.match('='): self.tokens.append(self.scanner.create_token(TokenType.MINUS_ASSIGN, "-="))
            else: self.tokens.append(self.scanner.create_token(TokenType.MINUS, "-"))
            return
            
        if char == '+': 
            if self.scanner.match('='): self.tokens.append(self.scanner.create_token(TokenType.PLUS_ASSIGN, "+="))
            else: self.tokens.append(self.scanner.create_token(TokenType.PLUS))
            return
        if char == '*': 
            if self.scanner.match('='): self.tokens.append(self.scanner.create_token(TokenType.STAR_ASSIGN, "*="))
            else: self.tokens.append(self.scanner.create_token(TokenType.STAR))
            return
        if char == '/': 
            if self.scanner.match('='): self.tokens.append(self.scanner.create_token(TokenType.SLASH_ASSIGN, "/="))
            else: self.tokens.append(self.scanner.create_token(TokenType.SLASH))
            return
        if char == '%': 
            if self.scanner.match('='): self.tokens.append(self.scanner.create_token(TokenType.PERCENT_ASSIGN, "%="))
            else: self.tokens.append(self.scanner.create_token(TokenType.PERCENT))
            return
        if char == '.': 
            self.tokens.append(self.scanner.create_token(TokenType.DOT))
            return
        
        if char == '>':
            if self.scanner.match('='): self.tokens.append(self.scanner.create_token(TokenType.GE, ">="))
            elif self.scanner.match('>'): self.tokens.append(self.scanner.create_token(TokenType.RSHIFT, ">>"))
            else: self.tokens.append(self.scanner.create_token(TokenType.GT, ">"))
            return
        if char == '<':
            if self.scanner.match('='): self.tokens.append(self.scanner.create_token(TokenType.LE, "<="))
            elif self.scanner.match('<'): self.tokens.append(self.scanner.create_token(TokenType.LSHIFT, "<<"))
            else: self.tokens.append(self.scanner.create_token(TokenType.LT, "<"))
            return
        if char == '!':
            if self.scanner.match('='): self.tokens.append(self.scanner.create_token(TokenType.NE, "!="))
            return
        
        # Bitwise operators
        if char == '&':
            self.tokens.append(self.scanner.create_token(TokenType.BIT_AND, "&"))
            return
        if char == '|':
            self.tokens.append(self.scanner.create_token(TokenType.BIT_OR, "|"))
            return
        if char == '^':
            self.tokens.append(self.scanner.create_token(TokenType.BIT_XOR, "^"))
            return

        # 9. 标识符 / 数字
        if char.isalpha() or char == '_' or '\u4e00' <= char <= '\u9fff':
            self._scan_identifier(char)
            return
        if char.isdigit():
            self._scan_number(char)
            return
            
        raise LexerError(f"Unexpected character '{char}'", self.scanner.line, self.scanner.col)

    def _scan_string_char(self):
        char = self.scanner.advance()
        
        if char == '\n':
            raise LexerError("EOL while scanning string literal", self.scanner.line, self.scanner.col)

        if char == '\\':
            if self.scanner.peek() == '\n':
                # 字符串内的显式延续
                self.continuation_mode = True
                self.scanner.advance() # 消耗换行符
                return
            else:
                # 转义序列处理
                if self.is_raw_string:
                    # Raw string: 保留反斜杠，但允许转义引号
                    next_char = self.scanner.peek()
                    if next_char == self.quote_char:
                        self.scanner.advance() # Consume quote
                        self.current_string_val += "\\" + next_char # Keep backslash
                    elif next_char == '\\':
                        # Handle double backslash to prevent escaping a following quote
                        self.scanner.advance()
                        self.current_string_val += "\\\\" 
                    else:
                        self.current_string_val += "\\" # Just keep backslash
                    return
                else:
                    # 标准转义序列
                    next_char = self.scanner.advance()
                    ESCAPE_SEQUENCES = {
                        'n': '\n', 't': '\t', 'r': '\r', 
                        '\\': '\\', '"': '"', "'": "'",
                        'b': '\b', 'f': '\f'
                    }
                    if next_char in ESCAPE_SEQUENCES:
                        self.current_string_val += ESCAPE_SEQUENCES[next_char]
                    else:
                        self.current_string_val += "\\" + next_char
                    return

        if char == self.quote_char:
            self.tokens.append(self.scanner.create_token(TokenType.STRING, self.current_string_val))
            self.sub_state = SubState.NORMAL
        else:
            self.current_string_val += char

    def _scan_behavior_char(self):
        char = self.scanner.peek()
        
        # 1. 检查结束标记 ~~
        if char == '~' and self.scanner.peek(1) == '~':
            self.scanner.advance() # ~
            self.scanner.advance() # ~
            self.tokens.append(self.scanner.create_token(TokenType.BEHAVIOR_MARKER, "~~"))
            self.sub_state = SubState.NORMAL
            return

        # 2. 处理转义: \~~, \$, \~
        if char == '\\':
            next_char = self.scanner.peek(1)
            if next_char == '~':
                # Check for \~~ (double tilde)
                if self.scanner.peek(2) == '~':
                    self.scanner.advance() # \
                    self.scanner.advance() # ~
                    self.scanner.advance() # ~
                    self.tokens.append(Token(TokenType.RAW_TEXT, "~~", self.scanner.line, self.scanner.col))
                    return
                else:
                    # \~ (single tilde)
                    self.scanner.advance() # \
                    self.scanner.advance() # ~
                    self.tokens.append(Token(TokenType.RAW_TEXT, "~", self.scanner.line, self.scanner.col))
                    return
            elif next_char == '$':
                # \$ (dollar sign)
                self.scanner.advance() # \
                self.scanner.advance() # $
                self.tokens.append(Token(TokenType.RAW_TEXT, "$", self.scanner.line, self.scanner.col))
                return
            
            # 其他反斜杠保持原样，作为 Raw Text 的一部分
            # Fall through to raw text handling

        # 3. 变量引用
        if char == '$':
            self._scan_var_ref()
            return
            
        # 4. 原始文本
        text = ""
        while not self.scanner.is_at_end():
            peek_char = self.scanner.peek()
            
            if peek_char == '$': 
                break
            if peek_char == '\n':
                break
            if peek_char == '~' and self.scanner.peek(1) == '~':
                break
            if peek_char == '\\':
                next_c = self.scanner.peek(1)
                if next_c == '~' or next_c == '$':
                    break
                
            text += self.scanner.advance()
        
        if text:
            self.tokens.append(Token(TokenType.RAW_TEXT, text, self.scanner.line, self.scanner.col))

    def _scan_identifier(self, first_char):
        value = first_char
        while not self.scanner.is_at_end() and (self.scanner.peek().isalnum() or self.scanner.peek() == '_' or '\u4e00' <= self.scanner.peek() <= '\u9fff'):
            value += self.scanner.advance()
            
        if value in self.KEYWORDS:
            type = self.KEYWORDS[value]
            self.tokens.append(self.scanner.create_token(type, value, self.is_new_line))
            
            if type == TokenType.LLM_DEF:
                self.current_line_has_llm_def = True
                
            elif type == TokenType.AND or type == TokenType.OR:
                # 逻辑运算符在行末隐式延续
                offset = 0
                while self.scanner.peek(offset) in ' \t':
                    offset += 1
                
                char = self.scanner.peek(offset)
                if char == '\n' or char == '#':
                    self.continuation_mode = True

        elif value in self.TYPES:
            self.tokens.append(self.scanner.create_token(TokenType.TYPE_NAME, value, self.is_new_line))
        else:
            self.tokens.append(self.scanner.create_token(TokenType.IDENTIFIER, value, self.is_new_line))
            
        self.is_new_line = False

    def _scan_number(self, first_char):
        value = first_char
        while self.scanner.peek().isdigit():
            value += self.scanner.advance()
        if self.scanner.peek() == '.' and self.scanner.peek(1).isdigit():
            value += self.scanner.advance()
            while self.scanner.peek().isdigit():
                value += self.scanner.advance()
        
        self.tokens.append(self.scanner.create_token(TokenType.NUMBER, value))
        self.is_new_line = False

    def _scan_var_ref(self):
        self.scanner.start_token()
        self.scanner.advance() # $
        name = ""
        while not self.scanner.is_at_end() and (self.scanner.peek().isalnum() or self.scanner.peek() == '_' or '\u4e00' <= self.scanner.peek() <= '\u9fff'):
            name += self.scanner.advance()
        self.tokens.append(self.scanner.create_token(TokenType.VAR_REF, "$" + name))

    def _scan_llm_chunk(self):
        # 检查行首关键字
        offset = 0
        while self.scanner.peek(offset) in ' \t':
            offset += 1
        
        # 定义需要检查的关键字及其对应的 Token 类型
        llm_keywords = [
            ('llmend', TokenType.LLM_END),
            ('__sys__', TokenType.LLM_SYS),
            ('__user__', TokenType.LLM_USER)
        ]
        
        for keyword, token_type in llm_keywords:
            if self._match_llm_keyword(offset, keyword):
                if offset > 0:
                    pass
                self._consume_llm_keyword(offset, keyword, token_type)
                
                if token_type == TokenType.LLM_END:
                    self.mode_stack.pop()
                return

        # 常规提示文本
        text = ""
        start_line = self.scanner.line
        start_col = self.scanner.col
        
        while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
            if self.scanner.peek() == '$' and self.scanner.peek(1) == '_' and self.scanner.peek(2) == '_':
                if text:
                    self.tokens.append(Token(TokenType.RAW_TEXT, text, start_line, start_col))
                    text = ""
                self._scan_param_placeholder()
                start_line = self.scanner.line
                start_col = self.scanner.col
            else:
                text += self.scanner.advance()
        
        if text:
            self.tokens.append(Token(TokenType.RAW_TEXT, text, start_line, start_col))
            
        if self.scanner.peek() == '\n':
            self.scanner.advance()
            self.tokens.append(Token(TokenType.NEWLINE, "\n", self.scanner.line, self.scanner.col))

    def _scan_param_placeholder(self):
        self.scanner.start_token()
        self.scanner.advance() # $
        self.scanner.advance() # _
        self.scanner.advance() # _
        while not self.scanner.is_at_end() and not (self.scanner.peek() == '_' and self.scanner.peek(1) == '_'):
            self.scanner.advance()
        if not self.scanner.is_at_end():
            self.scanner.advance()
            self.scanner.advance()
        self.tokens.append(self.scanner.create_token(TokenType.PARAM_PLACEHOLDER))

    def _match_llm_keyword(self, offset: int, keyword: str) -> bool:
        length = len(keyword)
        for i in range(length):
            if self.scanner.peek(offset + i) != keyword[i]:
                return False
        # Boundary check
        next_char = self.scanner.peek(offset + length)
        if next_char.isalnum() or next_char == '_':
            return False
        return True

    def _consume_llm_keyword(self, offset: int, keyword: str, token_type: TokenType):
        for _ in range(offset): self.scanner.advance()
        self.scanner.start_token()
        for _ in range(len(keyword)): self.scanner.advance()
        self.tokens.append(self.scanner.create_token(token_type))
        # 消耗行剩余部分
        while self.scanner.peek() != '\n' and not self.scanner.is_at_end():
            self.scanner.advance()
        if self.scanner.peek() == '\n':
            self.scanner.advance()
