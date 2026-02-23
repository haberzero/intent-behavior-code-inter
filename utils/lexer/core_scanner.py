from typing import List, Tuple, Optional
from typedef.lexer_types import Token, TokenType, SubState
from utils.lexer.str_stream import StrStream
from utils.diagnostics.issue_tracker import IssueTracker
from utils.diagnostics.codes import *
from typedef.diagnostic_types import Severity

class CoreTokenScanner:
    """
    Handles scanning of standard code tokens (identifiers, keywords, symbols, strings, behavior blocks).
    Maintains state for string parsing, parenthesis levels, and line continuation.
    """
    def __init__(self, scanner: StrStream, issue_tracker: IssueTracker):
        self.scanner = scanner
        self.issue_tracker = issue_tracker
        
        # Internal State
        self.sub_state = SubState.NORMAL
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
                
        return tokens, False, enter_llm_mode

    def check_eof_state(self):
        """Check for unclosed states at EOF."""
        if self.sub_state == SubState.IN_STRING:
            self.issue_tracker.report(Severity.ERROR, LEX_UNTERMINATED_STRING, "Unexpected EOF while scanning string literal", self.scanner)
        if self.sub_state == SubState.IN_BEHAVIOR:
            self.issue_tracker.report(Severity.ERROR, LEX_UNTERMINATED_BEHAVIOR, "Unexpected EOF while scanning behavior description", self.scanner)

    def _handle_newline(self, tokens: List[Token]) -> bool:
        """
        Handle newline character.
        Returns True if line processing ended, False if newline was consumed (e.g., in string).
        """
        # Case 1: In string
        if self.sub_state == SubState.IN_STRING:
            self._scan_string_char(tokens)
            return False
        
        # Case 2: In behavior description
        elif self.sub_state == SubState.IN_BEHAVIOR:
            tokens.append(Token(TokenType.RAW_TEXT, "\n", self.scanner.line, self.scanner.col))
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
        char = self.scanner.advance()
        
        # 1. Explicit line continuation
        if char == '\\':
            if self.scanner.peek() == '\n':
                self.continuation_mode = True
                return False
            else:
                self.issue_tracker.report(Severity.ERROR, LEX_INVALID_ESCAPE, f"Unexpected character '\\' or invalid escape sequence", self.scanner)
                return False

        # 2. Whitespace
        if char in ' \t':
            return False

        # 3. Comments
        if char == '#':
            self._skip_comment() 
            return False

        # 4. Raw String Prefix
        if char == 'r' and (self.scanner.peek() == '"' or self.scanner.peek() == "'"):
            quote = self.scanner.advance()
            self.sub_state = SubState.IN_STRING
            self.quote_char = quote
            self.current_string_val = ""
            self.is_raw_string = True
            return False

        # 5. String Literals
        if char == '"' or char == "'":
            self.sub_state = SubState.IN_STRING
            self.quote_char = char
            self.current_string_val = ""
            self.is_raw_string = False
            return False

        # 6. Intent Comments
        if char == '@':
            content = ""
            while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
                content += self.scanner.advance()
            tokens.append(self.scanner.create_token(TokenType.INTENT, content))
            return False

        # 7. Behavior Description and Bitwise Operators
        if char == '~':
            if self.scanner.peek() == '~':
                self.scanner.advance()
                self.sub_state = SubState.IN_BEHAVIOR
                tokens.append(self.scanner.create_token(TokenType.BEHAVIOR_MARKER, "~~"))
                return False
            else:
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
            if self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.STAR_ASSIGN, "*="))
            else: tokens.append(self.scanner.create_token(TokenType.STAR))
            return False
        if char == '/': 
            if self.scanner.match('='): tokens.append(self.scanner.create_token(TokenType.SLASH_ASSIGN, "/="))
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
            
        self.issue_tracker.report(Severity.ERROR, LEX_INVALID_CHAR, f"Unexpected character '{char}'", self.scanner)
        return False

    def _scan_string_char(self, tokens: List[Token]):
        char = self.scanner.advance()
        
        if char == '\n':
            self.issue_tracker.report(Severity.ERROR, LEX_UNTERMINATED_STRING, "EOL while scanning string literal", self.scanner)
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
            self.sub_state = SubState.NORMAL
        else:
            self.current_string_val += char

    def _scan_behavior_char(self, tokens: List[Token]):
        char = self.scanner.peek()
        
        # 1. Check for closing marker ~~
        if char == '~' and self.scanner.peek(1) == '~':
            self.scanner.advance() # ~
            self.scanner.advance() # ~
            tokens.append(self.scanner.create_token(TokenType.BEHAVIOR_MARKER, "~~"))
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
                    tokens.append(Token(TokenType.RAW_TEXT, "~~", self.scanner.line, self.scanner.col))
                    return
                else:
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
            
            # Other backslashes remain as is, part of Raw Text

        # 3. Variable Reference
        if char == '$':
            self._scan_var_ref(tokens)
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
            tokens.append(Token(TokenType.RAW_TEXT, text, self.scanner.line, self.scanner.col))

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
        
        tokens.append(self.scanner.create_token(TokenType.NUMBER, value))
        self.is_new_line_flag = False

    def _scan_var_ref(self, tokens: List[Token]):
        self.scanner.start_token()
        self.scanner.advance() # $
        name = ""
        
        if not self.scanner.is_at_end() and (self.scanner.peek().isalnum() or self.scanner.peek() == '_' or '\u4e00' <= self.scanner.peek() <= '\u9fff'):
            name += self.scanner.advance()
        else:
            self.issue_tracker.report(Severity.WARNING, "LEX_EMPTY_VAR_REF", r"Empty variable reference '$'. Did you mean '\$'?", self.scanner)

        while not self.scanner.is_at_end():
            peek = self.scanner.peek()
            if peek.isalnum() or peek == '_' or '\u4e00' <= peek <= '\u9fff':
                name += self.scanner.advance()
            elif peek == '.':
                next_char = self.scanner.peek(1)
                if next_char.isalnum() or next_char == '_' or '\u4e00' <= next_char <= '\u9fff':
                    name += self.scanner.advance() # .
                else:
                    break
            else:
                break
                
        tokens.append(self.scanner.create_token(TokenType.VAR_REF, "$" + name))

    def _skip_comment(self):
        """Skip comments until end of line (do not consume newline)."""
        while self.scanner.peek() != '\n' and not self.scanner.is_at_end():
            self.scanner.advance()
