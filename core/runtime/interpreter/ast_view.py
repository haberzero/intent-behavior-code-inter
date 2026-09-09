from typing import Any, Dict, Iterator, Mapping, Optional
from core.base.source_atomic import Location

class ReadOnlyNodePool(Mapping[str, Any]):
    """
    [Active Defense] AST 节点池的只读视图。
    采用 Proxy 模式封装原始 node_pool，禁止任何写操作。
    """
    def __init__(self, data: Dict[str, Any]):
        self._data = data
        # [P2 数据平面快速路径] 嵌套容器包装记忆化（id → 已包装视图）：AST 节点不可变
        # 且生命周期内存活（node_pool 持有），id 稳定；重复字段访问命中缓存，消除逐次
        # 递归重新包装（profile：ast_view.get ~490k 次/程序）。只读语义不变。
        self._wrap_memo: Dict[int, Any] = {}

    def __getitem__(self, key: str) -> Any:
        val = self._data[key]
        return self._wrap(val)

    def _wrap(self, val: Any) -> Any:
        if isinstance(val, (dict, list)):
            key = id(val)
            cached = self._wrap_memo.get(key)
            if cached is not None:
                return cached
            if isinstance(val, dict):
                # 递归包装嵌套字典 (AST 节点通常是嵌套字典)
                res: Any = ReadOnlyNodePool(val)
            else:
                # 包装列表中的所有元素
                res = [self._wrap(i) for i in val]
            self._wrap_memo[key] = res
            return res
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
