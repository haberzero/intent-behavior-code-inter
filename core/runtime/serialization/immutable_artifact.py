from typing import Any, Dict, Iterator, Mapping

class ImmutableArtifact(Mapping):
    """
    [IES 2.2] 不可变产物容器。
    用于确保编译器输出的 artifact dict 无法被解释器修改，
    从而保证 save_state/load_state 断点机制的确定性。

    设计原则：
    1. 任何修改操作都抛出 TypeError
    2. 提供只读的 dict-like 访问接口
    3. 嵌套 dict 也会被自动包装为 ImmutableArtifact
    """
    def __init__(self, data: Dict[str, Any], _memo: set = None):
        if _memo is None:
            _memo = set()
        object.__setattr__(self, '_data', self._wrap_if_dict(data, _memo))

    def _wrap_if_dict(self, value: Any, memo: set) -> Any:
        """递归将嵌套 dict 包装为 ImmutableArtifact，带循环引用检测"""
        if isinstance(value, dict):
            obj_id = id(value)
            if obj_id in memo:
                return value
            memo.add(obj_id)
            return ImmutableArtifact(value, _memo=memo)
        elif isinstance(value, list):
            return tuple(self._wrap_if_dict(item, memo) for item in value)
        return value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"ImmutableArtifact({self._data!r})"

    def __str__(self) -> str:
        return str(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        """只读访问，支持默认值"""
        return self._data.get(key, default)

    def keys(self):
        """返回键的只读视图"""
        return self._data.keys()

    def values(self):
        """返回值视图（已包装为不可变）"""
        return self._data.values()

    def items(self):
        """返回键值对视图"""
        return self._data.items()

    def __setitem__(self, key: str, value: Any) -> None:
        raise TypeError("ImmutableArtifact does not support item assignment")

    def __delitem__(self, key: str) -> None:
        raise TypeError("ImmutableArtifact does not support item deletion")

    def setdefault(self, key: str, default: Any = None) -> Any:
        raise TypeError("ImmutableArtifact does not support setdefault")

    def pop(self, key: str, *args) -> Any:
        raise TypeError("ImmutableArtifact does not support pop")

    def popitem(self) -> tuple:
        raise TypeError("ImmutableArtifact does not support popitem")

    def clear(self) -> None:
        raise TypeError("ImmutableArtifact does not support clear")

    def update(self, *args, **kwargs) -> None:
        raise TypeError("ImmutableArtifact does not support update")

    def __hash__(self) -> int:
        """支持将 ImmutableArtifact 用作 dict 的键"""
        return hash(self._data)

    def __eq__(self, other: object) -> bool:
        """支持相等性比较"""
        if isinstance(other, ImmutableArtifact):
            return self._data == other._data
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return False
