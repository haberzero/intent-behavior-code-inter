from enum import Enum
from typing import List, Optional, Any, Protocol, Union

class IntentMode(Enum):
    """意图合并模式"""
    APPEND = "+"    # 叠加 (默认)
    OVERRIDE = "!"  # 排他 (覆盖之前的所有意图)
    REMOVE = "-"    # 移除 (从栈中移除匹配的意图)

    @classmethod
    def from_str(cls, mode_val: Union[str, 'IntentMode']) -> 'IntentMode':
        """从字符串或枚举映射模式，支持多种别名"""
        if isinstance(mode_val, cls): return mode_val
        if not mode_val: return cls.APPEND
        m = str(mode_val).lower()
        if m in ("+", "append", "add"): return cls.APPEND
        if m in ("!", "override", "exclusive"): return cls.OVERRIDE
        if m in ("-", "remove", "delete"): return cls.REMOVE
        return cls.APPEND # 默认叠加

class IntentRole(Enum):
    """意图来源角色"""
    BLOCK = "block"      # 意图块 (intent "..." { ... })
    SMEAR = "smear"      # 涂抹式注释 (@ ...)
    CALL = "call"        # 函数调用时携带的意图 (func(...) @ ...)
    GLOBAL = "global"    # 全局意图 (context.set_global_intent)
    DYNAMIC = "dynamic"  # 编程式动态推入 (context.push_intent)

class IntentProtocol(Protocol):
    """
    意图对象的通用协议。
    允许编译器 (IbIntentInfo) 和运行时 (IbIntent) 使用同一套合并算法。
    """
    @property
    def content(self) -> str: ...
    @property
    def tag(self) -> Optional[str]: ...
    @property
    def mode(self) -> IntentMode: ...
    
    @property
    def is_override(self) -> bool:
        return self.mode == IntentMode.OVERRIDE

    @property
    def is_remove(self) -> bool:
        return self.mode == IntentMode.REMOVE

    def resolve_content(self, context: Any, evaluator: Any = None) -> str:
        """解析意图内容 (可能涉及动态评估)"""
        ...
