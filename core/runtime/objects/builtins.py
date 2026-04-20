from typing import Any, List, Dict, Optional, Callable, Union
from .kernel import IbObject, IbClass, IbNativeFunction, IbNone
from core.kernel.registry import KernelRegistry
from core.runtime.support.converters import _cast_numeric_to_native, _cast_string_to_native
from core.kernel.issue import InterpreterError

from .ib_type_mapping import register_ib_type

@register_ib_type("int")
class IbInteger(IbObject):
    """
    包装 Python 原生 int 的 IBC 对象。
    实现小整数驻留 (Interning) 以优化性能。
    现在驻留缓存已移动到 Registry 实例中，实现引擎隔离。
    """
    __slots__ = ('value',)
    
    def __init__(self, value: int, ib_class: IbClass):
        super().__init__(ib_class)
        self.value = value

    @classmethod
    def from_native(cls, value: int, ib_class: IbClass) -> 'IbInteger':
        """小整数驻留工厂方法"""
        cache = ib_class.registry.get_int_cache()
        
        if -5 <= value <= 256:
            if value not in cache:
                cache[value] = cls(value, ib_class=ib_class)
            return cache[value]
        return cls(value, ib_class=ib_class)

    def to_native(self, memo=None) -> int:
        return self.value

    def to_bool(self) -> IbObject:
        return self.ib_class.registry.box(1 if self.value != 0 else 0)

    def to_list(self) -> IbObject:
        return self.ib_class.registry.box(list(range(self.value)))

    def cast_to(self, target_class: Any) -> IbObject:
        target_desc = target_class.spec if hasattr(target_class, 'spec') else None
        res_val = _cast_numeric_to_native(self.value, target_desc)
        return self.ib_class.registry.box(res_val)

    def serialize_for_debug(self) -> Dict[str, Any]:
        # 强制从 ib_class.name 获取类型标签，消除硬编码
        return {"type": self.ib_class.name, "value": self.value}

    def __repr__(self):
        return f"Integer({self.value})"

    # ---  自动化运算符绑定支持 ---
    def __add__(self, other: IbObject) -> Any: return self.value + other.to_native()
    def __sub__(self, other: IbObject) -> Any: return self.value - other.to_native()
    def __mul__(self, other: IbObject) -> Any: return self.value * other.to_native()
    def __truediv__(self, other: IbObject) -> Any: 
        b = other.to_native()
        return self.value // b if isinstance(b, int) else self.value / b
    def __floordiv__(self, other: IbObject) -> Any: return self.value // other.to_native()
    def __mod__(self, other: IbObject) -> Any: return self.value % other.to_native()
    def __pow__(self, other: IbObject) -> Any: return self.value ** other.to_native()
    def __and__(self, other: IbObject) -> Any: return self.value & other.to_native()
    def __or__(self, other: IbObject) -> Any: return self.value | other.to_native()
    def __xor__(self, other: IbObject) -> Any: return self.value ^ other.to_native()
    def __lshift__(self, other: IbObject) -> Any: return self.value << other.to_native()
    def __rshift__(self, other: IbObject) -> Any: return self.value >> other.to_native()
    def __invert__(self) -> Any: return ~self.value
    def __neg__(self) -> Any: return -self.value
    def __pos__(self) -> Any: return +self.value

    def __lt__(self, other: IbObject) -> bool: return self.value < other.to_native()
    def __le__(self, other: IbObject) -> bool: return self.value <= other.to_native()
    def __gt__(self, other: IbObject) -> bool: return self.value > other.to_native()
    def __ge__(self, other: IbObject) -> bool: return self.value >= other.to_native()
    
    def __eq__(self, other):
        if isinstance(other, IbInteger):
            return self.value == other.value
        if isinstance(other, (int, bool)):
            return self.value == int(other)
        if isinstance(other, IbObject):
            return self.value == other.to_native()
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

@register_ib_type("bool")
class IbBool(IbObject):
    """
    包装 Python 原生 bool 的 IBC 对象。
    """
    __slots__ = ('value',)

    def __init__(self, value: bool, ib_class: IbClass):
        super().__init__(ib_class)
        self.value = value

    def to_native(self, memo=None) -> bool:
        return self.value

    def to_int(self) -> int:
        return 1 if self.value else 0

    def __eq__(self, other):
        if isinstance(other, IbBool):
            return self.value == other.value
        if hasattr(other, 'to_native'):
            return self.value == other.to_native()
        return False

    def __hash__(self):
        return hash(self.value)

    def __bool__(self):
        return self.value

