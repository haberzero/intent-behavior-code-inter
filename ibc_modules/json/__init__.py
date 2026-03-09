import json
from typing import Any
from core.extension import sdk as ibci

class JSONLib:
    @ibci.method("parse")
    def parse(self, s: str) -> Any:
        return json.loads(s)
    
    @ibci.method("stringify")
    def stringify(self, obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)

# Export the implementation
implementation = JSONLib()
