from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.kernel.types.descriptors import TypeDescriptor

from core.kernel.symbols import Symbol

class SideTableManager:
    """
    [IES 2.1] 侧表管理器。
    统一管理语义分析过程中产生的元数据侧表。
    """
    def __init__(self):
        self.node_scenes: Dict[Any, Any] = {}
        self.node_to_symbol: Dict[Any, Symbol] = {}
        self.node_to_type: Dict[Any, 'TypeDescriptor'] = {}
        self.node_is_deferred: Dict[Any, bool] = {}
        self.node_intents: Dict[Any, List[Any]] = {}
        self.node_to_loc: Dict[Any, Any] = {}
        self.decision_maps: Dict[Any, Dict[str, str]] = {}

    def bind_symbol(self, node: Any, sym: Symbol) -> None:
        self.node_to_symbol[node] = sym

    def bind_type(self, node: Any, type_desc: 'TypeDescriptor') -> None:
        self.node_to_type[node] = type_desc

    def bind_scene(self, node: Any, scene: Any) -> None:
        self.node_scenes[node] = scene

    def bind_decision_map(self, node: Any, decision_map: Dict[str, str]) -> None:
        self.decision_maps[node] = decision_map

    def set_deferred(self, node: Any, is_deferred: bool = True) -> None:
        self.node_is_deferred[node] = is_deferred

    def is_deferred(self, node: Any) -> bool:
        return self.node_is_deferred.get(node, False)

    def bind_intents(self, node: Any, intents: List[Any]) -> None:
        self.node_intents[node] = intents

    def bind_location(self, node: Any, loc: Any) -> None:
        self.node_to_loc[node] = loc

    def get_symbol(self, node: Any) -> Optional[Symbol]:
        return self.node_to_symbol.get(node)

    def get_type(self, node: Any) -> Optional['TypeDescriptor']:
        return self.node_to_type.get(node)

    def get_scene(self, node: Any) -> Optional[Any]:
        return self.node_scenes.get(node)

    def get_intents(self, node: Any) -> Optional[List[Any]]:
        return self.node_intents.get(node)

    def get_location(self, node: Any) -> Optional[Any]:
        return self.node_to_loc.get(node)

    def clear(self) -> None:
        self.node_scenes.clear()
        self.node_to_symbol.clear()
        self.node_to_type.clear()
        self.node_is_deferred.clear()
        self.node_intents.clear()
        self.node_to_loc.clear()
