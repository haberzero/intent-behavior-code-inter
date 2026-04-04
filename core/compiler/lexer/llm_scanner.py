from typing import List, Tuple
from core.compiler.common.tokens import Token, TokenType
from core.compiler.lexer.str_stream import StrStream

class LLMScanner:
    """
    Handles token scanning within an LLM block (between 'llm ...:' and 'llmend').
    Parses prompt keywords (__sys__, __user__), raw text, and variable placeholders ($var).

    [IES 2.2] 简化设计：仅支持 $var 格式的变量引用。
    只有当变量名是 llm 函数中声明的参数时，才会被替换；其他情况作为普通文本。
    """
    def __init__(self, scanner: StrStream):
        self.scanner = scanner
        self.section_just_started = False

    def scan_chunk(self) -> Tuple[List[Token], bool]:
        """
        Scan a single line/chunk in LLM mode.

        Returns:
            Tuple[List[Token], bool]:
            - List of generated tokens.
            - Boolean flag: True if 'llmend' was encountered (signal to exit LLM mode).
        """
        tokens: List[Token] = []
        should_exit_mode = False

        offset = 0
        while self.scanner.peek(offset) in ' \t':
            offset += 1

        llm_keywords = [
            ('llmend', TokenType.LLM_END),
            ('__sys__', TokenType.LLM_SYS),
            ('__user__', TokenType.LLM_USER)
        ]

        for keyword, token_type in llm_keywords:
            if self._match_llm_keyword(offset, keyword):
                check_offset = offset + len(keyword)
                while self.scanner.peek(check_offset) in ' \t':
                    check_offset += 1

                if self.scanner.peek(check_offset) not in ['\n', '\0', '']:
                    break

                self._consume_llm_keyword(offset, keyword, token_type, tokens)

                if token_type == TokenType.LLM_END:
                    self.section_just_started = False
                    should_exit_mode = True
                    while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
                        self.scanner.advance()
                    if self.scanner.peek() == '\n':
                        self.scanner.advance()
                    return tokens, should_exit_mode

                self.section_just_started = True
                while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
                    self.scanner.advance()
                if self.scanner.peek() == '\n':
                    self.scanner.advance()

                return tokens, should_exit_mode

        text = ""
        start_line = self.scanner.line
        start_col = self.scanner.col

        if self.section_just_started:
            is_empty_line = True
            check_offset = 0
            while self.scanner.peek(check_offset) != '\n' and self.scanner.peek(check_offset) != '':
                if self.scanner.peek(check_offset) not in ' \t':
                    is_empty_line = False
                    break
                check_offset += 1

            if is_empty_line:
                while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
                    self.scanner.advance()
                if self.scanner.peek() == '\n':
                    self.scanner.advance()
                self.section_just_started = False
                return [], False
            else:
                self.section_just_started = False

        while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
            if self.scanner.peek() == '$':
                if self.scanner.peek(1).isalpha() or (self.scanner.peek(1) == '_' and self.scanner.peek(2) != '_'):
                    if text:
                        tokens.append(Token(TokenType.RAW_TEXT, text, start_line, start_col))
                        text = ""
                    self._scan_var_ref(tokens)
                    start_line = self.scanner.line
                    start_col = self.scanner.col
                    continue

            char = self.scanner.advance()
            text += char

        if text:
            tokens.append(Token(TokenType.RAW_TEXT, text, start_line, start_col))

        if self.scanner.peek() == '\n':
            self.scanner.advance()
            tokens.append(Token(TokenType.NEWLINE, "\n", self.scanner.line, self.scanner.col))

        return tokens, should_exit_mode

    def _scan_var_ref(self, tokens: List[Token]):
        """
        扫描变量引用 $var。
        注意：这只是标记位置，实际的变量替换在运行时通过参数名匹配决定。
        """
        self.scanner.start_token()
        self.scanner.advance()

        name_start = self.scanner.pos
        while not self.scanner.is_at_end():
            peek = self.scanner.peek()
            if peek.isalnum() or peek == '_':
                self.scanner.advance()
            else:
                break

        var_name = self.scanner.source[name_start:self.scanner.pos]
        tokens.append(self.scanner.create_token(TokenType.VAR_REF, var_name))

    def _match_llm_keyword(self, offset: int, keyword: str) -> bool:
        length = len(keyword)
        for i in range(length):
            if self.scanner.peek(offset + i) != keyword[i]:
                return False
        next_char = self.scanner.peek(offset + length)
        if next_char.isalnum() or next_char == '_':
            return False
        return True

    def _consume_llm_keyword(self, offset: int, keyword: str, token_type: TokenType, tokens: List[Token]):
        for _ in range(offset): self.scanner.advance()
        self.scanner.start_token()
        for _ in range(len(keyword)): self.scanner.advance()
        tokens.append(self.scanner.create_token(token_type))
