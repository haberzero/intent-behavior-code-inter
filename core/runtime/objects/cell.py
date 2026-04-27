"""
core/runtime/objects/cell.py

IbCell —— 词法闭包 Cell 变量的独立堆容器。

公理层依据
----------
* SC-3 (Cell 语义): Cell 变量通过 ``IbCell`` 间接存储。``IbCell`` 是独立的、
  与任何 ``ScopeImpl`` 无关的堆对象，包含字段 ``value``。对 Cell 变量的读写
  实际上是对 ``IbCell.value`` 的读写。
* SC-4 (自由变量捕获): 嵌套函数/lambda 创建时，其自由变量对应的 ``IbCell``
  引用被复制进该函数对象的 ``closure`` 字典。此后函数对象持有这些 ``IbCell``
  的引用，无论外层作用域是否仍然活跃。
* LT-2 (Cell 延长生命周期): ``IbCell`` 的生命周期由所有引用它的 closure 字典
  决定，与原 ``ScopeImpl`` 解耦。
* LT-3 (snapshot 自包含性): snapshot 类型的 fn 对象通过持有自己的 ``IbCell``
  副本（值拷贝）实现自包含。

设计要点
--------
* ``IbCell`` 不是 IBCI 用户可见类型，不注册到类型映射，仅作为 VM 内部构造。
* ``IbCell`` 不继承 ``IbObject``：它是"持有 IbObject 的容器"，不能被 box 或
  作为 IBCI 对象传递。这避免了被误用作通用 IBCI 值。
* 身份语义优先于值语义：两个 cell 即使持有相等的 value 也不被视为相等——
  共享 cell 必须通过共享同一个 ``IbCell`` 实例实现，这是闭包共享语义的前提。
* 提供 ``trace_refs()`` 钩子供未来 GC 根集合扫描使用 (公理 GC-2)。

本模块为 M1 (fn 新语法 + IbCell 集成) 与 M2 (GC 根集合) 提供基础原语；
本身不引用任何 ``ScopeImpl`` / ``IbDeferred`` / ``IbBehavior``，保持纯粹。
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator, Optional


# 哨兵：表示 cell 尚未被赋值。使用独立的私有 sentinel 而非 None，
# 因为 IBCI 中 None 是合法值（IbNone），二者不应混淆。
class _Empty:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - 调试输出
        return "<IbCell.EMPTY>"


_EMPTY: Any = _Empty()


class IbCell:
    """
    词法闭包 Cell 容器。

    持有单一 ``value`` 槽位，独立于任何 ``ScopeImpl`` 生命周期存在。
    多个闭包可共享同一 ``IbCell`` 引用以实现"对同一变量的共享读写"语义
    (公理 SC-3 / SC-4)。

    示例 (典型用法，Step 12.5 / M1 集成后)::

        n_cell = IbCell(box_int(10))
        # 内层 lambda 持有 n_cell 引用 (closure["n"] = n_cell)
        # 调用 lambda 时:    n_cell.get() -> IbInteger(10)
        # 外层修改 n:        n_cell.set(box_int(20))
        # 再次调用 lambda:   n_cell.get() -> IbInteger(20)

    身份语义
    --------
    ``__eq__`` / ``__hash__`` 基于对象身份 (与 ``object`` 默认行为一致)，
    确保 cell 可以作为字典键，且两个独立 cell 即使 value 相等也不相等。
    """

    __slots__ = ("_value",)

    # 公开常量：未初始化哨兵。外部读取时可与 ``IbCell.EMPTY`` 比较。
    EMPTY: Any = _EMPTY

    def __init__(self, value: Any = _EMPTY):
        """
        创建 cell。不传 ``value`` 时 cell 处于"未初始化"状态 (``is_empty()`` 为真)。

        Parameters
        ----------
        value : IbObject 或 IbCell.EMPTY
            初始持有值。约定调用方传入的应是已经 box 过的 ``IbObject`` 实例；
            本类不主动 box，以保持 "纯容器" 语义、避免对 registry 的依赖。
        """
        self._value = value

    # ------------------------------------------------------------------
    # 核心读写 API
    # ------------------------------------------------------------------

    def get(self) -> Any:
        """
        读取当前值。

        若 cell 尚未初始化，抛出 ``RuntimeError``。这对应于"读取未赋值的
        Cell 变量"——在正确实现的语义分析下不应发生，故视为 VM 内部错误。
        """
        if self._value is _EMPTY:
            raise RuntimeError(
                "IbCell read before initialization. "
                "This indicates a VM bug or incorrect free-variable analysis: "
                "a closure attempted to dereference a cell whose binding had "
                "not yet been established."
            )
        return self._value

    def set(self, new_value: Any) -> None:
        """
        写入新值。约定 ``new_value`` 应已是 box 过的 ``IbObject``；
        本方法不做类型/box 处理，类型一致性由调用方 (resolver/handler) 保证。
        """
        self._value = new_value

    def is_empty(self) -> bool:
        """是否处于未初始化状态。"""
        return self._value is _EMPTY

    # ------------------------------------------------------------------
    # GC 钩子 (M2 将依赖此方法构造根集合追踪图，公理 GC-2)
    # ------------------------------------------------------------------

    def trace_refs(self) -> Iterator[Any]:
        """
        枚举此 cell 直接持有的 IBCI 对象引用，供追踪式 GC 使用。

        当前实现仅有 ``value`` 一个槽位；未初始化时返回空迭代。
        未来若 cell 内嵌更多结构（例如 weak-ref 元数据），扩展此方法即可，
        调用方协议保持不变。
        """
        if self._value is not _EMPTY:
            yield self._value

    # ------------------------------------------------------------------
    # 身份语义：显式声明，提示阅读者
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:  # pragma: no cover - 平凡
        return self is other

    def __ne__(self, other: object) -> bool:  # pragma: no cover - 平凡
        return self is not other

    def __hash__(self) -> int:  # pragma: no cover - 平凡
        return id(self)

    # ------------------------------------------------------------------
    # 调试输出
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        if self._value is _EMPTY:
            return f"<IbCell #{id(self):x} EMPTY>"
        return f"<IbCell #{id(self):x} value={self._value!r}>"


__all__ = ["IbCell"]
