from typing import List
from typedef.lexer_types import Token, TokenType
from typedef.symbol_types import SymbolType
from utils.parser.symbol_table import ScopeManager

class PreScanner:
    """
    交错式预扫描器 (Interleaved Pre-Scanner)
    负责在进入新作用域时，快速扫描当前块内的顶层定义，并注册到 ScopeManager。
    """
    def __init__(self, tokens: List[Token], start_index: int, scope_manager: ScopeManager):
        self.tokens = tokens
        self.current = start_index
        self.scope_manager = scope_manager
        self.length = len(tokens)

    def scan(self):
        """
        Execute the pre-scan for the current block.
        Stops when DEDENT matches the initial indentation level, 
        or simply scans until the end of the current block structure.
        
        This scanner is called by the Parser when entering a block. It scans until 
        it hits a DEDENT that closes this block.
        
        The goal is to register all symbols (functions, LLM functions, variables)
        visible in the CURRENT scope, including those nested in if/for/while blocks,
        but skipping the bodies of nested functions (as they create their own scopes).
        """
        
        initial_balance = 0 
        # Track indent level relative to start of scan.
        # Start is inside a block (after INDENT).
        
        while not self.is_at_end():
            token = self.peek()
            
            if token.type == TokenType.DEDENT:
                if initial_balance == 0:
                    # End of the current scope block
                    return
                initial_balance -= 1
                self.advance()
                continue
                
            if token.type == TokenType.INDENT:
                initial_balance += 1
                self.advance()
                continue
            
            # Register symbols in current scope.
            # We skip bodies of nested functions/LLM blocks because they have their own scopes.
            
            if token.type == TokenType.FUNC:
                self._register_func()
                self._skip_block()
                
            elif token.type == TokenType.LLM_DEF:
                self._register_llm()
                self._skip_llm_block() 
                
            # elif token.type == TokenType.CLASS: # Future support
            #     self._register_class()
            #     self._skip_block()
                
            elif token.type == TokenType.VAR:
                # Explicit var declaration: var x = ...
                self.advance() # var
                if self.check(TokenType.IDENTIFIER):
                    name = self.advance().value
                    self.scope_manager.define(name, SymbolType.VARIABLE)
                    
            # Implicit declarations: "Type Name" or "Generic[Type] Name"
            elif self.check(TokenType.IDENTIFIER):
                if self._check_declaration_pattern():
                    # The pattern checker advanced and registered the name
                    pass
                else:
                    self.advance()
            else:
                self.advance()

    def _register_func(self):
        self.advance() # func
        if self.check(TokenType.IDENTIFIER):
            name = self.advance().value
            self.scope_manager.define(name, SymbolType.FUNCTION)
        # Skip params until COLON
        while not self.is_at_end() and not self.check(TokenType.COLON):
            self.advance()
        if self.check(TokenType.COLON):
            self.advance()

    def _register_llm(self):
        self.advance() # llm
        if self.check(TokenType.IDENTIFIER):
            name = self.advance().value
            self.scope_manager.define(name, SymbolType.FUNCTION)
        # Skip params until COLON
        while not self.is_at_end() and not self.check(TokenType.COLON):
            self.advance()
        if self.check(TokenType.COLON):
            self.advance()

    def _skip_block(self):
        """
        Skip until the block ends.
        A block starts with NEWLINE INDENT ... and ends with DEDENT.
        """
        if self.check(TokenType.NEWLINE):
            self.advance()
            
        if self.check(TokenType.INDENT):
            self.advance()
            balance = 1
            while not self.is_at_end() and balance > 0:
                t = self.advance()
                if t.type == TokenType.INDENT:
                    balance += 1
                elif t.type == TokenType.DEDENT:
                    balance -= 1

    def _skip_llm_block(self):
        """
        Skip LLM block until 'llmend'.
        """
        if self.check(TokenType.NEWLINE):
            self.advance()
            
        while not self.is_at_end() and not self.check(TokenType.LLM_END):
            self.advance()
            
        if self.check(TokenType.LLM_END):
            self.advance()

    def _check_declaration_pattern(self) -> bool:
        """
        Try to identify 'Type Name' pattern.
        If found, register 'Name' and return True.
        Current token is the potential Type.
        """
        # Lookahead 1: Identifier? "Type Name"
        if self.peek(1).type == TokenType.IDENTIFIER:
            # "ID ID" is strongly indicative of a declaration in this language.
            # e.g. "int x", "MyType y"
            
            var_name = self.peek(1).value
            self.scope_manager.define(var_name, SymbolType.VARIABLE)
            self.advance() # Type
            self.advance() # Name
            return True
            
        # Lookahead for Generics: List[int] x
        if self.peek(1).type == TokenType.LBRACKET:
            # We need to skip the brackets to see if an identifier follows
            offset = 1
            balance = 0
            while self.current + offset < self.length:
                t = self.peek(offset)
                if t.type == TokenType.LBRACKET:
                    balance += 1
                elif t.type == TokenType.RBRACKET:
                    balance -= 1
                    if balance == 0:
                        # Found closing bracket. Check next.
                        next_t = self.peek(offset + 1)
                        if next_t.type == TokenType.IDENTIFIER:
                            var_name = next_t.value
                            self.scope_manager.define(var_name, SymbolType.VARIABLE)
                            
                            # Consume everything up to var_name
                            for _ in range(offset + 2):
                                self.advance()
                            return True
                        else:
                            return False
                offset += 1
                
        return False

    # --- Helpers ---

    def peek(self, offset: int = 0) -> Token:
        if self.current + offset >= self.length:
            return self.tokens[-1]
        return self.tokens[self.current + offset]

    def check(self, type: TokenType) -> bool:
        if self.is_at_end():
            return False
        return self.peek().type == type

    def advance(self) -> Token:
        if not self.is_at_end():
            self.current += 1
        return self.tokens[self.current - 1]

    def is_at_end(self) -> bool:
        return self.peek().type == TokenType.EOF
