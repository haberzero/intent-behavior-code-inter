# 向后兼容垫片 — 实际定义已移至 core/runtime/shared/op_constants.py
# 此文件保留以避免破坏可能存在的 ``from core.runtime.interpreter.constants import ...``
from core.runtime.shared.op_constants import OP_MAPPING, AST_OP_MAP, UNARY_OP_MAPPING

__all__ = ["OP_MAPPING", "AST_OP_MAP", "UNARY_OP_MAPPING"]
