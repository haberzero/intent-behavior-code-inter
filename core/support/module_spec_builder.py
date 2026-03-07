from typing import List, Dict, Any, Optional, Union, Callable
from core.foundation.types import (
    TypeDescriptor, INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
    BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR,
    ClassMetadata, FunctionMetadata, ModuleMetadata
)

class ClassSpecBuilder:
    """用于构建类元数据的子构建器"""
    def __init__(self, name: str, parent: Optional[ClassMetadata] = None):
        self.metadata = ClassMetadata(name=name)
        if parent:
            self.metadata.parent_name = parent.name
            self.metadata.parent_module = parent.module_path
        self._type_resolver: Optional[Callable[[Union[str, TypeDescriptor]], TypeDescriptor]] = None

    def field(self, name: str, type: Union[str, TypeDescriptor] = "any") -> 'ClassSpecBuilder':
        t = self._type_resolver(type)
        self.metadata.members[name] = t
        return self

    def method(self, name: str, params: List[Union[str, TypeDescriptor]] = None, returns: Union[str, TypeDescriptor] = "void") -> 'ClassSpecBuilder':
        # [NEW] 自动向类方法签名首位注入实例类型 (self)
        param_types = [self.metadata] + [self._type_resolver(p) for p in (params or [])]
        return_type = self._type_resolver(returns)
        self.metadata.members[name] = FunctionMetadata(name=name, param_types=param_types, return_type=return_type)
        return self

class SpecBuilder:
    """
    IBC-Inter 模块声明构建器。
    用于以简洁的方式定义模块的静态接口（元数据）。
    """
    def __init__(self, name: str):
        self.name = name
        self.exports: Dict[str, TypeDescriptor] = {}
        self._type_map = {
            "int": INT_DESCRIPTOR,
            "float": FLOAT_DESCRIPTOR,
            "str": STR_DESCRIPTOR,
            "bool": BOOL_DESCRIPTOR,
            "void": VOID_DESCRIPTOR,
            "any": ANY_DESCRIPTOR,
            "var": ANY_DESCRIPTOR
        }
        self._current_class_builder: Optional[ClassSpecBuilder] = None

    def _resolve_type(self, t: Union[str, TypeDescriptor]) -> TypeDescriptor:
        if isinstance(t, TypeDescriptor):
            return t
        
        name = t.lower()
        if name in self._type_map:
            return self._type_map[name]
        
        # 尝试在已导出的符号中查找
        if t in self.exports:
            return self.exports[t]
            
        return ANY_DESCRIPTOR

    def func(self, name: str, params: List[Union[str, TypeDescriptor]] = None, returns: Union[str, TypeDescriptor] = "void") -> 'SpecBuilder':
        """声明一个全局函数"""
        param_types = [self._resolve_type(p) for p in (params or [])]
        return_type = self._resolve_type(returns)
        
        self.exports[name] = FunctionMetadata(name=name, param_types=param_types, return_type=return_type)
        return self

    def var(self, name: str, type: Union[str, TypeDescriptor] = "any") -> 'SpecBuilder':
        """声明一个全局变量"""
        self.exports[name] = self._resolve_type(type)
        return self

    def cls(self, name: str, parent: Union[str, ClassMetadata] = None) -> 'SpecBuilder':
        """开始声明一个类"""
        parent_metadata = None
        if parent:
            if isinstance(parent, ClassMetadata):
                parent_metadata = parent
            else:
                p = self._resolve_type(parent)
                if isinstance(p, ClassMetadata):
                    parent_metadata = p
        
        self._current_class_builder = ClassSpecBuilder(name, parent_metadata)
        self._current_class_builder._type_resolver = self._resolve_type
        
        # 将类本身注册到导出和类型图中，以便后续引用
        self.exports[name] = self._current_class_builder.metadata
        self._type_map[name.lower()] = self._current_class_builder.metadata
        return self

    def field(self, name: str, type: Union[str, TypeDescriptor] = "any") -> 'SpecBuilder':
        """为当前类声明字段"""
        if self._current_class_builder:
            self._current_class_builder.field(name, type)
        return self

    def method(self, name: str, params: List[Union[str, TypeDescriptor]] = None, returns: Union[str, TypeDescriptor] = "void") -> 'SpecBuilder':
        """为当前类声明方法"""
        if self._current_class_builder:
            self._current_class_builder.method(name, params, returns)
        return self

    def build(self) -> ModuleMetadata:
        """构建并返回 ModuleMetadata"""
        return ModuleMetadata(name=self.name, exports=self.exports)
