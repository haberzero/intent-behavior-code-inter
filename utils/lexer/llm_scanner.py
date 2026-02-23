from typing import List, Tuple
from typedef.lexer_types import Token, TokenType
from utils.lexer.str_stream import StrStream

class LLMScanner:
    """
    Handles token scanning within an LLM block (between 'llm ...:' and 'llmend').
    Parses prompt keywords (__sys__, __user__), raw text, and parameter placeholders.
    """
    def __init__(self, scanner: StrStream):
        self.scanner = scanner

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
                self._consume_llm_keyword(offset, keyword, token_type, tokens)
                keyword_found = True
                
                if token_type == TokenType.LLM_END:
                    should_exit_mode = True
                    return tokens, should_exit_mode
                # For SYS/USER, we continue to scan the rest of the line as text
                break

        # Regular prompt text
        text = ""
        start_line = self.scanner.line
        start_col = self.scanner.col
        
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
                text += self.scanner.advance()
        
        if text:
            tokens.append(Token(TokenType.RAW_TEXT, text, start_line, start_col))
            
        if self.scanner.peek() == '\n':
            # If line contains a keyword (and not LLM_END) and no text followed,
            # skip the newline to avoid including it in the prompt content.
            if keyword_found and not text:
                self.scanner.advance()
            else:
                self.scanner.advance()
                tokens.append(Token(TokenType.NEWLINE, "\n", self.scanner.line, self.scanner.col))
                
        return tokens, should_exit_mode

    def _scan_param_placeholder(self, tokens: List[Token]):
        self.scanner.start_token()
        self.scanner.advance() # $
        self.scanner.advance() # _
        self.scanner.advance() # _
        while not self.scanner.is_at_end() and not (self.scanner.peek() == '_' and self.scanner.peek(1) == '_'):
            self.scanner.advance()
        if not self.scanner.is_at_end():
            self.scanner.advance()
            self.scanner.advance()
        tokens.append(self.scanner.create_token(TokenType.PARAM_PLACEHOLDER))

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
