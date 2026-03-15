from typing import Any, Dict, Optional, Union, TYPE_CHECKING
import sys
from .descriptors import TypeDescriptor, FunctionMetadata, ListMetadata, DictMetadata
from core.domain.symbols import FunctionSymbol, VariableSymbol, SymbolKind

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
            
        axiom_name = descriptor.name
        if isinstance(descriptor, ListMetadata):
            axiom_name = "list"
        elif isinstance(descriptor, DictMetadata):
            axiom_name = "dict"
        
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
            # 如果成员是裸的 TypeDescriptor，将其包装为 Symbol
            if isinstance(member, TypeDescriptor):
                hydrated_desc = self.hydrate_metadata(member)
                if hasattr(hydrated_desc, "param_types"): # 启发式判断是否为函数
                    sym = FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, descriptor=hydrated_desc)
                else:
                    sym = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, descriptor=hydrated_desc)
                new_members[name] = sym
            elif hasattr(member, 'descriptor'): # 已经是 Symbol
                member.descriptor = self.hydrate_metadata(member.descriptor)
                new_members[name] = member
            else:
                new_members[name] = member
        
        desc.members = new_members

    def hydrate_metadata(self, desc: Union[TypeDescriptor, str]) -> TypeDescriptor:
        """递归确保描述符及其引用的所有类型都来自当前注册表实例"""
        if isinstance(desc, str):
            resolved = self._registry.resolve(desc)
            if resolved: return resolved
            
            # [IES 2.0 Strict] 禁止类型猜测。所有外部发现的元数据必须在 spec.py 中显式定义。
            raise RuntimeError(f"UTS Error: Type '{desc}' not found in registry. [IES 2.0 No-Guessing Rule Violation]")

        if desc._registry is self._registry: return desc
        
        # 如果是原子类型，尝试在当前注册表中查找
        if desc.__class__ is TypeDescriptor or isinstance(desc, (ListMetadata, DictMetadata)):
            # 优先查找同名且同路径的已注册描述符
            resolved = self._registry.resolve(desc.name, desc.module_path)
            if resolved and resolved is not desc: 
                return resolved
            
            # 如果没找到且是原子类型，注入注册表上下文
            if desc.__class__ is TypeDescriptor:
                desc._registry = self._registry
                return desc
            
        # 如果是复合类型，递归处理其成员
        if isinstance(desc, FunctionMetadata):
            desc.param_types = [self.hydrate_metadata(p) for p in desc.param_types]
            if desc.return_type:
                desc.return_type = self.hydrate_metadata(desc.return_type)
        elif isinstance(desc, ListMetadata):
            if desc.element_type:
                desc.element_type = self.hydrate_metadata(desc.element_type)
        elif isinstance(desc, DictMetadata):
            if desc.key_type:
                desc.key_type = self.hydrate_metadata(desc.key_type)
            if desc.value_type:
                desc.value_type = self.hydrate_metadata(desc.value_type)
        
        desc._registry = self._registry
        return desc
