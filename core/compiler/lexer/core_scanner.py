from typing import List, Tuple, Optional
from core.compiler.common.tokens import Token, TokenType, SubState
from core.compiler.lexer.str_stream import StrStream
from core.compiler.common.diagnostics import DiagnosticReporter

class CoreTokenScanner:
    """
    Handles scanning of standard code tokens (identifiers, keywords, symbols, strings, behavior blocks).
    Maintains state for string parsing, parenthesis levels, and line continuation.
    """
    def __init__(self, scanner: StrStream, issue_tracker: DiagnosticReporter):
        self.scanner = scanner
        self.issue_tracker = issue_tracker
        
        # Internal State
        self.state_stack: List[SubState] = [SubState.NORMAL]
        self.paren_level = 0
        self.continuation_mode = False
        self.current_line_has_llm_def = False
        
        # String State
        self.is_raw_string = False
        self.quote_char = None
        self.current_string_val = ""
        
        self.is_new_line_flag = True # Track if we just finished a line

        self.KEYWORDS = {
            'import': TokenType.IMPORT, 'from': TokenType.FROM,
            'func': TokenType.FUNC, 'return': TokenType.RETURN,
            'lambda': TokenType.LAMBDA,
            'snapshot': TokenType.SNAPSHOT,
            'if': TokenType.IF, 'elif': TokenType.ELIF, 'else': TokenType.ELSE,
            'switch': TokenType.SWITCH, 'case': TokenType.CASE, 'default': TokenType.DEFAULT,
            'for': TokenType.FOR, 'while': TokenType.WHILE, 'in': TokenType.IN,
            'auto': TokenType.AUTO, 'fn': TokenType.FN, 'global': TokenType.GLOBAL, 'pass': TokenType.PASS,
            'break': TokenType.BREAK, 'continue': TokenType.CONTINUE,
            'try': TokenType.TRY, 'except': TokenType.EXCEPT,
            'finally': TokenType.FINALLY, 'raise': TokenType.RAISE,
            'class': TokenType.CLASS, 'self': TokenType.SELF,
            'as': TokenType.AS,
            'and': TokenType.AND, 'or': TokenType.OR, 'not': TokenType.NOT, 'is': TokenType.IS,
            'None': TokenType.NONE, 'Uncertain': TokenType.UNCERTAIN,
            'llm': TokenType.LLM_DEF, 'llmend': TokenType.LLM_END,
            'llmexcept': TokenType.LLM_EXCEPT, 
            'llmretry': TokenType.LLM_RETRY,
            'retry': TokenType.RETRY,
            '__sys__': TokenType.LLM_SYS, '__user__': TokenType.LLM_USER,
            '__llmretry__': TokenType.LLM_RETRY_HINT,
            'true': TokenType.TRUE, 'false': TokenType.FALSE
        }

    @property
    def sub_state(self) -> SubState:
        """获取当前子状态（栈顶）"""
        return self.state_stack[-1] if self.state_stack else SubState.NORMAL

    def push_state(self, new_state: SubState):
        """推入新状态"""
        self.state_stack.append(new_state)

    def pop_state(self) -> SubState:
        """弹出当前状态并返回"""
        if len(self.state_stack) > 1:
            return self.state_stack.pop()
        return SubState.NORMAL

    def get_snapshot(self) -> tuple:
        """获取当前扫描器完整逻辑快照"""
        return (
            self.scanner.get_snapshot(),
            list(self.state_stack),
            self.paren_level,
            self.is_raw_string,
            self.quote_char,
            self.current_string_val
        )

    def restore_snapshot(self, snapshot: tuple, tokens: List[Token], original_token_count: int):
        """恢复扫描器逻辑快照并回滚 Token 列表"""
        stream_snap, stack_snap, paren, raw, quote, s_val = snapshot
        self.scanner.restore_snapshot(stream_snap)
        self.state_stack = list(stack_snap)
        self.paren_level = paren
        self.is_raw_string = raw
        self.quote_char = quote
        self.current_string_val = s_val
        
        # 回滚 Token 列表
        if len(tokens) > original_token_count:
            del tokens[original_token_count:]

    def try_scan(self, tokens: List[Token], scan_func, *args) -> bool:
        """
        
        尝试执行特定的扫描函数。如果失败（抛出异常或返回 False），则回滚所有状态。
        """
        original_token_count = len(tokens)
        snapshot = self.get_snapshot()
        
        try:
            result = scan_func(tokens, *args)
            if result is False:
                self.restore_snapshot(snapshot, tokens, original_token_count)
                return False
            return True
        except Exception:
            self.restore_snapshot(snapshot, tokens, original_token_count)
            return False


    def scan_line(self) -> Tuple[List[Token], bool, bool]:
        """
        Scan tokens until the end of the current line (or logical line).
        
        Returns:
            Tuple[List[Token], bool, bool]:
            - List of generated tokens.
            - Boolean: True if a newline was fully processed (resetting indent check).
            - Boolean: True if LLM mode should be entered (LLM_DEF + COLON found).
        """
        tokens: List[Token] = []
        self.current_line_has_llm_def = False # Reset for new line scan
        enter_llm_mode = False
        
        # If we were in continuation mode, we are not at a "new line" for indentation purposes
        # But this is handled by Lexer before calling scan_line usually.
        # Here we just scan.

        while not self.scanner.is_at_end():
            char = self.scanner.peek()
            
            # 1. Handle newlines
            if char == '\n':
                should_return = self._handle_newline(tokens)
                if should_return:
                    return tokens, True, enter_llm_mode
                continue

            # 2. Dispatch based on sub-state
            if self.sub_state == SubState.NORMAL:
                enter_llm_mode = self._scan_normal_char(tokens) or enter_llm_mode
            elif self.sub_state == SubState.IN_STRING:
                self._scan_string_char(tokens)
            elif self.sub_state == SubState.IN_BEHAVIOR:
                self._scan_behavior_char(tokens)
            elif self.sub_state == SubState.IN_INTENT:
                self._scan_intent_char(tokens)
                
        return tokens, False, enter_llm_mode

    def check_eof_state(self):
        """Check for unclosed states at EOF."""
        if self.sub_state == SubState.IN_STRING:
            self.issue_tracker.error("Unexpected EOF while scanning string literal", self.scanner, code="LEX_002")
        elif self.sub_state == SubState.IN_BEHAVIOR:
            self.issue_tracker.error("Unexpected EOF while scanning behavior description", self.scanner, code="LEX_006")

    def _handle_newline(self, tokens: List[Token]) -> bool:
        """
        Handle newline character.
        Returns True if line processing ended, False if newline was consumed (e.g., in string).
        """
        current_state = self.sub_state
        
        # Case 1: In string
        if current_state == SubState.IN_STRING:
            self._scan_string_char(tokens)
            return False
        
        # Case 2: In behavior description
        elif current_state == SubState.IN_BEHAVIOR:
            tokens.append(Token(TokenType.RAW_TEXT, "\n", self.scanner.line, self.scanner.col))
            self.scanner.advance()
            return False
        
        # Case 2.1: In intent description
        elif current_state == SubState.IN_INTENT:
            # 意图在一行结束时自动退栈回到 NORMAL
            self.pop_state()
            self.scanner.advance()
            tokens.append(Token(TokenType.NEWLINE, "\n", self.scanner.line - 1, self.scanner.col))
            return True

        # Case 3: Implicit continuation (inside parentheses)
        elif self.paren_level > 0:
            self.scanner.advance()
            self.continuation_mode = True
            return True

        # Case 4: Explicit continuation (backslash)
        elif self.continuation_mode:
            self.scanner.advance()
            # continuation_mode remains True until cleared by Lexer (or next non-whitespace)
            # Actually Lexer clears it.
            return True

        # Case 5: Actual line end
        else:
            self.scanner.advance()
            tokens.append(Token(TokenType.NEWLINE, "\n", self.scanner.line - 1, self.scanner.col))
            return True

    def _scan_normal_char(self, tokens: List[Token]) -> bool:
        """
        Scan a character in normal mode.
        Returns True if LLM mode should be entered.
        """
        self.scanner.start_token()
        char = self.scanner.peek()

        # 1. Variable Reference (Support $ in NORMAL mode for 'intent $x:')
        # 使用尝试性扫描，避免物理回退
        if char == '$':
            self.try_scan(tokens, self._scan_var_ref)
            return False

        # 正常消费一个字符
        char = self.scanner.advance()
        
        # 2. Explicit line continuation
        if char == '\\':
            if self.scanner.peek() == '\n':
                self.continuation_mode = True
                return False
            else:
                self.issue_tracker.error(f"Unexpected character '\\' or invalid escape sequence", self.scanner, code="LEX_005")
                return False

        # 3. Whitespace
        if char in ' \t':
            return False

        # 4. Comments
        if char == '#':
            self._skip_comment() 
            return False

        # 5. Raw String Prefix
        if char == 'r' and (self.scanner.peek() == '"' or self.scanner.peek() == "'"):
            quote = self.scanner.advance()
            self.push_state(SubState.IN_STRING)
            self.quote_char = quote
            self.current_string_val = ""
            self.is_raw_string = True
            return False

        # 6. String Literals
        if char == '"' or char == "'":
            self.push_state(SubState.IN_STRING)
            self.quote_char = char
            self.current_string_val = ""
            self.is_raw_string = False
            return False

        # 7. Behavior Description and Intent Comments
        if char == '@':
            # Check for modifiers: @+, @!, @-
            mode = ""
            if self.scanner.peek() in '+!-':
                mode = self.scanner.advance()
            
            # Check for behavior marker: @~ or @tag~
            offset = 0
            while self.scanner.peek(offset).isalpha():
                offset += 1
            
            if self.scanner.peek(offset) == '~' and mode == "":
                # Behavior marker found!
                tag = ""
                for _ in range(offset):
                    tag += self.scanner.advance()
                self.scanner.advance() # Consume '~'
                self.push_state(SubState.IN_BEHAVIOR)
                tokens.append(self.scanner.create_token(TokenType.BEHAVIOR_MARKER, "@" + tag + "~"))
                return False
            else:
                # Regular Intent Comment or Modified Intent
                self.push_state(SubState.IN_INTENT)
                # Include @ in the value so parser knows it's an intent marker
                tokens.append(self.scanner.create_token(TokenType.INTENT, "@" + mode))
                return False

        # 8. Bitwise Not
        if char == '~':
            tokens.append(self.scanner.create_token(TokenType.BIT_NOT, "~"))
            return False

        # 8. Symbols
        if char == '(': 
            self.paren_level += 1
            tokens.append(self.scanner.create_token(TokenType.LPAREN))
            return False
        elif char == ')':
            self.paren_level = max(0, self.paren_level - 1)
            tokens.append(self.scanner.create_token(TokenType.RPAREN))
            return False
        elif char == '[': 
            self.paren_level += 1
            tokens.append(self.scanner.create_token(TokenType.LBRACKET))
            return False
        elif char == ']':
            self.paren_level = max(0, self.paren_level - 1)
            tokens.append(self.scanner.create_token(TokenType.RBRACKET))
            return False
        elif char == '{': 
            self.paren_level += 1
            tokens.append(self.scanner.create_token(TokenType.LBRACE))
            return False
        elif char == '}':
            self.paren_level = max(0, self.paren_level - 1)
            tokens.append(self.scanner.create_token(TokenType.RBRACE))
            return False
        
        if char == ',':
            tokens.append(self.scanner.create_token(TokenType.COMMA))
            return False
        if char == ':':
            tokens.append(self.scanner.create_token(TokenType.COLON))
            if self.current_line_has_llm_def:
                return True # Enter LLM Mode
            return False
        
        if char == '?':
            tokens.append(self.scanner.create_token(TokenType.QUESTION, "?"))
            return False

        if char == '=':
            if self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.EQ, "=="))
            else: tokens.append(self.scanner.create_token(TokenType.ASSIGN, "="))
            return False
            
        if char == '-':
            if self.scanner.match('>'): tokens.append(self.scanner.create_token(TokenType.ARROW, "->"))
            elif self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.MINUS_ASSIGN, "-="))
            else: tokens.append(self.scanner.create_token(TokenType.MINUS, "-"))
            return False
            
        if char == '+': 
            if self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.PLUS_ASSIGN, "+="))
            else: tokens.append(self.scanner.create_token(TokenType.PLUS))
            return False
        if char == '*': 
            if self.scanner.match('*'):
                if self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.STAR_STAR_ASSIGN, "**="))
                else: tokens.append(self.scanner.create_token(TokenType.STAR_STAR, "**"))
            elif self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.STAR_ASSIGN, "*="))
            else: tokens.append(self.scanner.create_token(TokenType.STAR))
            return False
        if char == '/': 
            if self.scanner.match('/'):
                if self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.FLOOR_DIV_ASSIGN, "//="))
                else: tokens.append(self.scanner.create_token(TokenType.FLOOR_DIV, "//"))
            elif self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.SLASH_ASSIGN, "/="))
            else: tokens.append(self.scanner.create_token(TokenType.SLASH))
            return False
        if char == '%': 
            if self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.PERCENT_ASSIGN, "%="))
            else: tokens.append(self.scanner.create_token(TokenType.PERCENT))
            return False
        if char == '.': 
            tokens.append(self.scanner.create_token(TokenType.DOT))
            return False
        
        if char == '>':
            if self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.GE, ">="))
            elif self.scanner.match('>'): tokens.append(self.scanner.create_token(TokenType.RSHIFT, ">>"))
            else: tokens.append(self.scanner.create_token(TokenType.GT, ">"))
            return False
        if char == '<':
            if self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.LE, "<="))
            elif self.scanner.match('<'): tokens.append(self.scanner.create_token(TokenType.LSHIFT, "<<"))
            else: tokens.append(self.scanner.create_token(TokenType.LT, "<"))
            return False
        if char == '!':
            if self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.NE, "!="))
            else: tokens.append(self.scanner.create_token(TokenType.NOT, "!"))
            return False
        
        # Bitwise operators
        if char == '&':
            tokens.append(self.scanner.create_token(TokenType.BIT_AND, "&"))
            return False
        if char == '|':
            tokens.append(self.scanner.create_token(TokenType.BIT_OR, "|"))
            return False
        if char == '^':
            tokens.append(self.scanner.create_token(TokenType.BIT_XOR, "^"))
            return False

        # 9. Identifiers / Numbers
        if char.isalpha() or char == '_' or '\u4e00' <= char <= '\u9fff':
            self._scan_identifier(char, tokens)
            return False
        if char.isdigit():
            self._scan_number(char, tokens)
            return False
            
        self.issue_tracker.error(f"Unexpected character '{char}'", self.scanner, code="LEX_001")
        return False

    def _scan_string_char(self, tokens: List[Token]):
        char = self.scanner.advance()
        
        if char == '\n':
            self.issue_tracker.error("EOL while scanning string literal", self.scanner, code="LEX_002")
            return

        if char == '\\':
            if self.scanner.peek() == '\n':
                # Explicit continuation inside string
                self.continuation_mode = True
                self.scanner.advance() # Consume newline
                return
            else:
                # Escape sequence handling
                if self.is_raw_string:
                    # Raw string: Keep backslash, but allow escaping quote
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
                    # Standard escape sequences
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
            tokens.append(self.scanner.create_token(TokenType.STRING, self.current_string_val))
            # 恢复之前状态 (回到意图或 NORMAL 模式)
            self.pop_state()
        else:
            self.current_string_val += char

    def _scan_behavior_char(self, tokens: List[Token]):
        char = self.scanner.peek()
        
        # 1. Check for closing marker ~
        if char == '~':
            self.scanner.advance() # ~
            tokens.append(self.scanner.create_token(TokenType.BEHAVIOR_MARKER, "~"))
            self.pop_state() # 退回到之前的模式
            return

        # 2. Handle escapes: \$, \~
        if char == '\\':
            next_char = self.scanner.peek(1)
            if next_char == '~':
                # \~ (single tilde)
                self.scanner.advance() # \
                self.scanner.advance() # ~
                tokens.append(Token(TokenType.RAW_TEXT, "~", self.scanner.line, self.scanner.col))
                return
            elif next_char == '$':
                # \$ (dollar sign)
                self.scanner.advance() # \
                self.scanner.advance() # $
                tokens.append(Token(TokenType.RAW_TEXT, "$", self.scanner.line, self.scanner.col))
                return

        # 3. String Literals (支持字符串内变量引用)
        if char == '"' or char == "'":
            self._scan_string_in_behavior(tokens)
            return

        # 4. Variable Reference
        # 行为块内部的变量引用目前被视为强制性的
        if char == '$':
            self._scan_var_ref(tokens)
            self._scan_complex_access(tokens)
            return
            
        # 5. Raw Text
        text = ""
        while not self.scanner.is_at_end():
            peek_char = self.scanner.peek()
            
            if peek_char == '$': 
                break
            if peek_char == '\n':
                break
            if peek_char == '~':
                break
            if peek_char == '\\':
                next_c = self.scanner.peek(1)
                if next_c == '~' or next_c == '$':
                    break
            if peek_char == '"' or peek_char == "'":
                break
                
            text += self.scanner.advance()
        
        if text:
            tokens.append(Token(TokenType.RAW_TEXT, text, self.scanner.line, self.scanner.col))

    def _scan_string_in_behavior(self, tokens: List[Token]):
        """扫描行为表达式中的字符串字面量，支持内部变量引用如 "$var" """
        quote_char = self.scanner.advance()  # consume opening quote
        string_content = ""
        
        while not self.scanner.is_at_end():
            char = self.scanner.peek()
            
            # 字符串结束
            if char == quote_char:
                self.scanner.advance()  # consume closing quote
                if string_content:
                    tokens.append(self.scanner.create_token(TokenType.STRING, string_content))
                return
            
            # 转义序列
            if char == '\\':
                next_char = self.scanner.peek(1)
                if next_char == quote_char or next_char == '\\' or next_char == 'n' or next_char == 't':
                    string_content += self.scanner.advance()  # \
                    string_content += self.scanner.advance()  # char
                    continue
                elif next_char == '$':
                    # \$
                    string_content += self.scanner.advance()  # \
                    string_content += self.scanner.advance()  # $
                    continue
            
            # 变量引用 - 先发出已累积的字符串内容
            if char == '$':
                if string_content:
                    tokens.append(self.scanner.create_token(TokenType.STRING, string_content))
                    string_content = ""
                # 处理变量引用
                self._scan_var_ref(tokens)
                self._scan_complex_access(tokens)
                continue
            
            # 换行 - 字符串不支持跨行
            if char == '\n':
                self.issue_tracker.error("Unexpected newline in string literal inside behavior expression", self.scanner, code="LEX_002")
                return
            
            string_content += self.scanner.advance()
        
        # 未闭合的字符串
        self.issue_tracker.error("Unterminated string literal in behavior expression", self.scanner, code="LEX_002")
        if string_content:
            tokens.append(self.scanner.create_token(TokenType.STRING, string_content))

    def _scan_intent_char(self, tokens: List[Token]):
        char = self.scanner.peek()
        
        # 1. Stop at newline (handled by _handle_newline)
        if char == '\n':
            return
            
        # 2. Variable Reference (使用尝试性扫描)
        # 意图模式下的 $ 可能是自然语言，也可能是插值变量
        if char == '$':
            if self.try_scan(tokens, self._scan_var_ref_with_access):
                return
            # 尝试失败则作为普通文本
            char = self.scanner.advance()
            tokens.append(Token(TokenType.RAW_TEXT, char, self.scanner.line, self.scanner.col))
            return

        # 3. String Literals (Quoted)
        if char == '"' or char == "'":
            # 进入字符串子模式
            self.push_state(SubState.IN_STRING)
            self.quote_char = self.scanner.advance() # consume quote
            self.current_string_val = ""
            self.is_raw_string = False
            return

        # 4. Raw Text
        text = ""
        while not self.scanner.is_at_end():
            peek_char = self.scanner.peek()
            if peek_char == '$' or peek_char == '\n':
                break
            if peek_char == '"' or peek_char == "'":
                break
                
            text += self.scanner.advance()
        
        if text:
            tokens.append(Token(TokenType.RAW_TEXT, text, self.scanner.line, self.scanner.col))

    def _scan_var_ref_with_access(self, tokens: List[Token]):
        """辅助方法：同时扫描变量引用和可能的复杂路径访问"""
        self._scan_var_ref(tokens)
        self._scan_complex_access(tokens)

    def _scan_complex_access(self, tokens: List[Token]):
        subscript_depth = 0
        while not self.scanner.is_at_end():
            peek = self.scanner.peek()
            
            if subscript_depth == 0:
                # Top-level: only allow .attr or [
                if peek == '.':
                    next_char = self.scanner.peek(1)
                    if next_char.isalpha() or next_char == '_' or '\u4e00' <= next_char <= '\u9fff':
                        self.scanner.start_token()
                        self.scanner.advance() # .
                        tokens.append(self.scanner.create_token(TokenType.DOT, "."))
                        
                        # Scan identifier
                        self.scanner.start_token()
                        id_val = ""
                        while not self.scanner.is_at_end() and (self.scanner.peek().isalnum() or self.scanner.peek() == '_' or '\u4e00' <= self.scanner.peek() <= '\u9fff'):
                            id_val += self.scanner.advance()
                        tokens.append(self.scanner.create_token(TokenType.IDENTIFIER, id_val))
                    else:
                        break # Literal dot after variable
                elif peek == '[':
                    self.scanner.start_token()
                    self.scanner.advance() # [
                    tokens.append(self.scanner.create_token(TokenType.LBRACKET, "["))
                    subscript_depth += 1
                else:
                    break # End of complex access chain
            else:
                # Inside subscript: allow digits, strings, identifiers, nested [. and ]
                if peek == ']':
                    self.scanner.start_token()
                    self.scanner.advance() # ]
                    tokens.append(self.scanner.create_token(TokenType.RBRACKET, "]"))
                    subscript_depth -= 1
                elif peek == '[':
                    self.scanner.start_token()
                    self.scanner.advance() # [
                    tokens.append(self.scanner.create_token(TokenType.LBRACKET, "["))
                    subscript_depth += 1
                elif peek == '.':
                    self.scanner.start_token()
                    self.scanner.advance() # .
                    tokens.append(self.scanner.create_token(TokenType.DOT, "."))
                elif peek.isdigit():
                    self.scanner.start_token()
                    num_val = ""
                    while self.scanner.peek().isdigit():
                        num_val += self.scanner.advance()
                    tokens.append(self.scanner.create_token(TokenType.NUMBER, num_val))
                elif peek == '"' or peek == "'":
                    quote = self.scanner.advance()
                    self.scanner.start_token()
                    s_val = ""
                    while not self.scanner.is_at_end() and self.scanner.peek() != quote:
                        s_val += self.scanner.advance()
                    if not self.scanner.is_at_end():
                        self.scanner.advance() # closing quote
                        tokens.append(self.scanner.create_token(TokenType.STRING, s_val))
                    else:
                        # This is a real unclosed string error
                        self.issue_tracker.error("Unclosed string literal in behavior subscript", self.scanner, code="LEX_002")
                        break
                elif peek.isalpha() or peek == '_' or '\u4e00' <= peek <= '\u9fff':
                    self.scanner.start_token()
                    id_val = ""
                    while not self.scanner.is_at_end() and (self.scanner.peek().isalnum() or self.scanner.peek() == '_' or '\u4e00' <= self.scanner.peek() <= '\u9fff'):
                        id_val += self.scanner.advance()
                    tokens.append(self.scanner.create_token(TokenType.IDENTIFIER, id_val))
                elif peek in ' \t':
                    # Allow spaces inside subscripts
                    self.scanner.advance()
                elif peek == '\n' or peek == '~':
                    # Behavior block ends before subscript closed!
                    break
                else:
                    # Unexpected character in subscript. Break and let parser handle it.
                    break
        
        if subscript_depth > 0:
            self.issue_tracker.error(f"Unclosed subscript '[' in behavior expression (depth: {subscript_depth})", self.scanner, code="LEX_003")

    def _scan_identifier(self, first_char: str, tokens: List[Token]):
        value = first_char
        while not self.scanner.is_at_end() and (self.scanner.peek().isalnum() or self.scanner.peek() == '_' or '\u4e00' <= self.scanner.peek() <= '\u9fff'):
            value += self.scanner.advance()
            
        if value in self.KEYWORDS:
            type = self.KEYWORDS[value]
            tokens.append(self.scanner.create_token(type, value, self.is_new_line_flag))
            
            if type == TokenType.LLM_DEF:
                self.current_line_has_llm_def = True
                
            elif type == TokenType.AND or type == TokenType.OR:
                # Logical operators implicitly continue at EOL
                offset = 0
                while self.scanner.peek(offset) in ' \t':
                    offset += 1
                
                char = self.scanner.peek(offset)
                if char == '\n' or char == '#':
                    self.continuation_mode = True

        else:
            tokens.append(self.scanner.create_token(TokenType.IDENTIFIER, value, self.is_new_line_flag))
            
        self.is_new_line_flag = False

    def _is_at_expression_start(self) -> bool:
        """检查是否处于表达式开头（用于判断负号是负号还是减号）"""
        idx = self.scanner.pos
        while idx > 0:
            pos = idx - 1
            if pos < 0:
                break
            char = self.scanner.source[pos]
            if char == ' ' or char == '\t':
                idx = pos
                continue
            if char == '\n':
                return True
            if char in '+-*/%=<>!&|,':
                return True
            return False
        return True

    def _scan_number(self, first_char: str, tokens: List[Token]):
        value = first_char
        
        # 1. Hexadecimal (0x...)
        if first_char == '0' and (self.scanner.peek() == 'x' or self.scanner.peek() == 'X'):
            value += self.scanner.advance()
            while not self.scanner.is_at_end() and (self.scanner.peek().isdigit() or self.scanner.peek() in 'abcdefABCDEF'):
                value += self.scanner.advance()
            tokens.append(self.scanner.create_token(TokenType.NUMBER, value))
            self.is_new_line_flag = False
            return

        # 2. Binary (0b...)
        if first_char == '0' and (self.scanner.peek() == 'b' or self.scanner.peek() == 'B'):
            value += self.scanner.advance()
            while not self.scanner.is_at_end() and self.scanner.peek() in '01':
                value += self.scanner.advance()
            tokens.append(self.scanner.create_token(TokenType.NUMBER, value))
            self.is_new_line_flag = False
            return

        # 2b. Octal (0o...)
        if first_char == '0' and (self.scanner.peek() == 'o' or self.scanner.peek() == 'O'):
            value += self.scanner.advance()
            while not self.scanner.is_at_end() and self.scanner.peek() in '01234567':
                value += self.scanner.advance()
            tokens.append(self.scanner.create_token(TokenType.NUMBER, value))
            self.is_new_line_flag = False
            return

        # 3. Decimal / Float
        while self.scanner.peek().isdigit():
            value += self.scanner.advance()
            
        # Fraction part
        if self.scanner.peek() == '.' and self.scanner.peek(1).isdigit():
            value += self.scanner.advance()
            while self.scanner.peek().isdigit():
                value += self.scanner.advance()
                
        # Scientific notation
        if self.scanner.peek() in 'eE':
            next_char = self.scanner.peek(1)
            if next_char.isdigit() or next_char in '+-':
                value += self.scanner.advance() # 'e' or 'E'
                if self.scanner.peek() in '+-':
                    value += self.scanner.advance()
                while self.scanner.peek().isdigit():
                    value += self.scanner.advance()

        # Check for negative number
        # Only treat as negative if this is at the start of an expression (after whitespace, operator, or at beginning of line)
        if self.is_new_line_flag or self._is_at_expression_start():
            if self.scanner.peek() == '-':
                self.scanner.advance()
                next_char = self.scanner.peek()
                if next_char.isdigit():
                    value = '-' + value
                    while self.scanner.peek().isdigit():
                        value += self.scanner.advance()
                    # Check for negative float
                    if self.scanner.peek() == '.' and self.scanner.peek(1).isdigit():
                        value += self.scanner.advance()
                        while self.scanner.peek().isdigit():
                            value += self.scanner.advance()

        tokens.append(self.scanner.create_token(TokenType.NUMBER, value))
        self.is_new_line_flag = False

    def _scan_var_ref(self, tokens: List[Token]):
        self.scanner.start_token()
        self.scanner.advance() # $
        name = ""
        
        if not self.scanner.is_at_end() and (self.scanner.peek().isalnum() or self.scanner.peek() == '_' or '\u4e00' <= self.scanner.peek() <= '\u9fff'):
            name += self.scanner.advance()
        else:
            self.issue_tracker.warning(r"Empty variable reference '$'. Did you mean '\$'?", self.scanner, code="LEX_001")

        while not self.scanner.is_at_end():
            peek = self.scanner.peek()
            if peek.isalnum() or peek == '_' or '\u4e00' <= peek <= '\u9fff':
                name += self.scanner.advance()
            else:
                break
                
        tokens.append(self.scanner.create_token(TokenType.VAR_REF, "$" + name))

    def _skip_comment(self):
        """Skip comments until end of line (do not consume newline)."""
        while self.scanner.peek() != '\n' and not self.scanner.is_at_end():
            self.scanner.advance()
