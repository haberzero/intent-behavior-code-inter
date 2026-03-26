from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from . import ast as ast_domain
from .symbols import Symbol, SymbolTable

@dataclass
class CompilationResult:
    """
    语义分析阶段的单模块产出物协议。
    它是蓝图层（Domain）的基本构成单元。
    """
    module_ast: ast_domain.IbModule
    symbol_table: SymbolTable
    node_scenes: Dict[ast_domain.IbASTNode, Any] = field(default_factory=dict) # Node object -> Scene name
    node_to_symbol: Dict[ast_domain.IbASTNode, Symbol] = field(default_factory=dict) # Node object -> Symbol object
    node_to_type: Dict[ast_domain.IbASTNode, Any] = field(default_factory=dict) # Node object -> Type name
    node_is_deferred: Dict[ast_domain.IbASTNode, bool] = field(default_factory=dict) # Node object -> bool
    node_intents: Dict[ast_domain.IbASTNode, List[ast_domain.IbIntentInfo]] = field(default_factory=dict) # Node object -> List of IntentInfo
    node_to_loc: Dict[ast_domain.IbASTNode, Any] = field(default_factory=dict) # Node object -> Location info
    decision_maps: Dict[ast_domain.IbASTNode, Dict[str, str]] = field(default_factory=dict) # Node object -> Decision Map
    
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
