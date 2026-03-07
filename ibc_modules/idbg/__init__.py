from typing import Dict, Any, Optional
from core.foundation.capabilities import ExtensionCapabilities

class IDbgLib:
    def __init__(self):
        self._capabilities: Optional[ExtensionCapabilities] = None

    def setup(self, capabilities: ExtensionCapabilities):
        self._capabilities = capabilities

    def vars(self) -> Any:
        """返回当前作用域变量的详细信息（原生 dict 格式）"""
        if not self._capabilities or not self._capabilities.state_reader:
            return {}
        return self._capabilities.state_reader.get_vars_snapshot()

    def last_llm(self) -> Dict[str, Any]:
        """返回最后一次 LLM 调用信息"""
        if not self._capabilities:
            return {}
        
        # 优先从内核 LLM 执行器获取（包含合并后的 Prompts）
        if self._capabilities.llm_executor:
            return self._capabilities.llm_executor.get_last_call_info()
            
        # 回退到从 Provider 获取
        if self._capabilities.llm_provider:
            return self._capabilities.llm_provider.get_last_call_info()
        
        return {}

    def env(self) -> Dict[str, Any]:
        """返回解释器环境信息"""
        if not self._capabilities or not self._capabilities.stack_inspector:
            return {}
            
        inspector = self._capabilities.stack_inspector
        return {
            "instruction_count": inspector.get_instruction_count(),
            "call_stack_depth": inspector.get_call_stack_depth(),
            "active_intents": inspector.get_active_intents()
        }

    def fields(self, obj: Any) -> Dict[str, Any]:
        """返回对象（IbObject）的内部细节。测试用例期望原生值。"""
        from core.foundation.kernel import IbObject
        if isinstance(obj, IbObject):
            # 优先使用专门的调试序列化方法
            if hasattr(obj, 'serialize_for_debug'):
                data = obj.serialize_for_debug()
            else:
                data = obj.fields
            
            # 递归转换为原生值，对齐测试用例期望
            def _to_native(v):
                if hasattr(v, 'to_native'): return v.to_native()
                if isinstance(v, dict): return {k: _to_native(i) for k, i in v.items()}
                if isinstance(v, list): return [_to_native(i) for i in v]
                return v
                
            return {k: _to_native(v) for k, v in data.items()}
        return {}

def create_implementation():
    return IDbgLib()
