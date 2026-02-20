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
        Stops when DEDENT matches the initial indentation level (conceptually), 
        or simply scans until the end of the current block structure.
        
        For simplicity in this interleaved approach, we assume the Parser calls this 
        when entering a block (after INDENT), and we scan until we hit a DEDENT 
        that closes this block.
        
        However, handling nested blocks (if/while) inside a function requires careful logic.
        We only want to register 'func' and 'class' and 'var' that are visible in the CURRENT scope.
        
        But wait, in Python/IBC-Inter (assuming Python-like scoping for vars), 
        variables in if/for blocks ARE visible in the function scope.
        So we should scan EVERYTHING inside this function body, regardless of nesting depth?
        
        YES. For a function scope, we want to find all local variables and nested functions.
        BUT, nested functions create their OWN scope. We should register the nested function NAME,
        but NOT dive into its body to register its local variables (that's for when we parse that function).
        
        So the rule is:
        - Scan until end of current block (DEDENT back to start level).
        - If we encounter 'func' or 'class' or 'llm', register the name, skip the body.
        - If we encounter 'var' or implicit declaration, register the name.
        """
        
        # We assume we are just after INDENT or at the start of a global file
        # We need to track indentation balance to know when to skip bodies.
        
        # Actually, since we are interleaved, we might be called at 'func main():\n INDENT'
        # We want to scan until the corresponding DEDENT.
        
        initial_balance = 0 
        # We don't track exact indent level from tokens, but we rely on INDENT/DEDENT tokens.
        # When we start, we are inside a block. 
        # If we see INDENT, depth++. If DEDENT, depth--.
        # If depth < 0, we exited our block.
        
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
            
            # If we are at depth 0 (current scope level) OR inside if/for blocks (which share scope),
            # we should register variables.
            # BUT, if we are inside a nested 'func' or 'class' body (which we skipped via INDENT/DEDENT tracking?),
            # wait.
            # If we see 'func', we register the name, then we need to SKIP its body.
            # How do we skip its body?
            # The body starts with COLON NEWLINE INDENT ... DEDENT.
            
            if token.type == TokenType.FUNC:
                self._register_func()
                # _register_func consumes 'func' 'name' 'params' ... ':'
                # Then we need to skip the body.
                self._skip_block()
                
            elif token.type == TokenType.LLM_DEF:
                self._register_llm()
                self._skip_llm_block() # LLM blocks are special, no INDENT tokens usually
                
            # elif token.type == TokenType.CLASS: # Future
            #     self._register_class()
            #     self._skip_block()
                
            elif token.type == TokenType.VAR:
                # Explicit var declaration: var x = ...
                self.advance() # var
                if self.check(TokenType.IDENTIFIER):
                    name = self.advance().value
                    # Only register if we are not deep inside a nested function (which we skipped)
                    # But wait, if we skipped nested functions, we wouldn't be here.
                    # So if we are here, we are in the current function's scope (or if/for block).
                    self.scope_manager.define(name, SymbolType.VARIABLE)
                    
            # Implicit declarations? "int x = 1" or "MyType x = 1"
            # This is harder to detect without full parsing.
            # Strategy: Look for "ID ID" pattern or "ID [ ... ] ID" pattern.
            elif self.check(TokenType.IDENTIFIER):
                # Check for Type Identifier pattern
                if self._check_declaration_pattern():
                    # The pattern checker will advance and extract the name
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
            
    def _register_class(self):
        self.advance() # class
        if self.check(TokenType.IDENTIFIER):
            name = self.advance().value
            self.scope_manager.define(name, SymbolType.USER_TYPE) # It's a type!
        # Skip inheritance until COLON
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
        LLM blocks don't respect INDENT/DEDENT in the same way, or rather Lexer handles them specially.
        Lexer emits LLM_END token.
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
        # Lookahead 1: Identifier?
        if self.peek(1).type == TokenType.IDENTIFIER:
            # Check if current token is a known type?
            # Wait, in PreScan we might not know user types yet if they are defined later in the file.
            # But wait, PreScan is interleaved.
            # If we are scanning a function, and we see "MyType x", 
            # MyType might be defined in the Global scope (already scanned) 
            # or in the current function (but later?).
            # Actually, "MyType x" is a declaration pattern regardless of whether MyType is known.
            # The syntax "ID ID" is strongly indicative of a declaration in this language.
            
            # HOWEVER, "x = y" is "ID ASSIGN ID".
            # "call(x)" is "ID LPAREN".
            # "x.y" is "ID DOT".
            # So "ID ID" is pretty unique to declarations.
            
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
