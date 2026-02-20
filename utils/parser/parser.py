from typing import List, Optional, Callable, Dict, TypeVar, Any
from typedef.lexer_types import Token, TokenType
from typedef import parser_types as ast
from typedef.parser_types import Precedence, ParseRule

from utils.parser.symbol_table import ScopeManager, ScopeType, SymbolType
from utils.parser.pre_scanner import PreScanner
from utils.diagnostics.issue_tracker import IssueTracker
from utils.diagnostics.codes import *
from typedef.diagnostic_types import Severity, CompilerError

class ParseControlFlowError(Exception):
    """Internal exception for parser synchronization control flow."""
    pass

T = TypeVar("T", bound=ast.ASTNode)

class Parser:
    """
    IBC-Inter 语法分析器 (Parser)
    采用交错式预构建 (Interleaved Pre-Pass) 和持久化符号表树架构。
    """
    def __init__(self, tokens: List[Token], issue_tracker: Optional[IssueTracker] = None, module_cache: Optional[Dict[str, Any]] = None):
        self.tokens = tokens
        self.current = 0
        self.issue_tracker = issue_tracker or IssueTracker()
        self.rules: Dict[TokenType, ParseRule] = {}
        self.pending_intent: Optional[str] = None
        self.module_cache = module_cache or {}
        
        # Scope Management
        self.scope_manager = ScopeManager()
        
        # Initial Global Scan
        self._run_pre_scanner()
        
        self.register_rules()

    def _warn(self, message: str):
        self.issue_tracker.report(Severity.WARNING, "PAR_WARN", message, self.peek())

    def _run_pre_scanner(self):
        """Run the PreScanner on the current scope."""
        scanner = PreScanner(self.tokens, self.current, self.scope_manager)
        scanner.scan()

    # --- Helpers ---

    def peek(self, offset: int = 0) -> Token:
        if self.current + offset >= len(self.tokens):
            return self.tokens[-1] # EOF
        return self.tokens[self.current + offset]

    def previous(self) -> Token:
        return self.tokens[self.current - 1]

    def is_at_end(self) -> bool:
        return self.peek().type == TokenType.EOF

    def check(self, type: TokenType) -> bool:
        if self.is_at_end():
            return False
        return self.peek().type == type

    def advance(self) -> Token:
        if not self.is_at_end():
            self.current += 1
        return self.previous()

    def consume(self, type: TokenType, message: str) -> Token:
        if self.check(type):
            return self.advance()
        raise self.error(self.peek(), message)

    def consume_end_of_statement(self, message: str):
        if self.check(TokenType.NEWLINE):
            self.advance()
        elif self.is_at_end():
            return
        else:
            raise self.error(self.peek(), message)

    def match(self, *types: TokenType) -> bool:
        for type in types:
            if self.check(type):
                self.advance()
                return True
        return False

    def error(self, token: Token, message: str) -> Exception:
        self.issue_tracker.report(Severity.ERROR, PAR_EXPECTED_TOKEN, message, token)
        return ParseControlFlowError()

    def synchronize(self):
        self.advance()
        while not self.is_at_end():
            if self.previous().type == TokenType.NEWLINE:
                return

            if self.peek().type in (TokenType.FUNC, TokenType.VAR, TokenType.FOR,
                                    TokenType.IF, TokenType.WHILE, TokenType.RETURN,
                                    TokenType.LLM_DEF):
                return

            self.advance()

    def register(self, type: TokenType, prefix, infix, precedence):
        self.rules[type] = ParseRule(prefix, infix, precedence)

    def get_rule(self, type: TokenType) -> ParseRule:
        return self.rules.get(type, ParseRule(None, None, Precedence.LOWEST))

    def parse_precedence(self, precedence: Precedence) -> ast.Expr:
        token = self.advance()
        rule = self.get_rule(token.type)
        prefix = rule.prefix
        if prefix is None:
            raise self.error(token, f"Expect expression. Got {token.type}")
        
        left = prefix()
        
        while precedence < self.get_rule(self.peek().type).precedence:
            token = self.advance()
            infix = self.get_rule(token.type).infix
            if infix is None:
                return left
            left = infix(left)
            
        return left
        
    def _loc(self, node: T, token: Token) -> T:
        """注入位置信息。"""
        node.lineno = token.line
        node.col_offset = token.column
        node.end_lineno = token.end_line
        node.end_col_offset = token.end_column
        return node

    def register_rules(self):
        # 字面量与标识符
        self.register(TokenType.IDENTIFIER, self.variable, None, Precedence.LOWEST)
        self.register(TokenType.NUMBER, self.number, None, Precedence.LOWEST)
        self.register(TokenType.STRING, self.string, None, Precedence.LOWEST)
        self.register(TokenType.BOOL, self.boolean, None, Precedence.LOWEST)
        
        # 分组与集合
        self.register(TokenType.LPAREN, self.grouping, self.call, Precedence.CALL)
        self.register(TokenType.LBRACKET, self.list_display, self.subscript, Precedence.CALL)
        self.register(TokenType.LBRACE, self.dict_display, None, Precedence.LOWEST)
        
        # 一元运算
        self.register(TokenType.MINUS, self.unary, self.binary, Precedence.TERM)
        self.register(TokenType.PLUS, None, self.binary, Precedence.TERM)
        self.register(TokenType.NOT, self.unary, None, Precedence.UNARY)
        self.register(TokenType.BIT_NOT, self.unary, None, Precedence.UNARY)
        
        # 二元运算
        self.register(TokenType.STAR, None, self.binary, Precedence.FACTOR)
        self.register(TokenType.SLASH, None, self.binary, Precedence.FACTOR)
        self.register(TokenType.PERCENT, None, self.binary, Precedence.FACTOR)
        
        # 位运算
        self.register(TokenType.BIT_AND, None, self.binary, Precedence.BIT_AND)
        self.register(TokenType.BIT_OR, None, self.binary, Precedence.BIT_OR)
        self.register(TokenType.BIT_XOR, None, self.binary, Precedence.BIT_XOR)
        self.register(TokenType.LSHIFT, None, self.binary, Precedence.SHIFT)
        self.register(TokenType.RSHIFT, None, self.binary, Precedence.SHIFT)
        
        # 比较运算
        self.register(TokenType.GT, None, self.binary, Precedence.COMPARISON)
        self.register(TokenType.GE, None, self.binary, Precedence.COMPARISON)
        self.register(TokenType.LT, None, self.binary, Precedence.COMPARISON)
        self.register(TokenType.LE, None, self.binary, Precedence.COMPARISON)
        self.register(TokenType.EQ, None, self.binary, Precedence.EQUALITY)
        self.register(TokenType.NE, None, self.binary, Precedence.EQUALITY)
        
        # 逻辑运算
        self.register(TokenType.AND, None, self.logical, Precedence.AND)
        self.register(TokenType.OR, None, self.logical, Precedence.OR)
        
        # 调用与属性
        self.register(TokenType.DOT, None, self.dot, Precedence.CALL)
        
        # 行为描述
        self.register(TokenType.BEHAVIOR_MARKER, self.behavior_expression, None, Precedence.LOWEST)

    # --- Core Parsing Logic ---

    def parse(self) -> ast.Module:
        statements = []
        while not self.is_at_end():
            try:
                if self.match(TokenType.NEWLINE):
                    continue
                decl = self.declaration()
                if decl:
                    statements.append(decl)
            except ParseControlFlowError:
                # Synchronize to continue parsing next statement.
                self.synchronize()
        
        # Check for errors at the end
        self.issue_tracker.check_errors()
        
        module_node = ast.Module(body=statements)
        # Attach global scope to module
        module_node.scope = self.scope_manager.global_scope
        return module_node

    def declaration(self) -> Optional[ast.Stmt]:
        # 处理 Intent (@)
        if self.match(TokenType.INTENT):
            if self.pending_intent is not None:
                raise self.error(self.previous(), "Multiple intent comments are not allowed for a single statement.")
            
            self.pending_intent = self.previous().value
            if self.check(TokenType.NEWLINE):
                self.advance()
            return self.declaration()
        
        stmt = None
        if self.match(TokenType.FUNC):
            stmt = self.function_declaration()
        elif self.match(TokenType.LLM_DEF):
            stmt = self.llm_function_declaration()
        elif self.match(TokenType.VAR):
            # Explicit 'var' declaration
            stmt = self.variable_declaration(explicit_var=True)
        elif self.check_declaration_lookahead():
            # Implicit type declaration: Type name = ...
            stmt = self.variable_declaration(explicit_var=False)
        else:
            stmt = self.statement()
        
        if self.pending_intent is not None and stmt is not None:
            self._warn(f"Intent comment '{self.pending_intent}' was not used by the following statement at line {stmt.lineno}.")
            self.pending_intent = None
            
        return stmt

    def check_declaration_lookahead(self) -> bool:
        """
        Check if the current tokens form a variable declaration:
        1. TypeName Identifier ...
        2. Identifier Identifier ... (User defined type)
        3. GenericType[Args] Identifier ...
        """
        # Case 1: Standard Type Name or Known Type in Symbol Table
        if self.check(TokenType.IDENTIFIER) and self.scope_manager.is_type(self.peek().value):
            # Check if followed by an identifier (variable name)
            # This distinguishes 'int x' (declaration) from 'int(1)' (call expression)
            next_token = self.peek(1)
            
            if next_token.type == TokenType.IDENTIFIER:
                return True
            
            # Special case: Generic type declaration like list[int] x
            if next_token.type == TokenType.LBRACKET:
                return self._check_generic_lookahead(1)
                
            return False
            
        # Case 2: Identifier starting a declaration (Maybe a type we missed or future extension)
        # Fallback: Identifier Identifier -> Declaration
        if self.check(TokenType.IDENTIFIER):
            # Check next token
            next_token = self.peek(1)
            
            # Identifier Identifier (e.g. MyType varName)
            if next_token.type == TokenType.IDENTIFIER:
                return True
                
            # Generic Type: Identifier [ ... ] Identifier
            if next_token.type == TokenType.LBRACKET:
                return self._check_generic_lookahead(1)
                
        return False

    def _check_generic_lookahead(self, offset: int) -> bool:
        # We need to scan past the matching bracket to see if an identifier follows
        # This is a simple bracket matching
        bracket_depth = 0
        while self.current + offset < len(self.tokens):
            t = self.peek(offset)
            if t.type == TokenType.LBRACKET:
                bracket_depth += 1
            elif t.type == TokenType.RBRACKET:
                bracket_depth -= 1
                if bracket_depth == 0:
                    # Found closing bracket. Check what's next.
                    after_bracket = self.peek(offset + 1)
                    if after_bracket.type == TokenType.IDENTIFIER:
                        return True
                    else:
                        return False # Likely a subscript assignment: list[0] = 1
            elif t.type == TokenType.NEWLINE or t.type == TokenType.EOF:
                return False # Incomplete
                
            offset += 1
        return False

    def variable_declaration(self, explicit_var: bool = False) -> ast.Assign:
        type_token = None
        type_annotation = None
        
        if explicit_var:
            # 'var' keyword already consumed
            type_token = self.previous()
            type_annotation = self._loc(ast.Name(id='var', ctx='Load'), type_token)
        else:
            # Parse type annotation (including generics)
            # Since check_declaration_lookahead confirmed it's a declaration, 
            # we can safely parse the type.
            start_token = self.peek()
            type_annotation = self.parse_type_annotation()
            type_token = start_token

        name_token = self.consume(TokenType.IDENTIFIER, "Expect variable name.")
        target = self._loc(ast.Name(id=name_token.value, ctx='Store'), name_token)
        
        value = None
        if self.match(TokenType.ASSIGN):
            value = self.expression()
        
        self.consume_end_of_statement("Expect newline after variable declaration.")
        
        return self._loc(ast.Assign(targets=[target], value=value, type_annotation=type_annotation), type_token)

    def function_declaration(self) -> ast.FunctionDef:
        start_token = self.previous()
        name = self.consume(TokenType.IDENTIFIER, "Expect function name.").value
        self.consume(TokenType.LPAREN, "Expect '(' after function name.")
        args = self.parameters()
        self.consume(TokenType.RPAREN, "Expect ')' after parameters.")
        
        returns = None
        if self.match(TokenType.ARROW):
            returns = self.parse_type_annotation()
            
        self.consume(TokenType.COLON, "Expect ':' before function body.")
        
        func_node = self._loc(ast.FunctionDef(name=name, args=args, body=[], returns=returns), start_token)
        
        # Enter Function Scope
        self.scope_manager.enter_scope(ScopeType.FUNCTION)
        
        # Attach scope to function node
        func_node.scope = self.scope_manager.current_scope
        
        # Register parameters in the new scope
        for arg in args:
            self.scope_manager.define(arg.arg, SymbolType.VARIABLE)
            
        # Pre-scan local variables/functions
        self._run_pre_scanner()
        
        body = self.block()
        
        # Exit Function Scope
        self.scope_manager.exit_scope()
        
        func_node.body = body
        return func_node

    def llm_function_declaration(self) -> ast.LLMFunctionDef:
        start_token = self.previous()
        name = self.consume(TokenType.IDENTIFIER, "Expect LLM function name.").value
        self.consume(TokenType.LPAREN, "Expect '(' after function name.")
        args = self.parameters()
        self.consume(TokenType.RPAREN, "Expect ')' after parameters.")
        
        returns = None
        if self.match(TokenType.ARROW):
            returns = self.parse_type_annotation()
            
        self.consume(TokenType.COLON, "Expect ':' before function body.")
        
        llm_node = self._loc(ast.LLMFunctionDef(name=name, args=args, sys_prompt=None, user_prompt=None, returns=returns), start_token)
        
        # LLM functions also have a scope (for params)
        self.scope_manager.enter_scope(ScopeType.FUNCTION)
        
        # Attach scope to function node
        llm_node.scope = self.scope_manager.current_scope
        
        # Register parameters in the new scope
        for arg in args:
            self.scope_manager.define(arg.arg, SymbolType.VARIABLE)
            
        self._run_pre_scanner() # Though LLM bodies are special, parameters are in scope
        
        sys_prompt, user_prompt = self.llm_body()
        llm_node.sys_prompt = sys_prompt
        llm_node.user_prompt = user_prompt
        
        self.scope_manager.exit_scope()
        
        return llm_node

    def parameters(self) -> List[ast.arg]:
        params = []
        if not self.check(TokenType.RPAREN):
            while True:
                annotation = self.parse_type_annotation()
                name_token = self.consume(TokenType.IDENTIFIER, "Expect parameter name.")
                
                # Parameters are defined in the function scope (handled by function_declaration).
                # Here we just parse them.
                
                params.append(self._loc(ast.arg(arg=name_token.value, annotation=annotation), name_token))
                if not self.match(TokenType.COMMA):
                    break
        return params

    def parse_type_annotation(self) -> ast.Expr:
        start_token = self.peek()
        # 1. Base Type
        base_type = None
        if self.check(TokenType.IDENTIFIER):
            # Check if it's a valid type in symbol table
            if self.scope_manager.is_type(self.peek().value):
                self.advance()
                base_type = self._loc(ast.Name(id=self.previous().value, ctx='Load'), self.previous())
            else:
                # Fallback: Assume it's a type (e.g. forward reference or user type not yet fully registered)
                self.advance()
                base_type = self._loc(ast.Name(id=self.previous().value, ctx='Load'), self.previous())
        else:
            raise self.error(self.peek(), "Expect type name.")

        # 2. Generics
        if self.match(TokenType.LBRACKET):
            elts = []
            while True:
                elts.append(self.parse_type_annotation())
                if not self.match(TokenType.COMMA):
                    break
            
            self.consume(TokenType.RBRACKET, "Expect ']' after type arguments.")
            
            if len(elts) == 1:
                slice_expr = elts[0]
            else:
                slice_expr = self._loc(ast.ListExpr(elts=elts, ctx='Load'), start_token)
            
            return self._loc(ast.Subscript(value=base_type, slice=slice_expr, ctx='Load'), start_token)
            
        return base_type

    def block(self) -> List[ast.Stmt]:
        self.consume(TokenType.NEWLINE, "Expect newline before block.")
        self.consume(TokenType.INDENT, "Expect indent after block start.")
        stmts = []
        while not self.check(TokenType.DEDENT) and not self.is_at_end():
            if self.match(TokenType.NEWLINE):
                continue
            stmt = self.declaration()
            if stmt:
                stmts.append(stmt)
        self.consume(TokenType.DEDENT, "Expect dedent after block.")
        return stmts

    def llm_body(self) -> tuple[Optional[ast.Constant], Optional[ast.Constant]]:
        self.consume(TokenType.NEWLINE, "Expect newline before LLM block.")
        # LLM 块特殊处理：Lexer 切换模式，不生成 INDENT/DEDENT
        
        sys_prompt = None
        user_prompt = None
        
        while not self.check(TokenType.LLM_END) and not self.is_at_end():
            if self.match(TokenType.LLM_SYS):
                sys_prompt = self.parse_llm_section_content()
            elif self.match(TokenType.LLM_USER):
                user_prompt = self.parse_llm_section_content()
            elif self.match(TokenType.NEWLINE):
                continue
            else:
                raise self.error(self.peek(), "Unexpected token in LLM block. Expect '__sys__', '__user__', or 'llmend'.")

        self.consume(TokenType.LLM_END, "Expect 'llmend' to close LLM block.")
        return sys_prompt, user_prompt

    def parse_llm_section_content(self) -> ast.Constant:
        start_token = self.previous()
        content_parts = []
        while not self.is_at_end():
            if self.check(TokenType.LLM_SYS) or self.check(TokenType.LLM_USER) or self.check(TokenType.LLM_END):
                break
            
            if self.match(TokenType.RAW_TEXT):
                content_parts.append(self.previous().value)
            elif self.match(TokenType.NEWLINE):
                content_parts.append("\n")
            elif self.match(TokenType.PARAM_PLACEHOLDER):
                content_parts.append(self.previous().value)
            else:
                raise self.error(self.peek(), "Unexpected token in LLM section content.")
        
        return self._loc(ast.Constant(value="".join(content_parts)), start_token)

    def statement(self) -> ast.Stmt:
        if self.match(TokenType.RETURN):
            return self.return_statement()
        if self.match(TokenType.IF):
            return self.if_statement()
        if self.match(TokenType.WHILE):
            return self.while_statement()
        if self.match(TokenType.FOR):
            return self.for_statement()
        if self.match(TokenType.PASS):
            start = self.previous()
            self.consume_end_of_statement("Expect newline after pass.")
            return self._loc(ast.Pass(), start)
        if self.match(TokenType.BREAK):
            start = self.previous()
            self.consume_end_of_statement("Expect newline after break.")
            return self._loc(ast.Break(), start)
        if self.match(TokenType.CONTINUE):
            start = self.previous()
            self.consume_end_of_statement("Expect newline after continue.")
            return self._loc(ast.Continue(), start)
        if self.check(TokenType.IMPORT) or self.check(TokenType.FROM):
            return self.import_statement()
        
        return self.expression_statement()

    def while_statement(self) -> ast.While:
        start_token = self.previous()
        test = self.expression()
        self.consume(TokenType.COLON, "Expect ':' after condition.")
        body = self.block()
        return self._loc(ast.While(test=test, body=body, orelse=[]), start_token)

    def for_statement(self) -> ast.For:
        start_token = self.previous()
        
        expr1 = self.expression()
        
        target = None
        iter_expr = None
        
        if self.match(TokenType.IN):
            # Case: for i in list
            target = expr1
            iter_expr = self.expression()
        elif self.check(TokenType.COLON):
            # Case: for 10:  or  for ~behavior~:
            # expr1 is the iterator/condition
            target = None
            iter_expr = expr1
        else:
            raise self.error(self.peek(), "Expect 'in' or ':' in for statement.")
            
        self.consume(TokenType.COLON, "Expect ':' after for loop iterator.")
        body = self.block()
        return self._loc(ast.For(target=target, iter=iter_expr, body=body, orelse=[]), start_token)

    def import_statement(self) -> ast.Stmt:
        start_token = self.peek() # will be import or from
        if self.match(TokenType.IMPORT):
            start_token = self.previous()
            names = self.parse_aliases()
            
            # Register imported modules
            for alias_node in names:
                module_name = alias_node.name
                asname = alias_node.asname or module_name
                
                # Check module cache for scope
                # Register symbol
                sym = self.scope_manager.define(asname, SymbolType.MODULE)
                if module_name in self.module_cache:
                    sym.exported_scope = self.module_cache[module_name]
                
            self.consume_end_of_statement("Expect newline after import.")
            return self._loc(ast.Import(names=names), start_token)
            
        elif self.match(TokenType.FROM):
            start_token = self.previous()
            module_name = self.parse_dotted_name()
            self.consume(TokenType.IMPORT, "Expect 'import'.")
            names = self.parse_aliases()
            
            module_scope = self.module_cache.get(module_name)
            
            for alias_node in names:
                name = alias_node.name
                asname = alias_node.asname or name
                
                # Define in current scope
                sym_type = SymbolType.VARIABLE
                exported_scope = None
                
                if module_scope:
                    # Look up in module scope
                    origin_sym = module_scope.resolve(name)
                    if origin_sym:
                        sym_type = origin_sym.type
                        exported_scope = origin_sym.exported_scope # If importing a submodule/class
                
                sym = self.scope_manager.define(asname, sym_type)
                sym.exported_scope = exported_scope
                
                # Copy type_info if available (for PreScanner/Analyzer benefit)
                if module_scope:
                    origin_sym = module_scope.resolve(name)
                    if origin_sym:
                        sym.type_info = origin_sym.type_info
                
            self.consume_end_of_statement("Expect newline after import.")
            return self._loc(ast.ImportFrom(module=module_name, names=names, level=0), start_token)
        raise self.error(self.peek(), "Expect import statement.")

    def parse_aliases(self) -> List[ast.alias]:
        aliases = []
        while True:
            start = self.peek()
            
            if self.match(TokenType.STAR):
                aliases.append(self._loc(ast.alias(name='*', asname=None), start))
            else:
                name = self.parse_dotted_name()
                asname = None
                
                # Check for 'as' keyword
                if self.match(TokenType.AS):
                    asname = self.consume(TokenType.IDENTIFIER, "Expect alias name.").value
                
                aliases.append(self._loc(ast.alias(name=name, asname=asname), start))
            
            if not self.match(TokenType.COMMA):
                break
        return aliases

    def parse_dotted_name(self) -> str:
        name = self.consume(TokenType.IDENTIFIER, "Expect identifier.").value
        while self.match(TokenType.DOT):
            name += "." + self.consume(TokenType.IDENTIFIER, "Expect identifier after '.'.").value
        return name


    def return_statement(self) -> ast.Return:
        start_token = self.previous()
        value = None
        if not self.check(TokenType.NEWLINE) and not self.is_at_end():
            value = self.expression()
        self.consume_end_of_statement("Expect newline after return.")
        return self._loc(ast.Return(value=value), start_token)

    def if_statement(self) -> ast.If:
        start_token = self.previous()
        test = self.expression()
        self.consume(TokenType.COLON, "Expect ':' after if condition.")
        body = self.block()
        orelse: List[ast.Stmt] = []
        
        if self.match(TokenType.ELIF):
            orelse.append(self.if_statement()) # Recursive for elif
        elif self.match(TokenType.ELSE):
            self.consume(TokenType.COLON, "Expect ':' after else.")
            orelse = self.block()
            
        return self._loc(ast.If(test=test, body=body, orelse=orelse), start_token)

    def expression_statement(self) -> ast.Stmt:
        expr = self.expression()
        
        # Check if it's an assignment or compound assignment
        if self.match(TokenType.ASSIGN):
            value = self.expression()
            self.consume_end_of_statement("Expect newline after assignment.")
            return self._loc(ast.Assign(targets=[expr], value=value), self.previous())
        
        # Compound assignments
        compound_ops = {
            TokenType.PLUS_ASSIGN: '+', TokenType.MINUS_ASSIGN: '-',
            TokenType.STAR_ASSIGN: '*', TokenType.SLASH_ASSIGN: '/',
            TokenType.PERCENT_ASSIGN: '%'
        }
        
        for token_type, op_str in compound_ops.items():
            if self.match(token_type):
                value = self.expression()
                self.consume_end_of_statement("Expect newline after compound assignment.")
                return self._loc(ast.AugAssign(target=expr, op=op_str, value=value), self.previous())
            
        self.consume_end_of_statement("Expect newline after expression.")
        return self._loc(ast.ExprStmt(value=expr), self.previous())

    def expression(self) -> ast.Expr:
        return self.parse_precedence(Precedence.LOWEST)

    # --- Pratt Parser Handlers ---

    def variable(self) -> ast.Expr:
        return self._loc(ast.Name(id=self.previous().value, ctx='Load'), self.previous())

    def number(self) -> ast.Expr:
        value = self.previous().value
        if '.' in value or 'e' in value or 'E' in value:
            num = float(value)
        else:
            num = int(value)
        return self._loc(ast.Constant(value=num), self.previous())

    def string(self) -> ast.Expr:
        return self._loc(ast.Constant(value=self.previous().value), self.previous())

    def boolean(self) -> ast.Expr:
        return self._loc(ast.Constant(value=self.previous().value == 'True'), self.previous())

    def grouping(self) -> ast.Expr:
        # Check for Cast Expression: (Type) Expr
        # Look ahead to see if it's a type name followed by RPAREN
        # Lexer produces IDENTIFIER for types now.
        if self.check(TokenType.IDENTIFIER) and self.tokens[self.current + 1].type == TokenType.RPAREN:
            # Check if identifier is a type in symbol table
            possible_type = self.peek()
            if self.scope_manager.is_type(possible_type.value):
                type_token = self.advance()
                self.consume(TokenType.RPAREN, "Expect ')' after cast type.")
                
                # Cast has very high precedence (UNARY or even higher)
                value = self.parse_precedence(Precedence.UNARY)
                return self._loc(ast.CastExpr(type_name=type_token.value, value=value), type_token)
        
        expr = self.expression()
        self.consume(TokenType.RPAREN, "Expect ')' after expression.")
        return expr
    
    def list_display(self) -> ast.Expr:
        start_token = self.previous()
        elts = []
        if not self.check(TokenType.RBRACKET):
            while True:
                elts.append(self.expression())
                if not self.match(TokenType.COMMA):
                    break
        self.consume(TokenType.RBRACKET, "Expect ']' after list elements.")
        return self._loc(ast.ListExpr(elts=elts, ctx='Load'), start_token)

    def dict_display(self) -> ast.Expr:
        start_token = self.previous()
        keys = []
        values = []
        if not self.check(TokenType.RBRACE):
            while True:
                keys.append(self.expression())
                self.consume(TokenType.COLON, "Expect ':' after dict key.")
                values.append(self.expression())
                if not self.match(TokenType.COMMA):
                    break
        self.consume(TokenType.RBRACE, "Expect '}' after dict entries.")
        return self._loc(ast.Dict(keys=keys, values=values), start_token)

    def unary(self) -> ast.Expr:
        op_token = self.previous()
        op = op_token.type.name
        operand = self.parse_precedence(Precedence.UNARY)
        op_map = {"MINUS": "-", "PLUS": "+", "NOT": "not", "BIT_NOT": "~"}
        return self._loc(ast.UnaryOp(op=op_map.get(op, op), operand=operand), op_token)

    def binary(self, left: ast.Expr) -> ast.Expr:
        op_token = self.previous()
        op = op_token.type.name
        rule = self.get_rule(op_token.type)
        # Left associative: pass same precedence
        right = self.parse_precedence(rule.precedence)
        
        op_map = {
            "PLUS": "+", "MINUS": "-", "STAR": "*", "SLASH": "/", "PERCENT": "%",
            "GT": ">", "GE": ">=", "LT": "<", "LE": "<=", "EQ": "==", "NE": "!=",
            "BIT_AND": "&", "BIT_OR": "|", "BIT_XOR": "^", "LSHIFT": "<<", "RSHIFT": ">>"
        }
        op_str = op_map.get(op, op)
        
        comparison_ops = ("GT", "GE", "LT", "LE", "EQ", "NE")
        
        if op in comparison_ops:
            if isinstance(left, ast.Compare):
                # Flatten chain: a < b < c
                left.ops.append(op_str)
                left.comparators.append(right)
                return left
            return self._loc(ast.Compare(left=left, ops=[op_str], comparators=[right]), op_token)
        
        return self._loc(ast.BinOp(left=left, op=op_str, right=right), op_token)

    def logical(self, left: ast.Expr) -> ast.Expr:
        op_token = self.previous()
        op = "and" if op_token.type == TokenType.AND else "or"
        rule = self.get_rule(op_token.type)
        right = self.parse_precedence(rule.precedence)
        
        if isinstance(left, ast.BoolOp) and left.op == op:
            left.values.append(right)
            return left
            
        return self._loc(ast.BoolOp(op=op, values=[left, right]), op_token)

    def call(self, left: ast.Expr) -> ast.Call:
        start_token = self.previous() # LPAREN (consumed by advance in parse_precedence loop)
        
        # Attach intent if available
        intent = self.pending_intent
        if intent:
            self.pending_intent = None
            
        arguments = []
        if not self.check(TokenType.RPAREN):
            while True:
                if self.is_at_end():
                    raise self.error(self.peek(), "Unterminated argument list.")
                arguments.append(self.expression())
                if not self.match(TokenType.COMMA):
                    break
        self.consume(TokenType.RPAREN, "Expect ')' after arguments.")
        
        return self._loc(ast.Call(func=left, args=arguments, keywords=[], intent=intent), start_token)

    def dot(self, left: ast.Expr) -> ast.Expr:
        op_token = self.previous()
        name = self.consume(TokenType.IDENTIFIER, "Expect property name after '.'.")
        return self._loc(ast.Attribute(value=left, attr=name.value, ctx='Load'), op_token)

    def subscript(self, left: ast.Expr) -> ast.Subscript:
        start_token = self.previous() # LBRACKET
        slice_expr = self.expression()
        self.consume(TokenType.RBRACKET, "Expect ']' after subscript.")
        return self._loc(ast.Subscript(value=left, slice=slice_expr, ctx='Load'), start_token)

    def behavior_expression(self) -> ast.BehaviorExpr:
        start_token = self.previous()
        # Expect raw text and variables until next BEHAVIOR_MARKER
        content_parts = []
        variables = []
        
        while not self.check(TokenType.BEHAVIOR_MARKER):
            if self.is_at_end():
                raise self.error(self.peek(), "Unterminated behavior expression.")
                
            if self.match(TokenType.RAW_TEXT):
                content_parts.append(self.previous().value)
            elif self.match(TokenType.VAR_REF):
                var_name = self.previous().value # e.g. "$x"
                variables.append(var_name)
                content_parts.append(var_name)
            else:
                self.advance() # Skip unknown
        
        self.consume(TokenType.BEHAVIOR_MARKER, "Expect closing '~~'.")
        
        # Check for intent
        intent = self.pending_intent
        if intent:
            self.pending_intent = None
            
        return self._loc(ast.BehaviorExpr(content="".join(content_parts), variables=variables, intent=intent), start_token)
