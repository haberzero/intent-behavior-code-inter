from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from core.foundation.source_atomic import Location
from core.runtime.objects.kernel import IbObject
from core.runtime.objects.intent import IbIntent

@dataclass
class StackFrame:
    """表示一个逻辑调用栈帧"""
    name: str                   # 函数名或模块名
    local_vars: Dict[str, Any]  # 当前帧的局部变量快照
    location: Optional[Location] # 当前执行到的源码位置 (PC)
    intent_stack: List[str]      # 当前帧活跃的意图栈
    is_user_function: bool = False # 是否为用户定义的函数

class LogicalCallStack:
    """
    IBCI 逻辑调用栈。
    不直接替代 Python 递归，但通过显式记录栈帧，实现：
    1. 类 GDB 的回溯 (Backtrace)
    2. 上下文快照 (Core Dump)
    3. 动态宿主重启恢复
    """
    def __init__(self, max_depth: int = 100):
        self.frames: List[StackFrame] = []
        self.max_depth = max_depth

    def push(self, name: str, local_vars: Dict[str, Any], 
             location: Optional[Location] = None, 
             intent_stack: Optional[List[str]] = None,
             is_user_function: bool = False):
        if len(self.frames) >= self.max_depth:
            raise RecursionError(f"IBCI Logical CallStack Overflow: depth > {self.max_depth}")
        
        frame = StackFrame(
            name=name,
            local_vars=local_vars,
            location=location,
            intent_stack=intent_stack or [],
            is_user_function=is_user_function
        )
        self.frames.append(frame)

    def pop(self) -> StackFrame:
        if not self.frames:
            raise IndexError("IBCI Logical CallStack Underflow")
        return self.frames.pop()

    @property
    def current_frame(self) -> Optional[StackFrame]:
        return self.frames[-1] if self.frames else None

    @property
    def depth(self) -> int:
        return len(self.frames)

    def get_backtrace(self) -> List[StackFrame]:
        """返回当前调用栈的副本（从顶到底）"""
        return list(reversed(self.frames))
