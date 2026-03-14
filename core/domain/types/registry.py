from typing import Optional, Any, Dict, List, TYPE_CHECKING
import sys
from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel, core_trace

from .descriptors import (
    TypeDescriptor, ListMetadata, DictMetadata, FunctionMetadata, 
    ClassMetadata, BoundMethodMetadata
)
from core.domain.symbols import SymbolKind, FunctionSymbol

if TYPE_CHECKING:
    from core.domain.axioms.protocols import TypeAxiom
    from core.domain.axioms.registry import AxiomRegistry

class TypeFactory:
    """
    描述符驻留工厂。
    基于结构哈希确保同构描述符在内存中仅存一份。
    """
    def __init__(self):
        self._memo: Dict[str, TypeDescriptor] = {}

    def _get_intern_key(self, kind: str, name: str, module: Optional[str], **kwargs) -> str:
        # 构建结构化哈希键
        # 对于复合类型，kwargs 应包含其子类型的 ID 或 UID
        sorted_items = sorted(kwargs.items())
        return f"{kind}:{module or ''}:{name}:{str(sorted_items)}"

    def create_primitive(self, name: str, is_nullable: bool = True) -> TypeDescriptor:
        key = self._get_intern_key("Primitive", name, None, nullable=is_nullable)
        if key not in self._memo:
            self._memo[key] = TypeDescriptor(name=name, is_nullable=is_nullable)
        return self._memo[key]

    def create_list(self, element_type: TypeDescriptor) -> ListMetadata:
        key = self._get_intern_key("List", "", None, element=id(element_type))
        if key not in self._memo:
            self._memo[key] = ListMetadata(element_type=element_type)
        return self._memo[key]

    def create_dict(self, key_type: TypeDescriptor, value_type: TypeDescriptor) -> DictMetadata:
        key = self._get_intern_key("Dict", "", None, k=id(key_type), v=id(value_type))
        if key not in self._memo:
            self._memo[key] = DictMetadata(key_type=key_type, value_type=value_type)
        return self._memo[key]

    def create_function(self, params: List[TypeDescriptor], ret: Optional[TypeDescriptor]) -> FunctionMetadata:
        p_ids = [id(p) for p in params]
        r_id = id(ret) if ret else 0
        key = self._get_intern_key("Func", "", None, p=p_ids, r=r_id)
        if key not in self._memo:
            self._memo[key] = FunctionMetadata(param_types=params, return_type=ret)
        return self._memo[key]

    def create_bound_method(self, receiver: TypeDescriptor, func: FunctionMetadata) -> BoundMethodMetadata:
        key = self._get_intern_key("BoundMethod", "", None, r=id(receiver), f=id(func))
        if key not in self._memo:
            self._memo[key] = BoundMethodMetadata(receiver_type=receiver, function_type=func)
        return self._memo[key]

    def create_class(self, name: str, module: Optional[str] = None, parent: Optional[str] = None, is_nullable: bool = True) -> ClassMetadata:
        key = self._get_intern_key("Class", name, module, p=parent, n=is_nullable)
        if key not in self._memo:
            self._memo[key] = ClassMetadata(name=name, module_path=module, parent_name=parent, is_nullable=is_nullable)
        return self._memo[key]

class MetadataRegistry:
    """
    UTS 元数据注册表。
    不再使用类级别单例，改为实例管理以支持多引擎隔离。
    """
    def __init__(self, axiom_registry: Optional['AxiomRegistry'] = None):
        self._descriptors: Dict[str, TypeDescriptor] = {}
        self.factory = TypeFactory() 
        self._axiom_registry = axiom_registry

    def register(self, descriptor: TypeDescriptor):
        key = f"{descriptor.module_path}.{descriptor.name}" if descriptor.module_path else descriptor.name
        core_trace(CoreModule.UTS, DebugLevel.BASIC, f"Registering UTS descriptor: {key}")
        self._descriptors[key] = descriptor
        
        # [Isolation] 将注册表上下文绑定到描述符上
        descriptor._registry = self
        
        # [IoC] 如果存在公理注册表，尝试注入公理
        if self._axiom_registry:
            axiom_name = descriptor.name
            if isinstance(descriptor, ListMetadata):
                axiom_name = "list"
            elif isinstance(descriptor, DictMetadata):
                axiom_name = "dict"
            
            descriptor._axiom = self._axiom_registry.get_axiom(axiom_name)
            
            # [Axiom-Driven Schema] 从公理中注入方法签名
            if descriptor._axiom:
                try:
                    method_descs = descriptor._axiom.get_methods()
                    if method_descs:
                        for m_name, m_desc in method_descs.items():
                            # [Hydration] 确保从公理注入的方法元数据使用当前注册表的类型标识
                            hydrated_m_desc = self._hydrate_metadata(m_desc)
                            
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

    def _hydrate_metadata(self, desc: TypeDescriptor) -> TypeDescriptor:
        """递归确保描述符及其引用的所有类型都来自当前注册表实例"""
        if desc._registry is self: return desc
        
        # 如果是原子类型，尝试在当前注册表中查找
        if desc.__class__ is TypeDescriptor:
            resolved = self.resolve(desc.name, desc.module_path)
            if resolved: return resolved
            # 如果没找到，至少把 registry 绑上
            desc._registry = self
            return desc
            
        # 如果是复合类型，递归处理其成员
        if isinstance(desc, FunctionMetadata):
            desc.param_types = [self._hydrate_metadata(p) for p in desc.param_types]
            if desc.return_type:
                desc.return_type = self._hydrate_metadata(desc.return_type)
        elif isinstance(desc, ListMetadata):
            if desc.element_type:
                desc.element_type = self._hydrate_metadata(desc.element_type)
        elif isinstance(desc, DictMetadata):
            if desc.key_type:
                desc.key_type = self._hydrate_metadata(desc.key_type)
            if desc.value_type:
                desc.value_type = self._hydrate_metadata(desc.value_type)
        
        desc._registry = self
        return desc

    def resolve(self, name: str, module_path: Optional[str] = None) -> Optional[TypeDescriptor]:
        key = f"{module_path}.{name}" if module_path else name
        return self._descriptors.get(key)
        
    def get_axiom_registry(self) -> Optional['AxiomRegistry']:
        return self._axiom_registry

    @property
    def all_descriptors(self) -> Dict[str, TypeDescriptor]:
        """获取所有已注册的描述符快照"""
        return dict(self._descriptors)
