from typing import Any, Dict, Iterator, Mapping, Optional

class ReadOnlyNodePool(Mapping[str, Any]):
    """
    [Active Defense] AST 节点池的只读视图。
    采用 Proxy 模式封装原始 node_pool，禁止任何写操作。
    """
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def __getitem__(self, key: str) -> Any:
        val = self._data[key]
        return self._wrap(val)

    def _wrap(self, val: Any) -> Any:
        if isinstance(val, dict):
            # 递归包装嵌套字典 (AST 节点通常是嵌套字典)
            return ReadOnlyNodePool(val)
        if isinstance(val, list):
            # 包装列表中的所有元素
            return [self._wrap(i) for i in val]
        return val

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __repr__(self):
        return f"ReadOnlyNodePool({repr(self._data)})"

    # 显式禁止修改
    def __setitem__(self, key, value):
        raise TypeError("AST View is read-only. Modification is strictly prohibited.")

    def __delitem__(self, key):
        raise TypeError("AST View is read-only. Deletion is strictly prohibited.")
