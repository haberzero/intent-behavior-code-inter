from typing import Dict, Any, Optional
from core.runtime.ext.capabilities import ExtensionCapabilities

class IDbgLib:
    def __init__(self):
        self._capabilities: Optional[ExtensionCapabilities] = None

    def setup(self, capabilities: ExtensionCapabilities):
        self._capabilities = capabilities

    def vars(self) -> Dict[str, Any]:
        """返回当前可见的所有变量信息（支持嵌套作用域）"""
        if not self._capabilities or not self._capabilities.state_reader:
            return {}
        
        # 使用标准化能力接口获取快照，不再自己实现回溯逻辑
        return self._capabilities.state_reader.get_vars_snapshot()

    def last_llm(self) -> Dict[str, Any]:
        """返回最后一次 LLM 调用信息"""
        if not self._capabilities or not self._capabilities.llm_provider:
            return {}
        
        return self._capabilities.llm_provider.get_last_call_info()

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

def create_implementation():
    return IDbgLib()
