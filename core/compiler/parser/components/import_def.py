from typing import List, Optional
from core.compiler.common.tokens import TokenType
from core.kernel import ast as ast
from core.compiler.parser.core.component import BaseComponent
from core.compiler.dependencies import ImportInfo, ImportType

# 宿主绑定伪模块名（标记"导入裸 Python 空间"）。
# ``import python "pkg" as lib: bind ...``——非保留字，作为 import 后的标识符识别。
HOST_MODULE_NAME = "python"


class ImportComponent(BaseComponent):
    """
    Component for parsing import statements.
    Produces AST nodes for further semantic analysis.
    """

    def __init__(self, context):
        super().__init__(context)

    def parse_import(self) -> ast.IbImport:
        """Parses 'import a.b, c as d'."""
        start_token = self.stream.previous()

        # 宿主绑定形态：``import python "pkg" as lib [bind 块]``。
        # 仅当 ``python`` 标识符后紧跟字符串模块名才走宿主绑定——避免误伤
        # 真实名为 ``python`` 的普通模块导入（``import python`` / ``import python as p``）。
        if self.stream.check(TokenType.IDENTIFIER):
            if self.stream.peek().value == HOST_MODULE_NAME and self.stream.peek(1).type == TokenType.STRING:
                return self.parse_host_import(start_token)

        names = self.parse_aliases()
        self.stream.consume_end_of_statement("Expect newline after import.")

        return self._loc(ast.IbImport(names=names), start_token)

    def parse_host_import(self, start_token) -> ast.IbHostImport:
        """Parses ``import python "pkg" as lib: bind ...``.

        宿主绑定 import：导入裸 Python 模块/包，显式声明绑定的成员（bind 块）。
        ``python`` 伪模块标识符已被消费（parse_import 已 match）。
        """
        self.stream.consume(TokenType.IDENTIFIER, "Expect 'python' pseudo-module.")  # 'python'
        module_name = self.stream.consume(TokenType.STRING, "Expect string module name after 'python'.").value

        asname = None
        if self.stream.match(TokenType.AS):
            asname = self.stream.consume(TokenType.IDENTIFIER, "Expect binding name after 'as'.").value

        bindings: List[ast.IbHostBinding] = []
        if self.stream.match(TokenType.COLON):
            bindings = self.parse_bind_block()
        else:
            self.stream.consume_end_of_statement("Expect newline after host import.")

        node = ast.IbHostImport(
            module_name=module_name,
            asname=asname,
            bindings=bindings,
        )
        return self._loc(node, start_token)

    def parse_bind_block(self) -> List[ast.IbHostBinding]:
        """Parses the ``:`` + indented block of ``bind`` declarations."""
        self.stream.consume(TokenType.NEWLINE, "Expect newline before bind block.")
        self.stream.consume(TokenType.INDENT, "Expect indent after host import block start.")
        bindings: List[ast.IbHostBinding] = []
        while not self.stream.check(TokenType.DEDENT) and not self.stream.is_at_end():
            if self.stream.match(TokenType.NEWLINE):
                continue
            start = self.stream.peek()
            self.stream.consume(TokenType.BIND, "Expect 'bind' in host import block.")
            binding = self.parse_bind_declaration()
            if binding is not None:
                bindings.append(self._loc(binding, start))
        self.stream.consume(TokenType.DEDENT, "Expect dedent after bind block.")
        return bindings

    def parse_bind_declaration(self) -> ast.IbHostBinding:
        """Parses one ``bind`` declaration.

        - 方法：``bind name(x: T, y: U) -> R``
        - 属性：``bind name -> T``
        """
        name_tok = self.stream.consume(TokenType.IDENTIFIER, "Expect binding member name after 'bind'.")

        # 方法签名（bind name(params) -> ret）
        if self.stream.match(TokenType.LPAREN):
            params: List[ast.IbHostBindingParam] = []
            if not self.stream.check(TokenType.RPAREN):
                while True:
                    pname = self.stream.consume(TokenType.IDENTIFIER, "Expect parameter name in bind signature.")
                    annotation = None
                    if self.stream.match(TokenType.COLON):
                        annotation = self.context.type_parser.parse_type_annotation()
                    params.append(self._loc(ast.IbHostBindingParam(name=pname.value, annotation=annotation), pname))
                    if not self.stream.match(TokenType.COMMA):
                        break
            self.stream.consume(TokenType.RPAREN, "Expect ')' after bind parameters.")
            self.stream.consume(TokenType.ARROW, "Expect '->' after bind parameters.")
            return_type = self.context.type_parser.parse_type_annotation()
            self.stream.consume_end_of_statement("Expect newline after bind declaration.")
            return ast.IbHostBinding(
                name=name_tok.value,
                is_method=True,
                params=params,
                return_type=return_type,
            )

        # 属性（bind name -> T）
        self.stream.consume(TokenType.ARROW, "Expect '->' after bind attribute name.")
        attr_type = self.context.type_parser.parse_type_annotation()
        self.stream.consume_end_of_statement("Expect newline after bind declaration.")
        return ast.IbHostBinding(
            name=name_tok.value,
            is_method=False,
            return_type=attr_type,
        )

    def parse_from_import(self) -> ast.IbImportFrom:
        """Parses 'from .a import b'."""
        start_token = self.stream.previous() # 'from' already consumed
        
        # Handle relative imports: from . import x, from ..foo import x
        level = 0
        while self.stream.match(TokenType.DOT):
            level += 1
            
        module_name = None
        if self.stream.check(TokenType.IDENTIFIER):
            module_name = self.parse_dotted_name()
            
        self.stream.consume(TokenType.IMPORT, "Expect 'import'.")
        names = self.parse_aliases()
        
        self.stream.consume_end_of_statement("Expect newline after import.")
        return self._loc(ast.IbImportFrom(module=module_name, names=names, level=level), start_token)

    def parse_aliases(self) -> List[ast.IbAlias]:
        aliases = []
        while True:
            start = self.stream.peek()
            
            # Handle '*' for from ... import *
            if self.stream.match(TokenType.STAR):
                aliases.append(self._loc(ast.IbAlias(name="*", asname=None), start))
            else:
                name = self.parse_dotted_name()
                asname = None
                if self.stream.match(TokenType.AS):
                    asname = self.stream.consume(TokenType.IDENTIFIER, "Expect alias name after 'as'.").value
                
                aliases.append(self._loc(ast.IbAlias(name=name, asname=asname), start))
            
            if not self.stream.match(TokenType.COMMA):
                break
        return aliases

    def parse_dotted_name(self) -> str:
        parts = [self.stream.consume(TokenType.IDENTIFIER, "Expect identifier in dotted name.").value]
        while self.stream.match(TokenType.DOT):
            parts.append(self.stream.consume(TokenType.IDENTIFIER, "Expect identifier after '.'.").value)
        return ".".join(parts)