@register_ib_type("float")
class IbFloat(IbObject):
    """
    包装 Python 原生 float 的 IBC 对象。
    """
    __slots__ = ('value',)

    def __init__(self, value: float, ib_class: IbClass):
        super().__init__(ib_class)
        self.value = value

    def to_native(self, memo=None) -> float:
        return self.value

    def to_bool(self) -> IbObject:
        return self.ib_class.registry.box(1 if self.value != 0.0 else 0)

    def cast_to(self, target_class: Any) -> IbObject:
        target_desc = target_class.spec if hasattr(target_class, 'spec') else None
        res_val = _cast_numeric_to_native(self.value, target_desc)
        return self.ib_class.registry.box(res_val)

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {"type": self.ib_class.name, "value": self.value}

    def __repr__(self):
        return f"Float({self.value})"

    # ---  自动化运算符绑定支持 ---
    def __add__(self, other: IbObject) -> Any: return self.value + other.to_native()
    def __sub__(self, other: IbObject) -> Any: return self.value - other.to_native()
    def __mul__(self, other: IbObject) -> Any: return self.value * other.to_native()
    def __truediv__(self, other: IbObject) -> Any: return self.value / other.to_native()
    def __floordiv__(self, other: IbObject) -> Any: return self.value // other.to_native()
    def __mod__(self, other: IbObject) -> Any: return self.value % other.to_native()
    def __pow__(self, other: IbObject) -> Any: return self.value ** other.to_native()
    def __neg__(self) -> Any: return -self.value
    def __pos__(self) -> Any: return +self.value

    def __lt__(self, other: IbObject) -> bool: return self.value < other.to_native()
    def __le__(self, other: IbObject) -> bool: return self.value <= other.to_native()
    def __gt__(self, other: IbObject) -> bool: return self.value > other.to_native()
    def __ge__(self, other: IbObject) -> bool: return self.value >= other.to_native()
    def __eq__(self, other: IbObject) -> bool: return self.value == other.to_native()
    def __ne__(self, other: IbObject) -> bool: return self.value != other.to_native()

