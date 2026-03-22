from typing import Any, Dict, Optional, Union, TYPE_CHECKING
import sys
from .descriptors import TypeDescriptor, FunctionMetadata, ListMetadata, DictMetadata

if TYPE_CHECKING:
    from .registry import MetadataRegistry
    from core.kernel.symbols import Symbol

class AxiomHydrator:
    """
    UTS 公理水合服务。
    负责将原始描述符与符号系统（Symbols）及公理系统（Axioms）建立关联。
    """
    def __init__(self, registry: 'MetadataRegistry'):
        self._registry = registry
        self._processing: set = set()

    def inject_axioms(self, descriptor: TypeDescriptor):
        """[IoC] 从公理注册表中获取并注入公理能力"""
        axiom_registry = self._registry.get_axiom_registry()
        if not axiom_registry:
            raise RuntimeError(
                f"Critical: AxiomRegistry not available for descriptor '{descriptor.name}'. "
                f"Cannot hydrate descriptor without axiom binding."
            )

        axiom_name = descriptor.get_base_axiom_name()
        descriptor._axiom = axiom_registry.get_axiom(axiom_name)

        if descriptor._axiom:
            try:
                method_descs = descriptor._axiom.get_methods()
                if method_descs:
                    # [ARCHITECTURE NOTE]
                    # 延迟导入 FunctionSymbol 和 SymbolKind 以避免循环依赖：
                    #   axiom_hydrator.py → descriptors.py → types/__init__.py →
                    #   registry.py → axiom_hydrator.py (顶层会形成循环)
                    #
                    # Symbol ↔ TypeDescriptor 的双向引用是设计的内在需求：
                    #   - Symbol.descriptor: 符号需要知道自己的类型
                    #   - TypeDescriptor.members: 类型需要知道自己的成员
                    # 这反映了编译器中符号表与类型系统的固有耦合关系。
                    #
                    # 未来如需彻底解耦，可考虑：
                    #   1. 引入 StaticType 中间接口层
                    #   2. 将 SymbolKind 等枚举移至独立子模块
                    #   3. 使用依赖注入容器管理初始化顺序
                    from core.kernel.symbols import FunctionSymbol, SymbolKind
                    for m_name, m_desc in method_descs.items():
                        hydrated_m_desc = self.hydrate_metadata(m_desc)
                        sym = FunctionSymbol(
                            name=m_name,
                            kind=SymbolKind.FUNCTION,
                            descriptor=hydrated_m_desc,
                            metadata={"is_builtin": True, "axiom_provided": True}
                        )
                        descriptor.members[m_name] = sym

            except Exception as e:
                print(f"Critical Error: Failed to inject methods from axiom '{axiom_name}' into descriptor: {e}", file=sys.stderr)
                raise RuntimeError(f"Axiom injection failed for '{axiom_name}': {e}") from e

    def deep_hydrate(self, desc: TypeDescriptor):
        """深度水合描述符的成员列表，确保每个成员都被正确包装为 Symbol 对象"""
        if not desc.members:
            return

        new_members = {}
        for name, member in desc.members.items():
            if hasattr(member, 'walk_references'):
                member.walk_references(self.hydrate_metadata)
                new_members[name] = member
            else:
                new_members[name] = member

        desc.members = new_members

    def hydrate_metadata(self, descriptor: Union[TypeDescriptor, str]) -> TypeDescriptor:
        """递归填充描述符及其成员"""
        if descriptor is None: return None

        if isinstance(descriptor, str):
            resolved = self._registry.resolve(descriptor)
            if resolved: return resolved
            raise RuntimeError(f"UTS Error: Type '{descriptor}' not found in registry.")

        if descriptor._registry is self._registry:
            return descriptor

        key = descriptor.name
        if key in self._registry._descriptors:
            cached = self._registry._descriptors[key]
            if cached._registry is self._registry:
                return cached

        obj_id = id(descriptor)
        if obj_id in self._processing:
            return descriptor

        self._processing.add(obj_id)
        try:
            descriptor._registry = self._registry
            descriptor.walk_references(self.hydrate_metadata)
            self.inject_axioms(descriptor)
            return self._registry.register(descriptor)
        finally:
            self._processing.discard(obj_id)
