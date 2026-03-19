import json
from typing import Any
from core.extension import ibcext

class JSONLib(ibcext.IbPlugin):
    """
    JSON 2.1: JSON 处理插件。
    """
    def __init__(self):
        super().__init__()

    @ibcext.method("parse")
    def parse(self, s: str) -> Any:
        return json.loads(s)

    @ibcext.method("stringify")
    def stringify(self, obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)

def create_implementation():
    return JSONLib()
