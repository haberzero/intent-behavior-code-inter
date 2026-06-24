from typing import Any
from ..kernel import IbObject, IbValue
from ..ib_type_mapping import register_ib_type

@register_ib_type("Exception")
class IbException(IbValue):
    """Exception 类型的运行时实现"""
    
    def message(self) -> IbObject:
        msg = self.fields.get("message")
        if msg: return msg
        return self.ib_class.registry.box("")

    def cast_to(self, target_class: Any) -> IbObject:
        """ 支持 Exception 的强转逻辑"""
        if target_class.name in ("str", "any"):
            msg = self.fields.get("message")
            if msg: return msg
            return self.ib_class.registry.box("Exception")
        return self
