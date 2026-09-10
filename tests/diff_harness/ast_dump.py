"""AST 规范 dumper——IBC 语法树 → 规范字符串形态（AST 级差分参考工具）。

差分 harness 的 AST 级门：Python parser（参考）与 Rust parser 对同一源码产出
的 AST 须经本 dumper 转成规范字符串，逐字节等价（零差异）方可放行。

规范形态：`<节点类名>(field1=<val1>, field2=<val2>, ...)`——字段按 dataclass
声明序，子节点递归，标量按 repr，列表 `[e1, e2, ...]`，None = "None"。含位置
信息（lineno/col_offset/end_lineno/end_col_offset）——Rust parser 须对齐 Python
parser 的位置跟踪。
"""
from __future__ import annotations

import dataclasses


# IbASTNode 基类位置字段（structure 模式排除——AST 结构差分核心 = 节点类型 +
# 字段值；位置跟踪 = Rust parser 后续增量单独验证）
_POSITION_FIELDS = {"lineno", "col_offset", "end_lineno", "end_col_offset"}


def _dump_value(value, include_positions: bool = True) -> str:
    """单值规范形态（标量/列表/AST 节点递归）。"""
    if value is None:
        return "None"
    if isinstance(value, bool):  # bool 先于 int
        return repr(value)
    if isinstance(value, (int, float, str)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_dump_value(v, include_positions) for v in value) + "]"
    if isinstance(value, dict):
        # 键排序（确定性）
        return "{" + ", ".join(
            f"{_dump_value(k, include_positions)}: {_dump_value(v, include_positions)}"
            for k, v in sorted(value.items())
        ) + "}"
    # AST 节点（IbASTNode 及其子类）——经 dataclass 字段递归
    if dataclasses.is_dataclass(value):
        fields = dataclasses.fields(value)
        if include_positions:
            parts = [
                f"{f.name}={_dump_value(getattr(value, f.name), include_positions)}"
                for f in fields
            ]
        else:
            parts = [
                f"{f.name}={_dump_value(getattr(value, f.name), include_positions)}"
                for f in fields
                if f.name not in _POSITION_FIELDS
            ]
        return f"{type(value).__name__}(" + ", ".join(parts) + ")"
    # 兜底：repr（未知类型）
    return repr(value)


def ast_dump(node, include_positions: bool = True) -> str:
    """AST 根节点 → 规范字符串形态（AST 级差分参考）。

    include_positions=False = structure 模式（排除位置字段——AST 结构差分核心）。
    """
    return _dump_value(node, include_positions)


def parse_ast_dump(source: str, include_positions: bool = True) -> str:
    """IBC 源码 → 经 Python parser 的 AST 规范形态（参考基准）。"""
    from core.compiler.lexer.lexer import Lexer
    from core.compiler.parser.parser import Parser
    tokens = Lexer(source).tokenize()
    module = Parser(tokens).parse()
    return ast_dump(module, include_positions)
