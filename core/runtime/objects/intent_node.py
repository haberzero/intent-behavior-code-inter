"""
core/runtime/objects/intent_node.py

IntentNode: 不可变意图链表节点，支持结构共享。

提取为独立模块以打破 intent_context.py ↔ runtime_context.py 的循环依赖。
"""
from __future__ import annotations

from typing import Any, List, Optional, Union


class IntentNode:
    """不可变意图节点，支持结构共享以优化内存"""

    def __init__(self, intent: Union[Any, Any], parent: Optional['IntentNode'] = None):
        self.intent = intent
        self.parent = parent
        self._cached_list: Optional[List[Any]] = None

    def to_list(self) -> List[Any]:
        """展平为列表（带缓存）"""
        if self._cached_list is not None:
            return self._cached_list

        res = []
        curr: Optional[IntentNode] = self
        while curr:
            res.append(curr.intent)
            curr = curr.parent
        # 由于是向上链接，展平后需要反转以保持从底到顶的顺序
        res.reverse()
        self._cached_list = res
        return res
