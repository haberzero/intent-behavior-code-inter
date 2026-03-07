from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class TypeDescriptor:
    """
    UTS (Unified Type System) 基础描述符。
    仅包含类型的静态元数据，不包含任何执行逻辑。
    """
    name: str
    module_path: Optional[str] = None
    is_nullable: bool = True

    def is_assignable_to(self, other: 'TypeDescriptor') -> bool:
        """
        基于名称和路径的逻辑比较。
        UTS 的核心原则：类型兼容性由元数据决定，而非运行时对象引用。
        """
        if self.name in ("Any", "var") or other.name in ("Any", "var"):
            return True
        
        # 基础名称匹配
        if self.name == other.name and self.module_path == other.module_path:
            return True

        # [SPECIAL] 内置类型的特殊兼容性规则（原 IbClass.is_assignable_to 逻辑）
        if self.name == "int" and other.name == "bool":
            return True
        
        # 模拟 callable 兼容性
        if other.name == "callable":
             if self.name in ("function", "NativeFunction", "AnonymousLLMFunction", "behavior", "Module"):
                 return True

        return False

    def __str__(self):
        if self.module_path:
            return f"{self.module_path}.{self.name}"
        return self.name
