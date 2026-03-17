from typing import Any, Dict, Optional, Union, TYPE_CHECKING
import sys
from .descriptors import TypeDescriptor, FunctionMetadata, ListMetadata, DictMetadata
from core.domain.symbols import FunctionSymbol, VariableSymbol, SymbolKind, SymbolFactory

if TYPE_CHECKING:
    from .registry import MetadataRegistry
    from core.domain.symbols import Symbol

class TypeHydrator:
    """
    UTS 类型水合服务。
    负责将原始描述符与符号系统（Symbols）及公理系统（Axioms）建立关联。
    """
    def __init__(self, registry: 'MetadataRegistry'):
        self._registry = registry

    def inject_axioms(self, descriptor: TypeDescriptor):
        """[IoC] 从公理注册表中获取并注入公理能力"""
        axiom_registry = self._registry.get_axiom_registry()
        if not axiom_registry:
            return
            
        # [IES 2.1 Axiom-Driven] 使用 get_base_axiom_name 自动发现公理名称，彻底消除 isinstance 硬编码
        axiom_name = descriptor.get_base_axiom_name()
        descriptor._axiom = axiom_registry.get_axiom(axiom_name)
        
        # [Axiom-Driven Schema] 从公理中注入方法签名
        if descriptor._axiom:
            try:
                method_descs = descriptor._axiom.get_methods()
                if method_descs:
                    for m_name, m_desc in method_descs.items():
                        # [Hydration] 确保从公理注入的方法元数据使用当前注册表的类型标识
                        hydrated_m_desc = self.hydrate_metadata(m_desc)
                        
                        sym = FunctionSymbol(
                            name=m_name, 
                            kind=SymbolKind.FUNCTION, 
                            descriptor=hydrated_m_desc, 
                            metadata={"is_builtin": True, "axiom_provided": True}
                        )
                        descriptor.members[m_name] = sym
                        
            except Exception as e:
                # [Strict Error Handling] 核心注册失败不再静默
                print(f"Critical Error: Failed to inject methods from axiom '{axiom_name}' into descriptor: {e}", file=sys.stderr)
                raise RuntimeError(f"Axiom injection failed for '{axiom_name}': {e}") from e

    def deep_hydrate(self, desc: TypeDescriptor):
        """深度水合描述符的成员列表，确保每个成员都被正确包装为 Symbol 对象"""
        if not desc.members:
            return
            
        new_members = {}
        for name, member in desc.members.items():
            # [IES 2.1 Refactor] 统一通过 Symbol.walk_references 多态处理
            # [Active Defense] 严禁使用裸描述符，必须通过 SymbolFactory 包装
            if hasattr(member, 'walk_references'):
                member.walk_references(self.hydrate_metadata)
                new_members[name] = member
            else:
                new_members[name] = member
        
        desc.members = new_members

    def hydrate_metadata(self, descriptor: Union[TypeDescriptor, str]) -> TypeDescriptor:
        """递归填充描述符及其成员"""
        if descriptor is None: return None
        
        # 0. 如果是字符串引用，尝试解析
        if isinstance(descriptor, str):
            resolved = self._registry.resolve(descriptor)
            if resolved: return resolved
            raise RuntimeError(f"UTS Error: Type '{descriptor}' not found in registry. [IES 2.0 No-Guessing Rule Violation]")

        # 1. 物理隔离：确保描述符是从当前注册表克隆出来的 (Interning)
        # 如果描述符已经绑定到当前注册表，直接返回
        if descriptor._registry is self._registry:
            return descriptor
            
        # 2. [IES 2.1 Refactor] 多态水化：利用 walk_references 递归处理子描述符
        descriptor.walk_references(self.hydrate_metadata)
        
        # 3. 注入公理能力
        self.inject_axioms(descriptor)
        
        # 4. 绑定注册表并完成注册
        descriptor._registry = self._registry
        return self._registry.register(descriptor)
