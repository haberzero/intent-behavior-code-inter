"""
IBCI Path - 统一的路径管理模块

完全独立于 Python os.path，实现跨平台路径操作。
这是 IBCI 与 Python 世界的唯一路径交互点。
"""
import os
from dataclasses import dataclass
from typing import Optional, Tuple, Union


@dataclass(frozen=True)
class IbPath:
    """
    IBCI 不可变路径对象

    设计原则：
    1. 不可变性 - 防止意外修改，支持安全的哈希和比较
    2. 规范化 - 统一路径表示，消除 . 和 .. 的歧义
    3. 平台无关 - 内部使用正斜杠作为分隔符

    与 Python 的交互：
    - from_native(): 从 Python/os 路径创建 IBCI 路径
    - to_native(): 将 IBCI 路径转换为 Python 路径
    """

    _normalized: str

    SEPARATOR: str = "/"
    ALT_SEPARATOR: str = "\\"

    def __post_init__(self):
        object.__setattr__(self, '_normalized', self._normalize(self._normalized))

    @staticmethod
    def _normalize(path: str) -> str:
        """内部路径规范化"""
        if not path:
            return ""

        normalized = path.replace(IbPath.ALT_SEPARATOR, IbPath.SEPARATOR)

        while "//" in normalized:
            normalized = normalized.replace("//", "/")

        if normalized == "/":
            return normalized

        if normalized.endswith("/") and len(normalized) > 1:
            normalized = normalized[:-1]

        return normalized

    @classmethod
    def from_native(cls, path: str) -> "IbPath":
        """
        从 Python/os 路径创建 IBCI 路径

        这是与 Python 世界的唯一交互点。
        将任意格式的路径转换为 IBCI 内部格式。

        参数:
            path: Python/os 格式的路径

        返回:
            IbPath: IBCI 规范化路径
        """
        if isinstance(path, cls):
            return path

        if not path:
            return cls(_normalized="")

        return cls(_normalized=cls._normalize(path))

    @classmethod
    def from_parts(cls, *parts: str) -> "IbPath":
        """
        从路径部分创建 IBCI 路径

        参数:
            *parts: 路径的各个部分

        返回:
            IbPath: 组合后的路径
        """
        if not parts:
            return cls(_normalized="")

        filtered_parts = [p.strip(IbPath.SEPARATOR) for p in parts if p and p != "."]
        normalized = IbPath.SEPARATOR.join(filtered_parts)

        if not normalized:
            return cls(_normalized="")

        first_part = parts[0]
        if len(first_part) >= 2 and first_part[1] == ":":
            normalized = first_part[0:2] + IbPath.SEPARATOR + normalized
        elif first_part.startswith(IbPath.SEPARATOR):
            normalized = IbPath.SEPARATOR + normalized

        return cls(_normalized=normalized)

    def to_native(self) -> str:
        """
        转换为原生 Python 路径

        仅在需要与 Python 交互时调用（如 open()、os.path.* 等）。

        返回:
            str: Python/os 格式的路径
        """
        if os.sep == IbPath.SEPARATOR:
            return self._normalized
        return self._normalized.replace(IbPath.SEPARATOR, os.sep)

    @property
    def is_absolute(self) -> bool:
        """是否绝对路径（支持 Unix 和 Windows）"""
        if not self._normalized:
            return False
        if self._normalized == IbPath.SEPARATOR:
            return True
        if self._normalized.startswith(IbPath.SEPARATOR):
            return True
        if len(self._normalized) >= 2 and self._normalized[1] == ":":
            return True
        return False

    @property
    def is_relative(self) -> bool:
        """是否相对路径"""
        return not self.is_absolute

    @property
    def parts(self) -> Tuple[str, ...]:
        """路径组成部分"""
        if not self._normalized:
            return tuple()
        if len(self._normalized) >= 2 and self._normalized[1] == ":":
            return tuple(self._normalized[2:].split(IbPath.SEPARATOR))
        if self._normalized.startswith(IbPath.SEPARATOR):
            return tuple(self._normalized[1:].split(IbPath.SEPARATOR))
        return tuple(self._normalized.split(IbPath.SEPARATOR))

    @property
    def name(self) -> str:
        """文件名或目录名（最后一部分）"""
        parts = self.parts
        return parts[-1] if parts else ""

    @property
    def parent(self) -> Optional["IbPath"]:
        """父目录"""
        parts_list = list(self.parts)
        if len(parts_list) <= 1:
            if self.is_absolute:
                return IbPath(_normalized=IbPath.SEPARATOR)
            return None

        parts_list.pop()
        if not parts_list:
            return IbPath(_normalized="")

        if self.is_absolute:
            return IbPath(_normalized=IbPath.SEPARATOR + IbPath.SEPARATOR.join(parts_list))
        return IbPath(_normalized=IbPath.SEPARATOR.join(parts_list))

    def join(self, *others: Union[str, "IbPath"]) -> "IbPath":
        """
        路径连接

        参数:
            *others: 要连接的路径部分

        返回:
            IbPath: 连接后的路径
        """
        if not others:
            return self

        all_parts = list(self.parts)
        for other in others:
            if isinstance(other, str):
                other_path = IbPath.from_native(other)
            else:
                other_path = other
            all_parts.extend(other_path.parts)

        if not all_parts:
            return IbPath(_normalized="")

        if len(self._normalized) >= 2 and self._normalized[1] == ":":
            drive = self._normalized[0:2]
            return IbPath(_normalized=drive + IbPath.SEPARATOR + IbPath.SEPARATOR.join(all_parts))

        if self.is_absolute:
            return IbPath(_normalized=IbPath.SEPARATOR + IbPath.SEPARATOR.join(all_parts))

        return IbPath(_normalized=IbPath.SEPARATOR.join(all_parts))

    def startswith(self, other: "IbPath") -> bool:
        """检查路径是否以指定前缀开始"""
        if not other._normalized:
            return True

        self_str = self._normalized.rstrip(IbPath.SEPARATOR)
        other_str = other._normalized.rstrip(IbPath.SEPARATOR)

        if not self_str or not other_str:
            return False

        self_str += IbPath.SEPARATOR
        other_str += IbPath.SEPARATOR

        return self_str.startswith(other_str)

    def endswith(self, other: "IbPath") -> bool:
        """检查路径是否以指定后缀结束"""
        if not other._normalized:
            return True
        return self._normalized.endswith(other._normalized)

    def resolve_dot_segments(self) -> "IbPath":
        """解析路径中的 . 和 .. 片段"""
        if not self._normalized:
            return self

        parts_list = []
        for part in self.parts:
            if part == "..":
                if parts_list and parts_list[-1] != "..":
                    parts_list.pop()
            elif part != "." and part:
                parts_list.append(part)

        if not parts_list:
            return IbPath(_normalized="")

        if self.is_absolute:
            return IbPath(_normalized=IbPath.SEPARATOR + IbPath.SEPARATOR.join(parts_list))
        return IbPath(_normalized=IbPath.SEPARATOR.join(parts_list))

    def __str__(self) -> str:
        """字符串表示"""
        return self._normalized

    def __repr__(self) -> str:
        """调试表示"""
        return f"IbPath('{self._normalized}')"

    def __eq__(self, other) -> bool:
        """相等比较"""
        if isinstance(other, IbPath):
            return self._normalized == other._normalized
        if isinstance(other, str):
            return self._normalized == IbPath._normalize(other)
        return False

    def __hash__(self) -> int:
        """哈希值"""
        return hash(self._normalized)

    def __add__(self, other: str) -> "IbPath":
        """路径连接（+ 操作符）"""
        if isinstance(other, IbPath):
            return self.join(other)
        return self.join(IbPath.from_native(other))

    def __truediv__(self, other: Union[str, "IbPath"]) -> "IbPath":
        """路径连接（/ 操作符）"""
        return self.join(other)
