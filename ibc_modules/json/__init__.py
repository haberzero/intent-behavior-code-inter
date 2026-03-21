"""
[IES 2.2] JSON 处理插件

纯 Python 实现，零侵入。
"""
import json
from typing import Any


class JSONLib:
    """
    [IES 2.2] JSON 2.2: JSON 处理插件。
    不继承任何核心类，完全独立。
    """
    def parse(self, s: str) -> Any:
        return json.loads(s)

    def stringify(self, obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)


def create_implementation():
    return JSONLib()
