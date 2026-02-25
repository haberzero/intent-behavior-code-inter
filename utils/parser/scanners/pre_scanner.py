from typing import List
from typedef.lexer_types import Token, TokenType
from typedef.symbol_types import SymbolType
from utils.parser.symbol_table import ScopeManager
from utils.parser.core.token_stream import TokenStream
from utils.parser.core.recognizer import SyntaxRecognizer, SyntaxRole

class PreScanner:
    """
    交错式预扫描器 (Interleaved Pre-Scanner)
    负责在进入新作用域时，快速扫描当前块内的顶层定义，并注册到 ScopeManager。
    """
    def __init__(self, stream: TokenStream, scope_manager: ScopeManager):
        self.stream = stream
        self.scope_manager = scope_manager

    def scan(self):
        """
        Execute the pre-scan for the current block.
        Stops when DEDENT matches the initial indentation level, 
        or simply scans until the end of the current block structure.
        """
        
        initial_balance = 0 
        
        while not self.stream.is_at_end():
            role = SyntaxRecognizer.get_role(self.stream, self.scope_manager)
            
            if role == SyntaxRole.BLOCK_MARKER:
                token = self.stream.peek()
                if token.type == TokenType.DEDENT:
                    if initial_balance == 0:
                        return
                    initial_balance -= 1
                elif token.type == TokenType.INDENT:
                    initial_balance += 1
                self.stream.advance()
                continue
            
            if role == SyntaxRole.FUNCTION_DEFINITION:
                self._register_func()
                self._skip_block()
            elif role == SyntaxRole.LLM_DEFINITION:
                self._register_llm()
                self._skip_llm_block()
            elif role == SyntaxRole.VARIABLE_DECLARATION:
                self._register_variable()
            elif role == SyntaxRole.IMPORT_STATEMENT:
                # We skip imports in PreScanner for now, as Parser handles them.
                # But we must advance the stream to avoid infinite loop.
                self.stream.advance()
            else:
                self.stream.advance()

    def _register_func(self):
        self.stream.advance() # func
        if self.stream.check(TokenType.IDENTIFIER):
            name = self.stream.advance().value
            self.scope_manager.define(name, SymbolType.FUNCTION)
        # Skip until COLON
        while not self.stream.is_at_end() and not self.stream.check(TokenType.COLON):
            self.stream.advance()
        if self.stream.check(TokenType.COLON):
            self.stream.advance()

    def _register_llm(self):
        self.stream.advance() # llm
        if self.stream.check(TokenType.IDENTIFIER):
            name = self.stream.advance().value
            self.scope_manager.define(name, SymbolType.FUNCTION)
        # Skip until COLON
        while not self.stream.is_at_end() and not self.stream.check(TokenType.COLON):
            self.stream.advance()
        if self.stream.check(TokenType.COLON):
            self.stream.advance()

    def _register_variable(self):
        start_index = self.stream.current
        if self.stream.match(TokenType.VAR):
            if self.stream.check(TokenType.IDENTIFIER):
                name = self.stream.advance().value
                sym = self.scope_manager.define(name, SymbolType.VARIABLE)
                # For 'var', we don't have a specific type node yet, it's inferred.
        else:
            # Implicit declaration: Type [Generics] Name
            
            # Skip type identifier and generics to find the name
            # But we also want to capture the type tokens
            type_start = self.stream.current
            
            # Skip type identifier
            self.stream.advance() 
            
            # Skip generics if any
            if self.stream.match(TokenType.LBRACKET):
                balance = 1
                while not self.stream.is_at_end() and balance > 0:
                    t = self.stream.advance()
                    if t.type == TokenType.LBRACKET:
                        balance += 1
                    elif t.type == TokenType.RBRACKET:
                        balance -= 1
            
            type_end = self.stream.current
            
            # Now we should be at the name
            if self.stream.check(TokenType.IDENTIFIER):
                name_token = self.stream.advance()
                name = name_token.value
                sym = self.scope_manager.define(name, SymbolType.VARIABLE)
                
                # Store type tokens for lazy parsing in SemanticAnalyzer
                # We'll use a special attribute to hold these tokens or just the range
                sym.declared_type_node = self.stream.tokens[type_start:type_end]

    def _skip_block(self):
        if self.stream.match(TokenType.NEWLINE):
            pass
        if self.stream.match(TokenType.INDENT):
            balance = 1
            while not self.stream.is_at_end() and balance > 0:
                t = self.stream.advance()
                if t.type == TokenType.INDENT:
                    balance += 1
                elif t.type == TokenType.DEDENT:
                    balance -= 1

    def _skip_llm_block(self):
        if self.stream.match(TokenType.NEWLINE):
            pass
        while not self.stream.is_at_end() and not self.stream.check(TokenType.LLM_END):
            self.stream.advance()
        if self.stream.match(TokenType.LLM_END):
            pass
