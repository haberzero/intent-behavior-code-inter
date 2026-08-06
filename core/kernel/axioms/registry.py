from typing import Dict, Optional, Type, List
from core.kernel.axioms.protocols import TypeAxiom

class AxiomRegistry:
    """
    [Registry] 公理注册表
    作为中介者，解耦 TypeDescriptor 与具体 Axiom 实现之间的循环依赖。
    现在改为实例管理以支持多引擎隔离。
    """
    def __init__(self):
        self._axioms: Dict[str, TypeAxiom] = {}

    def register(self, axiom: TypeAxiom):
        self._axioms[axiom.name] = axiom

    def get_axiom(self, name: str) -> Optional[TypeAxiom]:
        return self._axioms.get(name)

    def get_all_names(self) -> List[str]:
        return list(self._axioms.keys())

    def clear(self):
        self._axioms.clear()
