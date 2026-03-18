from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional

# --- 基础严重程度 (Foundation) ---

class Severity(Enum):
    HINT = auto()    # 优化建议
    INFO = auto()    # 编译过程信息
    WARNING = auto() # 可能的问题
    ERROR = auto()   # 语法/语义错误
    FATAL = auto()   # 内部错误

# --- 物理位置信息 (Foundation) ---

@dataclass
class Location:
    """
    IBC-Inter 物理位置信息。
    """
    file_path: Optional[str] = None
    line: int = 0
    column: int = 0
    length: int = 1
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    context_line: Optional[str] = None

    def __str__(self):
        loc_str = f"line {self.line}, column {self.column}"
        if self.file_path:
            return f"{self.file_path}:{loc_str}"
        return loc_str
