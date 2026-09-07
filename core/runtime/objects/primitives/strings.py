from typing import Any, Dict, Optional
from ..kernel import IbObject, IbValue, IbClass
from ..kernel.base import unbox
from core.runtime.support.converters import _cast_string_to_native
from core.kernel.issue import InterpreterError
from core.base.diagnostics.codes import RUN_TYPE_MISMATCH
from core.runtime.exceptions import ThrownException
from ..ib_type_mapping import register_ib_type

@register_ib_type("str")
class IbString(IbValue):
    """
    包装 Python 原生 str 的 IBC 对象。
    """
    __slots__ = ()

    def __init__(self, value: str, ib_class: IbClass):
        super().__init__(ib_class, payload=value)

    def to_native(self, memo=None) -> str:
        return self.value

    def len(self) -> IbObject:
        return self.ib_class.registry.box(len(self.value))

    def to_bool(self) -> IbObject:
        # 纯 Python 语义：非空字符串为 True，空字符串为 False
        # LLM 不确定性检测由 interpreter.is_truthy() 在使用点处理
        return self.ib_class.registry.box(bool(self.value))

    def cast_to(self, target_class: Any) -> IbObject:
        target_desc = target_class.spec
        try:
            res_val = _cast_string_to_native(self.value, target_desc)
            return self.ib_class.registry.box(res_val)
        except (ValueError, TypeError) as e:
            raise InterpreterError(
                f"TypeError: Cannot convert '{self.value}' to {target_desc.get_base_name() if target_desc else 'target type'}: {str(e)}"
            ) from e

    def upper(self) -> IbObject:
        return self.ib_class.registry.box(self.value.upper())

    def lower(self) -> IbObject:
        return self.ib_class.registry.box(self.value.lower())

    def strip(self) -> IbObject:
        return self.ib_class.registry.box(self.value.strip())

    def join(self, iterable: Any) -> IbObject:
        """用本字符串作为分隔符，连接列表中的元素。对齐 Python str.join(iterable)"""
        parts = unbox(iterable)
        str_parts = []
        for p in parts:
            native = unbox(p)
            str_parts.append(str(native))
        return self.ib_class.registry.box(self.value.join(str_parts))

    def format(self, arg: Any) -> IbObject:
        """简单格式化：将 {} 占位符替换为参数的字符串表示。对齐 Python str.format(value)"""
        val = arg.to_native() if isinstance(arg, IbObject) else str(arg)
        return self.ib_class.registry.box(self.value.format(str(val)))

    def split(self, sep: Optional[str] = None) -> IbObject:
        if sep is None:
            parts = self.value.split()
        else:
            # sep 可能是 IbString（通过 unbox=False 注册的原生方法传入），需先拆箱
            native_sep = unbox(sep)
            parts = self.value.split(native_sep)
        registry = self.ib_class.registry
        return registry.box([registry.box(p) for p in parts])

    def is_empty(self) -> IbObject:
        return self.ib_class.registry.box(len(self.value.strip()) == 0)

    def find(self, substring: Any) -> IbObject:
        """查找子串首次出现的位置，未找到返回 -1"""
        sub_str = substring.to_native() if isinstance(substring, IbObject) else str(substring)
        idx = self.value.find(sub_str)
        return self.ib_class.registry.box(idx)

    def find_last(self, substring: Any) -> IbObject:
        """查找子串最后一次出现的位置，未找到返回 -1"""
        sub_str = substring.to_native() if isinstance(substring, IbObject) else str(substring)
        idx = self.value.rfind(sub_str)
        return self.ib_class.registry.box(idx)

    def contains(self, substring: Any) -> IbObject:
        """检查是否包含子串"""
        sub_str = substring.to_native() if isinstance(substring, IbObject) else str(substring)
        return self.ib_class.registry.box(sub_str in self.value)

    def __contains__(self, item: Any) -> bool:
        """Python-level containment check used by the 'in' operator at runtime"""
        sub_str = item.to_native() if isinstance(item, IbObject) else str(item)
        return sub_str in self.value

    def replace(self, old: Any, new: Any) -> IbObject:
        """替换子串。对齐 Python str.replace(old, new)"""
        old_str = old.to_native() if isinstance(old, IbObject) else str(old)
        new_str = new.to_native() if isinstance(new, IbObject) else str(new)
        return self.ib_class.registry.box(self.value.replace(old_str, new_str))

    def startswith(self, prefix: Any) -> IbObject:
        """判断是否以指定前缀开头。对齐 Python str.startswith(prefix)"""
        prefix_str = prefix.to_native() if isinstance(prefix, IbObject) else str(prefix)
        return self.ib_class.registry.box(self.value.startswith(prefix_str))

    def endswith(self, suffix: Any) -> IbObject:
        """判断是否以指定后缀结尾。对齐 Python str.endswith(suffix)"""
        suffix_str = suffix.to_native() if isinstance(suffix, IbObject) else str(suffix)
        return self.ib_class.registry.box(self.value.endswith(suffix_str))

    def __getitem__(self, key: Any) -> IbObject:
        """支持字符串下标与切片"""
        idx = unbox(key)
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
        # 右操作数为 llm_uncertain 时抛出 LLMParseError
        if other.ib_class.name == "llm_uncertain":
            registry = self.ib_class.registry
            error = registry.make_llm_parse_error(
                "string concatenation with uncertain LLM result is not allowed; "
                "use explicit `(str)uncertain_var` cast or handle the value via try/except LLMParseError",
                raw_response="",
                type_name="str",
            )
            raise ThrownException(error)
        if other.ib_class.name != "str":
             raise InterpreterError(f"TypeError: Cannot concatenate 'str' and '{other.ib_class.name}'", error_code=RUN_TYPE_MISMATCH)
        return self.value + other.to_native()

    def __mul__(self, other: IbObject) -> Any:
        """字符串重复: str * int"""
        n = unbox(other)
        if not isinstance(n, int):
            raise InterpreterError(f"TypeError: can't multiply sequence by non-int of type '{other.ib_class.name}'", error_code=RUN_TYPE_MISMATCH)
        return self.value * n

    def _require_str_other(self, op: str, other: IbObject) -> None:
        if other.ib_class.name != "str":
            raise InterpreterError(f"TypeError: Cannot compare 'str' and '{other.ib_class.name}' with '{op}'", error_code=RUN_TYPE_MISMATCH)

    def __lt__(self, other: IbObject) -> bool:
        self._require_str_other("<", other); return self.value < other.to_native()
    def __le__(self, other: IbObject) -> bool:
        self._require_str_other("<=", other); return self.value <= other.to_native()
    def __gt__(self, other: IbObject) -> bool:
        self._require_str_other(">", other); return self.value > other.to_native()
    def __ge__(self, other: IbObject) -> bool:
        self._require_str_other(">=", other); return self.value >= other.to_native()
    def __eq__(self, other: IbObject) -> bool: return self.value == other.to_native()
    def __ne__(self, other: IbObject) -> bool: return self.value != other.to_native()