@register_ib_type("str")
class IbString(IbObject):
    """
    包装 Python 原生 str 的 IBC 对象。
    """
    __slots__ = ('value',)

    def __init__(self, value: str, ib_class: IbClass):
        super().__init__(ib_class)
        self.value = value

    def to_native(self, memo=None) -> str:
        return self.value

    def len(self) -> IbObject:
        return self.ib_class.registry.box(len(self.value))

    def to_bool(self) -> IbObject:
        val = self.value.strip().lower()
        # 强约束决策逻辑：
        # 1. 仅当显式为 "1", "true", "yes" 时为 True (1)
        # 2. 仅当显式为 "0", "false", "no" 或空字符串时为 False (0)
        # 3. 其余任何模糊回复（如 "maybe", "i think so"）均应触发不确定性标志，以便 llmexcept 捕获
        if val in ("1", "true", "yes", "on"):
            return self.ib_class.registry.box(1)
        if val in ("0", "false", "no", "off", "null", "none", ""):
            return self.ib_class.registry.box(0)
            
        # [Result Mode Refactor] 不再抛出 Python 异常。
        # 通过 Registry 获取当前执行上下文并设置不确定性结果。
        execution_context = self.ib_class.registry.get_execution_context()
        if execution_context and execution_context.runtime_context:
            from core.runtime.interpreter.llm_result import LLMResult
            execution_context.runtime_context.set_last_llm_result(
                LLMResult.uncertain_result(
                    raw_response=self.value,
                    retry_hint=f"模糊的布尔判定结果: '{self.value}'。期望 '0' 或 '1'。"
                )
            )
            
        # 返回 none (或者 0)，解释器（如 visit_IbIf）会检查 last_llm_result.is_uncertain 并立即停止执行
        return self.ib_class.registry.get_none()

    def cast_to(self, target_class: Any) -> IbObject:
        target_desc = target_class.spec if hasattr(target_class, 'spec') else None
        try:
            res_val = _cast_string_to_native(self.value, target_desc)
            return self.ib_class.registry.box(res_val)
        except (ValueError, TypeError) as e:
            # [Result Mode Refactor] 统一通过 LLMResult 信号不确定性，不再使用 Python 异常
            execution_context = self.ib_class.registry.get_execution_context()
            if execution_context and execution_context.runtime_context:
                from core.runtime.interpreter.llm_result import LLMResult
                execution_context.runtime_context.set_last_llm_result(
                    LLMResult.uncertain_result(
                        raw_response=self.value,
                        retry_hint=f"类型强制转换失败: 将 '{self.value}' 转换为 {target_desc} 失败: {str(e)}"
                    )
                )
            return self.ib_class.registry.get_none()

    def upper(self) -> IbObject:
        return self.ib_class.registry.box(self.value.upper())

    def lower(self) -> IbObject:
        return self.ib_class.registry.box(self.value.lower())

    def strip(self) -> IbObject:
        return self.ib_class.registry.box(self.value.strip())

    def split(self, sep: Optional[str] = None) -> IbObject:
        if sep is None:
            parts = self.value.split()
        else:
            # sep 可能是 IbString（通过 unbox=False 注册的原生方法传入），需先拆箱
            native_sep = sep.to_native() if hasattr(sep, 'to_native') else sep
            parts = self.value.split(native_sep)
        registry = self.ib_class.registry
        return registry.box([registry.box(p) for p in parts])

    def is_empty(self) -> IbObject:
        return self.ib_class.registry.box(len(self.value.strip()) == 0)

    def find(self, substring: Any) -> IbObject:
        """查找子串首次出现的位置，未找到返回 -1"""
        sub_str = substring.to_native() if hasattr(substring, 'to_native') else str(substring)
        idx = self.value.find(sub_str)
        return self.ib_class.registry.box(idx)

    def find_last(self, substring: Any) -> IbObject:
        """查找子串最后一次出现的位置，未找到返回 -1"""
        sub_str = substring.to_native() if hasattr(substring, 'to_native') else str(substring)
        idx = self.value.rfind(sub_str)
        return self.ib_class.registry.box(idx)

    def contains(self, substring: Any) -> IbObject:
        """检查是否包含子串"""
        sub_str = substring.to_native() if hasattr(substring, 'to_native') else str(substring)
        return self.ib_class.registry.box(sub_str in self.value)

    def __contains__(self, item: Any) -> bool:
        """Python-level containment check used by the 'in' operator at runtime"""
        sub_str = item.to_native() if isinstance(item, IbObject) else str(item)
        return sub_str in self.value

    def replace(self, old: Any, new: Any) -> IbObject:
        """替换子串。对齐 Python str.replace(old, new)"""
        old_str = old.to_native() if hasattr(old, 'to_native') else str(old)
        new_str = new.to_native() if hasattr(new, 'to_native') else str(new)
        return self.ib_class.registry.box(self.value.replace(old_str, new_str))

    def startswith(self, prefix: Any) -> IbObject:
        """判断是否以指定前缀开头。对齐 Python str.startswith(prefix)"""
        prefix_str = prefix.to_native() if hasattr(prefix, 'to_native') else str(prefix)
        return self.ib_class.registry.box(self.value.startswith(prefix_str))

    def endswith(self, suffix: Any) -> IbObject:
        """判断是否以指定后缀结尾。对齐 Python str.endswith(suffix)"""
        suffix_str = suffix.to_native() if hasattr(suffix, 'to_native') else str(suffix)
        return self.ib_class.registry.box(self.value.endswith(suffix_str))

    def __getitem__(self, key: Any) -> IbObject:
        """支持字符串下标与切片"""
        idx = key.to_native() if hasattr(key, 'to_native') else key
        try:
            res = self.value[idx]
            return self.ib_class.registry.box(res)
        except IndexError:
            raise InterpreterError(f"IndexError: string index out of range: {idx}")

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {"type": self.ib_class.name, "value": self.value}

    def __repr__(self):
        return f"String('{self.value}')"

    # ---  自动化运算符绑定支持 ---
    def __add__(self, other: IbObject) -> Any:
        if other.ib_class.name != "str":
             raise InterpreterError(f"TypeError: Cannot concatenate 'str' and '{other.ib_class.name}'")
        return self.value + other.to_native()
    
    def __eq__(self, other: IbObject) -> bool: return self.value == other.to_native()
    def __ne__(self, other: IbObject) -> bool: return self.value != other.to_native()

