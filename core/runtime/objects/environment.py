"""
core/runtime/objects/environment.py

EnvironmentState —— 一等环境对象的运行期状态（frames 栈）。

B3（一等环境/作用域对象）的运行期状态载体：``environment`` 实例
（IbObject + ``_environment`` 槽）持有的 frames 栈结构。

语义契约：

- **frames 栈**：``[{key: value}, ...]``——最内层帧在尾部。读（get）自
  内向外查找（**内帧遮蔽外帧**——shadowing）；写（set/pop）作用于最内层帧。
- **值隔离**：set 入的值深拷贝存储（防外部变异污染——与 knowledge 条目
  冻结快照同一纪律：容器值可共享引用会破坏审计确定性）。
- **快照**：``fork()`` = 深拷贝（帧 + 值）——快照与原件双向隔离（定义时
  快照/序列化水化的状态语义基础）。
- **当前环境**：经 RuntimeContext 持有（``environment.get_current()`` /
  ``environment.use(env)`` 静态面——use 以 fork 语义替换，非引用绑定，
  与 intent_context.use 同构）。
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional


class EnvironmentState:
    """环境状态：frames 栈（最内层帧在尾部）。

    帧值为**原生**值（unbox 后的 Python 对象）——存值时深拷贝隔离，
    取值时返回深拷贝（读隔离与写隔离对称）。
    """

    __slots__ = ("_frames",)

    def __init__(self, frames: Optional[List[Dict[str, Any]]] = None):
        # 构造即深拷贝——外部 frames 容器不被共享（引用陷阱纪律）
        self._frames: List[Dict[str, Any]] = (
            [copy.deepcopy(f) for f in frames] if frames else []
        )

    # ------------------------------------------------------------------
    # 读（内→外 shadowing）
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """自内向外查找 key，返回值的深拷贝（缺失返回 None）。"""
        for frame in reversed(self._frames):
            if key in frame:
                return copy.deepcopy(frame[key])
        return None

    def contains(self, key: str) -> bool:
        for frame in reversed(self._frames):
            if key in frame:
                return True
        return False

    def keys(self) -> List[str]:
        """全部帧的键并集（内→外序，去重）。"""
        seen: set = set()
        result: List[str] = []
        for frame in reversed(self._frames):
            for k in frame:
                if k not in seen:
                    seen.add(k)
                    result.append(k)
        return result

    def len(self) -> int:
        """键数（遮蔽去重后）。"""
        return len(self.keys())

    def frames_count(self) -> int:
        return len(self._frames)

    # ------------------------------------------------------------------
    # 写（最内层帧，mutating）
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any) -> None:
        """向最内层帧写入（值深拷贝存储——写隔离）。"""
        if not self._frames:
            self._frames.append({})
        self._frames[-1][key] = copy.deepcopy(value)

    def pop(self, key: str) -> Optional[Any]:
        """自内向外移除并返回 key（值的深拷贝；缺失返回 None）。"""
        for frame in reversed(self._frames):
            if key in frame:
                value = frame[key]
                del frame[key]
                return copy.deepcopy(value)
        return None

    def clear(self) -> None:
        """清空全部帧（mutating）。"""
        self._frames = []

    def push_frame(self) -> None:
        """压入新空帧（嵌套作用域）。"""
        self._frames.append({})

    def pop_frame(self) -> Dict[str, Any]:
        """弹出最内层帧（返回其内容拷贝；空栈 no-op 返回空 dict）。"""
        if not self._frames:
            return {}
        return copy.deepcopy(self._frames.pop())

    # ------------------------------------------------------------------
    # 快照
    # ------------------------------------------------------------------

    def fork(self) -> "EnvironmentState":
        """深拷贝快照（帧 + 值双向隔离）。"""
        return EnvironmentState(self._frames)

    def merge_into(self, other: "EnvironmentState") -> None:
        """将本环境的内容合并进 other（帧序列追加 + 键并集覆盖）。

        用于 use 的替代形态/恢复路径；默认路径为 fork 整体替换。
        """
        for frame in self._frames:
            other._frames.append(copy.deepcopy(frame))

    def to_native(self) -> Dict[str, Any]:
        """原生形态：``{"frames": [...]}``（深拷贝）。"""
        return {"frames": copy.deepcopy(self._frames)}


# ----------------------------------------------------------------------
# 实例槽访问（单一权威——isinstance 精确判别，与 intent_context 先例同构）
# ----------------------------------------------------------------------

_ENV_STATE_FIELD = "_environment"


def get_env_state(obj: Any) -> Optional[EnvironmentState]:
    """environment 实例的 ``_environment`` 槽读取（isinstance 精确判别）。"""
    from core.runtime.objects.kernel import IbObject

    if not isinstance(obj, IbObject):
        return None
    state = obj.fields.get(_ENV_STATE_FIELD)
    return state if isinstance(state, EnvironmentState) else None


def set_env_state(obj: Any, state: EnvironmentState) -> None:
    """environment 实例的 ``_environment`` 槽写入（构造函数恒设置；
    缺失槽即内部不变量破坏）。"""
    obj.fields[_ENV_STATE_FIELD] = state


def require_env_state(obj: Any) -> EnvironmentState:
    """槽读取（缺失即 fail-fast——构造恒设置，缺失 = 内部不变量破坏）。"""
    from core.kernel.issue import InterpreterError

    state = get_env_state(obj)
    if state is None:
        raise InterpreterError(
            "environment instance is missing its '_environment' state "
            "(invariant violated: constructor must set it)."
        )
    return state
