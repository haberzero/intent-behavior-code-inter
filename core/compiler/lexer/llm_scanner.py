from typing import List, Tuple
from core.compiler.common.tokens import Token, TokenType
from core.compiler.lexer.str_stream import StrStream

class LLMScanner:
    """
    Handles token scanning within an LLM block (between 'llm ...:' and 'llmend').
    Parses prompt keywords (__sys__, __user__), raw text, and parameter placeholders.
    """
    def __init__(self, scanner: StrStream):
        self.scanner = scanner
        self.section_just_started = False # Track if we just matched __sys__ or __user__

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
        
        # Check line-start keywords
        offset = 0
        while self.scanner.peek(offset) in ' \t':
            offset += 1
        
        llm_keywords = [
            ('llmend', TokenType.LLM_END),
            ('__sys__', TokenType.LLM_SYS),
            ('__user__', TokenType.LLM_USER)
        ]
        
        keyword_found = False
        for keyword, token_type in llm_keywords:
            if self._match_llm_keyword(offset, keyword):
                # [REFINEMENT] Keyword must be the ONLY thing on this line
                check_offset = offset + len(keyword)
                while self.scanner.peek(check_offset) in ' \t':
                    check_offset += 1
                
                if self.scanner.peek(check_offset) not in ['\n', '\0', '']:
                    # Not a standalone keyword line, treat as regular text
                    break
                
                self._consume_llm_keyword(offset, keyword, token_type, tokens)
                keyword_found = True
                
                if token_type == TokenType.LLM_END:
                    self.section_just_started = False
                    should_exit_mode = True
                    # Consume the rest of the line (should only be whitespace/newline)
                    while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
                        self.scanner.advance()
                    if self.scanner.peek() == '\n':
                        self.scanner.advance()
                    return tokens, should_exit_mode
                
                # For SYS/USER, we set the flag to ignore the next newline
                self.section_just_started = True
                
                # Consume the rest of the line (newline)
                while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
                    self.scanner.advance()
                if self.scanner.peek() == '\n':
                    self.scanner.advance()
                
                return tokens, should_exit_mode

        # Regular prompt text
        text = ""
        start_line = self.scanner.line
        start_col = self.scanner.col
        
        # [REFINEMENT] If section just started, we check if this line is empty
        # to decide if we should skip it.
        if self.section_just_started:
            is_empty_line = True
            check_offset = 0
            while self.scanner.peek(check_offset) != '\n' and self.scanner.peek(check_offset) != '':
                if self.scanner.peek(check_offset) not in ' \t':
                    is_empty_line = False
                    break
                check_offset += 1
            
            if is_empty_line:
                # Skip this first empty line after keyword
                while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
                    self.scanner.advance()
                if self.scanner.peek() == '\n':
                    self.scanner.advance()
                self.section_just_started = False
                return [], False
            else:
                # First line has content, so we don't skip it and stop skipping
                self.section_just_started = False

        while not self.scanner.is_at_end() and self.scanner.peek() != '\n':
            # Check for parameter placeholder $__param__
            if self.scanner.peek() == '$' and self.scanner.peek(1) == '_' and self.scanner.peek(2) == '_':
                if text:
                    tokens.append(Token(TokenType.RAW_TEXT, text, start_line, start_col))
                    text = ""
                self._scan_param_placeholder(tokens)
                
                start_line = self.scanner.line
                start_col = self.scanner.col
            else:
                char = self.scanner.advance()
                text += char
        
        if text:
            tokens.append(Token(TokenType.RAW_TEXT, text, start_line, start_col))
            
        if self.scanner.peek() == '\n':
            self.scanner.advance()
            tokens.append(Token(TokenType.NEWLINE, "\n", self.scanner.line, self.scanner.col))
                
        return tokens, should_exit_mode

    def _scan_param_placeholder(self, tokens: List[Token]):
        self.scanner.start_token()
        self.scanner.advance()
        self.scanner.advance()
        self.scanner.advance()

        name_start = self.scanner.pos
        while not self.scanner.is_at_end():
            if self.scanner.peek() == '_' and self.scanner.peek(1) == '_':
                break
            self.scanner.advance()

        param_name = self.scanner.source[name_start:self.scanner.pos]

        self.scanner.advance()
        self.scanner.advance()

        tokens.append(self.scanner.create_token(TokenType.EMBEDDED_PARAM, param_name))

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

    def _consume_llm_keyword(self, offset: int, keyword: str, token_type: TokenType, tokens: List[Token]):
        for _ in range(offset): self.scanner.advance()
        self.scanner.start_token()
        for _ in range(len(keyword)): self.scanner.advance()
        tokens.append(self.scanner.create_token(token_type))
