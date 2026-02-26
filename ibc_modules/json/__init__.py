import json
from typing import Any

class JSONLib:
    @staticmethod
    def parse(s: str) -> Any:
        return json.loads(s)
    
    @staticmethod
    def stringify(obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)

# Export the implementation
implementation = JSONLib()
