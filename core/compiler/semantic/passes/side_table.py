from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.kernel.spec import IbSpec

from core.kernel.symbols import Symbol

class SideTableManager:
    """
     侧表管理器。
    统一管理语义分析过程中产生的元数据侧表。

    注意：意图注释不再使用侧表存储，而是作为独立 AST 节点
    (IbIntentAnnotation, IbIntentStackOperation) 由解释器直接处理。
    """
    def __init__(self):
        self.node_to_symbol: Dict[Any, Symbol] = {}
        self.node_to_type: Dict[Any, 'IbSpec'] = {}
        self.node_is_deferred: Dict[Any, bool] = {}
        self.node_deferred_mode: Dict[Any, str] = {}
        self.node_to_loc: Dict[Any, Any] = {}
        self.node_protection: Dict[Any, Any] = {}

    def bind_protection(self, target_node: Any, handler_node: Any) -> None:
        """建立保护关系侧表"""
        self.node_protection[target_node] = handler_node

    def bind_symbol(self, node: Any, sym: Symbol) -> None:
        self.node_to_symbol[node] = sym

    def bind_type(self, node: Any, type_desc: 'IbSpec') -> None:
        self.node_to_type[node] = type_desc

    def set_deferred(self, node: Any, is_deferred: bool = True) -> None:
        self.node_is_deferred[node] = is_deferred

    def set_deferred_mode(self, node: Any, mode: str) -> None:
        self.node_deferred_mode[node] = mode

    def get_deferred_mode(self, node: Any) -> Optional[str]:
        return self.node_deferred_mode.get(node)

    def is_deferred(self, node: Any) -> bool:
        return self.node_is_deferred.get(node, False)

    def bind_location(self, node: Any, loc: Any) -> None:
        self.node_to_loc[node] = loc

    def get_symbol(self, node: Any) -> Optional[Symbol]:
        return self.node_to_symbol.get(node)

    def get_type(self, node: Any) -> Optional['IbSpec']:
        return self.node_to_type.get(node)

    def get_location(self, node: Any) -> Optional[Any]:
        return self.node_to_loc.get(node)

    def clear(self) -> None:
        self.node_to_symbol.clear()
        self.node_to_type.clear()
        self.node_is_deferred.clear()
        self.node_deferred_mode.clear()
        self.node_to_loc.clear()
        self.node_protection.clear()
