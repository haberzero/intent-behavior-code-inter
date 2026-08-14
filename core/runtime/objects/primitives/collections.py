from typing import Any, Dict, List, Optional
from ..kernel import IbObject, IbValue, IbClass
from ..kernel.base import unbox
from core.kernel.issue import InterpreterError
from ..ib_type_mapping import register_ib_type


def _element_spec_for(container: 'IbValue') -> Any:
    """解析容器值声明的元素类型 spec（统一 Optional 值模型用）。

    容器值绑定特化类（``list[Optional[int]]``）时，``ib_class.spec`` 携带
    元素类型 TypeRef（list/tuple → ``element_type``；dict → ``value_type``）；
    经 metadata registry 解析为 IbSpec。裸容器（``list``）spec 无元素类型
    → None。

    按 kind 分派：DICT 的 ``element_type`` 恒为 ``TypeRef("any")``（非 None
    非 Optional，遮蔽 ``value_type``），故 dict 必须优先 ``value_type``；
    list/tuple 读 ``element_type``。
    """
    from core.kernel.spec.base import TypeKind

    spec = getattr(container.ib_class, "spec", None)
    if spec is None:
        return None
    spec_reg = getattr(container.ib_class.registry, "get_metadata_registry", lambda: None)()
    if spec_reg is None:
        return None
    if getattr(spec, "kind", None) == TypeKind.DICT.value:
        ref = getattr(spec, "value_type", None)
    else:
        ref = getattr(spec, "element_type", None)
    if ref is None:
        return None
    return spec_reg.resolve_typeref(ref)


def _wrap_element_value(container: 'IbValue', value: Any) -> Any:
    """按容器元素声明类型包装 Optional 值（统一 Optional 值模型）。

    ``list[Optional[int]]`` 等容器写入元素（``__setitem__``/``append``/
    ``insert``/``update``）时，元素声明为 Optional 则按元素类型包装
    （空值 → ``IbOptional(is_some=False)``），与容器字面量/局部变量路径一致。
    非 Optional 元素类型原样返回。
    """
    elem_spec = _element_spec_for(container)
    if elem_spec is None:
        return value
    from core.runtime.objects.primitives.optional import wrap_optional

    return wrap_optional(value, elem_spec, container.ib_class.registry)

