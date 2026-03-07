import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from core.compiler.semantic.result import CompilationResult

@dataclass
class CompilationArtifact:
    """
    编译器交付给解释器的完整蓝图。
    它包含了一个项目所有模块的已决议 AST 和符号表。
    """
    # 模块名到编译结果的映射 (e.g., "utils.math" -> CompilationResult)
    modules: Dict[str, CompilationResult] = field(default_factory=dict)
    
    # 入口模块名 (e.g., "main")
    entry_module: Optional[str] = None
    
    # 全局公共符号 (如从 primitives.ibci 注入的内置类)
    global_symbols: Optional[Dict[str, Any]] = None

    def get_module(self, name: str) -> Optional[CompilationResult]:
        return self.modules.get(name)

    def add_module(self, name: str, result: CompilationResult):
        self.modules[name] = result

    @property
    def has_errors(self) -> bool:
        return any(m.has_errors for m in self.modules.values())

    def serialize(self) -> str:
        """
        将完整的编译蓝图序列化为 JSON 字符串。
        证明编译器可以在完全没有解释器的情况下产出“施工图纸”。
        """
        # 注意：这里需要一个递归处理 AST 和 SymbolTable 的序列化器
        # 目前先提供一个结构化的 dict 转换
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        """使用统一的平铺化序列化器将整个项目序列化为字典"""
        from core.compiler.semantic.serializer import FlatSerializer
        serializer = FlatSerializer()
        return serializer.serialize_artifact(self)