@register_ib_type("Exception")
class IbException(IbObject):
    """Exception 类型的运行时实现"""
    
    def message(self) -> IbObject:
        msg = self.fields.get("message")
        if msg: return msg
        return self.ib_class.registry.box("")

    def cast_to(self, target_class: Any) -> IbObject:
        """ 支持 Exception 的强转逻辑"""
        if target_class.name in ("str", "any"):
            msg = self.fields.get("message")
            if msg: return msg
            return self.ib_class.registry.box("Exception")
        return self

@register_ib_type("list")
class IbList(IbObject):
    """
    包装 Python 原生 list 的 IBC 对象。
    """
    __slots__ = ('elements',)

    def __init__(self, elements: List[IbObject], ib_class: IbClass):
        super().__init__(ib_class)
        self.elements = elements

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
        self.elements.append(item)
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
        idx = key.to_native() if hasattr(key, 'to_native') else key
        try:
            res = self.elements[idx]
            if isinstance(idx, slice):
                # 切片返回的是 IbObject 列表，需要重新装箱为 IbList
                return self.ib_class.registry.box(res)
            return res
        except IndexError:
            raise InterpreterError(f"IndexError: list index out of range: {idx}")

    def __setitem__(self, key: Any, val: IbObject) -> None:
        idx = key.to_native() if hasattr(key, 'to_native') else key
        self.elements[idx] = val

    def sort(self) -> IbObject:
        self.elements.sort(key=lambda x: x.to_native())
        return self.ib_class.registry.get_none()

    def insert(self, index: Any, item: IbObject) -> IbObject:
        """在指定位置插入元素。对齐 Python list.insert(index, item)"""
        idx = index.to_native() if hasattr(index, 'to_native') else int(index)
        self.elements.insert(idx, item)
        return self.ib_class.registry.get_none()

    def remove(self, item: Any) -> IbObject:
        """删除第一个匹配元素。对齐 Python list.remove(item)"""
        native = item.to_native() if hasattr(item, 'to_native') else item
        for i, el in enumerate(self.elements):
            if el.to_native() == native:
                del self.elements[i]
                return self.ib_class.registry.get_none()
        raise InterpreterError(f"ValueError: list.remove(x): x not in list")

    def index(self, item: Any) -> IbObject:
        """返回第一个匹配元素的索引。对齐 Python list.index(item)"""
        native = item.to_native() if hasattr(item, 'to_native') else item
        for i, el in enumerate(self.elements):
            if el.to_native() == native:
                return self.ib_class.registry.box(i)
        raise InterpreterError(f"ValueError: {native!r} is not in list")

    def count(self, item: Any) -> IbObject:
        """统计元素出现次数。对齐 Python list.count(item)"""
        native = item.to_native() if hasattr(item, 'to_native') else item
        cnt = sum(1 for el in self.elements if el.to_native() == native)
        return self.ib_class.registry.box(cnt)

    def contains(self, item: Any) -> IbObject:
        """检查是否包含元素（便捷方法，等价于 item in list）"""
        native = item.to_native() if hasattr(item, 'to_native') else item
        return self.ib_class.registry.box(any(el.to_native() == native for el in self.elements))

    def __contains__(self, item: Any) -> bool:
        """Python-level containment check used by the 'in' operator at runtime"""
        native = item.to_native() if isinstance(item, IbObject) else item
        return any(el.to_native() == native for el in self.elements)

    def __add__(self, other: IbObject) -> Any:
        """列表拼接。对齐 Python list + list"""
        if not isinstance(other, IbList):
            raise InterpreterError(f"TypeError: can only concatenate list (not '{other.ib_class.name}') to list")
        return self.elements + other.elements

@register_ib_type("tuple")
class IbTuple(IbObject):
    """
    包装 Python 原生 tuple 的 IBC 对象。
    与 IbList 的关键区别：不可变（没有 append/pop/sort/clear/__setitem__）。
    """
    __slots__ = ('elements',)

    def __init__(self, elements: tuple, ib_class: IbClass):
        super().__init__(ib_class)
        self.elements = elements  # tuple of IbObject

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
        idx = key.to_native() if hasattr(key, 'to_native') else key
        try:
            res = self.elements[idx]
            if isinstance(idx, slice):
                return self.ib_class.registry.box(tuple(res) if isinstance(res, (list, tuple)) else res)
            return res
        except IndexError:
            raise InterpreterError(f"IndexError: tuple index out of range: {idx}")

