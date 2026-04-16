from typing import List, Optional, Union

from core.kernel.spec import (
    IbSpec, ModuleSpec, ClassSpec, FuncSpec,
    MethodMemberSpec, MemberSpec,
    INT_SPEC, FLOAT_SPEC, STR_SPEC, BOOL_SPEC,
    VOID_SPEC, ANY_SPEC, LIST_SPEC, DICT_SPEC,
)


class ClassSpecBuilder:
    """用于构建类元数据的子构建器"""
    def __init__(self, name: str, parent: Optional[str] = None):
        self.spec = ClassSpec(name=name, parent_name=parent, is_user_defined=False)

    def field(self, name: str, type: Union[str, IbSpec] = "any") -> 'ClassSpecBuilder':
        type_name = type if isinstance(type, str) else type.name
        self.spec.members[name] = MemberSpec(name=name, kind="field", type_name=type_name)
        return self

    def method(self, name: str, params: Optional[List[Union[str, IbSpec]]] = None, returns: Union[str, IbSpec] = "void") -> 'ClassSpecBuilder':
        param_names = [p if isinstance(p, str) else p.name for p in (params or [])]
        ret_name = returns if isinstance(returns, str) else returns.name
        self.spec.members[name] = MethodMemberSpec(
            name=name,
            kind="method",
            param_type_names=param_names,
            param_type_modules=[None] * len(param_names),
            return_type_name=ret_name,
        )
        return self


class SpecBuilder:
    """
    IBC-Inter 模块声明构建器。
    用于以简洁的方式定义模块的静态接口（元数据）。
    """
    _TYPE_MAP: dict = {
        "int": "int",
        "float": "float",
        "str": "str",
        "bool": "bool",
        "void": "void",
        "any": "any",
        "auto": "any",
        "dict": "dict",
        "list": "list",
    }

    def __init__(self, name: str):
        self.name = name
        self._spec = ModuleSpec(name=name, is_user_defined=False)
        self._current_class_builder: Optional[ClassSpecBuilder] = None

    def _resolve_type_name(self, t: Union[str, IbSpec]) -> str:
        if isinstance(t, IbSpec):
            return t.name
        name = t.lower()
        return self._TYPE_MAP.get(name, t)

    def func(self, name: str, params: Optional[List[Union[str, IbSpec]]] = None, returns: Union[str, IbSpec] = "void") -> 'SpecBuilder':
        """声明一个全局函数"""
        param_names = [self._resolve_type_name(p) for p in (params or [])]
        ret_name = self._resolve_type_name(returns)
        self._spec.members[name] = MethodMemberSpec(
            name=name,
            kind="method",
            param_type_names=param_names,
            param_type_modules=[None] * len(param_names),
            return_type_name=ret_name,
        )
        return self

    def auto(self, name: str, type: Union[str, IbSpec] = "any") -> 'SpecBuilder':
        """声明一个全局变量"""
        type_name = self._resolve_type_name(type)
        self._spec.members[name] = MemberSpec(name=name, kind="field", type_name=type_name)
        return self

    def cls(self, name: str, parent: Union[str, None] = None) -> 'SpecBuilder':
        """开始声明一个类"""
        parent_name = parent if isinstance(parent, str) else (parent.name if parent else None)
        self._current_class_builder = ClassSpecBuilder(name, parent_name)
        self._spec.members[name] = MemberSpec(
            name=name, kind="field",
            type_name=name,
        )
        return self

    def field(self, name: str, type: Union[str, IbSpec] = "any") -> 'SpecBuilder':
        """为当前类声明字段"""
        if self._current_class_builder:
            self._current_class_builder.field(name, type)
        return self

    def method(self, name: str, params: Optional[List[Union[str, IbSpec]]] = None, returns: Union[str, IbSpec] = "void") -> 'SpecBuilder':
        """为当前类声明方法"""
        if self._current_class_builder:
            self._current_class_builder.method(name, params, returns)
        return self

    def build(self) -> ModuleSpec:
        """构建并返回 ModuleSpec"""
        return self._spec
