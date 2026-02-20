from typing import List, Optional
from typedef.lexer_types import TokenType, Token, LexerMode, SubState
from .scanner import Scanner
from utils.diagnostics.issue_tracker import IssueTracker
from utils.diagnostics.codes import *
from typedef.diagnostic_types import Severity

class Lexer:
    """
    IBC-Inter Lexer.
    Responsible for converting source code into Token stream, handling indentation, line continuation, and LLM block boundaries.
    """
    def __init__(self, source_code: str, issue_tracker: Optional[IssueTracker] = None):
        self.scanner = Scanner(source_code)
        self.tokens: List[Token] = []
        self.issue_tracker = issue_tracker or IssueTracker(source_code)
        
        # State Management
        self.mode_stack: List[LexerMode] = [LexerMode.NORMAL]
        self.indent_stack: List[int] = [0]
        self.sub_state = SubState.NORMAL
        self.paren_level = 0
        self.continuation_mode = False
        self.current_line_has_llm_def = False
        
        # Keyword Mapping
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
        
        self.is_new_line = True

    def tokenize(self) -> List[Token]:
        try:
            while not self.scanner.is_at_end():
                self._process_line()
                
            # Check residual state (defensive check)
            if self.sub_state == SubState.IN_STRING:
                self.issue_tracker.report(Severity.ERROR, LEX_UNTERMINATED_STRING, "Unexpected EOF while scanning string literal", self.scanner)
            if self.sub_state == SubState.IN_BEHAVIOR:
                self.issue_tracker.report(Severity.ERROR, LEX_UNTERMINATED_BEHAVIOR, "Unexpected EOF while scanning behavior description", self.scanner)
            
            # Handle remaining indentation at EOF
            while len(self.indent_stack) > 1:
                self.indent_stack.pop()
                self.tokens.append(Token(TokenType.DEDENT, "", self.scanner.line, 0))
                
            self.tokens.append(Token(TokenType.EOF, "", self.scanner.line, 0))
            
            # Throw exception if errors exist
            self.issue_tracker.check_errors()
            
            return self.tokens
        except Exception as e:
            # Ensure non-Diagnostic exceptions are propagated
            # If it's CompilerError, raise directly
            raise e

    def _report_error(self, code: str, message: str):
        """Helper to report lexical errors."""
        self.issue_tracker.report(Severity.ERROR, code, message, self.scanner)

    # ==========================
    # Line Processor
    # ==========================

    def _process_line(self):
        """Process single line, including indentation and mode dispatch."""
        self.current_line_has_llm_def = False
        current_mode = self.mode_stack[-1]
        
        # 1. Handle indentation
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

        # 2. Delegate content scanning
        if current_mode == LexerMode.NORMAL:
            self._scan_code_chunk()
        elif current_mode == LexerMode.LLM_BLOCK:
            self._scan_llm_chunk()

    def _handle_indentation(self) -> Optional[int]:
        """Calculate and generate INDENT/DEDENT tokens. Return None for empty or comment lines."""
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
                self._report_error(PAR_INDENTATION_ERROR, "Unindent does not match any outer indentation level")
        
        self.is_new_line = True
        return current_indent

    def _skip_whitespace(self):
        """Skip spaces and tabs, but not newlines."""
        while self.scanner.peek() in ' \t':
            self.scanner.advance()

    def _skip_comment(self):
        """Skip comments until end of line (do not consume newline)."""
        while self.scanner.peek() != '\n' and not self.scanner.is_at_end():
            self.scanner.advance()

    # ==========================
    # Layer 2: Token Scanner
    # ==========================

    def _scan_code_chunk(self):
        """Scan code content until end of line."""
        
        while not self.scanner.is_at_end():
            char = self.scanner.peek()
            
            # 1. Handle newlines
            if char == '\n':
                should_return = self._handle_newline()
                if should_return:
                    return
                continue

            # 2. Dispatch based on sub-state
            if self.sub_state == SubState.NORMAL:
                self._scan_normal_char()
            elif self.sub_state == SubState.IN_STRING:
                self._scan_string_char()
            elif self.sub_state == SubState.IN_BEHAVIOR:
                self._scan_behavior_char()

    def _handle_newline(self) -> bool:
        """
        Handle newline character.
        :return: True if line processing ended, False if newline was consumed (e.g., in string).
        """
        # Case 1: In string
        if self.sub_state == SubState.IN_STRING:
            self._scan_string_char()
            return False
        
        # Case 2: In behavior description
        elif self.sub_state == SubState.IN_BEHAVIOR:
            # Allow multi-line, treat newline as RAW_TEXT
            self.tokens.append(Token(TokenType.RAW_TEXT, "\n", self.scanner.line, self.scanner.col))
            self.scanner.advance()
            return False

        # Case 3: Implicit continuation (inside parentheses)
        elif self.paren_level > 0:
            self.scanner.advance()
            self.continuation_mode = True
            return True

        # Case 4: Explicit continuation (backslash)
        elif self.continuation_mode:
            self.scanner.advance()
            return True

        # Case 5: Actual line end
        else:
            self.scanner.advance()
            self.tokens.append(Token(TokenType.NEWLINE, "\n", self.scanner.line - 1, self.scanner.col))
            self.is_new_line = True
            return True

    def _scan_normal_char(self):
        self.scanner.start_token()
        char = self.scanner.advance()
        
        # 1. Explicit line continuation
        if char == '\\':
            if self.scanner.peek() == '\n':
                self.continuation_mode = True
                return
            else:
                self._report_error(LEX_INVALID_ESCAPE, f"Unexpected character '\\' or invalid escape sequence")
                return

        # 2. Whitespace
        if char in ' \t':
            return

        # 3. Comments
        if char == '#':
            self._skip_comment() 
            return

        # 4. Raw String Prefix (r"..." or r'...')
        if char == 'r' and (self.scanner.peek() == '"' or self.scanner.peek() == "'"):
            quote = self.scanner.advance()
            self.sub_state = SubState.IN_STRING
            self.quote_char = quote
            self.current_string_val = ""
            self.is_raw_string = True
            return

        # 5. String Literals
        if char == '"' or char == "'":
            self.sub_state = SubState.IN_STRING
            self.quote_char = char
            self.current_string_val = ""
            self.is_raw_string = False
            return

        # 6. Intent Comments
        if char == '@':
            content = ""
            while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
                content += self.scanner.advance()
            self.tokens.append(self.scanner.create_token(TokenType.INTENT, content))
            return

        # 7. Behavior Description and Bitwise Operators
        if char == '~':
            # Check for double tilde ~~
            if self.scanner.peek() == '~':
                self.scanner.advance()
                self.sub_state = SubState.IN_BEHAVIOR
                self.tokens.append(self.scanner.create_token(TokenType.BEHAVIOR_MARKER, "~~"))
                return
            else:
                # Single tilde -> Bitwise NOT
                self.tokens.append(self.scanner.create_token(TokenType.BIT_NOT, "~"))
                return

        # 8. Symbols
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

        # 9. Identifiers / Numbers
        if char.isalpha() or char == '_' or '\u4e00' <= char <= '\u9fff':
            self._scan_identifier(char)
            return
        if char.isdigit():
            self._scan_number(char)
            return
            
        self._report_error(LEX_INVALID_CHAR, f"Unexpected character '{char}'")

    def _scan_string_char(self):
        char = self.scanner.advance()
        
        if char == '\n':
            self._report_error(LEX_UNTERMINATED_STRING, "EOL while scanning string literal")
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
            self.tokens.append(self.scanner.create_token(TokenType.STRING, self.current_string_val))
            self.sub_state = SubState.NORMAL
        else:
            self.current_string_val += char

    def _scan_behavior_char(self):
        char = self.scanner.peek()
        
        # 1. Check for closing marker ~~
        if char == '~' and self.scanner.peek(1) == '~':
            self.scanner.advance() # ~
            self.scanner.advance() # ~
            self.tokens.append(self.scanner.create_token(TokenType.BEHAVIOR_MARKER, "~~"))
            self.sub_state = SubState.NORMAL
            return

        # 2. Handle escapes: \~~, \$, \~
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
            
            # Other backslashes remain as is, part of Raw Text
            # Fall through to raw text handling

        # 3. Variable Reference
        if char == '$':
            self._scan_var_ref()
            return
            
        # 4. Raw Text
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
                # Logical operators implicitly continue at EOL
                offset = 0
                while self.scanner.peek(offset) in ' \t':
                    offset += 1
                
                char = self.scanner.peek(offset)
                if char == '\n' or char == '#':
                    self.continuation_mode = True

        else:
            self.tokens.append(self.scanner.create_token(TokenType.IDENTIFIER, value, self.is_new_line))
            
        self.is_new_line = False

    def _scan_number(self, first_char):
        value = first_char
        
        # 1. Hexadecimal (0x...)
        if first_char == '0' and (self.scanner.peek() == 'x' or self.scanner.peek() == 'X'):
            value += self.scanner.advance()
            while not self.scanner.is_at_end() and (self.scanner.peek().isdigit() or self.scanner.peek() in 'abcdefABCDEF'):
                value += self.scanner.advance()
            self.tokens.append(self.scanner.create_token(TokenType.NUMBER, value))
            self.is_new_line = False
            return

        # 2. Binary (0b...)
        if first_char == '0' and (self.scanner.peek() == 'b' or self.scanner.peek() == 'B'):
            value += self.scanner.advance()
            while not self.scanner.is_at_end() and self.scanner.peek() in '01':
                value += self.scanner.advance()
            self.tokens.append(self.scanner.create_token(TokenType.NUMBER, value))
            self.is_new_line = False
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
            # Check if next char is valid (+, -, or digit)
            next_char = self.scanner.peek(1)
            if next_char.isdigit() or next_char in '+-':
                value += self.scanner.advance() # 'e' or 'E'
                if self.scanner.peek() in '+-':
                    value += self.scanner.advance()
                while self.scanner.peek().isdigit():
                    value += self.scanner.advance()
        
        self.tokens.append(self.scanner.create_token(TokenType.NUMBER, value))
        self.is_new_line = False

    def _scan_var_ref(self):
        self.scanner.start_token()
        self.scanner.advance() # $
        name = ""
        
        # Allow letter or underscore as first char
        if not self.scanner.is_at_end() and (self.scanner.peek().isalnum() or self.scanner.peek() == '_' or '\u4e00' <= self.scanner.peek() <= '\u9fff'):
            name += self.scanner.advance()
        else:
            self.issue_tracker.report(Severity.WARNING, "LEX_EMPTY_VAR_REF", r"Empty variable reference '$'. Did you mean '\$'?", self.scanner)


        while not self.scanner.is_at_end():
            peek = self.scanner.peek()
            if peek.isalnum() or peek == '_' or '\u4e00' <= peek <= '\u9fff':
                name += self.scanner.advance()
            elif peek == '.':
                # Check if dot is followed by a valid identifier start char
                next_char = self.scanner.peek(1)
                if next_char.isalnum() or next_char == '_' or '\u4e00' <= next_char <= '\u9fff':
                    name += self.scanner.advance() # .
                else:
                    break
            else:
                break
                
        self.tokens.append(self.scanner.create_token(TokenType.VAR_REF, "$" + name))

    def _scan_llm_chunk(self):
        # Check line-start keywords
        offset = 0
        while self.scanner.peek(offset) in ' \t':
            offset += 1
        
        # Define keywords to check and their Token types
        llm_keywords = [
            ('llmend', TokenType.LLM_END),
            ('__sys__', TokenType.LLM_SYS),
            ('__user__', TokenType.LLM_USER)
        ]
        
        keyword_found = False
        for keyword, token_type in llm_keywords:
            if self._match_llm_keyword(offset, keyword):
                self._consume_llm_keyword(offset, keyword, token_type)
                keyword_found = True
                
                if token_type == TokenType.LLM_END:
                    self.mode_stack.pop()
                    return
                # For SYS/USER, we continue to scan the rest of the line as text
                break

        # Regular prompt text
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
            # If line contains a keyword (and not LLM_END) and no text followed,
            # skip the newline to avoid including it in the prompt content.
            # e.g. "__sys__\n" -> skip newline
            #      "__sys__ content\n" -> emit newline
            if keyword_found and not text:
                self.scanner.advance()
            else:
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
