"""``BaseCPSDrive`` —— CPS 驱动 Waitable 的统一底座。

各 Drive 类（用户调用 / llm 可调用 / 实例化 / 批处理 / 流式 / 迭代消费 /
生成器消费）对 ``is_done`` / ``try_result`` / ``result`` / ``register_wake``
的脚手架实现高度重复（同一 Waitable 协议机械复写）。本基类收敛该公共部分，
使各执行 drive 基于**同一统一底座**（消除"特例实现"气味），子类只需实现：

- ``cps_drive(executor)``：帧内 CPS 权威路径（VM ``yield from cps_drive``）；
- ``_drive()``：宿主/线程体同步兜底（无活跃 VM 时经 ``try_result`` / ``result``）。

子类在完成时设置 ``self._done = True`` 与 ``self._result``。

``register_wake`` 为可选通知钩子（task_scheduler 契约）：已完成则即时 set
（唤醒全等待 park）；未完成交给调度器轮询 + 安全超时兜底（不误报完成）。
"""


class BaseCPSDrive:
    """CPS 驱动 Waitable 的统一底座（Waitable + CPSDrivable 公共脚手架）。"""

    def __init__(self) -> None:
        self._done = False
        self._result = None

    @property
    def is_done(self) -> bool:
        return self._done

    def register_wake(self, event) -> None:
        if self._done:
            event.set()

    def try_result(self):
        if self._done:
            return (True, self._result)
        self._drive()
        return (True, self._result)

    def result(self):
        self._drive()
        return self._result

    def _drive(self):
        raise NotImplementedError(
            f"{type(self).__name__} must implement _drive (sync fallback)."
        )
