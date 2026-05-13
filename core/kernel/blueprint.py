from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from . import ast as ast_domain
from .symbols import Symbol, SymbolTable

@dataclass
class CompilationResult:
    """
    语义分析阶段的单模块产出物协议（V2 UID-based）。
    它是蓝图层（Domain）的基本构成单元。

    V2架构改进：使用UID而不是对象引用，使结果可序列化和跨进程传递。

    注意：意图注释不再使用侧表存储，而是作为独立 AST 节点
    (IbIntentAnnotation, IbIntentStackOperation) 由解释器直接处理。
    """
    module_ast: ast_domain.IbModule
    symbol_table: SymbolTable
    # V2: UID-based映射，可序列化
    node_to_symbol: Dict[str, str] = field(default_factory=dict)  # node_uid -> symbol_uid
    node_to_type: Dict[str, str] = field(default_factory=dict)  # node_uid -> type_uid
    node_is_callable_instance: Dict[str, bool] = field(default_factory=dict)  # node_uid -> bool
    node_capture_mode: Dict[str, str] = field(default_factory=dict)  # node_uid -> 'lambda'|'snapshot'
    node_to_loc: Dict[str, Any] = field(default_factory=dict)  # node_uid -> Location info
    
    @property
    def has_errors(self) -> bool:
        return False

@dataclass
class CompilationArtifact:
    """
    编译器交付给解释器的完整蓝图。
    它包含了一个项目所有模块的已决议 AST 和符号表。
    """
    # 模块名到编译结果的映射
    modules: Dict[str, CompilationResult] = field(default_factory=dict)
    
    # 入口模块名
    entry_module: Optional[str] = None
    
    # 全局公共符号
    global_symbols: Optional[Dict[str, Any]] = None

    def get_module(self, name: str) -> Optional[CompilationResult]:
        return self.modules.get(name)

    def add_module(self, name: str, result: CompilationResult):
        self.modules[name] = result

    @property
    def has_errors(self) -> bool:
        return any(m.has_errors for m in self.modules.values())