@register_ib_type("dict")
class IbDict(IbObject):
    """
    包装 Python 原生 dict 的 IBC 对象。
    """
    def __init__(self, fields: Dict[str, IbObject], ib_class: IbClass):
        super().__init__(ib_class)
        self.fields = fields

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
        # 返回 IbList 包装的原生 key 列表
        # 注意：这里的 key 已经是原生类型（通常是 str）
        # 我们需要将其装箱
        native_keys = list(self.fields.keys())
        return self.ib_class.registry.box(native_keys)

    def values(self) -> IbObject:
        # 返回 IbList 包装的值列表
        return self.ib_class.registry.box(list(self.fields.values()))

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
        k = key.to_native() if hasattr(key, 'to_native') else key
        return self.fields[k]

    def __setitem__(self, key: Any, val: IbObject) -> None:
        k = key.to_native() if hasattr(key, 'to_native') else key
        self.fields[k] = val

    def get(self, key: Any, default: Optional[IbObject] = None) -> IbObject:
        k = key.to_native() if hasattr(key, 'to_native') else key
        if k in self.fields:
            return self.fields[k]
        return default or self.ib_class.registry.get_none()

    def pop(self, key: Any, default: Optional[IbObject] = None) -> IbObject:
        """删除并返回指定 key 的值。对齐 Python dict.pop(key[, default])"""
        k = key.to_native() if hasattr(key, 'to_native') else key
        if k in self.fields:
            return self.fields.pop(k)
        if default is not None:
            return default
        raise InterpreterError(f"KeyError: '{k}'")

    def __iter__(self):
        return iter(self.fields)

    def __contains__(self, key):
        # 支持 IbString 或原生 string key
        native_key = key.to_native() if isinstance(key, IbObject) else key
        return native_key in self.fields

    def __getitem__(self, key):
        native_key = key.to_native() if isinstance(key, IbObject) else key
        return self.fields[native_key]

@register_ib_type("deferred")
class IbDeferred(IbObject):
    """
    通用延迟表达式对象。

    ``lambda`` / ``snapshot`` 修饰的任意表达式都会被包装为 IbDeferred。
    调用时重新执行被延迟的 AST 节点（lambda 模式）或返回捕获的快照值
    （snapshot 模式）。

    公理化设计
    ----------
    * IbDeferred 在创建时捕获 ``execution_context`` 引用。
    * ``call()`` 重新访问被延迟的 AST 节点以完成求值。
    * deferred_mode='lambda'   —— 每次调用重新求值
    * deferred_mode='snapshot' —— 首次调用时求值并缓存

    继承链：IbDeferred → IbObject (axiom: deferred → callable → Object)
    """

    def __init__(
        self,
        node_uid: str,
        ib_class: IbClass,
        deferred_mode: str = "lambda",
        execution_context: Optional[Any] = None,
        captured_scope: Optional[Any] = None,
    ):
        super().__init__(ib_class)
        self.node_uid = node_uid
        self.deferred_mode = deferred_mode
        self._execution_context = execution_context
        self._captured_scope = captured_scope
        self._cache: Optional[IbObject] = None

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """
        调用延迟表达式：重新执行被延迟的 AST 节点。

        - lambda 模式：每次调用都重新求值（使用当前上下文）
        - snapshot 模式：首次调用求值并缓存，后续调用返回缓存
        """
        if self.deferred_mode == "snapshot" and self._cache is not None:
            return self._cache

        if self._execution_context is None:
            raise RuntimeError(
                f"IbDeferred '{self.node_uid}': execution_context is None. "
                "This typically occurs when the deferred expression was deserialized "
                "without a live interpreter, or when the factory failed to inject the context. "
                "Ensure engine._prepare_interpreter() has completed before invoking a deferred expression."
            )

        # 在捕获的作用域（如果有）中求值
        rt_context = self._execution_context.runtime_context
        old_scope = None
        if self._captured_scope is not None:
            old_scope = rt_context.current_scope
            rt_context.current_scope = self._captured_scope

        try:
            result = self._execution_context.visit(self.node_uid)
        finally:
            if old_scope is not None:
                rt_context.current_scope = old_scope

        if self.deferred_mode == "snapshot":
            self._cache = result

        return result

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        if self._cache is not None:
            return self._cache.to_native()
        return self

    def __to_prompt__(self) -> str:
        if self._cache is not None:
            return self._cache.__to_prompt__()
        return f"<Deferred {self.node_uid}>"

    def receive(self, message: str, args: List[IbObject]) -> IbObject:
        if self._cache is not None:
            return self._cache.receive(message, args)

        if message in ("__get_metadata__", "__to_prompt__", "node_uid"):
            return self.ib_class.registry.box(str(self))

        if message == "__call__":
            return self.call(self.ib_class.registry.get_none(), args)

        raise RuntimeError(f"Deferred '{self.node_uid}' is not yet evaluated. Cannot process message '{message}'.")

    def __repr__(self):
        mode = self.deferred_mode or "immediate"
        return f"<Deferred({mode}) {self.node_uid}>"


