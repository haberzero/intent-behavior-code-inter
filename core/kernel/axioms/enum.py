from typing import Optional, Tuple, Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.kernel.types.descriptors import TypeDescriptor, FunctionMetadata

from core.kernel.axioms.protocols import FromPromptCapability, IlmoutputHintCapability

class EnumAxiom(FromPromptCapability, IlmoutputHintCapability):
    """enum 类型的行为公理
    
    Enum 公理的 __llmoutput_hint__ 和 from_prompt 方法是动态的——
    它们在运行时查询具体枚举类的成员，自动生成提示和解析逻辑。
    """

    @property
    def name(self) -> str:
        return "enum"

    def get_parent_axiom_name(self) -> Optional[str]:
        return None

    def get_from_prompt_capability(self) -> Optional['FromPromptCapability']:
        return self

    def get_llmoutput_hint_capability(self) -> Optional['IlmoutputHintCapability']:
        return self

    def get_methods(self) -> Dict[str, 'FunctionMetadata']:
        return {}

    def get_call_capability(self) -> Optional['CallCapability']:
        return None

    def get_iter_capability(self) -> Optional['IterCapability']:
        return None

    def get_subscript_capability(self) -> Optional['SubscriptCapability']:
        return None

    def can_return_from_isolated(self) -> bool:
        return True

    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        return other.get_base_axiom_name() == "enum"

    def is_dynamic(self) -> bool:
        return False

    def is_class(self) -> bool:
        return False

    def is_module(self) -> bool:
        return False

    def get_base_axiom_name(self) -> str:
        return "enum"

    def _collect_enum_values(self, descriptor: Optional['TypeDescriptor']) -> List[str]:
        """从描述符收集枚举值名称"""
        if descriptor is None:
            return []
        
        members = getattr(descriptor, 'members', None)
        if not members:
            return []
        
        enum_values = []
        for name in members:
            if name.isupper() and not name.startswith('_'):
                enum_values.append(name)
        
        return enum_values

    def __llmoutput_hint__(self, descriptor: Optional['TypeDescriptor'] = None) -> str:
        """动态生成 LLM 输出约束"""
        enum_values = self._collect_enum_values(descriptor)
        
        if not enum_values:
            return "请回复有效的枚举值"
        
        if len(enum_values) == 1:
            return f"请只回复 {enum_values[0]}"
        
        if len(enum_values) == 2:
            return f"请只回复 {enum_values[0]} 或 {enum_values[1]}"
        
        values_str = ", ".join(enum_values[:-1]) + f" 或 {enum_values[-1]}"
        return f"请只回复 {values_str} 之一"

    def from_prompt(self, raw_response: str, descriptor: Optional['TypeDescriptor'] = None) -> Tuple[bool, Any]:
        """动态解析 LLM 输出为枚举值"""
        if descriptor is None:
            return (False, "无法解析枚举值：缺少类型信息")
        
        members = getattr(descriptor, 'members', None)
        if not members:
            return (False, "无法解析枚举值：类型缺少成员信息")
        
        val = raw_response.strip().upper()
        
        for name in members:
            if name.upper() == val:
                return (True, name)
        
        valid_values = ", ".join(self._collect_enum_values(descriptor)[:5])
        if len(self._collect_enum_values(descriptor)) > 5:
            valid_values += " 等"
        
        return (False, f"无法解析 '{raw_response}'，请回复有效枚举值如: {valid_values}")
