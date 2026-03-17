from core.compiler.lexer.tokens import TokenType

"""
[IES 2.1] 语法常量定义。
统一管理 Parser 中使用的保留标识符名称和运算符映射。
"""

# 保留标识符 (用于 AST 节点的 ID 字段)
ID_SELF = "self"
ID_VAR = "var"
ID_CALLABLE = "callable"

# 运算符映射 (键已由字符串重构为 TokenType 枚举，彻底消除解析器中的字符串比对)
OP_MAP = {
    TokenType.PLUS: "+",
    TokenType.MINUS: "-",
    TokenType.STAR: "*",
    TokenType.SLASH: "/",
    TokenType.PERCENT: "%",
    TokenType.EQ: "==",
    TokenType.NE: "!=",
    TokenType.GT: ">",
    TokenType.LT: "<",
    TokenType.GE: ">=",
    TokenType.LE: "<=",
    TokenType.BIT_AND: "&",
    TokenType.BIT_OR: "|",
    TokenType.BIT_XOR: "^",
    TokenType.LSHIFT: "<<",
    TokenType.RSHIFT: ">>",
    TokenType.NOT: "not",
    TokenType.BIT_NOT: "~",
}