@register_ib_type("behavior")
class IbBehavior(IbObject):
    """
    延迟执行的 LLM 行为对象 (~...~)。

    公理化设计原则
    --------------
    IbBehavior 是 deferred 家族中针对 LLM 行为表达式的特化。
    继承链：behavior → deferred → callable → Object

    * 行为对象在创建时捕获 ``execution_context`` 引用（与 IbUserFunction 同构）。
    * ``call()`` 通过 ``ib_class.registry.get_llm_executor().invoke_behavior()``
      完成自主执行，不再依赖外部的 ``_execute_behavior`` 路由。
    * BaseHandler 中的 ``_execute_behavior`` 方法已删除。
    * 与 IbDeferred 的区别：IbBehavior 延迟的是 LLM 调用（需要意图栈），
      IbDeferred 延迟的是普通表达式求值（纯 AST 重访）。
    """
    def __init__(
        self,
        node_uid: str,
        captured_intents: Union[List[Any], Any],
        ib_class: IbClass,
        expected_type: Optional[str] = None,
        call_intent: Optional[Any] = None,
        deferred_mode: Optional[str] = None,
        execution_context: Optional[Any] = None,
    ):
        """
        IbBehavior 是纯粹的数据描述符与自主执行单元。
        call_intent 用于保存 @! 排他意图，使延迟执行时意图不丢失。
        deferred_mode: 'lambda' | 'snapshot' | None (immediate)
        execution_context: 创建时的执行上下文引用（供 call() 使用）。
        """
        super().__init__(ib_class)
        self.node = node_uid
        self.captured_intents = captured_intents
        self.expected_type = expected_type
        self.call_intent = call_intent
        self.deferred_mode = deferred_mode
        self._execution_context = execution_context
        self._cache: Optional[IbObject] = None

    def value(self):
        if self._cache: return self._cache.to_native()
        raise RuntimeError("Behavior is not executed. Please use LLMExecutor to run it.")

    def to_native(self) -> Any:
        if self._cache: return self._cache.to_native()
        return self

    def __to_prompt__(self) -> str:
        if self._cache: return self._cache.__to_prompt__()
        return f"<Behavior {self.node}>"

    def __repr__(self):
        return f"<Behavior {self.node}>"

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {
            "type": self.ib_class.name,
            "node_uid": self.node,
            "captured_intents": [str(i) for i in self.captured_intents],
            "expected_type": self.expected_type
        }

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """
        公理化自主调用：通过内核 LLM 执行器完成行为执行。

        执行流程：
        1. 从 KernelRegistry 获取 IILLMExecutor（注入点：engine._prepare_interpreter）。
        2. 调用 executor.invoke_behavior(self, execution_context)：
           - 使用 captured_intents（snapshot 模式）或当前意图栈（lambda 模式）。
           - 按 expected_type 解析 LLM 返回值。
           - 将 LLMResult 写入 RuntimeContext 供 llmexcept 使用。
        3. 返回解析后的 IbObject。
        """
        executor = self.ib_class.registry.get_llm_executor()
        if executor is None:
            raise RuntimeError(
                f"IbBehavior '{self.node}': LLM executor not registered in KernelRegistry. "
                "Ensure engine._prepare_interpreter() has completed before invoking a behavior."
            )
        return executor.invoke_behavior(self, self._execution_context)

    def receive(self, message: str, args: List[IbObject]) -> IbObject:
        """
        行为对象的消息处理。
        允许查询元数据，仅在尝试"执行行为本身"且无上下文时才抛出异常。
        """
        if self._cache: return self._cache.receive(message, args)

        if message in ("__get_metadata__", "__to_prompt__", "node_uid"):
            return self.ib_class.registry.box(str(self))

        raise RuntimeError(f"Behavior '{self.node}' is not executed. Cannot process message '{message}'.")
