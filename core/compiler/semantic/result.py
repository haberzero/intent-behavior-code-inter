from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from core.types import parser_types as ast
from .symbols import SymbolTable

@dataclass
class CompilationResult:
    """
    语义分析阶段的产出物协议。
    这是分析器向解释器交付的标准产物。
    """
    module_ast: ast.Module
    symbol_table: SymbolTable
    
    @property
    def has_errors(self) -> bool:
        # 这个属性通常由 IssueTracker 决定，这里仅作为协议占位
        return False

    def to_dict(self) -> Dict[str, Any]:
        """使用平铺化序列化器将结果序列化为字典"""
        from .serializer import FlatSerializer
        serializer = FlatSerializer()
        return serializer.serialize_result(self)
