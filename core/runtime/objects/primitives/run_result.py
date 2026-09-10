"""
core/runtime/objects/primitives/run_result.py

IbRunResult —— 子进程子运行结果值对象（一等不可变值类型）。

``run_result`` 是 ``ihost.run_file`` / ``ihost.run_code`` 的返回值：独立子进程
隔离子运行的结果记录，**错误作值**（子失败不抛穿父，与 run_isolated 的错误作异常
+ 变量字典互补）。三**字段**（record 固定面，attribute 访问）：

- ``exit_status: str``（``"ok"`` / ``"error"``）
- ``stdout: str``（子 print 输出捕获，不经父 stdout 直接面）
- ``exception: any``（``None`` 或结构化 dict ``{code, message, source{...}}``——
  与 CLI ``--result-json`` exception 面同构，单一权威源
  ``core/runtime/exception_record.py``）

语义契约：

- **不可变值类型**：无修改字段面（结果 = 子运行的冻结快照）；deep_clone 走不可变
  引用复用（同 vector 纪律）。
- **值语义**：按三字段值相等（经原生 payload 比较）；``__hash__ = None``（不作
  dict 键/set 成员）。
- **字段访问**：``r.exit_status`` / ``r.stdout`` / ``r.exception``——字段值装箱
  存于 ``obj.fields``，经 ``_dispatch_getattr`` 实例字段优先命中（无括号访问，
  Exception.message 先例）；``exception`` 字段装箱 IbDict/None。
- **零 I/O 面**：纯内存值类型（fs/沙箱无交互）。

字段面由 ``RunResultAxiom`` 声明（``kind="field"``），``_dispatch_getattr`` 提供
attribute 访问；方法面（cast_to/__to_prompt__）经 axiom-driven auto-bind 绑定。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject, IbValue
from core.runtime.objects.ib_type_mapping import register_ib_type


@register_ib_type("run_result")
class IbRunResult(IbValue):
    """子进程子运行结果值对象。

    ``payload`` = 原生结构 ``{"exit_status": str, "stdout": str,
    "exception": dict-or-None}``（序列化/边界 to_native 消费）；``fields`` = 三
    字段装箱值（``exit_status``/``stdout`` 装箱 str，``exception`` 装箱 IbDict/None
    ——经 ``_dispatch_getattr`` 提供 ``r.exit_status`` 等 attribute 访问）。
    """

    __slots__ = ()

    def __init__(
        self,
        ib_class: "IbObject",
        exit_status: str = "ok",
        stdout: str = "",
        exception: Optional[Any] = None,
        payload: Optional[Dict[str, Any]] = None,
    ):
        if payload is not None:
            # 序列化水化直传（原生结构；字段据此重建装箱）
            exit_status = payload.get("exit_status", "ok")
            stdout = payload.get("stdout", "")
            exception = payload.get("exception")
        reg = ib_class.registry
        super().__init__(
            ib_class,
            payload={
                "exit_status": exit_status,
                "stdout": stdout,
                "exception": exception,
            },
            fields={
                "exit_status": reg.box(exit_status),
                "stdout": reg.box(stdout),
                "exception": (
                    reg.box(exception) if exception is not None else reg.get_none()
                ),
            },
        )

    # ------------------------------------------------------------------ #
    # 值语义（相等/哈希——经原生 payload 比较）
    # ------------------------------------------------------------------ #

    def _fields(self) -> tuple:
        return (
            self.payload.get("exit_status"),
            self.payload.get("stdout"),
            self.payload.get("exception"),
        )

    def __eq__(self, other: "IbRunResult") -> bool:
        if not isinstance(other, IbRunResult):
            return NotImplemented
        return self._fields() == other._fields()

    def __ne__(self, other: "IbRunResult") -> bool:
        if not isinstance(other, IbRunResult):
            return NotImplemented
        return self._fields() != other._fields()

    __hash__ = None  # 显式不可哈希（不作 dict 键/set 成员）

    # ------------------------------------------------------------------ #
    # 拆箱 / 序列化
    # ------------------------------------------------------------------ #

    def to_native(self, memo=None) -> Dict[str, Any]:
        # 结果记录 = 不可变值类型：原生表征 = 三字段原生结构（序列化/边界消费）
        return {
            "exit_status": self.payload["exit_status"],
            "stdout": self.payload["stdout"],
            "exception": self.payload["exception"],
        }

    def __to_prompt__(self) -> str:
        """提示词面渲染（截断摘要——stdout 全量进提示词 = 污染风险）。"""
        exc = self.payload["exception"]
        exc_repr = "none"
        if exc is not None:
            code = exc.get("code") if isinstance(exc, dict) else None
            exc_repr = code if code else "error"
        out = self.payload["stdout"]
        preview = out[:40].replace("\n", "\\n") + ("..." if len(out) > 40 else "")
        return (
            f"run_result(status={self.payload['exit_status']}, "
            f"exception={exc_repr}, stdout={preview!r})"
        )

    def cast_to(self, target_class) -> IbObject:
        if target_class.name in ("run_result", "any"):
            return self
        if target_class.name == "str":
            return self.ib_class.registry.box(self.__to_prompt__())
        raise InterpreterError(
            f"TypeError: Cannot cast 'run_result' to '{target_class.name}' "
            f"(str/any 转换受支持)。",
        )

    def serialize_for_debug(self):
        exc = self.payload["exception"]
        exc_code = exc.get("code") if isinstance(exc, dict) else None
        return {
            "type": "run_result",
            "exit_status": self.payload["exit_status"],
            "exception_code": exc_code,
            "stdout_len": len(self.payload["stdout"]),
        }

    def __repr__(self):
        return self.__to_prompt__()
