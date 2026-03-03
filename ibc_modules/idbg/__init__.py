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
        # 优先从内核 LLM 执行器获取（包含合并后的 Prompts）
        if self._capabilities and self._capabilities.llm_executor:
            return self._capabilities.llm_executor.get_last_call_info()
            
        # 回退到从 Provider 获取
        if self._capabilities and self._capabilities.llm_provider:
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
        """返回对象（ClassInstance 或 Lambda）的内部细节"""
        from core.runtime.interpreter.runtime_types import ClassInstance, AnonymousLLMFunction
        if isinstance(obj, ClassInstance):
            return dict(obj.fields)
        
        if isinstance(obj, AnonymousLLMFunction):
            res = {
                "__type__": "lambda",
                "tag": obj.node.scene_tag.name if hasattr(obj.node, "scene_tag") else ""
            }
            if self._capabilities and self._capabilities.stack_inspector:
                res["captured_intents"] = self._capabilities.stack_inspector.get_captured_intents(obj)
            return res
            
        return {}

def create_implementation():
    return IDbgLib()
