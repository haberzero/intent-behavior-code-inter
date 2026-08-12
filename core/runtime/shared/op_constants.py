# IBCI 运行时常量定义 (运算符映射等)
#
# 此模块位于 core/runtime/shared/ —— 运行时各子包（interpreter / vm / objects）
# 共享的纯数据叶子模块，无任何跨包导入，用于打破 interpreter ↔ vm 循环依赖。

# 二元运算符映射 (模拟汇编操作码)
OP_MAPPING = {
    '+': '__add__',
    '-': '__sub__',
    '*': '__mul__',
    '/': '__truediv__',
    '//': '__floordiv__',
    '%': '__mod__',
    '**': '__pow__',
    '&': '__and__',
    '|': '__or__',
    '^': '__xor__',
    '<<': '__lshift__',
    '>>': '__rshift__',
    '==': '__eq__',
    '!=': '__ne__',
    '<': '__lt__',
    '<=': '__le__',
    '>': '__gt__',
    '>=': '__ge__',
}

# AST 节点符号到标准运算符的映射 (归一化转换)
AST_OP_MAP = {
    # 二元/复合赋值
    'Add': '+', 'Sub': '-', 'Mult': '*', 'Div': '/', 'FloorDiv': '//', 'Mod': '%',
    'LShift': '<<', 'RShift': '>>', 'BitAnd': '&', 'BitOr': '|', 'BitXor': '^',
    # 一元
    'UAdd': '+', 'USub': '-', 'Not': 'not', 'Invert': '~',
}

# 一元运算符映射
UNARY_OP_MAPPING = {
    '-': '__neg__',
    '+': '__pos__',
    'not': '__not__',
    '~': '__invert__',
}