@register_ib_type("list")
class IbList(IbValue):
    """
    包装 Python 原生 list 的 IBC 对象。
    ``elements`` 是 ``payload`` 的具名视图；通过 property 保持两者自动同步。
    """
    __slots__ = ()

    def __init__(self, elements: List[IbObject], ib_class: IbClass):
        super().__init__(ib_class, payload=elements)

    @property
    def elements(self):
        return self.payload

    @elements.setter
    def elements(self, val):
        self.payload = val

    def to_native(self, memo=None) -> List[Any]:
        if memo is None: memo = {}
        if id(self) in memo: return memo[id(self)]
        
        res = []
        memo[id(self)] = res
        for e in self.elements:
            res.append(e.to_native(memo) if isinstance(e, IbObject) else e)
        return res

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {
            "type": self.ib_class.name, 
            "value": [e.serialize_for_debug() for e in self.elements]
        }

    def __repr__(self):
        return f"List({self.elements})"

    def pop(self) -> IbObject:
        if not self.elements:
            raise InterpreterError("IndexError: pop from empty list")
        return self.elements.pop()

    def clear(self) -> IbObject:
        self.elements.clear()
        return self.ib_class.registry.get_none()

    def append(self, item: IbObject) -> IbObject:
        self.elements.append(_wrap_element_value(self, item))
        return self.ib_class.registry.get_none()

    def len(self) -> IbObject:
        return self.ib_class.registry.box(len(self.elements))

    def cast_to(self, target_class: Any) -> IbObject:
        """ 支持 List 的强转逻辑"""
        if target_class.name in ("list", "any"):
            return self
        if target_class.name == "str":
            # 转换为字符串表示
            items_repr = [str(e.to_native()) for e in self.elements]
            return self.ib_class.registry.box("[" + ", ".join(items_repr) + "]")
        return self

    def __getitem__(self, key: Any) -> IbObject:
        idx = unbox(key)
        try:
            res = self.elements[idx]
            if isinstance(idx, slice):
                # 切片返回 IbObject 列表，重新装箱为 IbList——沿用自身 ib_class
                # （特化类 list[int] 保留特化身份；裸 list 保持裸），使
                # ``type(li[0:2]) == type(li)``（缺陷二根治：切片值层身份保真）。
                return IbList(list(res), self.ib_class)
            return res
        except IndexError:
            raise InterpreterError(f"IndexError: list index out of range: {idx}")

    def __setitem__(self, key: Any, val: IbObject) -> None:
        idx = unbox(key)
        self.elements[idx] = _wrap_element_value(self, val)

    def sort(self) -> IbObject:
        self.elements.sort(key=lambda x: x.to_native())
        return self.ib_class.registry.get_none()

    def reverse(self) -> IbObject:
        """原地反转列表。对齐 Python list.reverse()"""
        self.elements.reverse()
        return self.ib_class.registry.get_none()

    def insert(self, index: Any, item: IbObject) -> IbObject:
        """在指定位置插入元素。对齐 Python list.insert(index, item)"""
        idx = index.to_native() if isinstance(index, IbObject) else int(index)
        self.elements.insert(idx, _wrap_element_value(self, item))
        return self.ib_class.registry.get_none()

    def remove(self, item: Any) -> IbObject:
        """删除第一个匹配元素。对齐 Python list.remove(item)"""
        native = unbox(item)
        for i, el in enumerate(self.elements):
            if el.to_native() == native:
                del self.elements[i]
                return self.ib_class.registry.get_none()
        raise InterpreterError(f"ValueError: list.remove(x): x not in list")

    def index(self, item: Any) -> IbObject:
        """返回第一个匹配元素的索引。对齐 Python list.index(item)"""
        native = unbox(item)
        for i, el in enumerate(self.elements):
            if el.to_native() == native:
                return self.ib_class.registry.box(i)
        raise InterpreterError(f"ValueError: {native!r} is not in list")

    def count(self, item: Any) -> IbObject:
        """统计元素出现次数。对齐 Python list.count(item)"""
        native = unbox(item)
        cnt = sum(1 for el in self.elements if el.to_native() == native)
        return self.ib_class.registry.box(cnt)

    def contains(self, item: Any) -> IbObject:
        """检查是否包含元素（便捷方法，等价于 item in list）"""
        native = unbox(item)
        return self.ib_class.registry.box(any(el.to_native() == native for el in self.elements))

    def __contains__(self, item: Any) -> bool:
        """Python-level containment check used by the 'in' operator at runtime"""
        native = item.to_native() if isinstance(item, IbObject) else item
        return any(el.to_native() == native for el in self.elements)

    def __add__(self, other: IbObject) -> Any:
        """列表拼接。对齐 Python list + list"""
        if not isinstance(other, IbList):
            raise InterpreterError(f"TypeError: can only concatenate list (not '{other.ib_class.name}') to list")
        # 沿用自身 ib_class（特化类 list[int] 保留特化身份），使
        # ``list[int] a += [2]`` 结果仍为 list[int]（缺陷二根治：复合赋值
        # 值层身份保真；与切片 __getitem__ slice 分支同构）。
        # 元素统一按自身元素类型包装（list[Optional[int]] 拼接含 None 的
        # 列表时，产物元素保持 IbOptional 表示——统一 Optional 值模型）。
        return IbList(
            [_wrap_element_value(self, e) for e in list(self.elements) + list(other.elements)],
            self.ib_class,
        )

    def __mul__(self, other: IbObject) -> Any:
        """列表重复: list * int"""
        n = unbox(other)
        if not isinstance(n, int):
            raise InterpreterError(f"TypeError: can't multiply sequence by non-int of type '{other.ib_class.name}'")
        return IbList(
            [_wrap_element_value(self, e) for e in list(self.elements) * n],
            self.ib_class,
        )

@register_ib_type("tuple")
class IbTuple(IbValue):
    """
    包装 Python 原生 tuple 的 IBC 对象。
    与 IbList 的关键区别：不可变（没有 append/pop/sort/clear/__setitem__）。
    ``elements`` 是 ``payload`` 的具名视图；通过 property 保持两者自动同步。
    """
    __slots__ = ()

    def __init__(self, elements: tuple, ib_class: IbClass):
        super().__init__(ib_class, payload=elements)

    @property
    def elements(self):
        return self.payload

    @elements.setter
    def elements(self, val):
        self.payload = val

    def to_native(self, memo=None) -> tuple:
        if memo is None: memo = {}
        if id(self) in memo: return memo[id(self)]

        res_list = []
        memo[id(self)] = tuple(res_list)  # placeholder
        for e in self.elements:
            res_list.append(e.to_native(memo) if isinstance(e, IbObject) else e)
        result = tuple(res_list)
        memo[id(self)] = result
        return result

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {
            "type": self.ib_class.name,
            "value": [e.serialize_for_debug() for e in self.elements]
        }

    def __repr__(self):
        return f"Tuple({self.elements})"

    def len(self) -> IbObject:
        return self.ib_class.registry.box(len(self.elements))

    def cast_to(self, target_class: Any) -> IbObject:
        """支持 Tuple 的强转逻辑"""
        if target_class.name in ("tuple", "any"):
            return self
        if target_class.name == "list":
            return self.ib_class.registry.box(list(self.elements))
        if target_class.name == "str":
            items_repr = [str(e.to_native()) for e in self.elements]
            return self.ib_class.registry.box("(" + ", ".join(items_repr) + ")")
        return self

    def __getitem__(self, key: Any) -> IbObject:
        idx = unbox(key)
        try:
            res = self.elements[idx]
            if isinstance(idx, slice):
                # 切片返回 IbObject 元组，重新装箱为 IbTuple——沿用自身 ib_class
                # （特化类 tuple[int,str] 保留特化身份），使
                # ``type(t[0:2]) == type(t)``（缺陷二根治：切片值层身份保真）。
                native = tuple(res) if isinstance(res, (list, tuple)) else res
                return IbTuple(native, self.ib_class)
            return res
        except IndexError:
            raise InterpreterError(f"IndexError: tuple index out of range: {idx}")

