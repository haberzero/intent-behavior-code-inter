import json
from typing import Any
from core.extension import sdk as ibci

class JSONLib(ibci.IbPlugin):
    """
    JSON 2.1: JSON 处理插件。
    """
    def __init__(self):
        super().__init__()

    @ibci.method("parse")
    def parse(self, s: str) -> Any:
        return json.loads(s)
    
    @ibci.method("stringify")
    def stringify(self, obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)

def create_implementation():
    return JSONLib()
