from typing import Optional, Any, Dict, List, Union, TYPE_CHECKING
import sys
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_trace

from .descriptors import (
    TypeDescriptor, ListMetadata, DictMetadata, FunctionMetadata,
    ClassMetadata, BoundMethodMetadata, ModuleMetadata
)
from .axiom_hydrator import AxiomHydrator

if TYPE_CHECKING:
    from core.kernel.axioms.protocols import TypeAxiom
    from core.kernel.axioms.registry import AxiomRegistry

class TypeFactory:
    """
    描述符驻留工厂。
    基于结构哈希确保同构描述符在内存中仅存一份。
    """
    def __init__(self):
        self._memo: Dict[str, TypeDescriptor] = {}

    def _get_intern_key(self, kind: str, name: str, module: Optional[str], **kwargs) -> str:
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
            desc = ClassMetadata(name=name, module_path=module, parent_name=parent, is_nullable=is_nullable)
            desc.is_user_defined = True
            self._memo[key] = desc
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
        self._hydrator = AxiomHydrator(self)

    def register(self, descriptor: TypeDescriptor) -> TypeDescriptor:
        key = f"{descriptor.module_path}.{descriptor.name}" if descriptor.module_path else descriptor.name
        core_trace(CoreModule.UTS, DebugLevel.BASIC, f"Registering UTS descriptor: {key}")

        # [IES 2.0 Isolation] 强制克隆描述符以确保引擎间物理隔离 (Item 12)
        memo = {}
        descriptor = self._clone_and_bind(descriptor, memo)

        # [IES 2.0 Hydration] 采用两阶段注册模式
        # 第一阶段：占位 (Shelling)
        self._descriptors[key] = descriptor

        # 第二阶段：填充与能力注入 (Filling & Axiom Injection)
        # 注意：必须为克隆出的所有描述符注入能力，否则嵌套类型将丢失公理逻辑
        for desc in memo.values():
            if isinstance(desc, TypeDescriptor):
                if desc.members:
                    self._hydrator.deep_hydrate(desc)
                self._hydrator.inject_axioms(desc)

        return descriptor

    def _clone_and_bind(self, descriptor: TypeDescriptor, memo: Dict[int, Any]) -> TypeDescriptor:
        """克隆描述符并将其自身及其子类型递归绑定到当前注册表"""
        new_desc = descriptor.clone(memo)

        # 递归绑定所有克隆出来的描述符
        for desc in memo.values():
            if isinstance(desc, TypeDescriptor):
                desc._registry = self

        return new_desc

    def _deep_hydrate(self, desc: TypeDescriptor):
        """深度水合描述符的成员列表，确保每个成员都被正确包装为 Symbol 对象"""
        return self._hydrator.deep_hydrate(desc)

    def _hydrate_metadata(self, desc: Union[TypeDescriptor, str]) -> TypeDescriptor:
        """递归确保描述符及其引用的所有类型都来自当前注册表实例"""
        return self._hydrator.hydrate_metadata(desc)

    def resolve(self, name: str, module_path: Optional[str] = None) -> Optional[TypeDescriptor]:
        key = f"{module_path}.{name}" if module_path else name
        return self._descriptors.get(key)

    def resolve_from_value(self, value: Any) -> Optional[TypeDescriptor]:
        """[IES 2.1] 根据 Python 原生值解析对应的 UTS 描述符"""
        if isinstance(value, bool): return self.resolve("bool")
        if isinstance(value, int): return self.resolve("int")
        if isinstance(value, float): return self.resolve("float")
        if isinstance(value, str): return self.resolve("str")
        if value is None: return self.resolve("void")
        return None

    def get_all_modules(self) -> Dict[str, ModuleMetadata]:
        """获取所有已注册的模块元数据"""
        return {name: d for name, d in self._descriptors.items() if d.is_module()}

    def get_all_functions(self) -> Dict[str, FunctionMetadata]:
        """获取所有已注册的全局函数元数据"""
        return {name: d for name, d in self._descriptors.items() if d.get_call_trait() and not d.is_class()}

    def get_all_classes(self) -> Dict[str, ClassMetadata]:
        """获取所有已注册的类元数据"""
        return {name: d for name, d in self._descriptors.items() if d.is_class()}

    def get_axiom_registry(self) -> Optional['AxiomRegistry']:
        return self._axiom_registry

    def clone(self) -> 'MetadataRegistry':
        """
        [P1-F] 创建 MetadataRegistry 的深克隆。
        每个隔离引擎实例拥有独立的类型元数据注册表。
        """
        new_registry = MetadataRegistry(axiom_registry=self._axiom_registry)

        memo: Dict[int, Any] = {}
        for key, descriptor in self._descriptors.items():
            cloned_desc = descriptor.clone(memo)
            new_registry._descriptors[key] = cloned_desc

        # [IES 2.2 Fix] 重新水合克隆出的所有描述符，绑定新的注册表并注入公理能力
        # 否则子环境中的描述符将丢失 _registry 和 _axiom 引用，导致运算符解析失败
        for desc in memo.values():
            if isinstance(desc, TypeDescriptor):
                # 显式绑定到新的注册表
                desc._registry = new_registry
                
                # 重新填充成员 (Symbols)
                if desc.members:
                    new_registry._deep_hydrate(desc)
                
                # 重新注入公理能力 (Operators, Callables, etc.)
                new_registry._hydrator.inject_axioms(desc)

        return new_registry

    def to_dict(self) -> Dict[str, Any]:
        """
        [IES 2.2] 将 MetadataRegistry 序列化为字典，用于 .ibc_meta 文件生成。
        实现构建时元数据快照，使编译器能在编译前获取插件类型签名。
        """
        result = {
            "version": "1.0",
            "modules": {},
            "classes": {},
            "functions": {},
        }

        for key, desc in self._descriptors.items():
            if desc.is_module():
                result["modules"][key] = self._serialize_descriptor(desc)
            elif desc.is_class():
                result["classes"][key] = self._serialize_descriptor(desc)
            elif desc.get_call_trait():
                result["functions"][key] = self._serialize_descriptor(desc)

        return result

    def _serialize_descriptor(self, desc: TypeDescriptor) -> Dict[str, Any]:
        """将 TypeDescriptor 序列化为字典"""
        result = {
            "name": desc.name,
            "kind": desc.kind if hasattr(desc, 'kind') else type(desc).__name__,
            "module_path": desc.module_path if hasattr(desc, 'module_path') else None,
            "is_nullable": desc.is_nullable if hasattr(desc, 'is_nullable') else False,
            "is_user_defined": desc.is_user_defined if hasattr(desc, 'is_user_defined') else False,
        }

        if hasattr(desc, 'members') and desc.members:
            result["members"] = {
                name: self._serialize_symbol(member)
                for name, member in desc.members.items()
            }

        if hasattr(desc, 'element_type') and desc.element_type:
            result["element_type"] = desc.element_type.name if hasattr(desc.element_type, 'name') else str(desc.element_type)

        if hasattr(desc, 'key_type') and desc.key_type:
            result["key_type"] = desc.key_type.name if hasattr(desc.key_type, 'name') else str(desc.key_type)

        if hasattr(desc, 'value_type') and desc.value_type:
            result["value_type"] = desc.value_type.name if hasattr(desc.value_type, 'name') else str(desc.value_type)

        if hasattr(desc, 'param_types') and desc.param_types:
            result["param_types"] = [
                p.name if hasattr(p, 'name') else str(p)
                for p in desc.param_types
            ]

        if hasattr(desc, 'return_type') and desc.return_type:
            result["return_type"] = desc.return_type.name if hasattr(desc.return_type, 'name') else str(desc.return_type)

        return result

    def _serialize_symbol(self, symbol: Any) -> Dict[str, Any]:
        """将符号对象序列化为字典"""
        if hasattr(symbol, 'name'):
            return {"name": symbol.name, "type": type(symbol).__name__}
        return {"type": type(symbol).__name__}

    @property
    def all_descriptors(self) -> Dict[str, TypeDescriptor]:
        """获取所有已注册的描述符快照"""
        return dict(self._descriptors)
