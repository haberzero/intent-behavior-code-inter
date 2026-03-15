from typing import Optional, Any, Dict, List, Union, TYPE_CHECKING
import sys
from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel, core_trace
from core.foundation.enums import RegistrationState

from .descriptors import (
    TypeDescriptor, ListMetadata, DictMetadata, FunctionMetadata, 
    ClassMetadata, BoundMethodMetadata
)
from .hydrator import TypeHydrator

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
        self._hydrator = TypeHydrator(self)

    def register(self, descriptor: TypeDescriptor):
        key = f"{descriptor.module_path}.{descriptor.name}" if descriptor.module_path else descriptor.name
        core_trace(CoreModule.UTS, DebugLevel.BASIC, f"Registering UTS descriptor: {key}")
        
        # [Isolation] 将注册表上下文绑定到描述符上
        descriptor._registry = self
        
        # [IES 2.0 Hydration] 采用两阶段注册模式
        # 第一阶段：占位 (Shelling)
        self._descriptors[key] = descriptor
        
        # 第二阶段：填充 (Filling) - 如果描述符包含成员，进行深度水合
        if descriptor.members:
            self._hydrator.deep_hydrate(descriptor)
        
        # [IoC] 从公理注册表中获取并注入公理能力
        self._hydrator.inject_axioms(descriptor)

    def _deep_hydrate(self, desc: TypeDescriptor):
        """深度水合描述符的成员列表，确保每个成员都被正确包装为 Symbol 对象"""
        return self._hydrator.deep_hydrate(desc)

    def _hydrate_metadata(self, desc: Union[TypeDescriptor, str]) -> TypeDescriptor:
        """递归确保描述符及其引用的所有类型都来自当前注册表实例"""
        return self._hydrator.hydrate_metadata(desc)

    def resolve(self, name: str, module_path: Optional[str] = None) -> Optional[TypeDescriptor]:
        key = f"{module_path}.{name}" if module_path else name
        return self._descriptors.get(key)
        
    def get_axiom_registry(self) -> Optional['AxiomRegistry']:
        return self._axiom_registry

    @property
    def all_descriptors(self) -> Dict[str, TypeDescriptor]:
        """获取所有已注册的描述符快照"""
        return dict(self._descriptors)