@register_ib_type("dict")
class IbDict(IbValue):
    """
    包装 Python 原生 dict 的 IBC 对象。

    约定: ``payload`` 与 ``fields`` 指向同一个底层映射。
    ``fields`` 保持对象系统现有的消息/属性访问兼容面，``payload`` 则让
    该值同时满足统一 ``IbValue`` 承载层的结构约定。
    """
    def __init__(self, fields: Dict[str, IbObject], ib_class: IbClass):
        super().__init__(ib_class, payload=fields, fields=fields)

    def to_native(self, memo=None) -> Dict[str, Any]:
        if memo is None: memo = {}
        if id(self) in memo: return memo[id(self)]
        
        res = {}
        memo[id(self)] = res
        for k, v in self.fields.items():
            res[k] = v.to_native(memo) if isinstance(v, IbObject) else v
        return res

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {
            "type": self.ib_class.name,
            "value": {k: v.serialize_for_debug() if isinstance(v, IbObject) else v for k, v in self.fields.items()}
        }

    def __repr__(self):
        return f"Dict({self.fields})"

    def keys(self) -> IbObject:
        # key 已经是原生类型（通常是 str），需要装箱
        native_keys = list(self.fields.keys())
        return self.ib_class.registry.box(native_keys)

    def values(self) -> IbObject:
        return self.ib_class.registry.box(list(self.fields.values()))

    def items(self) -> IbObject:
        """返回 [(key, value), ...] 形式的列表。对齐 Python dict.items()"""
        pairs = [[k, v] for k, v in self.fields.items()]
        return self.ib_class.registry.box(pairs)

    def update(self, other: Any) -> IbObject:
        """将另一个字典合并到当前字典。对齐 Python dict.update(other)"""
        if isinstance(other, IbDict):
            self.fields.update({
                k: _wrap_element_value(self, v) for k, v in other.fields.items()
            })
        elif isinstance(other, IbObject):
            src = other.to_native()
            if isinstance(src, dict):
                for k, v in src.items():
                    self.fields[k] = _wrap_element_value(
                        self, self.ib_class.registry.box(v)
                    )
        return self.ib_class.registry.get_none()

    def len(self) -> IbObject:
        return self.ib_class.registry.box(len(self.fields))

    def cast_to(self, target_class: Any) -> IbObject:
        """ 支持 Dict 的强转逻辑"""
        if target_class.name in ("dict", "any"):
            return self
        if target_class.name == "str":
            items_repr = [f"{k}: {str(v.to_native())}" for k, v in self.fields.items()]
            return self.ib_class.registry.box("{" + ", ".join(items_repr) + "}")
        return self

    def __getitem__(self, key: Any) -> IbObject:
        k = unbox(key)
        try:
            return self.fields[k]
        except KeyError:
            raise InterpreterError(f"KeyError: '{k}'")

    def __setitem__(self, key: Any, val: IbObject) -> None:
        k = unbox(key)
        self.fields[k] = _wrap_element_value(self, val)

    def get(self, key: Any, default: Optional[IbObject] = None) -> IbObject:
        k = unbox(key)
        if k in self.fields:
            return self.fields[k]
        return default or self.ib_class.registry.get_none()

    def pop(self, key: Any, default: Optional[IbObject] = None) -> IbObject:
        """删除并返回指定 key 的值。对齐 Python dict.pop(key[, default])"""
        k = unbox(key)
        if k in self.fields:
            return self.fields.pop(k)
        if default is not None:
            return default
        raise InterpreterError(f"KeyError: '{k}'")

    def contains(self, key: Any) -> IbObject:
        """检查 key 是否存在于字典中（便捷方法，等价于 key in dict）"""
        k = unbox(key)
        return self.ib_class.registry.box(k in self.fields)

    def remove(self, key: Any) -> IbObject:
        """移除指定 key 的键值对，key 不存在时抛出错误"""
        k = unbox(key)
        if k not in self.fields:
            raise InterpreterError(f"KeyError: '{k}'")
        del self.fields[k]
        return self.ib_class.registry.get_none()

    def __iter__(self):
        return iter(self.fields)

    def __contains__(self, key):
        # 支持 IbString 或原生 string key
        native_key = key.to_native() if isinstance(key, IbObject) else key
        return native_key in self.fields

