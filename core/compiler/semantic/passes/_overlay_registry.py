"""
core/compiler/semantic/passes/_overlay_registry.py — 覆层声明登记。

类型检查访客（TypeCheckingVisitor）跨模块共享的覆层状态：
- 声明端（DeclarationVisitorsMixin.visit_IbImplDef is_overlay 分支）登记
  ``type_name -> {覆层方法名}``；
- 消费端（StatementVisitorsMixin.visit_IbWithOverlayStmt）校验目标
  ``<类型>.<协议方法>`` 存在对应覆层声明，并登记"被启用"的覆层目标；
- 模块末（visit_IbModule）对"声明了但从未被启用"的覆层发"存在未启用"告警。

单一权威：本类的字面量登记（声明 / 启用），不散落。
"""

from __future__ import annotations

from typing import Dict, Set


class _OverlayRegistry:
    """覆层声明与启用的跨声明/语句访客共享登记表（单声明、可增量启用）。"""

    def __init__(self) -> None:
        # type_name -> 已声明覆层方法名集合
        self._declared: Dict[str, Set[str]] = {}
        # 已通过 with overlay 引用的 (type_name, method_name) 集合（用于未启用告警）
        self._enabled_refs: Set[tuple] = set()

    def add(self, type_name: str, method_names: Set[str]) -> None:
        entry = self._declared.setdefault(type_name, set())
        entry.update(method_names)

    def methods(self, type_name: str) -> Set[str]:
        return set(self._declared.get(type_name, set()))

    def declared_items(self):
        """遍历已声明覆层 ``(type_name, method_name)``（供未启用告警消费）。"""
        for type_name, methods in self._declared.items():
            for method_name in methods:
                yield type_name, method_name

    def has(self, type_name: str, method_name: str) -> bool:
        return method_name in self._declared.get(type_name, set())

    def mark_enabled(self, type_name: str, method_name: str) -> None:
        self._enabled_refs.add((type_name, method_name))

    def enabled_targets(self) -> Set[tuple]:
        return set(self._enabled_refs)
